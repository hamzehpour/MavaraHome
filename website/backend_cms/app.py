"""
Mavara Home — website CMS backend (split architecture).

WHY THIS EXISTS: the original unified backend (bot/api/server.py) mixed
public-content management (events/portfolio/team) with the whole
reservation platform (sessions, payments, tickets, customer accounts,
messaging) in one process, sharing one database with the Telegram bot.
That meant the website could only be hosted anywhere the bot could be —
a persistent Python process with SSH/systemd access, which is exactly
what an ordinary shared-hosting cPanel/DirectAdmin plan (Python App /
Passenger, no SSH) can't run.

This file is the whole website's real backend now: a plain, synchronous
Flask (WSGI) app that manages ONLY public content (events, resume,
team members) and its own tiny admin login — nothing reservation-shaped
lives here at all. That's what makes it deployable on ordinary shared
hosting: request in, response out, no persistent background process,
no async, its own small SQLite database (db.py) that has nothing to do
with the bot's.

Booking still exists — it just isn't this app's job. See site.js's
event-detail rendering: a "book via Telegram/phone" button built from
the event's own contact_phone/contact_telegram fields, exactly like
this site's original (pre-reservation-platform) design.

Run locally:  FLASK_APP=app.py flask run --port 8790
Deploy: see DEPLOYMENT.md (cPanel "Setup Python App" / DirectAdmin
Python app, using passenger_wsgi.py as the entrypoint).
"""
from __future__ import annotations

import base64
import json
import os
import re
import time

from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Explicit path (not just load_dotenv()) — Passenger/WSGI servers don't
# reliably start with this directory as the working directory, so a
# bare load_dotenv() can silently find nothing. Must run before
# importing auth.py, which reads JWT_SECRET at import time.
load_dotenv(os.path.join(BASE_DIR, ".env"))

from flask import Blueprint, Flask, jsonify, request, send_from_directory

from db import init_db, get_connection
from auth import hash_password, verify_password, create_token, verify_token, ACCESS_TOKEN_TTL_SECONDS, REFRESH_TOKEN_TTL_SECONDS
# Where uploaded images/videos actually live. MUST be a plain,
# directly-web-accessible folder your webserver serves as static files —
# see DEPLOYMENT.md. Defaults to a sibling `media/` next to this app
# (i.e. website/media/, alongside index.html/assets/pages when this
# whole website/ folder is uploaded as one unit).
MEDIA_ROOT = os.path.abspath(os.getenv("MEDIA_ROOT", os.path.join(BASE_DIR, "..", "media")))

app = Flask(__name__)
app.json.ensure_ascii = False  # readable Persian in responses/logs, not \uXXXX escapes
init_db()

# All routes below are attached to this Blueprint with NO version/api
# prefix baked in (e.g. "/events", not "/api/v1/events") — the prefix is
# added at registration time, twice (see the bottom of this file), so
# the API answers at BOTH /v1/... and /api/v1/.... This isn't
# indecision: whether a cPanel/DirectAdmin "Application URL" mount point
# strips its own prefix from the path the WSGI app sees, or leaves it
# in, is genuinely inconsistent across panel/Passenger versions and not
# something to guess at deploy time. Registering both costs nothing and
# removes the guesswork — whichever behavior your host has, the frontend
# (which always calls /api/v1/...) just works.
api = Blueprint("api", __name__)


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

def _json_list(raw: str | None) -> list:
    if not raw:
        return []
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return []


def _admin_payload() -> dict | None:
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return None
    payload = verify_token(header[len("Bearer "):])
    if not payload or payload.get("type") != "access" or not payload.get("admin_id"):
        return None
    return payload


def require_admin():
    """Returns the admin payload, or None (caller should respond 401)."""
    return _admin_payload()


def _event_public(row: dict) -> dict:
    return {
        "id": row["id"], "title": row["title"], "title_en": row["title_en"],
        "description": row["description"], "description_en": row["description_en"],
        "location": row["location"], "location_en": row["location_en"],
        "date": row["date"], "status": row["status"], "tags": _json_list(row["tags"]),
        "poster": row["poster"], "gallery": _json_list(row["gallery"]), "video": row["video"],
        "contact_phone": row["contact_phone"], "contact_telegram": row["contact_telegram"],
    }


