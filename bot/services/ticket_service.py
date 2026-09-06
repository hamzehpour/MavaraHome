"""Issuing a ticket = generating a unique reservation code + its signed QR image."""
import os

from database.repositories import reservations as reservations_repo
from database.repositories import sessions as sessions_repo
from database.repositories import events as events_repo
from services import settings_service
from utils.code_generator import generate_reservation_code
from utils.qr_generator import generate_qr_image_bytes
from utils.qr_signing import sign_code


def issue_ticket(reservation_id: int) -> tuple[str, bytes]:
    """Returns (code, qr_png_bytes) — raw PNG bytes, not an aiogram type.
    This lives in services/ (shared by the bot AND the website's approve
    endpoint), and the website approve path must keep working with no
    aiogram installed at all (Phase 1's own stated rule: an API-only
    process should never need a Telegram token). The caller on the bot
    side (handlers/admin_reservations.py) wraps these bytes in
    aiogram.types.BufferedInputFile itself right before send_photo —
    that's where the aiogram dependency belongs, not here.

    (Found by testing the website approve flow with aiogram genuinely
    absent, in this sandbox — before this fix it crashed with
    'No module named aiogram' even though nothing about a website
    approval should ever need aiogram.)
    """
    code = generate_reservation_code()
    # Extremely unlikely collision, but guard anyway since the column is UNIQUE.
    while reservations_repo.get_by_code(code):
        code = generate_reservation_code()

    reservations_repo.set_reservation_code(reservation_id, code)
    # The QR image encodes CODE.SIGNATURE (not just the plain code) so a
    # forged/guessed code can never scan as valid — only reservations
    # actually issued by this bot produce a matching signature.
    qr_bytes = generate_qr_image_bytes(sign_code(code))
    return code, qr_bytes


def resolve_media_path(rel_path: str | None) -> str | None:
    """Turns a stored 'media/xxx/yyy.png' path (as returned by
    /api/v1/admin/upload) into a real filesystem path for reportlab to
    open. Returns None for anything falsy or unexpected, instead of
    raising — a missing/malformed logo path must never break ticket
    generation, it should just mean no logo gets drawn.

    Moved here from api/server.py (was module-private, _resolve_media_
    path) so services/reservation_service.py can build a ticket PDF too
    (for the admin-approve confirmation email) without api/server.py's
    module needing to be importable from the bot process."""
    if not rel_path or not isinstance(rel_path, str):
        return None
    bot_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    full = os.path.normpath(os.path.join(bot_root, rel_path))
    # Guard against a stray '../' in a stored path ever escaping bot_root.
    if not full.startswith(bot_root):
        return None
    return full


def get_ticket_context(reservation: dict) -> dict:
    """Assembles what a ticket PDF/screen needs from a bare reservation
    row — pure lookups + the existing display_date_for_event formatter,
    not new business logic. Shared by /api/v1/account/reservations/<id>/
    ticket.pdf (customer's own download) and
    reservation_service._build_ticket_pdf_bytes() (the copy attached to
    the admin-approve confirmation email) — moved here (was api/server.
    py's module-private _ticket_context) specifically so both can use
    the exact same assembly logic instead of two copies drifting apart."""
    from utils.jalali import display_date_for_event
    session = sessions_repo.get_session(reservation["session_id"]) or {}
    event = events_repo.get_event(session.get("event_id")) if session else None
    template = settings_service.get_ticket_template()
    logo_rel = ((event or {}).get("ticket_logo") or template.get("logo") or "").strip()
    return {
        "event_title": event["title"] if event else "",
        "address": (event or {}).get("address"),
        "session_date_display": display_date_for_event(session.get("session_date", ""), (event or {}).get("calendar_type", "jalali")) if session else "",
        "session_time": session.get("session_time", ""),
        # Per-event "important notes" (parking, silence, etc.) — printed
        # automatically under the ملاحظات heading, see utils/ticket_pdf.py.
        "important_notes": (event or {}).get("important_notes"),
        "logo_path": resolve_media_path(logo_rel) if logo_rel else None,
        "template": {"title": template["title"], "subtitle": template["subtitle"], "footer": template["footer"]},
    }
