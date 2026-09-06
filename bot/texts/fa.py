"""
Every single Persian string the bot shows to users or admins lives here.
Handlers and services NEVER contain literal text — they import from
this module. Changing wording, tone, or adding emoji never touches
business logic again.
Strings that need dynamic values use str.format placeholders.
"""

# ---------- generic ----------
UNKNOWN_ERROR = "❌ خطایی رخ داد. لطفاً دوباره تلاش کنید یا با پشتیبانی تماس بگیرید."
BACK_BUTTON = "🔙 بازگشت"
CANCEL_BUTTON = "❌ انصراف"

# ---------- start / menu ----------
def welcome(brand_name: str, welcome_message: str) -> str:
    return welcome_message or f"درود بر شما 👋\n\nبه ربات رسمی {brand_name} خوش آمدید."

MAIN_MENU_BOOKING = "🎭 رزرو بلیت"
MAIN_MENU_MY_RESERVATIONS = "📋 رزروهای من"
MAIN_MENU_RULES = "📜 قوانین"
MAIN_MENU_SUPPORT = "☎️ پشتیبانی"
MAIN_MENU_REOPENING_INTEREST = "🔔 منتظر اجرای بعدی"

# ---------- booking flow ----------
NO_ACTIVE_EVENT = "😔 در حال حاضر اجرای فعالی برای رزرو وجود ندارد."
CHOOSE_DATE = "🎭 رزرو بلیت\n\n📅 لطفاً تاریخ اجرا را انتخاب کنید:"
NO_SESSIONS_FOR_DATE = "😔 برای این تاریخ سانسی ثبت نشده است."
CHOOSE_SESSION = "🕒 لطفاً سانس مورد نظر را انتخاب کنید:"

def choosing_session_header(date_fa: str, has_full_session: bool = False) -> str:
    header = f"📅 شما در حال انتخاب سانس برای روز:\n{date_fa}\n\n{CHOOSE_SESSION}"
    if has_full_session:
        # Requested fix: without this, a buyer facing a "تکمیل ظرفیت" session
        # had no reason to believe tapping it would do anything — so they'd
        # just leave instead of ever discovering the overflow-request path.
        header += "\n\n⚠️ برای درخواست ظرفیت اضافه روی سانس‌های «تکمیل ظرفیت» هم می‌توانید کلیک کنید."
    return header

def reuse_contact_prompt(full_name: str, phone: str) -> str:
    return (
        "قبلاً این اطلاعات را از شما ثبت کرده‌ایم:\n\n"
        f"👤 {full_name}\n📱 {phone}\n\n"
        "همین اطلاعات درست است یا می‌خواهید ویرایش کنید؟"
    )

CHOOSE_PEOPLE_COUNT = "👥 تعداد بلیت را انتخاب کنید:"
PEOPLE_LIMIT_REACHED = "⚠️ حداکثر تعداد بلیت مجاز برای هر نفر {max_people} عدد است."

def people_confirmed(people: int) -> str:
    return f"👥 تعداد انتخاب شده: {people} نفر\n\n👤 لطفاً نام و نام خانوادگی را وارد کنید."

NAME_INVALID = "❌ لطفاً نام و نام خانوادگی معتبر وارد کنید (بین ۳ تا ۵۰ کاراکتر، فقط حروف)."
ASK_PHONE = "📱 لطفاً شماره موبایل را ارسال کنید."
SEND_PHONE_BUTTON = "📱 ارسال شماره موبایل"
PHONE_REQUIRED = "❌ لطفاً شماره موبایل وارد کنید."
PHONE_DIGITS_ONLY = "❌ شماره موبایل فقط باید شامل عدد باشد."
PHONE_FORMAT_INVALID = "❌ شماره موبایل باید ۱۱ رقم باشد و با 09 شروع شود."

def review_summary(full_name: str, phone: str, people: int, unit_price: int, total_price: int,
                    currency: str = "تومان", attendee_name: str | None = None, attendee_phone: str | None = None) -> str:
    attendee_block = ""
    if attendee_name:
        attendee_block = f"\n\n👤 نام فرد حاضر در سانس:\n{attendee_name}\n📱 شماره او:\n{attendee_phone}"
    return (
        "🫧 لطفاً اطلاعات رزرو را بررسی کنید\n\n"
        "━━━━━━━━━━━━━━\n\n"
        f"👤 نام (حساب شما):\n{full_name}\n\n"
        f"📱 شماره موبایل شما:\n{phone}\n\n"
        f"👥 تعداد بلیت:\n{people} نفر\n\n"
        f"🎫 قیمت هر بلیت:\n{unit_price:,} {currency}\n\n"
        f"💰 مبلغ کل قابل پرداخت:\n{total_price:,} {currency}"
        f"{attendee_block}\n\n"
        "اگر اطلاعات صحیح است، «ادامه پرداخت» را انتخاب کنید."
    )

