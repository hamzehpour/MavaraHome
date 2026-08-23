from aiogram import Router, F, Bot
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from texts import fa
from states.booking_states import BookingStates
from keyboards.main_menu import main_menu_keyboard
from keyboards.admin import reservation_review_keyboard
from services import reservation_service, settings_service
from database.repositories import reservations as reservations_repo
from database.repositories import logs as logs_repo

router = Router(name="payment")


@router.message(BookingStates.awaiting_receipt, F.photo)
async def receive_receipt(message: Message, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    reservation_id = data.get("reservation_id")
    if not reservation_id:
        await state.clear()
        await message.answer(fa.NO_ACTIVE_BOOKING_SESSION, reply_markup=main_menu_keyboard())
        return

    file_id = message.photo[-1].file_id
    reservation_service.submit_receipt(reservation_id, file_id)
    logs_repo.record("receipt_submitted", message.from_user.id, f"reservation_id={reservation_id}")

    await state.clear()
    await message.answer(settings_service.render_receipt_received(), reply_markup=main_menu_keyboard())

    # Notify only staff who can actually approve payments — not the whole
    # admin list (e.g. a 'content' or 'finance'-only staff member shouldn't
    # get pinged for something they can't act on).
    reservation = reservations_repo.get_reservation(reservation_id)
    reservation["user_full_name"] = data.get("full_name")
    reservation["user_phone"] = data.get("phone")

    from services import permissions
    for telegram_id in permissions.list_staff_with_permission(permissions.APPROVE_PAYMENTS):
        try:
            await bot.send_photo(
                telegram_id,
                photo=file_id,
                caption=fa.admin_reservation_card(reservation),
                reply_markup=reservation_review_keyboard(reservation_id),
            )
        except Exception:
            continue


@router.message(BookingStates.awaiting_receipt)
async def receive_receipt_wrong_type(message: Message) -> None:
    await message.answer(fa.RECEIPT_MUST_BE_PHOTO)
