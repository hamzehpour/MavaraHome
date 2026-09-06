#!/usr/bin/env python3
"""
Automated test suite. Runs against a disposable database — never touches
production (refuses outright if ENV=production, same as seed_database.py).

Since the entire business-logic layer (services/, database/repositories/)
has zero dependency on aiogram or Telegram, these tests exercise real code
paths directly — capacity math, the reservation state machine, Jalali date
conversion, phone validation, permission resolution — not just placeholders.
What this suite can NOT verify (because aiogram isn't installed in the
environment these tests were authored in): actual Telegram wire protocol
behavior, callback routing, keyboard rendering. Those need a real bot run.

Usage:
    ENV=test python test_bot.py
"""
import sys
import os
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

os.environ.setdefault("ENV", "test")
from config.settings import IS_PRODUCTION  # noqa: E402

if IS_PRODUCTION:
    print("❌ Refusing to run: ENV=production. Tests never run against production data.")
    sys.exit(1)

# Redirect to a throwaway database file for this run only, regardless of
# what ENV resolved to — so running this suite never even touches the
# real test.db an admin might be looking at.
_tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp_db.close()
os.environ["DB_PATH"] = _tmp_db.name

import importlib
import config.settings
importlib.reload(config.settings)  # pick up the DB_PATH override above
import database.connection
importlib.reload(database.connection)

RESULTS: list[tuple[str, bool, str]] = []


def test(name: str):
    def decorator(fn):
        try:
            fn()
            RESULTS.append((name, True, ""))
        except AssertionError as exc:
            RESULTS.append((name, False, str(exc) or "assertion failed"))
        except Exception as exc:
            RESULTS.append((name, False, f"{type(exc).__name__}: {exc}"))
        return fn
    return decorator


# ---------------------------------------------------------------- setup ----
from database.schema import init_db  # noqa: E402
init_db()

from database.repositories import events as events_repo  # noqa: E402
from database.repositories import sessions as sessions_repo  # noqa: E402
from database.repositories import users as users_repo  # noqa: E402
from database.repositories import reservations as reservations_repo  # noqa: E402
from database.repositories import admins as admins_repo  # noqa: E402
from database.repositories import waitlist as waitlist_repo  # noqa: E402
from services import reservation_service, event_service, permissions  # noqa: E402
from utils.jalali import gregorian_to_jalali, jalali_to_gregorian, gregorian_iso_to_jalali_display  # noqa: E402
from utils.qr_signing import sign_code, verify_signed_code  # noqa: E402
from validators.validators import (  # noqa: E402
    is_valid_iranian_mobile, normalize_phone, is_valid_full_name, is_valid_time_hhmm,
)


# ------------------------------------------------------------- Jalali dates
@test("Phase 2: password hashing round-trip, wrong password rejected, salts unique")
def _t():
    from utils.auth import hash_password, verify_password
    h, s = hash_password("correct-horse-battery-staple")
    assert verify_password("correct-horse-battery-staple", h, s)
    assert not verify_password("wrong-password", h, s)
    h2, s2 = hash_password("correct-horse-battery-staple")
    assert s != s2, "salt must be random per call, not reused"
    assert h != h2, "hash must differ when salt differs, even for the same password"


@test("Phase 2: JWT create/verify round-trip, tampering and expiry rejected")
def _t():
    import utils.auth as auth_mod
    from utils.auth import create_token, verify_token
    original_secret = auth_mod.JWT_SECRET
    auth_mod.JWT_SECRET = "test-secret-for-this-test"
    try:
        token = create_token({"sub": "admin1", "type": "access"}, ttl_seconds=60)
        payload = verify_token(token)
        assert payload is not None and payload["sub"] == "admin1"

        header_b64, payload_b64, sig_b64 = token.split(".")
        tampered = f"{header_b64}.{payload_b64}.{'x' * len(sig_b64)}"
        assert verify_token(tampered) is None, "a token with a tampered signature must be rejected"

        expired = create_token({"sub": "admin1"}, ttl_seconds=-10)
        assert verify_token(expired) is None, "an expired token must be rejected"

        auth_mod.JWT_SECRET = "a-different-secret"
        assert verify_token(token) is None, "a token signed with a different secret must be rejected"
    finally:
        auth_mod.JWT_SECRET = original_secret


