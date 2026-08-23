"""Repository for the `portfolio` table — Mansour's resume/CV entries.
Unrelated to reservations; kept on the same shared backend/database
instead of a third separate data store (see schema.py comment)."""
import json
from database.connection import get_connection

_FIELDS = (
    "title_fa", "title_en", "year", "category", "director", "director_en",
    "role", "role_en", "festival", "festival_en", "poster", "video",
    "desc_fa", "desc_en", "status", "sort_order",
)


def _row_to_dict(row: dict) -> dict:
    d = dict(row)
    if d.get("gallery"):
        try:
            d["gallery"] = json.loads(d["gallery"])
        except (json.JSONDecodeError, TypeError):
            d["gallery"] = []
    else:
        d["gallery"] = []
    return d


def list_all() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM portfolio ORDER BY sort_order, year DESC, id"
        ).fetchall()
        return [_row_to_dict(r) for r in rows]


def get(item_id: int) -> dict | None:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM portfolio WHERE id = ?", (item_id,)).fetchone()
        return _row_to_dict(row) if row else None


def create(**fields) -> int:
    data = {k: fields.get(k) for k in _FIELDS}
    if "status" not in fields or not fields.get("status"):
        data["status"] = "active"
    if "sort_order" not in fields or fields.get("sort_order") is None:
        data["sort_order"] = 0
    gallery = fields.get("gallery")
    gallery_json = json.dumps(gallery, ensure_ascii=False) if gallery else None
    with get_connection() as conn:
        cur = conn.execute(
            f"INSERT INTO portfolio ({', '.join(_FIELDS)}, gallery) VALUES ({', '.join('?' for _ in _FIELDS)}, ?)",
            (*[data[k] for k in _FIELDS], gallery_json),
        )
        return cur.lastrowid


def update(item_id: int, **fields) -> dict | None:
    updates = {k: v for k, v in fields.items() if k in _FIELDS}
    if "gallery" in fields:
        gallery = fields["gallery"]
        updates_gallery = json.dumps(gallery, ensure_ascii=False) if gallery else None
    else:
        updates_gallery = None
    if not updates and "gallery" not in fields:
        return get(item_id)
    set_parts = [f"{k} = ?" for k in updates]
    values = list(updates.values())
    if "gallery" in fields:
        set_parts.append("gallery = ?")
        values.append(updates_gallery)
    values.append(item_id)
    with get_connection() as conn:
        conn.execute(f"UPDATE portfolio SET {', '.join(set_parts)} WHERE id = ?", values)
        row = conn.execute("SELECT * FROM portfolio WHERE id = ?", (item_id,)).fetchone()
        return _row_to_dict(row) if row else None


def delete(item_id: int) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM portfolio WHERE id = ?", (item_id,))


def count() -> int:
    with get_connection() as conn:
        return conn.execute("SELECT COUNT(*) c FROM portfolio").fetchone()["c"]
