"""Event Reopening Interest ("🔔 منتظر اجرای بعدی") — a small CRM for
audience members of an event that currently has no bookable run.

Not the same feature as waiting_list. See schema.py / event_interests.py
for the distinction. This module owns:
  - registering / editing / cancelling a user's interest
  - the admin-facing audience list + counts
  - the notification fan-out when the event becomes bookable again
"""
from __future__ import annotations

from database.repositories import event_interests as interests_repo
from database.repositories import events as events_repo
from database.repositories import users as users_repo


def is_event_bookable(event: dict) -> bool:
    return bool(event["is_active"])


def register_interest(
    event_id: int, telegram_id: int, contact_name: str, phone_number: str, telegram_username: str | None
) -> tuple[bool, dict | None]:
    """Returns (created, existing_interest). If an active interest already
    exists for this user+event, created=False and the existing row is
    returned so the caller can offer edit/cancel instead of silently
    inserting a duplicate."""
    user = users_repo.get_or_create_user(telegram_id, contact_name)
    existing = interests_repo.get_active_interest(event_id, user["id"])
    if existing:
        return False, existing

    interests_repo.create_interest(
        event_id=event_id,
        user_id=user["id"],
        contact_name=contact_name,
        phone_number=phone_number,
        telegram_user_id=telegram_id,
        telegram_username=telegram_username,
    )
    return True, None


def edit_interest(interest_id: int, contact_name: str, phone_number: str) -> None:
    interests_repo.update_contact(interest_id, contact_name, phone_number)


def cancel_interest(interest_id: int) -> None:
    interests_repo.cancel_interest(interest_id)


def get_my_interest(event_id: int, telegram_id: int) -> dict | None:
    user = users_repo.get_by_telegram_id(telegram_id)
    if not user:
        return None
    return interests_repo.get_active_interest(event_id, user["id"])


def audience_summary(event_id: int) -> dict:
    """Numbers for the admin's event screen: total interested, notified,
    converted to an actual reservation, still needing a phone follow-up."""
    counts = interests_repo.count_by_status(event_id)
    return {
        "active": counts.get("active", 0),
        "notified": counts.get("notified", 0),
        "converted": counts.get("converted_to_reservation", 0),
        "cancelled": counts.get("cancelled", 0),
        "needs_call": counts.get("active", 0) + counts.get("notified", 0) - counts.get("converted_to_reservation", 0),
    }


async def notify_event_reopened(bot, event_id: int) -> dict:
    """Fan-out notification when an event becomes bookable again (is_active
    flips to 1 with at least one bookable session). Call this once per
    reopening event — NOT once per session created, otherwise announcing 5
    sessions at once would spam 5 separate messages to the same person
    (see spec §48). Every send is independent: one blocked/failed user
    never stops the rest. Idempotent in the sense that only currently
    'active' interests are notified — already-notified/cancelled/converted
    rows are skipped, so re-running this after a partial failure only
    reaches the ones still pending.
    """
    event = events_repo.get_event(event_id)
    if not event or not is_event_bookable(event):
        return {"sent": 0, "failed": 0}

    interested = interests_repo.list_active_for_event(event_id)
    sent, failed = 0, 0
    text = (
        f"🔔 خبر خوب!\n\n"
        f"اجرای جدید «{event['title']}» مشخص شد. 🎭\n\n"
        f"ثبت درخواست اطلاع‌رسانی شما با موفقیت انجام شده بود و اکنون امکان رزرو فراهم شده است.\n\n"
        f"اگر مایل هستید، می‌توانید رزرو خود را انجام دهید."
    )
    for interest in interested:
        try:
            await bot.send_message(interest["telegram_user_id"], text)
            interests_repo.mark_notified(interest["id"])
            sent += 1
        except Exception:
            # A blocked bot / deleted account must never stop the rest of
            # the campaign — log and move on to the next person.
            import logging
            logging.getLogger(__name__).warning(
                "reopening-interest notify failed for user_id=%s event_id=%s",
                interest["telegram_user_id"], event_id,
            )
            failed += 1
    return {"sent": sent, "failed": failed}


def mark_converted_if_matching(event_id: int, telegram_id: int, reservation_id: int) -> None:
    """If this user had an active/notified interest for this event and just
    completed a reservation, link the two for conversion-rate reporting.
    Silently does nothing if there was no such interest — most bookings
    never went through this flow at all."""
    user = users_repo.get_by_telegram_id(telegram_id)
    if not user:
        return
    for status in ("active", "notified"):
        rows = [r for r in interests_repo.list_for_event(event_id, status=status) if r["user_id"] == user["id"]]
        for row in rows:
            interests_repo.mark_converted(row["id"], reservation_id)
