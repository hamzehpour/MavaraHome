"""
Password hashing (PBKDF2-HMAC-SHA256) and JWT (HS256), stdlib-only —
copied verbatim from bot/utils/auth.py's approach (same reasoning: no
external JWT/bcrypt dependency needed for something this small and
well-understood, and it keeps this CMS backend's only dependency being
Flask itself — important on a shared-hosting Python App where every
extra pip package is another thing that has to install correctly).

Deliberately a standalone copy, not an import from bot/ — this backend
is meant to be deployable completely independently of bot/ (different
host, no shared code, no shared database — see README.md's "Split
architecture" section for why).
"""
import base64
import hashlib
import hmac
import json
import os
import time

JWT_SECRET = os.getenv("JWT_SECRET", "")
if not JWT_SECRET:
    import warnings
    warnings.warn(
        "JWT_SECRET is not set — admin login tokens would be signed with "
        "an empty secret, which is NOT safe. Set JWT_SECRET in .env before "
        "using admin login in anything but local testing."
    )

ACCESS_TOKEN_TTL_SECONDS = 60 * 60           # 1 hour — a content-only CMS session can be longer-lived than the reservation platform's 15 min
REFRESH_TOKEN_TTL_SECONDS = 30 * 24 * 3600   # 30 days


def hash_password(password: str, salt: bytes | None = None) -> tuple[str, str]:
    if salt is None:
        salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 200_000)
    return digest.hex(), salt.hex()


def verify_password(password: str, stored_hash_hex: str, stored_salt_hex: str) -> bool:
    salt = bytes.fromhex(stored_salt_hex)
    digest, _ = hash_password(password, salt)
    return hmac.compare_digest(digest, stored_hash_hex)


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
