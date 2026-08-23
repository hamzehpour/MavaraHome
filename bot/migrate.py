#!/usr/bin/env python3
"""
Initializes or upgrades the database schema for the CURRENT environment
(whatever ENV/DB_PATH your .env currently points at). Safe to run any
number of times — every statement is idempotent (CREATE TABLE IF NOT
EXISTS, etc.), and existing data is never touched, only the schema.

This exists as its own script — separate from health_check.py, which is
read-only by design and must never create/migrate anything — specifically
for the situation where a database file exists (SQLite auto-creates an
empty file the moment anything connects to it) but was never actually
initialized, because the bot itself was never started once. health_check.py
will tell you exactly when this is the case and point you here.

Usage:
    python migrate.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


def main() -> None:
    from config.settings import ENV, DB_PATH
    from database.schema import init_db, SCHEMA_VERSION

    print(f"Environment: {ENV}")
    print(f"Database:    {DB_PATH}")
    print(f"Target schema version: {SCHEMA_VERSION}")
    print()

    if ENV == "production":
        answer = input(
            "⚠️  This is PRODUCTION. Continuing is safe (schema-only, no data "
            "loss) but confirm you mean to run this here. Type 'yes' to continue: "
        )
        if answer.strip().lower() != "yes":
            print("Aborted.")
            return

    init_db()
    print("✅ Schema is now up to date.")
    print("Run `python health_check.py` to verify.")


if __name__ == "__main__":
    main()