def _portfolio_public(row: dict) -> dict:
    return {
        "id": row["id"], "title_fa": row["title_fa"], "title_en": row["title_en"],
        "year": row["year"], "category": row["category"],
        "director": row["director"], "director_en": row["director_en"],
        "role": row["role"], "role_en": row["role_en"],
        "festival": row["festival"], "festival_en": row["festival_en"],
        "poster": row["poster"], "gallery": _json_list(row["gallery"]), "video": row["video"],
        "desc_fa": row["desc_fa"], "desc_en": row["desc_en"],
        "status": row["status"], "sort_order": row["sort_order"],
    }


def _team_public(row: dict) -> dict:
    return {
        "id": row["id"], "slug": row["slug"], "full_name": row["full_name"], "full_name_en": row["full_name_en"],
        "role_title": row["role_title"], "role_title_en": row["role_title_en"], "photo": row["photo"],
        "bio_fa": row["bio_fa"], "bio_en": row["bio_en"], "gallery": _json_list(row["gallery"]),
        "contact_phone": row["contact_phone"], "contact_telegram": row["contact_telegram"],
        "status": row["status"], "sort_order": row["sort_order"],
    }


_SLUG_RE = re.compile(r"[^a-z0-9؀-ۿ]+")


def slugify(text: str) -> str:
    base = _SLUG_RE.sub("-", (text or "").strip().lower()).strip("-") or "member"
    with get_connection() as conn:
        candidate = base
        n = 1
        while conn.execute("SELECT 1 FROM team_members WHERE slug=?", (candidate,)).fetchone():
            n += 1
            candidate = f"{base}-{n}"
        return candidate


@app.after_request
def _cors(resp):
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    resp.headers["Access-Control-Allow-Methods"] = "GET, POST, PATCH, DELETE, OPTIONS"
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    return resp


@api.route("/<path:_any>", methods=["OPTIONS"])
def _cors_preflight(_any):
    return ("", 204)


# ---------------------------------------------------------------------
# Public reads
# ---------------------------------------------------------------------

@api.get("/events")
def list_events():
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM events ORDER BY id DESC").fetchall()
    return jsonify({"data": [_event_public(dict(r)) for r in rows]})


@api.get("/portfolio")
def list_portfolio():
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM portfolio ORDER BY sort_order, id DESC").fetchall()
    return jsonify({"data": [_portfolio_public(dict(r)) for r in rows]})


@api.get("/team")
def list_team():
    # Admin (valid token) sees every member, including inactive ones being
    # drafted; the public site only ever sees 'active'.
    is_admin = require_admin() is not None
    with get_connection() as conn:
        if is_admin:
            rows = conn.execute("SELECT * FROM team_members ORDER BY sort_order, id").fetchall()
        else:
            rows = conn.execute("SELECT * FROM team_members WHERE status='active' ORDER BY sort_order, id").fetchall()
    return jsonify({"data": [_team_public(dict(r)) for r in rows]})


@api.get("/team/<slug>")
def get_team_member(slug):
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM team_members WHERE slug=?", (slug,)).fetchone()
    if not row:
        return jsonify({"error": "not_found"}), 404
    return jsonify({"data": _team_public(dict(row))})


# ---------------------------------------------------------------------
# Admin auth
# ---------------------------------------------------------------------

# In-memory login rate limit — same simple sliding-window pattern
# bot/api/server.py uses. In-memory is fine here: a brute-force attempt
# restarting because the WSGI worker recycled is not a real gap (the
# attacker just lost their progress), and this backend doesn't have
# Redis/memcached available on typical shared hosting to do better.
_LOGIN_ATTEMPTS: dict[str, list[float]] = {}
_LOGIN_WINDOW_SECONDS = 15 * 60
_LOGIN_MAX_ATTEMPTS = 8


def _rate_limited(key: str) -> bool:
    now = time.time()
    attempts = [t for t in _LOGIN_ATTEMPTS.get(key, []) if now - t < _LOGIN_WINDOW_SECONDS]
    _LOGIN_ATTEMPTS[key] = attempts
    return len(attempts) >= _LOGIN_MAX_ATTEMPTS


