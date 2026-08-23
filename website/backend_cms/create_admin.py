#!/usr/bin/env python3
"""
Creates (or resets the password of) a CMS admin account. Mirrors
bot/create_web_admin.py's role for the bot's own admin system — same
idea, separate database, separate account, on purpose (the two backends
share nothing — see README.md's "Split architecture" note).

Usage:
    python3 create_admin.py
"""
import getpass
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

from db import init_db, get_connection  # noqa: E402
from auth import hash_password  # noqa: E402


def main() -> None:
    init_db()
    username = input("نام کاربری ادمین: ").strip()
    if not username:
        print("❌ نام کاربری نمی‌تواند خالی باشد.")
        sys.exit(1)

    password = getpass.getpass("رمز عبور (حداقل ۱۰ کاراکتر): ")
    if len(password) < 10:
        print("❌ رمز عبور باید حداقل ۱۰ کاراکتر باشد.")
        sys.exit(1)
    password2 = getpass.getpass("تکرار رمز عبور: ")
    if password != password2:
        print("❌ رمزهای عبور یکسان نیستند.")
        sys.exit(1)

    password_hash, password_salt = hash_password(password)
    with get_connection() as conn:
        existing = conn.execute("SELECT id FROM cms_admins WHERE username=?", (username,)).fetchone()
        if existing:
            conn.execute(
                "UPDATE cms_admins SET password_hash=?, password_salt=?, is_active=1 WHERE username=?",
                (password_hash, password_salt, username),
            )
            print(f"✅ رمز عبور «{username}» به‌روزرسانی شد.")
        else:
            conn.execute(
                "INSERT INTO cms_admins(username, password_hash, password_salt, role) VALUES (?, ?, ?, 'owner')",
                (username, password_hash, password_salt),
            )
            print(f"✅ حساب ادمین «{username}» ساخته شد.")


if __name__ == "__main__":
    if not os.getenv("JWT_SECRET"):
        print("⚠️  JWT_SECRET در .env تنظیم نشده — قبل از استفاده‌ی واقعی از پنل، آن را پر کنید.")
    main()
