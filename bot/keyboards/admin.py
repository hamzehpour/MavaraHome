from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from texts import fa
from utils.jalali import (
    MONTH_NAMES_FA, WEEKDAY_NAMES_FA, to_persian_digits, jalali_to_gregorian,
)
from datetime import date as _date


def _jalali_month_length(jy: int, jm: int) -> int:
    if jm <= 6:
        return 31
    if jm <= 11:
        return 30
    # esfand: 29, or 30 in a leap year — derive by converting the 1st of
    # next month back and diffing, which is always correct regardless of
    # the leap-year rule used.
    gy1, gm1, gd1 = jalali_to_gregorian(jy, jm, 1)
    if jm == 12:
        gy2, gm2, gd2 = jalali_to_gregorian(jy + 1, 1, 1)
    else:
        gy2, gm2, gd2 = jalali_to_gregorian(jy, jm + 1, 1)
    return (_date(gy2, gm2, gd2) - _date(gy1, gm1, gd1)).days


_WEEK_COLUMN_ORDER_FA = ["شنبه", "یکشنبه", "دوشنبه", "سه‌شنبه", "چهارشنبه", "پنجشنبه", "جمعه"]


def _column_position(python_weekday: int) -> int:
    """Python's date.weekday() is Monday=0..Sunday=6. The Persian week
    display is Saturday-first, Friday-last (like Gregorian's Sunday-last) —
    this maps one to the other."""
    return (python_weekday + 2) % 7


