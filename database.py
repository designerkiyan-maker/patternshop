# -*- coding: utf-8 -*-
"""
لایه دیتابیس - SQLite
تمام عملیات ذخیره و بازیابی داده در این فایل قرار دارد.
"""

import sqlite3
from datetime import datetime
from contextlib import contextmanager

from config import DB_PATH, OWNER_ID

# ---------------------------------------------------------------------------
# اتصال
# ---------------------------------------------------------------------------

@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


DEFAULT_SETTINGS = {
    "welcome_text": "👋 به فروشگاه کانفیگ V2Ray خوش آمدید!\nاز منوی زیر یکی از گزینه‌ها را انتخاب کنید.",
    "btn_buy": "🛒 خرید کانفیگ",
    "btn_test": "🧪 کانفیگ تست رایگان",
    "btn_contact": "📞 ارتباط با پشتیبانی",
    "btn_my_orders": "📦 سفارش‌های من",
    "btn_referral": "🤝 زیرمجموعه‌گیری من",
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
    "btn_admin_panel_style": "danger",
    # سیستم زیرمجموعه‌گیری
    "referral_enabled": "1",
    "referral_percent": "10",  # درصدی که به دعوت‌کننده به‌عنوان اعتبار کیف پول تعلق می‌گیرد
}


def init_db():
    with get_conn() as conn:
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
            """
        )

        # ادمین مالک
        c.execute("INSERT OR IGNORE INTO admins (telegram_id) VALUES (?)", (OWNER_ID,))

        # تنظیمات پیش‌فرض
        for k, v in DEFAULT_SETTINGS.items():
            c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v))

        # مهاجرت ستون‌های جدید برای دیتابیس‌هایی که قبلاً ساخته شده‌اند
        _migrate_columns(conn)


def _column_exists(conn, table: str, column: str) -> bool:
    cols = [r["name"] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]
    return column in cols


def _migrate_columns(conn):
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
        if not _column_exists(conn, table, col):
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {coltype}")


# ---------------------------------------------------------------------------
# تنظیمات (settings)
# ---------------------------------------------------------------------------

def get_setting(key: str, default: str = "") -> str:
    with get_conn() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default


def set_setting(key: str, value: str):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )


def get_all_settings() -> dict:
    with get_conn() as conn:
        rows = conn.execute("SELECT key, value FROM settings").fetchall()
        return {r["key"]: r["value"] for r in rows}


# ---------------------------------------------------------------------------
# کاربران
# ---------------------------------------------------------------------------

def add_or_update_user(tg_id: int, username: str, first_name: str):
    with get_conn() as conn:
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


def get_user(tg_id: int):
    with get_conn() as conn:
        return conn.execute("SELECT * FROM users WHERE telegram_id=?", (tg_id,)).fetchone()


def set_user_blocked(tg_id: int, blocked: bool):
    with get_conn() as conn:
        conn.execute("UPDATE users SET is_blocked=? WHERE telegram_id=?", (1 if blocked else 0, tg_id))


def mark_test_used(tg_id: int):
    with get_conn() as conn:
        conn.execute("UPDATE users SET test_used=test_used+1 WHERE telegram_id=?", (tg_id,))


def get_all_user_ids():
    with get_conn() as conn:
        rows = conn.execute("SELECT telegram_id FROM users WHERE is_blocked=0").fetchall()
        return [r["telegram_id"] for r in rows]


def count_users():
    with get_conn() as conn:
        return conn.execute("SELECT COUNT(*) c FROM users").fetchone()["c"]


# ---------------------------------------------------------------------------
# ادمین‌ها
# ---------------------------------------------------------------------------

def is_admin(tg_id: int) -> bool:
    with get_conn() as conn:
        row = conn.execute("SELECT 1 FROM admins WHERE telegram_id=?", (tg_id,)).fetchone()
        return row is not None


def add_admin(tg_id: int):
    with get_conn() as conn:
        conn.execute("INSERT OR IGNORE INTO admins (telegram_id) VALUES (?)", (tg_id,))


def remove_admin(tg_id: int):
    if tg_id == OWNER_ID:
        return False
    with get_conn() as conn:
        conn.execute("DELETE FROM admins WHERE telegram_id=?", (tg_id,))
    return True


def list_admins():
    with get_conn() as conn:
        rows = conn.execute("SELECT telegram_id FROM admins").fetchall()
        return [r["telegram_id"] for r in rows]


# ---------------------------------------------------------------------------
# دسته‌بندی‌ها
# ---------------------------------------------------------------------------

def add_category(name: str) -> int:
    with get_conn() as conn:
        cur = conn.execute("INSERT INTO categories (name) VALUES (?)", (name,))
        return cur.lastrowid


def get_categories(active_only=True):
    with get_conn() as conn:
        if active_only:
            rows = conn.execute(
                "SELECT * FROM categories WHERE is_active=1 ORDER BY sort_order, id"
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM categories ORDER BY sort_order, id").fetchall()
        return rows


def get_category(cat_id: int):
    with get_conn() as conn:
        return conn.execute("SELECT * FROM categories WHERE id=?", (cat_id,)).fetchone()


def toggle_category(cat_id: int):
    with get_conn() as conn:
        row = conn.execute("SELECT is_active FROM categories WHERE id=?", (cat_id,)).fetchone()
        if row:
            new_val = 0 if row["is_active"] else 1
            conn.execute("UPDATE categories SET is_active=? WHERE id=?", (new_val, cat_id))


def delete_category(cat_id: int):
    with get_conn() as conn:
        conn.execute("DELETE FROM categories WHERE id=?", (cat_id,))


# ---------------------------------------------------------------------------
# محصولات
# ---------------------------------------------------------------------------

def add_product(category_id: int, name: str, price: int, description: str = "") -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO products (category_id, name, price, description) VALUES (?, ?, ?, ?)",
            (category_id, name, price, description),
        )
        return cur.lastrowid


def get_products(category_id: int, active_only=True):
    with get_conn() as conn:
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


def get_all_products():
    with get_conn() as conn:
        return conn.execute(
            "SELECT p.*, c.name as category_name FROM products p "
            "JOIN categories c ON p.category_id=c.id ORDER BY c.sort_order, p.id"
        ).fetchall()


def get_product(product_id: int):
    with get_conn() as conn:
        return conn.execute("SELECT * FROM products WHERE id=?", (product_id,)).fetchone()


def toggle_product(product_id: int):
    with get_conn() as conn:
        row = conn.execute("SELECT is_active FROM products WHERE id=?", (product_id,)).fetchone()
        if row:
            new_val = 0 if row["is_active"] else 1
            conn.execute("UPDATE products SET is_active=? WHERE id=?", (new_val, product_id))


def delete_product(product_id: int):
    with get_conn() as conn:
        conn.execute("DELETE FROM products WHERE id=?", (product_id,))


# ---------------------------------------------------------------------------
# مخزن کانفیگ (بانک لینک) - هر لینک فقط یکبار به یک کاربر تعلق می‌گیرد
# ---------------------------------------------------------------------------

def add_configs(product_id: int, links: list):
    with get_conn() as conn:
        conn.executemany(
            "INSERT INTO configs (product_id, link) VALUES (?, ?)",
            [(product_id, link.strip()) for link in links if link.strip()],
        )


def count_available_configs(product_id: int) -> int:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) c FROM configs WHERE product_id=? AND is_used=0", (product_id,)
        ).fetchone()
        return row["c"]


def take_unused_config(product_id: int, user_tg_id: int):
    """یک لینک استفاده‌نشده را قفل کرده، به کاربر اختصاص می‌دهد و برمی‌گرداند."""
    with get_conn() as conn:
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


def get_config_by_id(config_id: int):
    with get_conn() as conn:
        return conn.execute("SELECT * FROM configs WHERE id=?", (config_id,)).fetchone()


def release_config(config_id: int):
    """در صورت رد شدن سفارش، لینک را به مخزن برمی‌گرداند تا دوباره قابل واگذاری باشد."""
    with get_conn() as conn:
        conn.execute(
            "UPDATE configs SET is_used=0, assigned_user_id=NULL, assigned_at=NULL WHERE id=?",
            (config_id,),
        )


# ---------------------------------------------------------------------------
# کانفیگ تست (مخزن جدا)
# ---------------------------------------------------------------------------

def add_test_configs(links: list):
    with get_conn() as conn:
        conn.executemany(
            "INSERT INTO test_configs (link) VALUES (?)",
            [(link.strip(),) for link in links if link.strip()],
        )


def count_available_test_configs() -> int:
    with get_conn() as conn:
        row = conn.execute("SELECT COUNT(*) c FROM test_configs WHERE is_used=0").fetchone()
        return row["c"]


def take_unused_test_config(user_tg_id: int):
    with get_conn() as conn:
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


# ---------------------------------------------------------------------------
# سفارش‌ها
# ---------------------------------------------------------------------------

def create_order(
    user_tg_id: int,
    product_id: int,
    base_price: int,
    wallet_used: int = 0,
    discount_code_id: int = None,
    discount_amount: int = 0,
) -> int:
    """سفارش جدید می‌سازد. مبلغ کیف پول و کد تخفیف در همین لحظه رزرو/کسر می‌شوند
    (نه در زمان تایید ادمین) تا در حین بررسی رسید توسط کاربر دیگری قابل استفاده مجدد نباشند.
    اگر سفارش بعداً رد شود، این مقادیر خودکار توسط reject_order برگردانده می‌شوند."""
    final_price = max(base_price - wallet_used - discount_amount, 0)
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO orders (user_id, product_id, status, base_price, wallet_used, "
            "discount_code_id, discount_amount, final_price) VALUES (?, ?, 'pending', ?, ?, ?, ?, ?)",
            (user_tg_id, product_id, base_price, wallet_used, discount_code_id, discount_amount, final_price),
        )
        return cur.lastrowid


def set_order_receipt(order_id: int, file_id: str):
    with get_conn() as conn:
        conn.execute("UPDATE orders SET receipt_file_id=? WHERE id=?", (file_id, order_id))


def set_order_admin_message(order_id: int, admin_chat_id: int, admin_message_id: int):
    with get_conn() as conn:
        conn.execute(
            "UPDATE orders SET admin_chat_id=?, admin_message_id=? WHERE id=?",
            (admin_chat_id, admin_message_id, order_id),
        )


def get_order(order_id: int):
    with get_conn() as conn:
        return conn.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()


def approve_order(order_id: int, config_id: int):
    with get_conn() as conn:
        conn.execute(
            "UPDATE orders SET status='approved', config_id=?, updated_at=? WHERE id=?",
            (config_id, datetime.utcnow().isoformat(), order_id),
        )


def reject_order(order_id: int):
    """سفارش را رد می‌کند و در صورت استفاده از کیف پول یا کد تخفیف، آن‌ها را برمی‌گرداند."""
    order = get_order(order_id)
    with get_conn() as conn:
        conn.execute(
            "UPDATE orders SET status='rejected', updated_at=? WHERE id=?",
            (datetime.utcnow().isoformat(), order_id),
        )
    if order:
        if order["wallet_used"]:
            add_wallet_credit(order["user_id"], order["wallet_used"])
        if order["discount_code_id"]:
            decrement_discount_usage(order["discount_code_id"])


def get_pending_orders():
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM orders WHERE status='pending' ORDER BY id"
        ).fetchall()


def get_user_orders(user_tg_id: int):
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM orders WHERE user_id=? ORDER BY id DESC", (user_tg_id,)
        ).fetchall()


# ---------------------------------------------------------------------------
# آمار
# ---------------------------------------------------------------------------

def get_stats():
    with get_conn() as conn:
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


# ---------------------------------------------------------------------------
# سیستم زیرمجموعه‌گیری (رفرال) و کیف پول اعتباری
# ---------------------------------------------------------------------------

def set_referred_by(user_tg_id: int, referrer_tg_id: int):
    """کاربر جدید را زیرمجموعه‌ی یک دعوت‌کننده ثبت می‌کند (فقط یک‌بار و فقط اگر قبلاً ثبت نشده باشد)."""
    if user_tg_id == referrer_tg_id:
        return
    with get_conn() as conn:
        row = conn.execute("SELECT referred_by FROM users WHERE telegram_id=?", (user_tg_id,)).fetchone()
        if row and row["referred_by"] is None:
            referrer_exists = conn.execute(
                "SELECT 1 FROM users WHERE telegram_id=?", (referrer_tg_id,)
            ).fetchone()
            if referrer_exists:
                conn.execute(
                    "UPDATE users SET referred_by=? WHERE telegram_id=?", (referrer_tg_id, user_tg_id)
                )


def get_referral_stats(user_tg_id: int) -> dict:
    with get_conn() as conn:
        count = conn.execute(
            "SELECT COUNT(*) c FROM users WHERE referred_by=?", (user_tg_id,)
        ).fetchone()["c"]
        row = conn.execute(
            "SELECT referral_credit FROM users WHERE telegram_id=?", (user_tg_id,)
        ).fetchone()
        credit = row["referral_credit"] if row else 0
        return {"count": count, "credit": credit}


def get_wallet_credit(user_tg_id: int) -> int:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT referral_credit FROM users WHERE telegram_id=?", (user_tg_id,)
        ).fetchone()
        return row["referral_credit"] if row else 0


def add_wallet_credit(user_tg_id: int, delta: int):
    """مقدار دلخواه (مثبت یا منفی) به اعتبار کیف پول کاربر اضافه می‌کند، هرگز منفی نمی‌شود."""
    with get_conn() as conn:
        conn.execute(
            "UPDATE users SET referral_credit = MAX(referral_credit + ?, 0) WHERE telegram_id=?",
            (delta, user_tg_id),
        )


def reward_referrer_if_first_purchase(referred_user_tg_id: int, paid_amount: int):
    """وقتی خرید یک کاربر تایید می‌شود، اگر این اولین خرید تاییدشده‌ی او باشد و او زیرمجموعه‌ی
    کسی باشد، درصدی از مبلغ به‌عنوان اعتبار کیف پول به دعوت‌کننده تعلق می‌گیرد.
    خروجی: (مبلغ پاداش, آیدی دعوت‌کننده) یا None اگر پاداشی تعلق نگرفت."""
    with get_conn() as conn:
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

    if get_setting("referral_enabled", "1") != "1":
        return None

    percent = int(get_setting("referral_percent", "10") or 0)
    reward = (paid_amount * percent) // 100
    if reward > 0:
        add_wallet_credit(referrer_id, reward)
        return reward, referrer_id
    return None


# ---------------------------------------------------------------------------
# کدهای تخفیف
# ---------------------------------------------------------------------------

def create_discount_code(code: str, percent: int = None, fixed_amount: int = None, max_uses: int = 0) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO discount_codes (code, percent, fixed_amount, max_uses) VALUES (?, ?, ?, ?)",
            (code.strip().upper(), percent, fixed_amount, max_uses),
        )
        return cur.lastrowid


def get_discount_code(code: str):
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM discount_codes WHERE code=?", (code.strip().upper(),)
        ).fetchone()


def get_discount_code_by_id(code_id: int):
    with get_conn() as conn:
        return conn.execute("SELECT * FROM discount_codes WHERE id=?", (code_id,)).fetchone()


def list_discount_codes():
    with get_conn() as conn:
        return conn.execute("SELECT * FROM discount_codes ORDER BY id DESC").fetchall()


def toggle_discount_code(code_id: int):
    with get_conn() as conn:
        row = conn.execute("SELECT is_active FROM discount_codes WHERE id=?", (code_id,)).fetchone()
        if row:
            conn.execute(
                "UPDATE discount_codes SET is_active=? WHERE id=?",
                (0 if row["is_active"] else 1, code_id),
            )


def delete_discount_code(code_id: int):
    with get_conn() as conn:
        conn.execute("DELETE FROM discount_codes WHERE id=?", (code_id,))


def increment_discount_usage(code_id: int):
    with get_conn() as conn:
        conn.execute("UPDATE discount_codes SET used_count = used_count + 1 WHERE id=?", (code_id,))


def decrement_discount_usage(code_id: int):
    with get_conn() as conn:
        conn.execute(
            "UPDATE discount_codes SET used_count = MAX(used_count - 1, 0) WHERE id=?", (code_id,)
        )


def is_discount_code_valid(row) -> bool:
    if not row:
        return False
    if not row["is_active"]:
        return False
    if row["max_uses"] and row["used_count"] >= row["max_uses"]:
        return False
    return True


def compute_discount_amount(row, price: int) -> int:
    if row["percent"]:
        return min((price * row["percent"]) // 100, price)
    if row["fixed_amount"]:
        return min(row["fixed_amount"], price)
    return 0


# ---------------------------------------------------------------------------
# شارژ کیف پول (توسط خود کاربر، با تایید ادمین)
# ---------------------------------------------------------------------------

def create_topup(user_tg_id: int, amount: int) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO wallet_topups (user_id, amount, status) VALUES (?, ?, 'pending')",
            (user_tg_id, amount),
        )
        return cur.lastrowid


def set_topup_receipt(topup_id: int, file_id: str):
    with get_conn() as conn:
        conn.execute("UPDATE wallet_topups SET receipt_file_id=? WHERE id=?", (file_id, topup_id))


def set_topup_admin_message(topup_id: int, admin_chat_id: int, admin_message_id: int):
    with get_conn() as conn:
        conn.execute(
            "UPDATE wallet_topups SET admin_chat_id=?, admin_message_id=? WHERE id=?",
            (admin_chat_id, admin_message_id, topup_id),
        )


def get_topup(topup_id: int):
    with get_conn() as conn:
        return conn.execute("SELECT * FROM wallet_topups WHERE id=?", (topup_id,)).fetchone()


def approve_topup(topup_id: int) -> bool:
    topup = get_topup(topup_id)
    if not topup or topup["status"] != "pending":
        return False
    with get_conn() as conn:
        conn.execute(
            "UPDATE wallet_topups SET status='approved', updated_at=? WHERE id=?",
            (datetime.utcnow().isoformat(), topup_id),
        )
    add_wallet_credit(topup["user_id"], topup["amount"])
    return True


def reject_topup(topup_id: int):
    with get_conn() as conn:
        conn.execute(
            "UPDATE wallet_topups SET status='rejected', updated_at=? WHERE id=?",
            (datetime.utcnow().isoformat(), topup_id),
        )


def get_pending_topups():
    with get_conn() as conn:
        return conn.execute("SELECT * FROM wallet_topups WHERE status='pending' ORDER BY id").fetchall()
