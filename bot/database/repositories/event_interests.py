"""Repository for event_reopening_interests — the "🔔 منتظر اجرای بعدی"
audience list. Deliberately separate from waiting_list (see schema.py
comment): this is "notify me when this event has ANY bookable run again",
not "I want into this specific full session".
"""
from database.connection import get_connection


def get_active_interest(event_id: int, user_id: int) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM event_reopening_interests WHERE event_id = ? AND user_id = ? AND status = 'active'",
            (event_id, user_id),
        ).fetchone()
        return dict(row) if row else None


def create_interest(
    event_id: int,
    user_id: int,
    contact_name: str,
    phone_number: str,
    telegram_user_id: int,
    telegram_username: str | None,
) -> int:
    """Caller must check get_active_interest() first to avoid a duplicate —
    the unique partial index (uq_reopening_interest_active) is the hard
    backstop against a race, but the friendly "already registered" message
    should come from the application-level check."""
    with get_connection() as conn:
        cur = conn.execute(
            """
            INSERT INTO event_reopening_interests
                (event_id, user_id, contact_name, phone_number, telegram_user_id, telegram_username)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (event_id, user_id, contact_name, phone_number, telegram_user_id, telegram_username),
        )
        return cur.lastrowid


def update_contact(interest_id: int, contact_name: str, phone_number: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE event_reopening_interests SET contact_name = ?, phone_number = ?, "
            "updated_at = datetime('now') WHERE id = ?",
            (contact_name, phone_number, interest_id),
        )


def cancel_interest(interest_id: int) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE event_reopening_interests SET status = 'cancelled', updated_at = datetime('now') WHERE id = ?",
            (interest_id,),
        )


def list_active_for_event(event_id: int) -> list[dict]:
    """Everyone eligible for the next reopening notification for this
    event — used both by admin (to see the audience) and by the
    notification service (to know who to message)."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM event_reopening_interests WHERE event_id = ? AND status = 'active' ORDER BY created_at",
            (event_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def list_for_event(event_id: int, status: str | None = None) -> list[dict]:
    """Admin listing — optionally filtered by status (active / notified /
    cancelled / converted_to_reservation)."""
    with get_connection() as conn:
        if status:
            rows = conn.execute(
                "SELECT * FROM event_reopening_interests WHERE event_id = ? AND status = ? ORDER BY created_at DESC",
                (event_id, status),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM event_reopening_interests WHERE event_id = ? ORDER BY created_at DESC",
                (event_id,),
            ).fetchall()
        return [dict(r) for r in rows]


def mark_notified(interest_id: int) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE event_reopening_interests SET status = 'notified', notified_at = datetime('now'), "
            "updated_at = datetime('now') WHERE id = ?",
            (interest_id,),
        )


def mark_converted(interest_id: int, reservation_id: int) -> None:
    """Interest → actual reservation. Kept for conversion-rate reporting;
    the row is never deleted."""
    with get_connection() as conn:
        conn.execute(
            "UPDATE event_reopening_interests SET status = 'converted_to_reservation', "
            "converted_reservation_id = ?, updated_at = datetime('now') WHERE id = ?",
            (reservation_id, interest_id),
        )


def count_by_status(event_id: int) -> dict:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT status, COUNT(*) c FROM event_reopening_interests WHERE event_id = ? GROUP BY status",
            (event_id,),
        ).fetchall()
        return {r["status"]: r["c"] for r in rows}
