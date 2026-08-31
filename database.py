# -*- coding: utf-8 -*-
"""
لایه دیتابیس - SQLite

فروشگاه الگوی خیاطی: محصولات، فایل‌های PDF الگو (به‌صورت file_id تلگرام)،
سفارش‌ها با تأیید دستی رسید کارت‌به‌کارت، کد تخفیف، زیرمجموعه‌گیری، کیف پول،
الگوی نمونه رایگان و ... همگی در همین یک دیتابیس نگهداری می‌شوند.
"""

import asyncio
import logging
import sqlite3
import secrets
import threading
import time
import json
from datetime import datetime, timedelta
from contextlib import contextmanager

logger = logging.getLogger(__name__)

# مجوزهای granular پنل مدیریت (وب و تلگرام مشترک هستند؛ یک سیستم مدیریت واحد).
# هر ادمین (به‌جز owner که همیشه دسترسی کامل دارد) یک زیرمجموعه دلخواه از این
# کلیدها را می‌تواند داشته باشد.
WEB_ADMIN_PERMISSIONS = (
    "orders",      # تأیید/رد سفارش و شارژ کیف پول
    "users",       # بلاک/آنبلاک کاربر، تنظیم دستی موجودی کیف پول
    "catalog",     # دسته‌بندی‌ها، محصولات، فایل‌های الگو، واریانت‌ها
    "discounts",   # کدهای تخفیف
    "tickets",     # پاسخ/بستن تیکت و چت زنده پشتیبانی
    "broadcast",   # ارسال پیام همگانی
    "system",      # وضعیت جاب‌های سیستمی، وضعیت بکاپ، لاگ فعالیت ادمین‌ها
    "settings",    # تنظیمات و برندینگ
    "backup",      # ساخت بکاپ فوری دیتابیس (بازیابی همیشه فقط برای owner است)
    "inventory",   # مدیریت موجودی/آستانه‌ی هشدار واریانت‌های فیزیکی
    "shipping",    # روش‌های ارسال و تکمیل/پیگیری ارسال فیزیکی
)

# نگاشت نقش‌های ثابت (تلگرام و وب هر دو) به مجوزهای معادل - این همان «ماتریس
# کانونیکال» است و هر دو رابط باید از همین یک ماتریس بخوانند تا تضاد نقش وجود
# نداشته باشد (آسیب P1-3: تلگرام به پشتیبان اجازه‌ی تایید سفارش می‌داد ولی وب به
# او هیچ مجوزی نمی‌داد). پشتیبان (support) دقیقاً همان کاری که از نقشش برمی‌آید
# - پشتیبانی/تیکت - را در هر دو سطح انجام می‌دهد؛ تصمیمات مالی (سفارش/شارژ) نه.
ROLE_PERMISSION_PRESETS = {
    "owner": list(WEB_ADMIN_PERMISSIONS),
    "admin": ["orders", "users", "catalog", "discounts", "tickets", "broadcast",
              "system", "settings", "inventory", "shipping"],
    "mid": ["orders", "users", "tickets", "broadcast", "inventory"],
    "support": ["tickets"],
}


DEFAULT_SETTINGS = {
    "welcome_text": "👋 به فروشگاه الگوی خیاطی خوش آمدید!\nاز منوی زیر یکی از گزینه‌ها را انتخاب کنید.",
    "btn_buy": "🛒 خرید الگو",
    "btn_test": "🧪 الگوی نمونه رایگان",
    "btn_contact": "📞 ارتباط با پشتیبانی",
    "btn_my_orders": "📦 سفارش‌های من",
    "btn_referral": "🤝 زیرمجموعه‌گیری من",
    "btn_wallet": "👛 کیف پول من",
    "btn_admin_panel": "⚙️ پنل مدیریت",
    "test_enabled": "1",
    "force_join_enabled": "0",
    "force_join_channel": "",  # مثلاً: @mychannel
    "card_number": "0000-0000-0000-0000",
    "card_holder": "نام صاحب حساب",
    "contact_text": "پیام خود را بنویسید تا مستقیم برای پشتیبانی ارسال شود:",
    "after_buy_text": "برای تکمیل خرید، مبلغ را به شماره کارت زیر واریز کرده و سپس عکس رسید را ارسال کنید:",
    # رنگ دکمه‌ها (ویژگی جدید Bot API 9.4 / فوریه 2026)
    # مقادیر مجاز: "" (پیش‌فرض/خاکستری), "primary" (آبی), "success" (سبز), "danger" (قرمز)
    "btn_buy_style": "primary",
    "btn_test_style": "success",
    "btn_contact_style": "",
    "btn_my_orders_style": "",
    "btn_referral_style": "",
    "btn_wallet_style": "success",
    "btn_admin_panel_style": "danger",
    # نمایش منوی اصلی: منوی پایین (Reply) و منوی شیشه‌ای بالا (Inline) هرکدام
    # جداگانه قابل فعال/غیرفعال هستند، و چیدمان (۱ یا ۲ دکمه در هر ردیف) مشترک است
    "main_menu_reply_enabled": "1",
    "main_menu_inline_enabled": "0",
    "main_menu_columns": "1",
    "store_name": "🧵 الگوشاپ",
    # سیستم زیرمجموعه‌گیری
    # کلید مستر: مستقل از سه مدل زیر - غیرفعال کردنش کل سیستم رفرال (دکمه/تب و
    # هر سه مدل پاداش) را کاملاً خاموش می‌کند، صرف‌نظر از اینکه کدام مدل روشن باشد.
    "referral_button_enabled": "1",
    # حالت ۱: پورسانت درصدی از اولین خرید هر زیرمجموعه
    "referral_enabled": "1",
    "referral_percent": "10",  # درصدی که به دعوت‌کننده به‌عنوان اعتبار کیف پول تعلق می‌گیرد
    "referral_commission_max_count": "0",  # حداکثر تعداد نفراتی که پورسانت خریدشان تعلق می‌گیرد (0 = نامحدود)
    # حالت ۲: دریافت یک الگوی رایگان با رسیدن تعداد دعوت‌شده‌ها به یک آستانه (نیازی به خرید نیست)
    "referral_free_config_enabled": "0",
    "referral_free_config_threshold": "10",  # تعداد دعوت لازم
    "referral_free_config_product_id": "",  # آیدی محصولی که رایگان تحویل داده می‌شود
    # حالت ۳: شارژ ثابت کیف پول به‌ازای هر دعوت (بدون نیاز به خرید)، تا سقف مشخص
    "referral_invite_bonus_enabled": "0",
    "referral_invite_bonus_amount": "0",  # مبلغ ثابت شارژ کیف پول به‌ازای هر دعوت (تومان)
    "referral_invite_bonus_max_count": "10",  # حداکثر تعداد دعوت‌هایی که این پاداش برایشان تعلق می‌گیرد (0 = نامحدود)
    # رنگ دکمه‌های شیشه‌ای داخل پنل مدیریت
    "adm_categories_style": "",
    "adm_products_style": "",
    "adm_add_configs_style": "",
    "adm_test_menu_style": "",
    "adm_pending_orders_style": "primary",
    "adm_pending_topups_style": "primary",
    "adm_discounts_menu_style": "",
    "adm_referral_settings_style": "",
    "adm_edit_buttons_style": "",
    "adm_set_card_style": "",
    "adm_edit_welcome_style": "",
    "adm_admins_menu_style": "",
    "adm_broadcast_style": "",
    "adm_stats_style": "success",
    "adm_wheel_settings_style": "success",
    # رنگ دکمه‌های شیشه‌ای مسیر خرید (دسته‌بندی/محصول/تایید و ...)
    "btn_cat_select_style": "primary",
    "btn_product_select_style": "primary",
    "btn_buy_continue_style": "success",
    "btn_enter_code_style": "",
    "btn_buy_back_style": "",
    # گردونه شانس
    "wheel_enabled": "1",
    "wheel_win_percent": "10",  # درصد احتمال برد از هر چرخش
    "wheel_prizes": "10,20,30,50",  # درصدهای تخفیف ممکن؛ در صورت برد یکی تصادفی انتخاب می‌شود
    "wheel_code_expiry_hours": "24",  # اعتبار کد جایزه پس از برد (ساعت)
    "wheel_cooldown_hours": "24",  # فاصله مجاز بین دو چرخش هر کاربر
    "btn_wheel": "🎡 گردونه شانس",
    "btn_wheel_style": "success",
    # باشگاه مشتریان (Loyalty) - همه‌ی مقادیر از پنل ادمین قابل تغییر هستند
    "loyalty_enabled": "1",
    "loyalty_points_per_toman": "10000",  # هر «امتیاز» به ازای این تعداد تومان خرید (مبلغ نهایی پرداختی)
    "loyalty_reg_bonus": "50",  # هدیه‌ی یک‌بار ثبت‌نام (0 = خاموش)
    "loyalty_referral_bonus": "20",  # امتیاز معرفی: به دعوت‌کننده وقتی نفر جدید از لینک دعوت می‌آید (0 = خاموش)
    "loyalty_redeem_points": "100",  # این تعداد امتیاز...
    "loyalty_redeem_toman": "10000",  # ...به این مقدار تومان کیف پول تبدیل می‌شود
    "loyalty_min_redeem": "100",  # حداقل امتیاز قابل تبدیل در هر درخواست
    "loyalty_max_per_order": "0",  # سقف امتیاز یک سفارش (0 = نامحدود)
    "loyalty_tiers": '[{"id":"bronze","name":"🥉 برنز","min":0,"mult":100},{"id":"silver","name":"🥈 نقره‌ای","min":500,"mult":110},{"id":"gold","name":"🥇 طلایی","min":2000,"mult":125},{"id":"platinum","name":"💎 پلاتینیوم","min":5000,"mult":150}]',
    "btn_loyalty": "🎁 باشگاه مشتریان",
    "btn_loyalty_style": "",
    # بنرهای مینی‌اپ (پیش‌فرض‌های مینی‌اپ فروشگاه الگو)
    "miniapp_banners": '',
    # چیدمان دکمه‌های منوی اصلی (ترتیب و نمایش) - آرایه JSON از کلیدها
    "menu_order": '["btn_buy","btn_test","btn_my_orders","btn_wallet","btn_referral","btn_wheel","btn_loyalty","btn_contact","btn_admin_panel"]',
}


# تعریف کامل دکمه‌های قابل‌مدیریت در منوی اصلی: کلید -> متادیتا
# toggle_key: نام تنظیمی که فعال/غیرفعال بودن دکمه را کنترل می‌کند (None یعنی همیشه نمایش داده می‌شود)
# admin_only: اگر True فقط برای ادمین‌ها نمایش داده می‌شود
MENU_BUTTON_META = {
    "btn_buy": {"label": "دکمه خرید الگو", "toggle_key": None, "admin_only": False, "has_text": True, "has_style": True},
    "btn_test": {"label": "دکمه الگوی نمونه", "toggle_key": "test_enabled", "admin_only": False, "has_text": True, "has_style": True},
    "btn_my_orders": {"label": "دکمه سفارش‌های من", "toggle_key": None, "admin_only": False, "has_text": True, "has_style": True},
    "btn_wallet": {"label": "دکمه کیف پول", "toggle_key": None, "admin_only": False, "has_text": True, "has_style": True},
    "btn_referral": {"label": "دکمه زیرمجموعه‌گیری", "toggle_key": "referral_button_enabled", "admin_only": False, "has_text": True, "has_style": True},
    "btn_wheel": {"label": "دکمه گردونه شانس", "toggle_key": "wheel_enabled", "admin_only": False, "has_text": True, "has_style": True},
    "btn_loyalty": {"label": "دکمه باشگاه مشتریان", "toggle_key": "loyalty_enabled", "admin_only": False, "has_text": True, "has_style": True},
    "btn_contact": {"label": "دکمه ارتباط با پشتیبانی", "toggle_key": None, "admin_only": False, "has_text": True, "has_style": True},
    "btn_admin_panel": {"label": "دکمه پنل مدیریت", "toggle_key": None, "admin_only": True, "has_text": True, "has_style": True},
}
DEFAULT_MENU_ORDER = [
    "btn_buy", "btn_test", "btn_my_orders", "btn_wallet", "btn_referral",
    "btn_wheel", "btn_loyalty", "btn_contact", "btn_admin_panel",
]


# بنرهای پیش‌فرض مینی‌اپ (پیش‌فرض‌های مینی‌اپ فروشگاه الگو)
DEFAULT_BANNERS = [
    {
        "id": "b_store",
        "icon": "🧵",
        "title": "الگوهای جدید را ببین!",
        "sub": "کاتالوگ الگوهای خیاطی با دانلود آنی",
        "cta": "بریم فروشگاه",
        "nav": "store",
        "bg": "linear-gradient(120deg, #0d1a12, #123a20 55%, #17532c)",
        "image": "",
        "image_only": False,
        "enabled": True,
    },
    {
        "id": "b_referral",
        "icon": "🤝",
        "title": "دوستاتو دعوت کن",
        "sub": "با دعوت از دوستان، اعتبار رایگان به کیف پولت اضافه کن.",
        "cta": "مشاهده لینک دعوت",
        "nav": "referral",
        "bg": "linear-gradient(120deg,#1a0d24,#3a1c33 55%,#53174a)",
        "image": "",
        "image_only": False,
        "enabled": True,
    },
]


