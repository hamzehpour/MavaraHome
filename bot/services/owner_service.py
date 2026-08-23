"""Owner-transfer safety: a separate passcode (never the person's real
Telegram password — no bot can access that) gates adding a new owner, and
removing an owner is delayed rather than instant so a mistake or a
compromised session can't silently kick out the real owner."""
from datetime import datetime, timedelta, timezone

from database.repositories import settings as settings_repo
from database.repositories import admins as admins_repo
from utils.secrets_util import hash_passcode, verify_passcode

OWNER_REMOVAL_DELAY_HOURS = 24


def set_passcode(passcode: str) -> None:
    digest, salt = hash_passcode(passcode)
    settings_repo.set("owner_passcode_hash", digest)
    settings_repo.set("owner_passcode_salt", salt)


def is_passcode_set() -> bool:
    return bool(settings_repo.get("owner_passcode_hash", ""))


def check_passcode(passcode: str) -> bool:
    stored_hash = settings_repo.get("owner_passcode_hash", "")
    salt = settings_repo.get("owner_passcode_salt", "")
    return verify_passcode(passcode, stored_hash, salt)


def schedule_owner_removal(telegram_id: int) -> str:
    removal_at = (datetime.now(timezone.utc) + timedelta(hours=OWNER_REMOVAL_DELAY_HOURS)).isoformat(timespec="seconds")
    admins_repo.schedule_owner_removal(telegram_id, removal_at)
    return removal_at


def cancel_owner_removal(telegram_id: int) -> None:
    admins_repo.cancel_owner_removal(telegram_id)


def process_due_removals() -> list[dict]:
    now_iso = datetime.now(timezone.utc).isoformat(timespec="seconds")
    due = admins_repo.list_due_owner_removals(now_iso)
    for row in due:
        admins_repo.remove_admin(row["telegram_id"])
    return due
