"""Repository for the `team_members` table — "اعضای خانه ماورا" (team
directory, separate from Mansour Nasiri's own about-page, which stays in
its own static content). Deliberately mirrors database/repositories/
portfolio.py field-by-field (create/update/delete/list_all shape) since
that pattern already proven for "admin-editable public bio content"."""
import json
import re
from database.connection import get_connection

_FIELDS = (
    "slug", "full_name", "full_name_en", "role_title", "role_title_en",
    "photo", "bio_fa", "bio_en", "contact_phone", "contact_telegram",
    "status", "sort_order",
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


def slugify(full_name: str) -> str:
    """Best-effort ASCII-ish slug for Persian names too — falls back to a
    transliteration-free scheme (strip non-alphanumerics, join with '-')
    since a perfect Persian->Latin transliterator isn't worth adding here;
    uniqueness (not prettiness) is what actually matters for a URL id."""
    base = re.sub(r"[^\w\-]+", "-", full_name.strip(), flags=re.UNICODE).strip("-").lower()
    return base or "member"


def list_all(status: str | None = None) -> list[dict]:
    with get_connection() as conn:
        if status:
            rows = conn.execute(
                "SELECT * FROM team_members WHERE status=? ORDER BY sort_order, id", (status,)
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM team_members ORDER BY sort_order, id").fetchall()
        return [_row_to_dict(r) for r in rows]


def get(member_id: int) -> dict | None:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM team_members WHERE id=?", (member_id,)).fetchone()
        return _row_to_dict(row) if row else None


def get_by_slug(slug: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM team_members WHERE slug=?", (slug,)).fetchone()
        return _row_to_dict(row) if row else None


def _unique_slug(conn, base_slug: str, exclude_id: int | None = None) -> str:
    slug = base_slug
    n = 2
    while True:
        q = "SELECT id FROM team_members WHERE slug=?"
        params = [slug]
        if exclude_id is not None:
            q += " AND id != ?"
            params.append(exclude_id)
        if not conn.execute(q, params).fetchone():
            return slug
        slug = f"{base_slug}-{n}"
        n += 1


def create(**fields) -> int:
    data = {k: fields.get(k) for k in _FIELDS}
    data["status"] = fields.get("status") or "active"
    data["sort_order"] = fields.get("sort_order") if fields.get("sort_order") is not None else 0
    gallery = fields.get("gallery")
    gallery_json = json.dumps(gallery, ensure_ascii=False) if gallery else None
    with get_connection() as conn:
        base_slug = slugify(fields.get("slug") or fields.get("full_name", ""))
        data["slug"] = _unique_slug(conn, base_slug)
        cur = conn.execute(
            f"INSERT INTO team_members ({', '.join(_FIELDS)}, gallery) VALUES ({', '.join('?' for _ in _FIELDS)}, ?)",
            (*[data[k] for k in _FIELDS], gallery_json),
        )
        return cur.lastrowid


def update(member_id: int, **fields) -> dict | None:
    updates = {k: v for k, v in fields.items() if k in _FIELDS and k != "slug"}
    with get_connection() as conn:
        if "full_name" in fields and not fields.get("slug"):
            # Renaming doesn't silently break the public URL unless the
            # admin explicitly changes the slug too, but we still keep
            # slug unique if they *do* pass a new one.
            pass
        if fields.get("slug"):
            updates["slug"] = _unique_slug(conn, slugify(fields["slug"]), exclude_id=member_id)
        if "gallery" in fields:
            gallery = fields["gallery"]
            updates["gallery"] = json.dumps(gallery, ensure_ascii=False) if gallery else None
        if not updates:
            row = conn.execute("SELECT * FROM team_members WHERE id=?", (member_id,)).fetchone()
            return _row_to_dict(row) if row else None
        set_parts = [f"{k} = ?" for k in updates]
        values = list(updates.values()) + [member_id]
        conn.execute(f"UPDATE team_members SET {', '.join(set_parts)} WHERE id = ?", values)
        row = conn.execute("SELECT * FROM team_members WHERE id=?", (member_id,)).fetchone()
        return _row_to_dict(row) if row else None


def delete(member_id: int) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM team_members WHERE id = ?", (member_id,))
