"""
Tiny in-process background loop — no extra dependency (no Celery/APScheduler)
needed for a single job at this scale. Runs inside the same asyncio event
loop as the bot (see bot.py).
"""
import asyncio

from aiogram import Bot

from services.reservation_service import expire_stale_reservations
from database.repositories import logs as logs_repo
from utils.logger import get_logger

logger = get_logger()

CHECK_INTERVAL_SECONDS = 120


async def run_expiry_loop(bot: Bot) -> None:
    while True:
        try:
            expired = expire_stale_reservations()
            for reservation in expired:
                logs_repo.record(
                    "reservation_expired", None, f"reservation_id={reservation['id']}"
                )
                with_user = _resolve_telegram_id(reservation["user_id"])
                if with_user:
                    try:
                        await bot.send_message(
                            with_user,
                            "⌛️ مهلت پرداخت رزرو شما به پایان رسید و رزرو لغو شد. "
                            "در صورت تمایل می‌توانید دوباره از منوی «رزرو بلیت» اقدام کنید.",
                        )
                    except Exception:
                        pass
                try:
                    from services import channel_service
                    await channel_service.on_reservation_changed(bot, reservation["session_id"])
                except Exception:
                    logger.exception("Failed to refresh channel board after expiry")
            if expired:
                logger.info("Expired %d stale reservation(s)", len(expired))

            await _maybe_rotate_bank_card()
            await _send_review_reminders(bot)
            await _process_owner_removals(bot)
        except Exception:
            logger.exception("Error while running the reservation-expiry job")

        await asyncio.sleep(CHECK_INTERVAL_SECONDS)


async def _process_owner_removals(bot: Bot) -> None:
    from services import owner_service

    due = owner_service.process_due_removals()
    for row in due:
        logger.info("Finalized scheduled owner removal for telegram_id=%s", row["telegram_id"])
        try:
            await bot.send_message(row["telegram_id"], "شما دیگر مالک این ربات نیستید (طبق فرایند حذف امن انجام‌شده).")
        except Exception:
            pass


async def _send_review_reminders(bot: Bot) -> None:
    """
    Reservations sitting in pending_review (or awaiting_buyer_confirmation)
    longer than `review_reminder_minutes` get staff pinged — this never
    frees the seat, it only nudges staff to actually decide. After the
    first ping, it repeats every `review_reminder_repeat_minutes` (like an
    alarm) until the reservation is finally resolved — a single one-time
    nudge was easy to miss and lost the seat-holding safety net's whole point.
    """
    from database.connection import get_connection
    from database.repositories import settings as settings_repo
    from datetime import datetime, timedelta, timezone

    first_wait = settings_repo.get_int("review_reminder_minutes", 60)
    repeat_every = settings_repo.get_int("review_reminder_repeat_minutes", 10)
    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=first_wait)).isoformat(timespec="seconds")
    repeat_cutoff = (datetime.now(timezone.utc) - timedelta(minutes=repeat_every)).isoformat(timespec="seconds")

    with get_connection() as conn:
        stale = conn.execute(
            """
            SELECT id, created_at FROM reservations
            WHERE status IN ('pending_review', 'awaiting_buyer_confirmation')
              AND created_at < ?
            """,
            (cutoff,),
        ).fetchall()

        for row in stale:
            last_reminder = conn.execute(
                "SELECT created_at FROM logs WHERE action = 'review_reminder_sent' "
                "AND details = ? ORDER BY created_at DESC LIMIT 1",
                (str(row["id"]),),
            ).fetchone()
            if last_reminder and last_reminder["created_at"] > repeat_cutoff:
                continue  # already reminded recently — wait for the next repeat window

            from services import permissions
            for telegram_id in permissions.list_staff_with_permission(permissions.APPROVE_PAYMENTS):
                try:
                    await bot.send_message(
                        telegram_id,
                        f"⏰ یادآوری: رزرو شماره {row['id']} همچنان منتظر بررسی است "
                        "— لطفاً هرچه زودتر تصمیم بگیرید.",
                    )
                except Exception:
                    pass
            conn.execute(
                "INSERT INTO logs(action, telegram_id, details) VALUES ('review_reminder_sent', NULL, ?)",
                (str(row["id"]),),
            )


async def _maybe_rotate_bank_card() -> None:
    from database.repositories import settings as settings_repo
    from database.repositories import bank_cards as bank_cards_repo
    from datetime import datetime, timezone

    if settings_repo.get("auto_rotate_cards", "0") != "1":
        return

    last = settings_repo.get("card_rotation_last_date", "")
    today = datetime.now(timezone.utc).date().isoformat()
    if last:
        last_date = datetime.fromisoformat(last).date()
        if (datetime.now(timezone.utc).date() - last_date).days < 7:
            return

    rotated = bank_cards_repo.rotate_to_next()
    if rotated:
        settings_repo.set("card_rotation_last_date", today)
        logs_repo.record("bank_card_auto_rotated", None, f"card_id={rotated['id']}")
        logger.info("Auto-rotated active bank card to id=%s", rotated["id"])


def _resolve_telegram_id(user_id: int) -> int | None:
    from database.connection import get_connection
    with get_connection() as conn:
        row = conn.execute("SELECT telegram_id FROM users WHERE id = ?", (user_id,)).fetchone()
        return row["telegram_id"] if row and row["telegram_id"] else None


async def run_outbox_loop(bot: Bot) -> None:
    """Phase 4/5: delivers messages the API process (api/server.py) has
    queued in bot_outbox — OTP codes and admin chat replies — since the
    API and the bot are two separate processes that only share the
    database (see database/schema.py's comment on BOT_OUTBOX_TABLE for
    why). Short interval (5s) because OTP codes are time-sensitive; still
    cheap since it's a single indexed SELECT most cycles."""
    from database.repositories import bot_outbox as outbox_repo

    while True:
        try:
            for item in outbox_repo.list_pending():
                try:
                    await bot.send_message(item["telegram_id"], item["body"])
                    outbox_repo.mark_sent(item["id"])
                except Exception:
                    logger.exception("Failed to deliver outbox message id=%s", item["id"])
                    outbox_repo.mark_failed(item["id"])
        except Exception:
            logger.exception("Error while running the outbox delivery job")

        await asyncio.sleep(5)


async def run_backup_loop() -> None:
    """
    Copies the SQLite database into backups/ once every 24 hours, keeping
    the last 14 dated copies. If the database gets corrupted or someone
    deletes something by mistake, this is the recovery path.
    """
    import shutil
    from pathlib import Path
    from datetime import datetime, timezone
    from config.settings import DB_PATH, BASE_DIR

    backup_dir = BASE_DIR / "backups"
    backup_dir.mkdir(exist_ok=True)

    while True:
        try:
            timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M")
            dest = backup_dir / f"mavara_backup_{timestamp}.db"
            shutil.copy2(DB_PATH, dest)
            logger.info("Database backed up to %s", dest)

            # Keep only the most recent 14 backups.
            backups = sorted(backup_dir.glob("mavara_backup_*.db"))
            for old in backups[:-14]:
                old.unlink(missing_ok=True)
        except Exception:
            logger.exception("Database backup failed")

        await asyncio.sleep(24 * 60 * 60)
