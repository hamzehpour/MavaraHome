from datetime import datetime, timedelta, timezone

from database.repositories import reservations as reservations_repo
from database.repositories import waitlist as waitlist_repo
from database.repositories import users as users_repo
from database.repositories import sessions as sessions_repo
from database.repositories import settings as settings_repo
from services import settings_service


def _expiry_timestamp() -> str:
    minutes = settings_repo.get_int("payment_expiry_minutes", 60)
    return (datetime.now(timezone.utc) + timedelta(minutes=minutes)).isoformat(timespec="seconds")


def start_reservation(telegram_id: int, session_id: int, people: int,
                       attendee_name: str | None = None, attendee_phone: str | None = None) -> dict:
    """Telegram-originated booking. Thin wrapper around _create_reservation_for_user
    — see that function for the actual logic, shared with the website path
    (start_reservation_web) so capacity/pricing/atomicity is never duplicated."""
    user = users_repo.get_or_create_user(telegram_id)
    return _create_reservation_for_user(user, session_id, people, source="telegram",
                                         attendee_name=attendee_name, attendee_phone=attendee_phone)


def start_reservation_web(phone: str, full_name: str, session_id: int, people: int,
                           email: str | None = None) -> dict:
    """Website-originated booking (Phase 1: unified backend). Same reservation
    core as the Telegram path — capacity check, pricing, atomic insert are
    ALL the same code, just identified by phone instead of telegram_id since
    a website visitor has no Telegram account yet. `source='website'` is
    what lets the admin/monitoring tell the two apart.

    `email` (reservation-migration phase 3): collected in the same booking
    form now, specifically so this goes through get_or_create_customer()
    (phase 0) instead of the phone-only lookup — the buyer's account is
    created/matched by email right here, at booking time, rather than
    needing a separate "log in later and hope it resolves to the same
    row" step. This is the actual fix for the "reservation archive is
    empty" finding: without an email attached from the start, a
    phone-only booking has no login path back to it at all, since login
    is email-only (see customer_auth_service)."""
    from validators.validators import normalize_phone
    normalized = normalize_phone(phone)
    user = users_repo.get_or_create_customer(email=email, phone=normalized, full_name=full_name)
    return _create_reservation_for_user(user, session_id, people, source="website",
                                         attendee_name=None, attendee_phone=None)


def _create_reservation_for_user(user: dict, session_id: int, people: int, source: str,
                                  attendee_name: str | None, attendee_phone: str | None) -> dict:
    """
    Creates the reservation (or waitlist entry if the session is full).
    Capacity check + insert are atomic — see repositories/reservations.py.
    A payment deadline (expires_at) is attached so the background expiry
    job can free the seats back up if the person never pays.
    attendee_name/attendee_phone are only set when the buyer is booking on
    behalf of someone else — the buyer's own account (full_name/phone) is
    never overwritten by that case.
    """
    session = sessions_repo.get_session(session_id)
    if not session:
        return {"success": False, "waiting": False, "error": "session_not_found"}

    from database.repositories import events as events_repo
    from services import event_service
    event = events_repo.get_event(session["event_id"])
    unit_price, currency = event_service.get_effective_price(event) if event else (settings_service.get_ticket_price(), "تومان")
    result = reservations_repo.create_reservation_locked(
        user_id=user["id"],
        session_id=session_id,
        people=people,
        unit_price=unit_price,
        capacity=session["capacity"],
        status="pending_payment",
        source=source,
        expires_at=_expiry_timestamp(),
        attendee_name=attendee_name,
        attendee_phone=attendee_phone,
    )

    if not result["success"] and result["waiting"]:
        waitlist_id = waitlist_repo.add(user_id=user["id"], session_id=session_id, people=people, source=source)
        result["waitlist_id"] = waitlist_id
        _notify_admin_channel_new_waitlist(waitlist_id)

    result["user_id"] = user["id"]
    result["unit_price"] = unit_price
    result["currency"] = currency
    return result


