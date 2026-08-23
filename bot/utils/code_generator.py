"""Unique, human-friendly reservation codes: MV-XXXXXX (uppercase base32-ish)."""
import secrets
import string

_ALPHABET = "".join(c for c in (string.ascii_uppercase + string.digits) if c not in "O0I1")


def generate_reservation_code(prefix: str = "MV") -> str:
    suffix = "".join(secrets.choice(_ALPHABET) for _ in range(6))
    return f"{prefix}-{suffix}"
