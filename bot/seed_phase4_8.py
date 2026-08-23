#!/usr/bin/env python3
"""
Seeds diverse, ready-to-use test scenarios for Phase 4-8 features
(customer accounts/OTP, messaging, team directory, ticket check-in),
ON TOP OF whatever seed_database.py + seed_portfolio.py already created.

Run this AFTER seed_database.py (order matters — this script assumes
some events/sessions may already exist, but creates its own if none do).

SAFETY: same rule as seed_database.py — refuses outright on ENV=production.

Usage:
    ENV=test python seed_phase4_8.py

What you get, printed at the end with exact values to paste into the UI:
  - A website admin login (username/password) for the admin panel
  - A CUSTOMER account (email) with a real, ready-to-use OTP login code
    (printed directly by this script, so you don't need a real SMTP
    server configured to test the login flow — see .env.example's
    SMTP_* section) that already owns the approved test reservation
    below, so logging in immediately shows a real ticket to download
  - 5 team members ("اعضای خانه ماورا") with bios, for the public team
    page and the admin team-management panel
  - One APPROVED reservation with a real signed ticket code, ready to
    download as a PDF and test at /admin/checkin.html
  - A short sample conversation in the admin's message inbox
"""
import sys
from pathlib import Path
from datetime import date, timedelta

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config.settings import ENV, DB_PATH, IS_PRODUCTION  # noqa: E402

if IS_PRODUCTION:
    print("❌ Refusing to run: ENV=production. This script never touches production data.")
    sys.exit(1)

from database.schema import init_db  # noqa: E402
from database.repositories import events as events_repo  # noqa: E402
from database.repositories import sessions as sessions_repo  # noqa: E402
from database.repositories import users as users_repo  # noqa: E402
from database.repositories import reservations as reservations_repo  # noqa: E402
from database.repositories import team_members as team_repo  # noqa: E402
from database.repositories import messages as messages_repo  # noqa: E402
from database.repositories import web_admins as web_admins_repo  # noqa: E402
from services import reservation_service  # noqa: E402
from database.repositories import customer_auth as customer_auth_repo  # noqa: E402
from utils.auth import hash_password  # noqa: E402


