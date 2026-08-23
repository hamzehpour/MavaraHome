from database.connection import get_connection


def get_by_telegram_id(telegram_id: int) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)
        ).fetchone()
        return dict(row) if row else None


def get_or_create_user_by_phone(phone: str, full_name: str | None = None) -> dict:
    """Website-originated users have no telegram_id yet, so they're looked
    up/created by phone instead. If this same phone number later starts a
    conversation with the bot, `link_telegram_id_by_phone` (below) merges
    the identity instead of creating a duplicate user row — one customer,
    one row, regardless of which channel they used first."""
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM users WHERE phone = ?", (phone,)).fetchone()
        if row:
            return dict(row)
        cur = conn.execute(
            "INSERT INTO users(phone, full_name) VALUES (?, ?)",
            (phone, full_name),
        )
        return {"id": cur.lastrowid, "telegram_id": None, "phone": phone, "full_name": full_name}


def get_or_create_user_by_email(email: str, full_name: str | None = None) -> dict:
    """Schema v9: customer account login identity (replaces the old
    phone+Telegram-linking flow — see services/customer_auth_service.py).
    One row per email, independent of whether that person separately has
    a phone-based guest-reservation row or a telegram_id — merging those
    identities isn't attempted here (same as the old phone/telegram split
    already had before this rewrite)."""
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if row:
            return dict(row)
        cur = conn.execute(
            "INSERT INTO users(email, full_name) VALUES (?, ?)",
            (email, full_name),
        )
        return {"id": cur.lastrowid, "telegram_id": None, "email": email, "full_name": full_name}


def set_email(user_id: int, email: str) -> None:
    """Attaches/updates the login email on an existing user row — e.g. a
    guest who booked by phone and later wants to log in and see that
    reservation. No verification step beyond the OTP itself sent to that
    email during the next login (same trust model the old phone flow had:
    possession of the OTP code is the proof)."""
    with get_connection() as conn:
        conn.execute("UPDATE users SET email = ? WHERE id = ?", (email, user_id))


def link_telegram_id_by_phone(phone: str, telegram_id: int) -> bool:
    """Merges a website-created user (phone-only) with their Telegram
    identity once they connect the bot — e.g. via the "دریافت بلیت در
    تلگرام" deep link. Returns False if that phone has no website-created
    user yet (nothing to link) or if the telegram_id is already used by a
    different user (never silently overwrite)."""
    with get_connection() as conn:
        existing_tg = conn.execute("SELECT id FROM users WHERE telegram_id = ?", (telegram_id,)).fetchone()
        if existing_tg:
            return False
        row = conn.execute("SELECT id FROM users WHERE phone = ? AND telegram_id IS NULL", (phone,)).fetchone()
        if not row:
            return False
        conn.execute("UPDATE users SET telegram_id = ? WHERE id = ?", (telegram_id, row["id"]))
        return True


def get_or_create_user(telegram_id: int, full_name: str | None = None) -> dict:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)
        ).fetchone()
        if row:
            return dict(row)

        cur = conn.execute(
            "INSERT INTO users(telegram_id, full_name) VALUES (?, ?)",
            (telegram_id, full_name),
        )
        return {"id": cur.lastrowid, "telegram_id": telegram_id, "full_name": full_name}


def update_contact_info(telegram_id: int, full_name: str, phone: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE users SET full_name = ?, phone = ? WHERE telegram_id = ?",
            (full_name, phone, telegram_id),
        )


def is_blocked(telegram_id: int) -> bool:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT is_blocked FROM users WHERE telegram_id = ?", (telegram_id,)
        ).fetchone()
        return bool(row and row["is_blocked"])


def count_users() -> int:
    with get_connection() as conn:
        return conn.execute("SELECT COUNT(*) c FROM users").fetchone()["c"]


def get_or_create_by_phone(phone: str, full_name: str) -> dict:
    """
    For phone/manual bookings taken by support staff — no Telegram account
    involved. Reuses an existing row if this phone number already booked
    before (keeps their history in one place), otherwise creates a new
    telegram_id-less user.
    """
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE phone = ? AND telegram_id IS NULL", (phone,)
        ).fetchone()
        if row:
            conn.execute("UPDATE users SET full_name = ? WHERE id = ?", (full_name, row["id"]))
            return dict(row)

        cur = conn.execute(
            "INSERT INTO users(telegram_id, full_name, phone) VALUES (NULL, ?, ?)",
            (full_name, phone),
        )
        return {"id": cur.lastrowid, "telegram_id": None, "full_name": full_name, "phone": phone}
