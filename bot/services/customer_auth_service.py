"""Phase 4 — customer account login.

Flow (no SMS provider in this project — codes are delivered through the
Telegram bot the user already has a relationship with, via bot_outbox):

  1. request_otp(phone)
       - phone belongs to a user who already has a telegram_id linked
         -> generates a code, queues it in bot_outbox, returns
            {"channel": "telegram", "delivered": True}
       - phone has no linked telegram_id yet (new customer, or a
         website-only booking that never connected the bot)
         -> returns {"channel": "link_required", "link_token": ...} so the
            website can send them to pages/connect-telegram.html, which
            deep-links into the bot's /start handler (see
            handlers/common.py) to link phone<->telegram_id once.
  2. verify_otp(phone, code) -> the customer's `users` row, or None.
"""
import secrets

from database.repositories import customer_auth as customer_auth_repo
from database.repositories import bot_outbox as outbox_repo
from database.repositories import users as users_repo
from validators.validators import normalize_phone, is_valid_iranian_mobile


def request_otp(raw_phone: str) -> dict:
    phone = normalize_phone(raw_phone)
    if not is_valid_iranian_mobile(phone):
        return {"error": "invalid_phone"}

    user = users_repo.get_or_create_user_by_phone(phone)
    telegram_id = user.get("telegram_id")

    if telegram_id:
        code = f"{secrets.randbelow(1_000_000):06d}"
        customer_auth_repo.create_otp(phone, code)
        outbox_repo.enqueue(
            telegram_id,
            f"🔐 کد ورود شما به سایت خانه ماورا:\n\n{code}\n\n"
            f"این کد تا {customer_auth_repo.OTP_TTL_MINUTES} دقیقه معتبر است. "
            "اگر این درخواست را نداده‌اید، این پیام را نادیده بگیرید.",
        )
        return {"channel": "telegram", "delivered": True}

    token = customer_auth_repo.create_link_token(phone)
    return {"channel": "link_required", "link_token": token}


def verify_otp(raw_phone: str, code: str) -> dict | None:
    phone = normalize_phone(raw_phone)
    if not customer_auth_repo.verify_otp(phone, code):
        return None
    return users_repo.get_or_create_user_by_phone(phone)


def link_telegram_from_token(token: str, telegram_id: int) -> bool:
    """Called from handlers/common.py's /start handler when a user opens
    a LINK-<token> deep link. Returns True if the link succeeded."""
    phone = customer_auth_repo.consume_link_token(token)
    if not phone:
        return False
    return users_repo.link_telegram_id_by_phone(phone, telegram_id)
