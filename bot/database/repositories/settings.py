from database.connection import get_connection


def get(key: str, default: str = "") -> str:
    # No process-local cache: api/server.py and bot.py are two separate
    # OS processes that only share the database (same reasoning as
    # bot_outbox — see its module comment in schema.py). A cache here
    # would mean a setting changed from one process (e.g. the ticket
    # price, edited on the website) silently keeps its stale value in
    # the OTHER process (the Telegram bot, still quoting the old price)
    # until that process happens to restart — exactly the kind of gap
    # that undermines "admin changes something and it takes effect,"
    # which is the entire point of exposing these as admin-editable at
    # all. Settings reads are not hot-path/high-frequency enough (a few
    # per reservation, not per request) for a bare SQLite SELECT to
    # matter for performance.
    with get_connection() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else default


def get_int(key: str, default: int = 0) -> int:
    try:
        return int(get(key, str(default)))
    except ValueError:
        return default


def set(key: str, value: str) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO settings(key, value, updated_at) VALUES (?, ?, datetime('now'))
            ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = datetime('now')
            """,
            (key, value),
        )


def all_settings() -> dict:
    with get_connection() as conn:
        rows = conn.execute("SELECT key, value FROM settings").fetchall()
        return {r["key"]: r["value"] for r in rows}