RESERVATION_SAVED = "✅ اطلاعات ثبت شد."

WAITLISTED = (
    "🌱 ظرفیت این سانس در حال حاضر تکمیل شده است.\n\n"
    "درخواست شما در لیست انتظار ثبت شد و تیم ما در صورت خالی شدن جا با شما تماس می‌گیرد."
)

ASK_RECEIPT_PHOTO = "📷 لطفاً تصویر رسید پرداخت را ارسال کنید."
RECEIPT_MUST_BE_PHOTO = "❌ لطفاً رسید را به‌صورت عکس ارسال کنید."
NO_ACTIVE_BOOKING_SESSION = "⚠️ رزرو فعالی پیدا نشد. لطفاً از ابتدا شروع کنید."

MY_RESERVATIONS_EMPTY = "شما هنوز هیچ رزروی ثبت نکرده‌اید."

# ---------- support ----------
SUPPORT_NOT_CONFIGURED = "پشتیبانی هنوز توسط ادمین تنظیم نشده است."
SUPPORT_MENU_CALL = "📞 تماس با پشتیبانی"
SUPPORT_MENU_MESSAGE = "✍️ ارسال پیام به پشتیبانی"

def support_contact_text(contact: str) -> str:
    return f"☎️ برای تماس با پشتیبانی:\n\n{contact}"

ASK_SUPPORT_MESSAGE = "پیام خود را بنویسید — برای تیم پشتیبانی ارسال می‌شود:"
SUPPORT_MESSAGE_SENT = "✅ پیام شما برای پشتیبانی ارسال شد. به‌زودی پاسخ داده می‌شود."

def support_ticket_notify(full_name: str, phone: str, text: str) -> str:
    return (
        "✉️ پیام جدید از پشتیبانی\n\n"
        f"👤 {full_name or '—'}\n"
        f"📱 {phone or '—'}\n\n"
        f"{text}"
    )

ASK_SUPPORT_REPLY = "پاسخ خود را بنویسید:"
SUPPORT_REPLY_SENT_STAFF_SIDE = "✅ پاسخ برای کاربر ارسال شد."

def support_reply_received(text: str) -> str:
    return f"↩️ پاسخ پشتیبانی:\n\n{text}"

def reservation_row(code: str, status_fa: str, people: int, total_price: int) -> str:
    return f"🎫 {code or '(در انتظار بررسی)'} — {status_fa} — {people} نفر — {total_price:,} تومان"

# ---------- reservation status labels (fa) ----------
STATUS_LABELS = {
    "pending_payment": "در انتظار پرداخت",
    "pending_review": "در انتظار بررسی ادمین",
    "awaiting_buyer_confirmation": "در انتظار پاسخ خریدار به رد پرداخت",
    "approved": "تأیید شده ✅",
    "rejected": "رد شده ❌",
    "cancelled": "لغو شده",
    "expired": "منقضی شده",
    "used": "استفاده شده",
    "waiting": "در لیست انتظار",
}

# ---------- admin: access ----------
NOT_ADMIN = "⛔️ شما دسترسی ادمین ندارید."
ADMIN_MENU_TITLE = "🛠 پنل مدیریت — لطفاً بخش مورد نظر را انتخاب کنید:"

# ---------- admin: reservation review ----------
NO_PENDING_RESERVATIONS = "✅ در حال حاضر رزرو در انتظار بررسی وجود ندارد."

def admin_reservation_card(res: dict) -> str:
    attendee_block = ""
    if res.get("attendee_name"):
        attendee_block = (
            f"\n👥 برای شخص دیگری — نام حاضر: {res['attendee_name']}\n"
            f"📱 شماره حاضر: {res.get('attendee_phone', '—')}"
        )
    return (
        f"🆕 رزرو جدید در انتظار بررسی\n\n"
        f"👤 نام خریدار: {res['user_full_name']}\n"
        f"📱 شماره خریدار: {res['user_phone']}\n"
        f"👥 تعداد: {res['people']} نفر\n"
        f"💰 مبلغ: {res['total_price']:,} تومان{attendee_block}\n"
        f"🕒 ثبت شده: {res['created_at']}\n"
    )

