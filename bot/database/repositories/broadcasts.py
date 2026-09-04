"""Admin broadcasts: segment customers by event/tag, email them (SMS to
follow later). See database/schema.py's comment on BROADCASTS_TABLE for
why this is two tables (broadcast + per-recipient rows) and why sending
is async via utils/scheduler.run_broadcast_loop_sync rather than inline
in the create-broadcast request."""
import json

from database.connection import get_connection


def create(channel: str, subject: str | None, body: str, filters: dict,
           created_by: int | None) -> int:
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO broadcasts(channel, subject, body, filters, created_by) VALUES (?, ?, ?, ?, ?)",
            (channel, subject, body, json.dumps(filters), created_by),
        )
        return cur.lastrowid


def add_recipients(broadcast_id: int, recipients: list[dict]) -> None:
    """recipients: [{user_id, email}, ...]. Also stamps recipient_count
    on the parent row in the same call — the two are always written
    together, never independently, so there's no window where one is
    stale relative to the other."""
    with get_connection() as conn:
        conn.executemany(
            "INSERT INTO broadcast_recipients(broadcast_id, user_id, email) VALUES (?, ?, ?)",
            [(broadcast_id, r["user_id"], r["email"]) for r in recipients],
        )
        conn.execute(
            "UPDATE broadcasts SET recipient_count = ? WHERE id = ?",
            (len(recipients), broadcast_id),
        )


def list_recent(limit: int = 50) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM broadcasts ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]


def get(broadcast_id: int) -> dict | None:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM broadcasts WHERE id = ?", (broadcast_id,)).fetchone()
        return dict(row) if row else None


def list_pending_recipients(limit: int = 20) -> list[dict]:
    """Oldest-first across ALL broadcasts, not grouped — a background
    loop drains this queue regardless of which broadcast a row belongs
    to, same as bot_outbox.list_pending()."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM broadcast_recipients WHERE status = 'pending' ORDER BY id ASC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]


def mark_recipient_sent(recipient_id: int, broadcast_id: int) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE broadcast_recipients SET status = 'sent', sent_at = datetime('now') WHERE id = ?",
            (recipient_id,),
        )
        conn.execute("UPDATE broadcasts SET sent_count = sent_count + 1 WHERE id = ?", (broadcast_id,))


def mark_recipient_failed(recipient_id: int, broadcast_id: int, error: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE broadcast_recipients SET status = 'failed', error = ? WHERE id = ?",
            (error[:500], recipient_id),
        )
        conn.execute("UPDATE broadcasts SET failed_count = failed_count + 1 WHERE id = ?", (broadcast_id,))


def mark_done_if_finished(broadcast_id: int) -> None:
    """A broadcast is 'done' once every one of its recipient rows has
    left 'pending' (sent or failed) — checked after each recipient is
    resolved rather than tracked with a separate counter, so it can
    never drift out of sync with the recipient rows themselves."""
    with get_connection() as conn:
        remaining = conn.execute(
            "SELECT COUNT(*) c FROM broadcast_recipients WHERE broadcast_id = ? AND status = 'pending'",
            (broadcast_id,),
        ).fetchone()["c"]
        if remaining == 0:
            conn.execute(
                "UPDATE broadcasts SET status = 'done', completed_at = datetime('now') WHERE id = ? AND status != 'done'",
                (broadcast_id,),
            )
