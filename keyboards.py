# -*- coding: utf-8 -*-
"""
ساخت کیبوردهای شیشه‌ای و معمولی بات
"""

from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

import database as db


# ---------------------------------------------------------------------------
# منوی اصلی (Reply Keyboard) - متن دکمه‌ها از تنظیمات خوانده می‌شود
# ---------------------------------------------------------------------------

def _styled_button(text: str, style_value: str) -> KeyboardButton:
    """می‌سازد یک دکمه با رنگ دلخواه (ویژگی style در Bot API 9.4 به بعد).
    مقدار خالی یعنی رنگ پیش‌فرض (خاکستری)."""
    style = style_value if style_value in ("primary", "success", "danger") else None
    return KeyboardButton(text=text, style=style)


def main_menu_kb(is_admin: bool, is_reseller: bool = False) -> ReplyKeyboardMarkup:
    settings = db.get_all_settings()
    rows = [
        [_styled_button(settings.get("btn_buy", "🛒 خرید کانفیگ"), settings.get("btn_buy_style", ""))],
    ]
    if settings.get("test_enabled", "1") == "1":
        rows.append(
            [_styled_button(settings.get("btn_test", "🧪 کانفیگ تست رایگان"), settings.get("btn_test_style", ""))]
        )
    rows.append(
        [_styled_button(settings.get("btn_my_orders", "📦 سفارش‌های من"), settings.get("btn_my_orders_style", ""))]
    )
    rows.append(
        [_styled_button(settings.get("btn_wallet", "👛 کیف پول من"), settings.get("btn_wallet_style", ""))]
    )
    if settings.get("referral_enabled", "1") == "1":
        rows.append(
            [
                _styled_button(
                    settings.get("btn_referral", "🤝 زیرمجموعه‌گیری من"), settings.get("btn_referral_style", "")
                )
            ]
        )
    rows.append(
        [_styled_button(settings.get("btn_contact", "📞 ارتباط با پشتیبانی"), settings.get("btn_contact_style", ""))]
    )
    if is_reseller and not is_admin:
        rows.append(
            [
                _styled_button(
                    settings.get("btn_reseller_panel", "🏪 پنل نمایندگی"), settings.get("btn_reseller_panel_style", "")
                )
            ]
        )
    if is_admin:
        rows.append(
            [
                _styled_button(
                    settings.get("btn_admin_panel", "⚙️ پنل مدیریت"), settings.get("btn_admin_panel_style", "")
                )
            ]
        )
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def menu_for_user(user_tg_id: int) -> ReplyKeyboardMarkup:
    """کیبورد اصلی متناسب با نقش کاربر (عادی/نماینده/ادمین) را می‌سازد."""
    return main_menu_kb(db.is_admin(user_tg_id), db.is_reseller(user_tg_id))


# ---------------------------------------------------------------------------
# دسته‌بندی‌ها / محصولات (کاربر)
# ---------------------------------------------------------------------------

def categories_kb(categories) -> InlineKeyboardMarkup:
    rows = []
    for cat in categories:
        rows.append([InlineKeyboardButton(text=f"📁 {cat['name']}", callback_data=f"cat:{cat['id']}")])
    rows.append([InlineKeyboardButton(text="⬅️ بازگشت", callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def products_kb(products, category_id) -> InlineKeyboardMarkup:
    rows = []
    for p in products:
        stock = db.count_available_configs(p["id"])
        stock_tag = "✅" if stock > 0 else "⛔️"
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{stock_tag} {p['name']} - {p['price']:,} تومان",
                    callback_data=f"prod:{p['id']}",
                )
            ]
        )
    rows.append([InlineKeyboardButton(text="⬅️ بازگشت به دسته‌بندی‌ها", callback_data="back_categories")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def product_confirm_kb(product_id) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="✅ ادامه و ارسال رسید", callback_data=f"buy_start:{product_id}")],
        [InlineKeyboardButton(text="🎟 وارد کردن کد تخفیف", callback_data=f"enter_code:{product_id}")],
        [InlineKeyboardButton(text="⬅️ بازگشت", callback_data="back_categories")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def cancel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="❌ انصراف", callback_data="cancel_flow")]]
    )