APPROVE_BUTTON = "✅ تأیید پرداخت"
REJECT_BUTTON = "❌ رد پرداخت"
ASK_REJECT_REASON = "لطفاً دلیل رد پرداخت را بنویسید (یا بنویسید «-» برای بدون دلیل):"
RESERVATION_APPROVED_ADMIN_SIDE = "✅ رزرو تأیید و بلیت برای کاربر ارسال شد."
RESERVATION_REJECTED_ADMIN_SIDE = "❌ رزرو رد شد و به کاربر اطلاع داده شد."

# ---------- admin: events/sessions ----------
EVENTS_MENU_TITLE = "🎭 مدیریت رویدادها:"
ASK_EVENT_TITLE = "عنوان اجرای جدید را وارد کنید:"
ASK_SESSION_DATE = "تاریخ سانس را وارد کنید (مثال: 2026-08-01):"
ASK_SESSION_TIME = "ساعت سانس را وارد کنید (مثال: 20:00):"
ASK_SESSION_CAPACITY = "ظرفیت این سانس را وارد کنید (عدد):"
EVENT_CREATED = "✅ اجرا با موفقیت ساخته شد."
SESSION_CREATED = "✅ سانس با موفقیت اضافه شد."
INVALID_NUMBER = "❌ لطفاً یک عدد معتبر وارد کنید."

# ---------- admin: stats/broadcast/settings ----------
def stats_report(stats: dict, users_count: int) -> str:
    return (
        "📊 آمار فروش\n\n"
        f"🎟 بلیت‌های فروخته‌شده: {stats['tickets_sold']}\n"
        f"💰 درآمد کل: {stats['revenue']:,} تومان\n"
        f"⏳ در انتظار بررسی: {stats['pending_review_count']}\n"
        f"❌ رد شده: {stats['rejected_count']}\n\n"
        f"👥 تعداد کاربران ربات: {users_count}"
    )

ASK_BROADCAST_MESSAGE = "متن پیام همگانی را ارسال کنید:"
BROADCAST_CONFIRM = "این پیام برای همه کاربران ({count} نفر) ارسال شود؟"
BROADCAST_DONE = "✅ پیام همگانی ارسال شد. موفق: {success} — ناموفق: {failed}"
SETTINGS_MENU_TITLE = "⚙️ تنظیمات قابل ویرایش:"
ASK_NEW_VALUE = "مقدار جدید برای «{label}» را وارد کنید:\n\nمقدار فعلی: {current}"
SETTING_UPDATED = "✅ به‌روزرسانی شد."
EXPORT_READY = "📊 خروجی اکسل آماده شد."

# ---------- multi-event support ----------
CHOOSE_EVENT = "🎭 لطفاً رویداد مورد نظر را انتخاب کنید:"
NO_ACTIVE_EVENTS = "😔 در حال حاضر هیچ رویداد فعالی برای رزرو وجود ندارد."

# ---------- staff (operator / phone-support) role ----------
STAFF_MENU_TITLE = "☎️ پنل پشتیبانی — لطفاً بخش مورد نظر را انتخاب کنید:"
STAFF_MENU_PENDING = "🕒 رزروهای در انتظار بررسی"
STAFF_MENU_CAPACITY = "📊 مشاهده ظرفیت سانس‌ها"
STAFF_MENU_MANUAL_BOOKING = "📞 ثبت رزرو تلفنی"

def capacity_report(event_title: str, sessions: list[dict]) -> str:
    lines = [f"🎭 {event_title}", ""]
    for s in sessions:
        lines.append(
            f"📅 {s['session_date']} — {s['session_time']} : "
            f"{s['reserved']}/{s['capacity']} پر شده (باقی‌مانده: {s['remaining']})"
        )
    return "\n".join(lines) if len(lines) > 2 else f"{event_title}\n\nسانسی ثبت نشده."

STAFF_LIST_TITLE = "👥 لیست مسئولان و ادمین‌ها:"

def staff_row(telegram_id: int, role: str, groups: set[str] | None = None) -> str:
    role_fa = {"owner": "مالک", "admin": "ادمین", "operator": "مسئول پشتیبانی/رزرو تلفنی"}.get(role, role)
    line = f"🆔 {telegram_id} — {role_fa}"
    if groups:
        group_labels = {"finance": "مالی", "sales": "فروش", "content": "محتوا"}
        line += " + " + "، ".join(group_labels.get(g, g) for g in sorted(groups))
    return line

ASK_STAFF_TELEGRAM_ID = (
    "یوزرنیم تلگرام فرد را با @ وارد کنید (مثل @username) — یا اگر یوزرنیم ندارد، "
    "آیدی عددی‌اش را وارد کنید (از ربات‌هایی مثل @userinfobot قابل دریافت است). "
    "توجه: برای شناسایی با یوزرنیم، آن فرد باید قبلاً حداقل یک بار ربات را استارت کرده باشد."
)
ASK_STAFF_ROLE = "نقش این فرد را انتخاب کنید:"
STAFF_ADDED = "✅ فرد با موفقیت به لیست مسئولان اضافه شد."
STAFF_REMOVED = "✅ دسترسی این فرد حذف شد."

