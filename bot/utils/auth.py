"""
Phase 2 authentication primitives — password hashing (PBKDF2-HMAC-SHA256)
and JWT (HS256), both implemented with Python's standard library only.

Why not a real JWT library (PyJWT) or bcrypt: the environment this was
built in has no internet access to `pip install` anything, and per the
project's own rule, nothing ships until it's actually been run and
verified — not just written against an assumed API. These are small,
well-understood algorithms (PBKDF2 and HMAC are both stdlib `hashlib`/
`hmac`), so a correct from-scratch implementation is both possible and
independently testable here. If PyJWT/bcrypt become available later,
swapping them in is a contained change — nothing outside this file needs
to know the difference (same create_token/verify_token,
hash_password/verify_password function signatures).
"""
import base64
import hashlib
import hmac
import json
import os
import time

# Read once at import time so a restart is required to rotate it (same
# operational model as BOT_TOKEN) — never hardcode a real secret here.
JWT_SECRET = os.getenv("JWT_SECRET", "")
if not JWT_SECRET:
    import warnings
    warnings.warn(
        "JWT_SECRET is not set — admin login tokens would be signed with "
        "an empty secret, which is NOT safe. Set JWT_SECRET in .env before "
        "using admin login in anything but local testing."
    )

ACCESS_TOKEN_TTL_SECONDS = 15 * 60          # short-lived — used on every admin request
REFRESH_TOKEN_TTL_SECONDS = 14 * 24 * 3600  # 14 days — used only to mint new access tokens


# ---------- password hashing ----------

def hash_password(password: str, salt: bytes | None = None) -> tuple[str, str]:
    """Returns (password_hash_hex, salt_hex). PBKDF2-HMAC-SHA256, 200k
    iterations — deliberately expensive (this runs once per login, not
    once per request, so the cost is acceptable)."""
    if salt is None:
        salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 200_000)
    return digest.hex(), salt.hex()


def verify_password(password: str, stored_hash_hex: str, stored_salt_hex: str) -> bool:
    salt = bytes.fromhex(stored_salt_hex)
    digest, _ = hash_password(password, salt)
    # Constant-time compare — a naive `==` here would leak timing
    # information about how many leading bytes matched.
    return hmac.compare_digest(digest, stored_hash_hex)


# ---------- JWT (HS256) ----------

def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def create_token(payload: dict, ttl_seconds: int) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    now = int(time.time())
    full_payload = {**payload, "iat": now, "exp": now + ttl_seconds}
    header_b64 = _b64url_encode(json.dumps(header, separators=(",", ":")).encode())
    payload_b64 = _b64url_encode(json.dumps(full_payload, separators=(",", ":")).encode())
    signing_input = f"{header_b64}.{payload_b64}".encode()
    signature = hmac.new(JWT_SECRET.encode("utf-8"), signing_input, hashlib.sha256).digest()
    signature_b64 = _b64url_encode(signature)
    return f"{header_b64}.{payload_b64}.{signature_b64}"


def verify_token(token: str) -> dict | None:
    """Returns the decoded payload if the token is validly signed and not
    expired, otherwise None. Never raises — callers just check for None."""
    try:
        header_b64, payload_b64, signature_b64 = token.split(".")
        signing_input = f"{header_b64}.{payload_b64}".encode()
        expected_sig = hmac.new(JWT_SECRET.encode("utf-8"), signing_input, hashlib.sha256).digest()
        actual_sig = _b64url_decode(signature_b64)
        if not hmac.compare_digest(expected_sig, actual_sig):
            return None
        payload = json.loads(_b64url_decode(payload_b64))
        if payload.get("exp", 0) < time.time():
            return None
        return payload
    except Exception:
        return None