def create_manual_reservation(operator_telegram_id: int, session_id: int, people: int,
                                full_name: str, phone: str) -> dict:
    """
    A phone/walk-in booking taken by support staff. Skips the payment-proof
    step entirely (staff confirmed payment or cash themselves) and issues
    the ticket immediately, so it goes straight to 'approved'.
    """
    from services.ticket_service import issue_ticket

    user = users_repo.get_or_create_by_phone(phone=phone, full_name=full_name)
    session = sessions_repo.get_session(session_id)
    if not session:
        return {"success": False, "waiting": False, "error": "session_not_found"}

    unit_price = settings_service.get_ticket_price()
    result = reservations_repo.create_reservation_locked(
        user_id=user["id"],
        session_id=session_id,
        people=people,
        unit_price=unit_price,
        capacity=session["capacity"],
        status="approved",
        source="phone",
        created_by_staff=operator_telegram_id,
    )

    if not result["success"] and result["waiting"]:
        waitlist_repo.add(user_id=user["id"], session_id=session_id, people=people, source="phone")
        return result

    if result["success"]:
        code, _ = issue_ticket(result["reservation_id"])
        result["reservation_code"] = code

    result["unit_price"] = unit_price
    return result


def submit_receipt(reservation_id: int, receipt_file_id: str, receipt_source: str = "telegram") -> bool:
    """
    receipt_source distinguishes a Telegram file_id from a website upload
    (a relative path under private_media/receipts/) — the two need
    different handling to actually display as a photo (a bare path means
    nothing to Telegram's API, only an upload does), which
    _notify_admin_channel_new_request() below takes care of when it
    builds the channel alert's photo_ref.

    Accepts a receipt from two starting states: the normal first-time
    'pending_payment' (buyer just booked), or 'needs_correction' (admin
    used the "نیازمند اصلاح" action — see request_correction() below —
    and the buyer is resubmitting a fixed receipt; no time limit applies
    there, so this can fire any time after that). Either way it lands on
    'pending_review'. Returns False (and does nothing) if the reservation
    is in neither state — e.g. the buyer sent a second photo right after
    the first, or resubmitted after it was already re-reviewed. Without
    this, a duplicate send would notify every admin a second time for the
    same reservation.
    """
    from database.repositories import payments as payments_repo

    reservation = reservations_repo.get_reservation(reservation_id)
    if not reservation or reservation["status"] not in ("pending_payment", "needs_correction"):
        return False
    transitioned = reservations_repo.set_status_if(reservation_id, reservation["status"], "pending_review")
    if not transitioned:
        return False

    reservation = reservations_repo.get_reservation(reservation_id)
    payments_repo.create_payment(
        reservation_id=reservation_id,
        receipt_file_id=receipt_file_id,
        amount=reservation["total_price"],
        receipt_source=receipt_source,
    )
    _notify_admin_channel_new_request(reservation, receipt_file_id, receipt_source)
    return True


def request_correction(reservation_id: int, reviewed_by: int, message: str) -> bool:
    """Third admin action alongside approve/reject, for a reservation the
    admin can't approve as-is (wrong receipt, wrong amount, illegible
    photo...) but doesn't want to reject outright either — sends the
    buyer `message` (both by email and, if they have a linked Telegram
    account, a DM) explaining what to fix, and waits: unlike
    'pending_payment', 'needs_correction' has NO time limit (see
    reservations_repo.list_expired_pending — it only ever matches
    'pending_payment') and never auto-expires. The buyer resubmits
    through the exact same receipt-upload path as the first time (see
    submit_receipt() above, which now accepts 'needs_correction' as a
    starting status too), landing back on 'pending_review' for the admin
    to make a final call.

    Accepts from 'pending_review' OR an existing 'needs_correction' — the
    latter lets an admin send a second/follow-up correction message (the
    buyer's resubmission still wasn't right, or they just want to add more
    detail) without first waiting for a resubmission that moves it back to
    pending_review. Returns False (does nothing) if the reservation is in
    neither state — e.g. a double-tap, or it was already resolved
    (approved/rejected) by another admin in the meantime."""
    from database.repositories import payments as payments_repo
    from database.repositories import users as users_repo

    transitioned = reservations_repo.set_status_if_any(
        reservation_id, ("pending_review", "needs_correction"), "needs_correction", admin_note=message,
    )
    if not transitioned:
        return False

    payment = payments_repo.get_latest_payment(reservation_id)
    if payment:
        payments_repo.set_payment_status(payment["id"], "needs_correction", reviewed_by)

    reservation = reservations_repo.get_reservation(reservation_id)
    ctx = _email_context_for_reservation(reservation)
    subject, body = settings_service.render_email(
        "needs_correction", event_title=ctx["event_title"], correction_message=message,
    )
    _notify_customer_by_email(reservation, subject=subject, body=body)

    user = users_repo.get_by_id(reservation["user_id"])
    if user and user.get("telegram_id"):
        from database.repositories import bot_outbox as outbox_repo
        outbox_repo.enqueue(
            user["telegram_id"],
            f"✏️ رزرو شما نیاز به اصلاح دارد:\n\n{message}\n\n"
            "لطفاً از طریق منوی «رزروهای من» رسید اصلاح‌شده را دوباره ارسال کنید.",
        )
    return True