# ---------- manual / phone booking (taken by support staff) ----------
MANUAL_BOOKING_INTRO = "📞 ثبت رزرو تلفنی\n\nلطفاً رویداد مربوطه را انتخاب کنید:"
ASK_MANUAL_PEOPLE = "تعداد نفرات را به‌صورت عدد وارد کنید:"
ASK_MANUAL_NAME = "نام و نام خانوادگی مشتری را وارد کنید:"
ASK_MANUAL_PHONE = "شماره موبایل مشتری را وارد کنید:"

def manual_booking_review(full_name: str, phone: str, people: int, total_price: int) -> str:
    return (
        "لطفاً اطلاعات را بررسی کنید:\n\n"
        f"👤 نام: {full_name}\n"
        f"📱 شماره: {phone}\n"
        f"👥 تعداد: {people} نفر\n"
        f"💰 مبلغ: {total_price:,} تومان\n\n"
        "با تأیید این رزرو، بلیت صادر و پیامک/کد رزرو در اختیار شما قرار می‌گیرد "
        "تا تلفنی به مشتری اعلام کنید."
    )

def manual_booking_confirmed(reservation_code: str) -> str:
    return (
        f"✅ رزرو با موفقیت ثبت و بلیت صادر شد.\n\n"
        f"🎫 کد رزرو: `{reservation_code}`\n\n"
        "این کد را می‌توانید تلفنی به مشتری اعلام کنید."
    )

MANUAL_BOOKING_WAITLISTED = (
    "⚠️ ظرفیت این سانس تکمیل است. مشتری در لیست انتظار ثبت شد."
)

# ---------- bank cards (multi-card support) ----------
BANK_CARDS_MENU_TITLE = "💳 مدیریت کارت‌های بانکی:"
NO_BANK_CARDS = "هنوز هیچ کارتی ثبت نشده — یک کارت اضافه کنید تا رزرو فعال شود."

def bank_card_row(bank_name: str, card_number: str, card_holder: str, is_active: bool) -> str:
    mark = "🟢 (فعال)" if is_active else "⚪️"
    bank = f" — {bank_name}" if bank_name else ""
    return f"{mark} {card_number} — {card_holder}{bank}"

ASK_NEW_CARD_NUMBER = "شماره کارت جدید را وارد کنید:"
ASK_NEW_CARD_HOLDER = "نام صاحب حساب را وارد کنید:"
ASK_NEW_CARD_BANK = "نام بانک را وارد کنید (اختیاری — می‌توانید «-» بزنید):"
CARD_ADDED = "✅ کارت اضافه شد."
CARD_LIMIT_REACHED = "❌ حداکثر ۱۰ کارت قابل ثبت است."
CARD_ACTIVATED = "✅ این کارت به‌عنوان کارت فعال انتخاب شد."
CARD_DELETED = "🗑 کارت حذف شد."
AUTO_ROTATE_ON = "🔁 چرخش خودکار هفتگی: روشن"
AUTO_ROTATE_OFF = "🔁 چرخش خودکار هفتگی: خاموش"

# ---------- "my reservations" — grouped, redesigned ----------
MY_RES_SECTION_WAITING = "⏳ در انتظار بررسی/پرداخت"
MY_RES_SECTION_UPCOMING = "🎫 بلیت‌های فعال (هنوز اجرا نشده)"
MY_RES_SECTION_PAST = "✅ اجراهای دیده‌شده"
MY_RES_SECTION_OTHER = "❌ لغو‌شده / رد‌شده / منقضی"

def my_reservation_line(event_title: str, session_date_fa: str, session_time: str,
                          people: int, code: str | None) -> str:
    code_part = f" — کد: {code}" if code else ""
    return f"🎭 {event_title} | {session_date_fa} — {session_time} | {people} نفر{code_part}"

# ---------- booking for someone else ----------
ASK_FOR_WHOM = "🎫 این بلیت برای خودتان است یا شخص دیگری؟"
ASK_ATTENDEE_NAME = "نام و نام خانوادگی فردی که تشریف می‌آورد را وارد کنید:"
ASK_ATTENDEE_PHONE = "شماره موبایل همان فرد (کسی که می‌آید) را وارد کنید:"
ATTENDEE_NOTE = "\n\nℹ️ توجه: رزرو زیر نام حساب شماست، اما اطلاعات فرد حاضر هم برای تیم ما ثبت می‌شود."

