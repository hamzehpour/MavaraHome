from database.connection import get_connection


def get_entry_with_context(entry_id: int) -> dict | None:
    from database.connection import get_connection
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT w.*, u.telegram_id, u.full_name, u.phone,
                   s.capacity, s.session_date, s.session_time, s.event_id
            FROM waiting_list w
            JOIN users u ON u.id = w.user_id
            JOIN sessions s ON s.id = w.session_id
            WHERE w.id = ?
            """,
            (entry_id,),
        ).fetchone()
        return dict(row) if row else None


def add(user_id: int, session_id: int, people: int) -> int:
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO waiting_list(user_id, session_id, people) VALUES (?, ?, ?)",
            (user_id, session_id, people),
        )
        return cur.lastrowid


def list_for_session(session_id: int) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM waiting_list WHERE session_id = ? AND status = 'waiting' ORDER BY created_at",
            (session_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def set_status(entry_id: int, status: str) -> None:
    with get_connection() as conn:
        conn.execute("UPDATE waiting_list SET status = ? WHERE id = ?", (status, entry_id))


def set_status_if(entry_id: int, expected_status: str, new_status: str) -> bool:
    with get_connection() as conn:
        cur = conn.execute(
            "UPDATE waiting_list SET status = ? WHERE id = ? AND status = ?",
            (new_status, entry_id, expected_status),
        )
        return cur.rowcount > 0
