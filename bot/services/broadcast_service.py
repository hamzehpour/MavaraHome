"""
Sending a message to a chosen audience — two independent features that
happen to share this module by concept ("broadcast to a segment"), not by
code path:

1. Telegram broadcast (original): an admin, inside the bot itself, picks
   an audience of Telegram users (everyone / attended today / didn't
   attend / one session / one day) and the bot sends them a message
   directly, with a small rate-limit-friendly sleep between sends. See
   handlers/admin_panel.py's broadcast_* handlers.

2. Website admin broadcast (reservation-migration follow-up): an admin on
   the website builds a customer segment by event/tag and emails them
   (SMS later). Deliberately async — see database/schema.py's comment on
   BROADCASTS_TABLE — so creating a broadcast to a large audience doesn't
   block the admin's HTTP request on a loop of individual SMTP
   round-trips. Function names below are prefixed `email_` specifically
   to avoid colliding with #1's `resolve_audience`/`broadcast`, which
   take a completely different shape (Telegram target keyword + user id
   list, vs. event/tag filters + customer rows).
"""
import asyncio
import json
from datetime import date

from database.connection import get_connection
from database.repositories import reservations as reservations_repo
from database.repositories import broadcasts as broadcasts_repo


# ═══════════ 1. Telegram broadcast (bot-side, pre-existing) ═══════════

def get_all_user_ids() -> list[int]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT telegram_id FROM users WHERE is_blocked = 0 AND telegram_id IS NOT NULL"
        ).fetchall()
        return [row["telegram_id"] for row in rows]


def resolve_audience(target: str, **kwargs) -> list[int]:
    today = date.today().isoformat()
    if target == "all":
        return get_all_user_ids()
    if target == "seen":
        return reservations_repo.telegram_ids_seen_show(today)
    if target == "not_seen":
        return reservations_repo.telegram_ids_not_seen_show(today)
    if target == "session":
        return reservations_repo.telegram_ids_for_session(kwargs["session_id"])
    if target == "date":
        return reservations_repo.telegram_ids_for_date(kwargs["event_id"], kwargs["date_iso"])
    return []


async def broadcast(bot, text: str, user_ids: list[int]) -> tuple[int, int]:
    success, failed = 0, 0
    for telegram_id in user_ids:
        try:
            await bot.send_message(telegram_id, text)
            success += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.05)  # stay well under Telegram's rate limits
    return success, failed


# ═══════════ 2. Website admin broadcast (email, segment by event/tag) ═══════════

def resolve_email_audience(event_ids: list[int] | None, tags: list[str] | None) -> list[dict]:
    """Distinct customers (by user id) with at least one APPROVED
    reservation — i.e. an actual completed purchase, not just an
    abandoned/pending one — matching the filter. event_ids and tags
    combine as OR (an event matching either counts), matching the two
    being two different ways to point at the same kind of audience
    rather than two conditions that must both hold. No filters at all
    (both empty/None) means every customer who has ever completed a
    purchase, of anything.

    Tag matching is done in Python, not SQL: events.tags is a JSON text
    column and event counts are small (this is a single-venue site, not
    a marketplace), so parsing here is simpler and more portable than
    relying on a specific SQLite build's JSON1 support.
    """
    with get_connection() as conn:
        resolved_event_ids = set(event_ids or [])
        if tags:
            for e in conn.execute("SELECT id, tags FROM events").fetchall():
                try:
                    ev_tags = json.loads(e["tags"]) if e["tags"] else []
                except (json.JSONDecodeError, TypeError):
                    ev_tags = []
                if any(t in ev_tags for t in tags):
                    resolved_event_ids.add(e["id"])

        where_event = ""
        params: list = []
        if event_ids or tags:
            if not resolved_event_ids:
                return []  # filters were given but matched no event at all
            placeholders = ",".join("?" * len(resolved_event_ids))
            where_event = f"AND e.id IN ({placeholders})"
            params = list(resolved_event_ids)

        rows = conn.execute(
            f"""
            SELECT DISTINCT u.id AS user_id, u.full_name, u.email, u.phone
            FROM reservations r
            JOIN users u ON u.id = r.user_id
            JOIN sessions s ON s.id = r.session_id
            JOIN events e ON e.id = s.event_id
            WHERE r.status = 'approved' {where_event}
            ORDER BY u.full_name
            """,
            params,
        ).fetchall()
        return [dict(r) for r in rows]


def create_email_broadcast(channel: str, subject: str | None, body: str,
                            event_ids: list[int] | None, tags: list[str] | None,
                            created_by: int | None) -> dict:
    """Resolves the audience right now (so the admin sees a real count
    back, not a promise), then queues one broadcast_recipients row per
    emailable customer — a customer with no email on file is counted in
    `matched` but not `queued`, since there's nowhere to send this
    version of a broadcast (channel='email' only, for now)."""
    audience = resolve_email_audience(event_ids, tags)
    emailable = [c for c in audience if c.get("email")]

    broadcast_id = broadcasts_repo.create(
        channel=channel, subject=subject, body=body,
        filters={"event_ids": event_ids or [], "tags": tags or []},
        created_by=created_by,
    )
    if emailable:
        broadcasts_repo.add_recipients(
            broadcast_id,
            [{"user_id": c["user_id"], "email": c["email"]} for c in emailable],
        )
    else:
        # Nothing to send — don't leave it sitting as 'pending' forever
        # waiting for a background loop that will never find work for it.
        with get_connection() as conn:
            conn.execute(
                "UPDATE broadcasts SET status = 'done', completed_at = datetime('now') WHERE id = ?",
                (broadcast_id,),
            )

    return {
        "id": broadcast_id,
        "matched": len(audience),
        "queued": len(emailable),
    }


def list_email_broadcasts() -> list[dict]:
    rows = broadcasts_repo.list_recent()
    for r in rows:
        try:
            r["filters"] = json.loads(r["filters"]) if r["filters"] else {}
        except (json.JSONDecodeError, TypeError):
            r["filters"] = {}
    return rows
