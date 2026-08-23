"""Two-way text support: buyer writes a message -> every staff member gets
it with a Reply button -> whoever replies first, their text goes straight
back to the buyer."""
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from texts import fa
from states.support_states import SupportStates, SupportReplyStates
from keyboards.main_menu import main_menu_keyboard
from database.repositories import admins as admins_repo
from database.repositories import users as users_repo
from database.repositories import logs as logs_repo

router = Router(name="support")


@router.message(F.text == fa.SUPPORT_MENU_MESSAGE)
async def ask_support_message(message: Message, state: FSMContext) -> None:
    await state.set_state(SupportStates.awaiting_message)
    await message.answer(fa.ASK_SUPPORT_MESSAGE)


@router.message(SupportStates.awaiting_message)
async def forward_support_message(message: Message, state: FSMContext, bot: Bot) -> None:
    await state.clear()
    user = users_repo.get_or_create_user(message.from_user.id, message.from_user.full_name)

    reply_kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="↩️ پاسخ", callback_data=f"support_reply:{message.from_user.id}")
    ]])
    text = fa.support_ticket_notify(user.get("full_name"), user.get("phone"), message.text or "")

    for admin in admins_repo.list_admins():
        try:
            await bot.send_message(admin["telegram_id"], text, reply_markup=reply_kb)
        except Exception:
            continue

    logs_repo.record("support_message", message.from_user.id, (message.text or "")[:200])
    await message.answer(fa.SUPPORT_MESSAGE_SENT, reply_markup=main_menu_keyboard())


@router.callback_query(F.data.startswith("support_reply:"))
async def start_reply(callback: CallbackQuery, state: FSMContext) -> None:
    if not admins_repo.is_admin(callback.from_user.id):
        await callback.answer()
        return
    target_user_id = int(callback.data.split(":", 1)[1])
    await state.update_data(support_reply_target=target_user_id)
    await state.set_state(SupportReplyStates.awaiting_reply)
    await callback.message.answer(fa.ASK_SUPPORT_REPLY)
    await callback.answer()


@router.message(SupportReplyStates.awaiting_reply)
async def send_reply(message: Message, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    target = data.get("support_reply_target")
    await state.clear()
    if not target:
        return

    try:
        await bot.send_message(target, fa.support_reply_received(message.text or ""))
        await message.answer(fa.SUPPORT_REPLY_SENT_STAFF_SIDE)
        logs_repo.record("support_reply", message.from_user.id, f"to={target}")
    except Exception:
        await message.answer("⚠️ ارسال پاسخ به کاربر ناموفق بود.")
