#!/usr/bin/env python3
"""
Creates a website admin account (username + password) for logging into
the admin panel. Run once to bootstrap the first account; run again any
time to add more admins.

Usage:
    python create_web_admin.py
"""
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


def main() -> None:
    from database.schema import init_db
    from database.repositories import web_admins as web_admins_repo
    from utils.auth import hash_password, JWT_SECRET

    if not JWT_SECRET:
        print("⚠️  JWT_SECRET is not set in .env — set it before using this in production.")
        print("   (Local testing without it still works, tokens just aren't safely signed.)")
        print()

    init_db()

    # Non-interactive mode: python create_web_admin.py <username> <password>
    # (for scripted deployment / automated testing — interactive prompts
    # below are for normal manual use, which is safer since the password
    # never ends up in shell history).
    if len(sys.argv) == 3:
        username, password = sys.argv[1], sys.argv[2]
    else:
        username = input("Username: ").strip()
        if not username:
            print("❌ Username cannot be empty.")
            return
        password = getpass.getpass("Password (min 10 characters): ")
        confirm = getpass.getpass("Confirm password: ")
        if password != confirm:
            print("❌ Passwords don't match.")
            return

    if not username:
        print("❌ Username cannot be empty.")
        return
    if len(password) < 10:
        print("❌ Password must be at least 10 characters.")
        return
    if web_admins_repo.get_by_username(username):
        print(f"❌ '{username}' already exists.")
        return

    password_hash, password_salt = hash_password(password)
    admin_id = web_admins_repo.create(username, password_hash, password_salt, role="admin")
    print(f"✅ Created web admin '{username}' (id={admin_id}).")


if __name__ == "__main__":
    main()
