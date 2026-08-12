# -*- coding: utf-8 -*-
"""
لایه دیتابیس - SQLite

این فایل حالا یک کلاس Database است، نه مجموعه‌ای از توابع سطح بالا.
دلیلش معماری چندباتی است: بات اصلی و هر بات نمایندگی، هرکدام یک نمونه‌ی
کاملاً جداگانه از Database (با فایل دیتابیس خودشان) دارند، در نتیجه هرکدام
به‌طور خودکار و مستقل صاحب تمام امکانات هستند (کد تخفیف، زیرمجموعه‌گیری،
کیف پول، کانفیگ تست، ...) بدون این‌که غیرفعال‌کردن یک قابلیت در یک بات
روی بات‌های دیگر اثر بگذارد.
"""

import sqlite3
import secrets
import threading
from datetime import datetime, timedelta
from contextlib import contextmanager


DEFAULT_SETTINGS = {
    "welcome_text": "👋 به فروشگاه کانفیگ V2Ray خوش آمدید!\nاز منوی زیر یکی از گزینه‌ها را انتخاب کنید.",
    "btn_buy": "🛒 خرید کانفیگ",
    "btn_test": "🧪 کانفیگ تست رایگان",
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
    "store_name": "⚡ SHOP VPN",
    "miniapp_banner_text": "اتصال امن و پایدار برقرار است",
    # سیستم زیرمجموعه‌گیری
    "referral_enabled": "1",
    "referral_percent": "10",  # درصدی که به دعوت‌کننده به‌عنوان اعتبار کیف پول تعلق می‌گیرد
    # رنگ دکمه‌های شیشه‌ای داخل پنل مدیریت
    "adm_categories_style": "",
    "adm_products_style": "",
    "adm_add_configs_style": "",
    "adm_test_menu_style": "",
    "adm_pending_orders_style": "primary",
    "adm_pending_topups_style": "primary",
    "adm_discounts_menu_style": "",
    "adm_referral_settings_style": "",
    "adm_resellers_menu_style": "success",
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
    # یادآوری اتمام سرویس + کد تخفیف تشویقی تمدید
    "renewal_reminder_enabled": "1",
    "renewal_reminder_days_before": "5",  # چند روز قبل از اتمام سرویس یادآوری ارسال شود
    "low_stock_threshold": "3",  # وقتی موجودی یک محصول به این عدد یا کمتر برسد، به ادمین‌ها هشدار داده می‌شود
    "renewal_discount_percent": "20",  # درصد تخفیف کد تشویقی تمدید
    "renewal_discount_expiry_hours": "24",  # اعتبار کد تشویقی تمدید (ساعت)
    "adm_renewal_settings_style": "success",
    "adm_stock_alert_settings_style": "",
    # چیدمان دکمه‌های منوی اصلی (ترتیب و نمایش) - آرایه JSON از کلیدها
    "menu_order": '["miniapp","btn_buy","btn_test","btn_my_orders","btn_wallet","btn_referral","btn_wheel","btn_contact","btn_admin_panel"]',
}


# تعریف کامل دکمه‌های قابل‌مدیریت در منوی اصلی: کلید -> متادیتا
# toggle_key: نام تنظیمی که فعال/غیرفعال بودن دکمه را کنترل می‌کند (None یعنی همیشه نمایش داده می‌شود)
# admin_only: اگر True فقط برای ادمین‌ها نمایش داده می‌شود
MENU_BUTTON_META = {
    "miniapp": {"label": "دکمه مینی‌اپ فروشگاه", "toggle_key": None, "admin_only": False, "has_text": False, "has_style": False},
    "btn_buy": {"label": "دکمه خرید کانفیگ", "toggle_key": None, "admin_only": False, "has_text": True, "has_style": True},
    "btn_test": {"label": "دکمه کانفیگ تست", "toggle_key": "test_enabled", "admin_only": False, "has_text": True, "has_style": True},
    "btn_my_orders": {"label": "دکمه سفارش‌های من", "toggle_key": None, "admin_only": False, "has_text": True, "has_style": True},
    "btn_wallet": {"label": "دکمه کیف پول", "toggle_key": None, "admin_only": False, "has_text": True, "has_style": True},
    "btn_referral": {"label": "دکمه زیرمجموعه‌گیری", "toggle_key": "referral_enabled", "admin_only": False, "has_text": True, "has_style": True},
    "btn_wheel": {"label": "دکمه گردونه شانس", "toggle_key": "wheel_enabled", "admin_only": False, "has_text": True, "has_style": True},
    "btn_contact": {"label": "دکمه ارتباط با پشتیبانی", "toggle_key": None, "admin_only": False, "has_text": True, "has_style": True},
    "btn_admin_panel": {"label": "دکمه پنل مدیریت", "toggle_key": None, "admin_only": True, "has_text": True, "has_style": True},
}
DEFAULT_MENU_ORDER = ["miniapp", "btn_buy", "btn_test", "btn_my_orders", "btn_wallet", "btn_referral", "btn_wheel", "btn_contact", "btn_admin_panel"]


