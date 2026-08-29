# -*- coding: utf-8 -*-
"""
ساخت کیبوردهای شیشه‌ای و معمولی بات فروش الگوی خیاطی

تمام توابعی که به تنظیمات/داده نیاز دارند، شیء db (نمونه‌ی Database) را
به‌عنوان پارامتر می‌گیرند - نه اینکه از یک ماژول سراسری import شود.
"""

import os

from aiogram.types import (
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    WebAppInfo,
)

from database import MENU_BUTTON_META


def _miniapp_url() -> str:
    """آدرس Mini App از متغیر محیطی MINIAPP_URL (خالی یعنی دکمه‌ی فروشگاه وب نمایش داده نشود)."""
    return os.getenv("MINIAPP_URL", "").rstrip("/")


# ---------------------------------------------------------------------------
# منوی اصلی (Reply Keyboard)
# ---------------------------------------------------------------------------

def _styled_button(text: str, style_value: str) -> KeyboardButton:
    """می‌سازد یک دکمه با رنگ دلخواه (ویژگی style در Bot API 9.4 به بعد).
    مقدار خالی یعنی رنگ پیش‌فرض (خاکستری)."""
    style = style_value if style_value in ("primary", "success", "danger") else None
    return KeyboardButton(text=text, style=style)


def _menu_items(db, is_admin: bool):
    """لیست مشترک آیتم‌های منوی اصلی را برمی‌گرداند: (key, text, style).
    این تابع پایه‌ی هر دو نوع منو (معمولی/پایین و شیشه‌ای/بالا) است تا منطق
    نمایش/عدم‌نمایش هر دکمه دقیقاً یک‌بار نوشته شده و همیشه هماهنگ بماند."""
    settings = db.get_all_settings()
    order = db.get_menu_order()

    def item_buy():
        return (settings.get("btn_buy", "🛒 خرید الگو"), settings.get("btn_buy_style", ""))

    def item_test():
        if settings.get("test_enabled", "1") != "1":
            return None
        return (settings.get("btn_test", "🧪 الگوی نمونه رایگان"), settings.get("btn_test_style", ""))

    def item_my_orders():
        return (settings.get("btn_my_orders", "📦 سفارش‌های من"), settings.get("btn_my_orders_style", ""))

    def item_wallet():
        return (settings.get("btn_wallet", "👛 کیف پول من"), settings.get("btn_wallet_style", ""))

    def item_referral():
        if settings.get("referral_button_enabled", "1") != "1":
            return None
        any_mode_enabled = (
            settings.get("referral_enabled", "1") == "1"
            or settings.get("referral_free_config_enabled", "0") == "1"
            or settings.get("referral_invite_bonus_enabled", "0") == "1"
        )
        if not any_mode_enabled:
            return None
        return (settings.get("btn_referral", "🤝 زیرمجموعه‌گیری من"), settings.get("btn_referral_style", ""))

    def item_wheel():
        if settings.get("wheel_enabled", "1") != "1":
            return None
        return (settings.get("btn_wheel", "🎡 گردونه شانس"), settings.get("btn_wheel_style", ""))

    def item_contact():
        return (settings.get("btn_contact", "📞 ارتباط با پشتیبانی"), settings.get("btn_contact_style", ""))

    def item_admin_panel():
        if not is_admin:
            return None
        return (settings.get("btn_admin_panel", "⚙️ پنل مدیریت"), settings.get("btn_admin_panel_style", ""))

    def item_miniapp():
        if not _miniapp_url():
            return None
        if settings.get("miniapp_button_enabled", "1") != "1":
            return None
        return (settings.get("btn_miniapp", "🛍 فروشگاه"), settings.get("btn_miniapp_style", "primary"))

    builders = {
        "btn_buy": item_buy,
        "btn_test": item_test,
        "btn_my_orders": item_my_orders,
        "btn_wallet": item_wallet,
        "btn_referral": item_referral,
        "btn_wheel": item_wheel,
        "btn_miniapp": item_miniapp,
        "btn_contact": item_contact,
        "btn_admin_panel": item_admin_panel,
    }

    items = []
    for key in order:
        builder = builders.get(key)
        if not builder:
            continue
        result = builder()
        if result:
            text, style = result
            items.append((key, text, style))
    return items


def _menu_columns(db) -> int:
    """تعداد دکمه در هر ردیف منوی اصلی (۱ یا ۲) بر اساس تنظیمات."""
    try:
        cols = int(db.get_setting("main_menu_columns", "1") or "1")
    except (TypeError, ValueError):
        cols = 1
    return 2 if cols == 2 else 1


def _chunk_row(buttons: list, columns: int) -> list:
    """لیست دکمه‌ها را به ردیف‌هایی با تعداد ستون مشخص تقسیم می‌کند - همان
    الگویی که در پنل مدیریت (admin_panel_kb) استفاده شده، فقط عمومی‌شده."""
    return [buttons[i:i + columns] for i in range(0, len(buttons), columns)]


def _menu_item_rows(db, items: list) -> list:
    """آیتم‌های منو (لیست تخت (key, text, style)) را بر اساس چیدمان دلخواه
    کاربر (main_menu_row_breaks) به ردیف‌ها تقسیم می‌کند: هر دکمه‌ای که کلیدش
    در لیست breaks باشد، یک ردیف تازه شروع می‌کند؛ بقیه به ردیف دکمه‌ی قبلی
    خودشان می‌چسبند. یعنی چیدمان دیگر به تعداد ستون ثابت محدود نیست - مثلاً
    می‌شود یک دکمه تمام‌عرض بالا، بعد چند دکمه کنار هم پایینش داشت.
    اگر کاربر هنوز چیدمان سفارشی نساخته باشد (breaks is None)، برای سازگاری
    با نصب‌های قدیمی از تنظیم main_menu_columns (۱ یا ۲ ستون ثابت) استفاده
    می‌شود."""
    breaks = db.get_menu_row_breaks()
    if breaks is None:
        columns = _menu_columns(db)
        return _chunk_row(items, columns)

    break_set = set(breaks)
    rows, current = [], []
    for item in items:
        key = item[0]
        if current and key in break_set:
            rows.append(current)
            current = []
        current.append(item)
    if current:
        rows.append(current)
    return rows


