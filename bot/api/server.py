"""
Mavara Home — Unified REST API (Phase 1).

WHY http.server INSTEAD OF FastAPI: the spec asked for FastAPI, and this
should become FastAPI — but the development environment this was built in
has no internet access to `pip install fastapi`, and the explicit rule for
this phase was "don't deliver until it's actually verified working, not
just written." Python's stdlib `http.server` needs zero external packages,
so every endpoint below was actually started and hit with curl (see the
test script). Migrating this to FastAPI later is a mechanical, low-risk
change: every route here just calls a function in services/ and returns a
dict — none of the business logic lives in this file, so swapping the HTTP
layer touches nothing underneath it.

ARCHITECTURE RULE THIS FILE FOLLOWS: no business logic here. Every route
is (parse request) -> (call a services/ or database/repositories/ function)
-> (return its result as JSON). Capacity checks, atomicity, pricing,
idempotency — all of that already exists in services/ and is reused
as-is, exactly as required ("Business Logic نباید دوبار نوشته شود").

Run: python -m api.server
Default port: 8788 (deliberately different from the website's own Node
server on 8787, so both can run side by side during Phase 1 testing).
"""
from __future__ import annotations

import json
import os
import re
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services import event_service, reservation_service, settings_service, customer_auth_service
from database.repositories import events as events_repo
from database.repositories import sessions as sessions_repo
from database.repositories import reservations as reservations_repo
from database.repositories import users as users_repo
from database.repositories import portfolio as portfolio_repo
from database.repositories import logs as logs_repo
from database.repositories import web_admins as web_admins_repo
from database.repositories import messages as messages_repo
from database.repositories import team_members as team_repo
from utils.auth import hash_password, verify_password, create_token, verify_token, ACCESS_TOKEN_TTL_SECONDS, REFRESH_TOKEN_TTL_SECONDS
from utils.qr_signing import verify_signed_code
from validators.validators import normalize_phone, is_valid_iranian_mobile, is_valid_full_name
from utils.logger import get_logger

logger = get_logger()

# Phase 1 admin auth: a single shared-secret header, same pattern the
# website's existing Node backend already uses (X-Admin-Token). Real JWT +
# per-admin sessions + roles is explicitly Phase 2 — this is intentionally
# the minimum needed to protect write endpoints for now, not the final
# auth design.
API_ADMIN_TOKEN = os.getenv("API_ADMIN_TOKEN", "1234")  # deprecated, see _is_admin() below

# Login rate limiting — deliberately simple in-process state (a dict), not
# a distributed store. Correct for a single mavara-api process (the
# deployment this project actually runs as — see DEPLOYMENT.md); would
# need a shared store (Redis etc.) if this API is ever horizontally
# scaled to multiple processes, which it isn't.
_login_attempts: dict[str, list[float]] = {}
_LOGIN_MAX_ATTEMPTS = 5
_LOGIN_WINDOW_SECONDS = 15 * 60


def _rate_limited(key: str) -> bool:
    import time
    now = time.time()
    attempts = [t for t in _login_attempts.get(key, []) if now - t < _LOGIN_WINDOW_SECONDS]
    _login_attempts[key] = attempts
    return len(attempts) >= _LOGIN_MAX_ATTEMPTS


def _record_login_attempt(key: str) -> None:
    import time
    _login_attempts.setdefault(key, []).append(time.time())

PORT = int(os.getenv("API_PORT", "8788"))

# Optional: serve the website's static files (index.html, pages/, assets/)
# from this SAME process, so a simple deployment is just "one Python
# process, one port" instead of needing a separate static host too. Unset
# (default) disables this — recommended production setup is still Nginx
# serving static files directly + reverse-proxying /api/v1/ to this
# process (see deploy/nginx.conf.example and DEPLOYMENT.md), which is
# faster and more standard, but this exists for a quick single-command
# deployment or local testing without touching Nginx at all.
STATIC_ROOT = os.getenv("STATIC_ROOT", "")
_MIME = {
    ".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8", ".json": "application/json; charset=utf-8",
    ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".svg": "image/svg+xml",
    ".webp": "image/webp", ".woff": "font/woff", ".woff2": "font/woff2", ".ico": "image/x-icon",
    ".mp4": "video/mp4", ".webm": "video/webm",
}


def _serve_static(handler, pathname: str) -> bool:
    """Returns True if it handled the request (found and served a file, or
    correctly 404'd within the static root), False if STATIC_ROOT isn't
    configured at all (caller should fall through to the normal 404)."""
    if not STATIC_ROOT:
        return False
    root = os.path.abspath(STATIC_ROOT)
    rel = "/index.html" if pathname == "/" else pathname
    file_path = os.path.abspath(os.path.join(root, rel.lstrip("/")))
    if not file_path.startswith(root) or not os.path.isfile(file_path):
        handler._send_json(404, {"error": "not_found"})
        return True
    ext = os.path.splitext(file_path)[1]
    with open(file_path, "rb") as f:
        body = f.read()
    handler.send_response(200)
    handler.send_header("Content-Type", _MIME.get(ext, "application/octet-stream"))
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)
    return True


