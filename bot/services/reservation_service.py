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


def start_reservation_web(phone: str, full_name: str, session_id: int, people: int) -> dict:
    """Website-originated booking (Phase 1: unified backend). Same reservation
    core as the Telegram path — capacity check, pricing, atomic insert are
    ALL the same code, just identified by phone instead of telegram_id since
    a website visitor has no Telegram account yet. `source='website'` is
    what lets the admin/monitoring tell the two apart."""
    from validators.validators import normalize_phone
    normalized = normalize_phone(phone)
    user = users_repo.get_or_create_user_by_phone(normalized, full_name)
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
        result["waitlist_id"] = waitlist_repo.add(user_id=user["id"], session_id=session_id, people=people)

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
        waitlist_repo.add(user_id=user["id"], session_id=session_id, people=people)
        return result

    if result["success"]:
        code, _ = issue_ticket(result["reservation_id"])
        result["reservation_code"] = code

    result["unit_price"] = unit_price
    return result


def submit_receipt(reservation_id: int, receipt_file_id: str, receipt_source: str = "telegram") -> bool:
    """
    receipt_source distinguishes a Telegram file_id from a future website
    upload (e.g. a URL/path) — both are just strings aiogram's send_photo
    can display to the admin either way, so no special-casing is needed
    when notifying staff; this only matters for bookkeeping / future UI.

    Returns False (and does nothing) if the reservation has already moved
    past pending_payment — e.g. the buyer sent a second photo right after
    the first. Without this, a duplicate send would notify every admin a
    second time for the same reservation.
    """
    from database.repositories import payments as payments_repo

    transitioned = reservations_repo.set_status_if(reservation_id, "pending_payment", "pending_review")
    if not transitioned:
        return False

    reservation = reservations_repo.get_reservation(reservation_id)
    payments_repo.create_payment(
        reservation_id=reservation_id,
        receipt_file_id=receipt_file_id,
        amount=reservation["total_price"],
        receipt_source=receipt_source,
    )
    return True


def approve_reservation(
    reservation_id: int, reviewed_by: int, expected_status: str = "pending_review"
) -> tuple[str, "io.BytesIO"] | None:
    """Returns None if the reservation had already moved past expected_status
    (e.g. a duplicate/double-tap callback) — the caller should treat that
    as 'already handled', not retry.

    expected_status defaults to pending_review (the normal admin-approves-a-
    fresh-receipt path). The dispute-resolution path — where a buyer
    disputed an earlier rejection and an admin now approves it after all —
    starts from awaiting_buyer_confirmation instead; passing that in here
    fixed a real bug where approving in that flow always incorrectly
    reported 'already processed' because it was hardcoded to only accept
    pending_review."""
    from database.repositories import payments as payments_repo
    from services.ticket_service import issue_ticket

    transitioned = reservations_repo.set_status_if(reservation_id, expected_status, "approved")
    if not transitioned:
        return None

    payment = payments_repo.get_latest_payment(reservation_id)
    if payment:
        payments_repo.set_payment_status(payment["id"], "approved", reviewed_by)

    code, qr_image = issue_ticket(reservation_id)
    return code, qr_image


def mark_awaiting_buyer_confirmation(reservation_id: int, admin_note: str) -> bool:
    """
    First step of rejecting a payment: the seat stays held (this status is
    counted the same as pending/approved everywhere capacity is computed)
    until the buyer either accepts the cancellation or disputes it and an
    admin makes the final call — this is what prevents the same seat being
    sold twice while a rejection is still being sorted out.
    Uses the same atomic conditional transition as approve_reservation, so
    a double-tapped Reject button (or two admins rejecting at once) can't
    both succeed. Returns False if the reservation had already moved past
    pending_review.
    """
    return reservations_repo.set_status_if(reservation_id, "pending_review",
                                            "awaiting_buyer_confirmation", admin_note=admin_note)


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
    return True


def finalize_rejection(reservation_id: int, reviewed_by: int, reason: str) -> None:
    reject_reservation(reservation_id, reviewed_by, reason)


def reject_reservation(reservation_id: int, reviewed_by: int, reason: str) -> None:
    from database.repositories import payments as payments_repo

    payment = payments_repo.get_latest_payment(reservation_id)
    if payment:
        payments_repo.set_payment_status(payment["id"], "rejected", reviewed_by)

    reservations_repo.set_status(reservation_id, "rejected", admin_note=reason)


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
    reservations_repo.increase_capacity_and_reserve_locked)."""
    unit_price = settings_service.get_ticket_price()
    result = reservations_repo.increase_capacity_and_reserve_locked(
        session_id=session_id, user_id=user_id, people=people,
        unit_price=unit_price, capacity_increase=people,
        expires_at=_expiry_timestamp(),
    )
    result["unit_price"] = unit_price
    return result


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