def calendar_keyboard(jalali_year: int, jalali_month: int, callback_prefix: str) -> InlineKeyboardMarkup:
    """
    A month-view Jalali calendar. Tapping a day fires
    '<callback_prefix>:pick:<ISO date>'. Prev/next month navigate within
    the same message via '<callback_prefix>:nav:<year>:<month>'.
    """
    rows = [[InlineKeyboardButton(
        text=to_persian_digits(f"{MONTH_NAMES_FA[jalali_month - 1]} {jalali_year}"),
        callback_data="noop",
    )]]
    rows.append([
        InlineKeyboardButton(text=d[:1], callback_data="noop")
        for d in _WEEK_COLUMN_ORDER_FA
    ])

    gy1, gm1, gd1 = jalali_to_gregorian(jalali_year, jalali_month, 1)
    first_weekday = _column_position(_date(gy1, gm1, gd1).weekday())
    days_in_month = _jalali_month_length(jalali_year, jalali_month)

    week = [InlineKeyboardButton(text=" ", callback_data="noop")] * first_weekday
    today_iso = _date.today().isoformat()
    for day in range(1, days_in_month + 1):
        gy, gm, gd = jalali_to_gregorian(jalali_year, jalali_month, day)
        iso = f"{gy:04d}-{gm:02d}-{gd:02d}"
        is_past = iso < today_iso
        day_text = to_persian_digits(str(day))
        week.append(InlineKeyboardButton(
            text=("· " if is_past else "") + day_text,
            callback_data="noop" if is_past else f"{callback_prefix}:pick:{iso}",
        ))
        if len(week) == 7:
            rows.append(week)
            week = []
    if week:
        while len(week) < 7:
            week.append(InlineKeyboardButton(text=" ", callback_data="noop"))
        rows.append(week)

    prev_y, prev_m = (jalali_year - 1, 12) if jalali_month == 1 else (jalali_year, jalali_month - 1)
    next_y, next_m = (jalali_year + 1, 1) if jalali_month == 12 else (jalali_year, jalali_month + 1)
    rows.append([
        InlineKeyboardButton(text="◀️ ماه قبل", callback_data=f"{callback_prefix}:nav:{prev_y}:{prev_m}"),
        InlineKeyboardButton(text="ماه بعد ▶️", callback_data=f"{callback_prefix}:nav:{next_y}:{next_m}"),
    ])
    rows.append([InlineKeyboardButton(text=fa.BACK_BUTTON, callback_data=f"{callback_prefix}:back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_main_menu() -> InlineKeyboardMarkup:
    from config.settings import IS_PRODUCTION
    rows = [
        [InlineKeyboardButton(text="🕒 رزروهای در انتظار بررسی", callback_data="admin:pending")],
        [InlineKeyboardButton(text=fa.STAFF_MENU_VERIFY_TICKET, callback_data="staff:verify_ticket")],
        [InlineKeyboardButton(text="🎭 مدیریت رویدادها", callback_data="admin:events")],
        [InlineKeyboardButton(text="📊 آمار فروش", callback_data="admin:stats")],
        [InlineKeyboardButton(text="📣 پیام همگانی", callback_data="admin:broadcast")],
        [InlineKeyboardButton(text="✉️ پیام به یک نفر", callback_data="admin:direct_message")],
        [InlineKeyboardButton(text="⚙️ تنظیمات", callback_data="admin:settings")],
        [InlineKeyboardButton(text="💳 مدیریت کارت‌های بانکی", callback_data="admin:bank_cards")],
        [InlineKeyboardButton(text="📡 راه‌اندازی کانال مانیتورینگ", callback_data="admin:channel_setup")],
        [InlineKeyboardButton(text="🔔 راه‌اندازی کانال هشدار رزرو", callback_data="admin:alerts_channel_setup")],
        [InlineKeyboardButton(text="👥 مدیریت مسئولان", callback_data="admin:staff")],
        [InlineKeyboardButton(text="👑 مدیریت مالکیت", callback_data="admin:owner_management")],
        [InlineKeyboardButton(text="📥 خروجی اکسل رزروها", callback_data="admin:export")],
        [InlineKeyboardButton(text="📄 خروجی CSV / JSON", callback_data="admin:export_other")],
        [InlineKeyboardButton(text="📜 خروجی اکسل لاگ تغییرات", callback_data="admin:export_logs")],
    ]
    if not IS_PRODUCTION:
        rows.append([InlineKeyboardButton(text=fa.FACTORY_RESET_BUTTON, callback_data="admin:factory_reset")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def staff_main_menu() -> InlineKeyboardMarkup:
    """Limited menu for the 'operator' (phone-support) role — no settings,
    no event/session management, no broadcast, no staff management."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=fa.STAFF_MENU_PENDING, callback_data="admin:pending")],
        [InlineKeyboardButton(text=fa.STAFF_MENU_CAPACITY, callback_data="staff:capacity")],
        [InlineKeyboardButton(text=fa.STAFF_MENU_MANUAL_BOOKING, callback_data="staff:manual_booking")],
        [InlineKeyboardButton(text=fa.STAFF_MENU_VERIFY_TICKET, callback_data="staff:verify_ticket")],
    ])


def staff_list_actions_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ افزودن مسئول جدید", callback_data="staff:add")],
        [InlineKeyboardButton(text="🗑 حذف مسئول", callback_data="staff:remove")],
        [InlineKeyboardButton(text=fa.STAFF_MENU_MANAGE_GROUPS, callback_data="staff:manage_groups")],
    ])


def staff_role_picker_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="ادمین (دسترسی کامل)", callback_data="staff_role:admin"),
        InlineKeyboardButton(text="پشتیبانی (محدود)", callback_data="staff_role:operator"),
    ]])


def owner_management_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔐 تنظیم/تغییر رمز انتقال مالکیت", callback_data="owner:set_passcode")],
        [InlineKeyboardButton(text="➕ افزودن مالک جدید", callback_data="owner:add")],
    ])


def reservation_review_keyboard(reservation_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=fa.APPROVE_BUTTON, callback_data=f"review:approve:{reservation_id}"),
            InlineKeyboardButton(text=fa.REJECT_BUTTON, callback_data=f"review:reject:{reservation_id}"),
        ]
    ])


def events_menu_keyboard(events: list[dict]) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(
            text=f"{'🟢' if e['is_active'] else '⚪️'} {e.get('icon', '🎭')} {e['title']}",
            callback_data=f"admin_event:{e['id']}",
        )]
        for e in events
    ]
    rows.append([InlineKeyboardButton(text="➕ اجرای جدید", callback_data="admin_event:new")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def event_detail_keyboard(event_id: int, is_active: bool, sessions: list[dict]) -> InlineKeyboardMarkup:
    from utils.jalali import gregorian_iso_to_jalali_display
    toggle_text = "⚪️ غیرفعال کردن رویداد" if is_active else "🟢 فعال کردن رویداد"
    rows = []
    for s in sessions:
        status_icon = "🟢" if s["status"] == "active" else "🟠"
        label = f"{status_icon} {gregorian_iso_to_jalali_display(s['session_date'])} — {s['session_time']}"
        rows.append([
            InlineKeyboardButton(text=label, callback_data=f"admin_session_view:{s['id']}"),
        ])
    rows.append([InlineKeyboardButton(text="➕ افزودن سانس جدید", callback_data=f"admin_session_new:{event_id}")])
    rows.append([InlineKeyboardButton(text="📍 ویرایش آدرس رویداد", callback_data=f"admin_event_edit_address:{event_id}")])
    rows.append([InlineKeyboardButton(text="📅 نوع تقویم نمایشی", callback_data=f"admin_event_edit_calendar:{event_id}")])
    rows.append([InlineKeyboardButton(text=toggle_text, callback_data=f"admin_event_toggle:{event_id}")])
    rows.append([InlineKeyboardButton(text="🗑 حذف کامل رویداد", callback_data=f"admin_event_delete_confirm:{event_id}")])
    rows.append([InlineKeyboardButton(text=fa.BACK_BUTTON, callback_data="admin:events")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def session_detail_keyboard(session_id: int, event_id: int, is_active: bool) -> InlineKeyboardMarkup:
    toggle_text = "⚪️ غیرفعال کردن این سانس" if is_active else "🟢 فعال کردن این سانس"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ ویرایش ظرفیت", callback_data=f"admin_session_edit_capacity:{session_id}")],
        [InlineKeyboardButton(text="✏️ ویرایش تاریخ/ساعت", callback_data=f"admin_session_edit_datetime:{session_id}")],
        [InlineKeyboardButton(text="👥 مدیریت رزروهای ثبت‌شده", callback_data=f"admin_session_manage_res:{session_id}")],
        [InlineKeyboardButton(text=toggle_text, callback_data=f"admin_session_toggle:{session_id}")],
        [InlineKeyboardButton(text="🗑 حذف این سانس", callback_data=f"admin_session_delete_confirm:{session_id}")],
        [InlineKeyboardButton(text=fa.BACK_BUTTON, callback_data=f"admin_event:{event_id}")],
    ])


def holder_edit_keyboard(holders: list[dict], session_id: int) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(
            text=f"✏️ {h.get('attendee_name') or h['full_name']} ({h['people']} نفر)",
            callback_data=f"admin_res_edit:{h['id']}",
        )]
        for h in holders
    ]
    rows.append([InlineKeyboardButton(text=fa.BACK_BUTTON, callback_data=f"admin_session_view:{session_id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def reservation_edit_menu_keyboard(reservation_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔢 تغییر تعداد نفرات", callback_data=f"res_edit_people:{reservation_id}")],
        [InlineKeyboardButton(text="🔀 جابجایی به سانس دیگر", callback_data=f"res_edit_move:{reservation_id}")],
        [InlineKeyboardButton(text="🗑 لغو این رزرو", callback_data=f"res_edit_cancel_confirm:{reservation_id}")],
    ])


def confirm_keyboard(yes_callback: str, no_callback: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ بله، مطمئنم", callback_data=yes_callback),
        InlineKeyboardButton(text="❌ انصراف", callback_data=no_callback),
    ]])


def settings_menu_keyboard(editable_settings: dict) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=label, callback_data=f"admin_setting:{key}")]
        for key, label in editable_settings.items()
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def broadcast_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ ارسال", callback_data="broadcast:send")],
        [InlineKeyboardButton(text=fa.CANCEL_BUTTON, callback_data="broadcast:cancel")],
    ])


_BANK_ICONS = {
    "ملی": "🏛️", "ملت": "🟡", "صادرات": "🟢", "تجارت": "🔵", "سپه": "🟤",
    "پارسیان": "🟣", "پاسارگاد": "🔴", "سامان": "🟠", "کشاورزی": "🌾",
    "مسکن": "🏠", "رفاه": "💠", "اقتصاد نوین": "🆕", "شهر": "🏙️",
    "دی": "🌙", "آینده": "🔮", "گردشگری": "🧳", "انصار": "⭐",
}


def _bank_icon(bank_name: str) -> str:
    for key, icon in _BANK_ICONS.items():
        if key in (bank_name or ""):
            return icon
    return "💳"


def _mask_card(number: str) -> str:
    digits = "".join(ch for ch in number if ch.isdigit())
    if len(digits) < 8:
        return number
    return f"{digits[:4]} •••• •••• {digits[-4:]}"


def bank_cards_menu_keyboard(cards: list[dict], auto_rotate: bool) -> InlineKeyboardMarkup:
    rows = []
    for c in cards:
        status = "🟢 فعال" if c["is_active"] else "⚪️ غیرفعال"
        icon = _bank_icon(c["bank_name"])
        label = f"{icon} {_mask_card(c['card_number'])} — {c['bank_name'] or 'نامشخص'} ({status})"
        rows.append([InlineKeyboardButton(text=label, callback_data=f"card_activate:{c['id']}")])
        rows.append([InlineKeyboardButton(text=f"🗑 حذف {c['bank_name'] or _mask_card(c['card_number'])}",
                                            callback_data=f"card_delete_confirm:{c['id']}")])
    rows.append([InlineKeyboardButton(text="➕ افزودن کارت جدید", callback_data="card_add")])
    rotate_label = fa.AUTO_ROTATE_ON if auto_rotate else fa.AUTO_ROTATE_OFF
    rows.append([InlineKeyboardButton(text=rotate_label, callback_data="card_toggle_rotation")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def broadcast_audience_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=fa.BROADCAST_AUDIENCE_ALL, callback_data="bc_aud:all")],
        [InlineKeyboardButton(text=fa.BROADCAST_AUDIENCE_SEEN, callback_data="bc_aud:seen")],
        [InlineKeyboardButton(text=fa.BROADCAST_AUDIENCE_NOT_SEEN, callback_data="bc_aud:not_seen")],
        [InlineKeyboardButton(text=fa.BROADCAST_AUDIENCE_DATE, callback_data="bc_aud:date")],
    ])


def broadcast_session_or_day_keyboard(event_id: int, date_iso: str, sessions: list[dict]) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(
        text=fa.BROADCAST_WHOLE_DAY, callback_data=f"bc_day:{event_id}:{date_iso}",
    )]]
    for s in sessions:
        rows.append([InlineKeyboardButton(
            text=f"🕒 {s['session_time']}", callback_data=f"bc_session:{s['id']}",
        )])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def reject_confirm_keyboard(reservation_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=fa.REJECT_CONFIRM_ACCEPT, callback_data=f"reject_confirm:accept:{reservation_id}")],
        [InlineKeyboardButton(text=fa.REJECT_CONFIRM_RESEND_RECEIPT, callback_data=f"reject_confirm:resend:{reservation_id}")],
        [InlineKeyboardButton(text=fa.REJECT_CONFIRM_DISPUTE, callback_data=f"reject_confirm:dispute:{reservation_id}")],
    ])


def overflow_request_keyboard(waitlist_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=fa.OVERFLOW_APPROVE_BUTTON, callback_data=f"overflow:approve:{waitlist_id}")],
        [InlineKeyboardButton(text=fa.OVERFLOW_REJECT_BUTTON, callback_data=f"overflow:reject:{waitlist_id}")],
    ])


def stats_event_keyboard() -> InlineKeyboardMarkup:
    """First step of the sales-report flow: which event these numbers are
    about. Needed once more than one event exists, so a report never
    silently mixes two events' revenue together."""
    from database.repositories import events as events_repo
    rows = [[InlineKeyboardButton(text="📊 همه رویدادها (مجموع)", callback_data="stats_event:0")]]
    for event in events_repo.list_all_events():
        rows.append([InlineKeyboardButton(text=f"🎭 {event['title']}", callback_data=f"stats_event:{event['id']}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def stats_period_keyboard(event_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=fa.STATS_PERIOD_TODAY, callback_data=f"stats_period:today:{event_id}")],
        [InlineKeyboardButton(text=fa.STATS_PERIOD_WEEK, callback_data=f"stats_period:week:{event_id}")],
        [InlineKeyboardButton(text=fa.STATS_PERIOD_ALL, callback_data=f"stats_period:all:{event_id}")],
        [InlineKeyboardButton(text=fa.STATS_PERIOD_CUSTOM, callback_data=f"stats_period:custom:{event_id}")],
    ])


def stats_result_keyboard(date_from: str | None, date_to: str | None, event_id: int) -> InlineKeyboardMarkup:
    from_part = date_from or "-"
    to_part = date_to or "-"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="📋 مشاهده لیست شماره‌ها",
            callback_data=f"stats_contacts:{from_part}:{to_part}:{event_id}",
        )],
    ])


def number_stepper_keyboard(current: int, min_val: int, max_val: int, prefix: str,
                             unit: str = "نفر") -> InlineKeyboardMarkup:
    display = f"{current} {unit}"
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="➖", callback_data=f"{prefix}:dec"),
            InlineKeyboardButton(text=display, callback_data="noop"),
            InlineKeyboardButton(text="➕", callback_data=f"{prefix}:inc"),
        ],
        [InlineKeyboardButton(text="✅ تأیید", callback_data=f"{prefix}:confirm")],
    ])


