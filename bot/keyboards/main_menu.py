from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from texts import fa


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    rows = [
        [KeyboardButton(text=fa.MAIN_MENU_BOOKING)],
        [KeyboardButton(text=fa.MAIN_MENU_MY_RESERVATIONS)],
    ]
    # Only show this row when it's actually useful — an empty "منتظر اجرای
    # بعدی" section would just be dead clutter for most events/times.
    from database.repositories import events as events_repo
    if any(not e["is_active"] for e in events_repo.list_all_events()):
        rows.append([KeyboardButton(text=fa.MAIN_MENU_REOPENING_INTEREST)])
    rows.append([KeyboardButton(text=fa.MAIN_MENU_RULES), KeyboardButton(text=fa.MAIN_MENU_SUPPORT)])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def admin_quick_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🛠 پنل مدیریت")],
            [KeyboardButton(text=fa.MAIN_MENU_BOOKING)],
        ],
        resize_keyboard=True,
    )


def staff_quick_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="☎️ پنل پشتیبانی")],
            [KeyboardButton(text=fa.MAIN_MENU_BOOKING)],
        ],
        resize_keyboard=True,
    )


def support_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=fa.SUPPORT_MENU_MESSAGE)],
            [KeyboardButton(text=fa.BACK_BUTTON)],
        ],
        resize_keyboard=True,
    )


def phone_request_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=fa.SEND_PHONE_BUTTON, request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )
