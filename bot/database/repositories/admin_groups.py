"""
Additive fine-grained permission groups (finance/sales/content), layered on
TOP of the existing owner/admin/operator single-role system in
database/repositories/admins.py — that system is untouched and keeps
working exactly as before. A staff member can hold zero or more of these
groups in addition to their base role.
"""
from database.connection import get_connection


def get_groups(telegram_id: int) -> set[str]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT group_name FROM admin_groups WHERE telegram_id = ?", (telegram_id,)
        ).fetchall()
        return {r["group_name"] for r in rows}


def add_group(telegram_id: int, group_name: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO admin_groups(telegram_id, group_name) VALUES (?, ?)",
            (telegram_id, group_name),
        )


def remove_group(telegram_id: int, group_name: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM admin_groups WHERE telegram_id = ? AND group_name = ?",
            (telegram_id, group_name),
        )


def remove_all_groups(telegram_id: int) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM admin_groups WHERE telegram_id = ?", (telegram_id,))


def list_telegram_ids_with_group(group_name: str) -> list[int]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT DISTINCT telegram_id FROM admin_groups WHERE group_name = ?", (group_name,)
        ).fetchall()
        return [r["telegram_id"] for r in rows]
