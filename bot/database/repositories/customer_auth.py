"""Schema v9 — customer login via OTP delivered by email.

Rewritten from the original phone+Telegram-delivery flow: this project
has no SMS provider, so codes used to be routed through the Telegram bot
(requiring a one-time "connect your Telegram" step for anyone who hadn't
already talked to the bot). Email needs no such indirection — the code
just gets emailed straight to the address the customer typed in, via
utils/email_sender.py.

`customer_otp` stores hashed codes (reuses the same PBKDF2 helper as
admin passwords — an OTP is short-lived but still shouldn't sit in the
database as plaintext). `phone` stays NOT NULL on this table for
backward compatibility with the original schema — new email-based rows
just write '' into it rather than requiring a full table rebuild to
relax that constraint (SQLite can't ALTER a column's NOT NULL in place).

The old `telegram_link_tokens` table/functions (create_link_token /
consume_link_token) are gone from here — they existed only to support
the phone+Telegram flow this replaces. The table itself is left in the
schema (harmless, and dropping tables is not this project's style), just
unused going forward.
"""
from datetime import datetime, timedelta, timezone

from database.connection import get_connection
from utils.auth import hash_password, verify_password

OTP_TTL_MINUTES = 5
OTP_MAX_ATTEMPTS = 5


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def create_otp(email: str, code: str) -> int:
    """Stores a hashed OTP for `email`."""
    code_hash, code_salt = hash_password(code)
    expires_at = (datetime.now(timezone.utc) + timedelta(minutes=OTP_TTL_MINUTES)).isoformat(timespec="seconds")
    with get_connection() as conn:
        # Invalidate any earlier still-pending codes for this email so a
        # user can never accidentally succeed with a stale code.
        conn.execute("UPDATE customer_otp SET status='expired' WHERE email=? AND status='pending'", (email,))
        cur = conn.execute(
            "INSERT INTO customer_otp(phone, email, code_hash, code_salt, expires_at) VALUES ('', ?, ?, ?, ?)",
            (email, code_hash, code_salt, expires_at),
        )
        return cur.lastrowid


def verify_otp(email: str, code: str) -> bool:
    """Checks the most recent pending OTP for this email. Returns True and
    marks it used on success. Enforces both expiry and a max-attempts
    counter (brute-force guard) independent of the API-level rate limit in
    api/server.py — defense in depth, not a duplicate of it."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM customer_otp WHERE email=? AND status='pending' ORDER BY created_at DESC LIMIT 1",
            (email,),
        ).fetchone()
        if not row:
            return False
        if row["expires_at"] < _now_iso():
            conn.execute("UPDATE customer_otp SET status='expired' WHERE id=?", (row["id"],))
            return False
        if row["attempts"] >= OTP_MAX_ATTEMPTS:
            conn.execute("UPDATE customer_otp SET status='expired' WHERE id=?", (row["id"],))
            return False

        if not verify_password(code, row["code_hash"], row["code_salt"]):
            conn.execute("UPDATE customer_otp SET attempts = attempts + 1 WHERE id=?", (row["id"],))
            return False

        conn.execute("UPDATE customer_otp SET status='verified' WHERE id=?", (row["id"],))
        return True
