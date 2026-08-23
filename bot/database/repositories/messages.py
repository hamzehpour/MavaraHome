from database.connection import get_connection


def add_message(user_id: int, sender: str, body: str, admin_id: int | None = None,
                 attachment_path: str | None = None) -> dict:
    """sender is 'customer' or 'admin'. A customer message marks itself
    read-by-customer (obviously) and unread-by-admin; an admin message is
    the mirror image — this is what drives unread badges on both sides."""
    is_read_by_admin = 1 if sender == "admin" else 0
    is_read_by_customer = 1 if sender == "customer" else 0
    with get_connection() as conn:
        cur = conn.execute(
            """INSERT INTO messages(user_id, sender, admin_id, body, attachment_path,
                                     is_read_by_admin, is_read_by_customer)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (user_id, sender, admin_id, body, attachment_path, is_read_by_admin, is_read_by_customer),
        )
        row = conn.execute("SELECT * FROM messages WHERE id=?", (cur.lastrowid,)).fetchone()
        return dict(row)


def list_for_user(user_id: int, limit: int = 200) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM messages WHERE user_id=? ORDER BY created_at ASC, id ASC LIMIT ?",
            (user_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]


def mark_read_by_customer(user_id: int) -> None:
    with get_connection() as conn:
        conn.execute("UPDATE messages SET is_read_by_customer=1 WHERE user_id=?", (user_id,))


def mark_read_by_admin(user_id: int) -> None:
    with get_connection() as conn:
        conn.execute("UPDATE messages SET is_read_by_admin=1 WHERE user_id=?", (user_id,))


def list_threads() -> list[dict]:
    """One row per customer who has ever exchanged a message, newest
    activity first, with the last message preview and admin-unread count
    — used by the admin inbox list (pages/admin/messages.html)."""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT u.id AS user_id, u.full_name, u.phone,
                   (SELECT body FROM messages m2 WHERE m2.user_id=u.id ORDER BY m2.created_at DESC, m2.id DESC LIMIT 1) AS last_body,
                   (SELECT created_at FROM messages m3 WHERE m3.user_id=u.id ORDER BY m3.created_at DESC, m3.id DESC LIMIT 1) AS last_at,
                   (SELECT COUNT(*) FROM messages m4 WHERE m4.user_id=u.id AND m4.is_read_by_admin=0) AS unread_count
            FROM users u
            WHERE EXISTS (SELECT 1 FROM messages m WHERE m.user_id=u.id)
            ORDER BY last_at DESC
            """
        ).fetchall()
        return [dict(r) for r in rows]


def unread_count_for_customer(user_id: int) -> int:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT COUNT(*) c FROM messages WHERE user_id=? AND is_read_by_customer=0", (user_id,)
        ).fetchone()
        return row["c"]
