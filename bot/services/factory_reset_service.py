"""
In-bot factory reset — lets an owner wipe and reseed the CURRENT database
from inside Telegram, for test/development environments only.

SAFETY: this refuses unconditionally if IS_PRODUCTION is true. There is no
parameter or override that changes that — if this bot process is running
against production, this function is a guaranteed no-op.
"""
from config.settings import IS_PRODUCTION


def factory_reset_allowed() -> bool:
    return not IS_PRODUCTION


def perform_factory_reset() -> None:
    if IS_PRODUCTION:
        raise RuntimeError("Factory reset is disabled in production — this should be unreachable.")

    from database.connection import get_connection
    tables = [
        "logs", "channel_boards", "admin_groups", "waiting_list", "payments",
        "reservations", "sessions", "events", "bank_cards", "admins", "users", "settings",
    ]
    with get_connection() as conn:
        for table in tables:
            conn.execute(f"DELETE FROM {table}")

    from database.schema import init_db
    init_db()
