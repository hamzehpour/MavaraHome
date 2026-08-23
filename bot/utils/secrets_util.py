"""
Simple, dependency-free password hashing for the owner-transfer passcode.
Not for storing anything more sensitive than this one internal PIN — but
correct: random salt per install, PBKDF2-SHA256, constant-time compare.
"""
import hashlib
import hmac
import secrets

_ITERATIONS = 200_000


def hash_passcode(passcode: str, salt: str | None = None) -> tuple[str, str]:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", passcode.encode(), bytes.fromhex(salt), _ITERATIONS)
    return digest.hex(), salt


def verify_passcode(passcode: str, stored_hash: str, salt: str) -> bool:
    if not stored_hash or not salt:
        return False
    candidate, _ = hash_passcode(passcode, salt)
    return hmac.compare_digest(candidate, stored_hash)
