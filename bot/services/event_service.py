from database.repositories import events as events_repo
from database.repositories import sessions as sessions_repo


def get_active_events() -> list[dict]:
    return events_repo.list_active_events()


def get_bookable_dates(event_id: int) -> list[dict]:
    """Every active session for ONE event, used to build the date picker."""
    return sessions_repo.list_sessions_for_event(event_id)


def get_sessions_on_date(event_id: int, date_str: str) -> list[dict]:
    return [s for s in get_bookable_dates(event_id) if s["session_date"] == date_str]


def get_available_seats(session: dict) -> int:
    reserved = sessions_repo.reserved_count(session["id"])
    return max(session["capacity"] - reserved, 0)


def get_effective_price(event: dict) -> tuple[int, str]:
    """Per-event ticket price/currency if the admin set one at creation,
    otherwise falls back to the global default price (always تومان)."""
    from services import settings_service
    if event.get("ticket_price"):
        return event["ticket_price"], event.get("currency") or "تومان"
    return settings_service.get_ticket_price(), "تومان"


def get_capacity_overview(event_id: int) -> list[dict]:
    """Per-session reserved/remaining breakdown — used by the staff capacity view."""
    overview = []
    for s in sessions_repo.list_sessions_for_event(event_id):
        reserved = sessions_repo.reserved_count(s["id"])
        overview.append({
            **s,
            "reserved": reserved,
            "remaining": max(s["capacity"] - reserved, 0),
        })
    return overview