def send_payment_reminders() -> int:
    """Reservations still sitting in 'pending_payment' past
    `payment_reminder_minutes` since they were created (but not expired
    yet) get a one-time email nudging the buyer that the clock is
    running out. Runs from BOTH the async bot loop and the sync API-
    process loop (see utils/scheduler.py) since it's plain email — no
    live aiogram Bot instance needed the way a Telegram DM would be, so
    unlike the bot-only chores in run_expiry_loop this one works even
    when bot.py isn't running. Dedup via the `logs` table (one row per
    reservation, checked before sending) rather than a new column — a
    single one-time nudge, not a repeating alarm, so nothing else needs
    tracking. Returns how many were actually sent, for the caller to log."""
    from database.connection import get_connection
    from database.repositories import settings as settings_repo

    remind_after = settings_repo.get_int("payment_reminder_minutes", 5)
    expiry_minutes = settings_repo.get_int("payment_expiry_minutes", 10)
    minutes_remaining = str(max(1, expiry_minutes - remind_after))

    sent = 0
    with get_connection() as conn:
        # created_at is stored via SQLite's own datetime('now') (space-
        # separated, no offset) — comparing it against a Python-side
        # isoformat() cutoff ("...T...+00:00") silently never matches
        # (different string shapes sort differently), so the cutoff has
        # to be computed with SQLite's own datetime() too, the same way
        # both sides end up in the same format.
        due = conn.execute(
            "SELECT id FROM reservations WHERE status = 'pending_payment' "
            "AND created_at < datetime('now', ?)",
            (f"-{remind_after} minutes",),
        ).fetchall()

        for row in due:
            already = conn.execute(
                "SELECT 1 FROM logs WHERE action = 'payment_reminder_sent' AND details = ? LIMIT 1",
                (str(row["id"]),),
            ).fetchone()
            if already:
                continue

            reservation = reservations_repo.get_reservation(row["id"])
            if not reservation or reservation["status"] != "pending_payment":
                continue
            ctx = _email_context_for_reservation(reservation)
            subject, body = settings_service.render_email(
                "payment_reminder", event_title=ctx["event_title"], minutes_remaining=minutes_remaining,
            )
            if _notify_customer_by_email(reservation, subject=subject, body=body):
                conn.execute(
                    "INSERT INTO logs(action, telegram_id, details) VALUES ('payment_reminder_sent', NULL, ?)",
                    (str(row["id"]),),
                )
                sent += 1
    return sent


