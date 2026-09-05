"""Admin sets up the live sales-monitoring channel two ways:

1. Forward any message from it (channel_setup_receive below) — the bot
   reads the origin chat id from the forward, the standard reliable way
   to resolve a channel_id without a public username. This only works
   for an actual Telegram *channel* (or a supergroup post sent
   anonymously "as the group") — Telegram sets `forward_from_chat` in
   both those cases.

2. Send /setgroup directly inside a *group* (group_setup below). A
   forward from an ordinary group message carries `forward_from` (the
   member who sent it), never `forward_from_chat` — there is no way to
   recover "this came from group X" from that forward at all, so route
   1 silently can't work for a group no matter how carefully it's
   followed. This route needs no forward: an explicit bot command is
   always delivered to the bot regardless of the group's privacy-mode
   setting, and `message.chat.id` inside the group IS the group's id
   directly — no forwarding required.

Both routes call _configure_monitoring_chat() so they save the same
setting, log the same way, and trigger the same backfill."""
from aiogram import Router, F, Bot
from aiogram.filters import Command
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


async def _configure_monitoring_chat(bot: Bot, chat_id: int, configured_by: int,
                                      reply_to: Message, success_text: str, failed_text: str) -> bool:
    try:
        await bot.send_message(chat_id, fa.CHANNEL_TEST_MESSAGE)
    except Exception:
        await reply_to.answer(failed_text)
        return False

    settings_repo.set("monitoring_channel_id", str(chat_id))
    logs_repo.record("channel_monitoring_configured", configured_by, str(chat_id))
    await reply_to.answer(success_text)

    # Immediately backfill every existing reservation across every active
    # event into the board, in chronological day order — otherwise anything
    # booked before this moment would silently never show up.
    from services import channel_service
    await reply_to.answer("⏳ در حال همگام‌سازی کامل داده‌های موجود با کانال...")
    try:
        synced = await channel_service.resync_all(bot)
        await reply_to.answer(f"✅ همگام‌سازی کامل شد — {synced} روز/رویداد در کانال ثبت شد.")
    except Exception:
        await reply_to.answer("⚠️ همگام‌سازی کامل با خطا مواجه شد — از دکمه «همگام‌سازی دوباره» در تنظیمات استفاده کنید.")
    return True


@router.message(ChannelSetupStates.awaiting_forwarded_message)
async def channel_setup_receive(message: Message, state: FSMContext, bot: Bot) -> None:
    await state.clear()
    origin = message.forward_from_chat
    if not origin:
        await message.answer(fa.CHANNEL_SETUP_NOT_A_FORWARD)
        return
    await _configure_monitoring_chat(
        bot, origin.id, message.from_user.id, message, fa.CHANNEL_SETUP_SUCCESS, fa.CHANNEL_SETUP_FAILED,
    )


@router.message(Command("setgroup"))
async def group_setup(message: Message, bot: Bot) -> None:
    if message.chat.type not in ("group", "supergroup"):
        await message.answer(fa.GROUP_SETUP_WRONG_CHAT)
        return
    await _configure_monitoring_chat(
        bot, message.chat.id, message.from_user.id, message, fa.GROUP_SETUP_SUCCESS, fa.GROUP_SETUP_FAILED,
    )