class Database:
    _SETTINGS_CACHE_TTL = 8  # ثانیه؛ برای هماهنگی بین پردازش بات و Mini App
    _ADMIN_CACHE_TTL = 5  # ثانیه؛ کوتاه‌تر از تنظیمات چون نقش ادمین حساس‌تر است

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._conn = None
        self._settings_cache = None
        self._settings_cache_loaded_at = 0.0
        # is_admin()/get_admin_role() قبلاً به ازای *هر* پیام و *هر* کلیک هر
        # کاربر (چه ادمین چه غیرادمین) مستقیماً یک SELECT synchronous به
        # sqlite می‌زدند (در BlockedUserMiddleware، AdminPresenceMiddleware و
        # داخل خود هندلرها - گاهی چندبار برای یک کلیک). چون این کوئری‌ها روی
        # همان event loop تک‌رشته‌ای اجرا می‌شوند، هر برخورد با قفل نوشتن
        # (مثلاً هم‌زمان با Mini App) کل بات را فریز می‌کرد. جدول admins بسیار
        # کم‌تغییر است، پس مثل تنظیمات کش می‌شود؛ بعد از add/set_role/remove
        # فوراً invalidate می‌شود تا تغییرات همین پردازش بلافاصله اعمال شوند.
        self._admin_cache = None
        self._admin_cache_loaded_at = 0.0
        # مینی‌اپ (FastAPI) توابع sync را در threadpool اجرا می‌کند، یعنی
        # ممکن است چند ریکوئست هم‌زمان از تردهای مختلف به همین یک Database
        # (مثلاً main_db) دسترسی داشته باشند. بات‌های aiogram هم در یک
        # event loop تک‌رشته‌ای هستند، پس این لاک برای آن‌ها overhead
        # واقعی ندارد ولی برای مینی‌اپ لازم است.
        #
        # RLock (به‌جای Lock): توابعی مثل reward_referrer_if_first_purchase
        # قبلاً داخل خودشان (در حالی که اتصال را گرفته‌اند) get_setting صدا
        # می‌زدند که آن هم دوباره _get_conn را صدا می‌زند؛ با Lock معمولی این
        # دقیقاً مسیر deadlock (قفل روی همان اتصال مشترک) بود. RLock اجازه‌ی
        # ورود مجدد همان ترد را می‌دهد و چون تمام دسترسی‌ها به اتصال همچنان
        # زیر همین قفل سری‌سازی می‌شوند، کلاس ترد-ایمن می‌ماند. (با این حال
        # از نظر بهترین‌روش، به‌جای تکیه بر RLock، خواندن تنظیمات را هم از
        # داخل بلوک‌های دارای اتصال بیرون کشیده‌ایم.)
        self._lock = threading.RLock()

    async def cache_autorefresh_loop(self, interval: float = 2.0):
        """فقط برای پردازش بات (aiogram) استفاده می‌شود، نه مینی‌اپ/پنل وب.

        is_admin()/get_setting() وقتی TTL کش تمام شده باشد، یک بار خودشان
        مستقیم (synchronous) کش را دوباره می‌خوانند - این خواندن چون روی
        همان event loop مشترک تمام بات‌ها اجرا می‌شود، اگر درست همان لحظه
        فایل دیتابیس توسط پردازش دیگری (مینی‌اپ/پنل وب) قفل باشد، کل بات را
        تا چند ثانیه (busy_timeout) برای همه‌ی کاربران فریز می‌کند - از دید
        ادمین دقیقاً شبیه «کرش‌کردن دکمه‌ها»ست، بدون این‌که هیچ Exception ای
        لاگ شود چون در نهایت با موفقیت (بعد از انتظار) تمام می‌شود.

        این تابع در پس‌زمینه، با فاصله‌ی کوتاه‌تر از TTL کش، خودش را با
        asyncio.to_thread (یعنی روی یک ترد جدا، نه event loop اصلی) تازه
        نگه می‌دارد؛ در نتیجه وقتی is_admin()/get_setting() صدا زده می‌شوند،
        کش تقریباً همیشه هنوز تازه است و آن‌ها هرگز مجبور به خواندن مستقیم و
        بلوکه‌کننده از sqlite روی event loop اصلی نمی‌شوند."""
        while True:
            try:
                await asyncio.to_thread(self._load_settings_cache)
            except Exception:
                logger.exception("تازه‌سازی پس‌زمینه‌ی کش تنظیمات ناموفق بود (db_path=%s).", self.db_path)
            try:
                await asyncio.to_thread(self._load_admin_cache)
            except Exception:
                logger.exception("تازه‌سازی پس‌زمینه‌ی کش ادمین‌ها ناموفق بود (db_path=%s).", self.db_path)
            await asyncio.sleep(interval)

    # -----------------------------------------------------------------------
    # اتصال
    # -----------------------------------------------------------------------
    # به‌جای باز و بسته‌کردن یک اتصال جدید sqlite در هر کوئری (که overhead
    # قابل توجهی داشت، مخصوصاً چون فیلترهای روتر aiogram به ازای هر پیام
    # ورودی صدا زده می‌شوند)، یک اتصال persistent نگه می‌داریم.
    # check_same_thread=False + لاک، چون همین نمونه ممکن است بین تردهای
    # threadpool مینی‌اپ مشترک باشد.

    def _connect(self):
        conn = sqlite3.connect(self.db_path, check_same_thread=False, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        # WAL باعث می‌شود خواندن‌ها همزمان با نوشتن قفل نشوند (بات + مینی‌اپ + پنل ادمین)
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        # بدون busy_timeout، وقتی بات و مینی‌اپ (دو پروسه‌ی جدا) هم‌زمان روی همین
        # فایل دیتابیس می‌نویسند، هر کوئری که با یک نوشتن هم‌زمان تداخل کند فوراً
        # با خطای «database is locked» شکست می‌خورد.
        #
        # نکته‌ی مهم: این PRAGMA باعث نمی‌شود انتظار async/غیربلوکه باشد؛
        # sqlite3.Connection.execute() یک تابع synchronous است و در طول این
        # انتظار، کل event loop تک‌رشته‌ای aiogram (که همه‌ی بات‌ها - اصلی و
        # نمایندگی‌ها - در bot_manager.py روی آن اجرا می‌شوند) بلوکه می‌ماند؛
        # یعنی هیچ کلیدی برای هیچ کاربری پردازش نمی‌شود تا این انتظار تمام شود.
        # قبلاً این مقدار ۳۰۰۰۰ (۳۰ ثانیه) بود که باعث می‌شد یک برخورد قفل ساده
        # (مثلاً هم‌زمانی با یک نوشتن از Mini App) کل بات را تا ۳۰ ثانیه برای
        # همه فریز کند - دقیقاً همان «همه‌چیز قفل می‌شود» که از دید کاربر شبیه
        # کرش‌کردن دکمه‌هاست. مقدار پایین‌تر این حداکثر زمان فریز را محدود
        # می‌کند؛ اگر قفل زودتر باز نشود، به‌جای فریز طولانی یک خطای
        # «database is locked» می‌دهد که توسط try/except هر هندلر یا هندلر
        # سراسری خطا (_global_error_handler) گرفته و به کاربر پیام کوتاه نشان
        # داده می‌شود - جایگزینی بسیار بهتر از فریز چندثانیه‌ای کل بات.
        conn.execute("PRAGMA busy_timeout = 4000")
        return conn

    @contextmanager
    def _get_conn(self):
        with self._lock:
            if self._conn is None:
                self._conn = self._connect()
            try:
                yield self._conn
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise

    @contextmanager
    def transaction(self):
        """تراکنش فوری (`BEGIN IMMEDIATE`) روی اتصال مشترک، برای عملیات مرکب
        اتمیک (تسویه‌ی سبد، رزرو موجودی، تأیید/رد مالی).

        BEGIN IMMEDIATE هنگام شروع، قفل نوشتن را رزرو می‌کند؛ نتیجه در حالت
        concurrent (مثلاً دو تسویه‌ی هم‌زمان از یک سبد بین پردازش بات و Mini App)
        سری‌سازیِ خودکار است: فراخوانی دوم تا commit شدن فراخوانی اول صبر می‌کند
        و سپس وضعیت متعهدشده را می‌بیند.

        هشدار: داخل این بلوک فقط باید دستور SQL مستقیم روی conn اجرا شود.
        صدا زدن متدهای دیگر دیتابیس (که _get_conn را باز می‌کنند) باعث commit
        زودهنگام/تداخل می‌شود - برای همین سرویس‌ها همه‌ی منطق تراکنش را با
        SQL روی همین conn می‌نویسند.
        """
        with self._lock:
            if self._conn is None:
                self._conn = self._connect()
            conn = self._conn
            conn.execute("BEGIN IMMEDIATE")
            try:
                yield conn
            except Exception:
                conn.rollback()
                raise
            else:
                conn.commit()

    def close(self):
        """اتصال persistent فعلی را می‌بندد و کش تنظیمات را پاک می‌کند. فراخوانی
        بعدی هر متدی خودش دوباره یک اتصال تازه باز می‌کند. لازم قبل از
        جایگزین‌کردن فایل دیتابیس (بازیابی بکاپ)."""
        with self._lock:
            if self._conn is not None:
                try:
                    self._conn.close()
                except Exception:
                    pass
                self._conn = None
            self._settings_cache = None
            self._admin_cache = None

    def init_db(self, owner_id: int):
        """owner_id: آیدی عددی کسی که مالک/ادمین اصلی همین یک نمونه از بات است
        (برای بات اصلی همان مالک بات، برای هر بات نمایندگی همان نماینده)."""
        with self._get_conn() as conn:
            c = conn.cursor()
            c.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_id INTEGER UNIQUE NOT NULL,
                    username TEXT,
                    first_name TEXT,
                    is_blocked INTEGER DEFAULT 0,
                    test_used INTEGER DEFAULT 0,
                    referred_by INTEGER,
                    referral_credit INTEGER DEFAULT 0,
                    referral_first_purchase_rewarded INTEGER DEFAULT 0,
                    referral_invite_bonus_given INTEGER DEFAULT 0,
                    referral_free_config_given INTEGER DEFAULT 0,
                    joined_at TEXT DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS admins (
                    telegram_id INTEGER PRIMARY KEY
                );

                CREATE TABLE IF NOT EXISTS categories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    is_active INTEGER DEFAULT 1,
                    sort_order INTEGER DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS products (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    price INTEGER NOT NULL,
                    description TEXT DEFAULT '',
                    preview_file_id TEXT DEFAULT '',
                    is_active INTEGER DEFAULT 1,
                    FOREIGN KEY(category_id) REFERENCES categories(id) ON DELETE CASCADE
                );

                -- فایل‌های الگو (PDF) هر محصول: file_id تلگرام. چون فروش نامحدود است،
                -- فایل‌ها هرگز مصرف نمی‌شوند (بدون is_used/assigned/order_id).
                CREATE TABLE IF NOT EXISTS product_files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_id INTEGER NOT NULL,
                    file_id TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(product_id) REFERENCES products(id) ON DELETE CASCADE
                );

                -- الگوهای نمونه رایگان (بدون مصرف - همیشه قابل ارسال مجدد هستند)
                CREATE TABLE IF NOT EXISTS sample_files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_id TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    product_id INTEGER NOT NULL,
                    status TEXT DEFAULT 'pending',
                    receipt_file_id TEXT,
                    receipt_type TEXT DEFAULT 'photo',
                    file_ids TEXT DEFAULT '',
                    admin_chat_id INTEGER,
                    admin_message_id INTEGER,
                    base_price INTEGER,
                    wallet_used INTEGER DEFAULT 0,
                    discount_code_id INTEGER,
                    discount_amount INTEGER DEFAULT 0,
                    final_price INTEGER,
                    quantity INTEGER DEFAULT 1,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT,
                    user_deleted INTEGER DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                );

                CREATE TABLE IF NOT EXISTS discount_codes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    code TEXT UNIQUE NOT NULL,
                    percent INTEGER,
                    fixed_amount INTEGER,
                    max_uses INTEGER DEFAULT 0,
                    used_count INTEGER DEFAULT 0,
                    is_active INTEGER DEFAULT 1,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS wallet_topups (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    amount INTEGER NOT NULL,
                    status TEXT DEFAULT 'pending',
                    receipt_file_id TEXT,
                    receipt_type TEXT DEFAULT 'photo',
                    admin_chat_id INTEGER,
                    admin_message_id INTEGER,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT
                );

                CREATE TABLE IF NOT EXISTS support_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    sender TEXT NOT NULL,
                    message TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    is_read_by_user INTEGER DEFAULT 0,
                    is_read_by_admin INTEGER DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS support_conversations (
                    user_id INTEGER PRIMARY KEY,
                    assigned_admin_id INTEGER,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS admin_presence (
                    telegram_id INTEGER PRIMARY KEY,
                    last_seen TEXT DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS tickets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    subject TEXT NOT NULL,
                    status TEXT DEFAULT 'open',
                    claimed_by INTEGER,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS ticket_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticket_id INTEGER NOT NULL,
                    sender TEXT NOT NULL,
                    message TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    is_read_by_user INTEGER DEFAULT 0,
                    is_read_by_admin INTEGER DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS admin_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    admin_id INTEGER NOT NULL,
                    action TEXT NOT NULL,
                    details TEXT DEFAULT '',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );

                CREATE INDEX IF NOT EXISTS idx_users_telegram_id ON users(telegram_id);
                CREATE INDEX IF NOT EXISTS idx_users_referred_by ON users(referred_by);
                CREATE INDEX IF NOT EXISTS idx_products_category_id ON products(category_id);
                CREATE INDEX IF NOT EXISTS idx_product_files_product_id ON product_files(product_id);
                CREATE INDEX IF NOT EXISTS idx_orders_user_id ON orders(user_id);
                CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
                CREATE INDEX IF NOT EXISTS idx_orders_product_id ON orders(product_id);
                CREATE INDEX IF NOT EXISTS idx_discount_codes_code ON discount_codes(code);
                CREATE INDEX IF NOT EXISTS idx_wallet_topups_user_id ON wallet_topups(user_id);
                CREATE INDEX IF NOT EXISTS idx_wallet_topups_status ON wallet_topups(status);
                CREATE INDEX IF NOT EXISTS idx_support_messages_user_id ON support_messages(user_id);
                CREATE INDEX IF NOT EXISTS idx_tickets_user_id ON tickets(user_id);
                CREATE INDEX IF NOT EXISTS idx_tickets_status ON tickets(status);
                CREATE INDEX IF NOT EXISTS idx_ticket_messages_ticket_id ON ticket_messages(ticket_id);

                -- ===================== پنل مدیریت وب مستقل (خارج از تلگرام) =====================
                CREATE TABLE IF NOT EXISTS web_admins (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'admin',
                    is_active INTEGER DEFAULT 1,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    last_login TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_web_admins_username ON web_admins(username);

                CREATE TABLE IF NOT EXISTS web_push_subscriptions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    admin_id INTEGER NOT NULL,
                    endpoint TEXT UNIQUE NOT NULL,
                    p256dh TEXT NOT NULL,
                    auth TEXT NOT NULL,
                    user_agent TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_push_subs_admin ON web_push_subscriptions(admin_id);

                CREATE TABLE IF NOT EXISTS loyalty_state (
                    user_id INTEGER PRIMARY KEY REFERENCES users(telegram_id) ON DELETE CASCADE,
                    current_points INTEGER NOT NULL DEFAULT 0 CHECK (current_points >= 0),
                    lifetime_earned INTEGER NOT NULL DEFAULT 0,
                    lifetime_spent INTEGER NOT NULL DEFAULT 0,
                    tier TEXT DEFAULT '',
                    last_activity_at TEXT DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS loyalty_ledger (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
                    tx_type TEXT NOT NULL,
                    amount INTEGER NOT NULL CHECK (amount <> 0),
                    balance_after INTEGER NOT NULL CHECK (balance_after >= 0),
                    reference_type TEXT,
                    reference_id TEXT,
                    idem_key TEXT,
                    description TEXT,
                    metadata TEXT,
                    expires_at TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
                CREATE UNIQUE INDEX IF NOT EXISTS uq_ledger_idem
                    ON loyalty_ledger(idem_key) WHERE idem_key IS NOT NULL;
                CREATE INDEX IF NOT EXISTS idx_ledger_user ON loyalty_ledger(user_id, id DESC);
                CREATE INDEX IF NOT EXISTS idx_ledger_created ON loyalty_ledger(created_at);
                CREATE INDEX IF NOT EXISTS idx_ledger_ref ON loyalty_ledger(reference_type, reference_id);
                """
            )

            c.execute("INSERT OR IGNORE INTO admins (telegram_id) VALUES (?)", (owner_id,))

            for k, v in DEFAULT_SETTINGS.items():
                c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v))

            self._migrate_columns(conn)
            self._migrate_commerce(conn)
            # اطمینان از این‌که همیشه مالک اصلی (از env) نقش «owner» را داشته باشد،
            # چه در نصب تازه و چه در ارتقای نصب‌های قدیمی‌تر که این ستون را نداشتند.
            conn.execute("UPDATE admins SET role='owner' WHERE telegram_id=?", (owner_id,))

    def _column_exists(self, conn, table: str, column: str) -> bool:
        # pragma_table_info به‌صورت table-valued function با پارامتر bind صدا زده
        # می‌شود تا هیچ کوئری داینامیکی ساخته نشود (ضد SQL injection).
        try:
            row = conn.execute(
                "SELECT 1 FROM pragma_table_info(?) WHERE name = ? LIMIT 1",
                (table, column),
            ).fetchone()
        except sqlite3.OperationalError:
            # جدول وجود ندارد یا نسخه‌ی sqlite از pragma function پشتیبانی نمی‌کند
            return False
        return row is not None

    def _migrate_columns(self, conn):
        # هر مهاجرت یک کوئری کاملِ «ثابت» است (بدون ساخت داینامیک رشته‌ی SQL
        # — ضد SQL injection). قبل از اجرا فقط با _column_exists چک می‌شود.
        if not self._column_exists(conn, "users", "referred_by"):
            conn.execute("ALTER TABLE users ADD COLUMN referred_by INTEGER")
        if not self._column_exists(conn, "users", "referral_credit"):
            conn.execute("ALTER TABLE users ADD COLUMN referral_credit INTEGER DEFAULT 0")
        if not self._column_exists(conn, "users", "referral_first_purchase_rewarded"):
            conn.execute("ALTER TABLE users ADD COLUMN referral_first_purchase_rewarded INTEGER DEFAULT 0")
        if not self._column_exists(conn, "users", "referral_invite_bonus_given"):
            conn.execute("ALTER TABLE users ADD COLUMN referral_invite_bonus_given INTEGER DEFAULT 0")
        if not self._column_exists(conn, "users", "referral_free_config_given"):
            conn.execute("ALTER TABLE users ADD COLUMN referral_free_config_given INTEGER DEFAULT 0")
        if not self._column_exists(conn, "users", "last_wheel_spin_at"):
            conn.execute("ALTER TABLE users ADD COLUMN last_wheel_spin_at TEXT")
        if not self._column_exists(conn, "orders", "status"):
            conn.execute("ALTER TABLE orders ADD COLUMN status TEXT DEFAULT 'pending'")
        if not self._column_exists(conn, "orders", "base_price"):
            conn.execute("ALTER TABLE orders ADD COLUMN base_price INTEGER")
        if not self._column_exists(conn, "orders", "wallet_used"):
            conn.execute("ALTER TABLE orders ADD COLUMN wallet_used INTEGER DEFAULT 0")
        if not self._column_exists(conn, "orders", "discount_code_id"):
            conn.execute("ALTER TABLE orders ADD COLUMN discount_code_id INTEGER")
        if not self._column_exists(conn, "orders", "discount_amount"):
            conn.execute("ALTER TABLE orders ADD COLUMN discount_amount INTEGER DEFAULT 0")
        if not self._column_exists(conn, "orders", "final_price"):
            conn.execute("ALTER TABLE orders ADD COLUMN final_price INTEGER")
        if not self._column_exists(conn, "orders", "receipt_type"):
            conn.execute("ALTER TABLE orders ADD COLUMN receipt_type TEXT DEFAULT 'photo'")
        if not self._column_exists(conn, "orders", "quantity"):
            conn.execute("ALTER TABLE orders ADD COLUMN quantity INTEGER DEFAULT 1")
        # شناسه‌های فایل‌های الگوی تحویل‌شده‌ی سفارش (CSV از product_files.id)
        if not self._column_exists(conn, "orders", "file_ids"):
            conn.execute("ALTER TABLE orders ADD COLUMN file_ids TEXT DEFAULT ''")
        # حذف سفارش از لیست «سفارش‌های من» توسط خود کاربر؛ سفارش از دیتابیس و
        # گزارش‌های ادمین حذف نمی‌شود و فقط از لیست کاربر مخفی می‌شود.
        if not self._column_exists(conn, "orders", "user_deleted"):
            conn.execute("ALTER TABLE orders ADD COLUMN user_deleted INTEGER DEFAULT 0")
        if not self._column_exists(conn, "products", "preview_file_id"):
            conn.execute("ALTER TABLE products ADD COLUMN preview_file_id TEXT DEFAULT ''")
        if not self._column_exists(conn, "wallet_topups", "receipt_type"):
            conn.execute("ALTER TABLE wallet_topups ADD COLUMN receipt_type TEXT DEFAULT 'photo'")
        if not self._column_exists(conn, "discount_codes", "expires_at"):
            conn.execute("ALTER TABLE discount_codes ADD COLUMN expires_at TEXT")
        if not self._column_exists(conn, "discount_codes", "source"):
            conn.execute("ALTER TABLE discount_codes ADD COLUMN source TEXT")
        if not self._column_exists(conn, "admins", "role"):
            conn.execute("ALTER TABLE admins ADD COLUMN role TEXT DEFAULT 'admin'")
        if not self._column_exists(conn, "support_messages", "is_read_by_admin"):
            conn.execute("ALTER TABLE support_messages ADD COLUMN is_read_by_admin INTEGER DEFAULT 0")
        if not self._column_exists(conn, "tickets", "claimed_by"):
            conn.execute("ALTER TABLE tickets ADD COLUMN claimed_by INTEGER")
        if not self._column_exists(conn, "web_admins", "permissions"):
            conn.execute("ALTER TABLE web_admins ADD COLUMN permissions TEXT")
        if not self._column_exists(conn, "admin_logs", "record_type"):
            conn.execute("ALTER TABLE admin_logs ADD COLUMN record_type TEXT")
        if not self._column_exists(conn, "admin_logs", "record_id"):
            conn.execute("ALTER TABLE admin_logs ADD COLUMN record_id TEXT")

        # مهاجرت نقش‌های ثابت قدیمی (owner/admin/mid/support) به مجموعه
        # مجوزهای granular. فقط رکوردهایی که هنوز permissions ندارند پر می‌شوند
        # تا override دستی مالک روی حساب‌های موجود دست‌نخورده بماند.
        if self._column_exists(conn, "web_admins", "permissions"):
            legacy_rows = conn.execute(
                "SELECT id, role FROM web_admins WHERE permissions IS NULL"
            ).fetchall()
            for row in legacy_rows:
                perms = ROLE_PERMISSION_PRESETS.get(row["role"], ROLE_PERMISSION_PRESETS["support"])
                conn.execute(
                    "UPDATE web_admins SET permissions=? WHERE id=?",
                    (json.dumps(perms), row["id"]),
                )

        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_admin_logs_record ON admin_logs(record_type, record_id)"
        )

    def _migrate_commerce(self, conn):
        """مهاجرت‌های لایه‌ی تجارت یکپارچه (سبد، واریانت، موجودی، ارسال، سبدچندقلمی).
        همه‌ی دستورات idempotent هستند (CREATE TABLE IF NOT EXISTS / ALTER بر اساس
        _column_exists) و هیچ‌کدام داده‌ی موجود را حذف/تخریب نمی‌کنند."""
        conn.executescript(
            """
            -- سبد خرید کاربر (سرور-ساید). واریانت NULL یعنی محصول دیجیتال.
            CREATE TABLE IF NOT EXISTS cart_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                variant_id INTEGER,
                quantity INTEGER NOT NULL DEFAULT 1 CHECK (quantity > 0),
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT,
                FOREIGN KEY(user_id) REFERENCES users(telegram_id) ON DELETE CASCADE,
                FOREIGN KEY(product_id) REFERENCES products(id) ON DELETE CASCADE,
                FOREIGN KEY(variant_id) REFERENCES product_variants(id) ON DELETE CASCADE
            );

            -- واریانت‌های یک محصول فیزیکی (سایز/رنگ و...). محصول دیجیتال واریانت ندارد.
            CREATE TABLE IF NOT EXISTS product_variants (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER NOT NULL,
                label TEXT NOT NULL,
                price INTEGER,
                attributes TEXT DEFAULT '{}',
                sort_order INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT,
                FOREIGN KEY(product_id) REFERENCES products(id) ON DELETE CASCADE
            );

            -- موجودی هر واریانت (فقط محصولات فیزیکی). available = on_hand - reserved
            CREATE TABLE IF NOT EXISTS inventory (
                variant_id INTEGER PRIMARY KEY REFERENCES product_variants(id) ON DELETE CASCADE,
                on_hand INTEGER NOT NULL DEFAULT 0 CHECK (on_hand >= 0),
                reserved INTEGER NOT NULL DEFAULT 0 CHECK (reserved >= 0),
                low_stock_threshold INTEGER DEFAULT 0,
                updated_at TEXT
            );

            -- دفتر کل تغییرات موجودی (منبع ممیزی/گزارش)
            CREATE TABLE IF NOT EXISTS inventory_transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                variant_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                delta INTEGER NOT NULL,
                on_hand_after INTEGER NOT NULL,
                reason TEXT NOT NULL DEFAULT '',
                order_id INTEGER,
                actor TEXT DEFAULT '',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(variant_id) REFERENCES product_variants(id) ON DELETE CASCADE
            );

            -- روش‌های ارسال (هزینه متعلق به روش؛ برای سبد‌های فیزیکی الزامی)
            CREATE TABLE IF NOT EXISTS shipping_methods (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                cost INTEGER NOT NULL DEFAULT 0 CHECK (cost >= 0),
                delivery_note TEXT DEFAULT '',
                is_active INTEGER DEFAULT 1,
                position INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT
            );

            -- آدرس‌های مشتری (خانه در checkout فیزیکی آب‌نخورده per-order snapshot می‌شود)
            CREATE TABLE IF NOT EXISTS customer_addresses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                recipient_name TEXT NOT NULL,
                mobile TEXT NOT NULL,
                province TEXT NOT NULL,
                city TEXT NOT NULL,
                address TEXT NOT NULL,
                postal_code TEXT DEFAULT '',
                is_default INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT,
                FOREIGN KEY(user_id) REFERENCES users(telegram_id) ON DELETE CASCADE
            );

            -- اقلامِ هر سفارش (یک سفارش می‌تواند چند قلم داشته باشد؛ فروش قدیمی
            -- تک‌محصولی همیشه یک قلم خواهد داشت). product_name/unit_price snapshot
            -- هستند تا تغییر بعدی کاتالوگ به تاریخچه‌ی سفارش برخورد نکند.
            CREATE TABLE IF NOT EXISTS order_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                variant_id INTEGER,
                product_type TEXT DEFAULT 'digital',
                product_name TEXT NOT NULL,
                quantity INTEGER NOT NULL DEFAULT 1,
                unit_price INTEGER NOT NULL,
                total_price INTEGER NOT NULL,
                file_ids TEXT DEFAULT '',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(order_id) REFERENCES orders(id) ON DELETE CASCADE
            );

            -- کلید idempotency تسویه: کلید یکتا؛ برخوردِ هم‌زمان با UNIQUE رهگیری
            -- می‌شود و فقط یک تسویه واقعی اتفاق می‌افتد.
            CREATE TABLE IF NOT EXISTS checkout_idem (
                idem_key TEXT PRIMARY KEY,
                order_id INTEGER NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            -- بایگانی وضعیت ارسال/تکمیل فیزیکی (چه کسی، از چه به چه، کی)
            CREATE TABLE IF NOT EXISTS fulfillment_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER NOT NULL,
                from_status TEXT DEFAULT '',
                to_status TEXT NOT NULL,
                actor_type TEXT DEFAULT '',
                actor_id TEXT DEFAULT '',
                note TEXT DEFAULT '',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(order_id) REFERENCES orders(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_cart_user ON cart_items(user_id);
            DROP INDEX IF EXISTS idx_cart_item_user;
            -- شاخص یکتای مؤثر بر (کاربر، محصول، واریانت)؛ تا کلیدِ ON CONFLICT در
            -- upsert سبد match کند و یک کاربر برای یک محصولِ هم‌واریانت یک قلم داشته باشد
            CREATE UNIQUE INDEX IF NOT EXISTS idx_cart_item_user
                ON cart_items(user_id, product_id, COALESCE(variant_id, 0));
            CREATE INDEX IF NOT EXISTS idx_variants_product ON product_variants(product_id);
            CREATE INDEX IF NOT EXISTS idx_inv_tx_variant ON inventory_transactions(variant_id, id);
            CREATE INDEX IF NOT EXISTS idx_order_items_order ON order_items(order_id);
            CREATE INDEX IF NOT EXISTS idx_addresses_user ON customer_addresses(user_id);
            CREATE INDEX IF NOT EXISTS idx_fulfillment_order ON fulfillment_events(order_id, id);
            """
        )

        # ستون‌های جدید روی جدول‌های موجود (همه‌ی ALTER ها بر اساس _column_exists)
        if not self._column_exists(conn, "products", "type"):
            conn.execute("ALTER TABLE products ADD COLUMN type TEXT DEFAULT 'digital'")
        if not self._column_exists(conn, "orders", "payment_status"):
            conn.execute("ALTER TABLE orders ADD COLUMN payment_status TEXT DEFAULT 'pending'")
        if not self._column_exists(conn, "orders", "order_type"):
            conn.execute("ALTER TABLE orders ADD COLUMN order_type TEXT DEFAULT 'digital'")
        if not self._column_exists(conn, "orders", "shipping_cost"):
            conn.execute("ALTER TABLE orders ADD COLUMN shipping_cost INTEGER DEFAULT 0")
        if not self._column_exists(conn, "orders", "shipping_method_id"):
            conn.execute("ALTER TABLE orders ADD COLUMN shipping_method_id INTEGER")
        if not self._column_exists(conn, "orders", "tracking_number"):
            conn.execute("ALTER TABLE orders ADD COLUMN tracking_number TEXT DEFAULT ''")
        if not self._column_exists(conn, "orders", "physical_fulfillment_status"):
            conn.execute("ALTER TABLE orders ADD COLUMN physical_fulfillment_status TEXT DEFAULT 'processing'")
        if not self._column_exists(conn, "orders", "fulfillment_note"):
            conn.execute("ALTER TABLE orders ADD COLUMN fulfillment_note TEXT DEFAULT ''")
        if not self._column_exists(conn, "orders", "address_id"):
            conn.execute("ALTER TABLE orders ADD COLUMN address_id INTEGER")
        if not self._column_exists(conn, "orders", "recipient_name"):
            conn.execute("ALTER TABLE orders ADD COLUMN recipient_name TEXT DEFAULT ''")
        if not self._column_exists(conn, "orders", "recipient_mobile"):
            conn.execute("ALTER TABLE orders ADD COLUMN recipient_mobile TEXT DEFAULT ''")
        if not self._column_exists(conn, "orders", "recipient_address"):
            conn.execute("ALTER TABLE orders ADD COLUMN recipient_address TEXT DEFAULT ''")
        if not self._column_exists(conn, "orders", "customer_note"):
            conn.execute("ALTER TABLE orders ADD COLUMN customer_note TEXT DEFAULT ''")
        if not self._column_exists(conn, "orders", "idem_key"):
            conn.execute("ALTER TABLE orders ADD COLUMN idem_key TEXT DEFAULT ''")

        # backfill وضعیت پرداخت از وضعیت قدیمی (فقط رکوردهای دارای NULL/پیش‌فرض)
        conn.execute(
            "UPDATE orders SET payment_status='paid' "
            "WHERE status='approved' AND (payment_status IS NULL OR payment_status='pending')"
        )
        conn.execute(
            "UPDATE orders SET payment_status='refunded' "
            "WHERE status='rejected' AND (payment_status IS NULL OR payment_status='pending')"
        )

        # تنظیماتِ جدیدِ لایه‌ی تجارت (فقط در صورت نبودن ثبت می‌شوند تا تنظیم
        # دستیِ اپراتور overwrite نشود)
        for _key, _val in (
            ("btn_cart", "🛒 سبد خرید"),
            ("btn_cart_style", "primary"),
            ("cart_enabled", "1"),
            ("physical_products_enabled", "1"),
            ("checkout_auto_approve_wallet", "1"),
        ):
            conn.execute(
                "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (_key, _val)
            )

    # -----------------------------------------------------------------------
    # تنظیمات (settings)
    # -----------------------------------------------------------------------

    def get_setting(self, key: str, default: str = "") -> str:
        # تنظیمات در حافظه کش می‌شوند چون به ازای هر پیام ورودی (فیلترهای
        # روتر در handlers_user.py) چندین بار خوانده می‌شوند؛ خواندن از dict
        # به‌جای query جدید sqlite تفاوت محسوسی در سرعت پاسخ‌گویی ایجاد می‌کند.
        # نکته: بات و Mini App دو پردازش جدا هستند، هرکدام کش خودشان را دارند؛
        # به همین دلیل این کش یک TTL کوتاه دارد تا تغییراتی که از پردازش دیگر
        # ذخیره می‌شوند (مثلاً چیدمان منو از Mini App) بعد از چند ثانیه در بات
        # هم اعمال شوند، بدون این‌که هر پیام مستقیم به sqlite بزند.
        self._maybe_reload_settings_cache()
        return self._settings_cache.get(key, default)

    def _maybe_reload_settings_cache(self):
        now = time.monotonic()
        if self._settings_cache is None or (now - self._settings_cache_loaded_at) > self._SETTINGS_CACHE_TTL:
            self._load_settings_cache()

    def _load_settings_cache(self):
        with self._get_conn() as conn:
            rows = conn.execute("SELECT key, value FROM settings").fetchall()
            cache = {r["key"]: r["value"] for r in rows}
        with self._lock:
            self._settings_cache = cache
            self._settings_cache_loaded_at = time.monotonic()

    def set_setting(self, key: str, value: str):
        with self._get_conn() as conn:
            conn.execute(
                "INSERT INTO settings (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, value),
            )
        if self._settings_cache is not None:
            self._settings_cache[key] = value

    def set_setting_default(self, key: str, value: str):
        """فقط اگر کلید هنوز وجود ندارد، مقدار پیش‌فرض را ثبت می‌کند
        (INSERT OR IGNORE) تا برای نصب‌های قدیمی، کلیدهای تجارت جدید ظاهر شوند."""
        with self._get_conn() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (key, value)
            )
        if self._settings_cache is not None and key not in self._settings_cache:
            self._settings_cache[key] = value

    def get_all_settings(self) -> dict:
        self._maybe_reload_settings_cache()
        return dict(self._settings_cache)

    # -----------------------------------------------------------------------
    # چیدمان منوی اصلی (ترتیب دکمه‌ها)
    # -----------------------------------------------------------------------

    def get_menu_order(self) -> list:
        """ترتیب کلیدهای دکمه‌های منوی اصلی را برمی‌گرداند. کلیدهای جدیدی که در
        تنظیمات ذخیره‌شده نیستند (مثلاً بعد از آپدیت پروژه) به انتهای لیست اضافه می‌شوند
        تا هیچ دکمه‌ای گم نشود."""
        import json
        raw = self.get_setting("menu_order", "")
        order = []
        if raw:
            try:
                order = [k for k in json.loads(raw) if k in DEFAULT_MENU_ORDER]
            except (ValueError, TypeError):
                order = []
        if not order:
            order = list(DEFAULT_MENU_ORDER)
        for k in DEFAULT_MENU_ORDER:
            if k not in order:
                order.append(k)
        return order

    def set_menu_order(self, order: list):
        import json
        clean = [k for k in order if k in DEFAULT_MENU_ORDER]
        for k in DEFAULT_MENU_ORDER:
            if k not in clean:
                clean.append(k)
        self.set_setting("menu_order", json.dumps(clean, ensure_ascii=False))

    def get_menu_row_breaks(self):
        """کلیدهایی که باید *قبل* از آن‌ها یک ردیف جدید در منو شروع شود.
        این یعنی چیدمان منو دیگر محدود به «همه‌ی دکمه‌ها زیر هم» یا «۲تا-۲تا»
        نیست: هر دکمه‌ای که اینجا نباشد به ردیف دکمه‌ی قبلی‌اش می‌چسبد، پس با
        همین یک لیست می‌شود مثلاً «یک دکمه تمام‌عرض، بعد دو دکمه کنار هم»
        ساخت. مقدار None یعنی کاربر هنوز چیدمان سفارشی نساخته - در این حالت
        فراخوان باید برای سازگاری با نصب‌های قدیمی از main_menu_columns
        استفاده کند (رفتار قبلی)."""
        import json
        raw = self.get_setting("main_menu_row_breaks", "")
        if not raw:
            return None
        try:
            data = json.loads(raw)
        except (ValueError, TypeError):
            return None
        if not isinstance(data, list):
            return None
        return [k for k in data if isinstance(k, str) and k in DEFAULT_MENU_ORDER]

    def set_menu_row_breaks(self, keys: list):
        import json
        clean = [k for k in keys if k in DEFAULT_MENU_ORDER]
        self.set_setting("main_menu_row_breaks", json.dumps(clean, ensure_ascii=False))

    # -----------------------------------------------------------------------
    # کاربران
    # -----------------------------------------------------------------------

    def add_or_update_user(self, tg_id: int, username: str, first_name: str):
        with self._get_conn() as conn:
            row = conn.execute("SELECT id FROM users WHERE telegram_id=?", (tg_id,)).fetchone()
            if row:
                conn.execute(
                    "UPDATE users SET username=?, first_name=? WHERE telegram_id=?",
                    (username, first_name, tg_id),
                )
            else:
                conn.execute(
                    "INSERT INTO users (telegram_id, username, first_name) VALUES (?, ?, ?)",
                    (tg_id, username, first_name),
                )

    def get_user(self, tg_id: int):
        with self._get_conn() as conn:
            return conn.execute("SELECT * FROM users WHERE telegram_id=?", (tg_id,)).fetchone()

    def set_user_blocked(self, tg_id: int, blocked: bool):
        with self._get_conn() as conn:
            conn.execute("UPDATE users SET is_blocked=? WHERE telegram_id=?", (1 if blocked else 0, tg_id))

    def search_users(self, query: str = "", status_filter: str = "all", limit: int = 30, offset: int = 0):
        """جستجو/فیلتر کاربران برای پنل مدیریت.
        status_filter: 'all' | 'active' (حداقل یک خرید تاییدشده دارد) |
                       'expired' (سفارش ثبت کرده ولی هیچ خرید تاییدشده‌ای ندارد) | 'blocked'
        خروجی: (rows, total_count)
        """
        conditions = []
        params = []

        if query:
            conditions.append("(CAST(u.telegram_id AS TEXT) LIKE ? OR u.username LIKE ? OR u.first_name LIKE ?)")
            like = f"%{query}%"
            params += [like, like, like]

        if status_filter == "blocked":
            conditions.append("u.is_blocked=1")
        elif status_filter == "active":
            conditions.append(
                "EXISTS (SELECT 1 FROM orders o WHERE o.user_id=u.telegram_id AND o.status='approved')"
            )
        elif status_filter == "expired":
            conditions.append(
                "EXISTS (SELECT 1 FROM orders o WHERE o.user_id=u.telegram_id) "
                "AND NOT EXISTS (SELECT 1 FROM orders o2 WHERE o2.user_id=u.telegram_id AND o2.status='approved')"
            )

        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        with self._get_conn() as conn:
            total = conn.execute(f"SELECT COUNT(*) c FROM users u {where}", params).fetchone()["c"]
            rows = conn.execute(
                f"SELECT u.* FROM users u {where} ORDER BY u.id DESC LIMIT ? OFFSET ?",
                params + [limit, offset],
            ).fetchall()
            return rows, total

    def get_user_status(self, tg_id: int) -> str:
        """وضعیت خلاصه‌ی یک کاربر: 'blocked' | 'active' (خرید تاییدشده دارد) |
        'expired' (سفارش داشته ولی هیچ خرید تاییدشده‌ای ندارد) | 'none' (هیچ سفارشی ندارد)."""
        with self._get_conn() as conn:
            u = conn.execute("SELECT is_blocked FROM users WHERE telegram_id=?", (tg_id,)).fetchone()
            if u and u["is_blocked"]:
                return "blocked"
            has_active = conn.execute(
                "SELECT 1 FROM orders WHERE user_id=? AND status='approved' LIMIT 1",
                (tg_id,),
            ).fetchone()
            if has_active:
                return "active"
            has_any = conn.execute(
                "SELECT 1 FROM orders WHERE user_id=? LIMIT 1", (tg_id,)
            ).fetchone()
            return "expired" if has_any else "none"

    def get_user_full_history(self, tg_id: int):
        """تاریخچه‌ی کامل یک کاربر: سفارش‌ها (با نام محصول) + شارژهای کیف‌پول."""
        with self._get_conn() as conn:
            orders = conn.execute(
                "SELECT o.*, p.name as product_name "
                "FROM orders o "
                "LEFT JOIN products p ON o.product_id = p.id "
                "WHERE o.user_id=? ORDER BY o.id DESC",
                (tg_id,),
            ).fetchall()
            topups = conn.execute(
                "SELECT * FROM wallet_topups WHERE user_id=? ORDER BY id DESC", (tg_id,)
            ).fetchall()
            return {"orders": orders, "topups": topups}

    def mark_test_used(self, tg_id: int):
        with self._get_conn() as conn:
            conn.execute("UPDATE users SET test_used=test_used+1 WHERE telegram_id=?", (tg_id,))

    def reset_user_sample_usage(self, tg_id: int) -> bool:
        """شمارنده‌ی دریافت الگوی نمونه‌ی یک کاربر مشخص را صفر می‌کند تا بتواند
        دوباره نمونه بگیرد. True اگر کاربر پیدا شد."""
        with self._get_conn() as conn:
            cur = conn.execute("UPDATE users SET test_used=0 WHERE telegram_id=?", (tg_id,))
            return cur.rowcount > 0

    def reset_all_test_usage(self) -> list:
        """test_used همه‌ی کاربرانی که قبلاً کانفیگ تست گرفته‌اند را صفر می‌کند تا
        دوباره بتوانند تست بگیرند. لیست آیدی همان کاربران را برمی‌گرداند تا بشود
        بهشان پیام اطلاع‌رسانی فرستاد."""
        with self._get_conn() as conn:
            rows = conn.execute("SELECT telegram_id FROM users WHERE test_used > 0").fetchall()
            user_ids = [r["telegram_id"] for r in rows]
            conn.execute("UPDATE users SET test_used=0 WHERE test_used > 0")
            return user_ids

    def get_all_user_ids(self):
        with self._get_conn() as conn:
            rows = conn.execute("SELECT telegram_id FROM users WHERE is_blocked=0").fetchall()
            return [r["telegram_id"] for r in rows]

    def count_users(self):
        with self._get_conn() as conn:
            return conn.execute("SELECT COUNT(*) c FROM users").fetchone()["c"]

    def _sqlite_retry(self, operation, attempts: int = 4, delay: float = 0.15):
        """اجرای عملیات SQLite با retry کوتاه برای برخوردهای موقت database is locked/busy."""
        last_error = None
        for attempt in range(attempts):
            try:
                return operation()
            except sqlite3.OperationalError as exc:
                last_error = exc
                if "locked" not in str(exc).lower() and "busy" not in str(exc).lower():
                    raise
                if attempt == attempts - 1:
                    raise
                time.sleep(delay * (attempt + 1))
        raise last_error

    # -----------------------------------------------------------------------
    # ادمین‌ها
    # -----------------------------------------------------------------------

    def _maybe_reload_admin_cache(self):
        now = time.monotonic()
        if self._admin_cache is None or (now - self._admin_cache_loaded_at) > self._ADMIN_CACHE_TTL:
            self._load_admin_cache()

    def _load_admin_cache(self):
        with self._get_conn() as conn:
            rows = conn.execute("SELECT telegram_id, role FROM admins").fetchall()
            cache = {r["telegram_id"]: (r["role"] or "admin") for r in rows}
        with self._lock:
            self._admin_cache = cache
            self._admin_cache_loaded_at = time.monotonic()

    def _invalidate_admin_cache(self):
        with self._lock:
            self._admin_cache = None

    def is_admin(self, tg_id: int) -> bool:
        self._maybe_reload_admin_cache()
        return tg_id in self._admin_cache

    def get_owner_telegram_id(self):
        """آیدی تلگرام مالک این بات (نقش owner در جدول admins)."""
        with self._get_conn() as conn:
            row = conn.execute("SELECT telegram_id FROM admins WHERE role='owner' LIMIT 1").fetchone()
            return row["telegram_id"] if row else None

    def get_admin_role(self, tg_id: int):
        """نقش ادمین را برمی‌گرداند: 'owner' | 'admin' | 'mid' | 'support' | None (اگر ادمین نباشد)."""
        self._maybe_reload_admin_cache()
        return self._admin_cache.get(tg_id)

    def is_full_admin(self, tg_id: int) -> bool:
        """دسترسی کامل عملیاتی: مالک، مدیر یا ادمین میانی (برخلاف پشتیبان که دسترسی محدود دارد)."""
        role = self.get_admin_role(tg_id)
        return role in ("owner", "admin", "mid")

    def is_senior_admin(self, tg_id: int) -> bool:
        """فقط مالک یا مدیر کامل؛ برای بخش‌های حساس که حتی ادمین میانی هم به آن‌ها دسترسی ندارد
        (آمار فروش، چیدمان منو، تنظیمات کمپین‌ها/تخفیف، لاگ ادمین،
        برندینگ فروشگاه، و مدیریت محصولات/دسته‌بندی‌ها/بانک فایل الگوها)."""
        role = self.get_admin_role(tg_id)
        return role in ("owner", "admin")

    def is_owner(self, tg_id: int) -> bool:
        return self.get_admin_role(tg_id) == "owner"

    def add_admin(self, tg_id: int, role: str = "admin"):
        if role not in ("admin", "mid", "support"):
            role = "admin"
        def op():
            with self._get_conn() as conn:
                conn.execute(
                    "INSERT INTO admins (telegram_id, role) VALUES (?, ?) "
                    "ON CONFLICT(telegram_id) DO UPDATE SET role=excluded.role",
                    (tg_id, role),
                )
        result = self._sqlite_retry(op)
        self._invalidate_admin_cache()
        return result

    def set_admin_role(self, tg_id: int, role: str) -> bool:
        """تغییر نقش یک ادمین موجود. نقش «owner» هرگز از این مسیر قابل واگذاری نیست."""
        if role not in ("admin", "mid", "support"):
            return False
        def op():
            with self._get_conn() as conn:
                row = conn.execute("SELECT role FROM admins WHERE telegram_id=?", (tg_id,)).fetchone()
                if not row or row["role"] == "owner":
                    return False
                conn.execute("UPDATE admins SET role=? WHERE telegram_id=?", (role, tg_id))
            return True
        result = self._sqlite_retry(op)
        self._invalidate_admin_cache()
        return result

    def remove_admin(self, tg_id: int, protected_owner_id: int = None) -> bool:
        if protected_owner_id is not None and tg_id == protected_owner_id:
            return False
        def op():
            with self._get_conn() as conn:
                row = conn.execute("SELECT role FROM admins WHERE telegram_id=?", (tg_id,)).fetchone()
                if row and row["role"] == "owner":
                    return False
                conn.execute("DELETE FROM admins WHERE telegram_id=?", (tg_id,))
            return True
        result = self._sqlite_retry(op)
        self._invalidate_admin_cache()
        return result

    def list_admins(self):
        with self._get_conn() as conn:
            rows = conn.execute("SELECT telegram_id FROM admins").fetchall()
            return [r["telegram_id"] for r in rows]

    def list_admins_with_roles(self):
        with self._get_conn() as conn:
            rows = conn.execute("SELECT telegram_id, role FROM admins ORDER BY "
                                 "CASE role WHEN 'owner' THEN 0 WHEN 'admin' THEN 1 WHEN 'mid' THEN 2 ELSE 3 END, telegram_id").fetchall()
            return [{"telegram_id": r["telegram_id"], "role": r["role"] or "admin"} for r in rows]

    # -----------------------------------------------------------------------
    # پنل مدیریت وب مستقل (کاربران وب، جدا از ادمین‌های تلگرام)
    # -----------------------------------------------------------------------

    def create_web_admin(self, username: str, password_hash: str, role: str = "admin",
                          permissions=None) -> int:
        if role not in ("owner", "admin", "mid", "support"):
            role = "admin"
        if permissions is None:
            perms = ROLE_PERMISSION_PRESETS.get(role, [])
        else:
            perms = [p for p in permissions if p in WEB_ADMIN_PERMISSIONS]
        with self._get_conn() as conn:
            cur = conn.execute(
                "INSERT INTO web_admins (username, password_hash, role, permissions) VALUES (?, ?, ?, ?)",
                (username.strip().lower(), password_hash, role, json.dumps(perms)),
            )
            return cur.lastrowid

    def get_web_admin_by_username(self, username: str):
        with self._get_conn() as conn:
            return conn.execute(
                "SELECT * FROM web_admins WHERE username=?", (username.strip().lower(),)
            ).fetchone()

    def get_web_admin(self, admin_id: int):
        with self._get_conn() as conn:
            return conn.execute("SELECT * FROM web_admins WHERE id=?", (admin_id,)).fetchone()

    def list_web_admins(self):
        with self._get_conn() as conn:
            return conn.execute(
                "SELECT * FROM web_admins ORDER BY "
                "CASE role WHEN 'owner' THEN 0 WHEN 'admin' THEN 1 WHEN 'mid' THEN 2 ELSE 3 END, id"
            ).fetchall()

    def count_web_admins(self) -> int:
        with self._get_conn() as conn:
            return conn.execute("SELECT COUNT(*) c FROM web_admins").fetchone()["c"]

    def set_web_admin_password(self, admin_id: int, password_hash: str):
        with self._get_conn() as conn:
            conn.execute("UPDATE web_admins SET password_hash=? WHERE id=?", (password_hash, admin_id))

    def set_web_admin_role(self, admin_id: int, role: str) -> bool:
        if role not in ("admin", "mid", "support"):
            return False
        with self._get_conn() as conn:
            row = conn.execute("SELECT role FROM web_admins WHERE id=?", (admin_id,)).fetchone()
            if not row or row["role"] == "owner":
                return False
            conn.execute(
                "UPDATE web_admins SET role=?, permissions=? WHERE id=?",
                (role, json.dumps(ROLE_PERMISSION_PRESETS.get(role, [])), admin_id),
            )
            return True

    def set_web_admin_permissions(self, admin_id: int, permissions) -> bool:
        perms = [p for p in permissions if p in WEB_ADMIN_PERMISSIONS]
        with self._get_conn() as conn:
            row = conn.execute("SELECT role FROM web_admins WHERE id=?", (admin_id,)).fetchone()
            if not row or row["role"] == "owner":
                return False
            conn.execute(
                "UPDATE web_admins SET permissions=? WHERE id=?", (json.dumps(perms), admin_id)
            )
            return True

    def get_web_admin_permissions(self, admin_row) -> list:
        if admin_row["role"] == "owner":
            return list(WEB_ADMIN_PERMISSIONS)
        try:
            perms = json.loads(admin_row["permissions"] or "[]")
        except (ValueError, TypeError):
            perms = []
        return [p for p in perms if p in WEB_ADMIN_PERMISSIONS]

    def has_web_admin_permission(self, admin_row, permission: str) -> bool:
        if admin_row["role"] == "owner":
            return True
        return permission in self.get_web_admin_permissions(admin_row)

    def set_web_admin_active(self, admin_id: int, active: bool) -> bool:
        with self._get_conn() as conn:
            row = conn.execute("SELECT role FROM web_admins WHERE id=?", (admin_id,)).fetchone()
            if not row or row["role"] == "owner":
                return False
            conn.execute("UPDATE web_admins SET is_active=? WHERE id=?", (1 if active else 0, admin_id))
            return True

    def delete_web_admin(self, admin_id: int) -> bool:
        with self._get_conn() as conn:
            row = conn.execute("SELECT role FROM web_admins WHERE id=?", (admin_id,)).fetchone()
            if not row or row["role"] == "owner":
                return False
            conn.execute("DELETE FROM web_admins WHERE id=?", (admin_id,))
            return True

    def touch_web_admin_login(self, admin_id: int):
        with self._get_conn() as conn:
            conn.execute(
                "UPDATE web_admins SET last_login=? WHERE id=?", (datetime.utcnow().isoformat(), admin_id)
            )

    def is_full_web_admin(self, role: str) -> bool:
        return role in ("owner", "admin", "mid")

    # ---------------------------------------------------- web push subs --

    def save_push_subscription(self, admin_id: int, endpoint: str, p256dh: str, auth: str, user_agent: str = None):
        """ذخیره یا به‌روزرسانی subscription پوش مرورگر یک ادمین (هر endpoint یکتاست؛
        اگر همان مرورگر قبلاً subscribe کرده بود، رکورد قبلی به‌روز می‌شود)."""
        with self._get_conn() as conn:
            conn.execute(
                "INSERT INTO web_push_subscriptions (admin_id, endpoint, p256dh, auth, user_agent, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(endpoint) DO UPDATE SET "
                "admin_id=excluded.admin_id, p256dh=excluded.p256dh, auth=excluded.auth, user_agent=excluded.user_agent",
                (admin_id, endpoint, p256dh, auth, user_agent, datetime.utcnow().isoformat()),
            )

    def delete_push_subscription_by_endpoint(self, endpoint: str):
        with self._get_conn() as conn:
            conn.execute("DELETE FROM web_push_subscriptions WHERE endpoint=?", (endpoint,))

    def delete_push_subscriptions_by_endpoints(self, endpoints):
        endpoints = list(endpoints or [])
        if not endpoints:
            return
        with self._get_conn() as conn:
            conn.executemany("DELETE FROM web_push_subscriptions WHERE endpoint=?", [(e,) for e in endpoints])

    def list_push_subscriptions_for_admin(self, admin_id: int):
        with self._get_conn() as conn:
            return conn.execute(
                "SELECT * FROM web_push_subscriptions WHERE admin_id=? ORDER BY id DESC", (admin_id,)
            ).fetchall()

    def list_push_subscriptions_for_permission(self, permission: str):
        """همه‌ی subscription های مرورگری ادمین‌های فعالی که مالک هستند یا مجوز
        داده‌شده را دارند؛ برای فرستادن پوش سراسری (سفارش/شارژ/تیکت جدید) استفاده می‌شود."""
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT s.*, a.role AS admin_role, a.permissions AS admin_permissions, a.is_active AS admin_active "
                "FROM web_push_subscriptions s JOIN web_admins a ON a.id = s.admin_id"
            ).fetchall()
        out = []
        for r in rows:
            if not r["admin_active"]:
                continue
            if r["admin_role"] == "owner":
                out.append(r)
                continue
            try:
                perms = json.loads(r["admin_permissions"] or "[]")
            except (ValueError, TypeError):
                perms = []
            if permission in perms:
                out.append(r)
        return out

    def is_senior_web_admin(self, role: str) -> bool:
        return role in ("owner", "admin")

    # -----------------------------------------------------------------------
    # لاگ فعالیت ادمین (audit log)
    # -----------------------------------------------------------------------

    def log_admin_action(self, admin_id: int, action: str, details: str = "",
                          record_type: str = None, record_id=None):
        """ثبت یک رخداد حساس (تغییر موجودی کیف‌پول، ویرایش قیمت و ...) در لاگ فعالیت ادمین.
        record_type/record_id اختیاری‌اند و امکان فیلتر «تاریخچه‌ی یک رکورد خاص» را می‌دهند
        (مثلاً همه‌ی رخدادهای سفارش #۱۲۳ یا کاربر ۱۲۳۴۵۶۷۸۹)."""
        with self._get_conn() as conn:
            conn.execute(
                "INSERT INTO admin_logs (admin_id, action, details, record_type, record_id, created_at) "
                "VALUES (?,?,?,?,?,?)",
                (admin_id, action, details, record_type,
                 str(record_id) if record_id is not None else None, datetime.utcnow().isoformat()),
            )

    def get_admin_logs(self, limit: int = 50, offset: int = 0, admin_id: int = None,
                        action: str = None, record_type: str = None, record_id=None):
        clauses, params = [], []
        if admin_id is not None:
            clauses.append("admin_id = ?")
            params.append(admin_id)
        if action:
            clauses.append("action = ?")
            params.append(action)
        if record_type:
            clauses.append("record_type = ?")
            params.append(record_type)
        if record_id is not None:
            clauses.append("record_id = ?")
            params.append(str(record_id))
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._get_conn() as conn:
            total = conn.execute(f"SELECT COUNT(*) c FROM admin_logs {where}", params).fetchone()["c"]
            rows = conn.execute(
                f"SELECT * FROM admin_logs {where} ORDER BY id DESC LIMIT ? OFFSET ?",
                params + [limit, offset],
            ).fetchall()
            return rows, total

    def list_admin_log_actions(self):
        """لیست یکتای انواع اکشن‌های ثبت‌شده، برای پر کردن فیلتر «نوع اکشن» در پنل."""
        with self._get_conn() as conn:
            rows = conn.execute("SELECT DISTINCT action FROM admin_logs ORDER BY action").fetchall()
            return [r["action"] for r in rows]

    # -----------------------------------------------------------------------
    # دسته‌بندی‌ها
    # -----------------------------------------------------------------------

    def add_category(self, name: str) -> int:
        def op():
            with self._get_conn() as conn:
                cur = conn.execute("INSERT INTO categories (name) VALUES (?)", (name,))
                return cur.lastrowid
        return self._sqlite_retry(op)

    def get_categories(self, active_only=True):
        with self._get_conn() as conn:
            if active_only:
                rows = conn.execute(
                    "SELECT * FROM categories WHERE is_active=1 ORDER BY sort_order, id"
                ).fetchall()
            else:
                rows = conn.execute("SELECT * FROM categories ORDER BY sort_order, id").fetchall()
            return rows

    def get_category(self, cat_id: int):
        with self._get_conn() as conn:
            return conn.execute("SELECT * FROM categories WHERE id=?", (cat_id,)).fetchone()

    def toggle_category(self, cat_id: int):
        def op():
            with self._get_conn() as conn:
                row = conn.execute("SELECT is_active FROM categories WHERE id=?", (cat_id,)).fetchone()
                if row:
                    new_val = 0 if row["is_active"] else 1
                    conn.execute("UPDATE categories SET is_active=? WHERE id=?", (new_val, cat_id))
                    return True
                return False
        return self._sqlite_retry(op)

    def edit_category(self, cat_id: int, name: str):
        with self._get_conn() as conn:
            conn.execute("UPDATE categories SET name=? WHERE id=?", (name, cat_id))

    def delete_category(self, cat_id: int):
        def op():
            with self._get_conn() as conn:
                cur = conn.execute("DELETE FROM categories WHERE id=?", (cat_id,))
                return cur.rowcount > 0
        return self._sqlite_retry(op)

    # -----------------------------------------------------------------------
    # محصولات
    # -----------------------------------------------------------------------

    def add_product(self, category_id: int, name: str, price: int, description: str = "",
                     preview_file_id: str = "") -> int:
        """ثبت الگوی جدید. preview_file_id: file_id عکس پیش‌نمایش الگو برای نمایش در کاتالوگ."""
        with self._get_conn() as conn:
            cur = conn.execute(
                "INSERT INTO products (category_id, name, price, description, preview_file_id) VALUES (?, ?, ?, ?, ?)",
                (category_id, name, price, description, preview_file_id),
            )
            return cur.lastrowid

    def get_products(self, category_id: int, active_only=True):
        with self._get_conn() as conn:
            if active_only:
                rows = conn.execute(
                    "SELECT * FROM products WHERE category_id=? AND is_active=1 ORDER BY id",
                    (category_id,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM products WHERE category_id=? ORDER BY id", (category_id,)
                ).fetchall()
            return rows

    def get_all_products(self):
        with self._get_conn() as conn:
            return conn.execute(
                "SELECT p.*, c.name as category_name FROM products p "
                "JOIN categories c ON p.category_id=c.id ORDER BY c.sort_order, p.id"
            ).fetchall()

    def get_product(self, product_id: int):
        with self._get_conn() as conn:
            return conn.execute("SELECT * FROM products WHERE id=?", (product_id,)).fetchone()

    def toggle_product(self, product_id: int):
        with self._get_conn() as conn:
            row = conn.execute("SELECT is_active FROM products WHERE id=?", (product_id,)).fetchone()
            if row:
                new_val = 0 if row["is_active"] else 1
                conn.execute("UPDATE products SET is_active=? WHERE id=?", (new_val, product_id))

    def edit_product(self, product_id: int, name: str = None, price: int = None,
                      description: str = None, preview_file_id: str = None):
        fields, values = [], []
        if name is not None:
            fields.append("name=?"); values.append(name)
        if price is not None:
            fields.append("price=?"); values.append(price)
        if description is not None:
            fields.append("description=?"); values.append(description)
        if preview_file_id is not None:
            fields.append("preview_file_id=?"); values.append(preview_file_id)
        if not fields:
            return
        values.append(product_id)
        with self._get_conn() as conn:
            conn.execute(f"UPDATE products SET {', '.join(fields)} WHERE id=?", values)

    def delete_product(self, product_id: int):
        with self._get_conn() as conn:
            conn.execute("DELETE FROM products WHERE id=?", (product_id,))

    # -----------------------------------------------------------------------
    # بانک فایل‌های الگو (file_id های تلگرام برای PDF هر محصول)
    # -----------------------------------------------------------------------

    def add_product_files(self, product_id: int, file_ids: list) -> tuple:
        """افزودن فایل‌های الگو (file_id های تلگرام) به بانک فایل‌های یک محصول، با حذف تکراری‌ها.

        تکراری بودن بر اساس (product_id, file_id) بررسی می‌شود - هم نسبت به
        رکوردهای موجود و هم نسبت به فایل‌های تکراری داخل همان لیست.
        خروجی: (added, duplicates).
        """
        added = 0
        duplicates = 0
        with self._get_conn() as conn:
            existing = {
                (row["file_id"] or "").strip()
                for row in conn.execute(
                    "SELECT file_id FROM product_files WHERE product_id=?", (product_id,)
                )
                if (row["file_id"] or "").strip()
            }
            seen = set()
            for raw in file_ids:
                file_id = (raw or "").strip()
                if not file_id:
                    continue
                if file_id in existing or file_id in seen:
                    duplicates += 1
                    continue
                conn.execute(
                    "INSERT INTO product_files (product_id, file_id) VALUES (?, ?)",
                    (product_id, file_id),
                )
                seen.add(file_id)
                existing.add(file_id)
                added += 1
        return added, duplicates

    def get_product_files(self, product_id: int) -> list:
        """لیست فایل‌های الگوی یک محصول (id, file_id, created_at) به ترتیب id."""
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT id, file_id, created_at FROM product_files WHERE product_id=? ORDER BY id",
                (product_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    def count_product_files(self, product_id: int) -> int:
        with self._get_conn() as conn:
            return conn.execute(
                "SELECT COUNT(*) c FROM product_files WHERE product_id=?", (product_id,)
            ).fetchone()["c"]

    def has_product_files(self, product_id: int) -> bool:
        """آیا برای این محصول حداقل یک فایل الگو ثبت شده است؟ (فروش نامحدود است؛
        وجود فقط یک فایل برای تحویل بی‌نهایت خرید کافی است.)"""
        return self.count_product_files(product_id) > 0

    def delete_product_file(self, file_id: str) -> bool:
        """حذف یک فایل الگو از بانک، بر اساس file_id تلگرام. True یعنی رکوردی حذف شد."""
        with self._get_conn() as conn:
            cur = conn.execute("DELETE FROM product_files WHERE file_id=?", (file_id,))
            return cur.rowcount > 0

    # -----------------------------------------------------------------------
    # الگوهای نمونه رایگان (مخزن جدا)
    # -----------------------------------------------------------------------

    def add_sample_files(self, file_ids: list) -> tuple:
        """افزودن الگوهای نمونه رایگان (file_id تلگرام) با حذف تکراری‌ها.
        خروجی: (added, duplicates)."""
        added = 0
        duplicates = 0
        with self._get_conn() as conn:
            existing = {
                (row["file_id"] or "").strip()
                for row in conn.execute("SELECT file_id FROM sample_files")
                if (row["file_id"] or "").strip()
            }
            seen = set()
            for raw in file_ids:
                file_id = (raw or "").strip()
                if not file_id:
                    continue
                if file_id in existing or file_id in seen:
                    duplicates += 1
                    continue
                conn.execute("INSERT INTO sample_files (file_id) VALUES (?)", (file_id,))
                seen.add(file_id)
                existing.add(file_id)
                added += 1
        return added, duplicates

    def get_sample_files(self) -> list:
        """لیست همه‌ی الگوهای نمونه (id, file_id, created_at) به ترتیب id."""
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT id, file_id, created_at FROM sample_files ORDER BY id"
            ).fetchall()
            return [dict(r) for r in rows]

    def count_sample_files(self) -> int:
        with self._get_conn() as conn:
            return conn.execute("SELECT COUNT(*) c FROM sample_files").fetchone()["c"]

    def delete_sample_file(self, file_id: str) -> bool:
        """حذف یک الگوی نمونه از مخزن، بر اساس file_id تلگرام. True یعنی رکوردی حذف شد."""
        with self._get_conn() as conn:
            cur = conn.execute("DELETE FROM sample_files WHERE file_id=?", (file_id,))
            return cur.rowcount > 0

    def take_unused_sample_file(self):
        """یک فایل نمونه برمی‌گرداند (id, file_id, created_at) یا None.
        الگوی نمونه مصرف نمی‌شود (فروش/ارسال نامحدود)؛ همین رکورد دفعه‌ی بعد هم برگردانده می‌شود."""
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT id, file_id, created_at FROM sample_files ORDER BY id LIMIT 1"
            ).fetchone()
            return dict(row) if row else None

    # -----------------------------------------------------------------------
    # سفارش‌ها
    # -----------------------------------------------------------------------

    def create_order(
        self,
        user_tg_id: int,
        product_id: int,
        base_price: int,
        wallet_used: int = 0,
        discount_code_id: int = None,
        discount_amount: int = 0,
        quantity: int = 1,
    ) -> int:
        final_price = max(base_price - wallet_used - discount_amount, 0)
        with self._get_conn() as conn:
            cur = conn.execute(
                "INSERT INTO orders (user_id, product_id, status, base_price, wallet_used, "
                "discount_code_id, discount_amount, final_price, quantity) VALUES (?, ?, 'pending', ?, ?, ?, ?, ?, ?)",
                (user_tg_id, product_id, base_price, wallet_used, discount_code_id, discount_amount, final_price, quantity),
            )
            return cur.lastrowid

    def set_order_receipt(self, order_id: int, file_id: str, receipt_type: str = "photo"):
        with self._get_conn() as conn:
            conn.execute(
                "UPDATE orders SET receipt_file_id=?, receipt_type=? WHERE id=?",
                (file_id, receipt_type, order_id),
            )

    def set_order_admin_message(self, order_id: int, admin_chat_id: int, admin_message_id: int):
        with self._get_conn() as conn:
            conn.execute(
                "UPDATE orders SET admin_chat_id=?, admin_message_id=? WHERE id=?",
                (admin_chat_id, admin_message_id, order_id),
            )

    def get_order(self, order_id: int):
        with self._get_conn() as conn:
            return conn.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()

    def approve_order(self, order_id: int, file_ids: list,
                      payment_status: str = "paid",
                      physical_fulfillment_status: str = "processing") -> bool:
        """تایید سفارش: status='approved' و ذخیره‌ی شناسه‌ی فایل‌های الگوی تحویلی
        (id رکوردهای product_files) به‌صورت CSV در ستون file_ids سفارش.
        تحویل واقعی فایل‌ها با خواندن file_id از product_files انجام می‌شود.

        ضدِrace/P1-2: انتقال فقط از status='pending' انجام می‌شود؛ اگر سفارش قبلاً
        بررسی شده باشد (approved/rejected) False برمی‌گرداند و هیچ اثری ندارد
        (در حالی که نسخه‌ی قبلی بدون شرط، رکورد را دوباره overwrite می‌کرد و
        مسیر دو ساختِ هم‌زمان approve+reject را باز می‌گذاشت)."""
        if not isinstance(file_ids, (list, tuple)):
            file_ids = [file_ids]
        now_iso = datetime.utcnow().isoformat()
        csv_ids = ",".join(str(i) for i in file_ids)
        with self._get_conn() as conn:
            cur = conn.execute(
                "UPDATE orders SET status='approved', file_ids=?, updated_at=?, "
                "payment_status=?, physical_fulfillment_status=? "
                "WHERE id=? AND status='pending'",
                (csv_ids, now_iso, payment_status, physical_fulfillment_status, order_id),
            )
            return cur.rowcount > 0

    def reject_order(self, order_id: int) -> bool:
        """رد سفارش: بازگشت کیف پول و کاهش مصرف کد تخفیف، همه در «یک» تراکنش.

        ضدِrace/P1-2: انتقال فقط از status='pending' انجام می‌شود (شرط rowcount).
        اگر دو فراخوانِ هم‌زمان (بات + پنل وب) هر دو reject بزنند، فقط یکی
        rowcount>0 می‌گیرد و بازگشت کیف پول دقیقاً یک‌بار اتفاق می‌افتد.
        بازگشت False یعنی سفارش قبلاً بررسی شده بود."""
        now_iso = datetime.utcnow().isoformat()
        with self._get_conn() as conn:
            cur = conn.execute(
                "UPDATE orders SET status='rejected', updated_at=?, payment_status='refunded' "
                "WHERE id=? AND status='pending'",
                (now_iso, order_id),
            )
            if cur.rowcount == 0:
                return False
            order = conn.execute(
                "SELECT user_id, wallet_used, discount_code_id, shipping_cost, order_type "
                "FROM orders WHERE id=?",
                (order_id,),
            ).fetchone()
            if order and order["wallet_used"]:
                conn.execute(
                    "UPDATE users SET referral_credit = MAX(referral_credit + ?, 0) WHERE telegram_id=?",
                    (order["wallet_used"], order["user_id"]),
                )
            if order and order["discount_code_id"]:
                conn.execute(
                    "UPDATE discount_codes SET used_count = MAX(used_count - 1, 0) WHERE id=?",
                    (order["discount_code_id"],),
                )
            # آزادسازی رزروِ اقلام فیزیکیِ سفارش ردشده (همان رفتاری که
            # cancel_physical_fulfillment دارد؛ رد سفارش = رزرو دیگر به‌جاست)
            if order and order["order_type"] != "digital":
                items = conn.execute(
                    "SELECT variant_id, quantity FROM order_items "
                    "WHERE order_id=? AND variant_id IS NOT NULL", (order_id,)
                ).fetchall()
                for it in items:
                    conn.execute(
                        "UPDATE inventory SET reserved = MAX(reserved - ?, 0) WHERE variant_id=?",
                        (it["quantity"], it["variant_id"]),
                    )
                    conn.execute(
                        "INSERT INTO inventory_transactions "
                        "(variant_id, product_id, delta, on_hand_after, reason, order_id, actor) "
                        "SELECT inv.variant_id, v.product_id, 0, inv.on_hand, 'reject', ?, 'system' "
                        "FROM inventory inv JOIN product_variants v ON v.id = inv.variant_id "
                        "WHERE inv.variant_id=?",
                        (order_id, it["variant_id"]),
                    )
            return True

    def get_orders_by_status(self, status: str, limit: int = 200):
        with self._get_conn() as conn:
            return conn.execute(
                "SELECT * FROM orders WHERE status=? ORDER BY id DESC LIMIT ?", (status, limit)
            ).fetchall()

    def list_physical_orders(self, limit: int = 200):
        """سفارش‌های دارای کالای فیزیکی (برای مدیریت ارسال/وضعیت فیزیکی)."""
        with self._get_conn() as conn:
            return conn.execute(
                "SELECT o.*, p.name AS product_name FROM orders o "
                "LEFT JOIN products p ON o.product_id = p.id "
                "WHERE o.order_type IS NOT NULL AND o.order_type != 'digital' "
                "ORDER BY o.id DESC LIMIT ?", (limit,)
            ).fetchall()

    def get_physical_order_items(self, order_id: int):
        with self._get_conn() as conn:
            return conn.execute(
                "SELECT oi.*, v.label AS variant_label, p.name AS product_name "
                "FROM order_items oi "
                "LEFT JOIN product_variants v ON v.id = oi.variant_id "
                "LEFT JOIN products p ON p.id = oi.product_id "
                "WHERE oi.order_id=? AND oi.product_type='physical'", (order_id,)
            ).fetchall()

    def get_pending_orders(self):
        """سفارش‌های نیازمند بررسی دستی (رسید ثبت‌شده یا در انتظار رسید)."""
        with self._get_conn() as conn:
            return conn.execute(
                "SELECT * FROM orders WHERE status='pending' ORDER BY id"
            ).fetchall()

    def get_latest_pending_order_awaiting_receipt(self, user_tg_id: int):
        """آخرین سفارش این کاربر که هنوز pending است و رسیدی برایش ثبت نشده -
        برای fallback بازیابی رسیدهایی که به‌خاطر گم‌شدن FSM state
        (مثلاً ری‌استارت بات) به هندلر state-دار اصلی نرسیده‌اند."""
        with self._get_conn() as conn:
            return conn.execute(
                "SELECT * FROM orders WHERE user_id=? AND status='pending' "
                "AND receipt_file_id IS NULL "
                "ORDER BY id DESC LIMIT 1",
                (user_tg_id,),
            ).fetchone()

    def get_user_orders(self, user_tg_id: int):
        """سفارش‌های «سفارش‌های من» کاربر (بدون سفارش‌های حذف‌شده توسط خودش)،
        همراه با نام محصول برای نمایش."""
        with self._get_conn() as conn:
            return conn.execute(
                "SELECT o.*, p.name AS product_name FROM orders o "
                "LEFT JOIN products p ON o.product_id = p.id "
                "WHERE o.user_id=? AND (o.user_deleted IS NULL OR o.user_deleted=0) "
                "ORDER BY o.id DESC",
                (user_tg_id,),
            ).fetchall()

    def delete_owned_order(self, order_id: int, user_tg_id: int) -> bool:
        """مخفی‌کردن یک سفارش از لیست «سفارش‌های من» توسط خود کاربر. اگر سفارش
        متعلق به این کاربر نباشد False برمی‌گرداند و کاری انجام نمی‌شود. رکورد سفارش
        برای گزارش‌های ادمین دست‌نخورده می‌ماند (فقط user_deleted=1 می‌شود)."""
        with self._get_conn() as conn:
            cur = conn.execute(
                "UPDATE orders SET user_deleted=1 WHERE id=? AND user_id=?",
                (order_id, user_tg_id),
            )
            return cur.rowcount > 0

    # -----------------------------------------------------------------------
    # آمار
    # -----------------------------------------------------------------------

    def get_stats(self):
        with self._get_conn() as conn:
            users_c = conn.execute("SELECT COUNT(*) c FROM users").fetchone()["c"]
            pending_c = conn.execute("SELECT COUNT(*) c FROM orders WHERE status='pending'").fetchone()["c"]
            approved_c = conn.execute("SELECT COUNT(*) c FROM orders WHERE status='approved'").fetchone()["c"]
            rejected_c = conn.execute("SELECT COUNT(*) c FROM orders WHERE status='rejected'").fetchone()["c"]
            revenue = conn.execute(
                "SELECT COALESCE(SUM(COALESCE(o.final_price, p.price)),0) s FROM orders o "
                "JOIN products p ON o.product_id=p.id WHERE o.status='approved'"
            ).fetchone()["s"]
            return {
                "users": users_c,
                "pending": pending_c,
                "approved": approved_c,
                "rejected": rejected_c,
                "revenue": revenue,
            }

    def get_sales_stats(self, start_date: str = None, end_date: str = None):
        """آمار فروش کامل برای یک بازه‌ی زمانی دلخواه.
        start_date/end_date به فرمت 'YYYY-MM-DD' (شامل خود آن روزها).
        اگر داده نشوند، پیش‌فرض ۱۴ روز اخیر است.
        شامل: کارت‌های خلاصه، مقایسه با بازه‌ی هم‌طول قبلی، نرخ تبدیل، میانگین سبد خرید،
        روند روزانه، تفکیک درآمد بر اساس دسته‌بندی، سهم رفرال در مقابل خرید مستقیم،
        و پرفروش‌ترین محصولات (همه محدود به همان بازه)."""
        with self._get_conn() as conn:
            if not end_date:
                end_date = conn.execute("SELECT date('now') d").fetchone()["d"]
            if not start_date:
                start_date = conn.execute("SELECT date(?, '-13 days') d", (end_date,)).fetchone()["d"]

            length_days = conn.execute(
                "SELECT CAST(julianday(?) - julianday(?) AS INTEGER) + 1 d", (end_date, start_date)
            ).fetchone()["d"]
            if length_days < 1:
                length_days = 1

            prev_end = conn.execute("SELECT date(?, '-1 day') d", (start_date,)).fetchone()["d"]
            prev_start = conn.execute(
                "SELECT date(?, ?) d", (prev_end, f"-{length_days - 1} days")
            ).fetchone()["d"]

            def _period_totals(s, e):
                row = conn.execute(
                    "SELECT "
                    "SUM(CASE WHEN o.status='approved' THEN 1 ELSE 0 END) approved_c, "
                    "SUM(CASE WHEN o.status='pending' THEN 1 ELSE 0 END) pending_c, "
                    "SUM(CASE WHEN o.status='rejected' THEN 1 ELSE 0 END) rejected_c, "
                    "COALESCE(SUM(CASE WHEN o.status='approved' THEN COALESCE(o.final_price, p.price) ELSE 0 END),0) revenue "
                    "FROM orders o JOIN products p ON o.product_id=p.id "
                    "WHERE date(o.created_at) BETWEEN ? AND ?",
                    (s, e),
                ).fetchone()
                approved = row["approved_c"] or 0
                pending = row["pending_c"] or 0
                rejected = row["rejected_c"] or 0
                revenue = row["revenue"] or 0
                decided = approved + rejected
                conversion = round(approved / decided * 100, 1) if decided else 0.0
                aov = round(revenue / approved) if approved else 0
                return {
                    "approved": approved, "pending": pending, "rejected": rejected,
                    "revenue": revenue, "conversion_rate": conversion, "aov": aov,
                }

            current = _period_totals(start_date, end_date)
            previous = _period_totals(prev_start, prev_end)

            def _pct_change(cur, prev):
                if prev == 0:
                    return None if cur == 0 else 100.0
                return round((cur - prev) / prev * 100, 1)

            current["revenue_change_pct"] = _pct_change(current["revenue"], previous["revenue"])
            current["orders_change_pct"] = _pct_change(current["approved"], previous["approved"])
            current["prev_revenue"] = previous["revenue"]
            current["prev_approved"] = previous["approved"]

            new_users = conn.execute(
                "SELECT COUNT(*) c FROM users WHERE date(joined_at) BETWEEN ? AND ?", (start_date, end_date)
            ).fetchone()["c"]
            current["new_users"] = new_users

            daily_rows = conn.execute(
                "SELECT date(o.created_at) d, "
                "COALESCE(SUM(CASE WHEN o.status='approved' THEN COALESCE(o.final_price, p.price) ELSE 0 END),0) revenue, "
                "SUM(CASE WHEN o.status='approved' THEN 1 ELSE 0 END) orders "
                "FROM orders o JOIN products p ON o.product_id=p.id "
                "WHERE date(o.created_at) BETWEEN ? AND ? "
                "GROUP BY date(o.created_at)",
                (start_date, end_date),
            ).fetchall()
            daily_map = {r["d"]: {"revenue": r["revenue"], "orders": r["orders"]} for r in daily_rows}
            daily_series = []
            for i in range(length_days):
                d = conn.execute("SELECT date(?, ?) d", (start_date, f"+{i} days")).fetchone()["d"]
                entry = daily_map.get(d, {"revenue": 0, "orders": 0})
                daily_series.append({"date": d, "revenue": entry["revenue"], "orders": entry["orders"]})

            category_rows = conn.execute(
                "SELECT c.name name, COUNT(*) orders, COALESCE(SUM(COALESCE(o.final_price, p.price)),0) revenue "
                "FROM orders o JOIN products p ON o.product_id=p.id JOIN categories c ON p.category_id=c.id "
                "WHERE o.status='approved' AND date(o.created_at) BETWEEN ? AND ? "
                "GROUP BY c.id ORDER BY revenue DESC",
                (start_date, end_date),
            ).fetchall()
            category_breakdown = [
                {"name": r["name"], "orders": r["orders"], "revenue": r["revenue"]} for r in category_rows
            ]

            referral_row = conn.execute(
                "SELECT "
                "COALESCE(SUM(CASE WHEN u.referred_by IS NOT NULL THEN COALESCE(o.final_price, p.price) ELSE 0 END),0) referral_revenue, "
                "COALESCE(SUM(CASE WHEN u.referred_by IS NULL THEN COALESCE(o.final_price, p.price) ELSE 0 END),0) direct_revenue "
                "FROM orders o JOIN products p ON o.product_id=p.id JOIN users u ON o.user_id=u.telegram_id "
                "WHERE o.status='approved' AND date(o.created_at) BETWEEN ? AND ?",
                (start_date, end_date),
            ).fetchone()
            current["referral_revenue"] = referral_row["referral_revenue"] or 0
            current["direct_revenue"] = referral_row["direct_revenue"] or 0

            top_products = conn.execute(
                "SELECT p.name name, COUNT(*) c, COALESCE(SUM(COALESCE(o.final_price, p.price)),0) s "
                "FROM orders o JOIN products p ON o.product_id=p.id "
                "WHERE o.status='approved' AND date(o.created_at) BETWEEN ? AND ? "
                "GROUP BY p.id ORDER BY c DESC LIMIT 5",
                (start_date, end_date),
            ).fetchall()

            total_users = conn.execute("SELECT COUNT(*) c FROM users").fetchone()["c"]
            open_tickets_c = conn.execute(
                "SELECT COUNT(*) c FROM tickets WHERE status IN ('open','answered')"
            ).fetchone()["c"]
            wallet_total = conn.execute("SELECT COALESCE(SUM(referral_credit),0) s FROM users").fetchone()["s"]

            current.update({
                "start_date": start_date,
                "end_date": end_date,
                "total_users": total_users,
                "open_tickets": open_tickets_c,
                "wallet_total": wallet_total,
                "daily_series": daily_series,
                "category_breakdown": category_breakdown,
                "top_products": [{"name": r["name"], "orders": r["c"], "revenue": r["s"]} for r in top_products],
            })
            return current

    def get_full_stats(self, start_date: str = None, end_date: str = None) -> dict:
        """آمار کامل: get_sales_stats به‌علاوه‌ی تیکت‌ها و مشتریان تکراری.
        منبع واحد برای آمار بات تا همه‌جا دقیقاً یک عدد نشان دهد."""
        stats = self.get_sales_stats(start_date, end_date)
        s, e = stats["start_date"], stats["end_date"]
        with self._get_conn() as conn:
            ticket_row = conn.execute(
                "SELECT COUNT(*) c, SUM(CASE WHEN status='open' THEN 1 ELSE 0 END) open_c, "
                "SUM(CASE WHEN status='closed' THEN 1 ELSE 0 END) closed_c "
                "FROM tickets WHERE date(created_at) BETWEEN ? AND ?", (s, e),
            ).fetchone()
            first_response_rows = conn.execute(
                "SELECT t.created_at t_created, MIN(m.created_at) first_admin_reply "
                "FROM tickets t JOIN ticket_messages m ON m.ticket_id=t.id AND m.sender='admin' "
                "WHERE date(t.created_at) BETWEEN ? AND ? GROUP BY t.id", (s, e),
            ).fetchall()
            response_minutes = [
                (conn.execute("SELECT (julianday(?) - julianday(?)) * 1440 d",
                               (r["first_admin_reply"], r["t_created"])).fetchone()["d"])
                for r in first_response_rows
            ]
            avg_response_minutes = round(sum(response_minutes) / len(response_minutes), 1) if response_minutes else None

            repeat_customers = conn.execute(
                "SELECT COUNT(*) c FROM (SELECT user_id FROM orders WHERE status='approved' "
                "GROUP BY user_id HAVING COUNT(*) > 1)"
            ).fetchone()["c"]
            total_customers = conn.execute(
                "SELECT COUNT(DISTINCT user_id) c FROM orders WHERE status='approved'"
            ).fetchone()["c"]
            repeat_rate = round(repeat_customers / total_customers * 100, 1) if total_customers else 0.0

        stats.update({
            "tickets_created": ticket_row["c"] or 0,
            "tickets_open": ticket_row["open_c"] or 0,
            "tickets_closed": ticket_row["closed_c"] or 0,
            "avg_ticket_response_minutes": avg_response_minutes,
            "repeat_customers": repeat_customers,
            "total_customers": total_customers,
            "repeat_customer_rate": repeat_rate,
        })
        return stats

    def get_orders_for_export(self, start_date: str = None, end_date: str = None):
        """لیست خام سفارش‌ها برای خروجی CSV، در بازه‌ی زمانی داده‌شده."""
        with self._get_conn() as conn:
            if not end_date:
                end_date = conn.execute("SELECT date('now') d").fetchone()["d"]
            if not start_date:
                start_date = conn.execute("SELECT date(?, '-13 days') d", (end_date,)).fetchone()["d"]
            rows = conn.execute(
                "SELECT o.id, o.created_at, o.status, o.user_id, u.username, u.first_name, "
                "p.name as product_name, COALESCE(o.final_price, p.price) as amount, "
                "o.wallet_used, o.discount_amount, COALESCE(o.quantity, 1) as quantity "
                "FROM orders o "
                "JOIN products p ON o.product_id=p.id "
                "LEFT JOIN users u ON o.user_id=u.telegram_id "
                "WHERE date(o.created_at) BETWEEN ? AND ? "
                "ORDER BY o.id DESC",
                (start_date, end_date),
            ).fetchall()
            return rows

    # -----------------------------------------------------------------------
    # زیرمجموعه‌گیری (رفرال) و کیف پول اعتباری
    # -----------------------------------------------------------------------

    def set_referred_by(self, user_tg_id: int, referrer_tg_id: int):
        if user_tg_id == referrer_tg_id:
            return
        with self._get_conn() as conn:
            row = conn.execute("SELECT referred_by FROM users WHERE telegram_id=?", (user_tg_id,)).fetchone()
            if row and row["referred_by"] is None:
                referrer_exists = conn.execute(
                    "SELECT 1 FROM users WHERE telegram_id=?", (referrer_tg_id,)
                ).fetchone()
                if referrer_exists:
                    conn.execute(
                        "UPDATE users SET referred_by=? WHERE telegram_id=?", (referrer_tg_id, user_tg_id)
                    )

    def get_referral_stats(self, user_tg_id: int) -> dict:
        with self._get_conn() as conn:
            count = conn.execute(
                "SELECT COUNT(*) c FROM users WHERE referred_by=?", (user_tg_id,)
            ).fetchone()["c"]
            row = conn.execute(
                "SELECT referral_credit FROM users WHERE telegram_id=?", (user_tg_id,)
            ).fetchone()
            credit = row["referral_credit"] if row else 0
            return {"count": count, "credit": credit}

    def get_wallet_credit(self, user_tg_id: int) -> int:
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT referral_credit FROM users WHERE telegram_id=?", (user_tg_id,)
            ).fetchone()
            return row["referral_credit"] if row else 0

    def add_wallet_credit(self, user_tg_id: int, delta: int):
        with self._get_conn() as conn:
            conn.execute(
                "UPDATE users SET referral_credit = MAX(referral_credit + ?, 0) WHERE telegram_id=?",
                (delta, user_tg_id),
            )

    # ------------------------------------------------------------------
    # باشگاه مشتریان (Loyalty) — لایه‌ی داده؛ منطق قواعد در loyalty.py
    # ------------------------------------------------------------------

    def get_loyalty_state(self, user_tg_id: int):
        with self._get_conn() as conn:
            return conn.execute(
                "SELECT * FROM loyalty_state WHERE user_id=?", (user_tg_id,)
            ).fetchone()

    def ensure_loyalty_state(self, user_tg_id: int):
        """ساخت ردیف state برای کاربر اگر وجود نداشته باشد و برگرداندن آن."""
        with self._get_conn() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO loyalty_state (user_id) VALUES (?)", (user_tg_id,)
            )
            return conn.execute(
                "SELECT * FROM loyalty_state WHERE user_id=?", (user_tg_id,)
            ).fetchone()

    def find_loyalty_tx(self, idem_key: str):
        """جست‌وجوی تراکنش دفتر کل با کلید idempotency (برای جلوگیری از دوباره‌کاری)."""
        if not idem_key:
            return None
        with self._get_conn() as conn:
            return conn.execute(
                "SELECT * FROM loyalty_ledger WHERE idem_key=?", (idem_key,)
            ).fetchone()

    def apply_loyalty_mutation(
        self,
        user_tg_id: int,
        tx_type: str,
        amount: int,
        tier: str = None,
        idem_key: str = None,
        reference_type: str = None,
        reference_id=None,
        description: str = "",
        metadata: str = "",
        expires_at: str = None,
    ):
        """هسته‌ی اتمیک هر تغییر موجودی امتیاز: در «یک» تراکنش، بررسی idempotency،
        بروزرسانی state و درج رکورد غیرقابل‌تغییر در دفتر کل انجام می‌شود.

        - اگر idem_key قبلاً ثبت شده باشد، هیچ کاری نمی‌کند و None برمی‌گرداند
          (ضد اعطای دوباره‌ی امتیاز برای همان رویداد).
        - اگر نتیجه موجودی منفی شود، ValueError پرتاب می‌شود و کل تراکنش
          rollback می‌شود (موجودی منفی غیرممکن است).
        - tier فقط وقتی به‌روز می‌شود که پاس داده شود (سرویس آن را از قواعد
          سطح‌ها محاسبه می‌کند)."""

        with self._get_conn() as conn:
            if idem_key:
                dup = conn.execute(
                    "SELECT 1 FROM loyalty_ledger WHERE idem_key=?", (idem_key,)
                ).fetchone()
                if dup:
                    return None

            conn.execute(
                "INSERT OR IGNORE INTO loyalty_state (user_id) VALUES (?)", (user_tg_id,)
            )
            state = conn.execute(
                "SELECT current_points, lifetime_earned, lifetime_spent FROM loyalty_state WHERE user_id=?",
                (user_tg_id,),
            ).fetchone()
            current = state["current_points"]
            new_balance = current + amount
            if new_balance < 0:
                raise ValueError("insufficient loyalty points")

            new_earned = state["lifetime_earned"] + (amount if amount > 0 else 0)
            # فقط مصرف واقعی امتیاز در lifetime_spent می‌شمارد؛ برگشتِ خرید
            # lifetime_earned را که سابقه‌ی واقعی کسب است کاهش نمی‌دهد.
            spent_delta = -amount if (amount < 0 and tx_type in ("POINTS_REDEEM", "POINTS_EXPIRE")) else 0
            new_spent = state["lifetime_spent"] + spent_delta

            if tier is None:
                conn.execute(
                    "UPDATE loyalty_state SET current_points=?, lifetime_earned=?, "
                    "lifetime_spent=?, last_activity_at=CURRENT_TIMESTAMP WHERE user_id=?",
                    (new_balance, new_earned, new_spent, user_tg_id),
                )
            else:
                conn.execute(
                    "UPDATE loyalty_state SET current_points=?, lifetime_earned=?, "
                    "lifetime_spent=?, tier=?, last_activity_at=CURRENT_TIMESTAMP WHERE user_id=?",
                    (new_balance, new_earned, new_spent, tier, user_tg_id),
                )

            cur = conn.execute(
                "INSERT INTO loyalty_ledger (user_id, tx_type, amount, balance_after, "
                "reference_type, reference_id, idem_key, description, metadata, expires_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    user_tg_id, tx_type, amount, new_balance,
                    reference_type,
                    str(reference_id) if reference_id is not None else None,
                    idem_key, description, metadata, expires_at,
                ),
            )
            ledger_id = cur.lastrowid
            row = conn.execute(
                "SELECT * FROM loyalty_ledger WHERE id=?", (ledger_id,)
            ).fetchone()
            return dict(row)

    def redeem_points_for_wallet(self, user_tg_id: int, points: int, toman_value: int, idem_key: str):
        """تبدیل اتمیک امتیاز به اعتبار کیف پول: کاهش شرطی امتیاز + درج دفتر کل
        + افزایش referral_credit، همه در «یک» تراکنش.

        None = موجودی ناکافی یا رویداد تکراری؛ در این حالت هیچ تغییری رخ نمی‌دهد."""
        with self._get_conn() as conn:
            dup = conn.execute(
                "SELECT 1 FROM loyalty_ledger WHERE idem_key=?", (idem_key,)
            ).fetchone()
            if dup:
                return None

            conn.execute(
                "INSERT OR IGNORE INTO loyalty_state (user_id) VALUES (?)", (user_tg_id,)
            )
            state = conn.execute(
                "SELECT current_points FROM loyalty_state WHERE user_id=?", (user_tg_id,)
            ).fetchone()
            current = state["current_points"]
            if current < points:
                return None

            new_balance = current - points
            conn.execute(
                "UPDATE loyalty_state SET current_points=?, lifetime_spent=lifetime_spent+?, "
                "last_activity_at=CURRENT_TIMESTAMP WHERE user_id=?",
                (new_balance, points, user_tg_id),
            )
            conn.execute(
                "UPDATE users SET referral_credit = referral_credit + ? WHERE telegram_id=?",
                (toman_value, user_tg_id),
            )
            cur = conn.execute(
                "INSERT INTO loyalty_ledger (user_id, tx_type, amount, balance_after, "
                "reference_type, reference_id, idem_key, description) "
                "VALUES (?, 'POINTS_REDEEM', ?, ?, 'wallet', NULL, ?, ?)",
                (user_tg_id, -points, new_balance, idem_key,
                 f"تبدیل {points} امتیاز به {toman_value:,} تومان اعتبار کیف پول"),
            )
            row = conn.execute(
                "SELECT * FROM loyalty_ledger WHERE id=?", (cur.lastrowid,)
            ).fetchone()
            return dict(row)

    def get_loyalty_history(self, user_tg_id: int, limit: int = 5, offset: int = 0):
        """تاریخچه‌ی امتیاز کاربر با صفحه‌بندی؛ خروجی (rows, total) مطابق الگوی
        search_users/get_admin_logs."""
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM loyalty_ledger WHERE user_id=? ORDER BY id DESC LIMIT ? OFFSET ?",
                (user_tg_id, limit, offset),
            ).fetchall()
            total = conn.execute(
                "SELECT COUNT(*) c FROM loyalty_ledger WHERE user_id=?", (user_tg_id,)
            ).fetchone()["c"]
            return rows, total

    def reward_referrer_if_first_purchase(self, referred_user_tg_id: int, paid_amount: int):
        """حالت ۱ از سه مدل زیرمجموعه‌گیری: پورسانت درصدی، فقط برای اولین خرید هر
        زیرمجموعه، و در صورت تنظیم بودن سقف (referral_commission_max_count)، فقط برای
        همان تعداد اول از زیرمجموعه‌هایی که خرید کرده‌اند.

        نکته‌ی اتمیک: علامت reward باید شرطی (rowcount) شود تا دو تأییدِ هم‌زمان
        از یک خریدِ اول (مثلاً پنل وب و بات) هر دو پورسانت ندهند."""
        # خواندن تنظیمات بیرون از بلوکِ دارای اتصال (جلوگیری از ورود مجدد به
        # _get_conn در حین نگه‌داشتن اتصال - که با Lock قبلی می‌توانست deadlock کند).
        if self.get_setting("referral_button_enabled", "1") != "1":
            return None
        if self.get_setting("referral_enabled", "1") != "1":
            return None
        max_count = int(self.get_setting("referral_commission_max_count", "0") or 0)
        percent = int(self.get_setting("referral_percent", "10") or 0)

        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT referred_by, referral_first_purchase_rewarded FROM users WHERE telegram_id=?",
                (referred_user_tg_id,),
            ).fetchone()
            if not row or not row["referred_by"] or row["referral_first_purchase_rewarded"]:
                return None
            referrer_id = row["referred_by"]

            if max_count > 0:
                already = conn.execute(
                    "SELECT COUNT(*) c FROM users WHERE referred_by=? AND referral_first_purchase_rewarded=1",
                    (referrer_id,),
                ).fetchone()["c"]
                if already >= max_count:
                    # سقف پر شده؛ همچنان به‌عنوان «رویدادِ اولین خرید» علامت می‌زنیم تا دوباره بررسی نشود
                    conn.execute(
                        "UPDATE users SET referral_first_purchase_rewarded=1 WHERE telegram_id=?",
                        (referred_user_tg_id,),
                    )
                    return None

            # ادعای اتمیک: فقط یکی از فراخوان‌های هم‌زمان می‌تواند این UPDATE را ببرد.
            cur = conn.execute(
                "UPDATE users SET referral_first_purchase_rewarded=1 "
                "WHERE telegram_id=? AND referral_first_purchase_rewarded=0",
                (referred_user_tg_id,),
            )
            if cur.rowcount == 0:
                return None

        reward = (paid_amount * percent) // 100
        if reward > 0:
            self.add_wallet_credit(referrer_id, reward)
            return reward, referrer_id
        return None

    def apply_referral_invite_rewards(self, referred_user_tg_id: int, referrer_tg_id: int) -> dict:
        """بلافاصله بعد از ثبت یک دعوت جدید (بدون نیاز به خرید) صدا زده می‌شود و
        حالت‌های ۲ و ۳ مدل زیرمجموعه‌گیری را بررسی/اعمال می‌کند:
        - حالت ۳: شارژ ثابت کیف پول به‌ازای هر دعوت، تا سقف مشخص.
        - حالت ۲: دریافت یک محصول مشخص و رایگان با رسیدن تعداد دعوت‌ها به یک آستانه.
        خروجی: {"invite_bonus": مبلغ یا None, "free_config_product_id": آیدی محصول یا None}
        """
        result = {"invite_bonus": None, "free_config_product_id": None}
        if self.get_setting("referral_button_enabled", "1") != "1":
            return result
        # خواندن تمام تنظیمات بیرون از بلوکِ دارای اتصال (جلوگیری از ورود مجدد
        # به _get_conn - anti-deadlock)
        invite_enabled = self.get_setting("referral_invite_bonus_enabled", "0") == "1"
        invite_amount = int(self.get_setting("referral_invite_bonus_amount", "0") or 0)
        invite_max = int(self.get_setting("referral_invite_bonus_max_count", "0") or 0)
        free_enabled = self.get_setting("referral_free_config_enabled", "0") == "1"
        free_threshold = int(self.get_setting("referral_free_config_threshold", "0") or 0)
        free_product_raw = self.get_setting("referral_free_config_product_id", "") or ""
        with self._get_conn() as conn:
            referrer = conn.execute(
                "SELECT referral_free_config_given FROM users WHERE telegram_id=?", (referrer_tg_id,)
            ).fetchone()
            if not referrer:
                return result

            # --- حالت ۳: شارژ ثابت کیف پول برای هر دعوت، تا سقف مشخص ---
            if invite_enabled and invite_amount > 0:
                # ادعای اتمیک: هر نفرِ دعوت‌شده فقط یک‌بار در این حالت شمارش می‌شود
                # (جلوگیری از شارژِ دوباره در برخورد هم‌زمان چند فراخوان).
                cur = conn.execute(
                    "UPDATE users SET referral_invite_bonus_given=1 "
                    "WHERE telegram_id=? AND referral_invite_bonus_given=0",
                    (referred_user_tg_id,),
                )
                if cur.rowcount:
                    already = conn.execute(
                        "SELECT COUNT(*) c FROM users WHERE referred_by=? AND referral_invite_bonus_given=1",
                        (referrer_tg_id,),
                    ).fetchone()["c"]
                    if invite_max == 0 or already <= invite_max:
                        conn.execute(
                            "UPDATE users SET referral_credit = MAX(referral_credit + ?, 0) WHERE telegram_id=?",
                            (invite_amount, referrer_tg_id),
                        )
                        result["invite_bonus"] = invite_amount

            # --- حالت ۲: محصول رایگان با رسیدن تعداد دعوت‌ها به یک آستانه (یک‌بار) ---
            if (
                free_enabled
                and not referrer["referral_free_config_given"]
            ):
                if free_threshold > 0 and free_product_raw.strip().isdigit():
                    invited_count = conn.execute(
                        "SELECT COUNT(*) c FROM users WHERE referred_by=?", (referrer_tg_id,)
                    ).fetchone()["c"]
                    if invited_count >= free_threshold:
                        conn.execute(
                            "UPDATE users SET referral_free_config_given=1 WHERE telegram_id=?",
                            (referrer_tg_id,),
                        )
                        result["free_config_product_id"] = int(free_product_raw)

        return result

    # -----------------------------------------------------------------------
    # کدهای تخفیف
    # -----------------------------------------------------------------------

    def create_discount_code(
        self, code: str, percent: int = None, fixed_amount: int = None, max_uses: int = 0,
        expires_at: str = None, source: str = "admin",
    ) -> int:
        with self._get_conn() as conn:
            cur = conn.execute(
                "INSERT INTO discount_codes (code, percent, fixed_amount, max_uses, expires_at, source) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (code.strip().upper(), percent, fixed_amount, max_uses, expires_at, source),
            )
            return cur.lastrowid

    def get_discount_code(self, code: str):
        with self._get_conn() as conn:
            return conn.execute(
                "SELECT * FROM discount_codes WHERE code=?", (code.strip().upper(),)
            ).fetchone()

    def get_discount_code_by_id(self, code_id: int):
        with self._get_conn() as conn:
            return conn.execute("SELECT * FROM discount_codes WHERE id=?", (code_id,)).fetchone()

    def list_discount_codes(self):
        with self._get_conn() as conn:
            return conn.execute("SELECT * FROM discount_codes ORDER BY id DESC").fetchall()

    def toggle_discount_code(self, code_id: int):
        with self._get_conn() as conn:
            row = conn.execute("SELECT is_active FROM discount_codes WHERE id=?", (code_id,)).fetchone()
            if row:
                conn.execute(
                    "UPDATE discount_codes SET is_active=? WHERE id=?",
                    (0 if row["is_active"] else 1, code_id),
                )

    def delete_discount_code(self, code_id: int):
        with self._get_conn() as conn:
            conn.execute("DELETE FROM discount_codes WHERE id=?", (code_id,))

    def increment_discount_usage(self, code_id: int):
        with self._get_conn() as conn:
            conn.execute("UPDATE discount_codes SET used_count = used_count + 1 WHERE id=?", (code_id,))

    def decrement_discount_usage(self, code_id: int):
        with self._get_conn() as conn:
            conn.execute(
                "UPDATE discount_codes SET used_count = MAX(used_count - 1, 0) WHERE id=?", (code_id,)
            )

    def is_discount_code_valid(self, row) -> bool:
        if not row:
            return False
        if not row["is_active"]:
            return False
        if row["max_uses"] and row["used_count"] >= row["max_uses"]:
            return False
        expires_at = row["expires_at"] if "expires_at" in row.keys() else None
        if expires_at and datetime.utcnow().isoformat() > expires_at:
            return False
        return True

    def compute_discount_amount(self, row, price: int) -> int:
        if row["percent"]:
            return min((price * row["percent"]) // 100, price)
        if row["fixed_amount"]:
            return min(row["fixed_amount"], price)
        return 0

    # -----------------------------------------------------------------------
    # شارژ کیف پول
    # -----------------------------------------------------------------------

    def create_topup(self, user_tg_id: int, amount: int) -> int:
        with self._get_conn() as conn:
            cur = conn.execute(
                "INSERT INTO wallet_topups (user_id, amount, status) VALUES (?, ?, 'pending')",
                (user_tg_id, amount),
            )
            return cur.lastrowid

    def set_topup_receipt(self, topup_id: int, file_id: str, receipt_type: str = "photo"):
        with self._get_conn() as conn:
            conn.execute(
                "UPDATE wallet_topups SET receipt_file_id=?, receipt_type=? WHERE id=?",
                (file_id, receipt_type, topup_id),
            )

    def set_topup_admin_message(self, topup_id: int, admin_chat_id: int, admin_message_id: int):
        with self._get_conn() as conn:
            conn.execute(
                "UPDATE wallet_topups SET admin_chat_id=?, admin_message_id=? WHERE id=?",
                (admin_chat_id, admin_message_id, topup_id),
            )

    def get_topup(self, topup_id: int):
        with self._get_conn() as conn:
            return conn.execute("SELECT * FROM wallet_topups WHERE id=?", (topup_id,)).fetchone()

    def get_latest_pending_topup_awaiting_receipt(self, user_tg_id: int):
        """آخرین درخواست شارژ کیف‌پول این کاربر که هنوز pending است و رسیدی
        برایش ثبت نشده - برای fallback بازیابی رسیدهایی که FSM state‌شان گم شده."""
        with self._get_conn() as conn:
            return conn.execute(
                "SELECT * FROM wallet_topups WHERE user_id=? AND status='pending' "
                "AND receipt_file_id IS NULL "
                "ORDER BY id DESC LIMIT 1",
                (user_tg_id,),
            ).fetchone()

    def approve_topup(self, topup_id: int) -> bool:
        """تایید شارژ کیف پول - ضدِ P0-1.

        نسخه‌ی قبلی: SELECT (pending) → UPDATE بدون شرط status → add_wallet_credit
        در یک بلوک جدا. بین آن سه قدم، دو فراخوانِ هم‌زمان (بات + پنل وب) هر دو
        `pending` را می‌دیدند و هر دو شارژ می‌کردند (credit دوبار). این نسخه همه
        را در یک تراکنش با UPDATE شرطی `status='pending'` انجام می‌دهد:
        فقط برنده (rowcount>0) اعتبار می‌گیرد."""
        now_iso = datetime.utcnow().isoformat()
        with self._get_conn() as conn:
            cur = conn.execute(
                "UPDATE wallet_topups SET status='approved', updated_at=? "
                "WHERE id=? AND status='pending'",
                (now_iso, topup_id),
            )
            if cur.rowcount == 0:
                return False
            row = conn.execute(
                "SELECT user_id, amount FROM wallet_topups WHERE id=?", (topup_id,)
            ).fetchone()
            if not row:
                return False
            conn.execute(
                "UPDATE users SET referral_credit = referral_credit + ? WHERE telegram_id=?",
                (row["amount"], row["user_id"]),
            )
            return True

    def reject_topup(self, topup_id: int) -> bool:
        with self._get_conn() as conn:
            cur = conn.execute(
                "UPDATE wallet_topups SET status='rejected', updated_at=? "
                "WHERE id=? AND status='pending'",
                (datetime.utcnow().isoformat(), topup_id),
            )
            return cur.rowcount > 0

    def get_topups_by_status(self, status: str, limit: int = 200):
        with self._get_conn() as conn:
            return conn.execute(
                "SELECT * FROM wallet_topups WHERE status=? ORDER BY id DESC LIMIT ?", (status, limit)
            ).fetchall()

    def get_pending_topups(self):
        """شارژهای کیف پول نیازمند بررسی دستی."""
        with self._get_conn() as conn:
            return conn.execute(
                "SELECT * FROM wallet_topups WHERE status='pending' ORDER BY id"
            ).fetchall()

    # -----------------------------------------------------------------------
    # گردونه شانس
    # -----------------------------------------------------------------------

    def get_wheel_settings(self) -> dict:
        return {
            "enabled": self.get_setting("wheel_enabled", "1") == "1",
            "win_percent": int(self.get_setting("wheel_win_percent", "10") or 0),
            "prizes": [int(p) for p in self.get_setting("wheel_prizes", "10,20,30,50").split(",") if p.strip().isdigit()],
            "expiry_hours": int(self.get_setting("wheel_code_expiry_hours", "24") or 24),
            "cooldown_hours": int(self.get_setting("wheel_cooldown_hours", "24") or 24),
        }

    def set_wheel_prizes(self, prizes: list):
        self.set_setting("wheel_prizes", ",".join(str(p) for p in prizes))

    def can_spin_wheel(self, user_tg_id: int):
        """برمی‌گرداند (True, None) اگر مجاز به چرخش باشد، وگرنه (False, ساعات باقی‌مانده)."""
        cooldown_hours = int(self.get_setting("wheel_cooldown_hours", "24") or 24)
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT last_wheel_spin_at FROM users WHERE telegram_id=?", (user_tg_id,)
            ).fetchone()
        if not row or not row["last_wheel_spin_at"]:
            return True, None
        last_spin = datetime.fromisoformat(row["last_wheel_spin_at"])
        elapsed = datetime.utcnow() - last_spin
        remaining = cooldown_hours - (elapsed.total_seconds() / 3600)
        if remaining <= 0:
            return True, None
        return False, remaining

    def record_wheel_spin(self, user_tg_id: int):
        with self._get_conn() as conn:
            conn.execute(
                "UPDATE users SET last_wheel_spin_at=? WHERE telegram_id=?",
                (datetime.utcnow().isoformat(), user_tg_id),
            )

    def generate_wheel_prize_code(self, user_tg_id: int, percent: int) -> tuple:
        """یک کد تخفیف یکبارمصرف با تاریخ انقضا برای برنده‌ی گردونه می‌سازد و برمی‌گرداند (code, expires_at)."""
        settings = self.get_wheel_settings()
        expires_at = (datetime.utcnow() + timedelta(hours=settings["expiry_hours"])).isoformat()
        code = f"LUCKY{user_tg_id}{secrets.randbelow(9000) + 1000}"
        self.create_discount_code(
            code, percent=percent, max_uses=1, expires_at=expires_at, source="wheel"
        )
        return code, expires_at

    # -----------------------------------------------------------------------
    # چت پشتیبانی (بات، یکپارچه)
    # -----------------------------------------------------------------------

    def add_support_message(self, user_id: int, sender: str, message: str) -> int:
        """sender باید 'user' یا 'admin' باشد."""
        with self._get_conn() as conn:
            cur = conn.execute(
                "INSERT INTO support_messages (user_id, sender, message, is_read_by_user, is_read_by_admin) "
                "VALUES (?, ?, ?, ?, ?)",
                (user_id, sender, message, 1 if sender == "user" else 0, 1 if sender == "admin" else 0),
            )
            conn.execute(
                "INSERT INTO support_conversations (user_id, updated_at) VALUES (?, CURRENT_TIMESTAMP) "
                "ON CONFLICT(user_id) DO UPDATE SET updated_at=CURRENT_TIMESTAMP",
                (user_id,),
            )
            return cur.lastrowid

    def get_support_messages(self, user_id: int, since_id: int = 0, limit: int = 100):
        with self._get_conn() as conn:
            return conn.execute(
                "SELECT * FROM support_messages WHERE user_id=? AND id>? ORDER BY id LIMIT ?",
                (user_id, since_id, limit),
            ).fetchall()

    def mark_support_read_by_user(self, user_id: int):
        with self._get_conn() as conn:
            conn.execute(
                "UPDATE support_messages SET is_read_by_user=1 WHERE user_id=? AND is_read_by_user=0",
                (user_id,),
            )

    def mark_support_read_by_admin(self, user_id: int):
        with self._get_conn() as conn:
            conn.execute(
                "UPDATE support_messages SET is_read_by_admin=1 WHERE user_id=? AND is_read_by_admin=0",
                (user_id,),
            )

    # -----------------------------------------------------------------------
    # آنلاین‌بودن ادمین‌ها (برای مسیریابی چت زنده به اولین ادمین/مالک آنلاین)
    # -----------------------------------------------------------------------

    PRESENCE_ONLINE_SECONDS = 90

    def touch_admin_presence(self, tg_id: int):
        """باید در هر تعامل ادمین (پیام/کلیک در بات، یا درخواست API مینی‌اپ) صدا زده شود."""
        with self._get_conn() as conn:
            conn.execute(
                "INSERT INTO admin_presence (telegram_id, last_seen) VALUES (?, CURRENT_TIMESTAMP) "
                "ON CONFLICT(telegram_id) DO UPDATE SET last_seen=CURRENT_TIMESTAMP",
                (tg_id,),
            )

    def get_online_admin_ids(self, timeout_seconds: int = None) -> list:
        timeout_seconds = timeout_seconds or self.PRESENCE_ONLINE_SECONDS
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT telegram_id FROM admin_presence WHERE last_seen >= datetime('now', ?)",
                (f"-{timeout_seconds} seconds",),
            ).fetchall()
            return [r["telegram_id"] for r in rows]

    def is_admin_online(self, tg_id: int, timeout_seconds: int = None) -> bool:
        return tg_id in self.get_online_admin_ids(timeout_seconds)

    # -----------------------------------------------------------------------
    # مسیریابی مکالمه‌ی چت زنده (به اولین ادمین/مالک آنلاین)
    # -----------------------------------------------------------------------

    def get_support_conversation(self, user_id: int):
        with self._get_conn() as conn:
            return conn.execute(
                "SELECT * FROM support_conversations WHERE user_id=?", (user_id,)
            ).fetchone()

    def set_support_conversation_admin(self, user_id: int, admin_id):
        with self._get_conn() as conn:
            conn.execute(
                "INSERT INTO support_conversations (user_id, assigned_admin_id, updated_at) "
                "VALUES (?, ?, CURRENT_TIMESTAMP) "
                "ON CONFLICT(user_id) DO UPDATE SET assigned_admin_id=excluded.assigned_admin_id, "
                "updated_at=CURRENT_TIMESTAMP",
                (user_id, admin_id),
            )

    def resolve_support_admin_for_message(self, user_id: int):
        """موقع رسیدن پیام جدید کاربر صدا زده می‌شود. اگر مکالمه قبلاً به ادمینی
        اختصاص یافته و آن ادمین همچنان آنلاین است، همان برگردانده می‌شود (یعنی پیام
        فقط برای همان یک نفر ارسال شود). در غیر این صورت اولین ادمین/مالک آنلاین
        انتخاب و مکالمه به او اختصاص داده می‌شود. اگر هیچ‌کس آنلاین نباشد None
        برمی‌گردد (یعنی طبق روال قدیم به همه‌ی ادمین‌ها اطلاع داده شود)."""
        conv = self.get_support_conversation(user_id)
        online_ids = set(self.get_online_admin_ids())
        current = conv["assigned_admin_id"] if conv else None
        if current and current in online_ids:
            return current
        if not online_ids:
            return None
        role_order = {"owner": 0, "admin": 1, "mid": 2, "support": 3}
        admins = self.list_admins_with_roles()
        candidates = [a for a in admins if a["telegram_id"] in online_ids]
        candidates.sort(key=lambda a: (role_order.get(a["role"], 9), a["telegram_id"]))
        chosen = candidates[0]["telegram_id"] if candidates else None
        if chosen:
            self.set_support_conversation_admin(user_id, chosen)
        return chosen

    def list_support_conversations(self):
        """لیست مکالمات چت زنده برای تب «پشتیبانی زنده» در پنل ادمین، جدیدترین اول."""
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT user_id, MAX(id) AS last_id, MAX(created_at) AS last_at, "
                "SUM(CASE WHEN sender='user' AND is_read_by_admin=0 THEN 1 ELSE 0 END) AS unread "
                "FROM support_messages GROUP BY user_id ORDER BY last_at DESC"
            ).fetchall()
            result = []
            for r in rows:
                last_msg = conn.execute(
                    "SELECT sender, message FROM support_messages WHERE user_id=? ORDER BY id DESC LIMIT 1",
                    (r["user_id"],),
                ).fetchone()
                conv = conn.execute(
                    "SELECT assigned_admin_id FROM support_conversations WHERE user_id=?", (r["user_id"],)
                ).fetchone()
                result.append({
                    "user_id": r["user_id"],
                    "last_at": r["last_at"],
                    "unread": r["unread"] or 0,
                    "last_message": last_msg["message"] if last_msg else "",
                    "last_sender": last_msg["sender"] if last_msg else "",
                    "assigned_admin_id": conv["assigned_admin_id"] if conv else None,
                })
            return result

    def count_unread_support_conversations(self) -> int:
        """تعداد مکالمات چت زنده‌ای که حداقل یک پیام خوانده‌نشده از کاربر دارند
        (برای بج زنده‌ی منو کنار «چت زنده»)."""
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT COUNT(DISTINCT user_id) AS c FROM support_messages "
                "WHERE sender='user' AND is_read_by_admin=0"
            ).fetchone()
            return row["c"] or 0

    def get_latest_user_support_message_id(self) -> int:
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT MAX(id) AS m FROM support_messages WHERE sender='user'"
            ).fetchone()
            return row["m"] or 0

    def get_new_support_messages_since(self, since_id: int):
        """پیام‌های جدید کاربر (نه ادمین) بعد از since_id، برای حلقه‌ی پوش زنده‌ی پنل وب."""
        with self._get_conn() as conn:
            return conn.execute(
                "SELECT * FROM support_messages WHERE sender='user' AND id>? ORDER BY id",
                (since_id,),
            ).fetchall()

    # -----------------------------------------------------------------------
    # سیستم تیکت (مستقل از چت مستقیم بالا - یک راه ارتباطی جداگانه و رسمی‌تر
    # با موضوع مشخص و وضعیت باز/پاسخ‌داده‌شده/بسته)
    # -----------------------------------------------------------------------

    def create_ticket(self, user_id: int, subject: str, first_message: str) -> int:
        with self._get_conn() as conn:
            cur = conn.execute(
                "INSERT INTO tickets (user_id, subject, status) VALUES (?, ?, 'open')",
                (user_id, subject),
            )
            ticket_id = cur.lastrowid
            conn.execute(
                "INSERT INTO ticket_messages (ticket_id, sender, message, is_read_by_user, is_read_by_admin) "
                "VALUES (?, 'user', ?, 1, 0)",
                (ticket_id, first_message),
            )
            return ticket_id

    def get_user_tickets(self, user_id: int):
        with self._get_conn() as conn:
            return conn.execute(
                "SELECT * FROM tickets WHERE user_id=? ORDER BY updated_at DESC", (user_id,)
            ).fetchall()

    def get_all_tickets(self, status: str = None):
        with self._get_conn() as conn:
            if status:
                return conn.execute(
                    "SELECT * FROM tickets WHERE status=? ORDER BY updated_at DESC", (status,)
                ).fetchall()
            return conn.execute("SELECT * FROM tickets ORDER BY updated_at DESC").fetchall()

    def get_ticket(self, ticket_id: int):
        with self._get_conn() as conn:
            return conn.execute("SELECT * FROM tickets WHERE id=?", (ticket_id,)).fetchone()

    def claim_ticket_if_open(self, ticket_id: int, admin_id: int):
        """اولین ادمین یا مالکی که به تیکت پاسخ می‌دهد، مالک آن پاسخ‌گویی می‌شود؛
        تا وقتی claimed_by خالی است این تابع آن را قفل می‌کند و از این پس فقط
        همان ادمین (و همیشه مالک اصلی بات) اجازه‌ی پاسخ‌دادن به این تیکت را دارند."""
        with self._get_conn() as conn:
            conn.execute(
                "UPDATE tickets SET claimed_by=? WHERE id=? AND claimed_by IS NULL",
                (admin_id, ticket_id),
            )

    def add_ticket_message(self, ticket_id: int, sender: str, message: str) -> int:
        """sender باید 'user' یا 'admin' باشد. وضعیت تیکت را هم خودکار به‌روز می‌کند:
        پاسخ ادمین -> answered ، پیام جدید کاربر روی تیکت بسته/پاسخ‌داده‌شده -> open."""
        with self._get_conn() as conn:
            cur = conn.execute(
                "INSERT INTO ticket_messages (ticket_id, sender, message, is_read_by_user, is_read_by_admin) "
                "VALUES (?, ?, ?, ?, ?)",
                (ticket_id, sender, message, 1 if sender == "user" else 0, 1 if sender == "admin" else 0),
            )
            new_status = "answered" if sender == "admin" else "open"
            conn.execute(
                "UPDATE tickets SET status=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (new_status, ticket_id),
            )
            return cur.lastrowid

    def get_ticket_messages(self, ticket_id: int, since_id: int = 0, limit: int = 200):
        with self._get_conn() as conn:
            return conn.execute(
                "SELECT * FROM ticket_messages WHERE ticket_id=? AND id>? ORDER BY id LIMIT ?",
                (ticket_id, since_id, limit),
            ).fetchall()

    def close_ticket(self, ticket_id: int):
        with self._get_conn() as conn:
            conn.execute(
                "UPDATE tickets SET status='closed', updated_at=CURRENT_TIMESTAMP WHERE id=?", (ticket_id,)
            )

    def mark_ticket_read_by_user(self, ticket_id: int):
        with self._get_conn() as conn:
            conn.execute(
                "UPDATE ticket_messages SET is_read_by_user=1 WHERE ticket_id=? AND is_read_by_user=0",
                (ticket_id,),
            )

    def mark_ticket_read_by_admin(self, ticket_id: int):
        with self._get_conn() as conn:
            conn.execute(
                "UPDATE ticket_messages SET is_read_by_admin=1 WHERE ticket_id=? AND is_read_by_admin=0",
                (ticket_id,),
            )

    # -----------------------------------------------------------------------
    # عضویت اجباری در کانال
    # -----------------------------------------------------------------------

    def get_force_join_settings(self) -> dict:
        return {
            "enabled": self.get_setting("force_join_enabled", "0") == "1",
            "channel": self.get_setting("force_join_channel", "").strip(),
        }

    # -----------------------------------------------------------------------
    # تجارت یکپارچه: سبد خرید
    # -----------------------------------------------------------------------

    def set_cart_item(self, user_tg_id: int, product_id: int, variant_id=None, quantity: int = 1):
        """درج/به‌روزرسانی یک قلم سبد (upsert اتمیک بر اساس شاخص یکتای
        (user_id, product_id, COALESCE(variant_id,0))). تعداد را «تنظیم» می‌کند
        نه جمع؛ جمع کردن بر عهده‌ی سرویس است. quantity باید >= 1 باشد."""
        if variant_id is None:
            variant_id = None
        with self._get_conn() as conn:
            conn.execute(
                "INSERT INTO cart_items (user_id, product_id, variant_id, quantity) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(user_id, product_id, COALESCE(variant_id,0)) "
                "DO UPDATE SET quantity=excluded.quantity, updated_at=CURRENT_TIMESTAMP",
                (user_tg_id, product_id, variant_id, max(quantity, 1)),
            )

    def change_cart_quantity(self, user_tg_id: int, item_id: int, quantity: int) -> bool:
        """تغییر تعداد یک قلم سبد (دقیقاً برای همان کاربر - ownership guard)."""
        if quantity < 1:
            return False
        with self._get_conn() as conn:
            cur = conn.execute(
                "UPDATE cart_items SET quantity=?, updated_at=CURRENT_TIMESTAMP "
                "WHERE id=? AND user_id=?",
                (quantity, item_id, user_tg_id),
            )
            return cur.rowcount > 0

    def remove_cart_item(self, user_tg_id: int, item_id: int) -> bool:
        with self._get_conn() as conn:
            cur = conn.execute(
                "DELETE FROM cart_items WHERE id=? AND user_id=?", (item_id, user_tg_id)
            )
            return cur.rowcount > 0

    def clear_cart(self, user_tg_id: int):
        with self._get_conn() as conn:
            conn.execute("DELETE FROM cart_items WHERE user_id=?", (user_tg_id,))

    def count_cart_items(self, user_tg_id: int) -> int:
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT COUNT(*) c FROM cart_items WHERE user_id=?", (user_tg_id,)
            ).fetchone()
            return row["c"] or 0

    def get_cart_items(self, user_tg_id: int):
        """اقلام سبد به‌همراه اطلاعات محصول/واریانت/موجودی برای نمایش و تسویه.
        available برای هر قلم فیزیکی = on_hand - reserved. available_ok می‌گوید
        آیا تعداد درخواستی هنوز تأمین است."""
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT ci.*, "
                "p.name AS product_name, p.price AS product_price, p.type AS product_type, "
                "v.label AS variant_label, v.price AS variant_price, v.is_active AS variant_active, "
                "COALESCE(i.on_hand, 0) AS on_hand, COALESCE(i.reserved, 0) AS reserved, "
                "COALESCE(i.low_stock_threshold, 0) AS low_stock_threshold "
                "FROM cart_items ci "
                "JOIN products p ON p.id = ci.product_id "
                "LEFT JOIN product_variants v ON v.id = ci.variant_id "
                "LEFT JOIN inventory i ON i.variant_id = ci.variant_id "
                "WHERE ci.user_id=? ORDER BY ci.id",
                (user_tg_id,),
            ).fetchall()
            result = []
            for r in rows:
                d = dict(r)
                d["available"] = d["on_hand"] - d["reserved"]
                d["available_ok"] = True if d["product_type"] == "digital" else (d["available"] >= d["quantity"])
                result.append(d)
            return result

    # -----------------------------------------------------------------------
    # تجارت یکپارچه: واریانت محصول
    # -----------------------------------------------------------------------

    def add_variant(self, product_id: int, label: str, price=None, attributes: str = "{}",
                    sort_order: int = 0) -> int:
        with self._get_conn() as conn:
            cur = conn.execute(
                "INSERT INTO product_variants (product_id, label, price, attributes, sort_order) "
                "VALUES (?, ?, ?, ?, ?)",
                (product_id, label, price, attributes, sort_order),
            )
            conn.execute(
                "INSERT OR IGNORE INTO inventory (variant_id) VALUES (?)", (cur.lastrowid,)
            )
            return cur.lastrowid

    def get_variant(self, variant_id: int):
        with self._get_conn() as conn:
            return conn.execute("SELECT * FROM product_variants WHERE id=?", (variant_id,)).fetchone()

    def list_variants(self, product_id: int, active_only=False):
        with self._get_conn() as conn:
            if active_only:
                return conn.execute(
                    "SELECT * FROM product_variants WHERE product_id=? AND is_active=1 ORDER BY sort_order, id",
                    (product_id,),
                ).fetchall()
            return conn.execute(
                "SELECT * FROM product_variants WHERE product_id=? ORDER BY sort_order, id",
                (product_id,),
            ).fetchall()

    def toggle_variant(self, variant_id: int):
        with self._get_conn() as conn:
            row = conn.execute("SELECT is_active FROM product_variants WHERE id=?", (variant_id,)).fetchone()
            if row:
                conn.execute(
                    "UPDATE product_variants SET is_active=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                    (0 if row["is_active"] else 1, variant_id),
                )

    def edit_variant(self, variant_id: int, label=None, price=None, attributes=None, sort_order=None):
        fields, values = [], []
        if label is not None:
            fields.append("label=?"); values.append(label)
        if price is not None:
            fields.append("price=?"); values.append(price)
        if attributes is not None:
            fields.append("attributes=?"); values.append(attributes)
        if sort_order is not None:
            fields.append("sort_order=?"); values.append(sort_order)
        if not fields:
            return
        fields.append("updated_at=CURRENT_TIMESTAMP")
        values.append(variant_id)
        with self._get_conn() as conn:
            conn.execute(f"UPDATE product_variants SET {', '.join(fields)} WHERE id=?", values)

    def delete_variant(self, variant_id: int):
        with self._get_conn() as conn:
            conn.execute("DELETE FROM product_variants WHERE id=?", (variant_id,))

    def set_product_type(self, product_id: int, product_type: str) -> bool:
        if product_type not in ("digital", "physical"):
            return False
        with self._get_conn() as conn:
            cur = conn.execute(
                "UPDATE products SET type=? WHERE id=?", (product_type, product_id)
            )
            return cur.rowcount > 0

    # -----------------------------------------------------------------------
    # تجارت یکپارچه: موجودی
    # -----------------------------------------------------------------------

    def _inv_login(self, conn, variant_id, product_id, delta, on_hand_after, reason, order_id, actor):
        conn.execute(
            "INSERT INTO inventory_transactions "
            "(variant_id, product_id, delta, on_hand_after, reason, order_id, actor) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (variant_id, product_id, delta, on_hand_after, reason, order_id, actor),
        )

    def adjust_inventory(self, variant_id: int, delta: int, reason: str = "manual",
                         actor: str = "", order_id=None) -> bool:
        """افزایش/کاهش مستقیم on_hand با شرطِ روی هم نبودن منفی (rowcount).
        خطا برای موجودی ناکافی False برمی‌گرداند؛ برای واریانت ناموجود هم False."""
        with self._get_conn() as conn:
            conn.execute("INSERT OR IGNORE INTO inventory (variant_id) VALUES (?)", (variant_id,))
            cur = conn.execute(
                "UPDATE inventory SET on_hand = on_hand + ?, reserved = reserved, "
                "updated_at=CURRENT_TIMESTAMP "
                "WHERE variant_id=? AND (on_hand + ?) >= 0",
                (delta, variant_id, delta),
            )
            if cur.rowcount == 0:
                return False
            row = conn.execute(
                "SELECT on_hand, product_id FROM inventory inv "
                "JOIN product_variants v ON v.id = inv.variant_id WHERE inv.variant_id=?",
                (variant_id,),
            ).fetchone()
            self._inv_login(conn, variant_id, row["product_id"], delta, row["on_hand"],
                            reason, order_id, actor)
            return True

    def set_inventory(self, variant_id: int, on_hand: int, low_stock_threshold: int = 0) -> bool:
        """تنظیم مطلق موجودی و آستانه‌ی هشدار (بدون تغییر reserved)."""
        with self._get_conn() as conn:
            conn.execute("INSERT OR IGNORE INTO inventory (variant_id) VALUES (?)", (variant_id,))
            cur = conn.execute(
                "UPDATE inventory SET on_hand=?, low_stock_threshold=?, updated_at=CURRENT_TIMESTAMP "
                "WHERE variant_id=?",
                (on_hand, low_stock_threshold, variant_id),
            )
            return cur.rowcount > 0

    def reserve_inventory(self, variant_id: int, qty: int, reason: str = "sale",
                          actor: str = "", order_id=None) -> bool:
        """رزرو اتمیک: `reserved += qty` فقط اگر available کافی باشد
        (`UPDATE ... WHERE (on_hand - reserved) >= qty` → rowcount)."""
        if qty <= 0:
            return False
        with self._get_conn() as conn:
            conn.execute("INSERT OR IGNORE INTO inventory (variant_id) VALUES (?)", (variant_id,))
            cur = conn.execute(
                "UPDATE inventory SET reserved = reserved + ?, updated_at=CURRENT_TIMESTAMP "
                "WHERE variant_id=? AND (on_hand - reserved) >= ?",
                (qty, variant_id, qty),
            )
            return cur.rowcount > 0

    def release_inventory(self, variant_id: int, qty: int, reason: str = "release",
                          actor: str = "", order_id=None):
        """آزادسازی رزرو (بدون تغییر on_hand)."""
        if qty <= 0:
            return
        with self._get_conn() as conn:
            conn.execute(
                "UPDATE inventory SET reserved = MAX(reserved - ?, 0), updated_at=CURRENT_TIMESTAMP "
                "WHERE variant_id=?",
                (qty, variant_id),
            )

    def commit_inventory(self, variant_id: int, qty: int, reason: str = "shipped",
                         actor: str = "", order_id=None) -> bool:
        """کاهش on_hand و آزادسازی رزرو هنگام ارسال/تحویل فیزیکی."""
        if qty <= 0:
            return False
        with self._get_conn() as conn:
            cur = conn.execute(
                "UPDATE inventory SET on_hand = on_hand - ?, reserved = MAX(reserved - ?, 0), "
                "updated_at=CURRENT_TIMESTAMP WHERE variant_id=? AND on_hand - ? >= 0",
                (qty, qty, variant_id, qty),
            )
            return cur.rowcount > 0

    def get_inventory(self, variant_id: int):
        with self._get_conn() as conn:
            return conn.execute(
                "SELECT inv.*, v.product_id, v.label, COALESCE(v.price, p.price) AS sell_price "
                "FROM inventory inv JOIN product_variants v ON v.id=inv.variant_id "
                "JOIN products p ON p.id=v.product_id WHERE inv.variant_id=?",
                (variant_id,),
            ).fetchone()

    def list_inventory(self, active_only=True):
        """وضعیت موجودی همه‌ی واریانت‌ها، همراه با نام محصول."""
        with self._get_conn() as conn:
            cond = " AND p.is_active=1" if active_only else ""
            return conn.execute(
                "SELECT inv.*, v.product_id, v.label, v.price AS variant_price, "
                "p.name AS product_name, p.price AS product_price, p.type AS product_type "
                "FROM inventory inv JOIN product_variants v ON v.id=inv.variant_id "
                "JOIN products p ON p.id=v.product_id WHERE 1=1" + cond + " ORDER BY v.id"
            ).fetchall()

    def list_low_stock(self):
        """واریانت‌هایی که available به زیر آستانه رسیده (یا آستانه صفر و موجودی صفر)."""
        with self._get_conn() as conn:
            return conn.execute(
                "SELECT inv.*, v.product_id, v.label, p.name AS product_name "
                "FROM inventory inv JOIN product_variants v ON v.id=inv.variant_id "
                "JOIN products p ON p.id=v.product_id "
                "WHERE p.is_active=1 AND (inv.on_hand - inv.reserved) <= inv.low_stock_threshold "
                "AND (inv.low_stock_threshold > 0 OR inv.on_hand = 0) "
                "ORDER BY (inv.on_hand - inv.reserved) ASC"
            ).fetchall()

    def get_inventory_transactions(self, variant_id: int, limit: int = 50):
        with self._get_conn() as conn:
            return conn.execute(
                "SELECT * FROM inventory_transactions WHERE variant_id=? ORDER BY id DESC LIMIT ?",
                (variant_id, limit),
            ).fetchall()

    # -----------------------------------------------------------------------
    # تجارت یکپارچه: روش‌های ارسال
    # -----------------------------------------------------------------------

    def add_shipping_method(self, name: str, cost: int, delivery_note: str = "", position: int = 0) -> int:
        with self._get_conn() as conn:
            cur = conn.execute(
                "INSERT INTO shipping_methods (name, cost, delivery_note, position) VALUES (?, ?, ?, ?)",
                (name, cost, delivery_note, position),
            )
            return cur.lastrowid

    def list_shipping_methods(self, active_only=True):
        with self._get_conn() as conn:
            if active_only:
                return conn.execute(
                    "SELECT * FROM shipping_methods WHERE is_active=1 ORDER BY position, id"
                ).fetchall()
            return conn.execute("SELECT * FROM shipping_methods ORDER BY position, id").fetchall()

    def get_shipping_method(self, method_id: int):
        with self._get_conn() as conn:
            return conn.execute(
                "SELECT * FROM shipping_methods WHERE id=?", (method_id,)
            ).fetchone()

    def toggle_shipping_method(self, method_id: int):
        with self._get_conn() as conn:
            row = conn.execute("SELECT is_active FROM shipping_methods WHERE id=?", (method_id,)).fetchone()
            if row:
                conn.execute(
                    "UPDATE shipping_methods SET is_active=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                    (0 if row["is_active"] else 1, method_id),
                )

    def edit_shipping_method(self, method_id: int, name=None, cost=None, delivery_note=None,
                             position=None):
        fields, values = [], []
        if name is not None:
            fields.append("name=?"); values.append(name)
        if cost is not None:
            fields.append("cost=?"); values.append(cost)
        if delivery_note is not None:
            fields.append("delivery_note=?"); values.append(delivery_note)
        if position is not None:
            fields.append("position=?"); values.append(position)
        if not fields:
            return
        fields.append("updated_at=CURRENT_TIMESTAMP")
        values.append(method_id)
        with self._get_conn() as conn:
            conn.execute(f"UPDATE shipping_methods SET {', '.join(fields)} WHERE id=?", values)

    def delete_shipping_method(self, method_id: int):
        with self._get_conn() as conn:
            conn.execute("DELETE FROM shipping_methods WHERE id=?", (method_id,))

    # -----------------------------------------------------------------------
    # تجارت یکپارچه: آدرس‌های مشتری
    # -----------------------------------------------------------------------

    def add_address(self, user_tg_id: int, recipient_name: str, mobile: str, province: str,
                    city: str, address: str, postal_code: str = "") -> int:
        with self._get_conn() as conn:
            first = conn.execute(
                "SELECT COUNT(*) c FROM customer_addresses WHERE user_id=?", (user_tg_id,)
            ).fetchone()["c"]
            cur = conn.execute(
                "INSERT INTO customer_addresses (user_id, recipient_name, mobile, province, city, address, postal_code, is_default) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (user_tg_id, recipient_name, mobile, province, city, address, postal_code, 1 if first == 0 else 0),
            )
            return cur.lastrowid

    def list_addresses(self, user_tg_id: int):
        with self._get_conn() as conn:
            return conn.execute(
                "SELECT * FROM customer_addresses WHERE user_id=? ORDER BY is_default DESC, id DESC",
                (user_tg_id,),
            ).fetchall()

    def get_address(self, address_id: int):
        with self._get_conn() as conn:
            return conn.execute(
                "SELECT * FROM customer_addresses WHERE id=?", (address_id,)
            ).fetchone()

    def delete_address(self, address_id: int, user_tg_id: int) -> bool:
        with self._get_conn() as conn:
            cur = conn.execute(
                "DELETE FROM customer_addresses WHERE id=? AND user_id=?", (address_id, user_tg_id)
            )
            return cur.rowcount > 0

    def set_default_address(self, address_id: int, user_tg_id: int) -> bool:
        with self._get_conn() as conn:
            owned = conn.execute(
                "SELECT is_default FROM customer_addresses WHERE id=? AND user_id=?",
                (address_id, user_tg_id),
            ).fetchone()
            if not owned:
                return False
            conn.execute("UPDATE customer_addresses SET is_default=0 WHERE user_id=?", (user_tg_id,))
            conn.execute(
                "UPDATE customer_addresses SET is_default=1 WHERE id=? AND user_id=?",
                (address_id, user_tg_id),
            )
            return True

    # -----------------------------------------------------------------------
    # تجارت یکپارچه: اقلام سفارش و idempotency تسویه
    # -----------------------------------------------------------------------

    def insert_order_item(self, conn, order_id: int, product_id: int, product_type: str,
                          product_name: str, quantity: int, unit_price: int, total_price: int,
                          variant_id=None, file_ids: str = ""):
        conn.execute(
            "INSERT INTO order_items (order_id, product_id, variant_id, product_type, product_name, "
            "quantity, unit_price, total_price, file_ids) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (order_id, product_id, variant_id, product_type, product_name, quantity,
             unit_price, total_price, file_ids),
        )

    def get_order_items(self, order_id: int):
        with self._get_conn() as conn:
            return conn.execute(
                "SELECT * FROM order_items WHERE order_id=? ORDER BY id", (order_id,)
            ).fetchall()

    def get_checkout_order_id(self, idem_key: str):
        if not idem_key:
            return None
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT order_id FROM checkout_idem WHERE idem_key=?", (idem_key,)
            ).fetchone()
            return row["order_id"] if row else None

    def add_fulfillment_event(self, order_id: int, from_status: str, to_status: str,
                              actor_type: str = "", actor_id: str = "", note: str = ""):
        with self._get_conn() as conn:
            conn.execute(
                "INSERT INTO fulfillment_events (order_id, from_status, to_status, actor_type, actor_id, note) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (order_id, from_status, to_status, actor_type, actor_id, note),
            )

    def get_fulfillment_events(self, order_id: int):
        with self._get_conn() as conn:
            return conn.execute(
                "SELECT * FROM fulfillment_events WHERE order_id=? ORDER BY id", (order_id,)
            ).fetchall()

    def set_physical_fulfillment_status(self, order_id: int, new_status: str) -> bool:
        """انتقال وضعیت ارسال فیزیکی (processing/packed/shipped/delivered)."""
        with self._get_conn() as conn:
            cur = conn.execute(
                "UPDATE orders SET physical_fulfillment_status=?, updated_at=CURRENT_TIMESTAMP "
                "WHERE id=?",
                (new_status, order_id),
            )
            return cur.rowcount > 0

    def set_order_tracking(self, order_id: int, tracking_number: str) -> bool:
        with self._get_conn() as conn:
            cur = conn.execute(
                "UPDATE orders SET tracking_number=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (tracking_number, order_id),
            )
            return cur.rowcount > 0

    def cancel_physical_fulfillment(self, order_id: int) -> bool:
        """لغو وضعیت فیزیکیِ یک سفارش: رزروِ اقلام فیزیکیِ آن آزاد می‌شود و
        physical_fulfillment_status به cancelled می‌رود. (بازگرداندن پول جداگانه
        توسط مسیرِ ردِ سفارش انجام می‌شود.)"""
        with self._get_conn() as conn:
            cur = conn.execute(
                "UPDATE orders SET physical_fulfillment_status='cancelled', "
                "updated_at=CURRENT_TIMESTAMP WHERE id=? AND order_type != 'digital'",
                (order_id,),
            )
            if cur.rowcount == 0:
                return False
            items = conn.execute(
                "SELECT variant_id, quantity FROM order_items "
                "WHERE order_id=? AND variant_id IS NOT NULL", (order_id,)
            ).fetchall()
            for it in items:
                conn.execute(
                    "UPDATE inventory SET reserved = MAX(reserved - ?, 0) WHERE variant_id=?",
                    (it["quantity"], it["variant_id"]),
                )
                conn.execute(
                    "INSERT INTO inventory_transactions "
                    "(variant_id, product_id, delta, on_hand_after, reason, order_id, actor) "
                    "SELECT inv.variant_id, v.product_id, 0, inv.on_hand, 'cancel', ?, 'system' "
                    "FROM inventory inv JOIN product_variants v ON v.id = inv.variant_id "
                    "WHERE inv.variant_id=?",
                    (order_id, it["variant_id"]),
                )
            return True
