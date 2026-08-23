"""Issuing a ticket = generating a unique reservation code + its signed QR image."""
from database.repositories import reservations as reservations_repo
from utils.code_generator import generate_reservation_code
from utils.qr_generator import generate_qr_image_bytes
from utils.qr_signing import sign_code


def issue_ticket(reservation_id: int) -> tuple[str, bytes]:
    """Returns (code, qr_png_bytes) — raw PNG bytes, not an aiogram type.
    This lives in services/ (shared by the bot AND the website's approve
    endpoint), and the website approve path must keep working with no
    aiogram installed at all (Phase 1's own stated rule: an API-only
    process should never need a Telegram token). Callers on the bot side
    (handlers/admin_reservations.py, handlers/reject_confirmation.py)
    wrap these bytes in aiogram.types.BufferedInputFile themselves right
    before send_photo — that's where the aiogram dependency belongs, not
    here.

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
