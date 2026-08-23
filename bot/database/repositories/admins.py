from database.connection import get_connection


def is_admin(telegram_id: int) -> bool:
    """True for ANY staff member — owner, admin, or operator (support/phone-booking role)."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT 1 FROM admins WHERE telegram_id = ?", (telegram_id,)
        ).fetchone()
        return row is not None


FULL_ACCESS_ROLES = ("owner", "admin")


def is_full_admin(telegram_id: int) -> bool:
    """True only for owner/admin — excludes the limited 'operator' (support) role."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT role FROM admins WHERE telegram_id = ?", (telegram_id,)
        ).fetchone()
        return bool(row and row["role"] in FULL_ACCESS_ROLES)


def get_role(telegram_id: int) -> str | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT role FROM admins WHERE telegram_id = ?", (telegram_id,)
        ).fetchone()
        return row["role"] if row else None


def list_admins() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM admins ORDER BY added_at").fetchall()
        return [dict(r) for r in rows]


def add_admin(telegram_id: int, role: str = "admin") -> None:
    with get_connection() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO admins(telegram_id, role) VALUES (?, ?)",
            (telegram_id, role),
        )


def remove_admin(telegram_id: int) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM admins WHERE telegram_id = ?", (telegram_id,))


def get_pending_removal(telegram_id: int) -> str | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT pending_removal_at FROM admins WHERE telegram_id = ?", (telegram_id,)
        ).fetchone()
        return row["pending_removal_at"] if row else None


def schedule_owner_removal(telegram_id: int, removal_at_iso: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE admins SET pending_removal_at = ? WHERE telegram_id = ? AND role = 'owner'",
            (removal_at_iso, telegram_id),
        )


def cancel_owner_removal(telegram_id: int) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE admins SET pending_removal_at = NULL WHERE telegram_id = ?",
            (telegram_id,),
        )


def list_due_owner_removals(now_iso: str) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM admins WHERE role = 'owner' AND pending_removal_at IS NOT NULL AND pending_removal_at <= ?",
            (now_iso,),
        ).fetchall()
        return [dict(r) for r in rows]
