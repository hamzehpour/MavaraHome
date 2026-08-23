#!/usr/bin/env python3
"""
Populates the current environment's database with realistic Persian test
data — events, sessions, users, reservations in every status, a waiting
list, multiple admin roles.

SAFETY: this refuses to run at all against ENV=production. There is no
override flag for that check on purpose — if you need production data,
this is the wrong tool; use the admin panel like a real admin would.

Usage:
    ENV=test python seed_database.py        # normal: adds to existing test data
    ENV=test python seed_database.py --reset  # wipes test.db first, then seeds

Uses the project's own repositories (not raw SQL) wherever the operation
already exists there, so the seeded data goes through the same validation
paths as real usage.
"""
import random
import sys
from pathlib import Path
from datetime import date, timedelta

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config.settings import ENV, DB_PATH, IS_PRODUCTION  # noqa: E402

if IS_PRODUCTION:
    print("❌ Refusing to run: ENV=production. This script never touches production data.")
    print("   Set ENV=test (or development) in .env, or export ENV=test for this run.")
    sys.exit(1)

if "--reset" in sys.argv:
    db_file = Path(DB_PATH)
    if db_file.exists():
        db_file.unlink()
        print(f"🗑  Removed existing {db_file}")

from database.schema import init_db  # noqa: E402
from database.repositories import events as events_repo  # noqa: E402
from database.repositories import sessions as sessions_repo  # noqa: E402
from database.repositories import users as users_repo  # noqa: E402
from database.repositories import admins as admins_repo  # noqa: E402
from database.repositories import reservations as reservations_repo  # noqa: E402
from database.repositories import waitlist as waitlist_repo  # noqa: E402
from database.repositories import payments as payments_repo  # noqa: E402
from database.connection import get_connection  # noqa: E402

FIRST_NAMES = [
    "علی", "محمد", "حسین", "رضا", "امیر", "سینا", "بابک", "کیوان", "آرش", "پویا",
    "زهرا", "فاطمه", "مریم", "نگار", "سارا", "الهام", "شیوا", "پریسا", "یاسمن", "ترانه",
]
LAST_NAMES = [
    "احمدی", "محمدی", "رضایی", "کریمی", "حسینی", "موسوی", "صادقی", "نصیری",
    "مظفری", "خمسه", "شهمیری", "جعفری", "یعقوبی", "پیران", "بهروزیان",
]
EVENT_TITLES = [
    "نیایش حباب", "شب‌های شعر", "تئاتر خاموشی", "کارگاه نقاشی", "کنسرت کوچک",
    "نمایش عروسکی", "شب داستان‌خوانی", "ورک‌شاپ عکاسی", "اجرای موسیقی سنتی", "نمایش خیابانی",
]


def fake_name() -> str:
    return f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"


def fake_phone() -> str:
    return "09" + "".join(str(random.randint(0, 9)) for _ in range(9))


