from database.connection import get_connection


def increase_capacity_and_reserve_locked(session_id: int, user_id: int, people: int,
                                           unit_price: int, capacity_increase: int,
                                           expires_at: str | None = None) -> dict:
    """
    Used when an admin approves an overflow-capacity request: growing the
    session's capacity and inserting the new reservation happen in ONE
    transaction, so a concurrent booking can't grab the newly freed seats
    before the waitlisted buyer does.
    """
    with get_connection() as conn:
        session = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
        new_capacity = session["capacity"] + capacity_increase
        conn.execute("UPDATE sessions SET capacity = ? WHERE id = ?", (new_capacity, session_id))

        total = people * unit_price
        cur = conn.execute(
            """
            INSERT INTO reservations(
                user_id, session_id, people, unit_price, total_price, status, source, expires_at
            )
            VALUES (?, ?, ?, ?, ?, 'pending_payment', 'telegram', ?)
            """,
            (user_id, session_id, people, unit_price, total, expires_at),
        )
        return {"success": True, "reservation_id": cur.lastrowid, "total_price": total, "new_capacity": new_capacity}


def create_reservation_locked(user_id: int, session_id: int, people: int,
                                unit_price: int, capacity: int,
                                status: str = "pending_payment",
                                source: str = "telegram",
                                created_by_staff: int | None = None,
                                expires_at: str | None = None,
                                attendee_name: str | None = None,
                                attendee_phone: str | None = None) -> dict:
    """
    Capacity check + insert happen inside ONE transaction/connection so two
    users booking at the same moment can't both slip past a nearly-full
    session (the race condition present in the previous version).
    SQLite serializes writers by default, so this connection-scoped
    check-then-insert is safe.
    Returns {"success": bool, "waiting": bool, "reservation_id": int|None, "remaining": int}
    """
    with get_connection() as conn:
        from database.repositories.sessions import reserved_count
        reserved = reserved_count(session_id, conn=conn)
        remaining = capacity - reserved

        if people <= remaining:
            total = people * unit_price
            cur = conn.execute(
                """
                INSERT INTO reservations(
                    user_id, session_id, people, unit_price, total_price,
                    status, source, created_by_staff, expires_at,
                    attendee_name, attendee_phone
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (user_id, session_id, people, unit_price, total,
                 status, source, created_by_staff, expires_at,
                 attendee_name, attendee_phone),
            )
            return {
                "success": True,
                "waiting": False,
                "reservation_id": cur.lastrowid,
                "remaining": remaining - people,
                "total_price": total,
            }

        return {"success": False, "waiting": True, "reservation_id": None, "remaining": remaining}


def get_reservation(reservation_id: int) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM reservations WHERE id = ?", (reservation_id,)
        ).fetchone()
        return dict(row) if row else None


def get_by_code(code: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM reservations WHERE reservation_code = ?", (code,)
        ).fetchone()
        return dict(row) if row else None


def set_checked_in(reservation_id: int) -> bool:
    """Phase 6 door check-in. Returns False if already checked in (so the
    caller can tell 'first scan tonight' from 'this ticket was already
    used') — never overwrites an existing checked_in_at timestamp."""
    with get_connection() as conn:
        row = conn.execute("SELECT checked_in_at FROM reservations WHERE id=?", (reservation_id,)).fetchone()
        if not row:
            return False
        if row["checked_in_at"]:
            return False
        conn.execute(
            "UPDATE reservations SET checked_in_at = datetime('now') WHERE id = ?", (reservation_id,)
        )
        return True


def list_for_user(user_id: int) -> list[dict]:
    """All reservations for one customer, newest first — regardless of
    whether the booking happened via the bot or the website, since both
    write to the same user_id. Used by the authenticated GET
    /api/v1/account/reservations (JWT-identified customer); the old
    unauthenticated ?phone= lookup that used to call this was removed as a
    security finding (phase 0) — anyone who knew a phone number could read
    that person's reservation history."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM reservations WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def list_recent(limit: int = 200) -> list[dict]:
    """Newest reservations across all users/sources — used by the admin
    API endpoint. Deliberately source-agnostic (telegram + website mixed
    in one list) since that's the entire point of Phase 1: one shared view
    regardless of which channel a booking came from.

    Joins users + sessions + events so the admin list has everything it
    actually needs (buyer name/phone, session date/time, event title) in
    one call — the bare `reservations` row alone only has attendee_name/
    attendee_phone, which are null for the common case (buyer booking for
    themselves, not on someone else's behalf)."""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT r.*, u.full_name AS buyer_name, u.phone AS buyer_phone,
                   s.session_date, s.session_time, e.title AS event_title, e.id AS event_id
            FROM reservations r
            JOIN users u ON u.id = r.user_id
            JOIN sessions s ON s.id = r.session_id
            JOIN events e ON e.id = s.event_id
            ORDER BY r.created_at DESC LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]


def set_status_if(reservation_id: int, expected_status: str, new_status: str,
                   admin_note: str | None = None) -> bool:
    """
    Atomic conditional transition: only changes status if it still matches
    `expected_status` at the moment of the UPDATE — this is the real fix
    for double-tap/duplicate-callback idempotency (a plain read-then-write
    check, even a fast one, still has a race window; this doesn't, because
    the check and the write are the same SQL statement).
    Returns True if the transition actually happened.
    """
    with get_connection() as conn:
        cur = conn.execute(
            """
            UPDATE reservations
            SET status = ?, admin_note = COALESCE(?, admin_note), updated_at = datetime('now')
            WHERE id = ? AND status = ?
            """,
            (new_status, admin_note, reservation_id, expected_status),
        )
        return cur.rowcount > 0


def set_status(reservation_id: int, status: str, admin_note: str | None = None) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE reservations
            SET status = ?, admin_note = COALESCE(?, admin_note), updated_at = datetime('now')
            WHERE id = ?
            """,
            (status, admin_note, reservation_id),
        )


def set_reservation_code(reservation_id: int, code: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE reservations SET reservation_code = ? WHERE id = ?",
            (code, reservation_id),
        )


def list_pending_review() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT r.*, u.full_name AS user_full_name, u.phone AS user_phone,
                   u.telegram_id AS user_telegram_id
            FROM reservations r
            JOIN users u ON u.id = r.user_id
            WHERE r.status = 'pending_review'
            ORDER BY r.created_at
            """
        ).fetchall()
        return [dict(r) for r in rows]


def list_for_session(session_id: int, statuses: tuple[str, ...] = ()) -> list[dict]:
    with get_connection() as conn:
        if statuses:
            placeholders = ",".join("?" * len(statuses))
            rows = conn.execute(
                f"SELECT * FROM reservations WHERE session_id = ? AND status IN ({placeholders})",
                (session_id, *statuses),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM reservations WHERE session_id = ?", (session_id,)
            ).fetchall()
        return [dict(r) for r in rows]


def update_people_and_price_locked(reservation_id: int, new_people: int) -> dict:
    """
    Capacity check + write happen inside ONE connection/transaction — same
    pattern as create_reservation_locked. Doing the check in one call and
    the write in another (the previous version) is a real race: another
    admin action or a new customer reservation could land in between and
    the write would proceed against stale capacity numbers.
    """
    with get_connection() as conn:
        reservation = conn.execute("SELECT * FROM reservations WHERE id = ?", (reservation_id,)).fetchone()
        session = conn.execute("SELECT * FROM sessions WHERE id = ?", (reservation["session_id"],)).fetchone()
        reserved = conn.execute(
            """
            SELECT COALESCE(SUM(people), 0) c FROM reservations
            WHERE session_id = ? AND status IN
                ('pending_payment', 'pending_review', 'awaiting_buyer_confirmation', 'approved')
            """,
            (session["id"],),
        ).fetchone()["c"]

        remaining_excl_self = session["capacity"] - (reserved - reservation["people"])
        if new_people > remaining_excl_self:
            return {"success": False, "remaining": remaining_excl_self}

        total = reservation["unit_price"] * new_people
        conn.execute(
            "UPDATE reservations SET people = ?, total_price = ?, updated_at = datetime('now') WHERE id = ?",
            (new_people, total, reservation_id),
        )
        return {"success": True, "total_price": total}


def move_to_session_locked(reservation_id: int, new_session_id: int) -> dict:
    """Same atomicity fix as above, for moving a reservation to another session."""
    with get_connection() as conn:
        reservation = conn.execute("SELECT * FROM reservations WHERE id = ?", (reservation_id,)).fetchone()
        new_session = conn.execute("SELECT * FROM sessions WHERE id = ?", (new_session_id,)).fetchone()
        if not new_session:
            return {"success": False, "error": "session_not_found"}

        reserved = conn.execute(
            """
            SELECT COALESCE(SUM(people), 0) c FROM reservations
            WHERE session_id = ? AND status IN
                ('pending_payment', 'pending_review', 'awaiting_buyer_confirmation', 'approved')
            """,
            (new_session_id,),
        ).fetchone()["c"]

        remaining = new_session["capacity"] - reserved
        if reservation["people"] > remaining:
            return {"success": False, "remaining": remaining}

        conn.execute(
            "UPDATE reservations SET session_id = ?, updated_at = datetime('now') WHERE id = ?",
            (new_session_id, reservation_id),
        )
        return {"success": True}


def update_people_and_price(reservation_id: int, people: int, total_price: int) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE reservations SET people = ?, total_price = ?, updated_at = datetime('now') WHERE id = ?",
            (people, total_price, reservation_id),
        )


