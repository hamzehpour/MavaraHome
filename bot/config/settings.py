"""
Static, deployment-level configuration.

RULE: only things that MUST come from the environment live here
(secrets, file paths). Everything an admin should be able to change
(prices, capacity, card number, texts, ...) lives in the `settings`
DB table and is read through services/settings_service.py instead.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

BOT_TOKEN = os.getenv("BOT_TOKEN")
# Root-cause fix for Phase 1 (API unification): this module used to hard-crash
# at import time if BOT_TOKEN was missing. That's correct for the Telegram
# bot process itself, but every service/repository transitively imports this
# module (via database/connection.py), which meant a pure REST API process
# that never touches Telegram was ALSO forced to have a real bot token just
# to boot. bot.py now does this check explicitly at startup instead (see
# bot.py's main()) — this module only warns, so `api/server.py` can import
# the exact same services/ the bot uses without needing BOT_TOKEN at all.
if not BOT_TOKEN:
    import warnings
    warnings.warn(
        "BOT_TOKEN is not set — fine for the API-only process, but bot.py "
        "will refuse to start without it. Copy .env.example to .env and "
        "fill it in if you intend to run the Telegram bot."
    )

# Bootstrap admins: only used to seed the `admins` table the first time
# the bot runs. After that, admin management happens from the admin panel
# and this env var is no longer consulted.
_raw_admin_ids = os.getenv("BOOTSTRAP_ADMIN_IDS", "")
BOOTSTRAP_ADMIN_IDS = [
    int(x.strip()) for x in _raw_admin_ids.split(",") if x.strip().isdigit()
]

# ---------------------------------------------------------------------------
# Environment separation (production / test / development)
#
# ENV picks which database file this process talks to. This is the ONLY
# thing that determines which data a running bot sees — there is
# deliberately no in-bot "switch database" button, because a live toggle
# like that is one accidental tap away from pointing a production bot at a
# scratch database (or vice versa). Switching environments means editing
# .env and restarting the process — explicit and safe.
# ---------------------------------------------------------------------------
ENV = os.getenv("ENV", "production").strip().lower()
if ENV not in ("production", "test", "development"):
    raise RuntimeError(f"Invalid ENV='{ENV}' in .env — must be production, test, or development.")

IS_PRODUCTION = ENV == "production"

# DEBUG=True is only ever meaningful outside production, and is force-disabled
# in production regardless of what .env says — this is the actual safety
# guarantee, not just a convention.
DEBUG = (os.getenv("DEBUG", "false").strip().lower() == "true") and not IS_PRODUCTION

_DB_FILENAMES = {
    "production": "production.db",
    "test": "test.db",
    "development": "development.db",
}
# DB_PATH in .env still wins if explicitly set (keeps existing single-environment
# deployments working unchanged). Otherwise: if this is production and the
# OLD default file (data/mavara.db, used before environment separation
# existed) is present but the new production.db is not, keep using the old
# file — auto-adopting a new filename here would make an existing bot's
# real reservation data silently "disappear" on next startup, which is
# exactly the kind of data-loss this whole environment system exists to
# prevent. Otherwise each ENV gets its own file under data/.
_explicit_db_path = os.getenv("DB_PATH")
if _explicit_db_path:
    DB_PATH = str(BASE_DIR / _explicit_db_path)
else:
    _legacy_path = BASE_DIR / "data" / "mavara.db"
    _new_path = BASE_DIR / "data" / _DB_FILENAMES[ENV]
    if IS_PRODUCTION and _legacy_path.exists() and not _new_path.exists():
        DB_PATH = str(_legacy_path)
    else:
        DB_PATH = str(_new_path)

LOG_FILE = str(BASE_DIR / os.getenv("LOG_FILE", f"logs/app-{ENV}.log"))

# ---------------------------------------------------------------------------
# Outbound email (Schema v9: customer account OTP login, see
# services/customer_auth_service.py). If SMTP_HOST is left empty, nothing
# actually connects to a mail server — utils/email_sender.py prints the
# email to the console/log instead, the same "works locally without real
# credentials" fallback this project already uses for BOT_TOKEN. Fill
# these in for a real deployment (any standard SMTP relay: your host's
# own mailbox, SendGrid, Mailgun, Amazon SES, etc. all speak SMTP).
# ---------------------------------------------------------------------------
SMTP_HOST = os.getenv("SMTP_HOST", "").strip()
SMTP_PORT = int(os.getenv("SMTP_PORT", "587") or 587)
SMTP_USER = os.getenv("SMTP_USER", "").strip()
SMTP_PASS = os.getenv("SMTP_PASS", "")
SMTP_FROM = os.getenv("SMTP_FROM", "").strip()
SMTP_FROM_NAME = os.getenv("SMTP_FROM_NAME", "خانه ماورا").strip()
SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "true").strip().lower() == "true"

APP_NAME = "Mavara Reservation Platform"
VERSION = "1.0.0"
SCHEMA_VERSION_APP_LABEL = f"{APP_NAME} v{VERSION}"