def _email_context_for_reservation(reservation: dict) -> dict:
    """event title + human-readable session date/time for a notification
    email — same join shape as get_user_reservations() above, just for
    one reservation instead of a whole list."""
    from database.connection import get_connection
    from utils.jalali import display_date_for_event

    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT s.session_date, s.session_time, e.title AS event_title, e.calendar_type
            FROM reservations r
            JOIN sessions s ON s.id = r.session_id
            JOIN events e ON e.id = s.event_id
            WHERE r.id = ?
            """,
            (reservation["id"],),
        ).fetchone()
    if not row:
        return {"event_title": "", "session_date": "", "session_time": ""}
    return {
        "event_title": row["event_title"],
        "session_date": display_date_for_event(row["session_date"], row["calendar_type"]),
        "session_time": row["session_time"],
    }


def _notify_admin_channel_new_request(reservation: dict, receipt_file_id: str, receipt_source: str) -> None:
    """Instant channel alert (see settings_service.notify_admin_channel*)
    the moment a reservation reaches pending_review — i.e. the buyer has
    submitted a receipt and staff actually need to look at it. Called
    from submit_receipt() itself so it fires the same way whether the
    receipt came from the Telegram bot or the website, unlike the
    existing photo+buttons DM in handlers/payment.py which is Telegram-
    only and never reaches website-submitted receipts at all.

    Includes the receipt image and the same approve/reject buttons that
    DM already has (requested: an admin should be able to act right from
    the channel) — `photo_ref` tells utils/scheduler._deliver_receipt_review
    how to resolve receipt_file_id into something Telegram will actually
    accept as a photo: a Telegram-submitted receipt is already a file_id
    the API happily reuses; a website-submitted one is a relative path
    under private_media/receipts/, meaningless to Telegram until it's
    read from disk and uploaded fresh."""
    ctx = _email_context_for_reservation(reservation)
    buyer = users_repo.get_by_id(reservation["user_id"]) or {}
    source_label = "تلگرام" if reservation.get("source") == "telegram" else "سایت"
    text = (
        "🔔 رزرو جدید نیاز به بررسی دارد\n\n"
        f"رویداد: {ctx['event_title']}\n"
        f"تاریخ: {ctx['session_date']} — {ctx['session_time']}\n"
        f"خریدار: {buyer.get('full_name') or '—'} ({buyer.get('phone') or '—'})\n"
        f"تعداد: {reservation.get('people')}\n"
        f"منبع: {source_label}"
    )
    prefix = "tg:" if receipt_source == "telegram" else "file:"
    settings_service.notify_admin_channel_with_receipt(text, reservation["id"], prefix + receipt_file_id)


def _notify_admin_channel_new_waitlist(waitlist_id: int) -> None:
    """Same idea as _notify_admin_channel_new_request() above, for a new
    waiting-list entry (session was full) — called from
    _create_reservation_for_user() so it fires for both Telegram and
    website signups from the one shared function, not duplicated per
    caller."""
    entry = waitlist_repo.get_entry_with_context(waitlist_id)
    if not entry:
        return
    from database.repositories import events as events_repo
    from utils.jalali import display_date_for_event

    event = events_repo.get_event(entry["event_id"])
    source_label = "تلگرام" if entry.get("source") == "telegram" else "سایت"
    text = (
        "⏳ درخواست جدید در لیست انتظار\n\n"
        f"رویداد: {event['title'] if event else ''}\n"
        f"تاریخ: {display_date_for_event(entry['session_date'], event.get('calendar_type') if event else None)} — {entry['session_time']}\n"
        f"خریدار: {entry.get('full_name') or '—'} ({entry.get('phone') or '—'})\n"
        f"تعداد: {entry['people']}\n"
        f"منبع: {source_label}"
    )
    settings_service.notify_admin_channel(text)


def _notify_customer_by_email(reservation: dict, subject: str, body: str,
                               attachments: list[tuple[str, bytes]] | None = None) -> bool:
    """Reservation-migration finding #5: a customer who booked without
    ever talking to the Telegram bot (website-originated, no telegram_id)
    used to get NO notification at all when their reservation was
    approved or rejected — the only delivery channel (bot_outbox) is
    keyed by telegram_id. Called from every status-transition function
    below regardless of which channel (Telegram or the future website
    booking flow) triggered it, so this can't drift out of sync with one
    of them the way two separate notification code paths eventually
    would. Best-effort: send_email() itself never raises (see
    utils/email_sender.py), so a delivery failure here can never fail the
    status transition that already committed.

    Returns whether an email actually went out — False both when there
    was no email on file (e.g. a Telegram-only customer) AND when send_
    email() itself failed (bad SMTP credentials, etc.). Callers that
    tell the admin "an email was sent" need the real outcome, not just
    "this buyer has an email on file" — those looked identical from the
    outside until a real SMTP auth failure showed the difference.

    attachments: passed straight through to send_email() — see
    _build_ticket_pdf_bytes() below, the only current source of one."""
    from database.repositories import users as users_repo
    from utils.email_sender import send_email

    user = users_repo.get_by_id(reservation["user_id"])
    if not user or not user.get("email"):
        return False
    return send_email(to=user["email"], subject=subject, body=body, attachments=attachments)


def _build_ticket_pdf_bytes(reservation: dict) -> list[tuple[str, bytes]]:
    """The PDF ticket attached to the approval confirmation email —
    requested so the buyer has the actual ticket in hand from the email
    alone, not just a text confirmation (the QR/PDF was previously only
    reachable via a Telegram photo or logging into the website account
    page). Returns [] instead of raising on any failure (a missing logo
    file, a malformed event address, reportlab hiccup, whatever) — the
    approval itself must never fail, or worse, silently not notify the
    buyer at all, just because the PDF couldn't be built; the email
    still goes out, just without the attachment. Reuses the exact same
    assembly (ticket_service.get_ticket_context) and renderer (utils.
    ticket_pdf.build_ticket_pdf) the customer's own ticket.pdf download
    already uses — one PDF layout, not two that could drift apart."""
    try:
        from services import ticket_service
        from utils.ticket_pdf import build_ticket_pdf

        ctx = ticket_service.get_ticket_context(reservation)
        pdf_bytes = build_ticket_pdf(reservation=reservation, **ctx)
        code = reservation.get("reservation_code") or "ticket"
        return [(f"ticket-{code}.pdf", pdf_bytes)]
    except Exception:
        import logging
        logging.getLogger("mavara_bot").exception(
            "Failed to build ticket PDF for reservation_id=%s — approval email sent without attachment",
            reservation.get("id"),
        )
        return []


def approve_reservation(
    reservation_id: int, reviewed_by: int,
    expected_status: str | tuple[str, ...] = ("pending_review", "needs_correction"),
) -> tuple[str, "io.BytesIO", bool] | None:
    """Returns None if the reservation had already moved past expected_status
    (e.g. a duplicate/double-tap callback) — the caller should treat that
    as 'already handled', not retry.

    expected_status defaults to accepting EITHER pending_review (the normal
    admin-approves-a-fresh-receipt path) or needs_correction (an admin who
    sent a "نیازمند اصلاح" message can still approve directly afterwards —
    e.g. the buyer explained in a DM that the receipt was actually fine —
    without waiting for a resubmission first; see request_correction()'s
    docstring for why that status has no time limit to race against here).
    The dispute-resolution path — where a buyer disputed an earlier
    rejection and an admin now approves it after all — passes a single
    string, 'awaiting_buyer_confirmation', instead; passing that in here
    fixed a real bug where approving in that flow always incorrectly
    reported 'already processed' because it was hardcoded to only accept
    pending_review.

    The third element is whether the confirmation email actually went out
    (see _notify_customer_by_email) — the Telegram admin-approve handler
    uses this to tell the admin the truth for a website-only buyer with
    no Telegram to message, instead of assuming the email succeeded just
    because the buyer has one on file."""
    from database.repositories import payments as payments_repo
    from services.ticket_service import issue_ticket

    expected_statuses = (expected_status,) if isinstance(expected_status, str) else tuple(expected_status)
    transitioned = reservations_repo.set_status_if_any(reservation_id, expected_statuses, "approved")
    if not transitioned:
        return None

    payment = payments_repo.get_latest_payment(reservation_id)
    if payment:
        payments_repo.set_payment_status(payment["id"], "approved", reviewed_by)

    code, qr_image = issue_ticket(reservation_id)

    reservation = reservations_repo.get_reservation(reservation_id)
    ctx = _email_context_for_reservation(reservation)
    subject, body = settings_service.render_email(
        "approved", event_title=ctx["event_title"], session_date=ctx["session_date"],
        session_time=ctx["session_time"], reservation_code=code,
    )
    email_sent = _notify_customer_by_email(
        reservation, subject=subject, body=body, attachments=_build_ticket_pdf_bytes(reservation),
    )
    return code, qr_image, email_sent


def mark_awaiting_buyer_confirmation(reservation_id: int, admin_note: str) -> bool:
    """
    First step of rejecting a payment: the seat stays held (this status is
    counted the same as pending/approved everywhere capacity is computed)
    until the buyer either accepts the cancellation or disputes it and an
    admin makes the final call — this is what prevents the same seat being
    sold twice while a rejection is still being sorted out.
    Uses the same atomic conditional transition as approve_reservation, so
    a double-tapped Reject button (or two admins rejecting at once) can't
    both succeed. Accepts from pending_review OR needs_correction — same
    reasoning as approve_reservation's default: an admin who sent a
    "نیازمند اصلاح" message can still reject outright afterwards instead of
    waiting on a resubmission. Returns False if the reservation had
    already moved past either of those.
    """
    return reservations_repo.set_status_if_any(reservation_id, ("pending_review", "needs_correction"),
                                                "awaiting_buyer_confirmation", admin_note=admin_note)


def _notify_rejection_email(reservation_id: int, reason: str) -> None:
    reservation = reservations_repo.get_reservation(reservation_id)
    if not reservation:
        return
    ctx = _email_context_for_reservation(reservation)
    reason_block = f"\n\nدلیل: {reason}" if reason else ""
    subject, body = settings_service.render_email(
        "rejected", event_title=ctx["event_title"], session_date=ctx["session_date"], reason_block=reason_block,
    )
    _notify_customer_by_email(reservation, subject=subject, body=body)


def finalize_rejection_if(reservation_id: int, expected_status: str, reviewed_by: int, reason: str) -> bool:
    """Same idea as approve_reservation's atomic guard — used by the buyer's
    'accept cancellation' button and the admin's dispute-resolution button,
    both of which could otherwise be double-tapped."""
    from database.repositories import payments as payments_repo

    transitioned = reservations_repo.set_status_if(reservation_id, expected_status, "rejected", admin_note=reason)
    if not transitioned:
        return False

    payment = payments_repo.get_latest_payment(reservation_id)
    if payment:
        payments_repo.set_payment_status(payment["id"], "rejected", reviewed_by)
    _notify_rejection_email(reservation_id, reason)
    return True


def finalize_rejection(reservation_id: int, reviewed_by: int, reason: str) -> None:
    reject_reservation(reservation_id, reviewed_by, reason)


def reject_reservation(reservation_id: int, reviewed_by: int, reason: str) -> None:
    from database.repositories import payments as payments_repo

    payment = payments_repo.get_latest_payment(reservation_id)
    if payment:
        payments_repo.set_payment_status(payment["id"], "rejected", reviewed_by)

    reservations_repo.set_status(reservation_id, "rejected", admin_note=reason)
    _notify_rejection_email(reservation_id, reason)


def expire_stale_reservations() -> list[dict]:
    """
    Called periodically (see utils/scheduler.py). Any 'pending_payment'
    reservation past its deadline is marked 'expired', which frees its
    seats immediately since reserved_count() only counts active statuses.
    Returns the list of reservations that were just expired, so the caller
    can notify their owners.
    """
    now_iso = datetime.now(timezone.utc).isoformat(timespec="seconds")
    stale = reservations_repo.list_expired_pending(now_iso)
    for r in stale:
        reservations_repo.set_status(r["id"], "expired")
    return stale


def admin_update_people(reservation_id: int, new_people: int) -> dict:
    """Admin manually changes a reservation's headcount — capacity check
    and write happen in one transaction (see update_people_and_price_locked)
    so a concurrent booking can't slip through between the check and the write."""
    return reservations_repo.update_people_and_price_locked(reservation_id, new_people)


