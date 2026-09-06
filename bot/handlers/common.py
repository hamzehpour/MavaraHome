from aiogram import Router, F, Bot
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from texts import fa
from keyboards.main_menu import main_menu_keyboard, admin_quick_menu, staff_quick_menu
from keyboards.admin import admin_main_menu, staff_main_menu
from states.resend_receipt_states import ResendReceiptStates
from database.repositories import users as users_repo
from database.repositories import admins as admins_repo
from database.repositories import reservations as reservations_repo
from database.repositories import logs as logs_repo
from services import settings_service, reservation_service

router = Router(name="common")


@router.callback_query(F.data == "noop")
async def noop(callback: CallbackQuery) -> None:
    await callback.answer()


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    users_repo.get_or_create_user(message.from_user.id, message.from_user.full_name)

    text = fa.welcome(settings_service.get_brand_name(), settings_service.get_welcome_message())

    role = admins_repo.get_role(message.from_user.id)
    if role in ("owner", "admin"):
        await message.answer(text, reply_markup=admin_quick_menu())
    elif role == "operator":
        await message.answer(text, reply_markup=staff_quick_menu())
    else:
        await message.answer(text, reply_markup=main_menu_keyboard())


@router.message(F.text == "🛠 پنل مدیریت")
async def open_admin_panel(message: Message) -> None:
    if not admins_repo.is_full_admin(message.from_user.id):
        return
    await message.answer(fa.ADMIN_MENU_TITLE, reply_markup=admin_main_menu())


@router.message(F.text == "☎️ پنل پشتیبانی")
async def open_staff_panel(message: Message) -> None:
    if not admins_repo.is_admin(message.from_user.id):
        return
    await message.answer(fa.STAFF_MENU_TITLE, reply_markup=staff_main_menu())


@router.message(F.text == fa.BACK_BUTTON)
async def back_to_main_menu(message: Message) -> None:
    role = admins_repo.get_role(message.from_user.id)
    if role in ("owner", "admin"):
        from keyboards.main_menu import admin_quick_menu
        await message.answer("منوی اصلی:", reply_markup=admin_quick_menu())
    elif role == "operator":
        from keyboards.main_menu import staff_quick_menu
        await message.answer("منوی اصلی:", reply_markup=staff_quick_menu())
    else:
        await message.answer("منوی اصلی:", reply_markup=main_menu_keyboard())


@router.message(F.text == fa.MAIN_MENU_RULES)
async def show_rules(message: Message) -> None:
    await message.answer(settings_service.get_rules_text())


@router.message(F.text == fa.MAIN_MENU_SUPPORT)
async def show_support(message: Message) -> None:
    from keyboards.main_menu import support_menu_keyboard
    contact = settings_service.get_support_contact()
    text = fa.support_contact_text(contact) if contact else fa.SUPPORT_NOT_CONFIGURED
    await message.answer(text, reply_markup=support_menu_keyboard())


@router.message(F.text == fa.MAIN_MENU_MY_RESERVATIONS)
async def my_reservations(message: Message) -> None:
    from datetime import date
    from utils.jalali import gregorian_iso_to_jalali_display

    rows = reservation_service.get_user_reservations(message.from_user.id)
    if not rows:
        await message.answer(fa.MY_RESERVATIONS_EMPTY)
        return

    today = date.today().isoformat()
    waiting, upcoming, past, other = [], [], [], []
    for r in rows:
        line = fa.my_reservation_line(
            r["event_title"],
            gregorian_iso_to_jalali_display(r["session_date"]),
            r["session_time"],
            r["people"],
            r.get("reservation_code"),
        )
        if r["status"] in ("pending_payment", "pending_review", "needs_correction", "waiting"):
            waiting.append(line)
        elif r["status"] == "approved" and r["session_date"] >= today:
            upcoming.append(line)
        elif r["status"] == "approved":
            past.append(line)
        else:
            other.append(line)

    blocks = []
    if waiting:
        blocks.append(fa.MY_RES_SECTION_WAITING + "\n" + "\n".join(waiting))
    if upcoming:
        blocks.append(fa.MY_RES_SECTION_UPCOMING + "\n" + "\n".join(upcoming))
    if past:
        blocks.append(fa.MY_RES_SECTION_PAST + "\n" + "\n".join(past))
    if other:
        blocks.append(fa.MY_RES_SECTION_OTHER + "\n" + "\n".join(other))

    await message.answer("\n\n".join(blocks))

    # A needs_correction reservation gets its own follow-up message with an
    # actual action button — the block above is plain summary text, no
    # buttons, and this is the one status here that needs the buyer to DO
    # something (resubmit a fixed receipt) rather than just wait.
    from keyboards.booking import resubmit_correction_keyboard
    for r in rows:
        if r["status"] != "needs_correction":
            continue
        await message.answer(
            fa.needs_correction_note(r.get("admin_note") or ""),
            reply_markup=resubmit_correction_keyboard(r["id"]),
        )


@router.callback_query(F.data.startswith("resubmit_correction:"))
async def start_resubmit_correction(callback: CallbackQuery, state: FSMContext) -> None:
    reservation_id = int(callback.data.split(":")[1])
    reservation = reservations_repo.get_reservation(reservation_id)
    if not reservation or reservation["status"] != "needs_correction":
        await callback.answer(fa.RESUBMIT_RECEIPT_NOT_FOUND, show_alert=True)
        return

    await state.update_data(correction_resubmit_reservation_id=reservation_id)
    await state.set_state(ResendReceiptStates.awaiting_correction_receipt)
    await callback.message.answer(fa.ASK_RESUBMIT_RECEIPT)
    await callback.answer()


@router.message(ResendReceiptStates.awaiting_correction_receipt, F.photo)
async def receive_resubmitted_correction(message: Message, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    reservation_id = data["correction_resubmit_reservation_id"]
    await state.clear()

    file_id = message.photo[-1].file_id
    ok = reservation_service.submit_receipt(reservation_id, file_id)
    if not ok:
        await message.answer(fa.RESUBMIT_RECEIPT_NOT_FOUND)
        return

    logs_repo.record("receipt_resubmitted_after_correction", message.from_user.id,
                      f"reservation_id={reservation_id}",
                      target_type="reservation", target_id=reservation_id)
    await message.answer(fa.RESUBMIT_RECEIPT_RECEIVED)


@router.message(ResendReceiptStates.awaiting_correction_receipt)
async def resubmit_correction_wrong_type(message: Message) -> None:
    await message.answer(fa.RECEIPT_MUST_BE_PHOTO)
