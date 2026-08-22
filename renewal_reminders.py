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

# کلیدهای settings برای نمایش فقط‌خواندنیِ وضعیت آخرین اجرا در پنل وب مدیریت
# (زمان‌بندی خودش هاردکد است و از پنل قابل تغییر نیست؛ فقط برای دیده‌شدن است)
STATUS_KEY_LAST_RUN = "_job_renewal_last_run"
STATUS_KEY_LAST_DATE_SENT = "_job_renewal_last_date_sent"
STATUS_KEY_LAST_VOLUME_SENT = "_job_renewal_last_volume_sent"

from sub_info import fetch_sub_info
from jalali import to_jalali_str

logger = logging.getLogger(__name__)


async def _send_single_reminder(bot, db, row, mark_fn) -> bool:
    user_id = row["assigned_user_id"]
    if not user_id:
        mark_fn(row["config_id"])
        return False

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
        return False

    try:
        expire_ts = float(info["expire"])
    except (TypeError, ValueError):
        logger.warning(
            "expire نامعتبر برای config=%s؛ یادآوری ارسال نمی‌شود.",
            row["config_id"],
        )
        return False

    now = datetime.now(timezone.utc)
    exp_dt = datetime.fromtimestamp(expire_ts, tz=timezone.utc)
    seconds_left = expire_ts - now.timestamp()
    reminder_window = settings["days_before"] * 24 * 60 * 60

    # هنوز وارد بازه یادآوری نشده است.
    if seconds_left > reminder_window:
        return False

    # کانفیگ منقضی شده است؛ یادآوری ارسال نکن.
    if seconds_left <= 0:
        return False

    # محاسبه فقط برای نمایش پیام است؛ شرط ارسال با ثانیه انجام می‌شود.
    real_days_left = int(seconds_left // (24 * 60 * 60))
    days_left = max(0, real_days_left)

    code, discount_expires_at, percent, expiry_hours = db.generate_renewal_discount_code(user_id)

    days_line = (
        f"⌛ حدود {days_left} روز از سرویس شما باقی مانده (انقضا: {to_jalali_str(exp_dt)}).\n\n"
        if days_left is not None else ""
    )

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
    mark_fn(row["config_id"])
    return True


async def check_and_send_renewal_reminders(bot, db) -> int:
    """یک بار کانفیگ‌ها را بررسی می‌کند و زمان‌بندی را فقط از Subscription واقعی می‌خواند.
    هم انبار کانفیگ ثابت و هم کانفیگ‌های ساخته‌شده مستقیم روی پنل VPN بررسی می‌شوند.
    تعداد یادآوری‌هایی که واقعاً ارسال شدند را برمی‌گرداند."""
    sent = 0
    try:
        rows = db.get_configs_due_for_renewal_reminder()
    except Exception:
        logger.exception("خطا در دریافت لیست یادآوری‌های تمدید سرویس (انبار کانفیگ)")
        rows = []
    for row in rows:
        if await _send_single_reminder(bot, db, row, db.mark_renewal_reminder_sent):
            sent += 1

    try:
        custom_rows = db.get_custom_configs_due_for_renewal_reminder()
    except Exception:
        logger.exception("خطا در دریافت لیست یادآوری‌های تمدید سرویس (کانفیگ‌های پنلی)")
        custom_rows = []
    for row in custom_rows:
        if await _send_single_reminder(bot, db, row, db.mark_custom_config_renewal_reminder_sent):
            sent += 1

    return sent


async def _send_single_volume_reminder(bot, db, row, mark_fn) -> bool:
    user_id = row["assigned_user_id"]
    if not user_id:
        mark_fn(row["config_id"])
        return False

    settings = db.get_volume_reminder_settings()

    info = await fetch_sub_info(row["link"])
    if not info.get("ok"):
        logger.warning(
            "اطلاعات مصرف Subscription برای config=%s قابل دریافت نیست؛ "
            "یادآوری حجم ارسال نمی‌شود.",
            row["config_id"],
        )
        return False

    total = info.get("total") or 0
    # کانفیگ‌های نامحدود مبنای حجمی ندارند؛ فقط یادآوری تاریخ انقضا برایشان معتبر است.
    if total <= 0:
        return False

    used = (info.get("upload") or 0) + (info.get("download") or 0)
    remaining_gb = max(0, total - used) / (1024 ** 3)
    percent_used = min(100, (used / total) * 100) if total else 0

    if settings["mode"] == "gb":
        due = remaining_gb <= settings["gb_left"]
    else:
        due = percent_used >= settings["percent"]

    if not due:
        return False

    code, discount_expires_at, percent, expiry_hours = db.generate_volume_discount_code(user_id)

    text = (
        "📉 یادآوری اتمام حجم\n\n"
        f"📦 حجم سرویس «{row['product_name']}» شما رو به اتمام است.\n\n"
        f"📊 حدود {remaining_gb:.2f} گیگابایت ({100 - round(percent_used)}٪) از حجم شما باقی مانده.\n\n"
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
        logger.warning("ارسال یادآوری اتمام حجم به کاربر %s ناموفق بود.", user_id)

    db.mark_volume_reminder_sent(row["config_id"])
    return True


async def check_and_send_volume_reminders(bot, db) -> int:
    """یک بار کانفیگ‌ها را بررسی می‌کند و بر اساس مصرف زنده‌ی Subscription، یادآوری اتمام حجم می‌فرستد.
    هم انبار کانفیگ ثابت و هم کانفیگ‌های ساخته‌شده مستقیم روی پنل VPN بررسی می‌شوند.
    تعداد یادآوری‌هایی که واقعاً ارسال شدند را برمی‌گرداند."""
    sent = 0
    try:
        rows = db.get_configs_due_for_volume_reminder()
    except Exception:
        logger.exception("خطا در دریافت لیست یادآوری‌های اتمام حجم (انبار کانفیگ)")
        rows = []
    for row in rows:
        if await _send_single_volume_reminder(bot, db, row, db.mark_volume_reminder_sent):
            sent += 1

    try:
        custom_rows = db.get_custom_configs_due_for_volume_reminder()
    except Exception:
        logger.exception("خطا در دریافت لیست یادآوری‌های اتمام حجم (کانفیگ‌های پنلی)")
        custom_rows = []
    for row in custom_rows:
        if await _send_single_volume_reminder(bot, db, row, db.mark_custom_config_volume_reminder_sent):
            sent += 1

    return sent


async def renewal_reminder_loop(bot, db, interval_seconds: int = 3600) -> None:
    """در پس‌زمینه، به‌صورت دوره‌ای (پیش‌فرض هر ۱ ساعت) بررسی و یادآوری‌های تاریخ انقضا و اتمام حجم را ارسال می‌کند.
    برای نمایش فقط‌خواندنی در پنل وب، بعد از هر چرخه‌ی کامل، زمان و تعداد یادآوری‌های
    ارسال‌شده در settings ذخیره می‌شود (این مقدار کنترل زمان‌بندی نیست، فقط وضعیت است)."""
    while True:
        date_sent = 0
        volume_sent = 0
        try:
            date_sent = await check_and_send_renewal_reminders(bot, db)
        except Exception:
            logger.exception("خطا در چرخه‌ی یادآوری تمدید سرویس")
        try:
            volume_sent = await check_and_send_volume_reminders(bot, db)
        except Exception:
            logger.exception("خطا در چرخه‌ی یادآوری اتمام حجم")
        try:
            db.set_setting(STATUS_KEY_LAST_RUN, datetime.now(timezone.utc).isoformat())
            db.set_setting(STATUS_KEY_LAST_DATE_SENT, str(date_sent))
            db.set_setting(STATUS_KEY_LAST_VOLUME_SENT, str(volume_sent))
        except Exception:
            logger.exception("خطا در ذخیره‌ی وضعیت آخرین اجرای یادآوری‌ها")
        await asyncio.sleep(interval_seconds)
