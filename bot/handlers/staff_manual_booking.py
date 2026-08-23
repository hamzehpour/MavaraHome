"""
Handlers exclusive to the limited 'operator' (phone-support) role, plus
shared by full admins too: viewing live capacity and taking a booking
over the phone on a customer's behalf.
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from texts import fa
from filters.admin_filter import IsAdmin
from states.admin_states import StaffBookingStates
from states.ticket_verify_states import TicketVerifyStates
from keyboards.booking import events_keyboard, dates_keyboard, sessions_keyboard
from services import event_service, settings_service, reservation_service
from validators.validators import is_valid_full_name, normalize_phone, is_valid_iranian_mobile, is_positive_int
from utils.safe_send import safe_answer
from database.repositories import reservations as reservations_repo
from database.repositories import sessions as sessions_repo
from database.repositories import logs as logs_repo
from utils.jalali import gregorian_iso_to_jalali_display

router = Router(name="staff_manual_booking")
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


# ---------------- QR ticket verification ----------------

@router.callback_query(F.data == "staff:verify_ticket")
async def verify_ticket_start(callback: CallbackQuery, state: FSMContext) -> None:
    from states.ticket_verify_states import TicketVerifyStates
    await state.set_state(TicketVerifyStates.awaiting_qr_payload)
    await callback.message.answer(fa.ASK_QR_PAYLOAD)
    await callback.answer()


@router.message(TicketVerifyStates.awaiting_qr_payload)
async def verify_ticket_check(message: Message, state: FSMContext) -> None:
    from utils.qr_signing import verify_signed_code
    from keyboards.admin import qr_mark_used_keyboard

    await state.clear()
    code = verify_signed_code((message.text or "").strip())
    if not code:
        await message.answer(fa.QR_INVALID_SIGNATURE)
        return

    reservation = reservations_repo.get_by_code(code)
    if not reservation:
        await message.answer(fa.QR_CODE_NOT_FOUND)
        return

    from database.connection import get_connection
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT u.full_name AS user_full_name FROM users u WHERE u.id = ?
            """,
            (reservation["user_id"],),
        ).fetchone()
    session = sessions_repo.get_session(reservation["session_id"])
    from database.repositories import events as events_repo
    event = events_repo.get_event(session["event_id"]) if session else None

    reservation["user_full_name"] = row["user_full_name"] if row else "—"
    await message.answer(
        fa.qr_verify_result(
            reservation, event["title"] if event else "",
            gregorian_iso_to_jalali_display(session["session_date"]) if session else "-",
            session["session_time"] if session else "-",
        ),
        reply_markup=qr_mark_used_keyboard(reservation["id"]) if reservation["status"] != "used" else None,
    )


@router.callback_query(F.data.startswith("qr_mark_used:"))
async def mark_ticket_used(callback: CallbackQuery) -> None:
    reservation_id = int(callback.data.split(":")[1])
    reservations_repo.set_status(reservation_id, "used")
    logs_repo.record("ticket_marked_used", callback.from_user.id,
                      target_type="reservation", target_id=reservation_id)
    await callback.message.edit_text(callback.message.text + f"\n\n{fa.QR_MARKED_USED}")
    await callback.answer()


# ---------------- capacity overview ----------------

@router.callback_query(F.data == "staff:capacity")
async def capacity_pick_event(callback: CallbackQuery) -> None:
    events = event_service.get_active_events()
    if not events:
        await callback.message.answer(fa.NO_ACTIVE_EVENTS)
        await callback.answer()
        return
    await callback.message.answer(fa.CHOOSE_EVENT, reply_markup=events_keyboard_for_capacity(events))
    await callback.answer()


def events_keyboard_for_capacity(events):
    # Reuses the same visual style as booking, but with a distinct
    # callback prefix so it can't be confused with the customer flow.
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=e["title"], callback_data=f"cap_event:{e['id']}")]
        for e in events
    ])


@router.callback_query(F.data.startswith("cap_event:"))
async def show_capacity(callback: CallbackQuery) -> None:
    event_id = int(callback.data.split(":", 1)[1])
    from database.repositories import events as events_repo
    event = events_repo.get_event(event_id)
    overview = event_service.get_capacity_overview(event_id)
    await callback.message.answer(fa.capacity_report(event["title"], overview))
    await callback.answer()


# ---------------- manual / phone booking ----------------

