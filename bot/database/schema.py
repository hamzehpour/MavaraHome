"""
Full database schema + first-run seeding.
Run automatically once at bot startup (see bot.py) — safe to call
every time, all statements are idempotent (CREATE TABLE IF NOT EXISTS).

SCHEMA_VERSION: bump this whenever a migration is added below. A fresh
install always ends up at the latest version immediately (all statements
run in order); an existing install's stored version tells us which
migrations it still needs — this is what lets a future upgrade apply only
what's missing instead of guessing from column-already-exists errors.
"""
from database.connection import get_connection
from config.settings import BOOTSTRAP_ADMIN_IDS

SCHEMA_VERSION = 10

SCHEMA_STATEMENTS = [
    # ---- users -------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        telegram_id INTEGER UNIQUE,
        full_name TEXT,
        phone TEXT,
        is_blocked INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """,

    # ---- events (a "show" / production, e.g. "حباب") -----------
    """
    CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        description TEXT,
        address TEXT,
        icon TEXT NOT NULL DEFAULT '🎭',
        calendar_type TEXT NOT NULL DEFAULT 'jalali',
        ticket_price INTEGER,
        currency TEXT NOT NULL DEFAULT 'تومان',
        is_active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """,

    # ---- sessions (a specific date+time run of an event) -------
    """
    CREATE TABLE IF NOT EXISTS sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
        session_date TEXT NOT NULL,
        session_time TEXT NOT NULL,
        capacity INTEGER NOT NULL,
        status TEXT NOT NULL DEFAULT 'active',
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """,

    # ---- reservations --------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS reservations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        reservation_code TEXT UNIQUE,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        session_id INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
        people INTEGER NOT NULL,
        unit_price INTEGER NOT NULL,
        total_price INTEGER NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending_payment',
        source TEXT NOT NULL DEFAULT 'telegram',
        created_by_staff INTEGER,
        attendee_name TEXT,
        attendee_phone TEXT,
        admin_note TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now')),
        expires_at TEXT
    )
    """,

    # ---- payments / receipts ------------------------------------
    """
    CREATE TABLE IF NOT EXISTS payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        reservation_id INTEGER NOT NULL REFERENCES reservations(id) ON DELETE CASCADE,
        receipt_file_id TEXT NOT NULL,
        receipt_source TEXT NOT NULL DEFAULT 'telegram',
        amount INTEGER NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending_review',
        submitted_at TEXT NOT NULL DEFAULT (datetime('now')),
        reviewed_at TEXT,
        reviewed_by INTEGER
    )
    """,

    # ---- waiting list ---------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS waiting_list (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        session_id INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
        people INTEGER NOT NULL,
        status TEXT NOT NULL DEFAULT 'waiting',
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """,

    # ---- key/value settings, admin-editable ------------------------
    """
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL,
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """,

    # ---- admins ------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS admins (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        telegram_id INTEGER UNIQUE NOT NULL,
        role TEXT NOT NULL DEFAULT 'admin',
        pending_removal_at TEXT,
        added_at TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """,

    # ---- logs ----------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        action TEXT NOT NULL,
        telegram_id INTEGER,
        target_type TEXT,
        target_id INTEGER,
        details TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """,

    # ---- event reopening interest ("منتظر اجرای بعدی") -----------
    # Deliberately NOT the waiting_list table — different business meaning.
    # waiting_list = "I want a specific full session". This = "this event
    # currently has no bookable run at all, notify me when one exists".
    """
    CREATE TABLE IF NOT EXISTS event_reopening_interests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        contact_name TEXT NOT NULL,
        phone_number TEXT NOT NULL,
        telegram_user_id INTEGER NOT NULL,
        telegram_username TEXT,
        status TEXT NOT NULL DEFAULT 'active',
        notified_at TEXT,
        converted_reservation_id INTEGER REFERENCES reservations(id) ON DELETE SET NULL,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """,

    "CREATE UNIQUE INDEX IF NOT EXISTS uq_reopening_interest_active "
    "ON event_reopening_interests(event_id, user_id) WHERE status = 'active'",
    "CREATE INDEX IF NOT EXISTS idx_reopening_interest_event ON event_reopening_interests(event_id)",

    # ---- portfolio (Mansour's resume/CV — unrelated to reservations, but
    # kept on this same shared backend rather than a third separate data
    # store, per "one backend" principle). Admin-editable via the website
    # panel; the Telegram bot never reads this table.
    """
    CREATE TABLE IF NOT EXISTS portfolio (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title_fa TEXT NOT NULL,
        title_en TEXT,
        year TEXT,
        category TEXT NOT NULL,
        director TEXT,
        director_en TEXT,
        role TEXT,
        role_en TEXT,
        festival TEXT,
        festival_en TEXT,
        poster TEXT,
        gallery TEXT,
        video TEXT,
        desc_fa TEXT,
        desc_en TEXT,
        status TEXT NOT NULL DEFAULT 'active',
        sort_order INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_portfolio_category ON portfolio(category)",

    # ---- web_admins (Phase 2: real website admin authentication —
    # separate from the Telegram-side `admins` table, which is keyed by
    # telegram_id and has no password. A website admin logs in with
    # username+password and gets a signed JWT back; every admin API write
    # endpoint now requires a valid token instead of the old static
    # shared-secret header.) ------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS web_admins (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        password_salt TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'admin',
        is_active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        last_login_at TEXT
    )
    """,

    "CREATE INDEX IF NOT EXISTS idx_reservations_session ON reservations(session_id)",
    "CREATE INDEX IF NOT EXISTS idx_reservations_status ON reservations(status)",
    # Phase 7 (performance pass): list_for_user() (customer dashboard,
    # Phase 4) filters by user_id — was previously unindexed, meaning a
    # full table scan on every "رزروهای من" page load as the reservations
    # table grows.
    "CREATE INDEX IF NOT EXISTS idx_reservations_user ON reservations(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_payments_reservation ON payments(reservation_id)",
    "CREATE INDEX IF NOT EXISTS idx_sessions_event ON sessions(event_id)",
    "CREATE INDEX IF NOT EXISTS idx_users_telegram ON users(telegram_id)",
    # Schema v10: was a plain (non-unique) index — replaced with a partial
    # UNIQUE one now that get_or_create_customer() (database/repositories/
    # users.py) is the single lookup/create path for phone identity. A
    # plain index let the two now-retired near-duplicate lookup functions
    # each create their own row for the same phone number; this makes that
    # impossible at the database level, not just by convention. Partial
    # (WHERE phone IS NOT NULL) because many rows legitimately have no
    # phone (email-only customers) and NULL/blank must never collide.
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_users_phone ON users(phone) "
    "WHERE phone IS NOT NULL AND phone != ''",
    # NOTE: uq_users_email / idx_customer_otp_email (schema v9/v10) are NOT
    # here — `email` is an ALTER-added column (see init_db() below), and
    # this list runs BEFORE that ALTER loop, so creating an index on it
    # here would fail on any database that doesn't already have the
    # column. They're created right after the ALTER loop instead.
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_session_slot ON sessions(event_id, session_date, session_time)",
]

BANK_CARDS_TABLE = """
    CREATE TABLE IF NOT EXISTS bank_cards (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        card_number TEXT NOT NULL,
        card_holder TEXT NOT NULL,
        bank_name TEXT NOT NULL DEFAULT '',
        is_active INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    )
"""
SCHEMA_STATEMENTS.append(BANK_CARDS_TABLE)

CHANNEL_BOARDS_TABLE = """
    CREATE TABLE IF NOT EXISTS channel_boards (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_id INTEGER NOT NULL,
        session_date TEXT NOT NULL,
        part_index INTEGER NOT NULL DEFAULT 0,
        message_id INTEGER NOT NULL,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        UNIQUE(event_id, session_date, part_index)
    )
"""
SCHEMA_STATEMENTS.append(CHANNEL_BOARDS_TABLE)

ADMIN_GROUPS_TABLE = """
    CREATE TABLE IF NOT EXISTS admin_groups (
        telegram_id INTEGER NOT NULL,
        group_name TEXT NOT NULL,
        added_at TEXT NOT NULL DEFAULT (datetime('now')),
        PRIMARY KEY (telegram_id, group_name)
    )
"""
SCHEMA_STATEMENTS.append(ADMIN_GROUPS_TABLE)

# ---- Phase 4: customer accounts (OTP delivered via the Telegram bot,
# not SMS — this project has no SMS provider). Two tables:
#   customer_otp          — the actual login codes
#   telegram_link_tokens   — one-time deep-link tokens used when a
#                            website-only user (phone, no telegram_id yet)
#                            needs to open the bot once to receive codes
CUSTOMER_OTP_TABLE = """
    CREATE TABLE IF NOT EXISTS customer_otp (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        phone TEXT NOT NULL,
        code_hash TEXT NOT NULL,
        code_salt TEXT NOT NULL,
        attempts INTEGER NOT NULL DEFAULT 0,
        status TEXT NOT NULL DEFAULT 'pending',
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        expires_at TEXT NOT NULL
    )
"""
SCHEMA_STATEMENTS.append(CUSTOMER_OTP_TABLE)
SCHEMA_STATEMENTS.append("CREATE INDEX IF NOT EXISTS idx_customer_otp_phone ON customer_otp(phone)")
# idx_customer_otp_email / idx_users_email (schema v9) are created after
# the ALTER loop in init_db() — see the NOTE next to idx_users_phone above.

TELEGRAM_LINK_TOKENS_TABLE = """
    CREATE TABLE IF NOT EXISTS telegram_link_tokens (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        token TEXT NOT NULL UNIQUE,
        phone TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        expires_at TEXT NOT NULL
    )
"""
SCHEMA_STATEMENTS.append(TELEGRAM_LINK_TOKENS_TABLE)
SCHEMA_STATEMENTS.append("CREATE INDEX IF NOT EXISTS idx_link_tokens_token ON telegram_link_tokens(token)")

# ---- Phase 4/5: bot_outbox — the API process (api/server.py) and the
# bot process (bot.py) are two separate OS processes that never talk to
# each other directly (see the project handoff: "بات ... مستقیم از همان
# services/ استفاده می‌کند ... نه از طریق HTTP"). The only thing they
# already share is the SQLite database, so a durable outbox table is the
# simplest correct way for the API to ask the bot to deliver a Telegram
# message (OTP codes, new-message notifications) without inventing a new
# transport (no HTTP callback, no message broker — nothing new to deploy).
# The bot polls this table on the same interval pattern as
# utils/scheduler.run_expiry_loop (already proven, already tested).
BOT_OUTBOX_TABLE = """
    CREATE TABLE IF NOT EXISTS bot_outbox (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        telegram_id INTEGER NOT NULL,
        kind TEXT NOT NULL DEFAULT 'text',
        body TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        sent_at TEXT
    )
"""
SCHEMA_STATEMENTS.append(BOT_OUTBOX_TABLE)
SCHEMA_STATEMENTS.append("CREATE INDEX IF NOT EXISTS idx_outbox_status ON bot_outbox(status)")

# ---- Phase 5: messages — one flat table, one thread per customer
# (user_id), admin replies are attributed by web_admin id when available.
# Deliberately no separate "conversations" table: with a single support
# inbox (not multi-department), the thread IS the customer, so grouping
# by user_id is enough and keeps the query surface small.
MESSAGES_TABLE = """
    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        sender TEXT NOT NULL,
        admin_id INTEGER,
        body TEXT NOT NULL,
        attachment_path TEXT,
        is_read_by_admin INTEGER NOT NULL DEFAULT 0,
        is_read_by_customer INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    )
