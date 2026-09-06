"""
Entrypoint. Run with: python bot.py
Responsible only for wiring things together — no business logic here.
"""
import asyncio

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from config.settings import BOT_TOKEN, APP_NAME, VERSION
from database.schema import init_db
from middlewares.logging_middleware import LoggingMiddleware
from utils.logger import get_logger
from utils.scheduler import run_expiry_loop, run_backup_loop, run_outbox_loop

from handlers import (
    common, booking, payment, admin_reservations, admin_events, admin_panel,
    staff_manual_booking, support, bank_cards, overflow_requests,
    owner_management, channel_setup, reopening_interest,
)

logger = get_logger()


async def main() -> None:
    if not BOT_TOKEN:
        raise RuntimeError(
            "BOT_TOKEN is not set. Copy .env.example to .env and fill it in."
        )
    init_db()
    logger.info("%s v%s starting up", APP_NAME, VERSION)

    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())

    dp.message.middleware(LoggingMiddleware())
    dp.callback_query.middleware(LoggingMiddleware())

    # Order matters: more specific/state-scoped routers first is not required
    # by aiogram (state filters already scope them), but keeping admin
    # routers grouped together and booking/payment together aids readability.
    dp.include_router(common.router)
    dp.include_router(booking.router)
    dp.include_router(payment.router)
    dp.include_router(admin_reservations.router)
    dp.include_router(admin_events.router)
    dp.include_router(admin_panel.router)
    dp.include_router(staff_manual_booking.router)
    dp.include_router(support.router)
    dp.include_router(bank_cards.router)
    dp.include_router(overflow_requests.router)
    dp.include_router(owner_management.router)
    dp.include_router(channel_setup.router)
    dp.include_router(reopening_interest.router)

    await bot.delete_webhook(drop_pending_updates=True)
    asyncio.create_task(run_expiry_loop(bot))
    asyncio.create_task(run_backup_loop())
    asyncio.create_task(run_outbox_loop(bot))
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped.")
