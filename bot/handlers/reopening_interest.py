"""User-facing flow for "🔔 منتظر اجرای بعدی" (Event Reopening Interest).

Distinct from waiting_list — see schema.py / event_interest_service.py for
why. This is reachable only for events currently paused (is_active = 0);
active/bookable events never show up here.
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from texts import fa
from states.reopening_interest_states import ReopeningInterestStates
from keyboards.main_menu import main_menu_keyboard, phone_request_keyboard
from services import event_interest_service
from database.repositories import events as events_repo
from validators.validators import is_valid_full_name, normalize_phone, is_valid_iranian_mobile

router = Router(name="reopening_interest")


def _paused_events_keyboard() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=f"{e.get('icon', '🎭')} {e['title']}", callback_data=f"reopen_event:{e['id']}")]
        for e in events_repo.list_all_events()
        if not e["is_active"]
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.message(F.text == fa.MAIN_MENU_REOPENING_INTEREST)
async def show_paused_events(message: Message) -> None:
    paused = [e for e in events_repo.list_all_events() if not e["is_active"]]
    if not paused:
        await message.answer("در حال حاضر رویداد متوقفی برای اطلاع‌رسانی وجود ندارد.")
        return
    await message.answer(
        "رویدادهایی که فعلاً اجرای فعالی برای رزرو ندارند:", reply_markup=_paused_events_keyboard()
    )


@router.callback_query(F.data.startswith("reopen_event:"))
async def show_event_reopen_page(callback: CallbackQuery, state: FSMContext) -> None:
    event_id = int(callback.data.split(":", 1)[1])
    event = events_repo.get_event(event_id)
    if not event or event["is_active"]:
        await callback.answer("این رویداد دیگر در این لیست نیست.", show_alert=True)
        return

    existing = event_interest_service.get_my_interest(event_id, callback.from_user.id)
    if existing:
        text = (
            f"🎭 {event['title']}\n\n"
            f"✅ شما قبلاً درخواست اطلاع‌رسانی برای اجرای بعدی این رویداد را ثبت کرده‌اید.\n\n"
            f"📱 شماره ثبت‌شده: {existing['phone_number']}\n👤 نام: {existing['contact_name']}"
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✏️ ویرایش اطلاعات", callback_data=f"reopen_edit:{existing['id']}:{event_id}")],
            [InlineKeyboardButton(text="❌ لغو درخواست", callback_data=f"reopen_cancel:{existing['id']}")],
        ])
        await callback.message.edit_text(text, reply_markup=kb)
        await callback.answer()
        return

    text = (
        f"🎭 {event['title']}\n\n"
        "در حال حاضر اجرای فعالی برای این رویداد برای رزرو وجود ندارد.\n\n"
        "اگر مایل هستید، مشخصات خود را ثبت کنید تا به محض مشخص شدن اجرای بعدی، به شما اطلاع دهیم.\n\n"
        "در صورت برگزاری اجرای جدید، افرادی که از قبل ثبت‌نام کرده‌اند ابتدا مطلع می‌شوند."
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔔 اطلاع از اجرای بعدی", callback_data=f"reopen_start:{event_id}")],
    ])
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("reopen_start:"))
async def start_registration(callback: CallbackQuery, state: FSMContext) -> None:
    event_id = int(callback.data.split(":", 1)[1])
    await state.update_data(reopen_event_id=event_id)
    await state.set_state(ReopeningInterestStates.confirming_name)

    suggested = callback.from_user.full_name or ""
    await state.update_data(reopen_suggested_name=suggested)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ بله", callback_data="reopen_name_ok")],
        [InlineKeyboardButton(text="✏️ ویرایش نام", callback_data="reopen_name_edit")],
    ])
    await callback.message.answer(f"نام شما:\n\n{suggested}\n\nآیا همین نام برای تماس مناسب است؟", reply_markup=kb)
    await callback.answer()


@router.callback_query(ReopeningInterestStates.confirming_name, F.data == "reopen_name_ok")
async def name_confirmed(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    await state.update_data(reopen_name=data.get("reopen_suggested_name", ""))
    await state.set_state(ReopeningInterestStates.awaiting_phone)
    await callback.message.answer("برای ثبت شماره تماس، روی دکمه زیر بزنید:", reply_markup=phone_request_keyboard())
    await callback.answer()


@router.callback_query(ReopeningInterestStates.confirming_name, F.data == "reopen_name_edit")
async def name_edit_requested(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(ReopeningInterestStates.entering_name)
    await callback.message.answer("نام موردنظر برای تماس را وارد کنید:")
    await callback.answer()


@router.message(ReopeningInterestStates.entering_name, F.text)
async def name_entered(message: Message, state: FSMContext) -> None:
    name = (message.text or "").strip()
    if not is_valid_full_name(name):
        await message.answer("نام واردشده معتبر نیست. دوباره وارد کنید:")
        return
    await state.update_data(reopen_name=name)
    await state.set_state(ReopeningInterestStates.awaiting_phone)
    await message.answer("برای ثبت شماره تماس، روی دکمه زیر بزنید:", reply_markup=phone_request_keyboard())


async def _finish_registration(message: Message, state: FSMContext, phone_raw: str) -> None:
    phone = normalize_phone(phone_raw)
    if not is_valid_iranian_mobile(phone):
        await message.answer("شماره نامعتبر است. لطفاً دوباره از طریق دکمه ارسال کنید.")
        return

    data = await state.get_data()
    event_id = data["reopen_event_id"]
    name = data.get("reopen_name") or (message.from_user.full_name or "")
    editing_id = data.get("reopen_editing_interest_id")
    await state.clear()

    if editing_id:
        event_interest_service.edit_interest(editing_id, name, phone)
        await message.answer(
            f"✅ اطلاعات شما به‌روزرسانی شد.\n\n📱 شماره تماس: {phone}\n👤 نام: {name}",
            reply_markup=main_menu_keyboard(),
        )
        return

    username = message.from_user.username
    created, existing = event_interest_service.register_interest(
        event_id, telegram_id=message.from_user.id, contact_name=name,
        phone_number=phone, telegram_username=username,
    )

    if not created:
        await message.answer("✅ شما قبلاً برای این رویداد ثبت شده بودید.", reply_markup=main_menu_keyboard())
        return

    event = events_repo.get_event(event_id)
    text = (
        "✅ اطلاعات شما ثبت شد.\n\n"
        f"به محض اینکه اجرای جدید «{event['title']}» مشخص شود، به شما اطلاع خواهیم داد.\n\n"
        "افرادی که از قبل درخواست اطلاع‌رسانی ثبت کرده‌اند، در اولویت اطلاع‌رسانی قرار خواهند گرفت.\n\n"
        f"📱 شماره تماس: {phone}\n👤 نام: {name}"
    )
    await message.answer(text, reply_markup=main_menu_keyboard())


@router.message(ReopeningInterestStates.awaiting_phone, F.contact)
async def phone_via_contact(message: Message, state: FSMContext) -> None:
    await _finish_registration(message, state, message.contact.phone_number)


@router.callback_query(F.data.startswith("reopen_cancel:"))
async def cancel_interest(callback: CallbackQuery) -> None:
    interest_id = int(callback.data.split(":", 1)[1])
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ بله، لغو کن", callback_data=f"reopen_cancel_confirm:{interest_id}")],
        [InlineKeyboardButton(text="⬅️ انصراف", callback_data="reopen_cancel_abort")],
    ])
    await callback.message.edit_text(
        "آیا مطمئن هستید؟ در صورت لغو، برای اجرای بعدی به شما اطلاع داده نخواهد شد.", reply_markup=kb
    )
    await callback.answer()


@router.callback_query(F.data.startswith("reopen_cancel_confirm:"))
async def cancel_interest_confirmed(callback: CallbackQuery) -> None:
    interest_id = int(callback.data.split(":", 1)[1])
    event_interest_service.cancel_interest(interest_id)
    await callback.message.edit_text("درخواست اطلاع‌رسانی شما لغو شد.")
    await callback.answer()


@router.callback_query(F.data == "reopen_cancel_abort")
async def cancel_interest_aborted(callback: CallbackQuery) -> None:
    await callback.message.edit_text("لغو نشد. درخواست شما همچنان فعال است.")
    await callback.answer()


@router.callback_query(F.data.startswith("reopen_edit:"))
async def edit_interest_start(callback: CallbackQuery, state: FSMContext) -> None:
    _, interest_id, event_id = callback.data.split(":")
    await state.update_data(reopen_event_id=int(event_id), reopen_editing_interest_id=int(interest_id))
    await state.set_state(ReopeningInterestStates.entering_name)
    await callback.message.answer("نام جدید برای تماس را وارد کنید:")
    await callback.answer()
