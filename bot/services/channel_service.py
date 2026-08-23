"""
Builds and keeps a live 'sales board' updated inside a Telegram channel the
admin designates — one continuously-edited message (or a few, if it grows
past Telegram's length limit) per event+day, refreshed on every reservation
change. The admin should never edit these messages by hand; the bot owns
them entirely to avoid the two of them fighting over the same message.
"""
from database.repositories import settings as settings_repo
from database.repositories import channel_boards as boards_repo
from database.repositories import sessions as sessions_repo
from database.repositories import reservations as reservations_repo
from database.repositories import events as events_repo
from utils.jalali import gregorian_iso_to_jalali_display, to_persian_digits

MAX_PART_LENGTH = 3500  # headroom under Telegram's 4096-char message limit

_CLOCK_EMOJIS = [
    "🕛", "🕧", "🕐", "🕜", "🕑", "🕝", "🕒", "🕞", "🕓", "🕟", "🕔", "🕠",
    "🕕", "🕡", "🕖", "🕢", "🕗", "🕣", "🕘", "🕤", "🕙", "🕥", "🕚", "🕦",
]


def _clock_emoji(time_str: str) -> str:
    try:
        hour, minute = (int(x) for x in time_str.split(":"))
    except Exception:
        return "🕒"
    idx = (hour % 12) * 2 + (1 if minute >= 30 else 0)
    return _CLOCK_EMOJIS[idx]


def _day_header(date_iso: str, event_title: str = "") -> str:
    from utils.jalali import gregorian_to_jalali, WEEKDAY_NAMES_FA, MONTH_NAMES_FA
    from datetime import date as _date
    y, m, d = (int(x) for x in date_iso.split("-"))
    jy, jm, jd = gregorian_to_jalali(y, m, d)
    weekday_fa = WEEKDAY_NAMES_FA[_date(y, m, d).weekday()]
    header = to_persian_digits(f"🗓️ {weekday_fa} | {jd} {MONTH_NAMES_FA[jm - 1]}")
    if event_title:
        # Event name always on top — a reader watching several events at once
        # in the same channel should never have to guess whose board this is.
        return f"🎭 {event_title}\n{header}"
    return header


# Reservation lifecycle → icon shown next to each holder in the board.
# Mirrors the real state machine in reservation_service.py — a reservation
# being *created* is never shown as a final/successful sale here.
_STATUS_ICON = {
    "pending_payment": "🕐",   # created, buyer hasn't sent a receipt yet
    "pending_review": "⏳",    # receipt sent, waiting on admin
    "awaiting_buyer_confirmation": "⏳",
    "approved": "✅",          # only this is a truly confirmed sale
}


def _session_block(session: dict, index: int) -> list[str]:
    reserved = sessions_repo.reserved_count(session["id"])
    remaining = session["capacity"] - reserved
    is_full = remaining <= 0
    is_near_full = (not is_full) and session["capacity"] > 0 and remaining <= max(1, round(session["capacity"] * 0.15))
    status_circle = "🔴" if is_full else ("🟠" if is_near_full else "🟢")

    approved_count = 0
    pending_count = 0

    lines = [
        to_persian_digits(f"{index}- {_clock_emoji(session['session_time'])}{status_circle} سانس {session['session_time']}")
    ]
    if is_full:
        lines.append("💯 تکمیل ظرفیت شد 💯")
    else:
        lines.append(to_persian_digits(f"{remaining} نفر مانده تا تکمیل ظرفیت"))

    holders = reservations_repo.list_holders_for_session(session["id"])
    if not holders:
        lines.append("-")
    for h in holders:
        name = h.get("attendee_name") or h["full_name"]
        phone = h.get("attendee_phone") or h["phone"]
        icon = _STATUS_ICON.get(h["status"], "•")
        if h["status"] == "approved":
            approved_count += h["people"]
        elif h["status"] in ("pending_review", "awaiting_buyer_confirmation"):
            pending_count += h["people"]
        lines.append(to_persian_digits(f"{icon} {name} {h['people']} نفر ({phone})"))

    # Summary so the admin never has to count manually: how many seats are
    # a done deal vs. still waiting on admin review.
    lines.insert(2, to_persian_digits(f"قطعی: {approved_count} نفر | در انتظار تأیید: {pending_count} نفر"))
    return lines


