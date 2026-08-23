"""Schema v9 — customer account login via email OTP.

Rewritten from the original phone+Telegram-delivery flow (see
database/repositories/customer_auth.py's module docstring for the full
reasoning). Flow is now a plain two-step OTP, no linking step:

  1. request_otp(email) -> generates a 6-digit code, stores it hashed,
     emails it via utils.email_sender.send_email(). Returns
     {"delivered": True} on success, {"error": "invalid_email"} if the
     address doesn't look valid.
  2. verify_otp(email, code) -> the customer's `users` row, or None.
"""
import secrets

from database.repositories import customer_auth as customer_auth_repo
from database.repositories import users as users_repo
from utils.email_sender import send_email
from validators.validators import is_valid_email


def request_otp(raw_email: str) -> dict:
    email = raw_email.strip().lower()
    if not is_valid_email(email):
        return {"error": "invalid_email"}

    users_repo.get_or_create_user_by_email(email)
    code = f"{secrets.randbelow(1_000_000):06d}"
    customer_auth_repo.create_otp(email, code)
    send_email(
        to=email,
        subject="کد ورود شما به خانه ماورا",
        body=(
            f"کد ورود شما به سایت خانه ماورا:\n\n{code}\n\n"
            f"این کد تا {customer_auth_repo.OTP_TTL_MINUTES} دقیقه معتبر است. "
            "اگر این درخواست را نداده‌اید، این ایمیل را نادیده بگیرید."
        ),
    )
    return {"delivered": True}


def verify_otp(raw_email: str, code: str) -> dict | None:
    email = raw_email.strip().lower()
    if not customer_auth_repo.verify_otp(email, code):
        return None
    return users_repo.get_or_create_user_by_email(email)