def move_to_session(reservation_id: int, new_session_id: int) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE reservations SET session_id = ?, updated_at = datetime('now') WHERE id = ?",
            (new_session_id, reservation_id),
        )


def list_expired_pending(now_iso: str) -> list[dict]:
    """Reservations still waiting for payment whose deadline has passed."""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT * FROM reservations
            WHERE status = 'pending_payment' AND expires_at IS NOT NULL AND expires_at < ?
            """,
            (now_iso,),
        ).fetchall()
        return [dict(r) for r in rows]


def telegram_ids_seen_show(before_date_iso: str) -> list[int]:
    """Buyers with an approved reservation for a session that already happened."""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT DISTINCT u.telegram_id FROM reservations r
            JOIN users u ON u.id = r.user_id
            JOIN sessions s ON s.id = r.session_id
            WHERE r.status = 'approved' AND s.session_date < ? AND u.telegram_id IS NOT NULL
            """,
            (before_date_iso,),
        ).fetchall()
        return [r["telegram_id"] for r in rows]


def telegram_ids_not_seen_show(from_date_iso: str) -> list[int]:
    """Buyers with an approved reservation for a session still upcoming."""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT DISTINCT u.telegram_id FROM reservations r
            JOIN users u ON u.id = r.user_id
            JOIN sessions s ON s.id = r.session_id
            WHERE r.status = 'approved' AND s.session_date >= ? AND u.telegram_id IS NOT NULL
            """,
            (from_date_iso,),
        ).fetchall()
        return [r["telegram_id"] for r in rows]


def telegram_ids_for_session(session_id: int) -> list[int]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT DISTINCT u.telegram_id FROM reservations r
            JOIN users u ON u.id = r.user_id
            WHERE r.session_id = ?
              AND r.status IN ('pending_payment', 'pending_review', 'awaiting_buyer_confirmation', 'approved')
              AND u.telegram_id IS NOT NULL
            """,
            (session_id,),
        ).fetchall()
        return [r["telegram_id"] for r in rows]