def admin_move_reservation(reservation_id: int, new_session_id: int) -> dict:
    return reservations_repo.move_to_session_locked(reservation_id, new_session_id)


def approve_overflow_atomic(session_id: int, user_id: int, people: int) -> dict:
    """Grows capacity and creates the reservation in one transaction (see
    reservations_repo.increase_capacity_and_reserve_locked).

    Prices at the session's own event's effective price (event_service.
    get_effective_price — per-event override, falling back to the global
    default), not unconditionally the global default price as before:
    an overflow-approved seat for an event with its own custom
    ticket_price was being charged the wrong amount, since this path
    predates per-event pricing and was never updated for it."""
    from database.repositories import events as events_repo
    from services import event_service

    session = sessions_repo.get_session(session_id)
    event = events_repo.get_event(session["event_id"]) if session else None
    unit_price, currency = (
        event_service.get_effective_price(event) if event else (settings_service.get_ticket_price(), "تومان")
    )
    result = reservations_repo.increase_capacity_and_reserve_locked(
        session_id=session_id, user_id=user_id, people=people,
        unit_price=unit_price, capacity_increase=people,
        expires_at=_expiry_timestamp(),
    )
    result["unit_price"] = unit_price
    result["currency"] = currency
    return result


def list_pending_waitlist() -> list[dict]:
    """Every waiting-list entry across every event/session, for the
    website admin panel — see waitlist_repo.list_all()'s docstring for
    why this differs from the Telegram bot's per-session "overflow
    request" prompt (which only ever surfaces one entry as it happens,
    and only to admins in a Telegram chat)."""
    return waitlist_repo.list_all("waiting")