# ---------- broadcast audience selection ----------
BROADCAST_ASK_AUDIENCE = "پیام همگانی برای چه کسانی ارسال شود؟"
BROADCAST_AUDIENCE_ALL = "👥 همه کاربران"
BROADCAST_AUDIENCE_SEEN = "✅ کسانی که اجرا را دیده‌اند"
BROADCAST_AUDIENCE_NOT_SEEN = "🎫 کسانی که بلیت دارند ولی هنوز ندیده‌اند"
BROADCAST_AUDIENCE_DATE = "📅 یک روز/سانس خاص"
BROADCAST_PICK_EVENT = "رویداد را انتخاب کنید:"
BROADCAST_PICK_DATE = "روز مورد نظر را انتخاب کنید:"
BROADCAST_PICK_SESSION_OR_WHOLE_DAY = "می‌خواهید به کل این روز پیام بدهید یا یک سانس مشخص؟"
BROADCAST_WHOLE_DAY = "📅 کل این روز"

# ---------- reject → buyer-confirmation grace period ----------
def reject_notice_to_buyer(admin_note: str) -> str:
    note = f"\n\nدلیل: {admin_note}" if admin_note else ""
    return (
        "😔 ادمین پرداخت شما را رد کرد." + note +
        "\n\nاگر این را می‌پذیرید، رزرو کنسل خواهد شد. "
        "اگر فکر می‌کنید اشتباهی رخ داده (مثلاً واریز انجام شده)، می‌توانید توضیح بدهید."
    )

REJECT_CONFIRM_ACCEPT = "✅ می‌پذیرم، رزرو کنسل شود"
REJECT_CONFIRM_DISPUTE = "✍️ توضیح می‌دهم"
RESERVATION_CANCELLED_BY_BUYER = "رزرو شما کنسل شد. هر زمان خواستید می‌توانید دوباره از منوی «رزرو بلیت» اقدام کنید."
ASK_DISPUTE_EXPLANATION = "توضیح خود را بنویسید — برای ادمین ارسال می‌شود:"
DISPUTE_SENT_TO_BUYER_SIDE = "✅ توضیح شما برای بررسی مجدد به ادمین ارسال شد."

def dispute_notify_admin(full_name: str, phone: str, admin_note: str, explanation: str) -> str:
    return (
        "⚠️ خریدار به رد پرداخت اعتراض کرد\n\n"
        f"👤 {full_name} — 📱 {phone}\n"
        f"دلیل رد قبلی: {admin_note or '—'}\n\n"
        f"توضیح خریدار:\n{explanation}\n\n"
        "لطفاً تصمیم نهایی را بگیرید:"
    )

DISPUTE_APPROVE_BUTTON = "✅ قبول می‌کنم، تأیید کن"
DISPUTE_REJECT_BUTTON = "❌ قطعاً رد کن"
DISPUTE_RESOLVED_REJECTED_ADMIN_SIDE = "رزرو قطعاً رد شد و به خریدار اطلاع داده شد."
RESERVATION_FINAL_REJECTED = "😔 پس از بررسی، رزرو شما نهایتاً رد شد و کنسل گردید."

# ---------- overflow-capacity request (waitlist → admin approval) ----------
def overflow_request_admin(full_name: str, phone: str, people: int, capacity: int,
                             session_date_fa: str, session_time: str) -> str:
    return (
        "📈 درخواست اضافه‌ظرفیت\n\n"
        f"👤 {full_name} — 📱 {phone}\n"
        f"🕒 سانس: {session_date_fa} — {session_time}\n"
        f"ظرفیت فعلی: {capacity} — درخواست: {people} نفر\n\n"
        "اگر ظرفیت را افزایش دهید، این فرد خودکار وارد فرایند پرداخت می‌شود."
    )

OVERFLOW_APPROVE_BUTTON = "✅ ظرفیت را اضافه کن و اجازه بده رزرو کند"
OVERFLOW_REJECT_BUTTON = "❌ امکان افزایش نیست"
OVERFLOW_APPROVED_BUYER_MSG = "🎉 خبر خوب! ظرفیت برای شما باز شد. لطفاً پرداخت را انجام دهید:"
OVERFLOW_REJECTED_BUYER_MSG = "😔 متأسفانه امکان افزایش ظرفیت برای این سانس نبود. لطفاً سانس دیگری را امتحان کنید."
OVERFLOW_RESOLVED_ADMIN_SIDE = "✅ انجام شد."

