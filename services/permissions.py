# -*- coding: utf-8 -*-
"""مجوزهای مدیریت - ماتریس کانونیکال برای «هر دو» رابط (تلگرام و پنل وب).

انتفاع اصلی: یک سیستم مدیریتی واحد با دو رابط. جدولِ ROLE_PERMISSION_PRESETS در
database.py تنها منبع حقیقتِ نگاشت نقش و مجوزهاست؛ این ماژول فقط رابط‌های خواندن
از همان ماتریس را برای سطح تلگرام فراهم می‌کند تا با سطح وب (که مستقیم از
WEB_ADMIN_PERMISSIONS / get_web_admin_permissions می‌خواند) هیچ تضادی نداشته باشد.
"""

import json

from database import ROLE_PERMISSION_PRESETS


def telegram_role_permissions(role) -> list:
    """مجوزهای کانونیکال یک نقش تلگرامی (همان کانونیکالِ وب). نقش ناشناخته = هیچ."""
    return list(ROLE_PERMISSION_PRESETS.get(role, []))


def telegram_has_permission(db, tg_id, permission: str) -> bool:
    """آیا این ادمینِ تلگرامی این مجوز کانونیکال را دارد؟ (همان ماتریسِ وب)."""
    role = db.get_admin_role(tg_id)
    return permission in telegram_role_permissions(role)


def web_has_permission(admin_row, permission: str) -> bool:
    """بررسی مجوز ردیفِ ادمین وب. owner همیشه همه	چیز؛ بقیه از ستون permissions."""
    if not admin_row:
        return False
    if admin_row.get("role") == "owner":
        return True
    try:
        perms = json.loads(admin_row.get("permissions") or "[]")
    except (ValueError, TypeError):
        perms = []
    return permission in perms


# ---------------------------------------------------------------------------
# گیت‌های مالی: نقش‌هایی که مجاز به تأیید/رد سفارش و شارژ کیف پول هستند.
# از ماتریس کانونیکال محاسبه می‌شود تا هرگز با پنل وب از سنکرون خارج نشود.
# ---------------------------------------------------------------------------

def can_manage_orders_role(role) -> bool:
    """آیا این نقش می‌تواند سفارش/شارژ را تأیید یا رد کند؟ owner/admin/mid بله."""
    return "orders" in telegram_role_permissions(role)


def telegram_can_manage_orders(db, tg_id) -> bool:
    return telegram_has_permission(db, tg_id, "orders")


def telegram_can_manage_catalog(db, tg_id) -> bool:
    return telegram_has_permission(db, tg_id, "catalog")


def telegram_can_manage_inventory(db, tg_id) -> bool:
    return telegram_has_permission(db, tg_id, "inventory")


def telegram_can_manage_shipping(db, tg_id) -> bool:
    return telegram_has_permission(db, tg_id, "shipping")


def telegram_can_manage_discounts(db, tg_id) -> bool:
    return telegram_has_permission(db, tg_id, "discounts")


def telegram_can_manage_settings(db, tg_id) -> bool:
    return telegram_has_permission(db, tg_id, "settings")