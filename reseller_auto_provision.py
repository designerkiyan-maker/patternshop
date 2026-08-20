# -*- coding: utf-8 -*-
"""
تحویل خودکار محصولات «اعتبار حجمی» در بات‌های نمایندگی.

وقتی مشتریِ یک بات نمایندگی محصولی با is_auto_provision=1 می‌خرد، به‌جای
برداشتن یک لینک از بانک کانفیگ (که برای این محصولات اصلاً پر نمی‌شود)،
همین لحظه یک کاربر جدید روی همان پنلی که برای «نمایندگی» صاحب این بات در
بات اصلی تنظیم شده ساخته می‌شود و از اعتبار حجمی او کم می‌شود.

این ماژول عمداً کاملاً مستقل از هر Database instance خاصی است چون باید هم
به دیتابیس ایزوله‌ی بات نمایندگی (برای خواندن مالک/محصول) و هم به دیتابیس
بات اصلی (برای اعتبار و پنل) دسترسی داشته باشد؛ هر دو در همان پروسه اجرا
می‌شوند پس این کار فقط یک اتصال SQLite دوم است، نه فراخوانی شبکه‌ای.
"""

import random
import string

from config import DB_PATH as MAIN_DB_PATH
from database import Database
from panel_providers import get_provider, PanelError, PanelUsernameTakenError


class ProvisionError(Exception):
    pass


def _random_username() -> str:
    return "r" + "".join(random.choices(string.ascii_lowercase + string.digits, k=8))


async def provision_auto_config(local_db: Database, product, quantity: int = 1) -> list:
    """محصول باید is_auto_provision=1 داشته باشد. برای هر واحد یک کاربر واقعی روی پنل
    نمایندگی ساخته می‌شود. برمی‌گرداند: لیستی از
    {"username": ..., "subscription_url": ..., "volume_gb": ..., "duration_days": ...}
    در صورت هر نوع خطا (حتی بعد از ساخت موفق چند واحد) ProvisionError پرتاب می‌شود و
    هیچ اعتباری کم نمی‌شود - یعنی این تابع همه‌یا-هیچ است تا خرید ناقص تحویل داده نشود."""
    owner_id = local_db.get_owner_telegram_id()
    if not owner_id:
        raise ProvisionError("مالک این بات مشخص نیست؛ با پشتیبانی تماس بگیرید.")

    volume_gb = product["auto_provision_volume_gb"]
    if not volume_gb or volume_gb <= 0:
        raise ProvisionError("حجم این محصول تنظیم نشده است.")
    duration_days = product["duration_days"] or 30
    total_volume_gb = volume_gb * quantity

    main_db = Database(MAIN_DB_PATH)

    if not main_db.is_reseller(owner_id):
        raise ProvisionError("دسترسی اعتبار حجمی برای مالک این بات فعال نیست؛ با پشتیبانی تماس بگیرید.")

    credit = main_db.get_reseller_credit(owner_id)
    if credit < total_volume_gb:
        raise ProvisionError(f"اعتبار حجمی نماینده کافی نیست (نیاز: {total_volume_gb:,} گیگ، باقیمانده: {credit:,} گیگ).")

    server = main_db.get_reseller_panel(owner_id)
    if not server or not server["is_active"]:
        raise ProvisionError("پنل اعتبار حجمی نماینده تنظیم نشده یا غیرفعال است؛ با پشتیبانی تماس بگیرید.")

    provider = get_provider(server)
    built = []
    try:
        for _ in range(quantity):
            username = None
            result = None
            for _try in range(5):
                candidate = _random_username()
                try:
                    result = await provider.create_user(candidate, volume_gb, duration_days)
                    username = candidate
                    break
                except PanelUsernameTakenError:
                    continue
            if username is None:
                raise ProvisionError("ساخت نام کاربری یکتا روی پنل ناموفق بود؛ دوباره تلاش کنید.")
            built.append({
                "username": result.username,
                "subscription_url": result.subscription_url,
                "volume_gb": volume_gb,
                "duration_days": duration_days,
            })
    except ProvisionError:
        raise
    except PanelError as e:
        raise ProvisionError(f"خطا در ساخت کانفیگ روی پنل: {e}")

    # فقط بعد از موفقیت واقعیِ ساخت همه‌ی واحدها روی پنل، از اعتبار کم می‌شود
    main_db.adjust_reseller_credit(
        owner_id, -total_volume_gb, reason=f"خرید خودکار مشتری - محصول «{product['name']}» × {quantity}"
    )

    return built
