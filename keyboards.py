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


def main_menu_kb(is_admin: bool) -> ReplyKeyboardMarkup:
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
        [_styled_button(settings.get("btn_contact", "📞 ارتباط با پشتیبانی"), settings.get("btn_contact_style", ""))]
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
        [InlineKeyboardButton(text="✅ خرید و ارسال رسید", callback_data=f"buy_confirm:{product_id}")],
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

def admin_panel_kb() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="📂 مدیریت دسته‌بندی‌ها", callback_data="adm_categories")],
        [InlineKeyboardButton(text="📦 مدیریت محصولات", callback_data="adm_products")],
        [InlineKeyboardButton(text="🔗 افزودن کانفیگ به محصول", callback_data="adm_add_configs")],
        [InlineKeyboardButton(text="🧪 مدیریت کانفیگ تست", callback_data="adm_test_menu")],
        [InlineKeyboardButton(text="🧾 سفارش‌های در انتظار", callback_data="adm_pending_orders")],
        [InlineKeyboardButton(text="✏️ ویرایش متن دکمه‌ها", callback_data="adm_edit_buttons")],
        [InlineKeyboardButton(text="💳 تنظیم شماره کارت", callback_data="adm_set_card")],
        [InlineKeyboardButton(text="📝 ویرایش پیام خوش‌آمد", callback_data="adm_edit_welcome")],
        [InlineKeyboardButton(text="👤 مدیریت ادمین‌ها", callback_data="adm_admins_menu")],
        [InlineKeyboardButton(text="📢 پیام همگانی", callback_data="adm_broadcast")],
        [InlineKeyboardButton(text="📊 آمار فروش", callback_data="adm_stats")],
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
