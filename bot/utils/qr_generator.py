"""Generates a QR code image, either as raw PNG bytes (used by the API's
web ticket PDF, Phase 6) or as an aiogram-ready image for send_photo()
(used by the bot)."""
import io
import qrcode


def generate_qr_image_bytes(data: str) -> bytes:
    """Raw PNG bytes — the shared primitive both callers below build on.
    Kept dependency-free of aiogram so api/server.py (which never imports
    aiogram — see api/server.py's own module docstring) can use it too."""
    img = qrcode.make(data)
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return buffer.getvalue()


def generate_qr_png(data: str) -> "BufferedInputFile":
    """
    Returns a BufferedInputFile — NOT a raw BytesIO. aiogram 3's send_photo
    only accepts InputFile subclasses or a string (file_id/URL); passing a
    raw BytesIO fails Pydantic validation with a confusing 'string_type'
    error and — critically — throws AFTER the caller's try/except already
    logged it as a delivery failure, which is exactly the bug that made
    every single approved ticket silently fail to reach the buyer.

    Only imports aiogram when actually called (not at module load) so
    api/server.py, which imports generate_qr_image_bytes above but must
    stay aiogram-free, is never forced to have aiogram installed.
    """
    from aiogram.types import BufferedInputFile
    return BufferedInputFile(generate_qr_image_bytes(data), filename="ticket.png")
