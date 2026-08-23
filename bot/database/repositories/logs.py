from database.connection import get_connection


def record(action: str, telegram_id: int | None = None, details: str = "",
           target_type: str | None = None, target_id: int | None = None) -> None:
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO logs(action, telegram_id, details, target_type, target_id) VALUES (?, ?, ?, ?, ?)",
            (action, telegram_id, details, target_type, target_id),
        )


def recent(limit: int = 100) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM logs ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]


def list_all(limit: int = 5000) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM logs ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]
