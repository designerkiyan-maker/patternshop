# -*- coding: utf-8 -*-
"""
تنظیمات اصلی بات فروش الگوی خیاطی

نکته مهم: مقادیر حساس (توکن، آیدی ادمین) از فایل .env خوانده می‌شوند و
داخل این فایل هاردکد نیستند تا در صورت آپلود پروژه روی گیت‌هاب لو نروند.
اگر فایل .env وجود نداشته باشد، این فایل با خطا متوقف می‌شود تا از اجرای
تصادفی بدون تنظیمات درست جلوگیری شود.
"""

import os

# مسیر مطلق پوشهی پروژه — قبل از load_dotenv محاسبه میشود تا
# .env همیشه از کنار همین فایل خوانده شود، فارغ از cwd سرویس/پروسه.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
from dotenv import load_dotenv

load_dotenv(os.path.join(BASE_DIR, ".env"))

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

DB_PATH = os.path.join(BASE_DIR, "bot_database.db")

# حداکثر تعداد الگوی نمونه‌ی رایگان مجاز برای هر کاربر
MAX_TEST_PER_USER = 1

# آدرس HTTPS مینی‌اپ (فروشگاه وب داخل تلگرام)؛ خالی یعنی دکمه‌ی فروشگاه وب نمایش داده نمی‌شود
MINIAPP_URL = os.getenv("MINIAPP_URL", "").rstrip("/")
TELEGRAM_PROXY = "http://127.0.0.1:18080"

# ---------------------------------------------------------------------------
# پسوندهای مجاز فایل‌های محصول (و «الگوی نمونه») — هم در پنل وب و هم در بات
# با همین لیست اعتبارسنجی می‌شود تا ورودی‌ها یکدست بمانند.
#   Vector:        AI, EPS, SVG, PDF, CDR, DXF, DWG, WMF, EMF
#   Fashion:       DXF, ASTM, AAMA, RUL, PDS, MDL, PAT (+ فرمت‌های نرم‌افزاری رایج)
#   Raster:        PSD, TIFF, PNG, JPG, WEBP
#   CLO_3D/PLT:    ZPRJ, ZPAC, AVATAR, GMOD, PLT
# پیش‌نمایش محصول جدا است و همان محدودیت عکس (image/*) را دارد.
# ---------------------------------------------------------------------------
ALLOWED_PRODUCT_FILE_EXTENSIONS = (
    # Vector
    ".ai", ".eps", ".svg", ".pdf", ".cdr", ".dxf", ".dwg", ".wmf", ".emf",
    # Fashion pattern + فرمت‌های نرم‌افزاری رایج (Optitex/Lectra/...)
    ".astm", ".aama", ".rul", ".pds", ".mdl", ".pat", ".dsn", ".iba",
    # Raster
    ".psd", ".tif", ".tiff", ".png", ".jpg", ".jpeg", ".webp",
    # CLO_3D + PLT
    ".zprj", ".zpac", ".avatar", ".gmod", ".plt",
    # بسته‌های زیپ‌شده‌ی فرمت‌های نرم‌افزاری
    ".zip", ".rar", ".7z",
)


def is_allowed_product_filename(filename: str) -> bool:
    """آیا پسوند این نام فایل در لیست مجاز فایل‌های محصول هست؟ (مقایسه‌ی case-insensitive)"""
    name = (filename or "").lower().strip()
    return name.endswith(tuple(ALLOWED_PRODUCT_FILE_EXTENSIONS))
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
