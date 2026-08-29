# -*- coding: utf-8 -*-
"""
تحویل فایل الگو به خریدار پس از تایید سفارش.

هر فایل الگو (PDF و ...) که قبلاً ادمین آپلود کرده و file_id آن در جدول
product_files ذخیره شده است، با send_document برای کاربر ارسال می‌شود؛ همراه
با کپشن ساختارمند (شماره سفارش، نام الگو، تاریخ شمسی) و در پایان خلاصه‌ی
مبلغ پرداخت‌شده.

توابع این ماژول عمداً مستقل از aiogram Router نوشته شده‌اند تا از هر نقطه‌ای
(تایید ادمین، خرید آنی با کیف پول، پاداش زیرمجموعه‌گیری) قابل فراخوانی باشند.
"""

import logging
from datetime import datetime

import jalali

logger = logging.getLogger(__name__)


def build_delivery_caption(product_name: str, file_idx: int, file_total: int, order_id: int) -> str:
    """کپشن پیام تحویل هر فایل الگو."""
    today = jalali.to_jalali_str(datetime.now())
    lines = [
        "🎉 با تشکر از خرید شما!",
        "",
        "✅ الگوی شما با موفقیت صادر و آماده‌ی دانلود است.",
        "",
        "🧾 مشخصات سفارش",
        f"┣ 🆔 شماره سفارش: #{order_id}",
        f"┣ 🧵 محصول: {product_name}",
    ]
    if file_total > 1:
        lines.append(f"┣ 📎 فایل {file_idx} از {file_total}")
    lines.append(f"┗ 📅 تاریخ تحویل: {today}")
    lines += [
        "",
        "🧵 فایل الگو ضمیمه‌ی همین پیام است؛ آن را ذخیره کنید.",
        "🔒 این فایل مخصوص شماست و نباید بازنشر شود.",
        "📞 هر سوالی دارید از بخش پشتیبانی بپرسید.",
    ]
    return "\n".join(lines)


def build_summary_text(final_price) -> str:
    """پیام خلاصه‌ی مبلغ پرداخت‌شده در پایان تحویل."""
    return f"\n💰 مبلغ کل پرداخت‌شده: {final_price:,} تومان"


async def deliver_pattern_to_user(bot, user_tg_id: int, product_name: str, file_ids, final_price, order_id: int) -> None:
    """ارسال همه‌ی فایل‌های یک سفارش به کاربر.

    file_ids: لیست file_id فایل‌های تلگرامی مربوط به این محصول.
    اگر ارسال یک فایل با خطا مواجه شود (مثلاً فایل از تلگرام حذف شده باشد)،
    بقیه‌ی فایل‌ها ارسال می‌شوند و خطا لاگ می‌شود.
    """
    total = len(file_ids)
    for idx, file_id in enumerate(file_ids, start=1):
        caption = build_delivery_caption(product_name, idx, total, order_id)
        try:
            await bot.send_document(user_tg_id, file_id, caption=caption)
        except Exception:
            logger.exception("ارسال فایل الگو ناموفق بود (order=%s, idx=%s).", order_id, idx)
            try:
                await bot.send_message(
                    user_tg_id,
                    f"⚠️ ارسال یکی از فایل‌های سفارش #{order_id} با خطا مواجه شد.\n"
                    "لطفاً از بخش «سفارش‌های من» دوباره تلاش کنید یا به پشتیبانی پیام بدهید.",
                )
            except Exception:
                pass

    try:
        await bot.send_message(user_tg_id, build_summary_text(final_price or 0))
    except Exception:
        pass
