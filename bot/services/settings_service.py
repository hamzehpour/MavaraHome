from database.repositories import settings as settings_repo
from utils.template_renderer import render_template

# Human labels shown in the admin settings menu -> DB key.
# For template keys, the label also lists the placeholders that key supports
# (shown to the admin right before they type the new text).
EDITABLE_SETTINGS = {
    "brand_name": "نام مجموعه",
    "welcome_message": "پیام خوش‌آمدگویی",
    "ticket_price": "قیمت پیش‌فرض بلیت (تومان) — فقط برای رویدادهایی که قیمت اختصاصی ندارند (قیمت هر رویداد را از صفحه «رویدادها» تنظیم کن)",
    "max_tickets_per_person": "حداکثر بلیت هر نفر",
    "rules_text": "متن قوانین",
    "support_contact": "شماره/آیدی پشتیبانی",
    "payment_expiry_minutes": "مهلت ارسال رسید توسط خریدار (دقیقه)",
    "review_reminder_minutes": "یادآوری به ادمین اگر رزرو دیرتر از این مدت بررسی نشد (دقیقه)",
    # Was already a real, working setting (utils/scheduler.py reads it) —
    # just never listed here, so it was editable nowhere at all, not even
    # from the Telegram menu that every other setting in this dict already
    # gets for free just by being listed.
    "review_reminder_repeat_minutes": "تکرار یادآوری بررسی رزرو دیرمانده، تا وقتی بررسی شود (دقیقه)",
    "tmpl_payment_instructions": (
        "متن راهنمای پرداخت — متغیرها: {people} {unit_price} {total_price} {card_number} {card_holder}"
    ),
    "tmpl_receipt_received": "متن «رسید دریافت شد» — بدون متغیر خاص",
    "tmpl_ticket_confirmed": (
        "متن نهایی بلیت (بعد از تأیید ادمین) — متغیرها: {event_title} {session_date_fa} "
        "{session_time} {people} {full_name} {reservation_code} {total_price} {event_address}"
    ),
    "tmpl_reservation_rejected": "متن «رد شدن پرداخت» — متغیر: {admin_note_block}",
    # ---- email templates (reservation-migration follow-up: these were
    # hardcoded Python strings before — see render_email() below) ----
    "tmpl_email_otp_subject": "موضوع ایمیل کد ورود — متغیرها: {brand_name}",
    "tmpl_email_otp_body": "متن ایمیل کد ورود — متغیرها: {code} {ttl_minutes} {brand_name}",
    "tmpl_email_approved_subject": (
        "موضوع ایمیل تایید رزرو (رزرو عادی و تایید ظرفیت لیست انتظار، هر دو همین یکی) — متغیرها: {event_title} {brand_name}"
    ),
    "tmpl_email_approved_body": (
        "متن ایمیل تایید رزرو — متغیرها: {event_title} {session_date} {session_time} {reservation_code} {brand_name}"
    ),
    "tmpl_email_rejected_subject": "موضوع ایمیل رد رزرو — متغیرها: {event_title} {brand_name}",
    "tmpl_email_rejected_body": "متن ایمیل رد رزرو — متغیرها: {event_title} {session_date} {reason_block} {brand_name}",
    "tmpl_email_waitlist_rejected_subject": "موضوع ایمیل «ظرفیتی آزاد نشد» (لیست انتظار) — متغیرها: {brand_name}",
    "tmpl_email_waitlist_rejected_body": "متن ایمیل «ظرفیتی آزاد نشد» (لیست انتظار) — متغیرها: {brand_name}",
    "ticket_template_title": "عنوان بالای بلیت PDF (مثلاً نام مجموعه)",
    "ticket_template_subtitle": "زیرعنوان بالای بلیت PDF (مثلاً «بلیت الکترونیک»)",
    "ticket_template_footer": "متن پایین بلیت PDF (زیر QR)",
    "otp_channels_enabled": (
        "روش‌های ورود مشتری (با کاما جدا کنید — فقط email فعلاً واقعاً کار می‌کند، "
        "phone فقط زیرساختش آماده است، تا سرویس پیامک وصل نشود کار نمی‌کند)"
    ),
    # ---- website content (phase 3: fixed public-site copy) — Persian
    # only, served publicly via GET /api/v1/site-content and merged into
    # the site's I18N table client-side (see CONTENT_KEYS below and
    # site.js's loadSiteContent()).
    "content_hero_tagline": "شعار زیر عنوان اصلی صفحه اول",
    "content_quotes": "نقل‌قول‌های چرخشی صفحه اول — هر نقل‌قول در یک خط (حداکثر ۶ خط)",
    "content_mansour_bio": "متن معرفی منصور نصیری (صفحه «منصور نصیری») — بخش اول",
    "content_mansour_bio_full": "متن معرفی منصور نصیری — ادامه (بعد از «بیشتر»)",
    "content_about_p1": "متن «درباره خانه ماورا» — پاراگراف اول",
    "content_about_p2": "متن «درباره خانه ماورا» — پاراگراف دوم",
    "content_companion_p1": "متن «همراهی» — پاراگراف اول",
    "content_companion_p2": "متن «همراهی» — پاراگراف دوم",
    "content_footer_tagline": "شعار زیر لوگو در فوتر (می‌تواند شامل <br> برای شکست خط باشد)",
    "content_footer_copyright": "متن کپی‌رایت پایین فوتر",
    "content_contact_telegram": "آیدی تلگرام نمایش‌داده‌شده در صفحه تماس",
    "content_contact_instagram": "آیدی اینستاگرام نمایش‌داده‌شده در صفحه تماس",
    "content_location": "موقعیت مکانی (صفحه تماس و فوتر)",
}

