"""Admin sets up two INDEPENDENT Telegram destinations, each the same
two ways (forward a message, or /set*group inside a group):

- monitoring_channel_id (channel_setup_start / group_setup below): the
  live sales-monitoring board (services/channel_service.py) — one
  message per event/day, silently EDITED in place as reservations
  change. No action buttons; Telegram doesn't even push a notification
  for an edit, so this is a dashboard to open, not an alert.

- admin_alerts_channel_id (alerts_channel_setup_start / alerts_group_
  setup below): a fresh message per new reservation-needing-review or
  waiting-list entry (services/settings_service.notify_admin_channel*),
  with the receipt + approve/reject buttons for a reservation. THIS is
  the one that's supposed to interrupt/notify.

These started out sharing one setting (monitoring_channel_id) — the
alerts feature was added later and reused the channel that was already
there to configure, since it existed and was already tested. An admin
who pointed both at the same real Telegram channel then got every
reservation twice: once silently edited into the board, once as a
fresh actionable message — indistinguishable at a glance, since both
showed up in the same feed. Splitting the setting in two lets the admin
either point both at the same channel (if they liked getting both there
before) or split them into two channels/groups — either way the two
message *kinds* are no longer accidentally forced to overlap.

Forwarding only resolves `forward_from_chat` for an actual channel (or
a supergroup post sent anonymously "as the group") — an ordinary group
message forwarded carries `forward_from` (the member who sent it), not
the group itself, so a ordinary group can never complete setup via
forward no matter how carefully it's done. The /set*group commands
exist specifically for that case: a command always reaches the bot
regardless of the group's privacy-mode setting, and `message.chat.id`
inside the group already is the group's id — no forwarding needed."""
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


async def _configure_channel(bot: Bot, chat_id: int, configured_by: int, reply_to: Message, *,
                              setting_key: str, log_action: str, test_message: str,
                              success_text: str, failed_text: str, resync_board: bool) -> bool:
    try:
        await bot.send_message(chat_id, test_message)
    except Exception:
        await reply_to.answer(failed_text)
        return False

    settings_repo.set(setting_key, str(chat_id))
    logs_repo.record(log_action, configured_by, str(chat_id))
    await reply_to.answer(success_text)

    if not resync_board:
        return True

    # Immediately backfill every existing reservation across every active
    # event into the board, in chronological day order — otherwise anything
    # booked before this moment would silently never show up. Only the
    # monitoring channel has a board to backfill — the alerts channel is
    # just a stream of one-off messages going forward, nothing to sync.
    from services import channel_service
    await reply_to.answer("⏳ در حال همگام‌سازی کامل داده‌های موجود با کانال...")
    try:
        synced = await channel_service.resync_all(bot)
        await reply_to.answer(f"✅ همگام‌سازی کامل شد — {synced} روز/رویداد در کانال ثبت شد.")
    except Exception:
        await reply_to.answer("⚠️ همگام‌سازی کامل با خطا مواجه شد — از دکمه «همگام‌سازی دوباره» در تنظیمات استفاده کنید.")
    return True


# ---------------- monitoring channel (silent board) ----------------

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
    await _configure_channel(
        bot, origin.id, message.from_user.id, message,
        setting_key="monitoring_channel_id", log_action="channel_monitoring_configured",
        test_message=fa.CHANNEL_TEST_MESSAGE,
        success_text=fa.CHANNEL_SETUP_SUCCESS, failed_text=fa.CHANNEL_SETUP_FAILED,
        resync_board=True,
    )


@router.message(Command("setgroup"))
async def group_setup(message: Message, bot: Bot) -> None:
    if message.chat.type not in ("group", "supergroup"):
        await message.answer(fa.GROUP_SETUP_WRONG_CHAT)
        return
    await _configure_channel(
        bot, message.chat.id, message.from_user.id, message,
        setting_key="monitoring_channel_id", log_action="channel_monitoring_configured",
        test_message=fa.CHANNEL_TEST_MESSAGE,
        success_text=fa.GROUP_SETUP_SUCCESS, failed_text=fa.GROUP_SETUP_FAILED,
        resync_board=True,
    )


# ---------------- admin alerts channel (actionable, per-request) ----------------

@router.callback_query(F.data == "admin:alerts_channel_setup")
async def alerts_channel_setup_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(ChannelSetupStates.awaiting_forwarded_alerts_message)
    await callback.message.answer(fa.ASK_FORWARD_ALERTS_CHANNEL_MESSAGE)
    await callback.answer()


@router.message(ChannelSetupStates.awaiting_forwarded_alerts_message)
async def alerts_channel_setup_receive(message: Message, state: FSMContext, bot: Bot) -> None:
    await state.clear()
    origin = message.forward_from_chat
    if not origin:
        await message.answer(fa.ALERTS_CHANNEL_SETUP_NOT_A_FORWARD)
        return
    await _configure_channel(
        bot, origin.id, message.from_user.id, message,
        setting_key="admin_alerts_channel_id", log_action="channel_alerts_configured",
        test_message=fa.ALERTS_CHANNEL_TEST_MESSAGE,
        success_text=fa.ALERTS_CHANNEL_SETUP_SUCCESS, failed_text=fa.ALERTS_CHANNEL_SETUP_FAILED,
        resync_board=False,
    )


@router.message(Command("setalertsgroup"))
async def alerts_group_setup(message: Message, bot: Bot) -> None:
    if message.chat.type not in ("group", "supergroup"):
        await message.answer(fa.ALERTS_GROUP_SETUP_WRONG_CHAT)
        return
    await _configure_channel(
        bot, message.chat.id, message.from_user.id, message,
        setting_key="admin_alerts_channel_id", log_action="channel_alerts_configured",
        test_message=fa.ALERTS_CHANNEL_TEST_MESSAGE,
        success_text=fa.ALERTS_GROUP_SETUP_SUCCESS, failed_text=fa.ALERTS_GROUP_SETUP_FAILED,
        resync_board=False,
    )