def _record_login_attempt(key: str) -> None:
    _LOGIN_ATTEMPTS.setdefault(key, []).append(time.time())


@api.post("/admin/login")
def admin_login():
    body = request.get_json(silent=True) or {}
    username = str(body.get("username", "")).strip()
    password = str(body.get("password", ""))
    rate_key = f"{request.remote_addr}:{username}"
    if _rate_limited(rate_key):
        return jsonify({"error": "too_many_attempts", "details": "try again later"}), 429
    if not username or not password:
        return jsonify({"error": "validation", "details": "username and password are required"}), 400
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM cms_admins WHERE username=? AND is_active=1", (username,)).fetchone()
        if not row or not verify_password(password, row["password_hash"], row["password_salt"]):
            _record_login_attempt(rate_key)
            return jsonify({"error": "invalid_credentials"}), 401
        conn.execute("UPDATE cms_admins SET last_login_at=datetime('now') WHERE id=?", (row["id"],))
    access = create_token({"admin_id": row["id"], "role": "admin", "type": "access"}, ACCESS_TOKEN_TTL_SECONDS)
    refresh = create_token({"admin_id": row["id"], "role": "admin", "type": "refresh"}, REFRESH_TOKEN_TTL_SECONDS)
    return jsonify({"data": {
        "access_token": access, "refresh_token": refresh,
        "username": row["username"], "role": row["role"],
    }})


@api.post("/admin/refresh")
def admin_refresh():
    body = request.get_json(silent=True) or {}
    payload = verify_token(str(body.get("refresh_token", "")))
    if not payload or payload.get("type") != "refresh" or not payload.get("admin_id"):
        return jsonify({"error": "invalid_refresh_token"}), 401
    access = create_token({"admin_id": payload["admin_id"], "role": "admin", "type": "access"}, ACCESS_TOKEN_TTL_SECONDS)
    return jsonify({"data": {"access_token": access}})


# ---------------------------------------------------------------------
# Admin: events
# ---------------------------------------------------------------------

_EVENT_FIELDS = ("title", "title_en", "description", "description_en", "location", "location_en",
                  "date", "status", "poster", "gallery", "video", "contact_phone", "contact_telegram")


@api.post("/admin/events")
def create_event():
    if not require_admin():
        return jsonify({"error": "unauthorized"}), 401
    body = request.get_json(silent=True) or {}
    if not body.get("title"):
        return jsonify({"error": "validation", "details": "title is required"}), 400
    fields = {k: body[k] for k in _EVENT_FIELDS if k in body}
    if "gallery" in body and isinstance(body["gallery"], list):
        fields["gallery"] = json.dumps(body["gallery"], ensure_ascii=False)
    tags = json.dumps(body.get("tags", []), ensure_ascii=False) if isinstance(body.get("tags"), list) else "[]"
    with get_connection() as conn:
        cols = ", ".join(fields.keys())
        placeholders = ", ".join("?" for _ in fields)
        cur = conn.execute(
            f"INSERT INTO events(tags, {cols}) VALUES (?, {placeholders})",
            (tags, *fields.values()),
        )
        row = conn.execute("SELECT * FROM events WHERE id=?", (cur.lastrowid,)).fetchone()
    return jsonify({"data": _event_public(dict(row))}), 201


@api.patch("/admin/events/<int:event_id>")
def update_event(event_id):
    if not require_admin():
        return jsonify({"error": "unauthorized"}), 401
    body = request.get_json(silent=True) or {}
    fields = {k: body[k] for k in _EVENT_FIELDS if k in body}
    if "gallery" in body and isinstance(body["gallery"], list):
        fields["gallery"] = json.dumps(body["gallery"], ensure_ascii=False)
    if "tags" in body and isinstance(body["tags"], list):
        fields["tags"] = json.dumps(body["tags"], ensure_ascii=False)
    if not fields:
        return jsonify({"error": "validation", "details": "no updatable fields given"}), 400
    with get_connection() as conn:
        set_clause = ", ".join(f"{k}=?" for k in fields)
        conn.execute(f"UPDATE events SET {set_clause} WHERE id=?", (*fields.values(), event_id))
        row = conn.execute("SELECT * FROM events WHERE id=?", (event_id,)).fetchone()
    if not row:
        return jsonify({"error": "not_found"}), 404
    return jsonify({"data": _event_public(dict(row))})


