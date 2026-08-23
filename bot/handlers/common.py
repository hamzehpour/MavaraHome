from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery

from texts import fa
from keyboards.main_menu import main_menu_keyboard, admin_quick_menu, staff_quick_menu
from keyboards.admin import admin_main_menu, staff_main_menu
from database.repositories import users as users_repo
from database.repositories import admins as admins_repo
from services import settings_service, reservation_service

router = Router(name="common")


@router.callback_query(F.data == "noop")
async def noop(callback: CallbackQuery) -> None:
    await callback.answer()


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    users_repo.get_or_create_user(message.from_user.id, message.from_user.full_name)

    # Phase 4: deep-link account linking. Telegram delivers a
    # t.me/<bot>?start=LINK-<token> open as the message text
    # "/start LINK-<token>" — this is the only way a website-only user
    # (phone, no telegram_id yet) can start receiving OTP codes, since
    # this project has no SMS provider (see
    # services/customer_auth_service.py for the full flow).
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) == 2 and parts[1].startswith("LINK-"):
        token = parts[1][len("LINK-"):]
        from services.customer_auth_service import link_telegram_from_token
        if link_telegram_from_token(token, message.from_user.id):
            await message.answer(
                "✅ حساب شما به تلگرام وصل شد. حالا به سایت خانه ماورا برگردید و "
                "دوباره دکمه‌ی «ارسال کد» را بزنید — کد ورود از همینجا برایتان ارسال می‌شود."
            )
        else:
            await message.answer(
                "⛔️ این لینک منقضی شده یا قبلاً استفاده شده. لطفاً از سایت دوباره تلاش کنید."
            )
        return

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
        if r["status"] in ("pending_payment", "pending_review", "waiting"):
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