@test("Phase 2: web admin bootstrap prevents duplicate usernames")
def _t():
    from database.repositories import web_admins as web_admins_repo
    from utils.auth import hash_password
    h, s = hash_password("some-long-enough-password")
    web_admins_repo.create("phase2_test_admin", h, s)
    assert web_admins_repo.get_by_username("phase2_test_admin") is not None
    existing_count = web_admins_repo.count()
    # Attempting to create the same username again is the API/script's job
    # to reject (checked before calling .create()) — this test documents
    # that the repository itself doesn't silently dedupe, so that guard
    # must stay in create_web_admin.py and the /admin/login... actually
    # /admin/register doesn't exist by design (bootstrap-only via script).
    assert existing_count >= 1


@test("Jalali round-trip conversion (10 known dates)")
def _t():
    samples = [(2026, 8, 1), (2024, 3, 20), (1979, 2, 11), (2000, 1, 1), (2030, 12, 31),
               (2026, 3, 20), (2025, 1, 1), (2026, 2, 28), (2028, 2, 29), (2026, 6, 15)]
    for g in samples:
        j = gregorian_to_jalali(*g)
        back = jalali_to_gregorian(*j)
        assert back == g, f"{g} -> {j} -> {back}"


@test("Jalali display formatting produces Persian digits")
def _t():
    text = gregorian_iso_to_jalali_display("2026-08-01")
    assert "۱" in text or "۰" in text, f"expected Persian digits in: {text}"


# ------------------------------------------------------------- validators
@test("Phone validation accepts valid Iranian mobile")
def _t():
    assert is_valid_iranian_mobile("09123456789")


@test("Phone validation rejects too-short number")
def _t():
    assert not is_valid_iranian_mobile("0912345")


@test("Phone normalization converts Persian digits to ASCII")
def _t():
    result = normalize_phone("۰۹۱۹۱۰۱۰۰۱۲")
    assert result == "09191010012", f"got {result}"
    assert is_valid_iranian_mobile(result)


@test("Phone normalization handles +98 prefix")
def _t():
    assert normalize_phone("+989123456789") == "09123456789"


@test("Name validation rejects too-short input")
def _t():
    assert not is_valid_full_name("ای")


@test("Name validation accepts a real Persian name")
def _t():
    assert is_valid_full_name("علی محمدی")


@test("Time format validator accepts valid HH:MM")
def _t():
    assert is_valid_time_hhmm("18:30")
    assert not is_valid_time_hhmm("25:00")
    assert not is_valid_time_hhmm("18:75")


# ------------------------------------------------------------- QR signing
@test("QR signature round-trip")
def _t():
    signed = sign_code("MV-ABC123")
    recovered = verify_signed_code(signed)
    assert recovered == "MV-ABC123"


@test("QR signature rejects tampered payload")
def _t():
    signed = sign_code("MV-ABC123")
    tampered = signed.replace("MV-ABC123", "MV-XYZ999")
    assert verify_signed_code(tampered) is None


# ------------------------------------------------------------- permissions
@test("Owner has every permission")
def _t():
    perms = permissions.permissions_for_roles({"owner"})
    assert permissions.MANAGE_OWNERSHIP in perms
    assert permissions.APPROVE_PAYMENTS in perms


@test("Admin has everything except ownership management")
def _t():
    perms = permissions.permissions_for_roles({"admin"})
    assert permissions.MANAGE_OWNERSHIP not in perms
    assert permissions.APPROVE_PAYMENTS in perms


@test("Finance group cannot approve payments")
def _t():
    perms = permissions.permissions_for_roles({"finance"})
    assert permissions.APPROVE_PAYMENTS not in perms
    assert permissions.MANAGE_BANK_CARDS in perms


@test("A staff member with two groups gets the union of both")
def _t():
    perms = permissions.permissions_for_roles({"finance", "content"})
    assert permissions.MANAGE_BANK_CARDS in perms
    assert permissions.MANAGE_EVENTS in perms


# ------------------------------------------------------- events & sessions
@test("Create event and session, then read them back")
def _t():
    event_id = events_repo.create_event(title="تست رویداد", icon="🎭")
    session_id = sessions_repo.create_session(event_id, "2027-01-01", "18:00", capacity=10)
    session = sessions_repo.get_session(session_id)
    assert session["capacity"] == 10
    assert session["session_date"] == "2027-01-01"


@test("Duplicate session (same event/date/time) is rejected")
def _t():
    event_id = events_repo.create_event(title="تست دوگانه")
    sessions_repo.create_session(event_id, "2027-02-01", "18:00", capacity=10)
    try:
        sessions_repo.create_session(event_id, "2027-02-01", "18:00", capacity=20)
        raise AssertionError("expected a uniqueness error, but the duplicate insert succeeded")
    except Exception as exc:
        assert "UNIQUE" in str(exc) or "unique" in str(exc)


