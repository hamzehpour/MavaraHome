"""Pure, framework-independent input validation. No Telegram, no DB, no text."""
import re

_NAME_RE = re.compile(r"^[a-zA-Zآ-ی\u200c\s]{3,50}$")


def is_valid_full_name(name: str) -> bool:
    return bool(_NAME_RE.match(name.strip()))


_PERSIAN_TO_EN = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")
_ARABIC_TO_EN = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")


def normalize_phone(raw: str) -> str:
    phone = raw.translate(_PERSIAN_TO_EN).translate(_ARABIC_TO_EN)
    phone = phone.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    if phone.startswith("+98"):
        phone = "0" + phone[3:]
    elif phone.startswith("0098"):
        phone = "0" + phone[4:]
    elif phone.startswith("98") and len(phone) == 12:
        phone = "0" + phone[2:]
    return phone


def is_valid_iranian_mobile(phone: str) -> bool:
    return phone.isdigit() and phone.startswith("09") and len(phone) == 11


# Deliberately simple (not the full RFC 5322 grammar) — good enough to
# reject typos before an OTP email gets sent, not meant to be a strict
# mailbox-existence check (only actually receiving the email proves that).
_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def is_valid_email(raw: str) -> bool:
    return bool(_EMAIL_RE.match(raw.strip()))


def normalize_digits(raw: str) -> str:
    return raw.translate(_PERSIAN_TO_EN).translate(_ARABIC_TO_EN)


_TIME_RE = re.compile(r"^([01]?\d|2[0-3]):[0-5]\d$")


def is_valid_time_hhmm(raw: str) -> bool:
    return bool(_TIME_RE.match(raw.strip()))


def is_positive_int(raw: str) -> bool:
    return raw.strip().isdigit() and int(raw.strip()) > 0