def main_menu_kb(db, is_admin: bool = False, *_legacy_args):
    """منوی پایین (Reply Keyboard). اگر از تنظیمات غیرفعال شده باشد،
    ReplyKeyboardRemove برمی‌گرداند تا کیبورد قبلی از پایین صفحه‌ی کاربر جمع شود.
    (پارامترهای قدیمی مثل is_main_bot دیگر معنا ندارند و نادیده گرفته می‌شوند.)"""
    if db.get_setting("main_menu_reply_enabled", "1") != "1":
        return ReplyKeyboardRemove()

    items = _menu_items(db, is_admin)
    item_rows = _menu_item_rows(db, items)
    rows = []
    for row in item_rows:
        buttons = []
        for _key, text, style in row:
            if _key == "btn_miniapp":
                # دکمه‌ی وب‌اپ: با کلیک، Mini App مستقیم باز می‌شود (بدون ارسال پیام)
                buttons.append(KeyboardButton(text=text, web_app=WebAppInfo(url=_miniapp_url())))
            else:
                buttons.append(_styled_button(text, style))
        rows.append(buttons)
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def main_menu_inline_kb(db, is_admin: bool = False, *_legacy_args) -> InlineKeyboardMarkup:
    """منوی شیشه‌ای بالا (Inline Keyboard) - همان آیتم‌های منوی پایین، به شکل inline.
    روی کلیک هر دکمه، callback_data به‌صورت 'mm:<key>' ارسال می‌شود که در
    handlers_user.py / handlers_admin.py به همان هندلر متنی متناظرش وصل شده."""
    items = _menu_items(db, is_admin)
    item_rows = _menu_item_rows(db, items)

    def _build_button(key, text, style):
        if key == "btn_miniapp":
            return InlineKeyboardButton(text=text, web_app=WebAppInfo(url=_miniapp_url()))
        s = style if style in ("primary", "success", "danger") else None
        return InlineKeyboardButton(text=text, callback_data=f"mm:{key}", style=s)

    rows = [[_build_button(key, text, style) for key, text, style in row] for row in item_rows]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def menu_for_user(db, user_tg_id: int, *_legacy_args):
    """منوی reply مناسب کاربر (پارامترهای قدیمی مثل is_main_bot نادیده گرفته می‌شوند)."""
    return main_menu_kb(db, db.is_admin(user_tg_id))


def inline_menu_for_user(db, user_tg_id: int, *_legacy_args) -> InlineKeyboardMarkup:
    """معادل menu_for_user ولی نسخه‌ی شیشه‌ای (inline). اگر منوی شیشه‌ای از
    تنظیمات غیرفعال باشد None برمی‌گرداند تا فراخوان اصلاً پیامی نفرستد."""
    if db.get_setting("main_menu_inline_enabled", "0") != "1":
        return None
    return main_menu_inline_kb(db, db.is_admin(user_tg_id))


# ---------------------------------------------------------------------------
# دسته‌بندی‌ها / محصولات (کاربر)
# ---------------------------------------------------------------------------

def categories_kb(db, categories, *_legacy_args) -> InlineKeyboardMarkup:
    rows = []
    for cat in categories:
        rows.append([_styled_inline(db, f"📁 {cat['name']}", f"cat:{cat['id']}", "btn_cat_select_style")])
    rows.append([_styled_inline(db, "⬅️ بازگشت", "back_main", "btn_buy_back_style")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def products_kb(db, category_id, products) -> InlineKeyboardMarkup:
    """کیبورد انتخاب محصول. چون فروش نامحدود است، محصول «موجود» است اگر
    دست‌کم یک فایل الگو برایش آپلود شده باشد. (category_id صرفاً برای هم‌خوانی
    با قرارداد فراخوانی نگه داشته شده و در بدنه استفاده نمی‌شود.)"""
    rows = []
    for p in products:
        if db.has_product_files(p["id"]):
            label = f"✅ {p['name']} - {p['price']:,} تومان"
        else:
            label = f"⛔️ {p['name']} - ناموجود"
        rows.append(
            [
                _styled_inline(
                    db,
                    label,
                    f"prod:{p['id']}",
                    "btn_product_select_style",
                )
            ]
        )
    rows.append([_styled_inline(db, "⬅️ بازگشت به دسته‌بندی‌ها", "back_categories", "btn_buy_back_style")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def product_confirm_kb(product_id, db=None) -> InlineKeyboardMarkup:
    """تایید خرید محصول - فروش تک‌عددی است و ردیف انتخاب تعداد ندارد.
    سازگاری با فراخوانی قدیمی به‌شکل (db, product_id): اگر آرگومان اول خودِ
    دیتابیس باشد، دو آرگومان جابه‌جا می‌شوند تا هر دو سبک فراخوانی کار کند."""
    if hasattr(product_id, "get_setting"):
        product_id, db = db, product_id

    def _btn(text: str, callback_data: str, style_key: str) -> InlineKeyboardButton:
        if db is not None:
            return _styled_inline(db, text, callback_data, style_key)
        return InlineKeyboardButton(text=text, callback_data=callback_data)

    rows = [
        [_btn("✅ ادامه و ارسال رسید", f"buy_start:{product_id}:1", "btn_buy_continue_style")],
        [_btn("🎟 وارد کردن کد تخفیف", f"enter_code:{product_id}:1", "btn_enter_code_style")],
        [_btn("⬅️ بازگشت", "back_categories", "btn_buy_back_style")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def cancel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="❌ انصراف", callback_data="cancel_flow")]]
    )


# ---------------------------------------------------------------------------
# سفارش‌های من (منوی سفارش‌ها با قابلیت دانلود مجدد فایل و حذف)
# ---------------------------------------------------------------------------

def my_orders_menu_kb(items) -> InlineKeyboardMarkup:
    """items: لیستی از دیکشنری‌های {cb_id, label} که هر کدام یک ردیف/دکمه‌ی جدا می‌شوند."""
    rows = [[InlineKeyboardButton(text=it["label"], callback_data=f"mo_v:{it['cb_id']}")] for it in items]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def my_order_item_kb(cb_id: str, deletable: bool) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text="📥 دانلود مجدد فایل", callback_data=f"mo_resend:{cb_id}")]]
    if deletable:
        rows.append([InlineKeyboardButton(text="🗑 حذف این سفارش از لیست", callback_data=f"mo_del:{cb_id}")])
    rows.append([InlineKeyboardButton(text="⬅️ بازگشت به لیست", callback_data="mo_back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def my_order_delete_confirm_kb(cb_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚠️ بله، برای همیشه حذف شود", callback_data=f"mo_delok:{cb_id}")],
        [InlineKeyboardButton(text="↩️ انصراف", callback_data=f"mo_v:{cb_id}")],
    ])