def _event_public(e: dict) -> dict:
    price, currency = event_service.get_effective_price(e)
    gallery = []
    if e.get("gallery"):
        try:
            gallery = json.loads(e["gallery"])
        except (json.JSONDecodeError, TypeError):
            gallery = []
    return {
        "id": e["id"], "title": e["title"], "title_en": e.get("title_en"),
        "description": e.get("description"), "description_en": e.get("description_en"),
        "icon": e.get("icon"), "is_active": bool(e["is_active"]), "calendar_type": e.get("calendar_type"),
        "price": price, "currency": currency,
        "address": e.get("address"), "location": e.get("location"), "location_en": e.get("location_en"),
        "poster": e.get("poster"), "gallery": gallery, "video": e.get("video"),
        "contact_phone": e.get("contact_phone"), "contact_telegram": e.get("contact_telegram"),
    }


def _session_public(s: dict) -> dict:
    available = event_service.get_available_seats(s)
    return {
        "id": s["id"], "event_id": s["event_id"], "date": s["session_date"],
        "time": s["session_time"], "capacity": s["capacity"],
        "available": available, "status": s.get("status", "active"),
    }


def _reservation_public(r: dict) -> dict:
    return {
        "id": r["id"], "reservation_code": r.get("reservation_code"),
        "session_id": r["session_id"], "people": r["people"],
        "unit_price": r.get("unit_price"), "total_price": r.get("total_price"),
        "status": r["status"], "source": r.get("source"),
        "attendee_name": r.get("attendee_name"), "attendee_phone": r.get("attendee_phone"),
        "created_at": r.get("created_at"),
        # Only present on the admin listing (list_recent's join) — the
        # per-customer lookup (list_for_user) doesn't need to tell a user
        # their own name/phone back.
        "buyer_name": r.get("buyer_name"), "buyer_phone": r.get("buyer_phone"),
        "event_id": r.get("event_id"), "event_title": r.get("event_title"),
        "session_date": r.get("session_date"), "session_time": r.get("session_time"),
    }


def _team_public(m: dict) -> dict:
    return {
        "id": m["id"], "slug": m["slug"], "full_name": m["full_name"], "full_name_en": m.get("full_name_en"),
        "role_title": m.get("role_title"), "role_title_en": m.get("role_title_en"), "photo": m.get("photo"),
        "bio_fa": m.get("bio_fa"), "bio_en": m.get("bio_en"), "gallery": m.get("gallery") or [],
        "contact_phone": m.get("contact_phone"), "contact_telegram": m.get("contact_telegram"),
        "status": m.get("status"), "sort_order": m.get("sort_order"),
    }


def _message_public(m: dict) -> dict:
    return {
        "id": m["id"], "sender": m["sender"], "body": m["body"],
        "attachment_path": m.get("attachment_path"), "created_at": m.get("created_at"),
    }