@api.delete("/admin/events/<int:event_id>")
def delete_event(event_id):
    if not require_admin():
        return jsonify({"error": "unauthorized"}), 401
    with get_connection() as conn:
        conn.execute("DELETE FROM events WHERE id=?", (event_id,))
    return jsonify({"data": {"deleted": True}})


# ---------------------------------------------------------------------
# Admin: portfolio
# ---------------------------------------------------------------------

_PORTFOLIO_FIELDS = ("title_fa", "title_en", "year", "category", "director", "director_en",
                      "role", "role_en", "festival", "festival_en", "poster", "gallery", "video",
                      "desc_fa", "desc_en", "status", "sort_order")


@api.post("/admin/portfolio")
def create_portfolio():
    if not require_admin():
        return jsonify({"error": "unauthorized"}), 401
    body = request.get_json(silent=True) or {}
    if not body.get("title_fa"):
        return jsonify({"error": "validation", "details": "title_fa is required"}), 400
    fields = {k: body[k] for k in _PORTFOLIO_FIELDS if k in body}
    if "gallery" in body and isinstance(body["gallery"], list):
        fields["gallery"] = json.dumps(body["gallery"], ensure_ascii=False)
    fields.setdefault("category", body.get("category", "film"))
    with get_connection() as conn:
        cols = ", ".join(fields.keys())
        placeholders = ", ".join("?" for _ in fields)
        cur = conn.execute(f"INSERT INTO portfolio({cols}) VALUES ({placeholders})", tuple(fields.values()))
        row = conn.execute("SELECT * FROM portfolio WHERE id=?", (cur.lastrowid,)).fetchone()
    return jsonify({"data": _portfolio_public(dict(row))}), 201


@api.patch("/admin/portfolio/<int:item_id>")
def update_portfolio(item_id):
    if not require_admin():
        return jsonify({"error": "unauthorized"}), 401
    body = request.get_json(silent=True) or {}
    fields = {k: body[k] for k in _PORTFOLIO_FIELDS if k in body}
    if "gallery" in body and isinstance(body["gallery"], list):
        fields["gallery"] = json.dumps(body["gallery"], ensure_ascii=False)
    if not fields:
        return jsonify({"error": "validation", "details": "no updatable fields given"}), 400
    with get_connection() as conn:
        set_clause = ", ".join(f"{k}=?" for k in fields)
        conn.execute(f"UPDATE portfolio SET {set_clause} WHERE id=?", (*fields.values(), item_id))
        row = conn.execute("SELECT * FROM portfolio WHERE id=?", (item_id,)).fetchone()
    if not row:
        return jsonify({"error": "not_found"}), 404
    return jsonify({"data": _portfolio_public(dict(row))})


@api.delete("/admin/portfolio/<int:item_id>")
def delete_portfolio(item_id):
    if not require_admin():
        return jsonify({"error": "unauthorized"}), 401
    with get_connection() as conn:
        conn.execute("DELETE FROM portfolio WHERE id=?", (item_id,))
    return jsonify({"data": {"deleted": True}})


# ---------------------------------------------------------------------
# Admin: team
# ---------------------------------------------------------------------

_TEAM_FIELDS = ("full_name", "full_name_en", "role_title", "role_title_en", "photo", "bio_fa", "bio_en",
                "gallery", "contact_phone", "contact_telegram", "status", "sort_order")


@api.post("/admin/team")
def create_team_member():
    if not require_admin():
        return jsonify({"error": "unauthorized"}), 401
    body = request.get_json(silent=True) or {}
    if not body.get("full_name"):
        return jsonify({"error": "validation", "details": "full_name is required"}), 400
    fields = {k: body[k] for k in _TEAM_FIELDS if k in body}
    if "gallery" in body and isinstance(body["gallery"], list):
        fields["gallery"] = json.dumps(body["gallery"], ensure_ascii=False)
    slug = slugify(body["full_name"])
    with get_connection() as conn:
        cols = ", ".join(fields.keys())
        placeholders = ", ".join("?" for _ in fields)
        cur = conn.execute(f"INSERT INTO team_members(slug, {cols}) VALUES (?, {placeholders})", (slug, *fields.values()))
        row = conn.execute("SELECT * FROM team_members WHERE id=?", (cur.lastrowid,)).fetchone()
    return jsonify({"data": _team_public(dict(row))}), 201


