"""
Schema + connection helper for the CMS's own SQLite database.

Deliberately a fresh, minimal schema — NOT the bot's database, NOT a
shared file. This backend only ever manages public site content
(events, resume/portfolio, team members) and its own admin accounts;
it knows nothing about reservations, payments, or tickets — see
README.md's "Split architecture" note for why.

Same connection pattern as bot/database/connection.py (WAL mode,
foreign keys, sqlite3.Row) — proven, no reason to do it differently here.
"""
import os
import sqlite3
from contextlib import contextmanager

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "data", "content.db")

SCHEMA = [
    """
    CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        title_en TEXT,
        description TEXT,
        description_en TEXT,
        location TEXT,
        location_en TEXT,
        date TEXT,
        status TEXT NOT NULL DEFAULT 'upcoming',
        tags TEXT,
        poster TEXT,
        gallery TEXT,
        video TEXT,
        contact_phone TEXT,
        contact_telegram TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """,
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
    """
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
    """,
    """
    CREATE TABLE IF NOT EXISTS cms_admins (
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
    "CREATE INDEX IF NOT EXISTS idx_portfolio_category ON portfolio(category)",
    "CREATE INDEX IF NOT EXISTS idx_team_status ON team_members(status)",
    "CREATE INDEX IF NOT EXISTS idx_events_status ON events(status)",
]


def init_db() -> None:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with get_connection() as conn:
        for statement in SCHEMA:
            conn.execute(statement)


@contextmanager
def get_connection():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 10000")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
