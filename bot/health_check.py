#!/usr/bin/env python3
"""
Inspects the current environment's setup and reports whether the project
is healthy. Read-only — never modifies anything.

Usage:
    python health_check.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

results: list[tuple[str, bool, str]] = []  # (check name, ok, detail)


def check(name: str):
    def decorator(fn):
        try:
            ok, detail = fn()
        except Exception as exc:
            ok, detail = False, f"exception: {exc}"
        results.append((name, ok, detail))
        return fn
    return decorator


@check("Environment configuration (.env)")
def _check_env():
    from config.settings import ENV, DEBUG, BOT_TOKEN, DB_PATH
    if not BOT_TOKEN or BOT_TOKEN == "your_bot_token_from_botfather":
        return False, "BOT_TOKEN looks unset or still the placeholder value"
    return True, f"ENV={ENV}, DEBUG={DEBUG}, DB_PATH={DB_PATH}"


@check("Database file exists and is reachable")
def _check_db_file():
    from config.settings import DB_PATH
    import sqlite3
    path = Path(DB_PATH)
    if not path.exists():
        return False, f"{DB_PATH} does not exist yet (run the bot once, or seed_database.py for test/dev)"
    conn = sqlite3.connect(DB_PATH)
    conn.execute("SELECT 1")
    # A brand-new SQLite file is ~4KB (just the header page) with zero
    # tables — this is the exact scenario that produced a confusing
    # cascade of "no such table" errors below for every other check.
    # Catching it here, once, with an actionable message, replaces that
    # whole cascade with one clear diagnosis.
    table_count = conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type = 'table'"
    ).fetchone()[0]
    conn.close()
    if table_count == 0:
        return False, (
            f"{DB_PATH} exists but has NO tables yet — the schema was never "
            f"initialized (this happens if the bot was never actually started "
            f"once). Run `python migrate.py` to initialize it safely, then "
            f"re-run this health check."
        )
    return True, f"{DB_PATH} ({path.stat().st_size:,} bytes, {table_count} tables)"


@check("Schema version")
def _check_schema_version():
    from database.connection import get_connection
    from database.schema import SCHEMA_VERSION
    with get_connection() as conn:
        row = conn.execute("SELECT value FROM schema_meta WHERE key = 'version'").fetchone()
    stored = int(row["value"]) if row else 0
    if stored < SCHEMA_VERSION:
        return False, f"database is at v{stored}, code expects v{SCHEMA_VERSION} — restart the bot once to auto-migrate"
    return True, f"v{stored} (up to date)"


@check("All expected tables exist")
def _check_tables():
    from database.connection import get_connection
    expected = {
        "users", "events", "sessions", "reservations", "payments", "waiting_list",
        "bank_cards", "admins", "logs", "settings", "channel_boards", "admin_groups", "schema_meta",
        # Phase 2
        "web_admins",
        # Phase 4/5/6/new-scope, added by schema v7 — see database/schema.py
        "customer_otp", "telegram_link_tokens", "bot_outbox", "messages", "team_members",
    }
    with get_connection() as conn:
        rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    existing = {r["name"] for r in rows}
    missing = expected - existing
    if missing:
        return False, f"missing tables: {', '.join(sorted(missing))}"
    return True, f"{len(expected)} tables present"


@check("Foreign key integrity")
def _check_fk():
    from database.connection import get_connection
    with get_connection() as conn:
        violations = conn.execute("PRAGMA foreign_key_check").fetchall()
    if violations:
        return False, f"{len(violations)} foreign key violation(s) found"
    return True, "no violations"


@check("No orphaned reservations (missing user or session)")
def _check_orphans():
    from database.connection import get_connection
    with get_connection() as conn:
        orphan_users = conn.execute(
            "SELECT COUNT(*) c FROM reservations r LEFT JOIN users u ON u.id = r.user_id WHERE u.id IS NULL"
        ).fetchone()["c"]
        orphan_sessions = conn.execute(
            "SELECT COUNT(*) c FROM reservations r LEFT JOIN sessions s ON s.id = r.session_id WHERE s.id IS NULL"
        ).fetchone()["c"]
    if orphan_users or orphan_sessions:
        return False, f"{orphan_users} reservation(s) with missing user, {orphan_sessions} with missing session"
    return True, "clean"


@check("At least one owner/admin configured")
def _check_admins():
    from database.repositories import admins as admins_repo
    admins = admins_repo.list_admins()
    owners = [a for a in admins if a["role"] == "owner"]
    if not owners:
        return False, "no owner configured — set BOOTSTRAP_ADMIN_IDS in .env and restart once"
    return True, f"{len(admins)} staff total, {len(owners)} owner(s)"


@check("Bank card configured (needed for real payments)")
def _check_bank_cards():
    from database.repositories import bank_cards as bank_cards_repo
    active = bank_cards_repo.get_active_card()
    if not active:
        return False, "no active bank card — payment instructions will show a blank card number"
    return True, f"active card ends in ...{active['card_number'][-4:]}"


@check("Log file is writable")
def _check_logs():
    from config.settings import LOG_FILE
    path = Path(LOG_FILE)
    path.parent.mkdir(parents=True, exist_ok=True)
    test_file = path.parent / ".health_check_write_test"
    test_file.write_text("ok")
    test_file.unlink()
    return True, str(path.parent)


@check("Backups directory reachable")
def _check_backups_dir():
    from config.settings import BASE_DIR
    backups = BASE_DIR / "backups"
    backups.mkdir(exist_ok=True)
    existing = list(backups.glob("*.db"))
    return True, f"{len(existing)} backup file(s) present"


@check("No broken internal imports (services layer)")
def _check_imports():
    import importlib
    modules = [
        "services.reservation_service", "services.event_service", "services.settings_service",
        "services.permissions", "services.channel_service", "services.export_service",
        "utils.jalali", "utils.qr_signing", "validators.validators",
    ]
    for m in modules:
        importlib.import_module(m)
    return True, f"{len(modules)} core modules import cleanly"


def main() -> None:
    print("=" * 60)
    print("  MAVARA BOT — HEALTH CHECK")
    print("=" * 60)
    passed = 0
    for name, ok, detail in results:
        icon = "✅" if ok else "❌"
        print(f"{icon} {name}")
        print(f"   {detail}")
        if ok:
            passed += 1
    print("=" * 60)
    print(f"  {passed}/{len(results)} checks passed")
    print("=" * 60)
    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