_EVENT_ICON_CHOICES = ["🎭", "🎵", "🎨", "🎪", "✨"]


def event_icon_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=icon, callback_data=f"event_icon:{icon}")
        for icon in _EVENT_ICON_CHOICES
    ]])


def qr_mark_used_keyboard(reservation_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=fa.QR_MARK_USED_BUTTON, callback_data=f"qr_mark_used:{reservation_id}")
    ]])


def pick_staff_for_groups_keyboard(admins: list[dict]) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=f"🆔 {a['telegram_id']} ({a['role']})", callback_data=f"groups_pick:{a['telegram_id']}")]
        for a in admins if a["role"] != "owner"  # owners always have everything — no groups needed
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def toggle_groups_keyboard(telegram_id: int, current_groups: set[str]) -> InlineKeyboardMarkup:
    labels = {"finance": "💰 مالی", "sales": "🎫 فروش", "content": "🎭 محتوا"}
    rows = []
    for group_name, label in labels.items():
        mark = "✅ " if group_name in current_groups else "⬜️ "
        rows.append([InlineKeyboardButton(
            text=mark + label, callback_data=f"groups_toggle:{telegram_id}:{group_name}",
        )])
    rows.append([InlineKeyboardButton(text=fa.BACK_BUTTON, callback_data="staff:manage_groups")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def reject_reason_menu_keyboard(reservation_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=fa.REJECT_REASON_TYPE_MYSELF, callback_data=f"reject_reason_mode:type:{reservation_id}")],
        [InlineKeyboardButton(text=fa.REJECT_REASON_RECEIPT_PROBLEM, callback_data=f"reject_reason_mode:receipt:{reservation_id}")],
    ])


