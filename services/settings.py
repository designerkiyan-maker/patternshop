# -*- coding: utf-8 -*-
"""تنظیمات - دسترسی تایپ‌شده و allow-list برای هر دو رابط (بات و وب).

هدف: مقداردهی مجاز تنظیمات فقط با کلیدهای شناخته‌شده و نوع درست انجام شود تا
هیچ رابطی با کلید دلخواه (مثلاً تنظیمات مخرب یا غلط) دیتابیس را آلوده نکند.
"""

import json

from database import DEFAULT_SETTINGS
from services.errors import SettingsError

# کلیدهای جدید (لایه‌ی تجارت فیزیکی/سبد) به همراه مقدار پیش‌فرض. این‌ها به‌صورت
# INSERT OR IGNORE هم در پیش‌فرض‌ها قرار می‌گیرند تا نصب‌های قدیمی هم آن‌ها را بگیرند.
COMMERCE_SETTINGS = {
    "btn_cart": "🛒 سبد خرید",
    "btn_cart_style": "primary",
    "cart_enabled": "1",
    "physical_products_enabled": "1",
    "checkout_auto_approve_wallet": "1",  # اگر موجودی/تخفیف کل مبلغ را پوشش دهد، خودکار تأیید شود
}

# کلیدهای عددی (تومان/عداد) - مقدار باید عدد صحیح مثبت یا 0 باشد
INT_KEYS = {
    "referral_percent",
    "referral_commission_max_count",
    "referral_free_config_threshold",
    "referral_invite_bonus_amount",
    "referral_invite_bonus_max_count",
    "wheel_win_percent",
    "wheel_code_expiry_hours",
    "wheel_cooldown_hours",
    "loyalty_points_per_toman",
    "loyalty_reg_bonus",
    "loyalty_referral_bonus",
    "loyalty_redeem_points",
    "loyalty_redeem_toman",
    "loyalty_min_redeem",
    "loyalty_max_per_order",
}

# کلیدهای بولی (0/1)
BOOL_KEYS = {
    "test_enabled",
    "force_join_enabled",
    "referral_button_enabled",
    "referral_enabled",
    "referral_free_config_enabled",
    "referral_invite_bonus_enabled",
    "wheel_enabled",
    "loyalty_enabled",
    "main_menu_reply_enabled",
    "main_menu_inline_enabled",
    "cart_enabled",
    "physical_products_enabled",
    "checkout_auto_approve_wallet",
}

# کلیدهای JSON (که باید قابل parse باشند)
JSON_KEYS = {"miniapp_banners", "menu_order", "main_menu_row_breaks", "loyalty_tiers"}

ALLOWED_KEYS = set(DEFAULT_SETTINGS.keys()) | set(COMMERCE_SETTINGS.keys())


def register_defaults(db):
    """این کلیدهای تجارت جدید را (بی‌خطر) در جدول تنظیمات ثبت می‌کند."""
    for k, v in COMMERCE_SETTINGS.items():
        db.set_setting_default(k, v)


def validate_setting(key: str, value: str) -> str:
    """کلید و مقدار را اعتبارسنجی/نرمال می‌کند. خطا -> SettingsError."""
    if key not in ALLOWED_KEYS:
        raise SettingsError(f"کلید تنظیمات شناخته‌شده نیست: {key}", code="unknown_key", key=key)
    if key in INT_KEYS:
        cleaned = str(value).strip()
        if not cleaned.lstrip("-").isdigit():
            raise SettingsError("مقدار باید عدد صحیح باشد.", code="invalid_int", key=key)
        if int(cleaned) < 0:
            raise SettingsError("مقدار نمی‌تواند منفی باشد.", code="invalid_int", key=key)
        return str(int(cleaned))
    if key in BOOL_KEYS:
        if str(value) not in ("0", "1"):
            raise SettingsError("مقدار باید 0 یا 1 باشد.", code="invalid_bool", key=key)
        return "1" if str(value) == "1" else "0"
    if key in JSON_KEYS:
        try:
            json.loads(value)
        except (ValueError, TypeError):
            raise SettingsError("مقدار باید JSON معتبر باشد.", code="invalid_json", key=key)
    return str(value)


# ---------------------------------------------------------------------------
# خواننده‌های تایپ‌شده (با پیش‌فرض ایمن)
# ---------------------------------------------------------------------------

def get_int(db, key: str, default: int = 0) -> int:
    try:
        return int(db.get_setting(key, str(default)) or default)
    except (ValueError, TypeError):
        return default


def get_bool(db, key: str, default: bool = False) -> bool:
    val = db.get_setting(key, "1" if default else "0")
    return str(val).strip() == "1"


def get_json(db, key: str, default=None):
    raw = db.get_setting(key, "")
    if not raw:
        return default
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        return default


def set_setting(db, key: str, value: str, *, actor: str = "") -> str:
    """تنظیم یک مقدار با اعتبارسنجی common؛ خروجی مقدار نرمال‌شده."""
    normalized = validate_setting(key, value)
    db.set_setting(key, normalized)
    return normalized