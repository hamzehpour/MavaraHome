"""
HMAC-signs the reservation code encoded into the QR so a ticket can't be
forged by just guessing/copying a plausible-looking code — the QR payload
is 'CODE.SIGNATURE' and only someone with the secret key (server-side only,
never exposed) can produce a signature that verifies.

The signing key is a dedicated secret, generated once and stored in the
settings table — deliberately NOT derived from BOT_TOKEN. If it were tied
to the bot token, rotating the token (e.g. after a leak, as already
happened once in this project's history) would silently invalidate every
ticket already issued and in someone's pocket. Rotating BOT_TOKEN and
rotating the QR signing key are now two independent operations.
"""
import hashlib
import hmac
import secrets


def _get_signing_key() -> bytes:
    from database.repositories import settings as settings_repo
    hex_key = settings_repo.get("qr_signing_secret", "")
    if not hex_key:
        hex_key = secrets.token_hex(32)
        settings_repo.set("qr_signing_secret", hex_key)
    return bytes.fromhex(hex_key)


def sign_code(reservation_code: str) -> str:
    signature = hmac.new(_get_signing_key(), reservation_code.encode(), hashlib.sha256).hexdigest()[:12]
    return f"{reservation_code}.{signature}"


def verify_signed_code(payload: str) -> str | None:
    """Returns the reservation_code if the signature is valid, else None."""
    if "." not in payload:
        return None
    code, signature = payload.rsplit(".", 1)
    expected = hmac.new(_get_signing_key(), code.encode(), hashlib.sha256).hexdigest()[:12]
    return code if hmac.compare_digest(signature, expected) else None
