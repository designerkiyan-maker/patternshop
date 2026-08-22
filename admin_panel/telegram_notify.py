# -*- coding: utf-8 -*-
"""ارسال پیام ساده به کاربر از طریق Bot API؛ برای اطلاع‌رسانی تایید/رد سفارش
و شارژ کیف پول وقتی این کارها از داخل پنل وب مستقل (نه خودِ بات) انجام می‌شوند."""

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
