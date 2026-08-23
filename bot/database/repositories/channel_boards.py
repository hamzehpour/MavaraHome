from database.connection import get_connection


def get_message_id(event_id: int, session_date: str, part_index: int) -> int | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT message_id FROM channel_boards WHERE event_id = ? AND session_date = ? AND part_index = ?",
            (event_id, session_date, part_index),
        ).fetchone()
        return row["message_id"] if row else None


def upsert_message_id(event_id: int, session_date: str, part_index: int, message_id: int) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO channel_boards(event_id, session_date, part_index, message_id)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(event_id, session_date, part_index) DO UPDATE SET message_id = excluded.message_id
            """,
            (event_id, session_date, part_index, message_id),
        )


def list_parts(event_id: int, session_date: str) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM channel_boards WHERE event_id = ? AND session_date = ? ORDER BY part_index",
            (event_id, session_date),
        ).fetchall()
        return [dict(r) for r in rows]


def delete_part(event_id: int, session_date: str, part_index: int) -> None:
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM channel_boards WHERE event_id = ? AND session_date = ? AND part_index = ?",
            (event_id, session_date, part_index),
        )


def has_any_board_ever() -> bool:
    with get_connection() as conn:
        row = conn.execute("SELECT 1 FROM channel_boards LIMIT 1").fetchone()
        return row is not None


def has_board_for_day(event_id: int, session_date: str) -> bool:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT 1 FROM channel_boards WHERE event_id = ? AND session_date = ? LIMIT 1",
            (event_id, session_date),
        ).fetchone()
        return row is not None