"""
SCHEMA_STATEMENTS.append(MESSAGES_TABLE)
SCHEMA_STATEMENTS.append("CREATE INDEX IF NOT EXISTS idx_messages_user ON messages(user_id)")

# ---- New scope item (not in the original 8-phase spec, added on request):
# team_members — "اعضای خانه ماورا". Deliberately modeled after the
# existing, already-proven `portfolio` table shape (same
# title/bio/photo/gallery/sort_order/status idea) rather than inventing a
# new shape, since portfolio already solved "admin-editable public bio
# content with images" once.
TEAM_MEMBERS_TABLE = """
    CREATE TABLE IF NOT EXISTS team_members (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        slug TEXT NOT NULL UNIQUE,
        full_name TEXT NOT NULL,
        full_name_en TEXT,
        role_title TEXT,
        role_title_en TEXT,
        photo TEXT,
        bio_fa TEXT,
        bio_en TEXT,
        gallery TEXT,
        contact_phone TEXT,
        contact_telegram TEXT,
        status TEXT NOT NULL DEFAULT 'active',
        sort_order INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    )
"""
SCHEMA_STATEMENTS.append(TEAM_MEMBERS_TABLE)
SCHEMA_STATEMENTS.append("CREATE INDEX IF NOT EXISTS idx_team_status ON team_members(status)")

# Defaults an admin can later change from the panel — never hardcoded
# in handlers/services again.
DEFAULT_SETTINGS = {
    "brand_name": "خانه ماورا",
    "welcome_message": "درود بر شما 👋\n\nبه ربات رسمی خانه ماورا خوش آمدید.",
    "ticket_price": "450000",
    "card_number": "",
    "card_holder": "",
    "max_tickets_per_person": "10",
    "rules_text": "",
    "support_contact": "",
    "payment_expiry_minutes": "15",
    "review_reminder_minutes": "60",
    "review_reminder_repeat_minutes": "10",
    "auto_rotate_cards": "0",
    "card_rotation_last_date": "",
    "owner_passcode_hash": "",
    "owner_passcode_salt": "",
    "monitoring_channel_id": "",
    "monitoring_last_week": "",

    # ---- admin-editable message templates ----
    # Placeholders are replaced literally — never crash on stray braces the
    # admin might type. Available tokens are documented in settings_service.py
    # and shown to the admin when they open each template for editing.
    "tmpl_payment_instructions": (
        "💳 لطفاً مبلغ زیر را واریز کنید.\n\n"
        "━━━━━━━━━━━━━━\n\n"
        "👥 تعداد بلیت:\n{people} نفر\n\n"
        "🎫 قیمت هر بلیت:\n{unit_price} تومان\n\n"
        "💰 مبلغ قابل پرداخت:\n\n{total_price} تومان\n\n"
        "━━━━━━━━━━━━━━\n\n"
        "💳 شماره کارت:\n\n`{card_number}`\n\n"
        "👤 صاحب حساب:\n\n{card_holder}\n\n"
        "━━━━━━━━━━━━━━\n\n"
        "📌 برای کپی کردن شماره کارت، روی همین پیام کلیک کنید.\n\n"
        "پس از پرداخت، رسید را از طریق دکمه زیر ارسال کنید."
    ),
    "tmpl_receipt_received": (
        "✅ رسید شما دریافت شد.\n\n"
        "پس از بررسی توسط تیم ما، نتیجه به همین ربات برایتان ارسال خواهد شد."
    ),
    "tmpl_ticket_confirmed": (
        "✅ رزرو شما برای {event_title}، انجام شد\n\n"
        "🎟️ مشخصات بلیت شما 🎟️\n"
        "روز:\n{session_date_fa}\n\n"
        "تعداد:\n{people}\n\n"
        "به نام:\n{full_name}\n\n"
        "سانس:\n{session_time}\n\n"
        "🎫 کد رزرو: {reservation_code}\n\n"
        "📍 آدرس:\n{event_address}\n\n"
        "[لطفا ۱۰ دقیقه زودتر در محدوده باشید]\n\n"
        "این متن را از پنل تنظیمات کامل ویرایش کنید تا آدرس، ساعت اجرا، شماره پشتیبان "
        "و ملاحظات اجرا مطابق رویداد واقعی‌تان باشد."
    ),
    "tmpl_reservation_rejected": (
        "😔 متأسفانه پرداخت شما تأیید نشد.\n\n"
        "{admin_note_block}\n\n"
        "در صورت وجود سوال با پشتیبانی تماس بگیرید."
    ),

    # ---- PDF ticket template (admin-editable from the website's
    # admin panel — pages/admin/ticket-template.html — and, for parity,
    # from the Telegram bot's settings menu too since it's the same
    # generic EDITABLE_SETTINGS mechanism). `ticket_template_logo` is the
    # header logo shown when a specific event has no `ticket_logo` of its
    # own (events.ticket_logo, set per-event) — see utils/ticket_pdf.py.
    "ticket_template_title": "خانه ماورا",
    "ticket_template_subtitle": "بلیت الکترونیک",
    "ticket_template_footer": "این بلیت را همراه داشته باشید و QR آن را دم در نشان دهید — فقط برای یک نفر معتبر است.",
    "ticket_template_logo": "",
}


def init_db() -> None:
    with get_connection() as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
        )
        row = conn.execute("SELECT value FROM schema_meta WHERE key = 'version'").fetchone()
        stored_version = int(row["value"]) if row else 0

        for statement in SCHEMA_STATEMENTS:
            try:
                conn.execute(statement)
            except Exception as exc:
                # Only the duplicate-session unique index can realistically fail
                # here, and only on a pre-existing database that already has
                # conflicting rows from before this constraint existed. Don't
                # crash the whole bot over it — surface it in the logs instead.
                import logging
                logging.getLogger("mavara_bot").warning(
                    "Skipped schema statement (%s): %s", exc, statement.strip()[:80]
                )

        # ALTER-based migrations for columns added after a database already
        # existed — CREATE TABLE IF NOT EXISTS silently does nothing to an
        # existing table, so new columns need an explicit ALTER here. Each
        # is wrapped individually since SQLite errors if the column is
        # already there (i.e. on a fresh database created with the new
        # schema directly).
        for alter_sql in (
            "ALTER TABLE reservations ADD COLUMN attendee_name TEXT",
            "ALTER TABLE reservations ADD COLUMN attendee_phone TEXT",
            "ALTER TABLE events ADD COLUMN address TEXT",
            "ALTER TABLE payments ADD COLUMN receipt_source TEXT NOT NULL DEFAULT 'telegram'",
            "ALTER TABLE events ADD COLUMN icon TEXT NOT NULL DEFAULT '🎭'",
            "ALTER TABLE events ADD COLUMN calendar_type TEXT NOT NULL DEFAULT 'jalali'",
            "ALTER TABLE events ADD COLUMN ticket_price INTEGER",
            "ALTER TABLE events ADD COLUMN currency TEXT NOT NULL DEFAULT 'تومان'",
            "ALTER TABLE logs ADD COLUMN target_type TEXT",
            "ALTER TABLE logs ADD COLUMN target_id INTEGER",
            "ALTER TABLE admins ADD COLUMN pending_removal_at TEXT",
            # Phase 1 (backend unification): the website's event model is
            # richer than the bot's original (bilingual text, poster/gallery/
            # video, direct contact info) — these columns make events the
            # single shared source of truth for BOTH the bot and the website,
            # instead of the website inventing its own parallel event shape.
            "ALTER TABLE events ADD COLUMN title_en TEXT",
            "ALTER TABLE events ADD COLUMN description_en TEXT",
            "ALTER TABLE events ADD COLUMN location TEXT",
            "ALTER TABLE events ADD COLUMN location_en TEXT",
            "ALTER TABLE events ADD COLUMN poster TEXT",
            "ALTER TABLE events ADD COLUMN gallery TEXT",  # JSON array of paths, stored as text
            "ALTER TABLE events ADD COLUMN video TEXT",
            "ALTER TABLE events ADD COLUMN contact_phone TEXT",
            "ALTER TABLE events ADD COLUMN contact_telegram TEXT",
            # Phase 6: door check-in. NULL = not checked in yet. Kept
            # separate from `status` on purpose — a reservation stays
            # "confirmed" after check-in, check-in is just a timestamp
            # overlay, so nothing that already reads `status` needs to
            # change.
            "ALTER TABLE reservations ADD COLUMN checked_in_at TEXT",
            # Phase 6 follow-up (ticket template + per-event notes, requested
            # after the original 8-phase handoff): `important_notes` is
            # free text, one consideration per line (e.g. "جای پارک ندارد،
            # لطفاً بالاتر پارک کنید" / "لطفاً سکوت را رعایت کنید") — the
            # admin fills it in once per event, and every ticket PDF for
            # that event prints it automatically, so nobody has to remember
            # to repeat it per reservation. `ticket_logo` is an OPTIONAL
            # per-event override of the ticket header logo (falls back to
            # the global `ticket_template_logo` setting, and to a plain
            # text header if neither is set — see utils/ticket_pdf.py).
            "ALTER TABLE events ADD COLUMN important_notes TEXT",
            "ALTER TABLE events ADD COLUMN ticket_logo TEXT",
            # Schema v9: customer account login rewritten from phone+
            # Telegram-delivery to email (this project has no SMS
            # provider, and routing every login through the Telegram bot
            # just to receive a code was awkward — see
            # services/customer_auth_service.py). `customer_otp.phone`
            # stays NOT NULL for backward compatibility (old rows), so
            # new email-based rows write '' into it rather than requiring
            # a full table rebuild just to relax that constraint.
            "ALTER TABLE users ADD COLUMN email TEXT",
            "ALTER TABLE customer_otp ADD COLUMN email TEXT",
        ):
            try:
                conn.execute(alter_sql)
            except Exception:
                pass  # column already exists

        # Schema v9/v10: these index the `email` column added above by the
        # ALTER loop — must run after it, not inside SCHEMA_STATEMENTS
        # (which runs before any ALTER, and would fail on a database that
        # doesn't have the column yet). uq_users_email is UNIQUE (v10) for
        # the same reason uq_users_phone is — see that statement's comment
        # above; wrapped in try/except like the ALTER loop just above it
        # since, unlike SCHEMA_STATEMENTS, statements here were never
        # individually guarded, and a database with pre-existing duplicate
        # emails (from testing before this constraint existed) must not
        # crash startup over it — same "warn and continue" fallback.
        try:
            conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_users_email ON users(email) "
                "WHERE email IS NOT NULL AND email != ''"
            )
        except Exception as exc:
            import logging
            logging.getLogger("mavara_bot").warning("Could not create uq_users_email: %s", exc)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_customer_otp_email ON customer_otp(email)")

        for key, value in DEFAULT_SETTINGS.items():
            conn.execute(
                "INSERT OR IGNORE INTO settings(key, value) VALUES (?, ?)",
                (key, value),
            )

        for admin_id in BOOTSTRAP_ADMIN_IDS:
            conn.execute(
                "INSERT OR IGNORE INTO admins(telegram_id, role) VALUES (?, 'owner')",
                (admin_id,),
            )

        # One-time migration: earlier versions stored a single card in
        # settings (card_number/card_holder). If bank_cards is still empty
        # but those old values exist, carry them over as the first active card.
        existing_cards = conn.execute("SELECT COUNT(*) c FROM bank_cards").fetchone()["c"]
        if existing_cards == 0:
            old_number = conn.execute("SELECT value FROM settings WHERE key='card_number'").fetchone()
            old_holder = conn.execute("SELECT value FROM settings WHERE key='card_holder'").fetchone()
            if old_number and old_number["value"]:
                conn.execute(
                    "INSERT INTO bank_cards(card_number, card_holder, bank_name, is_active) VALUES (?, ?, '', 1)",
                    (old_number["value"], old_holder["value"] if old_holder else ""),
                )

        # Record the version this database is now at. Future migrations
        # should check `stored_version` (captured above) to decide what
        # still needs applying, instead of relying purely on try/except
        # probing — that stays as a defensive fallback, not the primary
        # mechanism, from here on.
        if stored_version < SCHEMA_VERSION:
            import logging
            logging.getLogger("mavara_bot").info(
                "Database schema upgraded: v%d -> v%d", stored_version, SCHEMA_VERSION
            )
        conn.execute(
            "INSERT INTO schema_meta(key, value) VALUES ('version', ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (str(SCHEMA_VERSION),),
        )