def telegram_ids_for_date(event_id: int, date_iso: str) -> list[int]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT DISTINCT u.telegram_id FROM reservations r
            JOIN users u ON u.id = r.user_id
            JOIN sessions s ON s.id = r.session_id
            WHERE s.event_id = ? AND s.session_date = ?
              AND r.status IN ('pending_payment', 'pending_review', 'awaiting_buyer_confirmation', 'approved')
              AND u.telegram_id IS NOT NULL
            """,
            (event_id, date_iso),
        ).fetchall()
        return [r["telegram_id"] for r in rows]


def sales_totals(date_from: str | None = None, date_to: str | None = None, event_id: int | None = None) -> dict:
    query = (
        "SELECT COUNT(*) c, COALESCE(SUM(r.total_price),0) revenue, COALESCE(SUM(r.people),0) tickets "
        "FROM reservations r JOIN sessions s ON s.id = r.session_id "
        "WHERE r.status = 'approved'"
    )
    params: list = []
    if date_from:
        query += " AND s.session_date >= ?"; params.append(date_from)
    if date_to:
        query += " AND s.session_date <= ?"; params.append(date_to)
    if event_id is not None:
        query += " AND s.event_id = ?"; params.append(event_id)
    with get_connection() as conn:
        row = conn.execute(query, params).fetchone()
        return {"count": row["c"], "revenue": row["revenue"], "tickets": row["tickets"]}


def sales_by_session(date_from: str | None = None, date_to: str | None = None, event_id: int | None = None) -> list[dict]:
    query = (
        "SELECT s.id AS session_id, s.session_date, s.session_time, e.title AS event_title, "
        "COUNT(r.id) c, COALESCE(SUM(r.total_price),0) revenue, COALESCE(SUM(r.people),0) tickets "
        "FROM reservations r "
        "JOIN sessions s ON s.id = r.session_id "
        "JOIN events e ON e.id = s.event_id "
        "WHERE r.status = 'approved'"
    )
    params: list = []
    if date_from:
        query += " AND s.session_date >= ?"; params.append(date_from)
    if date_to:
        query += " AND s.session_date <= ?"; params.append(date_to)
    if event_id is not None:
        query += " AND s.event_id = ?"; params.append(event_id)
    query += " GROUP BY s.id ORDER BY s.session_date, s.session_time"
    with get_connection() as conn:
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]


def contact_list_for_range(date_from: str | None = None, date_to: str | None = None, event_id: int | None = None) -> list[dict]:
    query = (
        "SELECT u.full_name, u.phone, r.attendee_name, r.attendee_phone, r.people, "
        "s.session_date, s.session_time "
        "FROM reservations r "
        "JOIN users u ON u.id = r.user_id "
        "JOIN sessions s ON s.id = r.session_id "
        "WHERE r.status = 'approved'"
    )
    params: list = []
    if date_from:
        query += " AND s.session_date >= ?"; params.append(date_from)
    if date_to:
        query += " AND s.session_date <= ?"; params.append(date_to)
    if event_id is not None:
        query += " AND s.event_id = ?"; params.append(event_id)
    query += " ORDER BY s.session_date, s.session_time"
    with get_connection() as conn:
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]


def sales_stats(event_id: int | None = None) -> dict:
    join_clause = " JOIN sessions s ON s.id = reservations.session_id" if event_id is not None else ""
    event_filter = " AND s.event_id = ?" if event_id is not None else ""
    params = [event_id] if event_id is not None else []
    with get_connection() as conn:
        approved = conn.execute(
            f"SELECT COUNT(*) c, COALESCE(SUM(reservations.total_price),0) revenue, "
            f"COALESCE(SUM(reservations.people),0) tickets "
            f"FROM reservations{join_clause} WHERE reservations.status = 'approved'{event_filter}",
            params,
        ).fetchone()
        pending = conn.execute(
            f"SELECT COUNT(*) c FROM reservations{join_clause} WHERE reservations.status = 'pending_review'{event_filter}",
            params,
        ).fetchone()
        rejected = conn.execute(
            f"SELECT COUNT(*) c FROM reservations{join_clause} WHERE reservations.status = 'rejected'{event_filter}",
            params,
        ).fetchone()
        return {
            "approved_count": approved["c"],
            "revenue": approved["revenue"],
            "tickets_sold": approved["tickets"],
            "pending_review_count": pending["c"],
            "rejected_count": rejected["c"],
        }


def list_holders_for_session(session_id: int) -> list[dict]:
    """Everyone holding an active seat on this session — used when an admin
    edits/deactivates a session and needs to know who to contact."""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT r.id, r.people, r.status, r.reservation_code,
                   r.attendee_name, r.attendee_phone,
                   u.full_name, u.phone
            FROM reservations r
            JOIN users u ON u.id = r.user_id
            WHERE r.session_id = ?
              AND r.status IN ('pending_payment', 'pending_review', 'awaiting_buyer_confirmation', 'approved')
            ORDER BY r.created_at
            """,
            (session_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def list_all(limit: int = 500) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT r.*, u.full_name AS user_full_name, u.phone AS user_phone,
                   s.session_date, s.session_time
            FROM reservations r
            JOIN users u ON u.id = r.user_id
            JOIN sessions s ON s.id = r.session_id
            ORDER BY r.created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]
