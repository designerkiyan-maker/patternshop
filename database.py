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
from datetime import datetime
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
}


class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path

    # -----------------------------------------------------------------------
    # اتصال
    # -----------------------------------------------------------------------

    @contextmanager
    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

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
                """
            )

            c.execute("INSERT OR IGNORE INTO admins (telegram_id) VALUES (?)", (owner_id,))

            for k, v in DEFAULT_SETTINGS.items():
                c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v))

            self._migrate_columns(conn)

    def _column_exists(self, conn, table: str, column: str) -> bool:
        cols = [r["name"] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]
        return column in cols

    def _migrate_columns(self, conn):
        migrations = [
            ("users", "referred_by", "INTEGER"),
            ("users", "referral_credit", "INTEGER DEFAULT 0"),
            ("users", "referral_first_purchase_rewarded", "INTEGER DEFAULT 0"),
            ("orders", "base_price", "INTEGER"),
            ("orders", "wallet_used", "INTEGER DEFAULT 0"),
            ("orders", "discount_code_id", "INTEGER"),
            ("orders", "discount_amount", "INTEGER DEFAULT 0"),
            ("orders", "final_price", "INTEGER"),
        ]
        for table, col, coltype in migrations:
            if not self._column_exists(conn, table, col):
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {coltype}")

    # -----------------------------------------------------------------------
    # تنظیمات (settings)
    # -----------------------------------------------------------------------

    def get_setting(self, key: str, default: str = "") -> str:
        with self._get_conn() as conn:
            row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
            return row["value"] if row else default

    def set_setting(self, key: str, value: str):
        with self._get_conn() as conn:
            conn.execute(
                "INSERT INTO settings (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, value),
            )

    def get_all_settings(self) -> dict:
        with self._get_conn() as conn:
            rows = conn.execute("SELECT key, value FROM settings").fetchall()
            return {r["key"]: r["value"] for r in rows}

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

    def add_admin(self, tg_id: int):
        with self._get_conn() as conn:
            conn.execute("INSERT OR IGNORE INTO admins (telegram_id) VALUES (?)", (tg_id,))

    def remove_admin(self, tg_id: int, protected_owner_id: int = None) -> bool:
        if protected_owner_id is not None and tg_id == protected_owner_id:
            return False
        with self._get_conn() as conn:
            conn.execute("DELETE FROM admins WHERE telegram_id=?", (tg_id,))
        return True

    def list_admins(self):
        with self._get_conn() as conn:
            rows = conn.execute("SELECT telegram_id FROM admins").fetchall()
            return [r["telegram_id"] for r in rows]

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

    def delete_category(self, cat_id: int):
        with self._get_conn() as conn:
            conn.execute("DELETE FROM categories WHERE id=?", (cat_id,))

    # -----------------------------------------------------------------------
    # محصولات
    # -----------------------------------------------------------------------

    def add_product(self, category_id: int, name: str, price: int, description: str = "") -> int:
        with self._get_conn() as conn:
            cur = conn.execute(
                "INSERT INTO products (category_id, name, price, description) VALUES (?, ?, ?, ?)",
                (category_id, name, price, description),
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

    def take_unused_config(self, product_id: int, user_tg_id: int):
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT id, link FROM configs WHERE product_id=? AND is_used=0 ORDER BY id LIMIT 1",
                (product_id,),
            ).fetchone()
            if not row:
                return None
            conn.execute(
                "UPDATE configs SET is_used=1, assigned_user_id=?, assigned_at=? WHERE id=?",
                (user_tg_id, datetime.utcnow().isoformat(), row["id"]),
            )
            return {"id": row["id"], "link": row["link"]}

    def get_config_by_id(self, config_id: int):
        with self._get_conn() as conn:
            return conn.execute("SELECT * FROM configs WHERE id=?", (config_id,)).fetchone()

    def release_config(self, config_id: int):
        with self._get_conn() as conn:
            conn.execute(
                "UPDATE configs SET is_used=0, assigned_user_id=NULL, assigned_at=NULL WHERE id=?",
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

    def create_discount_code(self, code: str, percent: int = None, fixed_amount: int = None, max_uses: int = 0) -> int:
        with self._get_conn() as conn:
            cur = conn.execute(
                "INSERT INTO discount_codes (code, percent, fixed_amount, max_uses) VALUES (?, ?, ?, ?)",
                (code.strip().upper(), percent, fixed_amount, max_uses),
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

    def delete_reseller_bot(self, bot_id: int):
        with self._get_conn() as conn:
            conn.execute("DELETE FROM reseller_bots WHERE id=?", (bot_id,))
