from database.connection import get_connection


def get_by_telegram_id(telegram_id: int) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)
        ).fetchone()
        return dict(row) if row else None


def get_or_create_customer(email: str | None = None, phone: str | None = None,
                            full_name: str | None = None) -> dict:
    """Schema v10: THE single identity function for a non-Telegram customer
    — website booking, phone/manual booking, and email login all go through
    this now, instead of three near-identical functions that used three
    slightly different WHERE clauses (that divergence was the actual bug:
    one of them filtered `AND telegram_id IS NULL`, so a phone number
    belonging to a user who'd *also* used the bot was invisible to it and
    got a second, duplicate row).

    Priority is email, per product decision: if an email is given and a
    user already exists with it, that row is reused — never a new one —
    regardless of what phone/full_name accompany it. Falls back to phone
    when no email is given or no row matches it yet. Passing neither is a
    caller bug (raises), since there'd be nothing to look up or create by.

    A row found by one identifier gets the *other* one backfilled onto it
    when the caller supplied it and the row didn't have it yet — this is
    what turns "booked by phone once, logs in by email later" into the
    same row instead of two (see the empty-archive finding this fixes).
    Never overwrites a non-empty phone/email that's already there — only
    fills a blank, so this can't silently reassign an identifier from one
    real person to another.
    """
    if not email and not phone:
        raise ValueError("get_or_create_customer requires an email or a phone")

    with get_connection() as conn:
        row = None
        if email:
            row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if not row and phone:
            row = conn.execute("SELECT * FROM users WHERE phone = ?", (phone,)).fetchone()

        if row:
            row = dict(row)
            updates, params = [], []
            if email and not row.get("email"):
                updates.append("email = ?"); params.append(email); row["email"] = email
            if phone and not row.get("phone"):
                updates.append("phone = ?"); params.append(phone); row["phone"] = phone
            if full_name and not row.get("full_name"):
                updates.append("full_name = ?"); params.append(full_name); row["full_name"] = full_name
            if updates:
                params.append(row["id"])
                conn.execute(f"UPDATE users SET {', '.join(updates)} WHERE id = ?", params)
            return row

        cur = conn.execute(
            "INSERT INTO users(email, phone, full_name) VALUES (?, ?, ?)",
            (email, phone, full_name),
        )
        return {"id": cur.lastrowid, "telegram_id": None, "email": email, "phone": phone, "full_name": full_name}


def get_or_create_user_by_phone(phone: str, full_name: str | None = None) -> dict:
    """Website-originated booking, identified by phone only (no email
    collected at this call site yet). Thin wrapper — see
    get_or_create_customer for the actual (now-unified) lookup/create/merge
    logic. If this same phone number later starts a conversation with the
    bot, `link_telegram_id_by_phone` (below) merges the identity instead of
    creating a duplicate user row — one customer, one row, regardless of
    which channel they used first."""
    return get_or_create_customer(phone=phone, full_name=full_name)


def get_or_create_user_by_email(email: str, full_name: str | None = None) -> dict:
    """Customer account login identity (services/customer_auth_service.py).
    Thin wrapper — see get_or_create_customer. Product decision: an email
    that already has a user row is always reused, never duplicated."""
    return get_or_create_customer(email=email, full_name=full_name)


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
    involved. Thin wrapper — see get_or_create_customer. Used to filter
    `AND telegram_id IS NULL`, which was the actual bug this consolidation
    fixes: a phone number belonging to a user who'd separately used the bot
    was invisible to that filter and got a second, duplicate row created
    for it every time staff took a manual booking for them.
    """
    return get_or_create_customer(phone=phone, full_name=full_name)