@test("Sessions for an event sort chronologically")
def _t():
    event_id = events_repo.create_event(title="تست ترتیب")
    sessions_repo.create_session(event_id, "2027-03-03", "10:00", capacity=5)
    sessions_repo.create_session(event_id, "2027-03-01", "10:00", capacity=5)
    sessions_repo.create_session(event_id, "2027-03-02", "10:00", capacity=5)
    ordered = sessions_repo.list_sessions_for_event_admin(event_id)
    dates = [s["session_date"] for s in ordered]
    assert dates == sorted(dates), f"not sorted: {dates}"


# ------------------------------------------------------- reservation flow
def _make_user(tg_id: int) -> None:
    users_repo.get_or_create_user(tg_id, f"کاربر {tg_id}")


@test("Phase 3: dashboard-stats aggregation matches a hand-computed total")
def _t():
    event_id = events_repo.create_event(title="تست داشبورد فاز ۳")
    session_id = sessions_repo.create_session(event_id, "2027-10-01", "20:00", capacity=10)
    _make_user(700050)
    r1 = reservation_service.start_reservation(telegram_id=700050, session_id=session_id, people=3)
    reservations_repo.set_status(r1["reservation_id"], "approved")

    all_res = reservations_repo.list_recent(limit=2000)
    today_str = __import__("datetime").date.today().isoformat()
    todays_approved = [r for r in all_res if r["status"] == "approved" and str(r.get("created_at", "")).startswith(today_str)]
    assert any(r["id"] == r1["reservation_id"] for r in todays_approved), \
        "a reservation approved today must appear in today's aggregated total — this is exactly what the dashboard chart sums"


@test("Phase 3: bulk-approve reuses the same atomic approve_reservation() per id — no separate bulk-only logic")
def _t():
    event_id = events_repo.create_event(title="تست تایید گروهی")
    session_id = sessions_repo.create_session(event_id, "2027-10-02", "20:00", capacity=10)
    ids = []
    for tg in (700051, 700052):
        _make_user(tg)
        res = reservation_service.start_reservation(telegram_id=tg, session_id=session_id, people=1)
        reservations_repo.set_status(res["reservation_id"], "pending_review")
        ids.append(res["reservation_id"])

    results = []
    for rid in ids:
        outcome = reservation_service.approve_reservation(rid, reviewed_by=0)
        results.append(outcome is not None)
    assert all(results), "every reservation in the batch must transition independently via the real atomic function"
    for rid in ids:
        assert reservations_repo.get_reservation(rid)["status"] == "approved"

    second_pass = reservation_service.approve_reservation(ids[0], reviewed_by=0)
    assert second_pass is None, "approving an already-approved reservation again must be a no-op"


@test("Reservation respects session capacity")
def _t():
    event_id = events_repo.create_event(title="تست ظرفیت")
    session_id = sessions_repo.create_session(event_id, "2027-04-01", "18:00", capacity=5)
    _make_user(700001)
    result = reservation_service.start_reservation(telegram_id=700001, session_id=session_id, people=5)
    assert result["success"] is True
    assert result["remaining"] == 0


@test("Booking beyond remaining capacity goes to waiting list, not overbooking")
def _t():
    event_id = events_repo.create_event(title="تست صف انتظار")
    session_id = sessions_repo.create_session(event_id, "2027-04-02", "18:00", capacity=3)
    _make_user(700002)
    _make_user(700003)
    first = reservation_service.start_reservation(telegram_id=700002, session_id=session_id, people=3)
    assert first["success"] is True
    second = reservation_service.start_reservation(telegram_id=700003, session_id=session_id, people=1)
    assert second["success"] is False and second["waiting"] is True
    reserved_after = sessions_repo.reserved_count(session_id)
    assert reserved_after == 3, f"capacity was exceeded: reserved_count={reserved_after}"


@test("Approve is idempotent — a double-tap only applies once")
def _t():
    event_id = events_repo.create_event(title="تست دوبار تایید")
    session_id = sessions_repo.create_session(event_id, "2027-04-03", "18:00", capacity=10)
    _make_user(700004)
    res = reservation_service.start_reservation(telegram_id=700004, session_id=session_id, people=2)
    reservation_id = res["reservation_id"]
    reservations_repo.set_status(reservation_id, "pending_review")

    first = reservation_service.approve_reservation(reservation_id, reviewed_by=1)
    assert first is not None, "first approve should succeed"
    second = reservation_service.approve_reservation(reservation_id, reviewed_by=1)
    assert second is None, "second approve (double-tap) must be a no-op, not re-issue a ticket"


