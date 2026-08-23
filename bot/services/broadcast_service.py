"""
Sending a message to a chosen audience, with basic rate-limit friendliness
(small sleep between sends) and graceful handling of blocked/deleted users.
"""
import asyncio
from datetime import date

from database.connection import get_connection
from database.repositories import reservations as reservations_repo


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
