# -*- coding: utf-8 -*-
"""ارسال پیام ساده به کاربر از طریق Bot API؛ برای اطلاع‌رسانی تایید/رد سفارش
و شارژ کیف پول وقتی این کارها از داخل پنل وب مستقل (نه خودِ بات) انجام می‌شوند."""

import os
import logging

import aiohttp

logger = logging.getLogger("admin_panel.telegram_notify")


async def send_message(bot_token: str, chat_id: int, text: str) -> bool:
    if not bot_token:
        return False
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url, json={"chat_id": chat_id, "text": text}, timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                return resp.status == 200
    except Exception:
        logger.exception("ارسال پیام تلگرام به %s ناموفق بود", chat_id)
        return False


async def send_document(bot_token: str, chat_id: int, file_path: str, caption: str = "") -> bool:
    """ارسال فایل (مثلاً بکاپ دیتابیس) به یک ادمین تلگرامی، بدون وابستگی به aiogram
    (پنل وب یک نمونه‌ی Bot در دسترس ندارد، پس مستقیم با Bot API خام کار می‌کند)."""
    if not bot_token:
        return False
    url = f"https://api.telegram.org/bot{bot_token}/sendDocument"
    try:
        with open(file_path, "rb") as f:
            file_bytes = f.read()
        form = aiohttp.FormData()
        form.add_field("chat_id", str(chat_id))
        if caption:
            form.add_field("caption", caption)
        form.add_field(
            "document", file_bytes,
            filename=os.path.basename(file_path), content_type="application/octet-stream",
        )
        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=form, timeout=aiohttp.ClientTimeout(total=60)) as resp:
                return resp.status == 200
    except Exception:
        logger.exception("ارسال فایل تلگرام به %s ناموفق بود", chat_id)
        return False
