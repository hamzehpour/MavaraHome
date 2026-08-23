"""
The most sensitive admin actions: setting the ownership passcode, and
adding/removing an 'owner'. Gated by IsOwner (not just IsFullAdmin) —
an 'admin' role, even with full day-to-day access, cannot touch this.
"""
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from texts import fa
from filters.admin_filter import IsOwner
from states.owner_states import OwnerPasscodeStates, AddOwnerStates
from keyboards.admin import owner_management_keyboard
from services import owner_service
from database.repositories import admins as admins_repo
from database.repositories import logs as logs_repo

router = Router(name="owner_management")
router.message.filter(IsOwner())
router.callback_query.filter(IsOwner())


@router.callback_query(F.data == "admin:owner_management")
async def owner_management_menu(callback: CallbackQuery) -> None:
    await callback.message.answer("👑 مدیریت مالکیت:", reply_markup=owner_management_keyboard())
    await callback.answer()


@router.callback_query(F.data == "owner:set_passcode")
async def set_passcode_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(OwnerPasscodeStates.awaiting_new_passcode)
    await callback.message.answer(fa.ASK_SET_OWNER_PASSCODE)
    await callback.answer()


@router.message(OwnerPasscodeStates.awaiting_new_passcode)
async def set_passcode_save(message: Message, state: FSMContext) -> None:
    passcode = message.text.strip()
    if len(passcode) < 4:
        await message.answer("❌ رمز باید حداقل ۴ کاراکتر باشد.")
        return

    owner_service.set_passcode(passcode)
    logs_repo.record("owner_passcode_changed", message.from_user.id)
    await state.clear()
    # Delete the message containing the plaintext passcode so it doesn't
    # linger in chat history.
    try:
        await message.delete()
    except Exception:
        pass
    await message.answer(fa.OWNER_PASSCODE_SET)


@router.callback_query(F.data == "owner:add")
async def add_owner_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not owner_service.is_passcode_set():
        await callback.answer(fa.OWNER_PASSCODE_NOT_SET, show_alert=True)
        return
    await state.set_state(AddOwnerStates.awaiting_target)
    await callback.message.answer(fa.ASK_STAFF_TELEGRAM_ID)
    await callback.answer()


@router.message(AddOwnerStates.awaiting_target)
async def add_owner_target(message: Message, state: FSMContext, bot: Bot) -> None:
    raw = message.text.strip()
    if raw.startswith("@"):
        try:
            chat = await bot.get_chat(raw)
            telegram_id = chat.id
        except Exception:
            await message.answer("❌ این یوزرنیم پیدا نشد. آیدی عددی را وارد کنید یا مطمئن شوید ربات را استارت کرده.")
            return
    elif raw.lstrip("-").isdigit():
        telegram_id = int(raw)
    else:
        await message.answer("❌ لطفاً یک آیدی عددی یا یوزرنیم با @ وارد کنید.")
        return

    await state.update_data(new_owner_id=telegram_id)
    await state.set_state(AddOwnerStates.awaiting_passcode)
    await message.answer(fa.ASK_OWNER_PASSCODE_TO_CONFIRM)


@router.message(AddOwnerStates.awaiting_passcode)
async def add_owner_confirm(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    await state.clear()

    if not owner_service.check_passcode(message.text.strip()):
        logs_repo.record("owner_add_failed_wrong_passcode", message.from_user.id)
        await message.answer(fa.OWNER_PASSCODE_WRONG)
        return

    admins_repo.add_admin(data["new_owner_id"], role="owner")
    logs_repo.record("owner_added", message.from_user.id, f"new_owner={data['new_owner_id']}",
                      target_type="admin", target_id=data["new_owner_id"])
    await message.answer(fa.NEW_OWNER_ADDED)


@router.callback_query(F.data.startswith("owner_removal_cancel:"))
async def cancel_owner_removal(callback: CallbackQuery) -> None:
    telegram_id = int(callback.data.split(":")[1])
    owner_service.cancel_owner_removal(telegram_id)
    logs_repo.record("owner_removal_cancelled", callback.from_user.id,
                      target_type="admin", target_id=telegram_id)
    await callback.message.edit_text(fa.OWNER_REMOVAL_CANCELLED)
    await callback.answer()
