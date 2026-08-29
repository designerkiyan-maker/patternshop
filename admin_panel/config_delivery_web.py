# -*- coding: utf-8 -*-
"""
معادل وبِ تابع deliver_pattern_to_user در file_delivery.py؛ همان پیام «شیک»
(فایل الگو + کپشن مشخصات کامل سفارش + پیام خلاصه‌ی مبلغ) را برای خریدار
می‌فرستد، اما چون پنل وب مستقل نمونه‌ای از Bot در اختیار ندارد، مستقیم با
Bot API خام (sendDocument با file_id ثبت‌شده در دیتابیس) کار می‌کند.
"""

import logging

import aiohttp

from file_delivery import build_delivery_caption, build_summary_text
from admin_panel.telegram_notify import send_message as tg_send

logger = logging.getLogger("admin_panel.config_delivery_web")


async def send_document_by_file_id(bot_token: str, chat_id: int, file_id: str, caption: str = "") -> bool:
    """ارسال یک فایل تلگرامی (با file_id ذخیره‌شده در بانک فایل‌ها) بدون وابستگی به aiogram.
    وقتی به‌جای آپلود فایل، رشته‌ی file_id به فیلد document داده شود، تلگرام همان
    فایل قبلی را برای کاربر می‌فرستد (همان کاری که bot.send_document در بات می‌کند)."""
    if not bot_token or not file_id:
        return False
    url = f"https://api.telegram.org/bot{bot_token}/sendDocument"
    try:
        form = aiohttp.FormData()
        form.add_field("chat_id", str(chat_id))
        if caption:
            form.add_field("caption", caption)
        form.add_field("document", file_id)
        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=form, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                return resp.status == 200
    except Exception:
        logger.exception("ارسال فایل الگو به %s ناموفق بود", chat_id)
        return False


async def deliver_pattern_to_user_web(
    bot_token: str,
    user_tg_id: int,
    product_name: str,
    file_ids,
    final_price: int = None,
    order_id: int = None,
) -> None:
    """ارسال همه‌ی فایل‌های الگوی یک سفارشِ تاییدشده به خریدار، از داخل پنل وب.

    file_ids: لیست file_id فایل‌های تلگرامی این محصول (از جدول product_files).
    اگر ارسال یک فایل با خطا مواجه شود (مثلاً فایل از تلگرام حذف شده باشد)،
    متن مشخصات سفارش جایگزین ارسال می‌شود و بقیه‌ی فایل‌ها ادامه پیدا می‌کنند.
    """
    if isinstance(file_ids, str):
        file_ids = [file_ids]
    total = len(file_ids)

    for idx, file_id in enumerate(file_ids, start=1):
        caption = build_delivery_caption(product_name, idx, total, order_id)
        sent = await send_document_by_file_id(bot_token, user_tg_id, file_id, caption)
        if not sent:
            # اگر ارسال فایل به هر دلیلی ناموفق بود، حداقل متن مشخصات سفارش برای کاربر ارسال شود
            await tg_send(bot_token, user_tg_id, caption)

    if final_price is not None:
        await tg_send(bot_token, user_tg_id, build_summary_text(final_price or 0))