def approve_waitlist_entry(waitlist_id: int, reviewed_by: int, unit_price: int) -> dict:
    """Admin approves a waiting-list entry from the website admin panel.

    Deliberately NOT the same shape as the Telegram-only overflow-
    approval flow (approve_overflow_atomic): that one creates a
    pending_payment reservation and waits for the buyer to send a
    receipt over Telegram — appropriate when the buyer is the one who'll
    act next. Here, the admin looking at this page IS the one deciding
    to seat this person (found by report: it was creating a
    still-unpaid, ticketless reservation with no way to finalize it from
    this page at all), so this finalizes on the spot: the admin sets the
    price right here — it may not match the event's listed price (a
    courtesy discount, a plus-one at a different rate, cash already
    collected offline...) — capacity grows, the reservation is created
    already 'approved', and a real ticket/QR is issued immediately, the
    same way create_manual_reservation()'s phone/walk-in booking path
    already works.

    Notification is email-first, unlike the Telegram-only flow: a
    website waiting-list signup may well have no Telegram account at all
    (get_or_create_customer resolves by email). If they DO have a linked
    Telegram account, a message is also queued via bot_outbox —
    best-effort, informational only (unlike the Telegram-native flow's
    FSM trick, which needs the bot process's own in-memory dispatcher
    state and isn't reachable from this API process).
    """
    entry = waitlist_repo.get_entry_with_context(waitlist_id)
    if not entry or entry["status"] != "waiting":
        return {"success": False, "error": "not_found"}
    if not waitlist_repo.set_status_if(waitlist_id, "waiting", "converted"):
        return {"success": False, "error": "already_processed"}

    result = reservations_repo.increase_capacity_and_reserve_locked(
        session_id=entry["session_id"], user_id=entry["user_id"], people=entry["people"],
        unit_price=unit_price, capacity_increase=entry["people"],
        expires_at=None, status="approved", source=entry.get("source") or "telegram",
    )
    if not result.get("success"):
        # Nothing was actually created — don't leave the waitlist entry
        # stuck as "converted" with no reservation behind it.
        waitlist_repo.set_status(waitlist_id, "waiting")
        return {"success": False, "error": "reservation_failed"}

    from services.ticket_service import issue_ticket
    code, _qr_image = issue_ticket(result["reservation_id"])
    result["reservation_code"] = code

    reservation = reservations_repo.get_reservation(result["reservation_id"])
    ctx = _email_context_for_reservation(reservation)
    subject, body = settings_service.render_email(
        "approved", event_title=ctx["event_title"], session_date=ctx["session_date"],
        session_time=ctx["session_time"], reservation_code=code,
    )
    _notify_customer_by_email(
        reservation, subject=subject, body=body, attachments=_build_ticket_pdf_bytes(reservation),
    )
    if entry.get("telegram_id"):
        from database.repositories import bot_outbox as outbox_repo
        outbox_repo.enqueue(
            entry["telegram_id"],
            f"🎉 خبر خوب! ظرفیت برایت باز شد و بلیطت صادر شد.\nکد رزرو: {code}\nبرای دیدن بلیت وارد سایت خانه ماورا شو.",
        )

    result["waitlist_id"] = waitlist_id
    return result