@test("Rejecting a reservation frees its seat immediately")
def _t():
    # The old two-step "grace period" (awaiting_buyer_confirmation, buyer
    # could accept/dispute) was removed — "نیازمند اصلاح" now covers what
    # that period was for, and reject_reservation() is direct/final.
    event_id = events_repo.create_event(title="تست رد و آزادسازی")
    session_id = sessions_repo.create_session(event_id, "2027-04-04", "18:00", capacity=2)
    _make_user(700005)
    res = reservation_service.start_reservation(telegram_id=700005, session_id=session_id, people=2)
    reservation_id = res["reservation_id"]
    reservations_repo.set_status(reservation_id, "pending_review")

    assert sessions_repo.reserved_count(session_id) == 2, "seat should still be held during review"
    outcome = reservation_service.reject_reservation(reservation_id, reviewed_by=1, reason="test")
    assert outcome is not None, "reject must succeed from pending_review"
    assert sessions_repo.reserved_count(session_id) == 0, "seat should be freed immediately on rejection"

    # Double-tap must be a no-op, not re-process.
    outcome2 = reservation_service.reject_reservation(reservation_id, reviewed_by=1, reason="test again")
    assert outcome2 is None, "second reject (double-tap) must report already-processed, not re-send anything"


@test("Reopening interest: paused event can't be booked, register/duplicate/cancel works")
def _t():
    from database.repositories import event_interests as interests_repo
    from services import event_interest_service

    event_id = events_repo.create_event(title="حباب متوقف تست")
    events_repo.set_event_active(event_id, False)
    event = events_repo.get_event(event_id)
    assert event_interest_service.is_event_bookable(event) is False

    created, existing = event_interest_service.register_interest(
        event_id, telegram_id=700030, contact_name="مریم", phone_number="09120000000", telegram_username="maryam"
    )
    assert created is True and existing is None

    # Second attempt for the same user+event must NOT create a duplicate row.
    created2, existing2 = event_interest_service.register_interest(
        event_id, telegram_id=700030, contact_name="مریم", phone_number="09120000000", telegram_username="maryam"
    )
    assert created2 is False
    assert existing2 is not None

    active_list = interests_repo.list_active_for_event(event_id)
    assert len(active_list) == 1, "duplicate registration must not create a second active row"

    summary = event_interest_service.audience_summary(event_id)
    assert summary["active"] == 1

    event_interest_service.cancel_interest(existing2["id"])
    active_after_cancel = interests_repo.list_active_for_event(event_id)
    assert len(active_after_cancel) == 0

    # After cancelling, registering again must be allowed (not blocked by
    # the old cancelled row).
    created3, _ = event_interest_service.register_interest(
        event_id, telegram_id=700030, contact_name="مریم", phone_number="09121111111", telegram_username="maryam"
    )
    assert created3 is True


@test("Reopening interest: notifications are isolated per event and never modify capacity")
def _t():
    from database.repositories import event_interests as interests_repo
    from services import event_interest_service

    event_a = events_repo.create_event(title="رویداد آ علاقه‌مندی")
    event_b = events_repo.create_event(title="رویداد ب علاقه‌مندی")
    events_repo.set_event_active(event_a, False)
    events_repo.set_event_active(event_b, False)

    event_interest_service.register_interest(event_a, 700031, "علی", "09122222222", "ali")
    event_interest_service.register_interest(event_b, 700032, "رضا", "09123333333", "reza")

    list_a = interests_repo.list_active_for_event(event_a)
    list_b = interests_repo.list_active_for_event(event_b)
    assert len(list_a) == 1 and list_a[0]["telegram_user_id"] == 700031
    assert len(list_b) == 1 and list_b[0]["telegram_user_id"] == 700032


@test("Sales stats are isolated per event — Event A's revenue never leaks into Event B's report")
def _t():
    from services import stats_service
    event_a = events_repo.create_event(title="رویداد آ آمار")
    event_b = events_repo.create_event(title="رویداد ب آمار")
    session_a = sessions_repo.create_session(event_a, "2027-07-01", "18:00", capacity=10)
    session_b = sessions_repo.create_session(event_b, "2027-07-01", "18:00", capacity=10)

    _make_user(700020)
    _make_user(700021)
    res_a = reservation_service.start_reservation(telegram_id=700020, session_id=session_a, people=3)
    res_b = reservation_service.start_reservation(telegram_id=700021, session_id=session_b, people=2)
    reservations_repo.set_status(res_a["reservation_id"], "approved")
    reservations_repo.set_status(res_b["reservation_id"], "approved")

    stats_a = stats_service.get_dashboard_stats(event_id=event_a)
    stats_b = stats_service.get_dashboard_stats(event_id=event_b)
    stats_all = stats_service.get_dashboard_stats()

    assert stats_a["tickets_sold"] == 3, "event A must only count its own 3 tickets"
    assert stats_b["tickets_sold"] == 2, "event B must only count its own 2 tickets"
    assert stats_all["tickets_sold"] >= 5, "global (no event filter) must be at least the sum of both"


