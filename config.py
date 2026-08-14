# -*- coding: utf-8 -*-
"""
تنظیمات اصلی بات

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
        "BOT_TOKEN=توکن_بات_تو را داخلش قرار بده (نمونه در .env.example موجود است)."
    )

if not OWNER_ID_RAW or not OWNER_ID_RAW.strip().lstrip("-").isdigit():
    raise RuntimeError(
        "OWNER_ID تنظیم نشده یا عدد معتبر نیست. داخل فایل .env مقدار "
        "OWNER_ID=آیدی_عددی_تو را قرار بده."
    )

OWNER_ID = int(OWNER_ID_RAW)

# پوشه‌ی ریشه‌ی پروژه (مطلق) - برای اینکه مسیر دیتابیس‌ها به cwd پروسه‌ای که
# main.py یا uvicorn (مینی‌اپ) با آن اجرا می‌شوند وابسته نباشد و همیشه یکی باشد
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# مسیر فایل دیتابیس بات اصلی
DB_PATH = os.path.join(BASE_DIR, "bot_database.db")

# پوشه‌ای که دیتابیس هر بات نمایندگی داخلش ذخیره می‌شود
RESELLER_DBS_DIR = os.path.join(BASE_DIR, "reseller_dbs")


def resolve_db_path(path: str) -> str:
    """مسیرهای قدیمی که ممکن است نسبی داخل دیتابیس ذخیره شده باشند را هم
    به مسیر مطلق تبدیل می‌کند (سازگاری با رکوردهای نمایندگی قدیمی‌تر)."""
    if not path:
        return path
    return path if os.path.isabs(path) else os.path.join(BASE_DIR, path)

# حداکثر تعداد کانفیگ تست مجاز برای هر کاربر
MAX_TEST_PER_USER = 1

# آدرس مینی‌اپ (باید HTTPS با گواهی معتبر باشد؛ خالی یعنی دکمه مینی‌اپ نمایش داده نشود)
MINIAPP_URL = os.getenv("MINIAPP_URL", "")

# آدرس پایه‌ی API مینی‌اپ (همان دامنه‌ای که سرور FastAPI روی آن سرو می‌شود؛
# برای ساخت callback_url که Plisio بعد از پرداخت به آن درخواست می‌زند لازم است)
API_BASE_URL = os.getenv("API_BASE_URL", "")

# کلید API درگاه پرداخت کریپتو Plisio (فقط در دیتابیس بات اصلی معنا دارد؛
# https://plisio.net -> Settings -> API Keys)
PLISIO_API_KEY = os.getenv("PLISIO_API_KEY", "")