def seed() -> None:
    init_db()
    print(f"🌱 Seeding Phase 4-8 test scenarios into {ENV} database at {DB_PATH} ...\n")

    # ---- 1) Website admin login ----------------------------------------
    admin_username, admin_password = "admin", "MavaraTest123!"
    if not web_admins_repo.get_by_username(admin_username):
        h, s = hash_password(admin_password)
        web_admins_repo.create(admin_username, h, s, role="owner")
        print(f"✅ Admin login created — username: {admin_username} / password: {admin_password}")
    else:
        print(f"ℹ️  Admin '{admin_username}' already exists — reusing it (password unchanged).")

    # ---- 2) An event + session to attach a real reservation to ---------
    event_id = events_repo.create_event(
        title="نیایش حباب (تستی)", description="رویداد تستی برای Phase 4-8",
        icon="🎭", calendar_type="jalali", address="تهران، خیابان تستی، پلاک ۱",
        ticket_price=450000, currency="تومان",
    )
    events_repo.set_event_active(event_id, True)
    session_date_iso = (date.today() + timedelta(days=10)).isoformat()
    session_id = sessions_repo.create_session(event_id, session_date_iso, "19:00", capacity=30)
    print(f"✅ Test event + session created (session date: {session_date_iso})")

    # ---- 3) A test customer: books by phone (like any guest), then gets
    # an email attached so the SAME account can log in and see it -------
    linked_phone = "09120000001"
    test_email = "customer@example.com"
    linked_user = users_repo.get_or_create_user_by_phone(linked_phone)
    users_repo.set_email(linked_user["id"], test_email)
    print(f"✅ Test customer: booked by phone {linked_phone}, logs in with email {test_email}")

    # ---- 4) A real approved reservation + issued ticket for that user --
    result = reservation_service.start_reservation_web(
        session_id=session_id, phone=linked_phone, full_name="مشتری تستی", people=2,
    )
    if not result.get("success"):
        print(f"⚠️  Could not create the test reservation ({result.get('error', 'unknown')}) — skipping ticket demo.")
    else:
        reservation_id = result["reservation_id"]
        reservation_service.submit_receipt(
            reservation_id,
            "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=",
            receipt_source="website",
        )
        # reviewed_by is normally the admin's telegram_id — any int works
        # here since this is just seeding, not going through a real
        # Telegram approval callback.
        reservation_service.approve_reservation(reservation_id, reviewed_by=700000000)
        reservation = reservations_repo.get_reservation(reservation_id)
        from utils.qr_signing import sign_code
        signed_payload = sign_code(reservation["reservation_code"])
        print(f"✅ Approved test reservation #{reservation_id}, ticket code: {reservation['reservation_code']}")
        print(f"   → Signed check-in payload (paste this exact value into admin/checkin.html): {signed_payload}")
        print("   → Log in as this customer on /pages/account.html to download its PDF ticket (same QR).")

    # ---- 5) Team members -------------------------------------------------
    sample_members = [
        ("سارا احمدی", "Sara Ahmadi", "طراح صحنه", "Set Designer", "طراح صحنه با ده سال سابقه در تئاتر تجربی."),
        ("رضا کریمی", "Reza Karimi", "مدیر تولید", "Production Manager", "مسئول هماهنگی تولید و اجراهای خانه ماورا."),
        ("نگار موسوی", "Negar Mousavi", "بازیگر", "Actor", "بازیگر تئاتر و همراه ثابت گروه‌های اجرایی خانه ماورا."),
        ("امیر صادقی", "Amir Sadeghi", "طراح نور", "Lighting Designer", "طراح نور با تمرکز بر فضاسازی اتمسفریک."),
        ("یاسمن پیران", "Yasaman Piran", "مدیر روابط عمومی", "PR Manager", "مسئول ارتباط با رسانه‌ها و شبکه‌های اجتماعی."),
    ]
    created = 0
    for fa, en, role_fa, role_en, bio in sample_members:
        if not team_repo.get_by_slug(team_repo.slugify(fa)):
            team_repo.create(full_name=fa, full_name_en=en, role_title=role_fa, role_title_en=role_en,
                              bio_fa=bio, status="active")
            created += 1
    print(f"✅ {created} team member(s) added (see /pages/team.html and admin/team.html)")

    # ---- 6) A short sample support conversation -------------------------
    messages_repo.add_message(linked_user["id"], "customer", "سلام، رزرو من برای رویداد حباب تأیید شده؟")
    messages_repo.add_message(linked_user["id"], "admin", "سلام! بله، رزرو شما تأیید شده و بلیت صادر شده است 🎉")
    messages_repo.add_message(linked_user["id"], "customer", "ممنون! جای پارکینگ هم هست؟")
    print("✅ Sample support conversation added (admin/messages.html)")

    # ---- 7) A ready-to-use OTP code for the test customer's email ------
    # Generated directly (not via customer_auth_service.request_otp(),
    # which would try to actually send an email) so this script works
    # the same whether or not SMTP_* is configured in .env — the code is
    # printed either way.
    import secrets as _secrets
    otp_code = f"{_secrets.randbelow(1_000_000):06d}"
    customer_auth_repo.create_otp(test_email, otp_code)
    print(f"✅ A live OTP code was generated for {test_email}: {otp_code}")
    print(f"   → On /pages/account.html, enter {test_email}, then this code, to log in right now")
    print("     (valid for 5 minutes from when this script ran) — you'll see the approved reservation above.")

    print("\n🎉 Done. See DEPLOYMENT.md / README's testing walkthrough for the full click-by-click guide.")


if __name__ == "__main__":
    seed()
