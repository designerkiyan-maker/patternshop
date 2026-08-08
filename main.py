# -*- coding: utf-8 -*-
"""
نقطه ورود بات - اجرا با: python main.py
"""

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN
import database as db
import handlers_user
import handlers_admin

logging.basicConfig(level=logging.INFO)


async def main():
    db.init_db()

    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())

    # ترتیب مهم است: هندلرهای ادمین ابتدا (برای اولویت روی دکمه پنل مدیریت) سپس کاربر عادی
    dp.include_router(handlers_admin.router)
    dp.include_router(handlers_user.router)

    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        # بستن تمیز session برای جلوگیری از هشدار "Unclosed client session"
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nبات با Ctrl+C متوقف شد.")
