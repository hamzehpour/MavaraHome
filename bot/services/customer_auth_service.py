"""Schema v9 — customer account login via OTP, currently email only.

Rewritten from the original phone+Telegram-delivery flow (see
database/repositories/customer_auth.py's module docstring for the full
reasoning). Flow is a plain two-step OTP, no linking step:

  1. request_otp(identifier, channel) -> generates a 6-digit code, stores
     it hashed, delivers it. Returns {"delivered": True} on success, or
     an {"error": ...} the API layer turns into a 400/403.
  2. verify_otp(identifier, code, channel) -> the customer's `users` row,
     or None.

Schema v12 (reservation-migration phase 2) added `channel` as a product
decision: admin picks which login methods are offered, customer picks
between them if more than one is enabled (see settings_service.
get_otp_channels_enabled() / DEFAULT_SETTINGS["otp_channels_enabled"]).
`channel="phone"` is accepted by both functions below — the plumbing is
there — but always returns channel_not_supported, on purpose: this
project has no SMS provider, and pretending otherwise would silently
strand a customer who never receives a code. Wiring in a real one later
means implementing the `channel == "phone"` branch here; nothing else
about this file's shape needs to change.
"""
import secrets

from database.repositories import customer_auth as customer_auth_repo
from database.repositories import users as users_repo
from services import settings_service
from utils.email_sender import send_email
from validators.validators import is_valid_email


def request_otp(raw_identifier: str, channel: str = "email") -> dict:
    channel = channel.strip().lower()
    # Checked before the admin-enabled list on purpose: "phone" being
    # unsupported is a fact about this codebase (no SMS provider wired
    # in), not a toggle — an admin enabling it in settings wouldn't make
    # it start working, so it must never report the more-hopeful
    # "channel_disabled" (which implies flipping a setting is all it'd
    # take).
    if channel == "phone":
        return {"error": "channel_not_supported"}
    if channel != "email":
        return {"error": "invalid_channel"}
    if channel not in settings_service.get_otp_channels_enabled():
        return {"error": "channel_disabled"}

    email = raw_identifier.strip().lower()
    if not is_valid_email(email):
        return {"error": "invalid_email"}

    users_repo.get_or_create_customer(email=email)
    code = f"{secrets.randbelow(1_000_000):06d}"
    customer_auth_repo.create_otp(email, code, channel="email")
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


def verify_otp(raw_identifier: str, code: str, channel: str = "email") -> dict | None:
    channel = channel.strip().lower()
    if channel != "email":
        return None  # phone: no code was ever actually sent, nothing to verify

    email = raw_identifier.strip().lower()
    if not customer_auth_repo.verify_otp(email, code):
        return None
    return users_repo.get_or_create_customer(email=email)