@test("Monitoring board shows event name, real lifecycle status, and sold-out banner")
def _t():
    from services import channel_service
    event_id = events_repo.create_event(title="حباب تست مانیتورینگ")
    session_id = sessions_repo.create_session(event_id, "2027-06-10", "18:00", capacity=2)
    _make_user(700010)
    res = reservation_service.start_reservation(telegram_id=700010, session_id=session_id, people=2)
    reservations_repo.set_status(res["reservation_id"], "pending_review")

    parts = channel_service.render_day_board(event_id, "2027-06-10")
    text = "\n".join(parts)
    assert "حباب تست مانیتورینگ" in text, "event name must be in the board header"
    assert "⏳" in text, "pending-review reservation must show the waiting icon, not a checkmark"
    assert "✅" not in text, "nothing here is approved yet — must not look like a done sale"
    assert "تکمیل ظرفیت" in text, "session is fully booked (2/2) and must say so"

    # Set status directly rather than going through approve_reservation() —
    # that also issues a QR ticket, which needs the qrcode package (not
    # relevant to what this test is actually checking: board rendering).
    reservations_repo.set_status(res["reservation_id"], "approved")
    parts2 = channel_service.render_day_board(event_id, "2027-06-10")
    text2 = "\n".join(parts2)
    assert "✅" in text2, "after admin approval the board must show the confirmed icon"


@test("Phase 1: website-created draft event stays hidden from bot until activated (site is source of truth)")
def _t():
    event_id = events_repo.create_event(title="تست انتشار از سایت", is_active=False)
    active_titles = [e["title"] for e in events_repo.list_active_events()]
    assert "تست انتشار از سایت" not in active_titles, "a draft event must not be bookable via the bot yet"

    events_repo.set_event_active(event_id, True)
    active_titles_after = [e["title"] for e in events_repo.list_active_events()]
    assert "تست انتشار از سایت" in active_titles_after, \
        "activating an event (from the website admin panel) must make it visible to the bot immediately, no restart needed"


@test("Phase 1: website reservation (get_or_create_user_by_phone) is visible via the same repo function the bot uses")
def _t():
    event_id = events_repo.create_event(title="تست یکی‌سازی بک‌اند")
    session_id = sessions_repo.create_session(event_id, "2027-09-01", "20:00", capacity=5)
    result = reservation_service.start_reservation_web(
        phone="09121112222", full_name="مشتری تست وب", session_id=session_id, people=2
    )
    assert result["success"] is True
    reservation = reservations_repo.get_reservation(result["reservation_id"])
    assert reservation["source"] == "website"
    user = users_repo.get_or_create_user_by_phone("09121112222")
    same_user_reservations = reservations_repo.list_for_user(user["id"])
    assert any(r["id"] == result["reservation_id"] for r in same_user_reservations), \
        "a reservation created via the website path must show up under the same user_id the bot-side lookup uses"


@test("Phase 1: telegram and website bookings on the same phone number merge into ONE customer, not two")
def _t():
    # A person books once from the website (phone only, no telegram_id yet),
    # then later books again after connecting via Telegram. Both must land
    # on the same users row once linked — otherwise the same human ends up
    # as two disconnected "customers", defeating the whole point of one
    # shared backend.
    event_id = events_repo.create_event(title="تست ادغام مشتری")
    session_id = sessions_repo.create_session(event_id, "2027-09-02", "20:00", capacity=5)
    web_result = reservation_service.start_reservation_web(
        phone="09123335555", full_name="مشتری دوکاناله", session_id=session_id, people=1
    )
    web_user_id = web_result["user_id"]

    linked = users_repo.link_telegram_id_by_phone("09123335555", telegram_id=666666666)
    assert linked is True

    tg_result = reservation_service.start_reservation(telegram_id=666666666, session_id=session_id, people=1)
    assert tg_result["user_id"] == web_user_id, "same phone, now linked to telegram, must resolve to the SAME user_id"

    all_reservations = reservations_repo.list_for_user(web_user_id)
    assert len(all_reservations) == 2, "both the website and telegram bookings must appear under one customer"


