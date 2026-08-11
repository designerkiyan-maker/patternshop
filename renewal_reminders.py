# -*- coding: utf-8 -*-
"""
یادآوری خودکار اتمام سرویس + کد تخفیف تشویقی تمدید

این ماژول به‌صورت دوره‌ای (برای هر بات، مستقل و روی دیتابیس خودش) بررسی می‌کند
که آیا زمان انقضای واقعی Subscription کانفیگ فروخته‌شده به بازه یادآوری رسیده یا نه
(طبق تنظیم «چند روز قبل» در پنل مدیریت → «🔔 یادآوری تمدید سرویس»). به هر کاربری که سرویسش رو به
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

    # زمان انقضا فقط از Subscription واقعی خوانده می‌شود.
    # cf.expires_at دیتابیس نباید روی زمان ارسال یادآوری اثر بگذارد.
    info = await fetch_sub_info(row["link"])
    if not info.get("ok") or not info.get("expire"):
        logger.warning(
            "زمان انقضای واقعی Subscription برای config=%s قابل دریافت نیست؛ "
            "یادآوری ارسال نمی‌شود.",
            row["config_id"],
        )
        return

    try:
        expire_ts = float(info["expire"])
    except (TypeError, ValueError):
        logger.warning(
            "expire نامعتبر برای config=%s؛ یادآوری ارسال نمی‌شود.",
            row["config_id"],
        )
        return

    now = datetime.now(timezone.utc)
    exp_dt = datetime.fromtimestamp(expire_ts, tz=timezone.utc)
    seconds_left = expire_ts - now.timestamp()
    reminder_window = settings["days_before"] * 24 * 60 * 60

    # هنوز وارد بازه یادآوری نشده است.
    if seconds_left > reminder_window:
        return

    # کانفیگ منقضی شده است؛ یادآوری ارسال نکن.
    if seconds_left <= 0:
        return

    # محاسبه فقط برای نمایش پیام است؛ شرط ارسال با ثانیه انجام می‌شود.
    real_days_left = int(seconds_left // (24 * 60 * 60))
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
    """یک بار کانفیگ‌ها را بررسی می‌کند و زمان‌بندی را فقط از Subscription واقعی می‌خواند."""
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