# ---------------------------------------------------------------------------
# سفارش برای ادمین (تایید/رد)
# ---------------------------------------------------------------------------

def order_review_kb(order_id) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(text="✅ تایید و ارسال کانفیگ", callback_data=f"order_approve:{order_id}"),
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
# کلید رنگ هر دکمه در تنظیمات به شکل "{کلید}_style" ذخیره می‌شود
ADMIN_PANEL_ITEMS = [
    ("adm_categories", "📂 مدیریت دسته‌بندی‌ها", "adm_categories"),
    ("adm_products", "📦 مدیریت محصولات", "adm_products"),
    ("adm_add_configs", "🔗 افزودن کانفیگ به محصول", "adm_add_configs"),
    ("adm_test_menu", "🧪 مدیریت کانفیگ تست", "adm_test_menu"),
    ("adm_pending_orders", "🧾 سفارش‌های در انتظار", "adm_pending_orders"),
    ("adm_pending_topups", "👛 درخواست‌های شارژ کیف پول", "adm_pending_topups"),
    ("adm_discounts_menu", "🎟 مدیریت کدهای تخفیف", "adm_discounts_menu"),
    ("adm_referral_settings", "🤝 تنظیمات زیرمجموعه‌گیری", "adm_referral_settings"),
    ("adm_resellers_menu", "🏪 مدیریت نمایندگان", "adm_resellers_menu"),
    ("adm_edit_buttons", "✏️ ویرایش متن دکمه‌ها", "adm_edit_buttons"),
    ("adm_set_card", "💳 تنظیم شماره کارت", "adm_set_card"),
    ("adm_edit_welcome", "📝 ویرایش پیام خوش‌آمد", "adm_edit_welcome"),
    ("adm_admins_menu", "👤 مدیریت ادمین‌ها", "adm_admins_menu"),
    ("adm_broadcast", "📢 پیام همگانی", "adm_broadcast"),
    ("adm_stats", "📊 آمار فروش", "adm_stats"),
]


def _styled_inline(text: str, callback_data: str, style_key: str) -> InlineKeyboardButton:
    style_value = db.get_setting(style_key, "")
    style = style_value if style_value in ("primary", "success", "danger") else None
    return InlineKeyboardButton(text=text, callback_data=callback_data, style=style)


