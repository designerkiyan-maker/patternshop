# -*- coding: utf-8 -*-
"""
Middleware مسدودسازی کاربر.

قبل از اجرای هر هندلر (پیام یا دکمه‌ی شیشه‌ای)، اگر کاربر توسط ادمین بلاک شده
باشد، هندلر اصلی اجرا نمی‌شود و پیام «حساب شما مسدود شده» نمایش داده می‌شود.
ادمین‌های بات از این محدودیت معاف هستند (تا خودشون هیچ‌وقت قفل نشن).
"""

import logging

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery

logger = logging.getLogger(__name__)

BLOCKED_MESSAGE = "⛔️ حساب شما توسط مدیریت مسدود شده است. برای پیگیری با پشتیبانی تماس بگیرید."


class BlockedUserMiddleware(BaseMiddleware):
    def __init__(self, db):
        super().__init__()
        self.db = db

    async def __call__(self, handler, event: TelegramObject, data: dict):
        user = data.get("event_from_user")
        if not user:
            return await handler(event, data)

        # ادمین‌های بات از این محدودیت معاف هستند
        if self.db.is_admin(user.id):
            return await handler(event, data)

        db_user = self.db.get_user(user.id)
        if not db_user or not db_user["is_blocked"]:
            return await handler(event, data)

        if isinstance(event, CallbackQuery):
            await event.answer(BLOCKED_MESSAGE, show_alert=True)
        elif isinstance(event, Message):
            await event.answer(BLOCKED_MESSAGE)
        return  # هندلر اصلی اجرا نمی‌شود
