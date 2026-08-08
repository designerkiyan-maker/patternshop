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

# مسیر فایل دیتابیس بات اصلی
DB_PATH = "bot_database.db"

# پوشه‌ای که دیتابیس هر بات نمایندگی داخلش ذخیره می‌شود
RESELLER_DBS_DIR = "reseller_dbs"

# حداکثر تعداد کانفیگ تست مجاز برای هر کاربر
MAX_TEST_PER_USER = 1