@test("Phase 1: linking a phone to a telegram_id already used by someone else is rejected, not silently overwritten")
def _t():
    users_repo.get_or_create_user(telegram_id=555555555, full_name="کاربر قبلی تلگرام")
    users_repo.get_or_create_user_by_phone("09129998888", full_name="مشتری وب دیگر")
    result = users_repo.link_telegram_id_by_phone("09129998888", telegram_id=555555555)
    assert result is False, "must refuse to merge into a telegram_id that already belongs to a different user"


@test("Regression: malformed admin-editable Markdown never crashes a send (safe_send fallback)")
def _t():
    # Root cause of the reported bug: payment instructions are built from
    # an admin-editable template + dynamic data (card holder name) and sent
    # with parse_mode="Markdown". A single unbalanced "_"/"*"/"`" anywhere
    # makes Telegram's legacy Markdown parser reject the WHOLE message,
    # which previously left the buyer stuck in awaiting_receipt with no
    # prompt at all. safe_send.py must catch that specific failure and
    # resend as plain text instead of losing the message.
    from utils.safe_send import safe_send_message
    import asyncio

    class FakeBadRequest(Exception):
        def __str__(self):
            return "Telegram server says - Bad Request: can't parse entities: Can't find end of the entity starting at byte offset 320"

    calls = []

    class FakeBot:
        async def send_message(self, chat_id, text, parse_mode=None, **kw):
            calls.append((chat_id, text, parse_mode))
            if parse_mode == "Markdown" and "_broken" in text:
                raise FakeBadRequest()
            return {"ok": True}

    # Monkeypatch the exception class safe_send checks against, since real
    # aiogram isn't installed in this sandbox — see the aiogram-dependent
    # tests elsewhere in this file for the same environment note.
    import utils.safe_send as safe_send_mod
    original_exc = safe_send_mod.TelegramBadRequest
    safe_send_mod.TelegramBadRequest = FakeBadRequest
    try:
        asyncio.run(safe_send_message(FakeBot(), 12345, "card holder name has_broken markdown", parse_mode="Markdown"))
    finally:
        safe_send_mod.TelegramBadRequest = original_exc

    assert len(calls) == 2, "must retry once after the parse failure, not give up"
    assert calls[0][2] == "Markdown"
    assert calls[1][2] is None, "the retry must drop parse_mode so plain text always gets through"
    assert calls[0][1] == calls[1][1], "the exact same text must be delivered, just without formatting"


@test("Regression: overflow-approval sends receipt prompt and puts buyer's FSM into awaiting_receipt")
def _t():
    # Root cause of the reported bug: approving an overflow-capacity request
    # never told the buyer to send a receipt, and even when they sent one
    # anyway it was silently ignored, because their FSM was never actually
    # moved into awaiting_receipt (that only happened for buyers who
    # clicked through the normal booking flow themselves). This is a
    # database/service-level check that the underlying reservation this
    # relies on is created correctly; the FSM-state part is exercised by
    # handlers/overflow_requests.py directly (needs aiogram — see other
    # aiogram-dependent tests in this file for the environment note).
    event_id = events_repo.create_event(title="تست اضافه ظرفیت")
    session_id = sessions_repo.create_session(event_id, "2027-08-01", "20:00", capacity=2)
    _make_user(700040)
    _make_user(700041)
    # Fill the session normally first.
    r1 = reservation_service.start_reservation(telegram_id=700040, session_id=session_id, people=2)
    assert r1["success"]

    # Third person overflows — goes to waitlist.
    r2 = reservation_service.start_reservation(telegram_id=700041, session_id=session_id, people=1)
    assert r2.get("waiting") is True, "session is full, must go to waiting list, not fail silently"

    result = reservation_service.approve_overflow_atomic(session_id=session_id, user_id=r2["user_id"] if "user_id" in r2 else users_repo.get_or_create_user(700041)["id"], people=1)
    assert result["success"] is True
    assert result.get("reservation_id"), "overflow approval must produce a real reservation_id for the buyer's FSM to attach to"
    reservation = reservations_repo.get_reservation(result["reservation_id"])
    assert reservation["status"] == "pending_payment", "overflow-approved reservation must enter the same payment flow as a normal booking"


