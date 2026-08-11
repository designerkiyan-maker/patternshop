# -*- coding: utf-8 -*-
"""
یادآوری خودکار اتمام سرویس + کد تخفیف تشویقی تمدید

این ماژول به‌صورت دوره‌ای (برای هر بات، مستقل و روی دیتابیس خودش) بررسی می‌کند
که آیا کانفیگ فروخته‌شده‌ای به تاریخ انقضایش نزدیک شده یا نه (طبق تنظیم «چند روز
قبل» در پنل مدیریت → «🔔 یادآوری تمدید سرویس»). به هر کاربری که سرویسش رو به
اتمام است، دقیقاً یک‌بار پیام یادآوری همراه با یک کد تخفیف اختصاصی و محدود به
زمان ارسال می‌شود.
"""

import asyncio
import logging
from datetime import datetime, timezone

from sub_info import fetch_sub_info

logger = logging.getLogger(__name__)


async def _send_single_reminder(bot, db, row) -> None:
    user_id = row["assigned_user_id"]
    if not user_id:
        db.mark_renewal_reminder_sent(row["config_id"])
        return

    settings = db.get_renewal_settings()
    days_left = None

    info = await fetch_sub_info(row["link"])
    if info.get("ok") and info.get("expire"):
        exp_dt = datetime.fromtimestamp(info["expire"], tz=timezone.utc)
        real_days_left = (exp_dt - datetime.now(timezone.utc)).days
        if real_days_left > settings["days_before"]:
            # طبق داده‌ی واقعی پنل هنوز واقعاً نزدیک انقضا نیست (مثلاً کاربر
            # دستی در پنل تمدید شده)؛ فعلاً یادآوری نمی‌فرستیم و بعداً دوباره چک می‌شود.
            return
        days_left = max(0, real_days_left)

    code, discount_expires_at, percent, expiry_hours = db.generate_renewal_discount_code(user_id)

    days_line = f"⌛ حدود {days_left} روز از سرویس شما باقی مانده.\n\n" if days_left is not None else ""

    text = (
        "⏰ یادآوری اتمام سرویس\n\n"
        f"📦 سرویس «{row['product_name']}» شما به‌زودی منقضی می‌شود.\n\n"
        f"{days_line}"
        f"🎁 برای اینکه دچار قطعی نشوید، یک کد تخفیف اختصاصی {percent}٪ برایتان صادر شد:\n"
        f"🎟 کد تخفیف: `{code}`\n"
        f"⏳ این کد فقط تا {expiry_hours} ساعت آینده معتبر است.\n\n"
        "✅ اگر همین امروز تمدید کنید، از این تخفیف بهره‌مند خواهید شد.\n"
        "برای تمدید، از منوی اصلی «🛒 خرید کانفیگ» را بزنید و هنگام خرید، دکمه‌ی "
        "«🎟 وارد کردن کد تخفیف» را زده و این کد را وارد کنید."
    )

    try:
        await bot.send_message(user_id, text, parse_mode="Markdown")
    except Exception:
        logger.warning("ارسال یادآوری تمدید به کاربر %s ناموفق بود.", user_id)

    # صرف‌نظر از موفقیت ارسال پیام، برای جلوگیری از تلاش‌های مکرر، به‌عنوان ارسال‌شده علامت می‌زنیم
    db.mark_renewal_reminder_sent(row["config_id"])


async def check_and_send_renewal_reminders(bot, db) -> None:
    """یک بار کل کانفیگ‌های نزدیک به انقضا را بررسی و برای هرکدام یادآوری ارسال می‌کند."""
    try:
        rows = db.get_configs_due_for_renewal_reminder()
    except Exception:
        logger.exception("خطا در دریافت لیست یادآوری‌های تمدید سرویس")
        return

    for row in rows:
        await _send_single_reminder(bot, db, row)


async def renewal_reminder_loop(bot, db, interval_seconds: int = 3600) -> None:
    """در پس‌زمینه، به‌صورت دوره‌ای (پیش‌فرض هر ۱ ساعت) بررسی و یادآوری ارسال می‌کند."""
    while True:
        try:
            await check_and_send_renewal_reminders(bot, db)
        except Exception:
            logger.exception("خطا در چرخه‌ی یادآوری تمدید سرویس")
        await asyncio.sleep(interval_seconds)