def seed() -> None:
    init_db()
    print(f"🌱 Seeding {ENV} database at {DB_PATH} ...")

    # --- admins (in addition to whatever BOOTSTRAP_ADMIN_IDS already added) ---
    admins_repo.add_admin(900000001, role="admin")
    admins_repo.add_admin(900000002, role="operator")
    print("✅ 2 extra test admins added (900000001=admin, 900000002=operator)")

    from database.repositories import bank_cards as bank_cards_repo
    bank_cards_repo.add_card("6104337600000000", "تست تستی", "بانک تست")
    print("✅ 1 test bank card added")

    # --- events + sessions ---
    event_ids = []
    for i in range(10):
        calendar_type = "gregorian" if i == 9 else "jalali"  # one international event
        event_id = events_repo.create_event(
            title=EVENT_TITLES[i],
            description=f"رویداد تستی شماره {i + 1}",
            icon=random.choice(["🎭", "🎵", "🎨", "🎪", "✨"]),
            calendar_type=calendar_type,
            address="تهران، خیابان تستی، پلاک ۱" if calendar_type == "jalali" else "Istanbul, Test Street 1",
            ticket_price=random.choice([None, 350000, 500000, 750000]),
            currency="لیر" if calendar_type == "gregorian" else "تومان",
        )
        event_ids.append(event_id)
        if i % 3 != 0:  # leave a couple inactive to test that path too
            events_repo.set_event_active(event_id, True)
        else:
            events_repo.set_event_active(event_id, i % 2 == 0)

    session_ids = []
    today = date.today()
    for event_id in event_ids:
        num_days = random.randint(2, 5)
        for d in range(num_days):
            session_date = (today + timedelta(days=random.randint(1, 20))).isoformat()
            num_sessions = random.randint(1, 3)
            for _ in range(num_sessions):
                hour = random.choice([14, 15, 17, 18, 20])
                minute = random.choice([0, 30])
                try:
                    sid = sessions_repo.create_session(
                        event_id, session_date, f"{hour:02d}:{minute:02d}",
                        capacity=random.choice([5, 10, 14, 20, 30]),
                    )
                    session_ids.append(sid)
                except Exception:
                    continue  # duplicate slot — fine, just skip
    print(f"✅ {len(event_ids)} events, {len(session_ids)} sessions")

    # --- users + reservations across every status ---
    statuses_to_generate = (
        ["approved"] * 8 + ["pending_review"] * 4 + ["pending_payment"] * 3
        + ["rejected"] * 2 + ["awaiting_buyer_confirmation"] * 1 + ["expired"] * 2
        + ["cancelled"] * 1 + ["used"] * 2
    )
    user_count = 0
    reservation_count = 0
    for _ in range(200):
        telegram_id = 800000000 + user_count
        name = fake_name()
        phone = fake_phone()
        users_repo.get_or_create_user(telegram_id, name)
        users_repo.update_contact_info(telegram_id, name, phone)
        user_count += 1

        if session_ids and random.random() < 0.7:  # not every fake user has a reservation
            session_id = random.choice(session_ids)
            session = sessions_repo.get_session(session_id)
            people = random.randint(1, 4)
            unit_price = random.choice([350000, 450000, 500000])
            status = random.choice(statuses_to_generate)

            with get_connection() as conn:
                user_row = conn.execute("SELECT id FROM users WHERE telegram_id = ?", (telegram_id,)).fetchone()
                cur = conn.execute(
                    """
                    INSERT INTO reservations(user_id, session_id, people, unit_price, total_price, status, source)
                    VALUES (?, ?, ?, ?, ?, ?, 'telegram')
                    """,
                    (user_row["id"], session_id, people, unit_price, unit_price * people, status),
                )
                reservation_id = cur.lastrowid
                if status == "approved":
                    conn.execute(
                        "UPDATE reservations SET reservation_code = ? WHERE id = ?",
                        (f"MV-TEST{reservation_id:04d}", reservation_id),
                    )
            reservation_count += 1

            if status in ("pending_review", "approved", "rejected"):
                payments_repo.create_payment(reservation_id, f"fake_file_id_{reservation_id}", unit_price * people)

    print(f"✅ {user_count} users, {reservation_count} reservations (mixed statuses)")

    # --- a small waiting list ---
    waiting_count = 0
    for _ in range(15):
        if not session_ids:
            break
        telegram_id = 800000000 + user_count
        users_repo.get_or_create_user(telegram_id, fake_name())
        with get_connection() as conn:
            user_row = conn.execute("SELECT id FROM users WHERE telegram_id = ?", (telegram_id,)).fetchone()
        waitlist_repo.add(user_row["id"], random.choice(session_ids), random.randint(1, 5))
        user_count += 1
        waiting_count += 1
    print(f"✅ {waiting_count} waiting-list entries")

    print(f"\n🎉 Done. {ENV} database ready at {DB_PATH}")
    print("   Run `python health_check.py` to verify everything looks right.")


if __name__ == "__main__":
    seed()
