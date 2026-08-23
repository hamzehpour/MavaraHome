from database.connection import get_connection


def list_sessions_for_event(event_id: int) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT * FROM sessions
            WHERE event_id = ? AND status = 'active'
            ORDER BY session_date, session_time
            """,
            (event_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_session(session_id: int) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()
        return dict(row) if row else None


def create_session(event_id: int, session_date: str, session_time: str, capacity: int) -> int:
    with get_connection() as conn:
        cur = conn.execute(
            """
            INSERT INTO sessions(event_id, session_date, session_time, capacity)
            VALUES (?, ?, ?, ?)
            """,
            (event_id, session_date, session_time, capacity),
        )
        return cur.lastrowid


def update_capacity(session_id: int, capacity: int) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE sessions SET capacity = ? WHERE id = ?", (capacity, session_id)
        )


def set_session_status(session_id: int, status: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE sessions SET status = ? WHERE id = ?", (status, session_id)
        )


def slot_exists(event_id: int, session_date: str, session_time: str) -> bool:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT 1 FROM sessions WHERE event_id = ? AND session_date = ? AND session_time = ?",
            (event_id, session_date, session_time),
        ).fetchone()
        return row is not None


def list_sessions_for_event_admin(event_id: int) -> list[dict]:
    """ALL sessions (active + inactive) for the admin session-list screen,
    sorted chronologically — session_date is stored as ISO (YYYY-MM-DD),
    so a plain string sort is already correct chronological order."""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT * FROM sessions WHERE event_id = ?
            ORDER BY session_date ASC, session_time ASC
            """,
            (event_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def delete_session(session_id: int) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))


def update_session(session_id: int, session_date: str = None, session_time: str = None,
                    capacity: int = None) -> None:
    fields, params = [], []
    if session_date is not None:
        fields.append("session_date = ?"); params.append(session_date)
    if session_time is not None:
        fields.append("session_time = ?"); params.append(session_time)
    if capacity is not None:
        fields.append("capacity = ?"); params.append(capacity)
    if not fields:
        return
    params.append(session_id)
    with get_connection() as conn:
        conn.execute(f"UPDATE sessions SET {', '.join(fields)} WHERE id = ?", params)


def reserved_count(session_id: int, conn=None) -> int:
    """
    Sum of people in reservations that actually hold a seat
    (pending_payment / pending_review / approved all occupy capacity;
    rejected/cancelled/expired free it up again).
    Accepts an optional open connection so callers can run this inside
    the same transaction as the insert (see reservation_service).
    """
    query = """
        SELECT COALESCE(SUM(people), 0) c FROM reservations
        WHERE session_id = ?
        AND status IN ('pending_payment', 'pending_review', 'awaiting_buyer_confirmation', 'approved')
    """
    if conn is not None:
        return conn.execute(query, (session_id,)).fetchone()["c"]

    with get_connection() as new_conn:
        return new_conn.execute(query, (session_id,)).fetchone()["c"]