def dispute_resolve_keyboard(reservation_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=fa.DISPUTE_APPROVE_BUTTON, callback_data=f"dispute_resolve:approve:{reservation_id}")],
        [InlineKeyboardButton(text=fa.DISPUTE_REJECT_AGAIN_BUTTON, callback_data=f"dispute_resolve:again:{reservation_id}")],
        [InlineKeyboardButton(text=fa.DISPUTE_REJECT_BUTTON, callback_data=f"dispute_resolve:reject:{reservation_id}")],
    ])


def calendar_type_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📅 شمسی (پیش‌فرض)", callback_data="event_cal_type:jalali")],
        [InlineKeyboardButton(text="📅 میلادی (رویداد خارج از ایران)", callback_data="event_cal_type:gregorian")],
    ])


def calendar_type_edit_keyboard(event_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📅 شمسی", callback_data=f"event_cal_type_edit:{event_id}:jalali")],
        [InlineKeyboardButton(text="📅 میلادی", callback_data=f"event_cal_type_edit:{event_id}:gregorian")],
    ])


def gregorian_calendar_keyboard(year: int, month: int, callback_prefix: str) -> InlineKeyboardMarkup:
    """
    English/Gregorian equivalent of calendar_keyboard() — used for events
    where the admin picked 'gregorian' as the display calendar (e.g. an
    event held outside Iran). Sunday-last layout, matching Western calendars.
    """
    import calendar as _cal
    from datetime import date as _d

    month_name = _cal.month_name[month]
    rows = [[InlineKeyboardButton(text=f"{month_name} {year}", callback_data="noop")]]
    rows.append([
        InlineKeyboardButton(text=d, callback_data="noop")
        for d in ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    ])

    first_weekday = _d(year, month, 1).weekday()  # Monday=0
    days_in_month = _cal.monthrange(year, month)[1]
    today_iso = _d.today().isoformat()

    week = [InlineKeyboardButton(text=" ", callback_data="noop")] * first_weekday
    for day in range(1, days_in_month + 1):
        iso = f"{year:04d}-{month:02d}-{day:02d}"
        is_past = iso < today_iso
        week.append(InlineKeyboardButton(
            text=("· " if is_past else "") + str(day),
            callback_data="noop" if is_past else f"{callback_prefix}:pick:{iso}",
        ))
        if len(week) == 7:
            rows.append(week)
            week = []
    if week:
        while len(week) < 7:
            week.append(InlineKeyboardButton(text=" ", callback_data="noop"))
        rows.append(week)

    prev_y, prev_m = (year - 1, 12) if month == 1 else (year, month - 1)
    next_y, next_m = (year + 1, 1) if month == 12 else (year, month + 1)
    rows.append([
        InlineKeyboardButton(text="◀️ Prev", callback_data=f"{callback_prefix}:nav:{prev_y}:{prev_m}"),
        InlineKeyboardButton(text="Next ▶️", callback_data=f"{callback_prefix}:nav:{next_y}:{next_m}"),
    ])
    rows.append([InlineKeyboardButton(text=fa.BACK_BUTTON, callback_data=f"{callback_prefix}:back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def any_calendar_keyboard(year: int, month: int, callback_prefix: str, calendar_type: str) -> InlineKeyboardMarkup:
    """Picks Jalali or Gregorian rendering — 'year'/'month' should already
    be in the matching calendar system (Jalali year/month for 'jalali')."""
    if calendar_type == "gregorian":
        return gregorian_calendar_keyboard(year, month, callback_prefix)
    return calendar_keyboard(year, month, callback_prefix)
