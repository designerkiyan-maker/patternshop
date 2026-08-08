# -*- coding: utf-8 -*-
"""
ساخت کیبوردهای شیشه‌ای و معمولی بات

نکته مهم: چون هر بات (اصلی یا نمایندگی) دیتابیس مستقل خودش را دارد، تمام
توابعی که به تنظیمات/داده نیاز دارند، شیء db (نمونه‌ی Database همان بات) را
به‌عنوان پارامتر می‌گیرند - نه اینکه از یک ماژول سراسری import شود.
"""

from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    WebAppInfo,
)

from config import MINIAPP_URL


# ---------------------------------------------------------------------------
# منوی اصلی (Reply Keyboard)
# ---------------------------------------------------------------------------

def _styled_button(text: str, style_value: str) -> KeyboardButton:
    """می‌سازد یک دکمه با رنگ دلخواه (ویژگی style در Bot API 9.4 به بعد).
    مقدار خالی یعنی رنگ پیش‌فرض (خاکستری)."""
    style = style_value if style_value in ("primary", "success", "danger") else None
    return KeyboardButton(text=text, style=style)


def main_menu_kb(db, is_admin: bool) -> ReplyKeyboardMarkup:
    settings = db.get_all_settings()
    rows = []
    if MINIAPP_URL:
        rows.append([KeyboardButton(text="✨ مینی‌اپ فروشگاه", web_app=WebAppInfo(url=MINIAPP_URL))])
    rows.append(
        [_styled_button(settings.get("btn_buy", "🛒 خرید کانفیگ"), settings.get("btn_buy_style", ""))]
    )
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
    if settings.get("wheel_enabled", "1") == "1":
        rows.append(
            [_styled_button(settings.get("btn_wheel", "🎡 گردونه شانس"), settings.get("btn_wheel_style", ""))]
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


def menu_for_user(db, user_tg_id: int) -> ReplyKeyboardMarkup:
    return main_menu_kb(db, db.is_admin(user_tg_id))


# ---------------------------------------------------------------------------
# دسته‌بندی‌ها / محصولات (کاربر)
# ---------------------------------------------------------------------------

def categories_kb(categories) -> InlineKeyboardMarkup:
    rows = []
    for cat in categories:
        rows.append([InlineKeyboardButton(text=f"📁 {cat['name']}", callback_data=f"cat:{cat['id']}")])
    rows.append([InlineKeyboardButton(text="⬅️ بازگشت", callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def products_kb(db, products, category_id) -> InlineKeyboardMarkup:
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
ADMIN_PANEL_ITEMS = [
    ("adm_categories", "📂 مدیریت دسته‌بندی‌ها", "adm_categories"),
    ("adm_products", "📦 مدیریت محصولات", "adm_products"),
    ("adm_add_configs", "🔗 افزودن کانفیگ به محصول", "adm_add_configs"),
    ("adm_test_menu", "🧪 مدیریت کانفیگ تست", "adm_test_menu"),
    ("adm_pending_orders", "🧾 سفارش‌های در انتظار", "adm_pending_orders"),
    ("adm_pending_topups", "👛 درخواست‌های شارژ کیف پول", "adm_pending_topups"),
    ("adm_discounts_menu", "🎟 مدیریت کدهای تخفیف", "adm_discounts_menu"),
    ("adm_wheel_settings", "🎡 مدیریت گردونه شانس", "adm_wheel_settings"),
    ("adm_renewal_settings", "🔔 یادآوری تمدید سرویس", "adm_renewal_settings"),
    ("adm_referral_settings", "🤝 تنظیمات زیرمجموعه‌گیری", "adm_referral_settings"),
    ("adm_resellers_menu", "🏪 مدیریت بات‌های نمایندگی", "adm_resellers_menu"),
    ("adm_edit_buttons", "✏️ ویرایش متن دکمه‌ها", "adm_edit_buttons"),
    ("adm_set_card", "💳 تنظیم شماره کارت", "adm_set_card"),
    ("adm_edit_welcome", "📝 ویرایش پیام خوش‌آمد", "adm_edit_welcome"),
    ("adm_admins_menu", "👤 مدیریت ادمین‌ها", "adm_admins_menu"),
    ("adm_broadcast", "📢 پیام همگانی", "adm_broadcast"),
    ("adm_stats", "📊 آمار فروش", "adm_stats"),
]


def _styled_inline(db, text: str, callback_data: str, style_key: str) -> InlineKeyboardButton:
    style_value = db.get_setting(style_key, "")
    style = style_value if style_value in ("primary", "success", "danger") else None
    return InlineKeyboardButton(text=text, callback_data=callback_data, style=style)


def admin_panel_kb(db, is_main_bot: bool = True) -> InlineKeyboardMarkup:
    rows = []
    for key, label, callback_data in ADMIN_PANEL_ITEMS:
        if key == "adm_resellers_menu" and not is_main_bot:
            # بات‌های نمایندگی خودشان اجازه‌ی ساخت زیرنماینده ندارند
            continue
        rows.append([_styled_inline(db, label, callback_data, f"{key}_style")])
    rows.append([InlineKeyboardButton(text="🎨 رنگ‌آمیزی دکمه‌های پنل", callback_data="adm_panel_colors_menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_panel_colors_kb(db, is_main_bot: bool = True) -> InlineKeyboardMarkup:
    rows = []
    for key, label, _ in ADMIN_PANEL_ITEMS:
        if key == "adm_resellers_menu" and not is_main_bot:
            continue
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
                InlineKeyboardButton(text=f"{state_icon} {cat['name']}", callback_data="noop"),
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


def admin_products_list_kb(db, products) -> InlineKeyboardMarkup:
    rows = []
    for p in products:
        stock = db.count_available_configs(p["id"])
        state_icon = "🟢" if p["is_active"] else "🔴"
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{state_icon} {p['name']} | {p['price']:,}ت | موجودی: {stock} | مدت: {p['duration_days'] or 30} روز",
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


def admin_test_menu_kb(db) -> InlineKeyboardMarkup:
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
    "btn_wheel": "دکمه گردونه شانس",
    "btn_admin_panel": "دکمه پنل مدیریت",
}


def admin_edit_buttons_kb(db) -> InlineKeyboardMarkup:
    rows = []
    for key, label in BUTTON_LABELS.items():
        current_style = db.get_setting(f"{key}_style", "")
        style_icon = {"primary": "🔵", "success": "🟢", "danger": "🔴", "": "⚪️"}.get(current_style, "⚪️")
        rows.append(
            [
                InlineKeyboardButton(text=f"✏️ {style_icon} {label}", callback_data=f"adm_btn_edit:{key}"),
                InlineKeyboardButton(text="🎨 تغییر رنگ", callback_data=f"adm_btn_color_menu:{key}"),
            ]
        )
    rows.append([InlineKeyboardButton(text="⬅️ بازگشت", callback_data="adm_back_panel")])
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

def referral_settings_kb(db) -> InlineKeyboardMarkup:
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
        [InlineKeyboardButton(text="⬅️ بازگشت", callback_data="adm_back_panel")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def renewal_settings_kb(db) -> InlineKeyboardMarkup:
    s = db.get_renewal_settings()
    toggle_text = "🔴 غیرفعال کردن یادآوری" if s["enabled"] else "🟢 فعال کردن یادآوری"
    rows = [
        [InlineKeyboardButton(text=f"وضعیت: {'🟢 فعال' if s['enabled'] else '🔴 غیرفعال'}", callback_data="noop")],
        [InlineKeyboardButton(text=f"📅 چند روز قبل از اتمام سرویس: {s['days_before']} روز", callback_data="noop")],
        [InlineKeyboardButton(text=f"🎟 درصد تخفیف کد تشویقی: {s['discount_percent']}٪", callback_data="noop")],
        [InlineKeyboardButton(text=f"⏳ اعتبار کد تشویقی: {s['discount_expiry_hours']} ساعت", callback_data="noop")],
        [InlineKeyboardButton(text=toggle_text, callback_data="adm_renewal_toggle")],
        [InlineKeyboardButton(text="✏️ تغییر تعداد روز یادآوری", callback_data="adm_renewal_edit_days")],
        [InlineKeyboardButton(text="✏️ تغییر درصد تخفیف", callback_data="adm_renewal_edit_percent")],
        [InlineKeyboardButton(text="✏️ تغییر اعتبار کد (ساعت)", callback_data="adm_renewal_edit_hours")],
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
# مدیریت بات‌های نمایندگی (فقط در بات اصلی)
# ---------------------------------------------------------------------------

def resellers_kb(resellers) -> InlineKeyboardMarkup:
    rows = []
    for r in resellers:
        state_icon = "🟢" if r["is_active"] else "🔴"
        label = r["bot_username"] or r["bot_token"][:10] + "..."
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{state_icon} @{label} - {r['owner_name'] or r['owner_telegram_id']}",
                    callback_data="noop",
                )
            ]
        )
        rows.append(
            [
                InlineKeyboardButton(text="تغییر وضعیت", callback_data=f"adm_resbot_toggle:{r['id']}"),
                InlineKeyboardButton(text="🗑حذف", callback_data=f"adm_resbot_del:{r['id']}"),
            ]
        )
    rows.append([InlineKeyboardButton(text="➕ افزودن بات نمایندگی جدید", callback_data="adm_resbot_add")])
    rows.append([InlineKeyboardButton(text="⬅️ بازگشت", callback_data="adm_back_panel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
