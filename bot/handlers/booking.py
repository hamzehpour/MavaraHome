from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from texts import fa
from states.booking_states import BookingStates
from keyboards.main_menu import main_menu_keyboard, phone_request_keyboard
from keyboards.booking import (
    events_keyboard, dates_keyboard, sessions_keyboard, people_stepper_keyboard, people_direct_keyboard,
    name_step_keyboard, reuse_contact_keyboard, review_keyboard,
)
from services import event_service, settings_service, reservation_service
from validators.validators import is_valid_full_name, normalize_phone, is_valid_iranian_mobile
from database.repositories import users as users_repo
from utils.safe_send import safe_answer, safe_send_message

router = Router(name="booking")


@router.message(F.text == fa.MAIN_MENU_BOOKING)
async def start_booking(message: Message, state: FSMContext) -> None:
    await state.clear()
    events = event_service.get_active_events()
    if not events:
        await message.answer(fa.NO_ACTIVE_EVENTS)
        return

    # Always show which event(s) exist — even with just one — so the person
    # always knows exactly what they're booking (explicit requirement).
    await state.set_state(BookingStates.choosing_event)
    await message.answer(fa.CHOOSE_EVENT, reply_markup=events_keyboard(events))


@router.callback_query(BookingStates.choosing_event, F.data.startswith("book_event:"))
async def choose_event(callback: CallbackQuery, state: FSMContext) -> None:
    event_id = int(callback.data.split(":", 1)[1])
    from database.repositories import events as events_repo
    event = events_repo.get_event(event_id)
    await state.update_data(event_id=event_id, event_title=event["title"])
    await _show_dates(callback.message, state, event_id, event["title"], edit=True)
    await callback.answer()


async def _show_dates(message: Message, state: FSMContext, event_id: int, event_title: str, edit: bool = False) -> None:
    sessions = event_service.get_bookable_dates(event_id)
    if not sessions:
        await message.answer(fa.NO_ACTIVE_EVENT)
        return

    from database.repositories import events as events_repo
    event = events_repo.get_event(event_id)
    calendar_type = event.get("calendar_type", "jalali") if event else "jalali"
    await state.update_data(calendar_type=calendar_type)

    await state.set_state(BookingStates.choosing_date)
    text = f"🎭 {event_title}\n\n{fa.CHOOSE_DATE}"
    send = message.edit_text if edit else message.answer
    await send(text, reply_markup=dates_keyboard(sessions, calendar_type=calendar_type))


@router.callback_query(BookingStates.choosing_date, F.data.startswith("date:"))
async def choose_date(callback: CallbackQuery, state: FSMContext) -> None:
    date_str = callback.data.split(":", 1)[1]
    data = await state.get_data()
    sessions = event_service.get_sessions_on_date(data["event_id"], date_str)
    if not sessions:
        await callback.answer(fa.NO_SESSIONS_FOR_DATE, show_alert=True)
        return

    from utils.jalali import display_date_for_event
    await state.update_data(session_date=date_str)
    await state.set_state(BookingStates.choosing_session)
    has_full = any(event_service.get_available_seats(s) <= 0 for s in sessions)
    header = fa.choosing_session_header(
        display_date_for_event(date_str, data.get("calendar_type", "jalali")), has_full_session=has_full
    )
    await callback.message.edit_text(header, reply_markup=sessions_keyboard(sessions))
    await callback.answer()


@router.callback_query(BookingStates.choosing_session, F.data.startswith("session:") | F.data.startswith("session_full:"))
async def choose_session(callback: CallbackQuery, state: FSMContext) -> None:
    session_id = int(callback.data.split(":", 1)[1])
    is_full_tap = callback.data.startswith("session_full:")
    from database.repositories import sessions as sessions_repo
    session = sessions_repo.get_session(session_id)
    if not session:
        await callback.answer(fa.UNKNOWN_ERROR, show_alert=True)
        return

    available = event_service.get_available_seats(session)
    max_per_person = settings_service.get_max_tickets_per_person()
    # If the session is already full, still let the person pick a count —
    # start_reservation() will route them into the waiting list automatically
    # once it re-checks capacity (see services/reservation_service.py), which
    # is also what triggers the overflow-request notification to staff.
    max_selectable = max_per_person if available == 0 else max(min(available, max_per_person), 1)

    await state.update_data(session_id=session_id, people=1, max_selectable=max_selectable)
    await state.set_state(BookingStates.choosing_people)
    prompt = fa.CHOOSE_PEOPLE_COUNT
    if is_full_tap:
        prompt = "این سانس تکمیل ظرفیت است. تعداد مورد نیاز خود را انتخاب کنید تا درخواست اضافه‌ظرفیت برای ادمین ارسال شود:"
    await callback.message.edit_text(prompt, reply_markup=people_direct_keyboard(max_selectable))
    await callback.answer()


