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


# ---------------------------------------------------------------------
# Phase 1 (reservation-migration finding #4): the expiry and backup loops
# above only ever ran inside bot.py's asyncio event loop — if the site is
# deployed with the unified API (api/server.py) but the Telegram bot isn't
# running (the exact situation this project was in for a while), a
# pending_payment reservation's seat was NEVER freed; the session would
# silently look more and more "full" without actually being full, and the
# database was never backed up either. These two run as plain threads
# inside api/server.py itself, so both work regardless of whether bot.py
# is up. Deliberately NOT a port of the async run_expiry_loop above: this
# skips the Telegram-notification / bank-card-rotation / review-reminder /
# owner-removal chores bundled into that one (all genuinely need `bot`,
# none are correctness-critical the way freeing a seat is) — if bot.py
# IS also running, both loops end up doing the same expiry pass twice on
# occasion, which is harmless (expire_stale_reservations() only acts on
# rows still in pending_payment, so a reservation already expired by one
# loop is simply not picked up by the other).
def run_expiry_loop_sync(interval_seconds: int = CHECK_INTERVAL_SECONDS) -> None:
    """Blocking; call via threading.Thread(daemon=True). Frees capacity for
    reservations whose payment deadline has passed. No Telegram side
    effects — see the module note above for why."""
    import time

    while True:
        try:
            expired = expire_stale_reservations()
            for reservation in expired:
                logs_repo.record(
                    "reservation_expired", None, f"reservation_id={reservation['id']}"
                )
            if expired:
                logger.info("Expired %d stale reservation(s) (sync/API-process loop)", len(expired))
        except Exception:
            logger.exception("Error while running the sync reservation-expiry job")

        time.sleep(interval_seconds)


def run_broadcast_loop_sync(interval_seconds: int = 5) -> None:
    """Blocking; call via threading.Thread(daemon=True). Drains
    broadcast_recipients ('admin sends a segmented email' feature) a
    small batch at a time, same shape as run_outbox_loop's Telegram
    delivery but synchronous (this runs in api/server.py, which has no
    asyncio event loop) and over SMTP instead of the Telegram API. Short
    interval since an admin watching the broadcast's progress on the
    admin page shouldn't wait long between refreshes to see it move."""
    import time
    from database.repositories import broadcasts as broadcasts_repo
    from utils.email_sender import send_email

    while True:
        try:
            for item in broadcasts_repo.list_pending_recipients(limit=20):
                try:
                    broadcast = broadcasts_repo.get(item["broadcast_id"])
                    ok = send_email(
                        to=item["email"],
                        subject=(broadcast or {}).get("subject") or "خانه ماورا",
                        body=(broadcast or {}).get("body") or "",
                    )
                    if ok:
                        broadcasts_repo.mark_recipient_sent(item["id"], item["broadcast_id"])
                    else:
                        broadcasts_repo.mark_recipient_failed(item["id"], item["broadcast_id"], "send_email returned False")
                except Exception as exc:
                    logger.exception("Failed to send broadcast email, recipient id=%s", item["id"])
                    broadcasts_repo.mark_recipient_failed(item["id"], item["broadcast_id"], str(exc))
                broadcasts_repo.mark_done_if_finished(item["broadcast_id"])
        except Exception:
            logger.exception("Error while running the broadcast-send loop")

        time.sleep(interval_seconds)


def run_backup_loop_sync() -> None:
    """Blocking; call via threading.Thread(daemon=True). Same backup logic
    as run_backup_loop() above, just without asyncio — see the module note
    above for why api/server.py needs its own copy."""
    import shutil
    import time
    from datetime import datetime, timezone
    from config.settings import DB_PATH, BASE_DIR

    backup_dir = BASE_DIR / "backups"
    backup_dir.mkdir(exist_ok=True)

    while True:
        try:
            timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M")
            dest = backup_dir / f"mavara_backup_{timestamp}.db"
            shutil.copy2(DB_PATH, dest)
            logger.info("Database backed up to %s (sync/API-process loop)", dest)

            backups = sorted(backup_dir.glob("mavara_backup_*.db"))
            for old in backups[:-14]:
                old.unlink(missing_ok=True)
        except Exception:
            logger.exception("Database backup failed (sync/API-process loop)")

        time.sleep(24 * 60 * 60)
