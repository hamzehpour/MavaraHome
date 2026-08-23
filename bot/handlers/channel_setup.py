"""Admin sets up the live sales-monitoring channel by forwarding any
message from it — the bot reads the origin chat id from the forward,
which is the standard reliable way to resolve a channel_id without
requiring a public username."""
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from texts import fa
from filters.admin_filter import IsFullAdmin
from states.channel_states import ChannelSetupStates
from database.repositories import settings as settings_repo
from database.repositories import logs as logs_repo

router = Router(name="channel_setup")
router.message.filter(IsFullAdmin())
router.callback_query.filter(IsFullAdmin())


@router.callback_query(F.data == "admin:channel_setup")
async def channel_setup_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(ChannelSetupStates.awaiting_forwarded_message)
    await callback.message.answer(fa.ASK_FORWARD_CHANNEL_MESSAGE)
    await callback.answer()


@router.message(ChannelSetupStates.awaiting_forwarded_message)
async def channel_setup_receive(message: Message, state: FSMContext, bot: Bot) -> None:
    await state.clear()
    origin = message.forward_from_chat
    if not origin:
        await message.answer(fa.CHANNEL_SETUP_NOT_A_FORWARD)
        return

    try:
        sent = await bot.send_message(origin.id, fa.CHANNEL_TEST_MESSAGE)
    except Exception:
        await message.answer(fa.CHANNEL_SETUP_FAILED)
        return

    settings_repo.set("monitoring_channel_id", str(origin.id))
    logs_repo.record("channel_monitoring_configured", message.from_user.id, str(origin.id))
    await message.answer(fa.CHANNEL_SETUP_SUCCESS)

    # Immediately backfill every existing reservation across every active
    # event into the board, in chronological day order — otherwise anything
    # booked before this moment would silently never show up.
    from services import channel_service
    await message.answer("⏳ در حال همگام‌سازی کامل داده‌های موجود با کانال...")
    try:
        synced = await channel_service.resync_all(bot)
        await message.answer(f"✅ همگام‌سازی کامل شد — {synced} روز/رویداد در کانال ثبت شد.")
    except Exception:
        await message.answer("⚠️ همگام‌سازی کامل با خطا مواجه شد — از دکمه «همگام‌سازی دوباره» در تنظیمات استفاده کنید.")