def validate_people_pick(raw: str, max_selectable: int) -> int | None:
    """Pure validation for a direct-selector tap — separated out so it's
    testable without a live Telegram callback. Returns the validated
    quantity, or None if the value is not an in-range positive integer.
    This is the actual source of truth for what's accepted; the keyboard
    only ever offers 1..max_selectable, but a tampered/hand-crafted
    callback (e.g. people_pick:999, people_pick:-1, people_pick:abc) must
    still be rejected here regardless of what the UI showed."""
    try:
        picked = int(raw)
    except (TypeError, ValueError):
        return None
    if picked < 1 or picked > max_selectable:
        return None
    return picked


@router.callback_query(BookingStates.choosing_people, F.data.startswith("people_pick:"))
async def people_pick(callback: CallbackQuery, state: FSMContext) -> None:
    """Direct-selector tap: picking a number only updates the FSM state
    (quantity), nothing else. No reservation, no capacity change, no
    payment/notification happens here — those only ever happen at the final
    confirmation step later in the flow. The callback value is untrusted
    client input, so it is re-validated against the server-computed
    max_selectable before being accepted."""
    data = await state.get_data()
    max_selectable = data.get("max_selectable", 1)

    picked = validate_people_pick(callback.data.split(":", 1)[1], max_selectable)
    if picked is None:
        # Tampered/out-of-range/non-numeric callback — reject outright.
        await callback.answer(fa.UNKNOWN_ERROR, show_alert=True)
        return

    await state.update_data(people=picked)
    await _proceed_after_people(callback, state, picked)


@router.callback_query(BookingStates.choosing_people, F.data.startswith("people_step:"))
async def people_step(callback: CallbackQuery, state: FSMContext) -> None:
    """Legacy +/- handler, kept only for any FSM state still mid-flow from
    before this update (e.g. a bot restart during deploy). New sessions
    never see this keyboard."""
    action = callback.data.split(":", 1)[1]
    data = await state.get_data()
    current = data.get("people", 1)
    max_selectable = data.get("max_selectable", 1)

    if action == "inc":
        current = min(current + 1, max_selectable)
        await state.update_data(people=current)
        await callback.message.edit_reply_markup(reply_markup=people_direct_keyboard(max_selectable))
        await callback.answer()
        return

    if action == "dec":
        current = max(current - 1, 1)
        await state.update_data(people=current)
        await callback.message.edit_reply_markup(reply_markup=people_direct_keyboard(max_selectable))
        await callback.answer()
        return

    # confirm
    await _proceed_after_people(callback, state, current)


async def _get_session_price(session_id: int) -> tuple[int, str]:
    from database.repositories import sessions as sessions_repo
    from database.repositories import events as events_repo
    from services import event_service
    session = sessions_repo.get_session(session_id)
    event = events_repo.get_event(session["event_id"]) if session else None
    if event:
        return event_service.get_effective_price(event)
    return settings_service.get_ticket_price(), "تومان"


async def _proceed_after_people(callback: CallbackQuery, state: FSMContext, people: int) -> None:
    from keyboards.booking import for_whom_keyboard
    await state.set_state(BookingStates.choosing_for_whom)
    await callback.message.edit_text(fa.ASK_FOR_WHOM, reply_markup=for_whom_keyboard())
    await callback.answer()


@router.callback_query(BookingStates.choosing_for_whom, F.data == "for_whom:self")
async def for_whom_self(callback: CallbackQuery, state: FSMContext) -> None:
    await _go_to_buyer_contact_step(callback, state)


