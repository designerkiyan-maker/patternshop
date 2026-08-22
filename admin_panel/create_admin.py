# -*- coding: utf-8 -*-
"""
ساخت اولین حساب مالک (owner) پنل وب مستقل، یا ریست پسورد یک حساب موجود.

استفاده:
    python -m admin_panel.create_admin <username> <password>

اگر یوزرنیم قبلاً وجود داشته باشد، پسوردش با مقدار جدید آپدیت می‌شود.
اولین حساب همیشه owner ساخته می‌شود؛ حساب‌های بعدی را از داخل خودِ پنل
(بخش «کاربران پنل») با نقش دلخواه بساز.
"""

import sys

from config import DB_PATH
from database import Database
from admin_panel.security import hash_password


def main():
    if len(sys.argv) != 3:
        print("استفاده: python -m admin_panel.create_admin <username> <password>")
        sys.exit(1)

    username, password = sys.argv[1].strip().lower(), sys.argv[2]
    if len(password) < 8:
        print("پسورد باید حداقل ۸ کاراکتر باشد.")
        sys.exit(1)

    db = Database(DB_PATH)
    existing = db.get_web_admin_by_username(username)
    pw_hash = hash_password(password)

    if existing:
        db.set_web_admin_password(existing["id"], pw_hash)
        print(f"پسورد کاربر «{username}» (نقش: {existing['role']}) آپدیت شد.")
        return

    is_first = db.count_web_admins() == 0
    role = "owner" if is_first else "admin"
    db.create_web_admin(username, pw_hash, role)
    print(f"کاربر «{username}» با نقش «{role}» ساخته شد.")


if __name__ == "__main__":
    main()
