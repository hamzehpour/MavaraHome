"""Repository for the FAQ bank (`faqs`) and its per-event attachment
(`event_faqs`) — see schema.py's schema-v16 comment for the reasoning
behind the two-table shape. Every bank item is bilingual (question/
question_en, answer/answer_en), matching the fa/en pairing already used
for every other admin-editable content field in this project."""
from database.connection import get_connection

_FIELDS = ("question", "question_en", "answer", "answer_en")


def list_all() -> list[dict]:
    """The whole bank, newest first — used by the standalone bank-
    management page and by the "add existing question" picker inside an
    event's edit form. `usage_count` (how many events currently have this
    item attached) lets the bank page warn before deleting something
    that's still in use, and isn't a real column — computed via a
    correlated subquery rather than a JOIN+GROUP BY so a bank item with
    zero attachments still comes back as one row (0), not dropped."""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT f.*, (
                SELECT COUNT(*) FROM event_faqs ef WHERE ef.faq_id = f.id
            ) AS usage_count
            FROM faqs f
            ORDER BY f.created_at DESC, f.id DESC
            """
        ).fetchall()
        return [dict(r) for r in rows]


def get(faq_id: int) -> dict | None:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM faqs WHERE id = ?", (faq_id,)).fetchone()
        return dict(row) if row else None


def create(question: str, answer: str, question_en: str | None = None, answer_en: str | None = None) -> int:
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO faqs(question, question_en, answer, answer_en) VALUES (?, ?, ?, ?)",
            (question, question_en, answer, answer_en),
        )
        return cur.lastrowid


def update(faq_id: int, **fields) -> dict | None:
    updates = {k: v for k, v in fields.items() if k in _FIELDS}
    if not updates:
        return get(faq_id)
    set_parts = [f"{k} = ?" for k in updates] + ["updated_at = datetime('now')"]
    with get_connection() as conn:
        conn.execute(f"UPDATE faqs SET {', '.join(set_parts)} WHERE id = ?", (*updates.values(), faq_id))
    # get() opens its OWN connection (see database/connection.py) — must
    # run after the `with` block above has actually committed, not inside
    # it, or it can read the pre-update row back (found by this feature's
    # own test suite: a plain `return get(faq_id)` inside the `with`
    # returned the OLD `answer` every time).
    return get(faq_id)


def delete(faq_id: int) -> None:
    """Removes the bank item — `event_faqs` rows referencing it cascade
    automatically (ON DELETE CASCADE), so it also disappears from every
    event it was attached to. Callers (the admin API) show `usage_count`
    up front specifically so this isn't a surprise."""
    with get_connection() as conn:
        conn.execute("DELETE FROM faqs WHERE id = ?", (faq_id,))


def list_for_event(event_id: int) -> list[dict]:
    """This event's FAQs, in the admin's chosen display order — the shape
    consumed directly by the public API (embedded on every event object,
    see api/server.py's _event_public()) and by the admin edit form's
    prefill (same field, no separate admin-only fetch needed)."""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT f.id, f.question, f.question_en, f.answer, f.answer_en
            FROM event_faqs ef JOIN faqs f ON f.id = ef.faq_id
            WHERE ef.event_id = ?
            ORDER BY ef.sort_order, ef.id
            """,
            (event_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def set_event_faqs(event_id: int, faq_ids: list[int]) -> None:
    """Replaces this event's whole FAQ list/order in one call — the same
    "send the whole array back, replace it all" convention already used
    for `events.gallery`/`events.tags` (see events_repo.update_event_fields),
    which is simpler and less error-prone than incremental add/remove/
    reorder endpoints for a list an admin form always edits as a unit.
    Silently drops any id that isn't a real faqs row (e.g. a stale id from
    a bank item deleted in another tab) rather than raising, since a
    half-saved event form is worse than one missing question."""
    with get_connection() as conn:
        conn.execute("DELETE FROM event_faqs WHERE event_id = ?", (event_id,))
        for order, faq_id in enumerate(dict.fromkeys(faq_ids)):  # de-dupe, keep first occurrence's position
            conn.execute(
                "INSERT INTO event_faqs(event_id, faq_id, sort_order) "
                "SELECT ?, id, ? FROM faqs WHERE id = ?",
                (event_id, order, faq_id),
            )