# ---------- stats: period picker + breakdown + contact list ----------
STATS_ASK_PERIOD = "📊 آمار فروش برای کدام بازه؟"
STATS_PERIOD_TODAY = "امروز"
STATS_PERIOD_WEEK = "این هفته"
STATS_PERIOD_ALL = "کل"
STATS_PERIOD_CUSTOM = "بازه دلخواه (از تاریخ تا تاریخ)"
STATS_ASK_CUSTOM_FROM = "تاریخ شروع را انتخاب کنید:"
STATS_ASK_CUSTOM_TO = "تاریخ پایان را انتخاب کنید:"

def stats_range_report(totals: dict, by_session: list[dict]) -> str:
    from utils.jalali import gregorian_iso_to_jalali_display
    lines = [
        f"🎟 مجموع بلیت: {totals['tickets']}",
        f"💰 مجموع درآمد: {totals['revenue']:,} تومان",
        f"📄 تعداد رزرو: {totals['count']}",
        "",
        "━━━ به تفکیک سانس ━━━",
    ]
    if not by_session:
        lines.append("رزرو تأییدشده‌ای در این بازه نیست.")
    for s in by_session:
        lines.append(
            f"🎭 {s['event_title']} | {gregorian_iso_to_jalali_display(s['session_date'])} — {s['session_time']} "
            f"| {s['tickets']} بلیت | {s['revenue']:,} تومان"
        )
    return "\n".join(lines)

CONTACT_LIST_EMPTY = "کسی در این بازه رزرو تأییدشده ندارد."

def contact_list_report(entries: list[dict]) -> str:
    from utils.jalali import gregorian_iso_to_jalali_display
    lines = []
    current_session = None
    for e in entries:
        key = (e["session_date"], e["session_time"])
        if key != current_session:
            current_session = key
            lines.append(f"\n📅 {gregorian_iso_to_jalali_display(e['session_date'])} — {e['session_time']}")
        name = e.get("attendee_name") or e["full_name"]
        phone = e.get("attendee_phone") or e["phone"]
        lines.append(f"👤 {name} — {e['people']} نفر — {phone}")
    return "\n".join(lines).strip() or CONTACT_LIST_EMPTY

# ---------- direct message to a single user ----------
ASK_DIRECT_MESSAGE_TARGET = (
    "یوزرنیم (با @) یا آیدی عددی کاربری که می‌خواهید پیام بدهید را وارد کنید:"
)
ASK_DIRECT_MESSAGE_TEXT = "متن پیام را بنویسید:"
DIRECT_MESSAGE_SENT = "✅ پیام ارسال شد."
DIRECT_MESSAGE_FAILED = "❌ ارسال پیام ناموفق بود — احتمالاً این کاربر ربات را استارت نکرده یا بلاک کرده."

# ---------- QR ticket verification (at the door) ----------
STAFF_MENU_VERIFY_TICKET = "🔍 بررسی بلیت (QR)"
ASK_QR_PAYLOAD = "متن داخل QR کد را اینجا بفرستید (با یک اپ اسکنر QR روی گوشی، آن را اسکن و کپی کنید):"
QR_INVALID_SIGNATURE = "❌ این بلیت معتبر نیست یا جعلی است — امضا تطابق ندارد."
QR_CODE_NOT_FOUND = "❌ کدی با این مشخصات در سیستم پیدا نشد."

def qr_verify_result(reservation: dict, event_title: str, session_date_fa: str, session_time: str) -> str:
    status_fa = STATUS_LABELS.get(reservation["status"], reservation["status"])
    used_note = "\n\n⚠️ این بلیت قبلاً استفاده‌شده ثبت شده بود!" if reservation["status"] == "used" else ""
    return (
        f"✅ بلیت معتبر است\n\n"
        f"🎭 {event_title} | {session_date_fa} — {session_time}\n"
        f"👤 {reservation.get('attendee_name') or reservation['user_full_name']}\n"
        f"👥 {reservation['people']} نفر\n"
        f"وضعیت: {status_fa}{used_note}"
    )

QR_MARK_USED_BUTTON = "✅ ورود ثبت شود (استفاده‌شده)"
QR_MARKED_USED = "✅ ورود ثبت شد."

# ---------- owner passcode + protected owner removal ----------
ASK_SET_OWNER_PASSCODE = "یک رمز جدید برای انتقال مالکیت تعیین کنید (حداقل ۴ کاراکتر):"
OWNER_PASSCODE_SET = "✅ رمز انتقال مالکیت ثبت شد."
ASK_OWNER_PASSCODE_TO_CONFIRM = "برای افزودن مالک جدید، رمز انتقال مالکیت را وارد کنید:"
OWNER_PASSCODE_WRONG = "❌ رمز اشتباه است. عملیات لغو شد."
OWNER_PASSCODE_NOT_SET = "❌ هنوز رمز انتقال مالکیت تعیین نشده — اول از «🔐 تنظیم رمز انتقال مالکیت» آن را بسازید."
NEW_OWNER_ADDED = "✅ مالک جدید اضافه شد. حالا هر دو دسترسی کامل دارید."