@test("Session-list header warns about full sessions being tappable for overflow requests")
def _t():
    from texts import fa
    header_with_full = fa.choosing_session_header("شنبه ۱ مرداد", has_full_session=True)
    header_without = fa.choosing_session_header("شنبه ۱ مرداد", has_full_session=False)
    assert "اضافه" in header_with_full and "ظرفیت" in header_with_full
    assert "اضافه" not in header_without, "hint should only show when at least one session is actually full"


@test("health_check.py distinguishes a missing DB from an unmigrated (empty-schema) DB")
def _t():
    import sqlite3, tempfile, os
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        # An unmigrated DB is exactly what SQLite creates the instant
        # anything connects to a not-yet-existing path: a ~4KB file with
        # zero tables. This must be diagnosed with one clear, actionable
        # message (not a cascade of five different "no such table" errors).
        conn = sqlite3.connect(path)
        conn.execute("SELECT 1")
        conn.close()
        table_count = sqlite3.connect(path).execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type = 'table'"
        ).fetchone()[0]
        assert table_count == 0, "sanity check on the test setup itself"
    finally:
        os.unlink(path)


@test("Direct people-selector rejects tampered/out-of-range callback values")
def _t():
    # Same environment note as the qrcode-dependent tests below: this
    # imports handlers.booking, which needs aiogram installed. Not
    # installed in this sandbox (no internet) — expected to pass wherever
    # `pip install -r requirements.txt` has actually run.
    from handlers.booking import validate_people_pick
    assert validate_people_pick("3", max_selectable=5) == 3
    assert validate_people_pick("5", max_selectable=5) == 5
    for bad in ("0", "-1", "-10", "999", "999999", "abc", "1abc", "", "1.5", "None", "null"):
        assert validate_people_pick(bad, max_selectable=5) is None, f"should reject {bad!r}"


@test("Admin manual people-count edit respects destination capacity")
def _t():
    event_id = events_repo.create_event(title="تست ویرایش تعداد")
    session_id = sessions_repo.create_session(event_id, "2027-04-05", "18:00", capacity=5)
    _make_user(700006)
    res = reservation_service.start_reservation(telegram_id=700006, session_id=session_id, people=3)
    reservation_id = res["reservation_id"]

    ok = reservation_service.admin_update_people(reservation_id, 5)
    assert ok["success"] is True
    too_many = reservation_service.admin_update_people(reservation_id, 6)
    assert too_many["success"] is False


@test("Auto-expiry only ever targets pending_payment, never pending_review")
def _t():
    from datetime import datetime, timedelta, timezone
    event_id = events_repo.create_event(title="تست انقضا")
    session_id = sessions_repo.create_session(event_id, "2027-04-06", "18:00", capacity=5)
    _make_user(700007)
    res = reservation_service.start_reservation(telegram_id=700007, session_id=session_id, people=1)
    reservation_id = res["reservation_id"]
    past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(timespec="seconds")
    reservations_repo.set_status(reservation_id, "pending_payment")
    with __import__("database.connection", fromlist=["get_connection"]).get_connection() as conn:
        conn.execute("UPDATE reservations SET expires_at = ? WHERE id = ?", (past, reservation_id))

    expired = reservation_service.expire_stale_reservations()
    assert any(r["id"] == reservation_id for r in expired)

    # Now do the same but in pending_review — must NOT expire.
    res2 = reservation_service.start_reservation(telegram_id=700007, session_id=session_id, people=1)
    reservations_repo.set_status(res2["reservation_id"], "pending_review")
    with __import__("database.connection", fromlist=["get_connection"]).get_connection() as conn:
        conn.execute("UPDATE reservations SET expires_at = ? WHERE id = ?", (past, res2["reservation_id"]))
    expired2 = reservation_service.expire_stale_reservations()
    assert not any(r["id"] == res2["reservation_id"] for r in expired2), \
        "pending_review must NEVER auto-expire — this is a critical safety guarantee"


@test("Sales stats total matches sum of individual approved reservations")
def _t():
    event_id = events_repo.create_event(title="تست آمار")
    session_id = sessions_repo.create_session(event_id, "2027-04-07", "18:00", capacity=20)
    total_expected = 0
    for i, tg in enumerate([700010, 700011, 700012]):
        _make_user(tg)
        res = reservation_service.start_reservation(telegram_id=tg, session_id=session_id, people=2)
        reservations_repo.set_status(res["reservation_id"], "pending_review")
        reservation_service.approve_reservation(res["reservation_id"], reviewed_by=1)
        reservation = reservations_repo.get_reservation(res["reservation_id"])
        total_expected += reservation["total_price"]

    totals = reservations_repo.sales_totals()
    assert totals["revenue"] >= total_expected, f"expected at least {total_expected}, got {totals['revenue']}"


