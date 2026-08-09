# -*- coding: utf-8 -*-
"""
مدیریت چند بات هم‌زمان (بات اصلی + هر بات نمایندگی).

هر بات یک Bot و Dispatcher مستقل خودش را دارد و روی یک asyncio task جداگانه
در حال polling است؛ اضافه/حذف‌کردن یک بات نمایندگی نیازی به ری‌استارت کل
پروسه ندارد.
"""

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import MenuButtonWebApp, MenuButtonDefault, WebAppInfo

from database import Database
from handlers_user import create_user_router
from handlers_admin import create_admin_router
from renewal_reminders import renewal_reminder_loop
from force_join import ForceJoinMiddleware
import keyboards as kb

logger = logging.getLogger(__name__)


class BotManager:
    def __init__(self):
        self.instances = {}  # token -> {"bot": Bot, "dp": Dispatcher, "task": asyncio.Task, "db_path": str}

    async def _sync_menu_button(self, bot: Bot, db) -> None:
        """دکمه‌ی منو (کنار باکس پیام) را روی مینی‌اپ همین بات ست می‌کند.
        چون از Menu Button باز می‌شود، initData واقعی و معتبر تولید می‌شود
        (برخلاف دکمه‌ی reply keyboard که initData همیشه خالی است).
        این کار کاملاً خودکار است؛ نماینده هیچ کاری (دامنه/BotFather) لازم ندارد."""
        miniapp_url = kb._miniapp_url(db)
        try:
            if miniapp_url:
                await bot.set_chat_menu_button(
                    menu_button=MenuButtonWebApp(text="فروشگاه", web_app=WebAppInfo(url=miniapp_url))
                )
            else:
                await bot.set_chat_menu_button(menu_button=MenuButtonDefault())
        except Exception:
            logger.warning("ست‌کردن Menu Button ناموفق بود.", exc_info=True)

    async def start_bot(self, token: str, db_path: str, owner_id: int, is_main_bot: bool = False) -> bool:
        """یک بات جدید (اصلی یا نمایندگی) را با دیتابیس مستقل خودش راه‌اندازی می‌کند.
        اگر توکن از قبل در حال اجرا باشد، کاری نمی‌کند و False برمی‌گرداند."""
        if token in self.instances:
            return False

        db = Database(db_path)
        db.init_db(owner_id=owner_id)

        bot = Bot(token=token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
        dp = Dispatcher(storage=MemoryStorage())

        force_join_mw = ForceJoinMiddleware(db)
        dp.message.outer_middleware(force_join_mw)
        dp.callback_query.outer_middleware(force_join_mw)

        dp.include_router(create_admin_router(db, is_main_bot=is_main_bot, bot_manager=self))
        dp.include_router(create_user_router(db))

        await bot.delete_webhook(drop_pending_updates=True)
        await self._sync_menu_button(bot, db)
        task = asyncio.create_task(dp.start_polling(bot))
        reminder_task = asyncio.create_task(renewal_reminder_loop(bot, db))

        self.instances[token] = {
            "bot": bot, "dp": dp, "task": task, "reminder_task": reminder_task, "db_path": db_path,
        }
        logger.info("بات با db_path=%s راه‌اندازی شد.", db_path)
        return True

    async def stop_bot(self, token: str) -> bool:
        inst = self.instances.pop(token, None)
        if not inst:
            return False
        inst["task"].cancel()
        try:
            await inst["task"]
        except Exception:
            pass
        reminder_task = inst.get("reminder_task")
        if reminder_task:
            reminder_task.cancel()
            try:
                await reminder_task
            except Exception:
                pass
        try:
            await inst["bot"].session.close()
        except Exception:
            pass
        logger.info("بات با db_path=%s متوقف شد.", inst["db_path"])
        return True

    async def stop_all(self):
        for token in list(self.instances.keys()):
            await self.stop_bot(token)

    def is_running(self, token: str) -> bool:
        return token in self.instances

    async def wait_all(self):
        """تا وقتی حداقل یک بات در حال اجراست، برنامه را زنده نگه می‌دارد."""
        while True:
            tasks = [inst["task"] for inst in self.instances.values()]
            if not tasks:
                await asyncio.sleep(1)
                continue
            done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_EXCEPTION)
            for d in done:
                exc = d.exception()
                if exc and not isinstance(exc, asyncio.CancelledError):
                    logger.error("یکی از بات‌ها با خطا متوقف شد: %s", exc)