def owner_removal_scheduled(hours: int) -> str:
    return (
        f"⏳ حذف این مالک ثبت شد ولی بلافاصله انجام نمی‌شود — طبق تنظیمات امنیتی، "
        f"{hours} ساعت دیگر نهایی می‌شود. اگر پشیمان شدید، می‌توانید تا قبل از آن لغوش کنید."
    )
OWNER_REMOVAL_CANCEL_BUTTON = "↩️ لغو حذف این مالک"
OWNER_REMOVAL_CANCELLED = "✅ حذف این مالک لغو شد."
OWNER_REMOVAL_FINALIZED_NOTICE = "یک مالک بعد از گذشت مهلت امنیتی از ربات حذف شد."

# ---------- channel monitoring setup ----------
ASK_FORWARD_CHANNEL_MESSAGE = (
    "برای راه‌اندازی کانال مانیتورینگ:\n\n"
    "۱. ربات را در آن کانال ادمین کنید (با دسترسی ارسال پیام)\n"
    "۲. یک پیام از همان کانال را همین‌جا برای من فوروارد کنید\n\n"
    "اگر به‌جای کانال از یک گروه استفاده می‌کنید (فوروارد از گروه معمولاً کار نمی‌کند، "
    "چون به‌جای گروه، اسم خودتان به‌عنوان فرستنده روی پیام فوروارد‌شده می‌ماند): به‌جای فوروارد، "
    "ربات را به آن گروه اضافه کنید و دستور /setgroup را مستقیماً داخل همان گروه بفرستید."
)
CHANNEL_SETUP_NOT_A_FORWARD = (
    "❌ این یک پیام فوروارد‌شده از کانال نبود. لطفاً دوباره تلاش کنید.\n\n"
    "اگر می‌خواهید از یک گروه (نه کانال) استفاده کنید، فوروارد کار نمی‌کند — "
    "به‌جایش ربات را به آن گروه اضافه کنید و دستور /setgroup را همان‌جا داخل گروه بفرستید."
)
CHANNEL_SETUP_SUCCESS = "✅ کانال مانیتورینگ تنظیم شد و یک پیام آزمایشی ارسال شد."
CHANNEL_SETUP_FAILED = (
    "❌ نتوانستم در آن کانال پیام بفرستم — مطمئن شوید ربات را با دسترسی ارسال پیام "
    "به آن کانال اضافه کرده‌اید."
)
CHANNEL_TEST_MESSAGE = "✅ ربات با موفقیت به این کانال وصل شد — از این پس وضعیت فروش اینجا زنده به‌روزرسانی می‌شود."
GROUP_SETUP_WRONG_CHAT = "❌ دستور /setgroup باید داخل خودِ گروه فرستاده شود، نه اینجا."
GROUP_SETUP_FAILED = (
    "❌ نتوانستم داخل این گروه پیام بفرستم — مطمئن شوید ربات عضو این گروه است."
)
GROUP_SETUP_SUCCESS = "✅ این گروه به‌عنوان کانال مانیتورینگ تنظیم شد و یک پیام آزمایشی ارسال شد."

