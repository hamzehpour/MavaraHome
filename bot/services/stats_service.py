from datetime import date, timedelta

from database.repositories import reservations as reservations_repo
from database.repositories import users as users_repo


def get_dashboard_stats(event_id: int | None = None) -> dict:
    """event_id=None (default) keeps the old global-dashboard behavior.
    Pass a specific event_id to scope every number to just that event —
    needed once more than one event is running so figures don't mix."""
    stats = reservations_repo.sales_stats(event_id=event_id)
    if event_id is None:
        stats["users_count"] = users_repo.count_users()
    return stats


def resolve_range(period: str) -> tuple[str | None, str | None]:
    today = date.today()
    if period == "today":
        return today.isoformat(), today.isoformat()
    if period == "week":
        start = today - timedelta(days=today.weekday())
        return start.isoformat(), today.isoformat()
    if period == "all":
        return None, None
    return None, None  # custom range is handled by the caller directly


def get_range_report(date_from: str | None, date_to: str | None, event_id: int | None = None) -> dict:
    return {
        "totals": reservations_repo.sales_totals(date_from, date_to, event_id=event_id),
        "by_session": reservations_repo.sales_by_session(date_from, date_to, event_id=event_id),
    }


def get_contact_list(date_from: str | None, date_to: str | None, event_id: int | None = None) -> list[dict]:
    return reservations_repo.contact_list_for_range(date_from, date_to, event_id=event_id)