def my_orders_back_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="⬅️ بازگشت به لیست", callback_data="mo_back")]]
    )


def payment_choice_kb() -> InlineKeyboardMarkup:
    """کیبورد مرحله‌ی ارسال رسید پرداخت (فقط کارت‌به‌کارت) - دکمه‌ی انصراف."""
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="❌ انصراف", callback_data="cancel_flow")]]
    )


# ---------------------------------------------------------------------------
# سفارش برای ادمین (تایید/رد)
# ---------------------------------------------------------------------------

def order_review_kb(order_id) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(text="✅ تایید و ارسال فایل‌ها", callback_data=f"order_approve:{order_id}"),
            InlineKeyboardButton(text="❌ رد کردن", callback_data=f"order_reject:{order_id}"),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def contact_reply_kb(user_tg_id) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="↩️ پاسخ به کاربر", callback_data=f"reply_user:{user_tg_id}")]]
    )


# ---------------------------------------------------------------------------
# پنل مدیریت
# ---------------------------------------------------------------------------

# لیست دکمه‌های پنل مدیریت: (کلید تنظیمات رنگ, متن, callback_data)
ADMIN_PANEL_ITEMS = [
    ("adm_categories", "📂 مدیریت دسته‌بندی‌ها", "adm_categories"),
    ("adm_products", "📦 مدیریت محصولات", "adm_products"),
    ("adm_product_files", "📎 مدیریت فایل‌های الگو", "adm_product_files"),
    ("adm_sample_menu", "🧪 الگوی نمونه رایگان", "adm_sample_menu"),
    ("adm_forcejoin_menu", "📢 عضویت اجباری در کانال", "adm_forcejoin_menu"),
    ("adm_pending_orders", "🧾 سفارش‌های در انتظار", "adm_pending_orders"),
    ("adm_pending_topups", "👛 درخواست‌های شارژ کیف پول", "adm_pending_topups"),
    ("adm_discounts_menu", "🎟 مدیریت کدهای تخفیف", "adm_discounts_menu"),
    ("adm_wheel_settings", "🎡 مدیریت گردونه شانس", "adm_wheel_settings"),
    ("adm_referral_settings", "🤝 تنظیمات زیرمجموعه‌گیری", "adm_referral_settings"),
    ("adm_edit_buttons", "✏️ ویرایش متن دکمه‌ها", "adm_edit_buttons"),
    ("adm_main_menu_settings", "🧩 چیدمان/نمایش منوی اصلی", "adm_main_menu_settings"),
    ("adm_set_card", "💳 تنظیم شماره کارت", "adm_set_card"),
    ("adm_edit_welcome", "📝 ویرایش پیام خوش‌آمد", "adm_edit_welcome"),
    ("adm_admins_menu", "👤 مدیریت ادمین‌ها", "adm_admins_menu"),
    ("adm_broadcast", "📢 پیام همگانی", "adm_broadcast"),
    ("adm_stats", "📊 آمار فروش", "adm_stats"),
    ("adm_backup_menu", "🗄 بکاپ و بازیابی", "adm_backup_menu"),
]


def _styled_inline(db, text: str, callback_data: str, style_key: str) -> InlineKeyboardButton:
    style_value = db.get_setting(style_key, "")
    style = style_value if style_value in ("primary", "success", "danger") else None
    return InlineKeyboardButton(text=text, callback_data=callback_data, style=style)


# ---------------------------------------------------------------------------
# دسته‌بندی پنل مدیریت: هر دسته یک زیرمنوی مجزا می‌شود تا صفحه‌ی اصلی پنل
# شلوغ نباشد. ترتیب دسته‌ها بر اساس میزان استفاده‌ی روزمره‌ی ادمین چیده شده.
# ---------------------------------------------------------------------------
ADMIN_PANEL_CATEGORIES = [
    ("daily", "📋 کارهای روزانه", [
        "adm_pending_orders",
        "adm_pending_topups",
    ]),
    ("products", "📦 محصولات و فایل‌ها", [
        "adm_categories",
        "adm_products",
        "adm_product_files",
        "adm_sample_menu",
    ]),
    ("marketing", "🎯 بازاریابی و تشویقی", [
        "adm_discounts_menu",
        "adm_wheel_settings",
        "adm_referral_settings",
        "adm_broadcast",
    ]),
    ("finance", "💰 مالی و پرداخت", [
        "adm_set_card",
    ]),
    ("access", "🔐 دسترسی و امنیت", [
        "adm_forcejoin_menu",
        "adm_admins_menu",
    ]),
    ("appearance", "🎨 ظاهر و رنگ‌بندی", [
        "adm_edit_buttons",
        "adm_main_menu_settings",
        "adm_edit_welcome",
        "adm_panel_colors_menu",
        "adm_buyflow_colors_menu",
    ]),
    ("management", "👥 مدیریت و آمار", [
        "adm_stats",
        "adm_backup_menu",
    ]),
]

