from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from texts import fa
from filters.admin_filter import IsFullAdmin
from states.bank_card_states import BankCardStates
from keyboards.admin import bank_cards_menu_keyboard, confirm_keyboard
from database.repositories import bank_cards as bank_cards_repo
from database.repositories import settings as settings_repo
from database.repositories import logs as logs_repo
from utils.navigation import go_to

router = Router(name="bank_cards")
router.message.filter(IsFullAdmin())
router.callback_query.filter(IsFullAdmin())


def _menu_content():
    cards = bank_cards_repo.list_cards()
    auto_rotate = settings_repo.get("auto_rotate_cards", "0") == "1"
    text = fa.BANK_CARDS_MENU_TITLE if cards else fa.NO_BANK_CARDS
    return text, bank_cards_menu_keyboard(cards, auto_rotate)


async def _render_menu_new_message(message: Message) -> None:
    """Used at the end of a text-input flow (adding a card) — there's no
    single message to edit back into at that point, so a fresh one is
    the correct behavior here, not stacking."""
    text, kb = _menu_content()
    await message.answer(text, reply_markup=kb)


async def _render_menu_in_place(callback: CallbackQuery) -> None:
    text, kb = _menu_content()
    await go_to(callback, text, reply_markup=kb)


@router.callback_query(F.data == "admin:bank_cards")
async def bank_cards_menu(callback: CallbackQuery) -> None:
    await _render_menu_in_place(callback)
    await callback.answer()


@router.callback_query(F.data == "card_add")
async def add_card_start(callback: CallbackQuery, state: FSMContext) -> None:
    if bank_cards_repo.count_cards() >= bank_cards_repo.MAX_CARDS:
        await callback.answer(fa.CARD_LIMIT_REACHED, show_alert=True)
        return
    await state.set_state(BankCardStates.awaiting_number)
    await go_to(callback, fa.ASK_NEW_CARD_NUMBER)
    await callback.answer()


@router.message(BankCardStates.awaiting_number)
async def add_card_number(message: Message, state: FSMContext) -> None:
    await state.update_data(new_card_number=message.text.strip())
    await state.set_state(BankCardStates.awaiting_holder)
    await message.answer(fa.ASK_NEW_CARD_HOLDER)


@router.message(BankCardStates.awaiting_holder)
async def add_card_holder(message: Message, state: FSMContext) -> None:
    await state.update_data(new_card_holder=message.text.strip())
    await state.set_state(BankCardStates.awaiting_bank)
    await message.answer(fa.ASK_NEW_CARD_BANK)


@router.message(BankCardStates.awaiting_bank)
async def add_card_bank(message: Message, state: FSMContext) -> None:
    bank = "" if message.text.strip() == "-" else message.text.strip()
    data = await state.get_data()
    bank_cards_repo.add_card(data["new_card_number"], data["new_card_holder"], bank)
    logs_repo.record("bank_card_added", message.from_user.id, data["new_card_number"])
    await state.clear()
    await message.answer(fa.CARD_ADDED)
    await _render_menu_new_message(message)


@router.callback_query(F.data.startswith("card_activate:"))
async def activate_card(callback: CallbackQuery) -> None:
    card_id = int(callback.data.split(":")[1])
    bank_cards_repo.set_active(card_id)
    logs_repo.record("bank_card_activated", callback.from_user.id, str(card_id))
    await callback.answer(fa.CARD_ACTIVATED)
    await _render_menu_in_place(callback)


@router.callback_query(F.data.startswith("card_delete_confirm:"))
async def delete_card_confirm(callback: CallbackQuery) -> None:
    card_id = int(callback.data.split(":")[1])
    await go_to(
        callback,
        "آیا مطمئنید می‌خواهید این کارت را حذف کنید؟",
        reply_markup=confirm_keyboard(f"card_delete_do:{card_id}", "admin:bank_cards"),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("card_delete_do:"))
async def delete_card_do(callback: CallbackQuery) -> None:
    card_id = int(callback.data.split(":")[1])
    bank_cards_repo.delete_card(card_id)
    logs_repo.record("bank_card_deleted", callback.from_user.id, str(card_id))
    await callback.answer(fa.CARD_DELETED)
    await _render_menu_in_place(callback)


@router.callback_query(F.data == "card_toggle_rotation")
async def toggle_rotation(callback: CallbackQuery) -> None:
    current = settings_repo.get("auto_rotate_cards", "0") == "1"
    settings_repo.set("auto_rotate_cards", "0" if current else "1")
    logs_repo.record("card_rotation_toggled", callback.from_user.id, str(not current))
    await callback.answer("✅ انجام شد.")
    await _render_menu_in_place(callback)