class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._conn = None
        self._settings_cache = None
        # مینی‌اپ (FastAPI) توابع sync را در threadpool اجرا می‌کند، یعنی
        # ممکن است چند ریکوئست هم‌زمان از تردهای مختلف به همین یک Database
        # (مثلاً main_db) دسترسی داشته باشند. بات‌های aiogram هم در یک
        # event loop تک‌رشته‌ای هستند، پس این لاک برای آن‌ها overhead
        # واقعی ندارد ولی برای مینی‌اپ لازم است.
        self._lock = threading.Lock()

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
        # با خطای «database is locked» شکست می‌خورد به‌جای اینکه چند میلی‌ثانیه صبر
        # کند. چون خطا داخل هندلر کلیدها/کالبک‌ها catch نمی‌شد، دکمه از دید کاربر
        # بی‌واکنش/فریز به‌نظر می‌رسید. این مقدار به SQLite می‌گوید تا ۵ ثانیه صبر
        # و دوباره تلاش کند قبل از اینکه خطا بدهد.
        conn.execute("PRAGMA busy_timeout = 5000")
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
                    is_active INTEGER DEFAULT 1,
                    FOREIGN KEY(category_id) REFERENCES categories(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS configs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_id INTEGER NOT NULL,
                    link TEXT NOT NULL,
                    is_used INTEGER DEFAULT 0,
                    assigned_user_id INTEGER,
                    assigned_at TEXT,
                    FOREIGN KEY(product_id) REFERENCES products(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS test_configs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    link TEXT NOT NULL,
                    is_used INTEGER DEFAULT 0,
                    assigned_user_id INTEGER,
                    assigned_at TEXT
                );

                CREATE TABLE IF NOT EXISTS orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    product_id INTEGER NOT NULL,
                    status TEXT DEFAULT 'pending',
                    receipt_file_id TEXT,
                    config_id INTEGER,
                    admin_chat_id INTEGER,
                    admin_message_id INTEGER,
                    base_price INTEGER,
                    wallet_used INTEGER DEFAULT 0,
                    discount_code_id INTEGER,
                    discount_amount INTEGER DEFAULT 0,
                    final_price INTEGER,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT
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
                    admin_chat_id INTEGER,
                    admin_message_id INTEGER,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT
                );

                CREATE TABLE IF NOT EXISTS reseller_bots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    bot_token TEXT UNIQUE NOT NULL,
                    bot_username TEXT,
                    owner_telegram_id INTEGER NOT NULL,
                    owner_name TEXT,
                    db_path TEXT NOT NULL,
                    is_active INTEGER DEFAULT 1,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
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
                CREATE INDEX IF NOT EXISTS idx_configs_product_id ON configs(product_id);
                CREATE INDEX IF NOT EXISTS idx_configs_product_unused ON configs(product_id, is_used);
                CREATE INDEX IF NOT EXISTS idx_configs_assigned_user_id ON configs(assigned_user_id);
                CREATE INDEX IF NOT EXISTS idx_test_configs_unused ON test_configs(is_used);
                CREATE INDEX IF NOT EXISTS idx_test_configs_assigned_user_id ON test_configs(assigned_user_id);
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
                CREATE INDEX IF NOT EXISTS idx_reseller_bots_active ON reseller_bots(is_active);
                """
            )

            c.execute("INSERT OR IGNORE INTO admins (telegram_id) VALUES (?)", (owner_id,))

            for k, v in DEFAULT_SETTINGS.items():
                c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v))

            self._migrate_columns(conn)
            # اطمینان از این‌که همیشه مالک اصلی (از env) نقش «owner» را داشته باشد،
            # چه در نصب تازه و چه در ارتقای نصب‌های قدیمی‌تر که این ستون را نداشتند.
            conn.execute("UPDATE admins SET role='owner' WHERE telegram_id=?", (owner_id,))

    def _column_exists(self, conn, table: str, column: str) -> bool:
        cols = [r["name"] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]
        return column in cols

    def _migrate_columns(self, conn):
        migrations = [
            ("users", "referred_by", "INTEGER"),
            ("users", "referral_credit", "INTEGER DEFAULT 0"),
            ("users", "referral_first_purchase_rewarded", "INTEGER DEFAULT 0"),
            ("orders", "status", "TEXT DEFAULT 'pending'"),
            ("orders", "base_price", "INTEGER"),
            ("orders", "wallet_used", "INTEGER DEFAULT 0"),
            ("orders", "discount_code_id", "INTEGER"),
            ("orders", "discount_amount", "INTEGER DEFAULT 0"),
            ("orders", "final_price", "INTEGER"),
            ("users", "last_wheel_spin_at", "TEXT"),
            ("discount_codes", "expires_at", "TEXT"),
            ("discount_codes", "source", "TEXT"),
            ("products", "duration_days", "INTEGER DEFAULT 30"),
            ("configs", "expires_at", "TEXT"),
            ("configs", "renewal_reminder_sent", "INTEGER DEFAULT 0"),
            ("products", "low_stock_alert_sent", "INTEGER DEFAULT 0"),
            ("admins", "role", "TEXT DEFAULT 'admin'"),
            ("support_messages", "is_read_by_admin", "INTEGER DEFAULT 0"),
            ("tickets", "claimed_by", "INTEGER"),
        ]
        for table, col, coltype in migrations:
            if not self._column_exists(conn, table, col):
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {coltype}")

    # -----------------------------------------------------------------------
    # تنظیمات (settings)
    # -----------------------------------------------------------------------

    def get_setting(self, key: str, default: str = "") -> str:
        # تنظیمات در حافظه کش می‌شوند چون به ازای هر پیام ورودی (فیلترهای
        # روتر در handlers_user.py) چندین بار خوانده می‌شوند؛ خواندن از dict
        # به‌جای query جدید sqlite تفاوت محسوسی در سرعت پاسخ‌گویی ایجاد می‌کند.
        if self._settings_cache is None:
            self._load_settings_cache()
        return self._settings_cache.get(key, default)

    def _load_settings_cache(self):
        with self._get_conn() as conn:
            rows = conn.execute("SELECT key, value FROM settings").fetchall()
            cache = {r["key"]: r["value"] for r in rows}
        with self._lock:
            self._settings_cache = cache

    def set_setting(self, key: str, value: str):
        with self._get_conn() as conn:
            conn.execute(
                "INSERT INTO settings (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, value),
            )
        if self._settings_cache is not None:
            self._settings_cache[key] = value

    def get_all_settings(self) -> dict:
        if self._settings_cache is None:
            self._load_settings_cache()
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
        status_filter: 'all' | 'active' | 'expired' | 'blocked'
        خروجی: (rows, total_count)
        """
        now = datetime.utcnow().isoformat()
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
                "EXISTS (SELECT 1 FROM configs c WHERE c.assigned_user_id=u.telegram_id AND c.is_used=1 "
                "AND (c.expires_at IS NULL OR c.expires_at > ?))"
            )
            params.append(now)
        elif status_filter == "expired":
            conditions.append(
                "EXISTS (SELECT 1 FROM configs c WHERE c.assigned_user_id=u.telegram_id AND c.is_used=1) "
                "AND NOT EXISTS (SELECT 1 FROM configs c2 WHERE c2.assigned_user_id=u.telegram_id AND c2.is_used=1 "
                "AND (c2.expires_at IS NULL OR c2.expires_at > ?))"
            )
            params.append(now)

        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        with self._get_conn() as conn:
            total = conn.execute(f"SELECT COUNT(*) c FROM users u {where}", params).fetchone()["c"]
            rows = conn.execute(
                f"SELECT u.* FROM users u {where} ORDER BY u.id DESC LIMIT ? OFFSET ?",
                params + [limit, offset],
            ).fetchall()
            return rows, total

    def get_user_status(self, tg_id: int) -> str:
        """وضعیت خلاصه‌ی یک کاربر: 'blocked' | 'active' | 'expired' | 'none' (هیچ سرویسی نداشته)."""
        now = datetime.utcnow().isoformat()
        with self._get_conn() as conn:
            u = conn.execute("SELECT is_blocked FROM users WHERE telegram_id=?", (tg_id,)).fetchone()
            if u and u["is_blocked"]:
                return "blocked"
            has_active = conn.execute(
                "SELECT 1 FROM configs WHERE assigned_user_id=? AND is_used=1 "
                "AND (expires_at IS NULL OR expires_at > ?) LIMIT 1",
                (tg_id, now),
            ).fetchone()
            if has_active:
                return "active"
            has_any = conn.execute(
                "SELECT 1 FROM configs WHERE assigned_user_id=? AND is_used=1 LIMIT 1", (tg_id,)
            ).fetchone()
            return "expired" if has_any else "none"

    def get_user_full_history(self, tg_id: int):
        """تاریخچه‌ی کامل یک کاربر: سفارش‌ها (با نام محصول و لینک کانفیگ) + شارژهای کیف‌پول."""
        with self._get_conn() as conn:
            orders = conn.execute(
                "SELECT o.*, p.name as product_name, cf.link as config_link, cf.expires_at as config_expires_at "
                "FROM orders o "
                "LEFT JOIN products p ON o.product_id = p.id "
                "LEFT JOIN configs cf ON o.config_id = cf.id "
                "WHERE o.user_id=? ORDER BY o.id DESC",
                (tg_id,),
            ).fetchall()
            topups = conn.execute(
                "SELECT * FROM wallet_topups WHERE user_id=? ORDER BY id DESC", (tg_id,)
            ).fetchall()
            return {"orders": orders, "topups": topups}

    def get_expired_user_ids(self):
        """آیدی کاربرانی که سابقه‌ی سرویس دارند ولی الان هیچ سرویس فعالی ندارند و بلاک نیستند
        (برای ارسال پیام گروهی تشویق به تمدید)."""
        now = datetime.utcnow().isoformat()
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT DISTINCT u.telegram_id FROM users u "
                "WHERE u.is_blocked=0 "
                "AND EXISTS (SELECT 1 FROM configs c WHERE c.assigned_user_id=u.telegram_id AND c.is_used=1) "
                "AND NOT EXISTS (SELECT 1 FROM configs c2 WHERE c2.assigned_user_id=u.telegram_id AND c2.is_used=1 "
                "AND (c2.expires_at IS NULL OR c2.expires_at > ?))",
                (now,),
            ).fetchall()
            return [r["telegram_id"] for r in rows]

    def mark_test_used(self, tg_id: int):
        with self._get_conn() as conn:
            conn.execute("UPDATE users SET test_used=test_used+1 WHERE telegram_id=?", (tg_id,))

    def get_all_user_ids(self):
        with self._get_conn() as conn:
            rows = conn.execute("SELECT telegram_id FROM users WHERE is_blocked=0").fetchall()
            return [r["telegram_id"] for r in rows]

    def count_users(self):
        with self._get_conn() as conn:
            return conn.execute("SELECT COUNT(*) c FROM users").fetchone()["c"]

    # -----------------------------------------------------------------------
    # ادمین‌ها
    # -----------------------------------------------------------------------

    def is_admin(self, tg_id: int) -> bool:
        with self._get_conn() as conn:
            row = conn.execute("SELECT 1 FROM admins WHERE telegram_id=?", (tg_id,)).fetchone()
            return row is not None

    def get_admin_role(self, tg_id: int):
        """نقش ادمین را برمی‌گرداند: 'owner' | 'admin' | 'mid' | 'support' | None (اگر ادمین نباشد)."""
        with self._get_conn() as conn:
            row = conn.execute("SELECT role FROM admins WHERE telegram_id=?", (tg_id,)).fetchone()
            return row["role"] if row else None

    def is_full_admin(self, tg_id: int) -> bool:
        """دسترسی کامل عملیاتی: مالک، مدیر یا ادمین میانی (برخلاف پشتیبان که دسترسی محدود دارد)."""
        role = self.get_admin_role(tg_id)
        return role in ("owner", "admin", "mid")

    def is_senior_admin(self, tg_id: int) -> bool:
        """فقط مالک یا مدیر کامل؛ برای بخش‌های حساس که حتی ادمین میانی هم به آن‌ها دسترسی ندارد
        (آمار فروش، چیدمان منو، تنظیمات کمپین‌ها/تخفیف، لاگ ادمین، نمایندگی‌ها،
        برندینگ فروشگاه، و مدیریت محصولات/دسته‌بندی‌ها/کانفیگ‌بانک)."""
        role = self.get_admin_role(tg_id)
        return role in ("owner", "admin")

    def is_owner(self, tg_id: int) -> bool:
        return self.get_admin_role(tg_id) == "owner"

    def add_admin(self, tg_id: int, role: str = "admin"):
        if role not in ("admin", "mid", "support"):
            role = "admin"
        with self._get_conn() as conn:
            conn.execute(
                "INSERT INTO admins (telegram_id, role) VALUES (?, ?) "
                "ON CONFLICT(telegram_id) DO UPDATE SET role=excluded.role",
                (tg_id, role),
            )

    def set_admin_role(self, tg_id: int, role: str) -> bool:
        """تغییر نقش یک ادمین موجود. نقش «owner» هرگز از این مسیر قابل واگذاری نیست."""
        if role not in ("admin", "mid", "support"):
            return False
        with self._get_conn() as conn:
            row = conn.execute("SELECT role FROM admins WHERE telegram_id=?", (tg_id,)).fetchone()
            if not row or row["role"] == "owner":
                return False
            conn.execute("UPDATE admins SET role=? WHERE telegram_id=?", (role, tg_id))
        return True

    def remove_admin(self, tg_id: int, protected_owner_id: int = None) -> bool:
        if protected_owner_id is not None and tg_id == protected_owner_id:
            return False
        with self._get_conn() as conn:
            row = conn.execute("SELECT role FROM admins WHERE telegram_id=?", (tg_id,)).fetchone()
            if row and row["role"] == "owner":
                return False
            conn.execute("DELETE FROM admins WHERE telegram_id=?", (tg_id,))
        return True

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
    # لاگ فعالیت ادمین (audit log)
    # -----------------------------------------------------------------------

    def log_admin_action(self, admin_id: int, action: str, details: str = ""):
        """ثبت یک رخداد حساس (تغییر موجودی کیف‌پول، ویرایش قیمت و ...) در لاگ فعالیت ادمین."""
        with self._get_conn() as conn:
            conn.execute(
                "INSERT INTO admin_logs (admin_id, action, details, created_at) VALUES (?,?,?,?)",
                (admin_id, action, details, datetime.utcnow().isoformat()),
            )

    def get_admin_logs(self, limit: int = 50, offset: int = 0, admin_id: int = None):
        with self._get_conn() as conn:
            if admin_id is not None:
                total = conn.execute(
                    "SELECT COUNT(*) c FROM admin_logs WHERE admin_id = ?", (admin_id,)
                ).fetchone()["c"]
                rows = conn.execute(
                    "SELECT * FROM admin_logs WHERE admin_id = ? ORDER BY id DESC LIMIT ? OFFSET ?",
                    (admin_id, limit, offset),
                ).fetchall()
            else:
                total = conn.execute("SELECT COUNT(*) c FROM admin_logs").fetchone()["c"]
                rows = conn.execute(
                    "SELECT * FROM admin_logs ORDER BY id DESC LIMIT ? OFFSET ?", (limit, offset)
                ).fetchall()
            return rows, total

    # -----------------------------------------------------------------------
    # دسته‌بندی‌ها
    # -----------------------------------------------------------------------

    def add_category(self, name: str) -> int:
        with self._get_conn() as conn:
            cur = conn.execute("INSERT INTO categories (name) VALUES (?)", (name,))
            return cur.lastrowid

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
        with self._get_conn() as conn:
            row = conn.execute("SELECT is_active FROM categories WHERE id=?", (cat_id,)).fetchone()
            if row:
                new_val = 0 if row["is_active"] else 1
                conn.execute("UPDATE categories SET is_active=? WHERE id=?", (new_val, cat_id))

    def edit_category(self, cat_id: int, name: str):
        with self._get_conn() as conn:
            conn.execute("UPDATE categories SET name=? WHERE id=?", (name, cat_id))

    def delete_category(self, cat_id: int):
        with self._get_conn() as conn:
            conn.execute("DELETE FROM categories WHERE id=?", (cat_id,))

    # -----------------------------------------------------------------------
    # محصولات
    # -----------------------------------------------------------------------

    def add_product(self, category_id: int, name: str, price: int, description: str = "", duration_days: int = 30) -> int:
        with self._get_conn() as conn:
            cur = conn.execute(
                "INSERT INTO products (category_id, name, price, description, duration_days) VALUES (?, ?, ?, ?, ?)",
                (category_id, name, price, description, duration_days),
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
                      description: str = None, duration_days: int = None):
        fields, values = [], []
        if name is not None:
            fields.append("name=?"); values.append(name)
        if price is not None:
            fields.append("price=?"); values.append(price)
        if description is not None:
            fields.append("description=?"); values.append(description)
        if duration_days is not None:
            fields.append("duration_days=?"); values.append(duration_days)
        if not fields:
            return
        values.append(product_id)
        with self._get_conn() as conn:
            conn.execute(f"UPDATE products SET {', '.join(fields)} WHERE id=?", values)

    def delete_product(self, product_id: int):
        with self._get_conn() as conn:
            conn.execute("DELETE FROM products WHERE id=?", (product_id,))

    # -----------------------------------------------------------------------
    # مخزن کانفیگ (بانک لینک)
    # -----------------------------------------------------------------------

    def add_configs(self, product_id: int, links: list):
        with self._get_conn() as conn:
            conn.executemany(
                "INSERT INTO configs (product_id, link) VALUES (?, ?)",
                [(product_id, link.strip()) for link in links if link.strip()],
            )

    def count_available_configs(self, product_id: int) -> int:
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT COUNT(*) c FROM configs WHERE product_id=? AND is_used=0", (product_id,)
            ).fetchone()
            return row["c"]

    def check_low_stock_alert_state(self, product_id: int, stock: int, threshold: int) -> bool:
        """مدیریت وضعیت هشدار موجودی کم برای یک محصول.
        فقط یک‌بار برای هر افت زیر آستانه هشدار می‌دهد (True برمی‌گرداند)، و وقتی موجودی
        دوباره از آستانه بیشتر شد، وضعیت را ریست می‌کند تا برای افت بعدی دوباره هشدار بدهد."""
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT low_stock_alert_sent FROM products WHERE id=?", (product_id,)
            ).fetchone()
            already_sent = bool(row["low_stock_alert_sent"]) if row else False
            if stock <= threshold and not already_sent:
                conn.execute("UPDATE products SET low_stock_alert_sent=1 WHERE id=?", (product_id,))
                return True
            if stock > threshold and already_sent:
                conn.execute("UPDATE products SET low_stock_alert_sent=0 WHERE id=?", (product_id,))
            return False

    def get_unused_configs(self, product_id: int):
        with self._get_conn() as conn:
            return conn.execute(
                "SELECT id, link FROM configs WHERE product_id=? AND is_used=0 ORDER BY id", (product_id,)
            ).fetchall()

    def delete_config(self, config_id: int):
        with self._get_conn() as conn:
            conn.execute("DELETE FROM configs WHERE id=? AND is_used=0", (config_id,))

    def take_unused_config(self, product_id: int, user_tg_id: int):
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT id, link FROM configs WHERE product_id=? AND is_used=0 ORDER BY id LIMIT 1",
                (product_id,),
            ).fetchone()
            if not row:
                return None
            prod = conn.execute(
                "SELECT duration_days FROM products WHERE id=?", (product_id,)
            ).fetchone()
            duration_days = (prod["duration_days"] if prod and prod["duration_days"] else 30)
            now = datetime.utcnow()
            expires_at = (now + timedelta(days=duration_days)).isoformat()
            conn.execute(
                "UPDATE configs SET is_used=1, assigned_user_id=?, assigned_at=?, expires_at=?, "
                "renewal_reminder_sent=0 WHERE id=?",
                (user_tg_id, now.isoformat(), expires_at, row["id"]),
            )
            return {"id": row["id"], "link": row["link"], "expires_at": expires_at}

    def admin_take_random_config(self, product_id: int, admin_tg_id: int):
        """برای دکمه‌ی «دریافت کانفیگ رندوم» در پنل ادمین: برخلاف take_unused_config
        (که برای فروش واقعی به‌ترتیب FIFO عمل می‌کند)، این یکی از کانفیگ‌های آزاد را
        کاملاً تصادفی برمی‌دارد و مصرف‌شده علامت می‌زند."""
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT id, link FROM configs WHERE product_id=? AND is_used=0 ORDER BY RANDOM() LIMIT 1",
                (product_id,),
            ).fetchone()
            if not row:
                return None
            prod = conn.execute(
                "SELECT duration_days FROM products WHERE id=?", (product_id,)
            ).fetchone()
            duration_days = (prod["duration_days"] if prod and prod["duration_days"] else 30)
            now = datetime.utcnow()
            expires_at = (now + timedelta(days=duration_days)).isoformat()
            conn.execute(
                "UPDATE configs SET is_used=1, assigned_user_id=?, assigned_at=?, expires_at=?, "
                "renewal_reminder_sent=0 WHERE id=?",
                (admin_tg_id, now.isoformat(), expires_at, row["id"]),
            )
            return {"id": row["id"], "link": row["link"], "expires_at": expires_at}

    def get_config_by_id(self, config_id: int):
        with self._get_conn() as conn:
            return conn.execute("SELECT * FROM configs WHERE id=?", (config_id,)).fetchone()

    def release_config(self, config_id: int):
        with self._get_conn() as conn:
            conn.execute(
                "UPDATE configs SET is_used=0, assigned_user_id=NULL, assigned_at=NULL, "
                "expires_at=NULL, renewal_reminder_sent=0 WHERE id=?",
                (config_id,),
            )

    # -----------------------------------------------------------------------
    # کانفیگ تست (مخزن جدا)
    # -----------------------------------------------------------------------

    def add_test_configs(self, links: list):
        with self._get_conn() as conn:
            conn.executemany(
                "INSERT INTO test_configs (link) VALUES (?)",
                [(link.strip(),) for link in links if link.strip()],
            )

    def count_available_test_configs(self) -> int:
        with self._get_conn() as conn:
            row = conn.execute("SELECT COUNT(*) c FROM test_configs WHERE is_used=0").fetchone()
            return row["c"]

    def take_unused_test_config(self, user_tg_id: int):
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT id, link FROM test_configs WHERE is_used=0 ORDER BY id LIMIT 1"
            ).fetchone()
            if not row:
                return None
            conn.execute(
                "UPDATE test_configs SET is_used=1, assigned_user_id=?, assigned_at=? WHERE id=?",
                (user_tg_id, datetime.utcnow().isoformat(), row["id"]),
            )
            return {"id": row["id"], "link": row["link"]}

    def get_assigned_test_config(self, user_tg_id: int):
        with self._get_conn() as conn:
            return conn.execute(
                "SELECT id, link FROM test_configs WHERE assigned_user_id=? ORDER BY id DESC LIMIT 1",
                (user_tg_id,),
            ).fetchone()

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
    ) -> int:
        final_price = max(base_price - wallet_used - discount_amount, 0)
        with self._get_conn() as conn:
            cur = conn.execute(
                "INSERT INTO orders (user_id, product_id, status, base_price, wallet_used, "
                "discount_code_id, discount_amount, final_price) VALUES (?, ?, 'pending', ?, ?, ?, ?, ?)",
                (user_tg_id, product_id, base_price, wallet_used, discount_code_id, discount_amount, final_price),
            )
            return cur.lastrowid

    def set_order_receipt(self, order_id: int, file_id: str):
        with self._get_conn() as conn:
            conn.execute("UPDATE orders SET receipt_file_id=? WHERE id=?", (file_id, order_id))

    def set_order_admin_message(self, order_id: int, admin_chat_id: int, admin_message_id: int):
        with self._get_conn() as conn:
            conn.execute(
                "UPDATE orders SET admin_chat_id=?, admin_message_id=? WHERE id=?",
                (admin_chat_id, admin_message_id, order_id),
            )

    def get_order(self, order_id: int):
        with self._get_conn() as conn:
            return conn.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()

    def approve_order(self, order_id: int, config_id: int):
        with self._get_conn() as conn:
            conn.execute(
                "UPDATE orders SET status='approved', config_id=?, updated_at=? WHERE id=?",
                (config_id, datetime.utcnow().isoformat(), order_id),
            )

    def reject_order(self, order_id: int):
        order = self.get_order(order_id)
        with self._get_conn() as conn:
            conn.execute(
                "UPDATE orders SET status='rejected', updated_at=? WHERE id=?",
                (datetime.utcnow().isoformat(), order_id),
            )
        if order:
            if order["wallet_used"]:
                self.add_wallet_credit(order["user_id"], order["wallet_used"])
            if order["discount_code_id"]:
                self.decrement_discount_usage(order["discount_code_id"])

    def get_pending_orders(self):
        with self._get_conn() as conn:
            return conn.execute("SELECT * FROM orders WHERE status='pending' ORDER BY id").fetchall()

    def get_user_orders(self, user_tg_id: int):
        with self._get_conn() as conn:
            return conn.execute(
                "SELECT * FROM orders WHERE user_id=? ORDER BY id DESC", (user_tg_id,)
            ).fetchall()

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
            active_configs_c = conn.execute("SELECT COUNT(*) c FROM configs WHERE is_used=1").fetchone()["c"]
            open_tickets_c = conn.execute(
                "SELECT COUNT(*) c FROM tickets WHERE status IN ('open','answered')"
            ).fetchone()["c"]
            wallet_total = conn.execute("SELECT COALESCE(SUM(referral_credit),0) s FROM users").fetchone()["s"]

            current.update({
                "start_date": start_date,
                "end_date": end_date,
                "total_users": total_users,
                "active_configs": active_configs_c,
                "open_tickets": open_tickets_c,
                "wallet_total": wallet_total,
                "daily_series": daily_series,
                "category_breakdown": category_breakdown,
                "top_products": [{"name": r["name"], "orders": r["c"], "revenue": r["s"]} for r in top_products],
            })
            return current

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
                "o.wallet_used, o.discount_amount "
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

    def reward_referrer_if_first_purchase(self, referred_user_tg_id: int, paid_amount: int):
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT referred_by, referral_first_purchase_rewarded FROM users WHERE telegram_id=?",
                (referred_user_tg_id,),
            ).fetchone()
            if not row or not row["referred_by"] or row["referral_first_purchase_rewarded"]:
                return None

            conn.execute(
                "UPDATE users SET referral_first_purchase_rewarded=1 WHERE telegram_id=?",
                (referred_user_tg_id,),
            )
            referrer_id = row["referred_by"]

        if self.get_setting("referral_enabled", "1") != "1":
            return None

        percent = int(self.get_setting("referral_percent", "10") or 0)
        reward = (paid_amount * percent) // 100
        if reward > 0:
            self.add_wallet_credit(referrer_id, reward)
            return reward, referrer_id
        return None

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

    def set_topup_receipt(self, topup_id: int, file_id: str):
        with self._get_conn() as conn:
            conn.execute("UPDATE wallet_topups SET receipt_file_id=? WHERE id=?", (file_id, topup_id))

    def set_topup_admin_message(self, topup_id: int, admin_chat_id: int, admin_message_id: int):
        with self._get_conn() as conn:
            conn.execute(
                "UPDATE wallet_topups SET admin_chat_id=?, admin_message_id=? WHERE id=?",
                (admin_chat_id, admin_message_id, topup_id),
            )

    def get_topup(self, topup_id: int):
        with self._get_conn() as conn:
            return conn.execute("SELECT * FROM wallet_topups WHERE id=?", (topup_id,)).fetchone()

    def approve_topup(self, topup_id: int) -> bool:
        topup = self.get_topup(topup_id)
        if not topup or topup["status"] != "pending":
            return False
        with self._get_conn() as conn:
            conn.execute(
                "UPDATE wallet_topups SET status='approved', updated_at=? WHERE id=?",
                (datetime.utcnow().isoformat(), topup_id),
            )
        self.add_wallet_credit(topup["user_id"], topup["amount"])
        return True

    def reject_topup(self, topup_id: int):
        with self._get_conn() as conn:
            conn.execute(
                "UPDATE wallet_topups SET status='rejected', updated_at=? WHERE id=?",
                (datetime.utcnow().isoformat(), topup_id),
            )

    def get_pending_topups(self):
        with self._get_conn() as conn:
            return conn.execute("SELECT * FROM wallet_topups WHERE status='pending' ORDER BY id").fetchall()

    # -----------------------------------------------------------------------
    # ثبت‌نام بات‌های نمایندگی (فقط در دیتابیس بات اصلی معنا دارد)
    # -----------------------------------------------------------------------

    def register_reseller_bot(self, bot_token: str, bot_username: str, owner_telegram_id: int, owner_name: str, db_path: str) -> int:
        with self._get_conn() as conn:
            cur = conn.execute(
                "INSERT INTO reseller_bots (bot_token, bot_username, owner_telegram_id, owner_name, db_path) "
                "VALUES (?, ?, ?, ?, ?)",
                (bot_token, bot_username, owner_telegram_id, owner_name, db_path),
            )
            return cur.lastrowid

    def list_reseller_bots(self, active_only: bool = False):
        with self._get_conn() as conn:
            if active_only:
                return conn.execute("SELECT * FROM reseller_bots WHERE is_active=1 ORDER BY id").fetchall()
            return conn.execute("SELECT * FROM reseller_bots ORDER BY id").fetchall()

    def get_reseller_bot(self, bot_id: int):
        with self._get_conn() as conn:
            return conn.execute("SELECT * FROM reseller_bots WHERE id=?", (bot_id,)).fetchone()

    def toggle_reseller_bot(self, bot_id: int):
        with self._get_conn() as conn:
            row = conn.execute("SELECT is_active FROM reseller_bots WHERE id=?", (bot_id,)).fetchone()
            if row:
                conn.execute(
                    "UPDATE reseller_bots SET is_active=? WHERE id=?", (0 if row["is_active"] else 1, bot_id)
                )

    def edit_reseller_bot(self, bot_id: int, owner_telegram_id: int = None, owner_name: str = None):
        fields, values = [], []
        if owner_telegram_id is not None:
            fields.append("owner_telegram_id=?"); values.append(owner_telegram_id)
        if owner_name is not None:
            fields.append("owner_name=?"); values.append(owner_name)
        if not fields:
            return
        values.append(bot_id)
        with self._get_conn() as conn:
            conn.execute(f"UPDATE reseller_bots SET {', '.join(fields)} WHERE id=?", values)

    def delete_reseller_bot(self, bot_id: int):
        with self._get_conn() as conn:
            conn.execute("DELETE FROM reseller_bots WHERE id=?", (bot_id,))

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
    # یادآوری اتمام سرویس + کد تخفیف تشویقی تمدید
    # -----------------------------------------------------------------------

    def get_renewal_settings(self) -> dict:
        return {
            "enabled": self.get_setting("renewal_reminder_enabled", "1") == "1",
            "days_before": int(self.get_setting("renewal_reminder_days_before", "5") or 5),
            "discount_percent": int(self.get_setting("renewal_discount_percent", "20") or 20),
            "discount_expiry_hours": int(self.get_setting("renewal_discount_expiry_hours", "24") or 24),
        }

    def get_configs_due_for_renewal_reminder(self):
        """کانفیگ‌های فعال و بدون یادآوری را برمی‌گرداند.

        نکته مهم: زمان انقضای ذخیره‌شده در cf.expires_at عمداً در اینجا
        برای زمان‌بندی یادآوری استفاده نمی‌شود. زمان واقعی انقضا از لینک
        Subscription در renewal_reminders.py خوانده می‌شود.
        """
        settings = self.get_renewal_settings()
        if not settings["enabled"]:
            return []
        with self._get_conn() as conn:
            return conn.execute(
                "SELECT cf.id as config_id, cf.link, cf.assigned_user_id, cf.expires_at, "
                "p.id as product_id, p.name as product_name "
                "FROM configs cf JOIN products p ON cf.product_id = p.id "
                "WHERE cf.is_used=1 AND cf.renewal_reminder_sent=0 "
                "AND cf.link IS NOT NULL AND TRIM(cf.link) != ''"
            ).fetchall()

    def mark_renewal_reminder_sent(self, config_id: int):
        with self._get_conn() as conn:
            conn.execute("UPDATE configs SET renewal_reminder_sent=1 WHERE id=?", (config_id,))

    def generate_renewal_discount_code(self, user_tg_id: int) -> tuple:
        """یک کد تخفیف یکبارمصرف و محدود به زمان برای یادآوری تمدید سرویس کاربر می‌سازد.
        خروجی: (code, expires_at, percent, expiry_hours)"""
        settings = self.get_renewal_settings()
        expires_at = (datetime.utcnow() + timedelta(hours=settings["discount_expiry_hours"])).isoformat()
        code = f"RENEW{user_tg_id}{secrets.randbelow(9000) + 1000}"
        self.create_discount_code(
            code, percent=settings["discount_percent"], max_uses=1, expires_at=expires_at, source="renewal_reminder"
        )
        return code, expires_at, settings["discount_percent"], settings["discount_expiry_hours"]

    # -----------------------------------------------------------------------
    # چت پشتیبانی (مینی‌اپ + بات، یکپارچه)
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

    def get_expiring_configs_for_user(self, user_tg_id: int, days_before: int = None):
        """کانفیگ‌های فعال کاربر که تا چند روز آینده منقضی می‌شوند."""
        if days_before is None:
            days_before = int(self.get_setting("renewal_reminder_days_before", "5") or 5)
        with self._get_conn() as conn:
            threshold = (datetime.utcnow() + timedelta(days=days_before)).isoformat()
            now = datetime.utcnow().isoformat()
            return conn.execute(
                "SELECT cf.id as config_id, cf.link, cf.expires_at, o.product_id "
                "FROM configs cf JOIN orders o ON o.config_id = cf.id "
                "WHERE cf.assigned_user_id=? AND cf.is_used=1 AND cf.expires_at IS NOT NULL "
                "AND cf.expires_at > ? AND cf.expires_at <= ? AND o.user_id=?",
                (user_tg_id, now, threshold, user_tg_id),
            ).fetchall()

    # -----------------------------------------------------------------------
    # عضویت اجباری در کانال
    # -----------------------------------------------------------------------

    def get_force_join_settings(self) -> dict:
        return {
            "enabled": self.get_setting("force_join_enabled", "0") == "1",
            "channel": self.get_setting("force_join_channel", "").strip(),
        }