def reject_waitlist_entry(waitlist_id: int, reviewed_by: int) -> dict:
    """Admin declines a waiting-list entry — no seat opened up. Same
    email-first / best-effort-Telegram notification shape as
    approve_waitlist_entry()."""
    entry = waitlist_repo.get_entry_with_context(waitlist_id)
    if not entry or entry["status"] != "waiting":
        return {"success": False, "error": "not_found"}
    if not waitlist_repo.set_status_if(waitlist_id, "waiting", "rejected"):
        return {"success": False, "error": "already_processed"}

    user = users_repo.get_by_id(entry["user_id"])
    if user and user.get("email"):
        from utils.email_sender import send_email
        subject, body = settings_service.render_email("waitlist_rejected")
        send_email(to=user["email"], subject=subject, body=body)
    if entry.get("telegram_id"):
        from database.repositories import bot_outbox as outbox_repo
        from texts import fa
        outbox_repo.enqueue(entry["telegram_id"], fa.OVERFLOW_REJECTED_BUYER_MSG)

    return {"success": True}


def admin_cancel_reservation(reservation_id: int) -> None:
    reservations_repo.set_status(reservation_id, "cancelled")


def get_user_reservations(telegram_id: int) -> list[dict]:
    from database.connection import get_connection

    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT r.*, s.session_date, s.session_time, e.title AS event_title
            FROM reservations r
            JOIN users u ON u.id = r.user_id
            JOIN sessions s ON s.id = r.session_id
            JOIN events e ON e.id = s.event_id
            WHERE u.telegram_id = ?
            ORDER BY s.session_date DESC, s.session_time DESC
            """,
            (telegram_id,),
        ).fetchall()
        return [dict(r) for r in rows]