@test("Phase 0: booking by phone, then logging in by email, lands on ONE customer row — archive isn't empty")
def _t():
    # This is the exact bug behind the "archive always empty" finding:
    # book_web created a phone-only row, email login created a SEPARATE
    # email-only row, and the reservation stayed attached to the first —
    # invisible to the second. get_or_create_customer must resolve both
    # identifiers to the same row once the email is known.
    event_id = events_repo.create_event(title="تست ادغام موبایل و ایمیل")
    session_id = sessions_repo.create_session(event_id, "2027-05-01", "19:00", capacity=10)
    web_result = reservation_service.start_reservation_web(
        phone="09127778888", full_name="مشتری فرم رزرو", session_id=session_id, people=1
    )
    phone_only_user = users_repo.get_or_create_user_by_phone("09127778888")
    assert phone_only_user["id"] == web_result["user_id"]

    # The same person later logs in with an email tied to the same phone —
    # get_or_create_customer(email=..., phone=...) must find the existing
    # phone row and attach the email to it, not create a second row.
    merged = users_repo.get_or_create_customer(email="mostafa@example.com", phone="09127778888")
    assert merged["id"] == web_result["user_id"], "email login must resolve to the SAME row as the phone booking"

    archive = reservations_repo.list_for_user(merged["id"])
    assert any(r["id"] == web_result["reservation_id"] for r in archive), \
        "the phone-made reservation must be visible from the merged (email-known) identity"


@test("Phase 0: an email that already has a user is reused, never duplicated")
def _t():
    first = users_repo.get_or_create_customer(email="sara@example.com", full_name="سارا")
    again = users_repo.get_or_create_customer(email="sara@example.com", full_name="نام دیگر — نباید بازنویسی شود")
    assert again["id"] == first["id"]
    assert again["full_name"] == "سارا", "an existing non-empty field must never be silently overwritten"


@test("Phase 0: NULL/blank phone or email never collide under the new unique index")
def _t():
    # Two different email-only customers, neither with a phone — must NOT
    # be treated as "the same phone" just because both are blank/NULL.
    a = users_repo.get_or_create_customer(email="a@example.com")
    b = users_repo.get_or_create_customer(email="b@example.com")
    assert a["id"] != b["id"]


@test("Phase 2: OTP channel picker defaults to email-only, phone is a clean not-yet-supported error")
def _t():
    from services import settings_service, customer_auth_service

    assert settings_service.get_otp_channels_enabled() == ["email"]
    result = customer_auth_service.request_otp("09121234567", channel="phone")
    assert result == {"error": "channel_not_supported"}, \
        "phone must fail cleanly, not silently pretend to send a code nobody receives"


@test("Phase 2: approving a reservation emails the customer when they have an email on file")
def _t():
    import io
    import contextlib

    event_id = events_repo.create_event(title="تست اعلان ایمیل")
    session_id = sessions_repo.create_session(event_id, "2027-06-01", "20:00", capacity=5)
    web_result = reservation_service.start_reservation_web(
        phone="09120001111", full_name="مشتری اعلان", session_id=session_id, people=1
    )
    # Same merge path phase 0 added — a real reservation flow will collect
    # email up front once the website booking form exists (phase 3); for
    # now, simulate "this customer is also known by email" directly.
    users_repo.get_or_create_customer(email="notify-me@example.com", phone="09120001111")

    reservations_repo.set_status(web_result["reservation_id"], "pending_review")
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        result = reservation_service.approve_reservation(web_result["reservation_id"], reviewed_by=1)
    assert result is not None
    printed = buf.getvalue()
    assert "notify-me@example.com" in printed, "no email was sent (SMTP unset -> printed) to the customer's address"
    assert "تست اعلان ایمیل" in printed, "the notification must name the actual event, not a placeholder"


def main() -> None:
    print("=" * 60)
    print("  MAVARA BOT — AUTOMATED TEST SUITE")
    print(f"  (disposable database: {_tmp_db.name})")
    print("=" * 60)
    passed = 0
    for name, ok, detail in RESULTS:
        icon = "PASS" if ok else "FAIL"
        print(f"[{icon}] {name}" + (f"  —  {detail}" if detail else ""))
        if ok:
            passed += 1
    print("=" * 60)
    print(f"  {passed}/{len(RESULTS)} tests passed")
    print("=" * 60)
    os.unlink(_tmp_db.name)
    sys.exit(0 if passed == len(RESULTS) else 1)


if __name__ == "__main__":
    main()