@router.callback_query(F.data == "staff:manual_booking")
async def manual_booking_start(callback: CallbackQuery, state: FSMContext) -> None:
    events = event_service.get_active_events()
    if not events:
        await callback.message.answer(fa.NO_ACTIVE_EVENTS)
        await callback.answer()
        return

    await state.set_state(StaffBookingStates.choosing_event)
    await callback.message.answer(fa.MANUAL_BOOKING_INTRO, reply_markup=events_keyboard(events, with_back=False))
    await callback.answer()


@router.callback_query(StaffBookingStates.choosing_event, F.data.startswith("book_event:"))
async def manual_choose_event(callback: CallbackQuery, state: FSMContext) -> None:
    event_id = int(callback.data.split(":", 1)[1])
    sessions = event_service.get_bookable_dates(event_id)
    if not sessions:
        await callback.answer(fa.NO_ACTIVE_EVENT, show_alert=True)
        return

    await state.update_data(event_id=event_id)
    await state.set_state(StaffBookingStates.choosing_date)
    await callback.message.edit_text(fa.CHOOSE_DATE, reply_markup=dates_keyboard(sessions, show_back=False))
    await callback.answer()


@router.callback_query(StaffBookingStates.choosing_date, F.data.startswith("date:"))
async def manual_choose_date(callback: CallbackQuery, state: FSMContext) -> None:
    date_str = callback.data.split(":", 1)[1]
    data = await state.get_data()
    sessions = event_service.get_sessions_on_date(data["event_id"], date_str)
    if not sessions:
        await callback.answer(fa.NO_SESSIONS_FOR_DATE, show_alert=True)
        return

    await state.set_state(StaffBookingStates.choosing_session)
    await callback.message.edit_text(fa.CHOOSE_SESSION, reply_markup=sessions_keyboard(sessions, show_back=False))
    await callback.answer()


@router.callback_query(StaffBookingStates.choosing_session, F.data.startswith("session:"))
async def manual_choose_session(callback: CallbackQuery, state: FSMContext) -> None:
    session_id = int(callback.data.split(":", 1)[1])
    await state.update_data(session_id=session_id)
    await state.set_state(StaffBookingStates.entering_people)
    await callback.message.edit_text(fa.ASK_MANUAL_PEOPLE)
    await callback.answer()


@router.message(StaffBookingStates.entering_people)
async def manual_enter_people(message: Message, state: FSMContext) -> None:
    if not is_positive_int(message.text):
        await message.answer(fa.INVALID_NUMBER)
        return

    await state.update_data(people=int(message.text.strip()))
    await state.set_state(StaffBookingStates.entering_name)
    await message.answer(fa.ASK_MANUAL_NAME)


@router.message(StaffBookingStates.entering_name)
async def manual_enter_name(message: Message, state: FSMContext) -> None:
    name = (message.text or "").strip()
    if not is_valid_full_name(name):
        await message.answer(fa.NAME_INVALID)
        return

    await state.update_data(full_name=name)
    await state.set_state(StaffBookingStates.entering_phone)
    await message.answer(fa.ASK_MANUAL_PHONE)


@router.message(StaffBookingStates.entering_phone)
async def manual_enter_phone(message: Message, state: FSMContext) -> None:
    phone = normalize_phone(message.text or "")
    if not phone.isdigit() or not is_valid_iranian_mobile(phone):
        await message.answer(fa.PHONE_FORMAT_INVALID)
        return

    data = await state.update_data(phone=phone)
    unit_price = settings_service.get_ticket_price()
    total = unit_price * data["people"]
    await state.set_state(StaffBookingStates.reviewing)
    await message.answer(
        fa.manual_booking_review(data["full_name"], phone, data["people"], total)
        + "\n\nبرای تأیید «بله» و برای انصراف «لغو» را ارسال کنید.",
    )


@router.message(StaffBookingStates.reviewing, F.text == "بله")
async def manual_confirm(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    result = reservation_service.create_manual_reservation(
        operator_telegram_id=message.from_user.id,
        session_id=data["session_id"],
        people=data["people"],
        full_name=data["full_name"],
        phone=data["phone"],
    )
    await state.clear()

    if result.get("waiting"):
        await message.answer(fa.MANUAL_BOOKING_WAITLISTED)
        return

    if not result.get("success"):
        await message.answer(fa.UNKNOWN_ERROR)
        return

    await safe_answer(message, fa.manual_booking_confirmed(result["reservation_code"]), parse_mode="Markdown")
    from services import channel_service
    await channel_service.on_reservation_changed(message.bot, data["session_id"])


@router.message(StaffBookingStates.reviewing, F.text == "لغو")
async def manual_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("لغو شد.")
