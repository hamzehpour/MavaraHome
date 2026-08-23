from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from texts import fa


def events_keyboard(events: list[dict], with_back: bool = False) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=f"{e.get('icon', '🎭')} {e['title']}", callback_data=f"book_event:{e['id']}")]
        for e in events
    ]
    if with_back:
        rows.append([InlineKeyboardButton(text=fa.BACK_BUTTON, callback_data="book_nav:back_to_main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def dates_keyboard(sessions: list[dict], show_back: bool = True, calendar_type: str = "jalali") -> InlineKeyboardMarkup:
    from utils.jalali import display_date_for_event
    seen_dates = []
    rows = []
    for s in sessions:
        if s["session_date"] not in seen_dates:
            seen_dates.append(s["session_date"])
            rows.append([InlineKeyboardButton(
                text=display_date_for_event(s["session_date"], calendar_type),
                callback_data=f"date:{s['session_date']}",
            )])
    if show_back:
        rows.append([InlineKeyboardButton(text=fa.BACK_BUTTON, callback_data="book_nav:back_to_event")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def sessions_keyboard(sessions_for_date: list[dict], show_back: bool = True) -> InlineKeyboardMarkup:
    from database.repositories import sessions as sessions_repo
    rows = []
    for s in sessions_for_date:
        remaining = s["capacity"] - sessions_repo.reserved_count(s["id"])
        if remaining > 0:
            label = f"{s['session_time']} (ظرفیت باقی‌مانده: {remaining} نفر)"
            rows.append([InlineKeyboardButton(text=label, callback_data=f"session:{s['id']}")])
        else:
            label = f"⛔️ {s['session_time']} — ظرفیت تکمیل شده است"
            rows.append([InlineKeyboardButton(text=label, callback_data=f"session_full:{s['id']}")])
    if show_back:
        rows.append([InlineKeyboardButton(text=fa.BACK_BUTTON, callback_data="book_nav:back_to_date")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def people_stepper_keyboard(current: int, max_people: int) -> InlineKeyboardMarkup:
    """Deprecated: kept only so any stale in-flight FSM state referencing the
    old plus/minus stepper still renders something sane. New flows use
    people_direct_keyboard() below — one tap picks the number directly
    instead of N taps of +/-."""
    rows = [[
        InlineKeyboardButton(text="➖", callback_data="people_step:dec"),
        InlineKeyboardButton(text=f"{current} نفر", callback_data="noop"),
        InlineKeyboardButton(text="➕", callback_data="people_step:inc"),
    ]]
    rows.append([InlineKeyboardButton(text="✅ ادامه", callback_data="people_step:confirm")])
    rows.append([InlineKeyboardButton(text=fa.BACK_BUTTON, callback_data="book_nav:back_to_session")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def people_direct_keyboard(max_people: int) -> InlineKeyboardMarkup:
    """Direct number-grid selector: one tap picks the quantity instead of
    tapping +/- repeatedly. Only ever shows 1..max_people — never more than
    what's actually allowed, so there is nothing invalid to tap in the UI.
    Backend still re-validates the picked number independently (see
    handlers/booking.py::people_pick) — this keyboard is UX only, not the
    source of truth."""
    max_people = max(1, int(max_people))
    numbers = list(range(1, max_people + 1))
    rows: list[list[InlineKeyboardButton]] = []
    per_row = 4
    for i in range(0, len(numbers), per_row):
        chunk = numbers[i:i + per_row]
        rows.append([
            InlineKeyboardButton(text=str(n), callback_data=f"people_pick:{n}")
            for n in chunk
        ])
    rows.append([InlineKeyboardButton(text=fa.BACK_BUTTON, callback_data="book_nav:back_to_session")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def for_whom_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🙋 برای خودم", callback_data="for_whom:self")],
        [InlineKeyboardButton(text="👥 برای شخص دیگری", callback_data="for_whom:other")],
        [InlineKeyboardButton(text=fa.BACK_BUTTON, callback_data="book_nav:back_to_people")],
    ])


def name_step_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=fa.BACK_BUTTON, callback_data="book_nav:back_to_people")],
    ])


def reuse_contact_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ همین اطلاعات درست است", callback_data="reuse_contact:yes")],
        [InlineKeyboardButton(text="✏️ ویرایش می‌کنم", callback_data="reuse_contact:no")],
    ])


def review_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ ادامه پرداخت", callback_data="review:confirm")],
        [InlineKeyboardButton(text="✏️ ویرایش نام", callback_data="review:edit_name")],
        [InlineKeyboardButton(text="✏️ ویرایش شماره", callback_data="review:edit_phone")],
        [InlineKeyboardButton(text=fa.BACK_BUTTON, callback_data="book_nav:back_to_phone")],
        [InlineKeyboardButton(text=fa.CANCEL_BUTTON, callback_data="review:cancel")],
    ])