# The subset of EDITABLE_SETTINGS meant for public consumption on the
# website itself (footer, about/companion copy, contact info, quotes) —
# GET /api/v1/site-content in api/server.py serves exactly this list,
# unauthenticated, so every other setting (prices, templates, bank
# cards...) never has to be reasoned about as "is this safe to expose
# to anonymous visitors" key by key.
CONTENT_KEYS = [
    "content_hero_tagline", "content_quotes", "content_mansour_bio", "content_mansour_bio_full",
    "content_about_p1", "content_about_p2", "content_companion_p1", "content_companion_p2",
    "content_footer_tagline", "content_footer_copyright", "content_contact_telegram",
    "content_contact_instagram", "content_location",
]


def get_public_site_content() -> dict:
    return {key: settings_repo.get(key, "") for key in CONTENT_KEYS}


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


_KNOWN_OTP_CHANNELS = ("email", "phone")


def get_otp_channels_enabled() -> list[str]:
    """Comma-separated setting -> list, silently dropping anything that
    isn't a recognized channel name (a typo in the Telegram settings menu
    must never lock every customer out of login, or crash it — see the
    setting's own comment in database/schema.py for why this is a comma
    list and not JSON). Always falls back to ["email"] if the result would
    otherwise be empty, since that's the one channel guaranteed to work."""
    raw = settings_repo.get("otp_channels_enabled", "email")
    channels = [c.strip().lower() for c in raw.split(",") if c.strip().lower() in _KNOWN_OTP_CHANNELS]
    return channels or ["email"]


def update_setting(key: str, value: str) -> None:
    if key not in EDITABLE_SETTINGS:
        raise ValueError(f"Unknown setting key: {key}")
    settings_repo.set(key, value)


def render_email(template_key: str, **values) -> tuple[str, str]:
    """Renders an admin-editable email's subject+body from settings —
    `template_key` is the shared name: e.g. 'otp' reads
    tmpl_email_otp_subject / tmpl_email_otp_body. Was three hardcoded
    Python f-strings (OTP, reservation approved, reservation rejected)
    plus a fourth ad-hoc one (waitlist rejected) before this — now every
    email an admin can see the content of, they can also edit, same as
    the Telegram message templates already were.

    `brand_name` is always available to every email template without
    the caller having to pass it — every one of these reasonably wants
    to say who they're from."""
    values.setdefault("brand_name", get_brand_name())
    subject = render_template(settings_repo.get(f"tmpl_email_{template_key}_subject", ""), **values)
    body = render_template(settings_repo.get(f"tmpl_email_{template_key}_body", ""), **values)
    return subject, body