def _ticket_context(reservation: dict) -> dict:
    """Assembles what a ticket PDF/screen needs from a bare reservation
    row — pure lookups + the existing display_date_for_event formatter,
    not new business logic (mirrors how _reservation_public already
    composes data for the admin list)."""
    from utils.jalali import display_date_for_event
    session = sessions_repo.get_session(reservation["session_id"]) or {}
    event = events_repo.get_event(session.get("event_id")) if session else None
    return {
        "event_title": event["title"] if event else "",
        "address": (event or {}).get("address"),
        "session_date_display": display_date_for_event(session.get("session_date", ""), (event or {}).get("calendar_type", "jalali")) if session else "",
        "session_time": session.get("session_time", ""),
    }


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        logger.info("api %s - %s", self.address_string(), fmt % args)

    def _send_json(self, status: int, payload: dict):
        body = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PATCH, DELETE, OPTIONS")
        # Basic security headers (Phase 7 will do a fuller pass — this
        # covers the cheap, high-value ones with zero functional risk).
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
        self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}

    def _is_admin(self) -> bool:
        return self._get_admin_payload() is not None

    def _get_admin_payload(self) -> dict | None:
        """Phase 2: real JWT auth. The old static X-Admin-Token header is
        no longer accepted — a shared password-equivalent token that never
        expires and is identical for every admin was exactly the gap this
        phase exists to close. See /api/v1/admin/login.

        Phase 4 regression note (found by this feature's own live test,
        not by inspection — same discipline as every earlier phase in
        this project): before customer accounts existed, EVERY valid
        access token in the system was necessarily an admin token, so
        checking only `type == "access"` was sufficient. Once
        /api/v1/auth/customer/verify-otp started minting access tokens
        too, that check silently accepted a customer token on every
        admin-only endpoint. Fixed by requiring the admin-only `admin_id`
        claim (never present on a customer token) rather than just
        checking token validity.
        """
        auth_header = self.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return None
        token = auth_header[len("Bearer "):]
        payload = verify_token(token)
        if not payload or payload.get("type") != "access" or "admin_id" not in payload:
            return None
        return payload

    def _get_customer_payload(self) -> dict | None:
        """Phase 4: same JWT mechanism as admin auth (utils/auth.py),
        distinguished by role='customer' so a customer token can never be
        replayed against an admin-only endpoint or vice versa — both
        checks are explicit, not just 'is there a valid token'."""
        auth_header = self.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return None
        token = auth_header[len("Bearer "):]
        payload = verify_token(token)
        if not payload or payload.get("type") != "access" or payload.get("role") != "customer":
            return None
        return payload

    def do_OPTIONS(self):
        self._send_json(204, {})

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)
        try:
            if path == "/health":
                return self._send_json(200, {"status": "ok"})

            if path.startswith("/media/"):
                # Uploaded posters/gallery/video/receipts are written to disk
                # by the upload endpoints below, but were never actually
                # servable back over HTTP until this route — every uploaded
                # image would have been a broken link. Always active
                # (unlike STATIC_ROOT), since uploaded content must be
                # reachable regardless of deployment mode.
                media_root = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "media")
                file_path = os.path.abspath(os.path.join(media_root, path[len("/media/"):]))
                if not file_path.startswith(os.path.abspath(media_root)) or not os.path.isfile(file_path):
                    return self._send_json(404, {"error": "not_found"})
                ext = os.path.splitext(file_path)[1]
                with open(file_path, "rb") as f:
                    body = f.read()
                self.send_response(200)
                self.send_header("Content-Type", _MIME.get(ext, "application/octet-stream"))
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return

            if path == "/api/v1/events":
                events = events_repo.list_active_events() if not self._is_admin() else events_repo.list_all_events()
                return self._send_json(200, {"data": [_event_public(e) for e in events]})

            m = re.match(r"^/api/v1/events/(\d+)$", path)
            if m:
                event = events_repo.get_event(int(m.group(1)))
                if not event:
                    return self._send_json(404, {"error": "not_found"})
                return self._send_json(200, {"data": _event_public(event)})

            m = re.match(r"^/api/v1/events/(\d+)/dates$", path)
            if m:
                dates = event_service.get_bookable_dates(int(m.group(1)))
                return self._send_json(200, {"data": dates})

            if path == "/api/v1/sessions":
                event_id = qs.get("event_id", [None])[0]
                date = qs.get("date", [None])[0]
                if not event_id:
                    return self._send_json(400, {"error": "validation", "details": "event_id query param is required"})
                if self._is_admin():
                    # Admin calendar view: ALL sessions for the event (including
                    # inactive/sold-out ones), optionally still filterable by date.
                    sessions = sessions_repo.list_sessions_for_event_admin(int(event_id))
                    if date:
                        sessions = [s for s in sessions if s["session_date"] == date]
                else:
                    # Public/customer booking widget: every bookable session
                    # for the event, across all dates — the frontend groups
                    # these into a date-picker client-side (API.dates.forEvent).
                    # This does NOT need admin auth; a website visitor
                    # browsing available showtimes is not an admin action.
                    # Filtering to one date is still supported (optional)
                    # for callers that already know which date they want.
                    sessions = event_service.get_bookable_dates(int(event_id))
                    if date:
                        sessions = [s for s in sessions if s["session_date"] == date]
                return self._send_json(200, {"data": [_session_public(s) for s in sessions]})

            if path == "/api/v1/reservations":
                phone = qs.get("phone", [None])[0]
                if not phone:
                    return self._send_json(400, {"error": "validation", "details": "phone query param is required"})
                user = users_repo.get_or_create_user_by_phone(normalize_phone(phone))
                # Look up without creating side effects beyond the lookup above
                # being idempotent (get_or_create is safe to call for reads too).
                rows = reservations_repo.list_for_user(user["id"])
                return self._send_json(200, {"data": [_reservation_public(r) for r in rows]})

            if path == "/api/v1/admin/reservations":
                if not self._is_admin():
                    return self._send_json(401, {"error": "unauthorized"})
                rows = reservations_repo.list_recent(limit=200)
                return self._send_json(200, {"data": [_reservation_public(r) for r in rows]})

            if path == "/api/v1/admin/activity":
                if not self._is_admin():
                    return self._send_json(401, {"error": "unauthorized"})
                limit = int(qs.get("limit", [100])[0])
                rows = logs_repo.recent(limit=min(limit, 500))
                return self._send_json(200, {"data": rows})

            if path == "/api/v1/admin/dashboard-stats":
                if not self._is_admin():
                    return self._send_json(401, {"error": "unauthorized"})
                # Real numbers for the dashboard charts — computed here
                # (not re-derived client-side from the full reservation
                # list) so the same aggregation logic can't drift between
                # the website and any future consumer of this endpoint.
                import datetime
                today = datetime.date.today()
                daily = []
                all_res = reservations_repo.list_recent(limit=2000)
                for i in range(13, -1, -1):
                    day = today - datetime.timedelta(days=i)
                    day_str = day.isoformat()
                    day_res = [r for r in all_res if str(r.get("created_at", "")).startswith(day_str)]
                    approved = [r for r in day_res if r["status"] == "approved"]
                    daily.append({
                        "date": day_str,
                        "reservations": len(day_res),
                        "revenue": sum(r.get("total_price") or 0 for r in approved),
                    })
                by_status: dict[str, int] = {}
                for r in all_res:
                    by_status[r["status"]] = by_status.get(r["status"], 0) + 1
                return self._send_json(200, {"data": {"daily": daily, "by_status": by_status}})

            if path == "/api/v1/portfolio":
                # Public — every website visitor's resume page needs this.
                # No admin filtering by status here (yet); status is
                # informational (e.g. 'active' for "currently running").
                items = portfolio_repo.list_all()
                return self._send_json(200, {"data": items})

            if path == "/api/v1/payment-info":
                # Public, read-only: what the website's payment step needs to
                # show the buyer — same active card the bot itself uses, so
                # there's only ever one place this is configured.
                from database.repositories import bank_cards as bank_cards_repo
                card = bank_cards_repo.get_active_card()
                return self._send_json(200, {"data": {
                    "card_number": card["card_number"] if card else None,
                    "card_holder": card["card_holder"] if card else None,
                    "bank_name": card["bank_name"] if card else None,
                }})

            # ---------------- Phase 4: customer account ----------------
            if path == "/api/v1/account/reservations":
                payload = self._get_customer_payload()
                if not payload:
                    return self._send_json(401, {"error": "unauthorized"})
                rows = reservations_repo.list_for_user(payload["user_id"])
                # list_for_user() is a flat, unjoined query (shared with
                # Phase 1's phone-lookup endpoint — not changing it here,
                # see database/repositories/reservations.py), so the
                # customer dashboard needs to enrich each row with its
                # event/session details itself, same as the ticket PDF
                # already does via _ticket_context().
                enriched = []
                for r in rows:
                    r = dict(r)
                    ctx = _ticket_context(r)
                    r["event_title"] = ctx["event_title"]
                    r["session_date"] = ctx["session_date_display"]
                    r["session_time"] = ctx["session_time"]
                    enriched.append(r)
                return self._send_json(200, {"data": [_reservation_public(r) for r in enriched]})

            m = re.match(r"^/api/v1/account/reservations/(\d+)/ticket\.pdf$", path)
            if m:
                payload = self._get_customer_payload()
                if not payload:
                    return self._send_json(401, {"error": "unauthorized"})
                reservation = reservations_repo.get_reservation(int(m.group(1)))
                if not reservation or reservation["user_id"] != payload["user_id"]:
                    return self._send_json(404, {"error": "not_found"})
                if reservation["status"] != "approved" or not reservation.get("reservation_code"):
                    return self._send_json(409, {"error": "ticket_not_ready", "details": "reservation is not confirmed yet"})
                from utils.ticket_pdf import build_ticket_pdf
                ctx = _ticket_context(reservation)
                pdf_bytes = build_ticket_pdf(reservation=reservation, **ctx)
                self.send_response(200)
                self.send_header("Content-Type", "application/pdf")
                self.send_header("Content-Length", str(len(pdf_bytes)))
                self.send_header("Content-Disposition", f'inline; filename="ticket-{reservation["reservation_code"]}.pdf"')
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(pdf_bytes)
                return

            if path == "/api/v1/account/messages":
                payload = self._get_customer_payload()
                if not payload:
                    return self._send_json(401, {"error": "unauthorized"})
                rows = messages_repo.list_for_user(payload["user_id"])
                messages_repo.mark_read_by_customer(payload["user_id"])
                return self._send_json(200, {"data": [_message_public(m) for m in rows]})

            # ---------------- Phase 5: admin messaging ----------------
            if path == "/api/v1/admin/messages":
                if not self._is_admin():
                    return self._send_json(401, {"error": "unauthorized"})
                return self._send_json(200, {"data": messages_repo.list_threads()})

            m = re.match(r"^/api/v1/admin/messages/(\d+)$", path)
            if m:
                if not self._is_admin():
                    return self._send_json(401, {"error": "unauthorized"})
                user_id = int(m.group(1))
                rows = messages_repo.list_for_user(user_id)
                messages_repo.mark_read_by_admin(user_id)
                return self._send_json(200, {"data": [_message_public(m) for m in rows]})

            # ---------------- New scope: team directory ----------------
            if path == "/api/v1/team":
                members = team_repo.list_all() if self._is_admin() else team_repo.list_all(status="active")
                return self._send_json(200, {"data": [_team_public(m) for m in members]})

            m = re.match(r"^/api/v1/team/([\w-]+)$", path)
            if m:
                member = team_repo.get_by_slug(m.group(1))
                if not member or (member["status"] != "active" and not self._is_admin()):
                    return self._send_json(404, {"error": "not_found"})
                return self._send_json(200, {"data": _team_public(member)})

            if not path.startswith("/api/v1"):
                if _serve_static(self, path):
                    return

            return self._send_json(404, {"error": "not_found"})
        except Exception as exc:
            logger.exception("API GET error on %s", path)
            return self._send_json(500, {"error": "internal_error", "details": str(exc)})

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        try:
            if path == "/api/v1/admin/login":
                body = self._read_json_body()
                username = str(body.get("username", "")).strip()
                password = str(body.get("password", ""))
                client_ip = self.client_address[0] if self.client_address else "unknown"
                rate_key = f"{client_ip}:{username}"
                if _rate_limited(rate_key):
                    return self._send_json(429, {"error": "too_many_attempts", "details": "try again later"})
                if not username or not password:
                    return self._send_json(400, {"error": "validation", "details": "username and password are required"})

                admin = web_admins_repo.get_by_username(username)
                if not admin or not verify_password(password, admin["password_hash"], admin["password_salt"]):
                    _record_login_attempt(rate_key)
                    # Deliberately the same error for "no such user" and
                    # "wrong password" — distinguishing them lets an
                    # attacker enumerate valid usernames.
                    return self._send_json(401, {"error": "invalid_credentials"})

                web_admins_repo.mark_login(admin["id"])
                access_token = create_token({"sub": admin["username"], "admin_id": admin["id"], "role": admin["role"], "type": "access"}, ACCESS_TOKEN_TTL_SECONDS)
                refresh_token = create_token({"sub": admin["username"], "admin_id": admin["id"], "type": "refresh"}, REFRESH_TOKEN_TTL_SECONDS)
                return self._send_json(200, {"data": {
                    "access_token": access_token, "refresh_token": refresh_token,
                    "expires_in": ACCESS_TOKEN_TTL_SECONDS, "username": admin["username"], "role": admin["role"],
                }})

            if path == "/api/v1/admin/refresh":
                body = self._read_json_body()
                refresh_token = body.get("refresh_token", "")
                payload = verify_token(refresh_token)
                if not payload or payload.get("type") != "refresh" or "admin_id" not in payload:
                    return self._send_json(401, {"error": "invalid_refresh_token"})
                admin = web_admins_repo.get_by_id(payload["admin_id"])
                if not admin or not admin["is_active"]:
                    return self._send_json(401, {"error": "invalid_refresh_token"})
                access_token = create_token({"sub": admin["username"], "admin_id": admin["id"], "role": admin["role"], "type": "access"}, ACCESS_TOKEN_TTL_SECONDS)
                return self._send_json(200, {"data": {"access_token": access_token, "expires_in": ACCESS_TOKEN_TTL_SECONDS}})

            m = re.match(r"^/api/v1/reservations/(\d+)/receipt$", path)
            if m:
                reservation_id = int(m.group(1))
                body = self._read_json_body()
                data_url = body.get("data")
                if not data_url or not isinstance(data_url, str) or not data_url.startswith("data:"):
                    return self._send_json(400, {"error": "validation", "details": "data must be a base64 data URL"})
                if len(data_url) > 1_500_000 * 4 // 3 + 100:  # base64 inflates size by ~4/3
                    return self._send_json(400, {"error": "receipt_too_large"})
                match = re.match(r"^data:([^;]+);base64,(.*)$", data_url, re.S)
                if not match:
                    return self._send_json(400, {"error": "validation", "details": "malformed data URL"})
                mime, b64 = match.group(1), match.group(2)
                ext_map = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}
                ext = ext_map.get(mime, ".jpg")
                import base64, time, random
                safe_name = f"{reservation_id}-{int(time.time() * 1000)}-{random.randint(1000, 9999)}{ext}"
                upload_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "media", "receipts")
                os.makedirs(upload_dir, exist_ok=True)
                with open(os.path.join(upload_dir, safe_name), "wb") as f:
                    f.write(base64.b64decode(b64))
                receipt_path = f"media/receipts/{safe_name}"

                # Same service function the Telegram bot uses for a photo
                # receipt — a website upload is identified by
                # receipt_source="website" so admin tooling can tell the two
                # apart, but the state transition and admin notification
                # logic is the exact same code, not reimplemented here.
                success = reservation_service.submit_receipt(reservation_id, receipt_path, receipt_source="website")
                if not success:
                    return self._send_json(409, {"error": "invalid_status", "details": "reservation is not awaiting a receipt"})
                return self._send_json(200, {"data": {"submitted": True}})

            if path == "/api/v1/reservations":
                body = self._read_json_body()
                phone = body.get("phone")
                full_name = body.get("full_name")
                session_id = body.get("session_id")
                people = body.get("people")

                if not phone or not is_valid_iranian_mobile(normalize_phone(str(phone))):
                    return self._send_json(400, {"error": "validation", "details": "valid phone is required"})
                if not full_name or not is_valid_full_name(str(full_name)):
                    return self._send_json(400, {"error": "validation", "details": "valid full_name is required"})
                if not isinstance(session_id, int):
                    return self._send_json(400, {"error": "validation", "details": "session_id must be an integer"})
                if not isinstance(people, int) or people < 1:
                    return self._send_json(400, {"error": "validation", "details": "people must be a positive integer"})

                # This is THE call that matters for Phase 1: same
                # atomic-capacity-checked reservation function the Telegram
                # bot itself uses — no separate logic, no separate database.
                result = reservation_service.start_reservation_web(
                    phone=phone, full_name=full_name, session_id=session_id, people=people,
                )
                if not result.get("success"):
                    if result.get("waiting"):
                        return self._send_json(200, {"data": {"waiting": True, "waitlist_id": result.get("waitlist_id")}})
                    return self._send_json(409, {"error": result.get("error", "reservation_failed")})

                reservation = reservations_repo.get_reservation(result["reservation_id"])
                return self._send_json(201, {"data": _reservation_public(reservation)})

            m = re.match(r"^/api/v1/admin/reservations/(\d+)/approve$", path)
            if m:
                if not self._is_admin():
                    return self._send_json(401, {"error": "unauthorized"})
                reservation_id = int(m.group(1))
                # Same approve_reservation() the Telegram admin-approve
                # button calls — issues the ticket/QR the exact same way,
                # regardless of which channel the booking came from.
                result = reservation_service.approve_reservation(reservation_id, reviewed_by=0)
                if result is None:
                    return self._send_json(409, {"error": "already_processed"})
                reservation = reservations_repo.get_reservation(reservation_id)
                return self._send_json(200, {"data": _reservation_public(reservation)})

            m = re.match(r"^/api/v1/admin/reservations/(\d+)/reject$", path)
            if m:
                if not self._is_admin():
                    return self._send_json(401, {"error": "unauthorized"})
                reservation_id = int(m.group(1))
                body = self._read_json_body()
                reason = body.get("reason", "")
                reservation_service.reject_reservation(reservation_id, reviewed_by=0, reason=reason)
                reservation = reservations_repo.get_reservation(reservation_id)
                return self._send_json(200, {"data": _reservation_public(reservation)})

            if path == "/api/v1/admin/reservations/bulk-approve":
                if not self._is_admin():
                    return self._send_json(401, {"error": "unauthorized"})
                body = self._read_json_body()
                ids = body.get("ids", [])
                if not isinstance(ids, list) or not ids:
                    return self._send_json(400, {"error": "validation", "details": "ids must be a non-empty array"})
                results = []
                for rid in ids:
                    # Same per-reservation function as the single approve
                    # endpoint — bulk is a loop over the real atomic
                    # operation, not a separate bulk-only code path that
                    # could skip the capacity/idempotency checks.
                    try:
                        outcome = reservation_service.approve_reservation(int(rid), reviewed_by=0)
                        results.append({"id": rid, "success": outcome is not None})
                    except Exception as exc:
                        results.append({"id": rid, "success": False, "error": str(exc)})
                return self._send_json(200, {"data": {"results": results}})

            if path == "/api/v1/admin/portfolio":
                if not self._is_admin():
                    return self._send_json(401, {"error": "unauthorized"})
                body = self._read_json_body()
                if not body.get("title_fa"):
                    return self._send_json(400, {"error": "validation", "details": "title_fa is required"})
                item_id = portfolio_repo.create(**body)
                return self._send_json(201, {"data": portfolio_repo.get(item_id)})

            if path == "/api/v1/admin/payment-info":
                if not self._is_admin():
                    return self._send_json(401, {"error": "unauthorized"})
                body = self._read_json_body()
                card_number = body.get("card_number")
                card_holder = body.get("card_holder")
                bank_name = body.get("bank_name", "")
                if not card_number or not card_holder:
                    return self._send_json(400, {"error": "validation", "details": "card_number and card_holder are required"})
                from database.repositories import bank_cards as bank_cards_repo
                card_id = bank_cards_repo.add_card(card_number, card_holder, bank_name)
                if card_id:
                    bank_cards_repo.set_active(card_id)
                return self._send_json(201, {"data": {"card_number": card_number, "card_holder": card_holder, "bank_name": bank_name}})

            if path == "/api/v1/admin/events":
                if not self._is_admin():
                    return self._send_json(401, {"error": "unauthorized"})
                body = self._read_json_body()
                title = body.get("title")
                if not title:
                    return self._send_json(400, {"error": "validation", "details": "title is required"})
                event_id = events_repo.create_event(
                    title=title, description=body.get("description", ""),
                    icon=body.get("icon", "🎭"), calendar_type=body.get("calendar_type", "jalali"),
                    address=body.get("address", ""), ticket_price=body.get("price"),
                    currency=body.get("currency", "تومان"),
                    is_active=bool(body.get("is_active", True)),
                )
                if any(k in body for k in ("title_en", "description_en", "location", "location_en", "poster", "gallery", "video", "contact_phone", "contact_telegram")):
                    fields = {k: body[k] for k in ("title_en", "description_en", "location", "location_en", "poster", "video", "contact_phone", "contact_telegram") if k in body}
                    if "gallery" in body and isinstance(body["gallery"], list):
                        fields["gallery"] = json.dumps(body["gallery"], ensure_ascii=False)
                    events_repo.update_event_fields(event_id, **fields)
                return self._send_json(201, {"data": _event_public(events_repo.get_event(event_id))})

            if path == "/api/v1/admin/upload":
                if not self._is_admin():
                    return self._send_json(401, {"error": "unauthorized"})
                body = self._read_json_body()
                data_url = body.get("data")
                kind = body.get("kind") if body.get("kind") in ("poster", "gallery", "video", "portfolio") else "gallery"
                if not data_url or not isinstance(data_url, str) or not data_url.startswith("data:"):
                    return self._send_json(400, {"error": "validation", "details": "data must be a base64 data URL"})
                match = re.match(r"^data:([^;]+);base64,(.*)$", data_url, re.S)
                if not match:
                    return self._send_json(400, {"error": "validation", "details": "malformed data URL"})
                mime, b64 = match.group(1), match.group(2)
                ext_map = {
                    "image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "image/gif": ".gif",
                    "video/mp4": ".mp4", "video/webm": ".webm",
                }
                ext = ext_map.get(mime, ".bin")
                import base64, time, random
                safe_name = f"{int(time.time() * 1000)}-{random.randint(1000, 9999)}{ext}"
                upload_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "media", kind)
                os.makedirs(upload_dir, exist_ok=True)
                with open(os.path.join(upload_dir, safe_name), "wb") as f:
                    f.write(base64.b64decode(b64))
                return self._send_json(201, {"data": {"path": f"media/{kind}/{safe_name}", "kind": kind}})

            if path == "/api/v1/admin/sessions":
                if not self._is_admin():
                    return self._send_json(401, {"error": "unauthorized"})
                body = self._read_json_body()
                required = ("event_id", "date", "time", "capacity")
                if not all(k in body for k in required):
                    return self._send_json(400, {"error": "validation", "details": f"required: {required}"})
                if sessions_repo.slot_exists(body["event_id"], body["date"], body["time"]):
                    return self._send_json(409, {"error": "duplicate_slot"})
                session_id = sessions_repo.create_session(
                    body["event_id"], body["date"], body["time"], body["capacity"],
                )
                return self._send_json(201, {"data": _session_public(sessions_repo.get_session(session_id))})

            # ---------------- Phase 4: customer OTP login ----------------
            if path == "/api/v1/auth/customer/request-otp":
                body = self._read_json_body()
                phone = str(body.get("phone", ""))
                client_ip = self.client_address[0] if self.client_address else "unknown"
                rate_key = f"otp:{client_ip}:{normalize_phone(phone) if phone else phone}"
                if _rate_limited(rate_key):
                    return self._send_json(429, {"error": "too_many_attempts", "details": "try again later"})
                _record_login_attempt(rate_key)
                if not phone or not is_valid_iranian_mobile(normalize_phone(phone)):
                    return self._send_json(400, {"error": "validation", "details": "valid phone is required"})
                result = customer_auth_service.request_otp(phone)
                if result.get("error"):
                    return self._send_json(400, {"error": result["error"]})
                return self._send_json(200, {"data": result})

            if path == "/api/v1/auth/customer/verify-otp":
                body = self._read_json_body()
                phone = str(body.get("phone", ""))
                code = str(body.get("code", ""))
                client_ip = self.client_address[0] if self.client_address else "unknown"
                rate_key = f"otp-verify:{client_ip}:{normalize_phone(phone) if phone else phone}"
                if _rate_limited(rate_key):
                    return self._send_json(429, {"error": "too_many_attempts", "details": "try again later"})
                if not phone or not code:
                    return self._send_json(400, {"error": "validation", "details": "phone and code are required"})
                user = customer_auth_service.verify_otp(phone, code)
                if not user:
                    _record_login_attempt(rate_key)
                    return self._send_json(401, {"error": "invalid_code"})
                access_token = create_token({"user_id": user["id"], "role": "customer", "type": "access"}, ACCESS_TOKEN_TTL_SECONDS)
                refresh_token = create_token({"user_id": user["id"], "role": "customer", "type": "refresh"}, REFRESH_TOKEN_TTL_SECONDS)
                return self._send_json(200, {"data": {
                    "access_token": access_token, "refresh_token": refresh_token,
                    "expires_in": ACCESS_TOKEN_TTL_SECONDS,
                    "full_name": user.get("full_name"), "phone": user.get("phone"),
                }})

            if path == "/api/v1/auth/customer/refresh":
                body = self._read_json_body()
                refresh_token = body.get("refresh_token", "")
                payload = verify_token(refresh_token)
                if not payload or payload.get("type") != "refresh" or payload.get("role") != "customer":
                    return self._send_json(401, {"error": "invalid_refresh_token"})
                access_token = create_token({"user_id": payload["user_id"], "role": "customer", "type": "access"}, ACCESS_TOKEN_TTL_SECONDS)
                return self._send_json(200, {"data": {"access_token": access_token, "expires_in": ACCESS_TOKEN_TTL_SECONDS}})

            # ---------------- Phase 5: messaging ----------------
            if path == "/api/v1/account/messages":
                payload = self._get_customer_payload()
                if not payload:
                    return self._send_json(401, {"error": "unauthorized"})
                body = self._read_json_body()
                text = str(body.get("body", "")).strip()
                if not text:
                    return self._send_json(400, {"error": "validation", "details": "body is required"})
                if len(text) > 4000:
                    return self._send_json(400, {"error": "validation", "details": "message too long"})
                msg = messages_repo.add_message(payload["user_id"], "customer", text)
                return self._send_json(201, {"data": _message_public(msg)})

            m = re.match(r"^/api/v1/admin/messages/(\d+)$", path)
            if m:
                if not self._is_admin():
                    return self._send_json(401, {"error": "unauthorized"})
                user_id = int(m.group(1))
                body = self._read_json_body()
                text = str(body.get("body", "")).strip()
                if not text:
                    return self._send_json(400, {"error": "validation", "details": "body is required"})
                admin_payload = self._get_admin_payload()
                msg = messages_repo.add_message(user_id, "admin", text, admin_id=admin_payload.get("admin_id"))
                # Best-effort notify the customer's Telegram if they're
                # linked — same durable outbox pattern as OTP delivery, so
                # a bot outage never loses the message, only delays the ping.
                from database.connection import get_connection
                with get_connection() as conn:
                    row = conn.execute("SELECT telegram_id FROM users WHERE id=?", (user_id,)).fetchone()
                if row and row["telegram_id"]:
                    from database.repositories import bot_outbox as outbox_repo
                    outbox_repo.enqueue(row["telegram_id"], f"💬 پیام جدید از پشتیبانی خانه ماورا:\n\n{text}")
                return self._send_json(201, {"data": _message_public(msg)})

            # ---------------- New scope: team directory (admin write) ----
            if path == "/api/v1/admin/team":
                if not self._is_admin():
                    return self._send_json(401, {"error": "unauthorized"})
                body = self._read_json_body()
                if not body.get("full_name"):
                    return self._send_json(400, {"error": "validation", "details": "full_name is required"})
                member_id = team_repo.create(**body)
                return self._send_json(201, {"data": team_repo.get(member_id)})

            # ---------------- Phase 6: ticket verification / check-in ----
            if path == "/api/v1/admin/tickets/verify":
                if not self._is_admin():
                    return self._send_json(401, {"error": "unauthorized"})
                body = self._read_json_body()
                code = verify_signed_code(str(body.get("payload", "")))
                if not code:
                    return self._send_json(400, {"error": "invalid_signature", "details": "QR payload does not match a real ticket"})
                reservation = reservations_repo.get_by_code(code)
                if not reservation:
                    return self._send_json(404, {"error": "not_found"})
                return self._send_json(200, {"data": {
                    "reservation": _reservation_public(reservation),
                    "checked_in_at": reservation.get("checked_in_at"),
                }})

            if path == "/api/v1/admin/tickets/checkin":
                if not self._is_admin():
                    return self._send_json(401, {"error": "unauthorized"})
                body = self._read_json_body()
                code = verify_signed_code(str(body.get("payload", "")))
                if not code:
                    return self._send_json(400, {"error": "invalid_signature"})
                reservation = reservations_repo.get_by_code(code)
                if not reservation:
                    return self._send_json(404, {"error": "not_found"})
                if reservation["status"] != "approved":
                    return self._send_json(409, {"error": "not_confirmed", "details": "reservation is not an approved ticket"})
                newly_checked_in = reservations_repo.set_checked_in(reservation["id"])
                return self._send_json(200, {"data": {
                    "already_checked_in": not newly_checked_in,
                    "reservation": _reservation_public(reservations_repo.get_reservation(reservation["id"])),
                }})

            return self._send_json(404, {"error": "not_found"})
        except Exception as exc:
            logger.exception("API POST error on %s", path)
            return self._send_json(500, {"error": "internal_error", "details": str(exc)})

    def do_PATCH(self):
        parsed = urlparse(self.path)
        path = parsed.path
        try:
            m = re.match(r"^/api/v1/admin/events/(\d+)$", path)
            if m:
                if not self._is_admin():
                    return self._send_json(401, {"error": "unauthorized"})
                event_id = int(m.group(1))
                body = self._read_json_body()
                fields = dict(body)
                if "gallery" in fields and isinstance(fields["gallery"], list):
                    fields["gallery"] = json.dumps(fields["gallery"], ensure_ascii=False)
                if "is_active" in fields:
                    events_repo.set_event_active(event_id, bool(fields.pop("is_active")))
                updated = events_repo.update_event_fields(event_id, **fields)
                if not updated:
                    return self._send_json(404, {"error": "not_found"})
                return self._send_json(200, {"data": _event_public(updated)})
            m = re.match(r"^/api/v1/admin/sessions/(\d+)$", path)
            if m:
                if not self._is_admin():
                    return self._send_json(401, {"error": "unauthorized"})
                session_id = int(m.group(1))
                body = self._read_json_body()
                if "status" in body:
                    sessions_repo.set_session_status(session_id, body["status"])
                if "capacity" in body:
                    sessions_repo.update_capacity(session_id, body["capacity"])
                updated = sessions_repo.get_session(session_id)
                if not updated:
                    return self._send_json(404, {"error": "not_found"})
                return self._send_json(200, {"data": _session_public(updated)})
            m = re.match(r"^/api/v1/admin/portfolio/(\d+)$", path)
            if m:
                if not self._is_admin():
                    return self._send_json(401, {"error": "unauthorized"})
                item_id = int(m.group(1))
                body = self._read_json_body()
                updated = portfolio_repo.update(item_id, **body)
                if not updated:
                    return self._send_json(404, {"error": "not_found"})
                return self._send_json(200, {"data": updated})
            m = re.match(r"^/api/v1/admin/team/(\d+)$", path)
            if m:
                if not self._is_admin():
                    return self._send_json(401, {"error": "unauthorized"})
                member_id = int(m.group(1))
                body = self._read_json_body()
                updated = team_repo.update(member_id, **body)
                if not updated:
                    return self._send_json(404, {"error": "not_found"})
                return self._send_json(200, {"data": updated})
            return self._send_json(404, {"error": "not_found"})
        except Exception as exc:
            logger.exception("API PATCH error on %s", path)
            return self._send_json(500, {"error": "internal_error", "details": str(exc)})

    def do_DELETE(self):
        parsed = urlparse(self.path)
        path = parsed.path
        try:
            m = re.match(r"^/api/v1/admin/sessions/(\d+)$", path)
            if m:
                if not self._is_admin():
                    return self._send_json(401, {"error": "unauthorized"})
                sessions_repo.delete_session(int(m.group(1)))
                return self._send_json(200, {"data": {"deleted": True}})
            m = re.match(r"^/api/v1/admin/portfolio/(\d+)$", path)
            if m:
                if not self._is_admin():
                    return self._send_json(401, {"error": "unauthorized"})
                portfolio_repo.delete(int(m.group(1)))
                return self._send_json(200, {"data": {"deleted": True}})
            m = re.match(r"^/api/v1/admin/team/(\d+)$", path)
            if m:
                if not self._is_admin():
                    return self._send_json(401, {"error": "unauthorized"})
                team_repo.delete(int(m.group(1)))
                return self._send_json(200, {"data": {"deleted": True}})
            return self._send_json(404, {"error": "not_found"})
        except Exception as exc:
            logger.exception("API DELETE error on %s", path)
            return self._send_json(500, {"error": "internal_error", "details": str(exc)})


def main():
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    logger.info("Mavara unified API listening on :%d", PORT)
    print(f"[mavara-api] listening on :{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == "__main__":
    main()
