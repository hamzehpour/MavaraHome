"""Phase 4 — customer login via OTP delivered through the Telegram bot.

Two concerns live here:
  * customer_otp            — the actual 6-digit codes (hashed, never
                               stored in plaintext — same principle as
                               web_admins password hashing)
  * telegram_link_tokens    — one-time deep-link tokens for a phone that
                               has no telegram_id yet (see
                               services/customer_auth_service.py for the
                               full flow)
"""
import secrets
from datetime import datetime, timedelta, timezone

from database.connection import get_connection
from utils.auth import hash_password, verify_password

OTP_TTL_MINUTES = 5
OTP_MAX_ATTEMPTS = 5
LINK_TOKEN_TTL_MINUTES = 30


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def create_otp(phone: str, code: str) -> int:
    """Stores a hashed OTP (reuses the same PBKDF2 helper as admin
    passwords — an OTP is short-lived but still shouldn't sit in the
    database as plaintext)."""
    code_hash, code_salt = hash_password(code)
    expires_at = (datetime.now(timezone.utc) + timedelta(minutes=OTP_TTL_MINUTES)).isoformat(timespec="seconds")
    with get_connection() as conn:
        # Invalidate any earlier still-pending codes for this phone so a
        # user can never accidentally succeed with a stale code.
        conn.execute("UPDATE customer_otp SET status='expired' WHERE phone=? AND status='pending'", (phone,))
        cur = conn.execute(
            "INSERT INTO customer_otp(phone, code_hash, code_salt, expires_at) VALUES (?, ?, ?, ?)",
            (phone, code_hash, code_salt, expires_at),
        )
        return cur.lastrowid


def verify_otp(phone: str, code: str) -> bool:
    """Checks the most recent pending OTP for this phone. Returns True and
    marks it used on success. Enforces both expiry and a max-attempts
    counter (brute-force guard) independent of the API-level rate limit in
    api/server.py — defense in depth, not a duplicate of it."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM customer_otp WHERE phone=? AND status='pending' ORDER BY created_at DESC LIMIT 1",
            (phone,),
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


def create_link_token(phone: str) -> str:
    """A one-time token embedded in a t.me/<bot>?start=LINK-<token> deep
    link — see handlers/common.py's extended /start handler. Lets a
    website-only user (phone, no telegram_id) open the bot once so future
    OTP codes can actually be delivered to them."""
    token = secrets.token_urlsafe(16)
    expires_at = (datetime.now(timezone.utc) + timedelta(minutes=LINK_TOKEN_TTL_MINUTES)).isoformat(timespec="seconds")
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO telegram_link_tokens(token, phone, expires_at) VALUES (?, ?, ?)",
            (token, phone, expires_at),
        )
    return token


def consume_link_token(token: str) -> str | None:
    """Returns the phone number if the token is valid and unused, and
    marks it used. Returns None otherwise (bad/expired/already-used)."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM telegram_link_tokens WHERE token=? AND status='pending'", (token,)
        ).fetchone()
        if not row or row["expires_at"] < _now_iso():
            return None
        conn.execute("UPDATE telegram_link_tokens SET status='used' WHERE id=?", (row["id"],))
        return row["phone"]