# ---------- admin alerts channel setup (separate from monitoring above:
# monitoring is a silent live board with no action buttons; this channel
# gets a fresh message per new reservation/waitlist entry — with the
# receipt + approve/reject buttons for reservations — so the two can be
# two different channels/groups instead of interleaving in one) ----------
ASK_FORWARD_ALERTS_CHANNEL_MESSAGE = (
    "برای راه‌اندازی کانال هشدار رزرو (پیام جدید + دکمه تایید/رد برای هر رزرو/لیست انتظار جدید):\n\n"
    "۱. ربات را در آن کانال ادمین کنید (با دسترسی ارسال پیام)\n"
    "۲. یک پیام از همان کانال را همین‌جا برای من فوروارد کنید\n\n"
    "اگر به‌جای کانال از یک گروه استفاده می‌کنید: به‌جای فوروارد، ربات را به آن گروه اضافه کنید "
    "و دستور /setalertsgroup را مستقیماً داخل همان گروه بفرستید.\n\n"
    "این کانال با «کانال مانیتورینگ» فرق دارد — می‌توانید همان کانال قبلی یا یک کانال/گروه جداگانه انتخاب کنید."
)
ALERTS_CHANNEL_SETUP_NOT_A_FORWARD = (
    "❌ این یک پیام فوروارد‌شده از کانال نبود. لطفاً دوباره تلاش کنید.\n\n"
    "اگر می‌خواهید از یک گروه (نه کانال) استفاده کنید، فوروارد کار نمی‌کند — "
    "به‌جایش ربات را به آن گروه اضافه کنید و دستور /setalertsgroup را همان‌جا داخل گروه بفرستید."
)
ALERTS_CHANNEL_SETUP_SUCCESS = "✅ کانال هشدار رزرو تنظیم شد و یک پیام آزمایشی ارسال شد."
ALERTS_CHANNEL_SETUP_FAILED = (
    "❌ نتوانستم در آن کانال پیام بفرستم — مطمئن شوید ربات را با دسترسی ارسال پیام "
    "به آن کانال اضافه کرده‌اید."
)
ALERTS_CHANNEL_TEST_MESSAGE = "✅ ربات با موفقیت به این کانال وصل شد — از این پس هشدار رزرو/لیست انتظار جدید اینجا ارسال می‌شود."
ALERTS_GROUP_SETUP_WRONG_CHAT = "❌ دستور /setalertsgroup باید داخل خودِ گروه فرستاده شود، نه اینجا."
ALERTS_GROUP_SETUP_FAILED = (
    "❌ نتوانستم داخل این گروه پیام بفرستم — مطمئن شوید ربات عضو این گروه است."
)
ALERTS_GROUP_SETUP_SUCCESS = "✅ این گروه به‌عنوان کانال هشدار رزرو تنظیم شد و یک پیام آزمایشی ارسال شد."

# ---------- permission groups (finance/sales/content) ----------
STAFF_MENU_MANAGE_GROUPS = "🏷 مدیریت گروه‌های دسترسی"
ASK_PICK_STAFF_FOR_GROUPS = "برای کدام فرد می‌خواهید گروه‌های دسترسی را تنظیم کنید؟"

def manage_groups_header(telegram_id: int, groups: set[str]) -> str:
    group_labels = {"finance": "مالی", "sales": "فروش", "content": "محتوا"}
    current = "، ".join(group_labels.get(g, g) for g in sorted(groups)) or "هیچ‌کدام"
    return f"گروه‌های فعلی آیدی {telegram_id}:\n{current}\n\nروی هرکدام بزنید تا اضافه/حذف شود:"

# ---------- resend-receipt / repeat-dispute flow ----------
REJECT_CONFIRM_RESEND_RECEIPT = "📤 ارسال رسید جدید"
ASK_NEW_RECEIPT_PHOTO = "لطفاً تصویر رسید جدید را ارسال کنید:"
NEW_RECEIPT_SUBMITTED_BUYER_SIDE = "✅ رسید جدید ارسال شد و دوباره برای بررسی به تیم ما رفت."
RECEIPT_PROBLEM_PRESET_REASON = "فیش پرداختی واضح نیست یا خوانا نیست — لطفاً رسید واضح‌تری ارسال کنید."
ADMIN_REJECT_REASON_MENU = "دلیل رد را چطور اعلام می‌کنید؟"
REJECT_REASON_TYPE_MYSELF = "✍️ خودم می‌نویسم"
REJECT_REASON_RECEIPT_PROBLEM = "🧾 مشکل از رسید است (پیام آماده)"
DISPUTE_REJECT_AGAIN_BUTTON = "🔁 رد دوباره (دلیل جدید)"
ASK_REJECT_AGAIN_REASON = "دلیل جدید رد را بنویسید:"
DISPUTE_FINAL_REJECT_CONFIRM = "آیا مطمئنید می‌خواهید این رزرو را قطعاً و نهایی رد/کنسل کنید؟"

# ---------- factory reset (test/dev only) ----------
FACTORY_RESET_BUTTON = "🧹 پاک‌سازی کامل و شروع تمیز (فقط تست)"
FACTORY_RESET_WARNING = (
    "⚠️ این کار **همه چیز** را در این دیتابیس (رزروها، کاربران، رویدادها، تنظیمات) پاک می‌کند "
    "و دوباره از صفر می‌سازد.\n\nاین فقط روی محیط تست/توسعه فعلی اثر می‌گذارد، نه دیتای واقعی.\n\n"
    "آیا کاملاً مطمئن هستید؟"
)
FACTORY_RESET_DONE = "✅ دیتابیس کاملاً پاک و از نو ساخته شد."
FACTORY_RESET_BLOCKED_PRODUCTION = "⛔️ این قابلیت روی محیط Production غیرفعال است."
