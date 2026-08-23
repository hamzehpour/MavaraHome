from database.connection import get_connection


def list_active_events() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM events WHERE is_active = 1 ORDER BY id"
        ).fetchall()
        return [dict(r) for r in rows]


def list_all_events() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM events ORDER BY id DESC").fetchall()
        return [dict(r) for r in rows]


def get_event(event_id: int) -> dict | None:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
        return dict(row) if row else None


def create_event(title: str, description: str = "", icon: str = "🎭", calendar_type: str = "jalali",
                  address: str = "", ticket_price: int | None = None, currency: str = "تومان",
                  is_active: bool = True) -> int:
    with get_connection() as conn:
        cur = conn.execute(
            """
            INSERT INTO events(title, description, icon, calendar_type, address, ticket_price, currency, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (title, description, icon, calendar_type, address, ticket_price, currency, int(is_active)),
        )
        return cur.lastrowid


def set_calendar_type(event_id: int, calendar_type: str) -> None:
    with get_connection() as conn:
        conn.execute("UPDATE events SET calendar_type = ? WHERE id = ?", (calendar_type, event_id))


def set_event_active(event_id: int, is_active: bool) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE events SET is_active = ? WHERE id = ?", (int(is_active), event_id)
        )


def update_address(event_id: int, address: str) -> None:
    with get_connection() as conn:
        conn.execute("UPDATE events SET address = ? WHERE id = ?", (address, event_id))


# Fields the website's richer event model needs (Phase 1 unification) that
# the bot didn't originally have. A single generic updater rather than one
# setter per field, since the admin UI edits these together as one form.
_UPDATABLE_WEBSITE_FIELDS = (
    "title", "title_en", "description", "description_en", "location", "location_en",
    "poster", "gallery", "video", "contact_phone", "contact_telegram",
    "ticket_price", "currency", "address",
    # Per-event ticket template additions: important_notes (free text, one
    # consideration per line, auto-printed on every ticket for this event
    # — see utils/ticket_pdf.py) and ticket_logo (optional header image
    # override, falls back to the global ticket_template_logo setting).
    "important_notes", "ticket_logo",
)


def update_event_fields(event_id: int, **fields) -> dict | None:
    """Updates only the given fields (whitelisted against
    _UPDATABLE_WEBSITE_FIELDS so a caller can never write to an arbitrary
    column). `gallery`, if given, must already be a JSON string — callers
    that have a Python list should json.dumps() it first."""
    updates = {k: v for k, v in fields.items() if k in _UPDATABLE_WEBSITE_FIELDS}
    if not updates:
        return get_event(event_id)
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    with get_connection() as conn:
        conn.execute(f"UPDATE events SET {set_clause} WHERE id = ?", (*updates.values(), event_id))
        row = conn.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
        return dict(row) if row else None


def delete_event(event_id: int) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM events WHERE id = ?", (event_id,))