# دو آیتم زیر واقعی نیستند (منوی رنگ‌بندی هستند نه اکشن مستقیم) اما برای اینکه
# در دسته‌ی «ظاهر» قابل نمایش باشند، برچسب/کال‌بک‌شان اینجا تعریف می‌شود.
_EXTRA_PANEL_ITEM_LABELS = {
    "adm_panel_colors_menu": "🎨 رنگ‌آمیزی دکمه‌های پنل مدیریت",
    "adm_buyflow_colors_menu": "🎨 رنگ‌آمیزی دکمه‌های مسیر خرید",
}


def _admin_item_label_and_cb(key: str):
    if key in _EXTRA_PANEL_ITEM_LABELS:
        return _EXTRA_PANEL_ITEM_LABELS[key], key
    for item_key, label, callback_data in ADMIN_PANEL_ITEMS:
        if item_key == key:
            return label, callback_data
    return key, key


def admin_panel_kb(db) -> InlineKeyboardMarkup:
    """کیبورد سطح اول پنل مدیریت: فقط دسته‌ها نمایش داده می‌شوند."""
    rows = []
    current_row = []
    for cat_key, cat_label, item_keys in ADMIN_PANEL_CATEGORIES:
        if not item_keys:
            continue
        current_row.append(InlineKeyboardButton(text=cat_label, callback_data=f"adm_cat:{cat_key}"))
        if len(current_row) == 2:
            rows.append(current_row)
            current_row = []
    if current_row:
        rows.append(current_row)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_category_kb(db, cat_key: str) -> InlineKeyboardMarkup:
    """زیرمنوی یک دسته: آیتم‌های همان دسته با چیدمان دو ستونه + بازگشت."""
    item_keys = next((items for key, _, items in ADMIN_PANEL_CATEGORIES if key == cat_key), [])
    rows = []
    current_row = []
    for key in item_keys:
        label, callback_data = _admin_item_label_and_cb(key)
        if key in _EXTRA_PANEL_ITEM_LABELS:
            current_row.append(InlineKeyboardButton(text=label, callback_data=callback_data))
        else:
            current_row.append(_styled_inline(db, label, callback_data, f"{key}_style"))
        if len(current_row) == 2:
            rows.append(current_row)
            current_row = []
    if current_row:
        rows.append(current_row)
    rows.append([InlineKeyboardButton(text="⬅️ بازگشت به پنل مدیریت", callback_data="adm_back_panel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_category_label(cat_key: str) -> str:
    for key, label, _ in ADMIN_PANEL_CATEGORIES:
        if key == cat_key:
            return label
    return "🔧 پنل مدیریت"


def admin_backup_menu_kb() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="📥 دریافت بکاپ فوری", callback_data="adm_backup_now")],
        [InlineKeyboardButton(text="♻️ بازیابی از فایل بکاپ", callback_data="adm_restore_start")],
        [InlineKeyboardButton(text="⬅️ بازگشت", callback_data="adm_cat:management")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_restore_confirm_kb() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="✅ بله، جایگزین کن", callback_data="adm_restore_confirm")],
        [InlineKeyboardButton(text="❌ انصراف", callback_data="adm_restore_cancel")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_restore_waiting_kb() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="❌ انصراف", callback_data="adm_restore_cancel_wait")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_panel_colors_kb(db, *_legacy_args) -> InlineKeyboardMarkup:
    """رنگ‌آمیزی دکمه‌های پنل مدیریت، گروه‌بندی‌شده بر اساس همان دسته‌های پنل
    تا پیدا کردن دکمه‌ی موردنظر برای تغییر رنگ ساده‌تر باشد."""
    rows = []
    for cat_key, cat_label, item_keys in ADMIN_PANEL_CATEGORIES:
        # آیتم‌های منوی رنگ (خودشان) در این لیست معنا ندارند
        real_items = [k for k in item_keys if k not in _EXTRA_PANEL_ITEM_LABELS]
        if not real_items:
            continue
        rows.append([InlineKeyboardButton(text=f"── {cat_label} ──", callback_data="noop")])
        for key in real_items:
            label, _ = _admin_item_label_and_cb(key)
            current_style = db.get_setting(f"{key}_style", "")
            style_icon = {"primary": "🔵", "success": "🟢", "danger": "🔴", "": "⚪️"}.get(current_style, "⚪️")
            rows.append(
                [
                    InlineKeyboardButton(text=f"{style_icon} {label}", callback_data="noop"),
                    InlineKeyboardButton(text="🎨 تغییر رنگ", callback_data=f"adm_btn_color_menu:{key}"),
                ]
            )
    rows.append([InlineKeyboardButton(text="⬅️ بازگشت", callback_data="adm_cat:appearance")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


BUY_FLOW_COLOR_ITEMS = [
    ("btn_cat_select", "📁 دکمه‌های انتخاب دسته‌بندی"),
    ("btn_product_select", "📦 دکمه‌های انتخاب محصول"),
    ("btn_buy_continue", "✅ دکمه «ادامه و ارسال رسید»"),
    ("btn_enter_code", "🎟 دکمه «وارد کردن کد تخفیف»"),
    ("btn_buy_back", "⬅️ دکمه‌های بازگشت در مسیر خرید"),
]


def buy_flow_colors_kb(db) -> InlineKeyboardMarkup:
    rows = []
    for key, label in BUY_FLOW_COLOR_ITEMS:
        current_style = db.get_setting(f"{key}_style", "")
        style_icon = {"primary": "🔵", "success": "🟢", "danger": "🔴", "": "⚪️"}.get(current_style, "⚪️")
        rows.append(
            [
                InlineKeyboardButton(text=f"{style_icon} {label}", callback_data="noop"),
                InlineKeyboardButton(text="🎨 تغییر رنگ", callback_data=f"adm_btn_color_menu:{key}"),
            ]
        )
    rows.append([InlineKeyboardButton(text="⬅️ بازگشت", callback_data="adm_cat:appearance")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_stats_period_kb(active_days: int = 7) -> InlineKeyboardMarkup:
    periods = [(1, "امروز"), (7, "۷ روز اخیر"), (30, "۳۰ روز اخیر"), (90, "۹۰ روز اخیر")]
    rows = [
        [
            InlineKeyboardButton(
                text=("✅ " if d == active_days else "") + label,
                callback_data=f"adm_stats_p:{d}",
            )
            for d, label in periods[:2]
        ],
        [
            InlineKeyboardButton(
                text=("✅ " if d == active_days else "") + label,
                callback_data=f"adm_stats_p:{d}",
            )
            for d, label in periods[2:]
        ],
        [InlineKeyboardButton(text="⬅️ بازگشت به پنل مدیریت", callback_data="adm_back_panel")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_back_kb(callback_data="adm_back_panel") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="⬅️ بازگشت به پنل مدیریت", callback_data=callback_data)]]
    )


def admin_categories_kb(categories) -> InlineKeyboardMarkup:
    rows = []
    for cat in categories:
        state_icon = "🟢" if cat["is_active"] else "🔴"
        rows.append(
            [
                InlineKeyboardButton(text=f"{state_icon} {cat['name']}", callback_data="noop"),
                InlineKeyboardButton(text="تغییر وضعیت", callback_data=f"adm_cat_toggle:{cat['id']}"),
                InlineKeyboardButton(text="🗑حذف", callback_data=f"adm_cat_del:{cat['id']}"),
            ]
        )
    rows.append([InlineKeyboardButton(text="➕ افزودن دسته‌بندی جدید", callback_data="adm_cat_add")])
    rows.append([InlineKeyboardButton(text="⬅️ بازگشت", callback_data="adm_cat:products")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_products_categories_kb(categories, prefix="adm_prod_cat") -> InlineKeyboardMarkup:
    rows = []
    for cat in categories:
        rows.append([InlineKeyboardButton(text=f"📁 {cat['name']}", callback_data=f"{prefix}:{cat['id']}")])
    rows.append([InlineKeyboardButton(text="➕ افزودن محصول جدید", callback_data="adm_prod_add")])
    rows.append([InlineKeyboardButton(text="⬅️ بازگشت", callback_data="adm_cat:products")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_products_list_kb(db, products) -> InlineKeyboardMarkup:
    rows = []
    for p in products:
        state_icon = "🟢" if p["is_active"] else "🔴"
        files_txt = "✅ فایل آماده" if db.has_product_files(p["id"]) else "⛔️ بدون فایل"
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{state_icon} {p['name']} | {p['price']:,}ت | {files_txt}",
                    callback_data="noop",
                )
            ]
        )
        rows.append(
            [
                InlineKeyboardButton(text="تغییر وضعیت", callback_data=f"adm_prod_toggle:{p['id']}"),
                InlineKeyboardButton(text="🗑حذف", callback_data=f"adm_prod_del:{p['id']}"),
            ]
        )
    rows.append([InlineKeyboardButton(text="⬅️ بازگشت", callback_data="adm_products")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_pick_category_kb(categories, prefix) -> InlineKeyboardMarkup:
    rows = []
    for cat in categories:
        rows.append([InlineKeyboardButton(text=f"📁 {cat['name']}", callback_data=f"{prefix}:{cat['id']}")])
    rows.append([InlineKeyboardButton(text="⬅️ بازگشت", callback_data="adm_cat:products")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_pick_product_kb(products, prefix) -> InlineKeyboardMarkup:
    rows = []
    for p in products:
        rows.append([InlineKeyboardButton(text=f"📦 {p['name']}", callback_data=f"{prefix}:{p['id']}")])
    rows.append([InlineKeyboardButton(text="⬅️ بازگشت", callback_data="adm_cat:products")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _file_record_id(f, idx: int) -> str:
    """شناسه‌ی یکتای رکورد فایل برای قرارگرفتن در callback_data.
    چون file_id تلگرام معمولا از سقف ۶۴ بایتی callback_data بلندتر است، از
    شناسه‌ی عددی رکورد (id) استفاده می‌کنیم؛ اگر دیتابیس فقط رشته‌ی file_id
    برگرداند، همان رشته به‌کار می‌رود."""
    if isinstance(f, str):
        return f
    try:
        return str(f["id"])
    except (KeyError, IndexError, TypeError):
        try:
            return str(f["file_id"])
        except (KeyError, IndexError, TypeError):
            return str(idx)


def sample_menu_kb(db) -> InlineKeyboardMarkup:
    """منوی مدیریت «الگوی نمونه رایگان» (جایگزین منوی تست قدیمی)."""
    rows = [
        [InlineKeyboardButton(text="➕ آپلود الگوی نمونه", callback_data="adm_sample_add")],
    ]
    samples = db.get_sample_files()
    for idx, f in enumerate(samples, start=1):
        rows.append(
            [
                InlineKeyboardButton(text=f"📎 نمونه {idx}", callback_data="noop"),
                InlineKeyboardButton(text="🗑", callback_data=f"adm_sample_del:{_file_record_id(f, idx)}"),
            ]
        )
    rows.append([InlineKeyboardButton(text="♻️ ریست استفاده کاربر", callback_data="adm_sample_reset")])
    rows.append([InlineKeyboardButton(text="⬅️ بازگشت", callback_data="adm_cat:products")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def product_files_pick_kb(products) -> InlineKeyboardMarkup:
    """انتخاب محصول برای مدیریت فایل‌های الگو (منوی adm_product_files)."""
    rows = []
    for p in products:
        rows.append([InlineKeyboardButton(text=f"📦 {p['name']}", callback_data=f"adm_file_pick:{p['id']}")])
    rows.append([InlineKeyboardButton(text="⬅️ بازگشت", callback_data="adm_product_files")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def product_files_kb(db, product_id) -> InlineKeyboardMarkup:
    """مدیریت فایل‌های الگوی یک محصول (جایگزین منوی افزودن فایل به محصول)."""
    rows = []
    files = db.get_product_files(product_id)
    for idx, f in enumerate(files, start=1):
        rows.append(
            [
                InlineKeyboardButton(text=f"📎 فایل {idx}", callback_data="noop"),
                InlineKeyboardButton(
                    text="🗑",
                    callback_data=f"adm_file_del:{_file_record_id(f, idx)}:{product_id}",
                ),
            ]
        )
    rows.append([InlineKeyboardButton(text="➕ افزودن فایل", callback_data=f"adm_file_add:{product_id}")])
    rows.append([InlineKeyboardButton(text="🖼 تنظیم عکس پیش‌نمایش", callback_data=f"adm_preview_set:{product_id}")])
    rows.append([InlineKeyboardButton(text="⬅️ بازگشت به محصول", callback_data=f"adm_prod_view:{product_id}")])
    rows.append([InlineKeyboardButton(text="⬅️ بازگشت", callback_data="adm_product_files")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def files_upload_done_kb() -> InlineKeyboardMarkup:
    """دکمه‌ی پایان آپلود چندتایی فایل در FSM (هم برای ساخت محصول جدید و هم
    برای «مدیریت فایل‌های الگو»)، چون کاربر ممکن است چند فایل پشت‌سرهم بفرستد."""
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="✅ تمام شد", callback_data="adm_files_done")]]
    )


def admin_forcejoin_menu_kb(db) -> InlineKeyboardMarkup:
    settings = db.get_force_join_settings()
    toggle_text = "🔴 غیرفعال کردن عضویت اجباری" if settings["enabled"] else "🟢 فعال کردن عضویت اجباری"
    channel_text = f"کانال فعلی: {settings['channel']}" if settings["channel"] else "کانالی ثبت نشده است"
    rows = [
        [InlineKeyboardButton(text=channel_text, callback_data="noop")],
        [InlineKeyboardButton(text="✏️ تنظیم / تغییر کانال", callback_data="adm_forcejoin_set_channel")],
        [InlineKeyboardButton(text=toggle_text, callback_data="adm_forcejoin_toggle")],
        [InlineKeyboardButton(text="⬅️ بازگشت", callback_data="adm_cat:access")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


BUTTON_LABELS = {
    "btn_buy": "دکمه خرید الگو",
    "btn_test": "دکمه الگوی نمونه رایگان",
    "btn_contact": "دکمه ارتباط با پشتیبانی",
    "btn_my_orders": "دکمه سفارش‌های من",
    "btn_referral": "دکمه زیرمجموعه‌گیری",
    "btn_wallet": "دکمه کیف پول",
    "btn_wheel": "دکمه گردونه شانس",
    "btn_admin_panel": "دکمه پنل مدیریت",
}


def admin_edit_buttons_kb(db) -> InlineKeyboardMarkup:
    rows = []
    for key, label in BUTTON_LABELS.items():
        current_style = db.get_setting(f"{key}_style", "")
        style_icon = {"primary": "🔵", "success": "🟢", "danger": "🔴", "": "⚪️"}.get(current_style, "⚪️")
        row = [
            InlineKeyboardButton(text=f"✏️ {style_icon} {label}", callback_data=f"adm_btn_edit:{key}"),
            InlineKeyboardButton(text="🎨 تغییر رنگ", callback_data=f"adm_btn_color_menu:{key}"),
        ]
        toggle_key = MENU_BUTTON_META.get(key, {}).get("toggle_key")
        if toggle_key:
            enabled = db.get_setting(toggle_key, "1") == "1"
            row.append(
                InlineKeyboardButton(
                    text="🟢 فعال" if enabled else "🔴 غیرفعال",
                    callback_data=f"adm_btn_toggle:{key}",
                )
            )
        rows.append(row)
    rows.append([InlineKeyboardButton(text="⬅️ بازگشت", callback_data="adm_cat:appearance")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def main_menu_settings_kb(db) -> InlineKeyboardMarkup:
    """تنظیمات نمایش منوی اصلی: فعال/غیرفعال کردن جداگانه‌ی منوی پایین (Reply)
    و منوی شیشه‌ای بالا (Inline)، و تعداد ستون هر دو منو (۱ یا ۲ دکمه در هر ردیف)."""
    reply_on = db.get_setting("main_menu_reply_enabled", "1") == "1"
    inline_on = db.get_setting("main_menu_inline_enabled", "0") == "1"
    columns = _menu_columns(db)

    reply_toggle = "🔴 غیرفعال کردن منوی پایین" if reply_on else "🟢 فعال کردن منوی پایین"
    inline_toggle = "🔴 غیرفعال کردن منوی شیشه‌ای بالا" if inline_on else "🟢 فعال کردن منوی شیشه‌ای بالا"
    col_toggle = "↔️ چیدمان: ۲ دکمه در هر ردیف" if columns == 1 else "↕️ چیدمان: ۱ دکمه در هر ردیف"

    rows = [
        [InlineKeyboardButton(text=f"منوی پایین (Reply): {'🟢 فعال' if reply_on else '🔴 غیرفعال'}", callback_data="noop")],
        [InlineKeyboardButton(text=reply_toggle, callback_data="adm_mm_toggle_reply")],
        [InlineKeyboardButton(text=f"منوی شیشه‌ای بالا (Inline): {'🟢 فعال' if inline_on else '🔴 غیرفعال'}", callback_data="noop")],
        [InlineKeyboardButton(text=inline_toggle, callback_data="adm_mm_toggle_inline")],
        [InlineKeyboardButton(text=f"چیدمان فعلی: {columns} دکمه در هر ردیف", callback_data="noop")],
        [InlineKeyboardButton(text=col_toggle, callback_data="adm_mm_toggle_columns")],
        [InlineKeyboardButton(text="⬅️ بازگشت", callback_data="adm_cat:appearance")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_color_picker_kb(key: str, back_callback: str = "adm_edit_buttons") -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="🔵 آبی (Primary)", callback_data=f"adm_btn_color_set:{key}:primary")],
        [InlineKeyboardButton(text="🟢 سبز (Success)", callback_data=f"adm_btn_color_set:{key}:success")],
        [InlineKeyboardButton(text="🔴 قرمز (Danger)", callback_data=f"adm_btn_color_set:{key}:danger")],
        [InlineKeyboardButton(text="⚪️ پیش‌فرض (خاکستری)", callback_data=f"adm_btn_color_set:{key}:none")],
        [InlineKeyboardButton(text="⬅️ بازگشت", callback_data=back_callback)],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_admins_menu_kb() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="📃 لیست ادمین‌ها و نقش‌ها", callback_data="adm_admins_list")],
        [InlineKeyboardButton(text="➕ افزودن ادمین", callback_data="adm_admin_add")],
        [InlineKeyboardButton(text="🔄 تغییر نقش ادمین", callback_data="adm_admin_role_change")],
        [InlineKeyboardButton(text="➖ حذف ادمین", callback_data="adm_admin_remove")],
        [InlineKeyboardButton(text="⬅️ بازگشت", callback_data="adm_cat:management")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


ADMIN_ROLE_LABELS = {"owner": "👑 مالک", "admin": "🛡 مدیر کامل", "mid": "🥈 ادمین میانی", "support": "🎧 پشتیبان"}


def admin_role_pick_kb(target_tg_id: int, action: str) -> InlineKeyboardMarkup:
    """action: 'add' یا 'setrole' - پیشوند callback_data برای تمایز دو مسیر."""
    prefix = "adm_add_admin_role" if action == "add" else "adm_change_role_set"
    rows = [
        [InlineKeyboardButton(text="🛡 مدیر کامل (دسترسی کامل)", callback_data=f"{prefix}:{target_tg_id}:admin")],
        [InlineKeyboardButton(text="🥈 ادمین میانی (بدون آمار و فروش)", callback_data=f"{prefix}:{target_tg_id}:mid")],
        [InlineKeyboardButton(text="🎧 پشتیبان (فقط تیکت و سفارش)", callback_data=f"{prefix}:{target_tg_id}:support")],
        [InlineKeyboardButton(text="⬅️ انصراف", callback_data="adm_admins_menu")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def pending_orders_kb(orders) -> InlineKeyboardMarkup:
    rows = []
    for o in orders:
        rows.append(
            [InlineKeyboardButton(text=f"سفارش #{o['id']} - کاربر {o['user_id']}", callback_data=f"view_order:{o['id']}")]
        )
    rows.append([InlineKeyboardButton(text="⬅️ بازگشت", callback_data="adm_cat:daily")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def pending_topups_kb(topups) -> InlineKeyboardMarkup:
    rows = []
    for t in topups:
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"شارژ #{t['id']} - کاربر {t['user_id']} - {t['amount']:,} تومان",
                    callback_data=f"view_topup:{t['id']}",
                )
            ]
        )
    rows.append([InlineKeyboardButton(text="⬅️ بازگشت", callback_data="adm_cat:daily")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ---------------------------------------------------------------------------
# مدیریت کدهای تخفیف
# ---------------------------------------------------------------------------

def discount_codes_kb(codes) -> InlineKeyboardMarkup:
    rows = []
    for c in codes:
        state_icon = "🟢" if c["is_active"] else "🔴"
        if c["percent"]:
            value_txt = f"{c['percent']}%"
        else:
            value_txt = f"{c['fixed_amount']:,}ت"
        usage_txt = f"{c['used_count']}/{c['max_uses'] if c['max_uses'] else '∞'}"
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{state_icon} {c['code']} | {value_txt} | استفاده: {usage_txt}", callback_data="noop"
                )
            ]
        )
        rows.append(
            [
                InlineKeyboardButton(text="تغییر وضعیت", callback_data=f"adm_disc_toggle:{c['id']}"),
                InlineKeyboardButton(text="🗑حذف", callback_data=f"adm_disc_del:{c['id']}"),
            ]
        )
    rows.append([InlineKeyboardButton(text="➕ ساخت کد تخفیف جدید", callback_data="adm_disc_add")])
    rows.append([InlineKeyboardButton(text="⬅️ بازگشت", callback_data="adm_cat:marketing")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ---------------------------------------------------------------------------
# تنظیمات زیرمجموعه‌گیری
# ---------------------------------------------------------------------------

def referral_settings_kb(db) -> InlineKeyboardMarkup:
    # --- حالت ۱: پورسانت درصدی از اولین خرید هر زیرمجموعه ---
    enabled = db.get_setting("referral_enabled", "1") == "1"
    toggle_text = "🔴 غیرفعال کردن پورسانت خرید" if enabled else "🟢 فعال کردن پورسانت خرید"
    percent = db.get_setting("referral_percent", "10")
    commission_max = int(db.get_setting("referral_commission_max_count", "0") or 0)
    commission_max_text = f"{commission_max} نفر" if commission_max > 0 else "نامحدود"

    # --- حالت ۲: محصول رایگان با رسیدن به تعداد دعوت مشخص ---
    fc_enabled = db.get_setting("referral_free_config_enabled", "0") == "1"
    fc_toggle_text = "🔴 غیرفعال کردن الگوی رایگان" if fc_enabled else "🟢 فعال کردن الگوی رایگان"
    fc_threshold = db.get_setting("referral_free_config_threshold", "10")
    fc_product_id = db.get_setting("referral_free_config_product_id", "") or ""
    fc_product_name = "تنظیم نشده"
    if fc_product_id:
        p = db.get_product(int(fc_product_id))
        fc_product_name = p["name"] if p else "محصول حذف‌شده - دوباره انتخاب کنید"

    # --- حالت ۳: شارژ ثابت کیف پول به‌ازای هر دعوت ---
    ib_enabled = db.get_setting("referral_invite_bonus_enabled", "0") == "1"
    ib_toggle_text = "🔴 غیرفعال کردن شارژ به‌ازای دعوت" if ib_enabled else "🟢 فعال کردن شارژ به‌ازای دعوت"
    ib_amount = db.get_setting("referral_invite_bonus_amount", "0")
    ib_max = int(db.get_setting("referral_invite_bonus_max_count", "0") or 0)
    ib_max_text = f"{ib_max} نفر" if ib_max > 0 else "نامحدود"

    rows = [
        [InlineKeyboardButton(text="① پورسانت درصدی از خرید زیرمجموعه", callback_data="noop")],
        [InlineKeyboardButton(text=f"درصد پورسانت: {percent}% | سقف: {commission_max_text}", callback_data="noop")],
        [InlineKeyboardButton(text=toggle_text, callback_data="adm_referral_toggle")],
        [InlineKeyboardButton(text="✏️ تغییر درصد پورسانت", callback_data="adm_referral_percent_edit")],
        [InlineKeyboardButton(text="✏️ تغییر سقف تعداد نفرات (۰=نامحدود)", callback_data="adm_referral_commission_max_edit")],

        [InlineKeyboardButton(text="② الگوی رایگان با تعداد دعوت مشخص", callback_data="noop")],
        [InlineKeyboardButton(text=f"آستانه: {fc_threshold} نفر | محصول: {fc_product_name}", callback_data="noop")],
        [InlineKeyboardButton(text=fc_toggle_text, callback_data="adm_referral_freeconfig_toggle")],
        [InlineKeyboardButton(text="✏️ تغییر تعداد دعوت لازم", callback_data="adm_referral_freeconfig_threshold_edit")],
        [InlineKeyboardButton(text="📦 انتخاب محصول جایزه", callback_data="adm_referral_freeconfig_product")],

        [InlineKeyboardButton(text="③ شارژ ثابت کیف پول به‌ازای هر دعوت", callback_data="noop")],
        [InlineKeyboardButton(text=f"مبلغ: {ib_amount} تومان | سقف: {ib_max_text}", callback_data="noop")],
        [InlineKeyboardButton(text=ib_toggle_text, callback_data="adm_referral_invitebonus_toggle")],
        [InlineKeyboardButton(text="✏️ تغییر مبلغ شارژ", callback_data="adm_referral_invitebonus_amount_edit")],
        [InlineKeyboardButton(text="✏️ تغییر سقف تعداد نفرات (۰=نامحدود)", callback_data="adm_referral_invitebonus_max_edit")],

        [InlineKeyboardButton(text="⬅️ بازگشت", callback_data="adm_cat:marketing")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def referral_freeconfig_product_kb(db) -> InlineKeyboardMarkup:
    products = db.get_all_products()
    rows = []
    for p in products:
        rows.append([InlineKeyboardButton(
            text=f"{p['name']} ({p['category_name']})", callback_data=f"adm_referral_freeconfig_setprod:{p['id']}"
        )])
    rows.append([InlineKeyboardButton(text="⬅️ بازگشت", callback_data="adm_referral_settings")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ---------------------------------------------------------------------------
# گردونه شانس
# ---------------------------------------------------------------------------

def wheel_settings_kb(db) -> InlineKeyboardMarkup:
    s = db.get_wheel_settings()
    toggle_text = "🔴 غیرفعال کردن گردونه" if s["enabled"] else "🟢 فعال کردن گردونه"
    prizes_txt = "، ".join(f"{p}%" for p in s["prizes"]) or "---"
    rows = [
        [InlineKeyboardButton(text=f"احتمال برد: {s['win_percent']}%", callback_data="noop")],
        [InlineKeyboardButton(text=f"جوایز ممکن: {prizes_txt}", callback_data="noop")],
        [InlineKeyboardButton(text=f"اعتبار کد جایزه: {s['expiry_hours']} ساعت", callback_data="noop")],
        [InlineKeyboardButton(text=f"فاصله بین دو چرخش: {s['cooldown_hours']} ساعت", callback_data="noop")],
        [InlineKeyboardButton(text=toggle_text, callback_data="adm_wheel_toggle")],
        [InlineKeyboardButton(text="✏️ تغییر درصد برد", callback_data="adm_wheel_edit_percent")],
        [InlineKeyboardButton(text="✏️ تغییر لیست جوایز", callback_data="adm_wheel_edit_prizes")],
        [InlineKeyboardButton(text="✏️ تغییر اعتبار کد", callback_data="adm_wheel_edit_expiry")],
        [InlineKeyboardButton(text="✏️ تغییر فاصله چرخش", callback_data="adm_wheel_edit_cooldown")],
        [InlineKeyboardButton(text="⬅️ بازگشت", callback_data="adm_cat:marketing")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ---------------------------------------------------------------------------
# کیف پول
# ---------------------------------------------------------------------------

def wallet_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="➕ شارژ کیف پول", callback_data="start_topup")]]
    )


def topup_review_kb(topup_id) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(text="✅ تایید و شارژ کیف پول", callback_data=f"topup_approve:{topup_id}"),
            InlineKeyboardButton(text="❌ رد کردن", callback_data=f"topup_reject:{topup_id}"),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)
