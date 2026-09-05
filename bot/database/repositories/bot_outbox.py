"""Durable queue table so api/server.py (a separate OS process from
bot.py) can ask the bot to deliver a Telegram message, using only the
database they already both share — see the comment on BOT_OUTBOX_TABLE in
database/schema.py for why this exists instead of an HTTP callback."""
from database.connection import get_connection


def enqueue(telegram_id: int, body: str, kind: str = "text",
            reservation_id: int | None = None, photo_ref: str | None = None) -> int:
    """reservation_id/photo_ref are only used by kind="receipt_review" (see
    utils/scheduler.run_outbox_loop) — a plain "text" message leaves both
    NULL, same as before these columns existed."""
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO bot_outbox(telegram_id, kind, body, reservation_id, photo_ref) VALUES (?, ?, ?, ?, ?)",
            (telegram_id, kind, body, reservation_id, photo_ref),
        )
        return cur.lastrowid


def list_pending(limit: int = 50) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM bot_outbox WHERE status='pending' ORDER BY id ASC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]


def mark_sent(message_id: int) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE bot_outbox SET status='sent', sent_at=datetime('now') WHERE id=?", (message_id,)
        )


def mark_failed(message_id: int) -> None:
    with get_connection() as conn:
        conn.execute("UPDATE bot_outbox SET status='failed' WHERE id=?", (message_id,))