@router.callback_query(BookingStates.choosing_for_whom, F.data == "for_whom:other")
async def for_whom_other(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(BookingStates.entering_attendee_name)
    await callback.message.edit_text(fa.ASK_ATTENDEE_NAME)
    await callback.answer()


@router.message(BookingStates.entering_attendee_name)
async def enter_attendee_name(message: Message, state: FSMContext) -> None:
    name = (message.text or "").strip()
    if not is_valid_full_name(name):
        await message.answer(fa.NAME_INVALID)
        return
    await state.update_data(attendee_name=name)
    await state.set_state(BookingStates.entering_attendee_phone)
    await message.answer(fa.ASK_ATTENDEE_PHONE, reply_markup=phone_request_keyboard())


@router.message(BookingStates.entering_attendee_phone, F.contact)
async def enter_attendee_phone_contact(message: Message, state: FSMContext) -> None:
    await _handle_attendee_phone(message, state, message.contact.phone_number)


@router.message(BookingStates.entering_attendee_phone, F.text)
async def enter_attendee_phone_text(message: Message, state: FSMContext) -> None:
    await _handle_attendee_phone(message, state, message.text)


async def _handle_attendee_phone(message: Message, state: FSMContext, raw_phone: str) -> None:
    phone = normalize_phone(raw_phone or "")
    if not phone.isdigit() or not is_valid_iranian_mobile(phone):
        await message.answer(fa.PHONE_FORMAT_INVALID)
        return
    await state.update_data(attendee_phone=phone)
    await _go_to_buyer_contact_step(message, state)


async def _go_to_buyer_contact_step(target, state: FSMContext) -> None:
    """Shared by both the self and for-someone-else paths: this always
    establishes the BUYER's own account name/phone (never overwritten by
    attendee info), reusing a known profile when we already have one."""
    telegram_id_obj = getattr(target, "from_user", None)
    telegram_id = telegram_id_obj.id if telegram_id_obj else None
    known = users_repo.get_or_create_user(telegram_id) if telegram_id else {}
    send = target.message.edit_text if isinstance(target, CallbackQuery) else target.answer

    if known.get("full_name") and known.get("phone"):
        await state.update_data(full_name=known["full_name"], phone=known["phone"], prefilled=True)
        await state.set_state(BookingStates.entering_name)  # reused as a checkpoint state
        await send(
            fa.reuse_contact_prompt(known["full_name"], known["phone"]),
            reply_markup=reuse_contact_keyboard(),
        )
    else:
        data = await state.get_data()
        await state.set_state(BookingStates.entering_name)
        await send(fa.people_confirmed(data.get("people", 1)), reply_markup=name_step_keyboard())

    if isinstance(target, CallbackQuery):
        await target.answer()


@router.callback_query(BookingStates.entering_name, F.data.startswith("reuse_contact:"))
async def reuse_contact(callback: CallbackQuery, state: FSMContext) -> None:
    choice = callback.data.split(":", 1)[1]
    if choice == "yes":
        data = await state.get_data()
        await state.set_state(BookingStates.reviewing)
        unit_price, currency = await _get_session_price(data["session_id"])
        total = unit_price * data["people"]
        await callback.message.edit_text(
            fa.review_summary(data["full_name"], data["phone"], data["people"], unit_price, total, currency,
                               data.get("attendee_name"), data.get("attendee_phone")),
            reply_markup=review_keyboard(),
        )
        await callback.answer()
        return

    await callback.message.edit_text(fa.people_confirmed((await state.get_data())["people"]),
                                      reply_markup=name_step_keyboard())
    await callback.answer()


@router.message(BookingStates.entering_name)
async def enter_name(message: Message, state: FSMContext) -> None:
    name = (message.text or "").strip()
    if not is_valid_full_name(name):
        await message.answer(fa.NAME_INVALID)
        return

    await state.update_data(full_name=name)
    await state.set_state(BookingStates.entering_phone)
    await message.answer(fa.ASK_PHONE, reply_markup=phone_request_keyboard())


@router.message(BookingStates.entering_phone, F.contact)
async def enter_phone_contact(message: Message, state: FSMContext) -> None:
    await _handle_phone(message, state, message.contact.phone_number)


@router.message(BookingStates.entering_phone, F.text)
async def enter_phone_text(message: Message, state: FSMContext) -> None:
    await _handle_phone(message, state, message.text)


async def _handle_phone(message: Message, state: FSMContext, raw_phone: str) -> None:
    if not raw_phone:
        await message.answer(fa.PHONE_REQUIRED)
        return

    phone = normalize_phone(raw_phone)
    if not phone.isdigit():
        await message.answer(fa.PHONE_DIGITS_ONLY)
        return
    if not is_valid_iranian_mobile(phone):
        await message.answer(fa.PHONE_FORMAT_INVALID)
        return

    data = await state.update_data(phone=phone)
    await state.set_state(BookingStates.reviewing)

    unit_price, currency = await _get_session_price(data["session_id"])
    total = unit_price * data["people"]
    await message.answer(
        fa.review_summary(data["full_name"], phone, data["people"], unit_price, total, currency,
                           data.get("attendee_name"), data.get("attendee_phone")),
        reply_markup=review_keyboard(),
    )


@router.callback_query(BookingStates.reviewing, F.data == "review:edit_name")
async def edit_name(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(BookingStates.entering_name)
    await callback.message.answer(fa.people_confirmed((await state.get_data())["people"]),
                                   reply_markup=name_step_keyboard())
    await callback.answer()


@router.callback_query(BookingStates.reviewing, F.data == "review:edit_phone")
async def edit_phone(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(BookingStates.entering_phone)
    await callback.message.answer(fa.ASK_PHONE, reply_markup=phone_request_keyboard())
    await callback.answer()


@router.callback_query(BookingStates.reviewing, F.data == "review:cancel")
async def cancel_review(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.answer("رزرو لغو شد.", reply_markup=main_menu_keyboard())
    await callback.answer()


@router.callback_query(BookingStates.reviewing, F.data == "review:confirm")
async def confirm_review(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    users_repo.update_contact_info(callback.from_user.id, data["full_name"], data["phone"])

    result = reservation_service.start_reservation(
        telegram_id=callback.from_user.id,
        session_id=data["session_id"],
        people=data["people"],
        attendee_name=data.get("attendee_name"),
        attendee_phone=data.get("attendee_phone"),
    )

    # Remove the review step's buttons (edit name / edit phone / cancel) now
    # that a decision has been made — leaving them clickable afterwards is
    # exactly the kind of stray leftover button that confuses buyers.
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    if result.get("waiting"):
        await state.clear()
        await callback.message.answer(fa.WAITLISTED, reply_markup=main_menu_keyboard())
        await _notify_admins_of_overflow(callback.bot, result.get("waitlist_id"))
        await callback.answer()
        return

    if not result.get("success"):
        await callback.answer(fa.UNKNOWN_ERROR, show_alert=True)
        return

    await state.update_data(reservation_id=result["reservation_id"])
    await state.set_state(BookingStates.awaiting_receipt)

    from services import channel_service
    await channel_service.on_reservation_changed(callback.bot, data["session_id"])

    # Root-cause fix for the reported bug: this message is built from an
    # admin-editable template + dynamic data (card holder name, etc.) and
    # rendered as Markdown — a single unbalanced "_"/"*"/"`" anywhere in
    # either would previously make Telegram reject the WHOLE message,
    # silently stranding the buyer in awaiting_receipt with no prompt at
    # all. safe_answer falls back to plain text instead of losing the
    # message (and the flow) when that happens.
    await safe_answer(
        callback.message,
        settings_service.render_payment_instructions(
            people=data["people"],
            unit_price=result["unit_price"],
            total_price=result["total_price"],
        ),
        parse_mode="Markdown",
    )
    await callback.message.answer(fa.ASK_RECEIPT_PHOTO)
    await callback.answer()
async def _notify_admins_of_overflow(bot, waitlist_id: int | None) -> None:
    if not waitlist_id:
        return
    from database.repositories import waitlist as waitlist_repo
    from keyboards.admin import overflow_request_keyboard
    from utils.jalali import gregorian_iso_to_jalali_display
    from services import permissions

    entry = waitlist_repo.get_entry_with_context(waitlist_id)
    if not entry:
        return
    text = fa.overflow_request_admin(
        entry["full_name"], entry["phone"], entry["people"], entry["capacity"],
        gregorian_iso_to_jalali_display(entry["session_date"]), entry["session_time"],
    )
    for telegram_id in permissions.list_staff_with_permission(permissions.REQUEST_OVERFLOW_DECISION):
        try:
            await bot.send_message(telegram_id, text, reply_markup=overflow_request_keyboard(waitlist_id))
        except Exception:
            continue


# ---------------- back navigation ----------------

@router.callback_query(F.data.startswith("book_nav:"))
async def back_nav(callback: CallbackQuery, state: FSMContext) -> None:
    target = callback.data.split(":", 1)[1]
    data = await state.get_data()

    if target == "back_to_main":
        await state.clear()
        await callback.message.answer("منوی اصلی:", reply_markup=main_menu_keyboard())
        await callback.answer()
        return

    if target == "back_to_event":
        await start_booking(callback.message, state)
        await callback.answer()
        return

    if target == "back_to_date":
        await _show_dates(callback.message, state, data["event_id"], data.get("event_title", ""), edit=True)
        await callback.answer()
        return

    if target == "back_to_session":
        sessions = event_service.get_sessions_on_date(data["event_id"], data["session_date"])
        from utils.jalali import display_date_for_event
        has_full = any(event_service.get_available_seats(s) <= 0 for s in sessions)
        header = fa.choosing_session_header(
            display_date_for_event(data["session_date"], data.get("calendar_type", "jalali")), has_full_session=has_full
        )
        await state.set_state(BookingStates.choosing_session)
        await callback.message.edit_text(header, reply_markup=sessions_keyboard(sessions))
        await callback.answer()
        return

    if target == "back_to_people":
        max_selectable = data.get("max_selectable", 1)
        await state.set_state(BookingStates.choosing_people)
        await callback.message.edit_text(
            fa.CHOOSE_PEOPLE_COUNT, reply_markup=people_direct_keyboard(max_selectable)
        )
        await callback.answer()
        return

    if target == "back_to_phone":
        await state.set_state(BookingStates.entering_phone)
        await callback.message.answer(fa.ASK_PHONE, reply_markup=phone_request_keyboard())
        await callback.answer()
        return

    await callback.answer()