def admin_panel_kb() -> InlineKeyboardMarkup:
    rows = []
    for key, label, callback_data in ADMIN_PANEL_ITEMS:
        rows.append([_styled_inline(label, callback_data, f"{key}_style")])
    rows.append([InlineKeyboardButton(text="🎨 رنگ‌آمیزی دکمه‌های پنل", callback_data="adm_panel_colors_menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_panel_colors_kb() -> InlineKeyboardMarkup:
    rows = []
    for key, label, _ in ADMIN_PANEL_ITEMS:
        current_style = db.get_setting(f"{key}_style", "")
        style_icon = {"primary": "🔵", "success": "🟢", "danger": "🔴", "": "⚪️"}.get(current_style, "⚪️")
        rows.append(
            [
                InlineKeyboardButton(text=f"{style_icon} {label}", callback_data="noop"),
                InlineKeyboardButton(text="🎨 تغییر رنگ", callback_data=f"adm_btn_color_menu:{key}"),
            ]
        )
    rows.append([InlineKeyboardButton(text="⬅️ بازگشت", callback_data="adm_back_panel")])
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
                InlineKeyboardButton(text=f"{state_icon} {cat['name']}", callback_data=f"noop"),
                InlineKeyboardButton(text="تغییر وضعیت", callback_data=f"adm_cat_toggle:{cat['id']}"),
                InlineKeyboardButton(text="🗑حذف", callback_data=f"adm_cat_del:{cat['id']}"),
            ]
        )
    rows.append([InlineKeyboardButton(text="➕ افزودن دسته‌بندی جدید", callback_data="adm_cat_add")])
    rows.append([InlineKeyboardButton(text="⬅️ بازگشت", callback_data="adm_back_panel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_products_categories_kb(categories, prefix="adm_prod_cat") -> InlineKeyboardMarkup:
    rows = []
    for cat in categories:
        rows.append([InlineKeyboardButton(text=f"📁 {cat['name']}", callback_data=f"{prefix}:{cat['id']}")])
    rows.append([InlineKeyboardButton(text="➕ افزودن محصول جدید", callback_data="adm_prod_add")])
    rows.append([InlineKeyboardButton(text="⬅️ بازگشت", callback_data="adm_back_panel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_products_list_kb(products) -> InlineKeyboardMarkup:
    rows = []
    for p in products:
        stock = db.count_available_configs(p["id"])
        state_icon = "🟢" if p["is_active"] else "🔴"
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{state_icon} {p['name']} | {p['price']:,}ت | موجودی: {stock}",
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
    rows.append([InlineKeyboardButton(text="⬅️ بازگشت", callback_data="adm_back_panel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_pick_product_kb(products, prefix) -> InlineKeyboardMarkup:
    rows = []
    for p in products:
        rows.append([InlineKeyboardButton(text=f"📦 {p['name']}", callback_data=f"{prefix}:{p['id']}")])
    rows.append([InlineKeyboardButton(text="⬅️ بازگشت", callback_data="adm_back_panel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_test_menu_kb() -> InlineKeyboardMarkup:
    enabled = db.get_setting("test_enabled", "1") == "1"
    toggle_text = "🔴 غیرفعال کردن کانفیگ تست" if enabled else "🟢 فعال کردن کانفیگ تست"
    remaining = db.count_available_test_configs()
    rows = [
        [InlineKeyboardButton(text=f"موجودی فعلی: {remaining} عدد", callback_data="noop")],
        [InlineKeyboardButton(text=toggle_text, callback_data="adm_test_toggle")],
        [InlineKeyboardButton(text="➕ افزودن لینک تست", callback_data="adm_test_add")],
        [InlineKeyboardButton(text="⬅️ بازگشت", callback_data="adm_back_panel")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


BUTTON_LABELS = {
    "btn_buy": "دکمه خرید کانفیگ",
    "btn_test": "دکمه کانفیگ تست",
    "btn_contact": "دکمه ارتباط با پشتیبانی",
    "btn_my_orders": "دکمه سفارش‌های من",
    "btn_referral": "دکمه زیرمجموعه‌گیری",
    "btn_wallet": "دکمه کیف پول",
    "btn_reseller_panel": "دکمه پنل نمایندگی",
    "btn_admin_panel": "دکمه پنل مدیریت",
}


def admin_edit_buttons_kb() -> InlineKeyboardMarkup:
    rows = []
    for key, label in BUTTON_LABELS.items():
        current_style = db.get_setting(f"{key}_style", "")
        style_name = {"primary": "🔵", "success": "🟢", "danger": "🔴", "": "⚪️"}.get(current_style, "⚪️")
        rows.append(
            [
                InlineKeyboardButton(text=f"{style_name} {label}", callback_data="noop"),
            ]
        )
        rows.append(
            [
                InlineKeyboardButton(text="✏️ ویرایش متن", callback_data=f"adm_btn_edit:{key}"),
                InlineKeyboardButton(text="🎨 تغییر رنگ", callback_data=f"adm_btn_color_menu:{key}"),
            ]
        )
    rows.append([InlineKeyboardButton(text="⬅️ بازگشت", callback_data="adm_back_panel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_color_picker_kb(key: str) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="🔵 آبی (Primary)", callback_data=f"adm_btn_color_set:{key}:primary")],
        [InlineKeyboardButton(text="🟢 سبز (Success)", callback_data=f"adm_btn_color_set:{key}:success")],
        [InlineKeyboardButton(text="🔴 قرمز (Danger)", callback_data=f"adm_btn_color_set:{key}:danger")],
        [InlineKeyboardButton(text="⚪️ پیش‌فرض (خاکستری)", callback_data=f"adm_btn_color_set:{key}:none")],
        [InlineKeyboardButton(text="⬅️ بازگشت", callback_data="adm_edit_buttons")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_admins_menu_kb() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="📃 لیست ادمین‌ها", callback_data="adm_admins_list")],
        [InlineKeyboardButton(text="➕ افزودن ادمین", callback_data="adm_admin_add")],
        [InlineKeyboardButton(text="➖ حذف ادمین", callback_data="adm_admin_remove")],
        [InlineKeyboardButton(text="⬅️ بازگشت", callback_data="adm_back_panel")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def pending_orders_kb(orders) -> InlineKeyboardMarkup:
    rows = []
    for o in orders:
        rows.append(
            [InlineKeyboardButton(text=f"سفارش #{o['id']} - کاربر {o['user_id']}", callback_data=f"view_order:{o['id']}")]
        )
    rows.append([InlineKeyboardButton(text="⬅️ بازگشت", callback_data="adm_back_panel")])
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
    rows.append([InlineKeyboardButton(text="⬅️ بازگشت", callback_data="adm_back_panel")])
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
    rows.append([InlineKeyboardButton(text="⬅️ بازگشت", callback_data="adm_back_panel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ---------------------------------------------------------------------------
# تنظیمات زیرمجموعه‌گیری
# ---------------------------------------------------------------------------

def referral_settings_kb() -> InlineKeyboardMarkup:
    enabled = db.get_setting("referral_enabled", "1") == "1"
    toggle_text = "🔴 غیرفعال کردن زیرمجموعه‌گیری" if enabled else "🟢 فعال کردن زیرمجموعه‌گیری"
    percent = db.get_setting("referral_percent", "10")
    rows = [
        [InlineKeyboardButton(text=f"درصد پورسانت فعلی: {percent}%", callback_data="noop")],
        [InlineKeyboardButton(text=toggle_text, callback_data="adm_referral_toggle")],
        [InlineKeyboardButton(text="✏️ تغییر درصد پورسانت", callback_data="adm_referral_percent_edit")],
        [InlineKeyboardButton(text="⬅️ بازگشت", callback_data="adm_back_panel")],
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


# ---------------------------------------------------------------------------
# پنل نمایندگی (برای خود نماینده - نسخه‌ی کوچک‌شده‌ی پنل مدیریت)
# ---------------------------------------------------------------------------

def reseller_panel_kb() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="📂 دسته‌بندی‌های من", callback_data="adm_categories")],
        [InlineKeyboardButton(text="📦 محصولات من", callback_data="adm_products")],
        [InlineKeyboardButton(text="🔗 افزودن کانفیگ به محصول", callback_data="adm_add_configs")],
        [InlineKeyboardButton(text="🧾 سفارش‌های در انتظار من", callback_data="adm_pending_orders")],
        [InlineKeyboardButton(text="💳 تنظیم شماره کارت من", callback_data="adm_set_card")],
        [InlineKeyboardButton(text="📊 آمار فروش من", callback_data="adm_stats")],
        [InlineKeyboardButton(text="🔗 لینک فروشگاه من", callback_data="reseller_get_link")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ---------------------------------------------------------------------------
# مدیریت نمایندگان (فقط مالک بات)
# ---------------------------------------------------------------------------

def resellers_kb(resellers) -> InlineKeyboardMarkup:
    rows = []
    for r in resellers:
        state_icon = "🟢" if r["is_active"] else "🔴"
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{state_icon} {r['name'] or r['telegram_id']} ({r['telegram_id']})",
                    callback_data="noop",
                )
            ]
        )
        rows.append(
            [
                InlineKeyboardButton(text="تغییر وضعیت", callback_data=f"adm_reseller_toggle:{r['telegram_id']}"),
                InlineKeyboardButton(text="🗑حذف", callback_data=f"adm_reseller_del:{r['telegram_id']}"),
                InlineKeyboardButton(text="🔗 لینک", callback_data=f"adm_reseller_link:{r['telegram_id']}"),
            ]
        )
    rows.append([InlineKeyboardButton(text="➕ افزودن نماینده جدید", callback_data="adm_reseller_add")])
    rows.append([InlineKeyboardButton(text="⬅️ بازگشت", callback_data="adm_back_panel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
