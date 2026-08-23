"""
Single place that knows how to open a SQLite connection.
Uses WAL mode + foreign keys so the small write-heavy Telegram-bot
workload doesn't lock itself out, and so FK constraints are enforced.

Concurrency note: SQLite allows many readers but only one writer at a
time. With several admins/operators clicking buttons simultaneously,
two writes can collide. PRAGMA busy_timeout below is the real defense —
it makes SQLite itself wait and retry *internally*, inside the C
library, for up to 10 seconds before ever raising 'database is locked'
to Python. That covers the overwhelming majority of real contention.
A thin retry only wraps commit() itself (see below) as a second, very
narrow safety net — it deliberately does NOT retry the caller's
with-block body, since re-running arbitrary already-executed code would
not be safe.
"""
import sqlite3
import time
from contextlib import contextmanager

from config.settings import DB_PATH

_BUSY_TIMEOUT_MS = 10_000
_COMMIT_RETRIES = 3


def _configure(conn: sqlite3.Connection) -> sqlite3.Connection:
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute(f"PRAGMA busy_timeout = {_BUSY_TIMEOUT_MS}")
    return conn


def _commit_with_retry(conn: sqlite3.Connection) -> None:
    for attempt in range(_COMMIT_RETRIES):
        try:
            conn.commit()
            return
        except sqlite3.OperationalError as exc:
            if "locked" not in str(exc).lower() or attempt == _COMMIT_RETRIES - 1:
                raise
            time.sleep(0.2 * (attempt + 1))


@contextmanager
def get_connection():
    """
    Context manager: commits on success, rolls back on exception,
    always closes. Use as:
        with get_connection() as conn:
            conn.execute(...)
    """
    conn = _configure(sqlite3.connect(DB_PATH, timeout=_BUSY_TIMEOUT_MS / 1000))
    try:
        yield conn
        _commit_with_retry(conn)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
