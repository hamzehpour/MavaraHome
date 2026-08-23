from database.repositories import settings as settings_repo
from utils.template_renderer import render_template

# Human labels shown in the admin settings menu -> DB key.
# For template keys, the label also lists the placeholders that key supports
# (shown to the admin right before they type the new text).
EDITABLE_SETTINGS = {
    "brand_name": "نام مجموعه",
    "welcome_message": "پیام خوش‌آمدگویی",
    "ticket_price": "قیمت هر بلیت (تومان)",
    "max_tickets_per_person": "حداکثر بلیت هر نفر",
    "rules_text": "متن قوانین",
    "support_contact": "شماره/آیدی پشتیبانی",
    "payment_expiry_minutes": "مهلت ارسال رسید توسط خریدار (دقیقه)",
    "review_reminder_minutes": "یادآوری به ادمین اگر رزرو دیرتر از این مدت بررسی نشد (دقیقه)",
    "tmpl_payment_instructions": (
        "متن راهنمای پرداخت — متغیرها: {people} {unit_price} {total_price} {card_number} {card_holder}"
    ),
    "tmpl_receipt_received": "متن «رسید دریافت شد» — بدون متغیر خاص",
    "tmpl_ticket_confirmed": (
        "متن نهایی بلیت (بعد از تأیید ادمین) — متغیرها: {event_title} {session_date_fa} "
        "{session_time} {people} {full_name} {reservation_code} {total_price} {event_address}"
    ),
    "tmpl_reservation_rejected": "متن «رد شدن پرداخت» — متغیر: {admin_note_block}",
}


def get_brand_name() -> str:
    return settings_repo.get("brand_name", "خانه ماورا")


def get_welcome_message() -> str:
    return settings_repo.get("welcome_message", "")


def get_ticket_price() -> int:
    return settings_repo.get_int("ticket_price", 450000)


def get_active_card_number() -> str:
    from database.repositories import bank_cards as bank_cards_repo
    card = bank_cards_repo.get_active_card()
    return card["card_number"] if card else ""


def get_active_card_holder() -> str:
    from database.repositories import bank_cards as bank_cards_repo
    card = bank_cards_repo.get_active_card()
    return card["card_holder"] if card else ""


def get_max_tickets_per_person() -> int:
    return settings_repo.get_int("max_tickets_per_person", 10)


def get_rules_text() -> str:
    return settings_repo.get("rules_text", "قوانینی هنوز ثبت نشده است.")


def get_support_contact() -> str:
    return settings_repo.get("support_contact", "")


def update_setting(key: str, value: str) -> None:
    if key not in EDITABLE_SETTINGS:
        raise ValueError(f"Unknown setting key: {key}")
    settings_repo.set(key, value)


# ---------------- admin-editable message templates ----------------

def render_payment_instructions(people: int, unit_price: int, total_price: int) -> str:
    template = settings_repo.get("tmpl_payment_instructions", "")
    return render_template(
        template,
        people=people,
        unit_price=f"{unit_price:,}",
        total_price=f"{total_price:,}",
        # Always wrapped in backticks so Telegram renders it as tap-to-copy
        # monospace — independent of whatever the admin typed in the
        # template text itself (that was the actual bug: an admin editing
        # the message loses the backticks and the copy feature dies).
        card_number=f"`{get_active_card_number()}`",
        card_holder=get_active_card_holder(),
    )


def render_receipt_received() -> str:
    return settings_repo.get("tmpl_receipt_received", "")


def render_ticket_confirmed(event_title: str, session_date_iso: str, session_time: str,
                             people: int, full_name: str, reservation_code: str,
                             total_price: int, event_address: str = "", calendar_type: str = "jalali") -> str:
    from utils.jalali import display_date_for_event
    template = settings_repo.get("tmpl_ticket_confirmed", "")
    return render_template(
        template,
        event_title=event_title,
        session_date_fa=display_date_for_event(session_date_iso, calendar_type),
        session_time=session_time,
        people=people,
        full_name=full_name,
        reservation_code=reservation_code,
        total_price=f"{total_price:,}",
        event_address=event_address or "—",
    )


def render_rejection(admin_note: str) -> str:
    template = settings_repo.get("tmpl_reservation_rejected", "")
    note_block = f"دلیل: {admin_note}" if admin_note else ""
    return render_template(template, admin_note_block=note_block)