@api.patch("/admin/team/<int:member_id>")
def update_team_member(member_id):
    if not require_admin():
        return jsonify({"error": "unauthorized"}), 401
    body = request.get_json(silent=True) or {}
    fields = {k: body[k] for k in _TEAM_FIELDS if k in body}
    if "gallery" in body and isinstance(body["gallery"], list):
        fields["gallery"] = json.dumps(body["gallery"], ensure_ascii=False)
    if not fields:
        return jsonify({"error": "validation", "details": "no updatable fields given"}), 400
    with get_connection() as conn:
        set_clause = ", ".join(f"{k}=?" for k in fields)
        conn.execute(f"UPDATE team_members SET {set_clause} WHERE id=?", (*fields.values(), member_id))
        row = conn.execute("SELECT * FROM team_members WHERE id=?", (member_id,)).fetchone()
    if not row:
        return jsonify({"error": "not_found"}), 404
    return jsonify({"data": _team_public(dict(row))})


@api.delete("/admin/team/<int:member_id>")
def delete_team_member(member_id):
    if not require_admin():
        return jsonify({"error": "unauthorized"}), 401
    with get_connection() as conn:
        conn.execute("DELETE FROM team_members WHERE id=?", (member_id,))
    return jsonify({"data": {"deleted": True}})


# ---------------------------------------------------------------------
# Admin: media upload
# ---------------------------------------------------------------------

_EXT_MAP = {
    "image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "image/gif": ".gif",
    "video/mp4": ".mp4", "video/webm": ".webm",
}
_ALLOWED_KINDS = ("poster", "gallery", "video", "portfolio", "team")


@api.post("/admin/upload")
def upload_media():
    if not require_admin():
        return jsonify({"error": "unauthorized"}), 401
    body = request.get_json(silent=True) or {}
    data_url = body.get("data")
    kind = body.get("kind") if body.get("kind") in _ALLOWED_KINDS else "gallery"
    if not data_url or not isinstance(data_url, str) or not data_url.startswith("data:"):
        return jsonify({"error": "validation", "details": "data must be a base64 data URL"}), 400
    match = re.match(r"^data:([^;]+);base64,(.*)$", data_url, re.S)
    if not match:
        return jsonify({"error": "validation", "details": "malformed data URL"}), 400
    mime, b64 = match.group(1), match.group(2)
    ext = _EXT_MAP.get(mime, ".bin")
    safe_name = f"{int(time.time() * 1000)}-{os.urandom(4).hex()}{ext}"
    upload_dir = os.path.join(MEDIA_ROOT, kind)
    os.makedirs(upload_dir, exist_ok=True)
    with open(os.path.join(upload_dir, safe_name), "wb") as f:
        f.write(base64.b64decode(b64))
    return jsonify({"data": {"path": f"media/{kind}/{safe_name}", "kind": kind}}), 201


# ---------------------------------------------------------------------
# Local-dev-only convenience: serve uploaded media directly. In
# production the real webserver (Apache/LiteSpeed under cPanel/
# DirectAdmin) serves MEDIA_ROOT as plain static files at /media/... —
# this route only exists so `flask run` works standalone for testing.
# ---------------------------------------------------------------------

@app.get("/media/<path:filename>")
def _dev_media(filename):
    return send_from_directory(MEDIA_ROOT, filename)


# Register the API blueprint at both possible mount shapes — see the
# comment above `api = Blueprint(...)`.
app.register_blueprint(api, url_prefix="/api/v1", name="api_with_full_prefix")
app.register_blueprint(api, url_prefix="/v1", name="api_with_short_prefix")


if __name__ == "__main__":
    app.run(port=int(os.getenv("PORT", "8790")), debug=os.getenv("FLASK_DEBUG") == "1")