def render_day_board(event_id: int, date_iso: str) -> list[str]:
    """Returns the board split into Telegram-message-sized parts. Each part
    after the first starts with a header stating which day (and, if the
    split happened mid-session, which session) it continues."""
    sessions = [
        s for s in sessions_repo.list_sessions_for_event_admin(event_id)
        if s["session_date"] == date_iso
    ]
    sessions.sort(key=lambda s: s["session_time"])

    event = events_repo.get_event(event_id)
    event_title = event["title"] if event else ""
    header = _day_header(date_iso, event_title)
    parts: list[str] = []
    current_lines = [header, ""]

    def flush():
        nonlocal current_lines
        parts.append("\n".join(current_lines).strip())
        current_lines = []

    for i, session in enumerate(sessions, start=1):
        block = _session_block(session, i)
        block_text = "\n".join(block)

        if len("\n".join(current_lines)) + len(block_text) > MAX_PART_LENGTH and current_lines != [header, ""]:
            flush()
            current_lines = [f"{header} (ادامه)", ""]

        # If even a single session's own block is too long (huge waitlist),
        # split it internally with an explicit "ادامه سانس" header.
        if len(block_text) > MAX_PART_LENGTH:
            for j in range(0, len(block), 20):
                chunk = block[j:j + 20]
                if j > 0:
                    flush()
                    current_lines = [f"{header} — ادامه سانس {session['session_time']}", ""]
                current_lines.extend(chunk)
        else:
            current_lines.append(block_text)
        current_lines.append("")

    flush()
    return [p for p in parts if p]


async def refresh_board(bot, event_id: int, date_iso: str) -> None:
    channel_id = settings_repo.get("monitoring_channel_id", "")
    if not channel_id:
        return  # monitoring not set up — nothing to do

    is_new_day = not boards_repo.has_board_for_day(event_id, date_iso)
    if is_new_day:
        await _maybe_send_separators(bot, int(channel_id), date_iso)

    parts = render_day_board(event_id, date_iso)
    existing = boards_repo.list_parts(event_id, date_iso)
    existing_by_index = {p["part_index"]: p["message_id"] for p in existing}

    for idx, text in enumerate(parts):
        message_id = existing_by_index.get(idx)
        if message_id:
            try:
                await bot.edit_message_text(chat_id=int(channel_id), message_id=message_id, text=text)
                continue
            except Exception:
                pass  # message may have been deleted manually — fall through and resend
        try:
            sent = await bot.send_message(int(channel_id), text)
            boards_repo.upsert_message_id(event_id, date_iso, idx, sent.message_id)
        except Exception:
            pass

    # If the board shrank (e.g. all reservations for a session were cancelled
    # and the whole day now fits in fewer parts), remove the leftover tail.
    for idx, message_id in existing_by_index.items():
        if idx >= len(parts):
            try:
                await bot.delete_message(int(channel_id), message_id)
            except Exception:
                pass
            boards_repo.delete_part(event_id, date_iso, idx)


async def _maybe_send_separators(bot, channel_id: int, date_iso: str) -> None:
    from datetime import date as _date
    is_first_ever = not boards_repo.has_any_board_ever()

    if not is_first_ever:
        y, m, d = (int(x) for x in date_iso.split("-"))
        iso_week = _date(y, m, d).isocalendar()[1]
        last_week = settings_repo.get("monitoring_last_week", "")
        if str(iso_week) != last_week:
            try:
                await bot.send_message(channel_id, "🆕🆕🆕🆕🆕🆕🆕🆕🆕🆕🆕🆕")
            except Exception:
                pass
        else:
            try:
                await bot.send_message(channel_id, "⛵️⛵️⛵️⛵️⛵️⛵️⛵️⛵️⛵️⛵️⛵️⛵️")
            except Exception:
                pass
        settings_repo.set("monitoring_last_week", str(iso_week))
    else:
        y, m, d = (int(x) for x in date_iso.split("-"))
        settings_repo.set("monitoring_last_week", str(_date(y, m, d).isocalendar()[1]))


async def on_reservation_changed(bot, session_id: int) -> None:
    """Call this after ANY change that affects what the board shows for a
    session (new booking, approve, reject, cancel, move, expire, capacity
    edit, overflow approval, ...). Safe to call even if monitoring isn't
    configured — it's a no-op in that case."""
    session = sessions_repo.get_session(session_id)
    if not session:
        return
    await refresh_board(bot, session["event_id"], session["session_date"])


async def resync_all(bot) -> int:
    """Rebuild every board from scratch, in strict chronological day order
    (Wed before Thu before Fri, etc.) across every active event.

    Two things this fixes:
    1. Connecting the monitoring channel for the first time used to only
       start covering days from that moment forward — anything booked
       before the channel was connected never appeared. This walks every
       future session date that has at least one reservation and posts it,
       so nothing is missed.
    2. Boards used to appear in whatever order a reservation happened to
       come in, not calendar order. Since refresh_board sends/edits boards
       in the order this function calls it, sorting the (event, date) pairs
       by date_iso first guarantees Wed/Thu/Fri (etc.) show up top-to-bottom
       in real calendar order.

    Returns how many day-boards were (re)synced. Safe to call repeatedly —
    it's the same idempotent upsert refresh_board already does per part.
    """
    pairs: set[tuple[int, str]] = set()
    for event in events_repo.list_active_events():
        for session in sessions_repo.list_sessions_for_event_admin(event["id"]):
            if reservations_repo.list_holders_for_session(session["id"]):
                pairs.add((event["id"], session["session_date"]))

    for event_id, date_iso in sorted(pairs, key=lambda p: p[1]):
        await refresh_board(bot, event_id, date_iso)

    return len(pairs)
