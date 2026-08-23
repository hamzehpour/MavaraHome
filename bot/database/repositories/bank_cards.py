from database.connection import get_connection

MAX_CARDS = 10


def list_cards() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM bank_cards ORDER BY id").fetchall()
        return [dict(r) for r in rows]


def count_cards() -> int:
    with get_connection() as conn:
        return conn.execute("SELECT COUNT(*) c FROM bank_cards").fetchone()["c"]


def get_active_card() -> dict | None:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM bank_cards WHERE is_active = 1 LIMIT 1").fetchone()
        return dict(row) if row else None


def add_card(card_number: str, card_holder: str, bank_name: str) -> int | None:
    if count_cards() >= MAX_CARDS:
        return None
    with get_connection() as conn:
        make_active = conn.execute("SELECT COUNT(*) c FROM bank_cards WHERE is_active = 1").fetchone()["c"] == 0
        cur = conn.execute(
            "INSERT INTO bank_cards(card_number, card_holder, bank_name, is_active) VALUES (?, ?, ?, ?)",
            (card_number, card_holder, bank_name, int(make_active)),
        )
        return cur.lastrowid


def set_active(card_id: int) -> None:
    with get_connection() as conn:
        conn.execute("UPDATE bank_cards SET is_active = 0")
        conn.execute("UPDATE bank_cards SET is_active = 1 WHERE id = ?", (card_id,))


def delete_card(card_id: int) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM bank_cards WHERE id = ?", (card_id,))
        # If we just deleted the active card, promote the next one so
        # payment instructions never go out with a blank card number.
        still_active = conn.execute("SELECT COUNT(*) c FROM bank_cards WHERE is_active = 1").fetchone()["c"]
        if still_active == 0:
            next_row = conn.execute("SELECT id FROM bank_cards ORDER BY id LIMIT 1").fetchone()
            if next_row:
                conn.execute("UPDATE bank_cards SET is_active = 1 WHERE id = ?", (next_row["id"],))


def rotate_to_next() -> dict | None:
    """Used by the weekly auto-rotation job — activates the next card in
    id order, wrapping around to the first after the last."""
    cards = list_cards()
    if len(cards) < 2:
        return None
    active_idx = next((i for i, c in enumerate(cards) if c["is_active"]), 0)
    next_card = cards[(active_idx + 1) % len(cards)]
    set_active(next_card["id"])
    return next_card