# ── Website settings page: type + range/length guardrails ──
# The Telegram menu above (update_setting) stays exactly as free-text as
# it always was — deliberately unchanged, so nothing about the existing
# in-bot flow is affected. The website editor is new, so it gets real
# validation from day one: a numeric field can't be saved as "abc" or a
# negative payment-expiry time, and a text field can't be pasted with an
# unbounded wall of text that would blow out a Telegram message or an
# email. Keys not listed in these two maps default to a generic
# short-text field, max 300 characters — safe for anything added to
# EDITABLE_SETTINGS later without updating this file too.
SETTINGS_FIELD_TYPES: dict[str, str] = {
    "brand_name": "text",
    "welcome_message": "textarea",
    "ticket_price": "int",
    "max_tickets_per_person": "int",
    "rules_text": "textarea",
    "support_contact": "text",
    "payment_expiry_minutes": "int",
    "review_reminder_minutes": "int",
    "review_reminder_repeat_minutes": "int",
    "tmpl_payment_instructions": "textarea",
    "tmpl_receipt_received": "textarea",
    "tmpl_ticket_confirmed": "textarea",
    "tmpl_reservation_rejected": "textarea",
    "ticket_template_title": "text",
    "ticket_template_subtitle": "text",
    "ticket_template_footer": "text",
    "otp_channels_enabled": "text",
    "tmpl_email_otp_subject": "text",
    "tmpl_email_otp_body": "textarea",
    "tmpl_email_approved_subject": "text",
    "tmpl_email_approved_body": "textarea",
    "tmpl_email_rejected_subject": "text",
    "tmpl_email_rejected_body": "textarea",
    "tmpl_email_waitlist_rejected_subject": "text",
    "tmpl_email_waitlist_rejected_body": "textarea",
    "content_hero_tagline": "text",
    "content_quotes": "textarea",
    "content_mansour_bio": "textarea",
    "content_mansour_bio_full": "textarea",
    "content_about_p1": "textarea",
    "content_about_p2": "textarea",
    "content_companion_p1": "textarea",
    "content_companion_p2": "textarea",
    "content_footer_tagline": "text",
    "content_footer_copyright": "text",
    "content_contact_telegram": "text",
    "content_contact_instagram": "text",
    "content_location": "text",
}
SETTINGS_INT_RANGE: dict[str, tuple[int, int]] = {
    "ticket_price": (0, 1_000_000_000),
    "max_tickets_per_person": (1, 100),
    "payment_expiry_minutes": (1, 60 * 24 * 7),
    "review_reminder_minutes": (1, 60 * 24 * 7),
    "review_reminder_repeat_minutes": (1, 60 * 24),
}
_MAX_LEN_BY_TYPE = {"text": 300, "textarea": 4000}


def validate_setting_value(key: str, value: str) -> str | None:
    """Returns an error message (Persian, shown as-is to the admin) if
    `value` isn't acceptable for `key`, or None if it's fine to save."""
    if key not in EDITABLE_SETTINGS:
        return "کلید تنظیمات ناشناخته است."
    field_type = SETTINGS_FIELD_TYPES.get(key, "text")
    if field_type == "int":
        try:
            n = int(str(value).strip())
        except ValueError:
            return "این مقدار باید یک عدد صحیح باشد."
        lo, hi = SETTINGS_INT_RANGE.get(key, (0, 10**9))
        if not (lo <= n <= hi):
            return f"مقدار باید بین {lo:,} تا {hi:,} باشد."
        return None
    max_len = _MAX_LEN_BY_TYPE.get(field_type, 300)
    if len(value) > max_len:
        return f"متن نباید بیشتر از {max_len:,} نویسه باشد (الان {len(value):,} نویسه است)."
    return None


def update_setting_validated(key: str, value: str) -> str | None:
    """Website settings page's write path. Returns an error message (and
    does NOT write) if invalid; returns None on success."""
    error = validate_setting_value(key, value)
    if error:
        return error
    settings_repo.set(key, value)
    return None


def get_ticket_template() -> dict:
    """Global PDF ticket template (title/subtitle/footer/logo) — admin-
    editable from pages/admin/ticket-template.html (PATCH
    /api/v1/admin/ticket-template) or, for title/subtitle/footer, from the
    Telegram bot's own settings menu (same EDITABLE_SETTINGS mechanism as
    every other admin-editable text). `logo` is a media/ path set only via
    the website's upload UI (see api/server.py's ticket-template PATCH
    handler) — there's no sane way to type a file path from a Telegram
    settings menu, so it's deliberately not in EDITABLE_SETTINGS above."""
    return {
        "title": settings_repo.get("ticket_template_title", "خانه ماورا"),
        "subtitle": settings_repo.get("ticket_template_subtitle", "بلیت الکترونیک"),
        "footer": settings_repo.get("ticket_template_footer", ""),
        "logo": settings_repo.get("ticket_template_logo", ""),
    }


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
