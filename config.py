# -*- coding: utf-8 -*-
"""
تنظیمات اصلی بات فروش الگوی خیاطی

نکته مهم: مقادیر حساس (توکن، آیدی ادمین) از فایل .env خوانده می‌شوند و
داخل این فایل هاردکد نیستند تا در صورت آپلود پروژه روی گیت‌هاب لو نروند.
اگر فایل .env وجود نداشته باشد، این فایل با خطا متوقف می‌شود تا از اجرای
تصادفی بدون تنظیمات درست جلوگیری شود.
"""

import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID_RAW = os.getenv("OWNER_ID")

if not BOT_TOKEN:
    raise RuntimeError(
        "BOT_TOKEN تنظیم نشده است. یک فایل .env در کنار main.py بساز و مقدار "
        "BOT_TOKEN=توکن_بات_تو را داخلش قرار بده."
    )

if not OWNER_ID_RAW or not OWNER_ID_RAW.strip().lstrip("-").isdigit():
    raise RuntimeError(
        "OWNER_ID تنظیم نشده یا عدد معتبر نیست. داخل فایل .env مقدار "
        "OWNER_ID=آیدی_عددی_تو را قرار بده."
    )

OWNER_ID = int(OWNER_ID_RAW)

# پوشه‌ی ریشه‌ی پروژه (مطلق) - برای اینکه مسیر دیتابیس به cwd پروسه‌ای که
# main.py با آن اجرا می‌شود وابسته نباشد
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# مسیر فایل دیتابیس بات
DB_PATH = os.path.join(BASE_DIR, "bot_database.db")

# حداکثر تعداد الگوی نمونه‌ی رایگان مجاز برای هر کاربر
MAX_TEST_PER_USER = 1

# آدرس HTTPS مینی‌اپ (فروشگاه وب داخل تلگرام)؛ خالی یعنی دکمه‌ی فروشگاه وب نمایش داده نمی‌شود
MINIAPP_URL = os.getenv("MINIAPP_URL", "").rstrip("/")

# کلید امضای نشست (session) پنل مدیریت وب مستقل. اگر ست نشود، هر ری‌استارت
# پروسه همه‌ی نشست‌ها را باطل می‌کند (لاگین مجدد لازم می‌شود) اما خطایی نمی‌دهد.
ADMIN_PANEL_SECRET = os.getenv("ADMIN_PANEL_SECRET", "")
if not ADMIN_PANEL_SECRET:
    import secrets as _secrets
    ADMIN_PANEL_SECRET = _secrets.token_hex(32)

# کلیدهای VAPID برای اعلان Push مرورگر در پنل مدیریت وب (با دستور زیر ساخته می‌شوند:
# python -m admin_panel.generate_vapid_keys)؛ خالی یعنی فقط Push غیرفعال است.
VAPID_PUBLIC_KEY = os.getenv("VAPID_PUBLIC_KEY", "")
VAPID_PRIVATE_KEY = os.getenv("VAPID_PRIVATE_KEY", "")
VAPID_CLAIM_EMAIL = os.getenv("VAPID_CLAIM_EMAIL", "admin@example.com")
