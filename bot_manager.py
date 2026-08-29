# -*- coding: utf-8 -*-
"""
راه‌اندازی بات فروش الگو.

یک Bot و Dispatcher با FSM پایدار روی SQLite، سه میدلور (مسدودسازی، حضور
ادمین، عضویت اجباری) و دو روتر (ادمین + کاربر) می‌سازد و حلقه‌ی بکاپ روزانه
و تازه‌سازی کش تنظیمات را کنار polling اجرا می‌کند.
"""

import asyncio
import logging
import os
import time

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from fsm_storage import SQLiteStorage
from aiogram.types import MenuButtonWebApp, MenuButtonDefault, WebAppInfo, ErrorEvent

from database import Database
from handlers_user import create_user_router
from handlers_admin import create_admin_router
from backup import backup_loop
from force_join import ForceJoinMiddleware
from blocked_user import BlockedUserMiddleware

logger = logging.getLogger(__name__)


class AdminPresenceMiddleware:
    """با هر پیام/کلیک یک ادمین در بات، حضور آنلاین او را ثبت می‌کند تا پیام‌های
    جدید پشتیبانی زنده به اولین ادمین/مالک آنلاین مسیریابی شوند (نه به همه).

    برای این هدف نیازی نیست *هر* کلیک واقعاً روی دیتابیس نوشته شود (آستانه‌ی
    آنلاین‌بودن ۹۰ ثانیه است - PRESENCE_ONLINE_SECONDS در database.py). هر
    کلیک/پیام ادمین یک نوشتن synchronous جدا به sqlite می‌زند که روی همان
    event loop اجرا می‌شود؛ با این throttle هر ادمین حداکثر هر
    PRESENCE_WRITE_INTERVAL ثانیه یک‌بار واقعاً روی دیتابیس نوشته می‌شود و
    کلیک‌های بین این فاصله فقط از حافظه چک می‌شوند."""

    PRESENCE_WRITE_INTERVAL = 20  # ثانیه

    def __init__(self, db):
        self.db = db
        self._last_write = {}  # tg_id -> time.monotonic() آخرین نوشتن واقعی

    async def __call__(self, handler, event, data: dict):
        user = data.get("event_from_user")
        if user is not None and self.db.is_admin(user.id):
            now = time.monotonic()
            last = self._last_write.get(user.id, 0.0)
            if now - last >= self.PRESENCE_WRITE_INTERVAL:
                self._last_write[user.id] = now
                try:
                    self.db.touch_admin_presence(user.id)
                except Exception:
                    pass
        return await handler(event, data)


async def _global_error_handler(event: ErrorEvent) -> bool:
    """هندلر سراسری خطا.

    بدون این، وقتی هندلر یک دکمه‌ی شیشه‌ای (callback_query) با یک خطای
    پیش‌بینی‌نشده مواجه می‌شود (مثلاً callback_data مربوط به یک محصول/سفارش/کد
    تخفیفی که دیگر وجود ندارد)، await call.answer() هرگز اجرا نمی‌شود و از
    دید کاربر دکمه فقط «لودینگ» می‌ماند و بعد بدون هیچ واکنشی متوقف می‌شود.
    این هندلر خطا را لاگ می‌کند و در صورت امکان همان callback را با یک پیام
    کوتاه answer می‌کند تا کاربر دست‌کم بفهمد خطایی رخ داده.
    """
    logger.error("خطای پردازش‌نشده در آپدیت: %s", event.exception, exc_info=event.exception)
    cq = event.update.callback_query
    if cq is not None:
        try:
            await cq.answer("⚠️ خطایی رخ داد، دوباره تلاش کنید.", show_alert=False)
        except Exception:
            pass
        return True
    msg = event.update.message
    if msg is not None:
        try:
            await msg.answer("⚠️ در پردازش پیام شما خطایی رخ داد. لطفاً دوباره تلاش کنید یا با پشتیبانی تماس بگیرید.")
        except Exception:
            pass
    return True


class BotManager:
    def __init__(self):
        self.instances = {}  # token -> {"bot": Bot, "dp": Dispatcher, "task": asyncio.Task, "db_path": str}

    async def _sync_menu_button(self, bot: Bot) -> None:
        """دکمه‌ی منو (کنار باکس پیام) را روی Mini App فروشگاه ست می‌کند.
        اگر MINIAPP_URL تنظیم نشده باشد، دکمه‌ی پیش‌فرض برمی‌گردد."""
        miniapp_url = os.getenv("MINIAPP_URL", "").rstrip("/")
        try:
            if miniapp_url:
                await bot.set_chat_menu_button(
                    menu_button=MenuButtonWebApp(text="فروشگاه", web_app=WebAppInfo(url=miniapp_url))
                )
            else:
                await bot.set_chat_menu_button(menu_button=MenuButtonDefault())
        except Exception:
            logger.warning("ست‌کردن Menu Button ناموفق بود.", exc_info=True)

    async def start_bot(self, token: str, db_path: str, owner_id: int) -> bool:
        """بات را با دیتابیس خودش راه‌اندازی می‌کند.
        اگر توکن از قبل در حال اجرا باشد، کاری نمی‌کند و False برمی‌گرداند."""
        if token in self.instances:
            return False

        db = Database(db_path)
        db.init_db(owner_id=owner_id)

        bot = Bot(token=token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
        # FSM روی فایل SQLite ذخیره می‌شود تا state های در حال انتظار (از جمله
        # «منتظر رسید») بعد از ری‌استارت هم بمانند.
        fsm_db_path = f"{db_path}.fsm.sqlite3"
        try:
            fsm_storage = SQLiteStorage(fsm_db_path)
        except Exception:
            logger.exception(
                "ساخت SQLiteStorage برای FSM با db_path=%s ناموفق بود؛ استفاده‌ی موقت از MemoryStorage.",
                fsm_db_path,
            )
            fsm_storage = MemoryStorage()
        dp = Dispatcher(storage=fsm_storage)
        dp.errors.register(_global_error_handler)

        blocked_mw = BlockedUserMiddleware(db)
        dp.message.outer_middleware(blocked_mw)
        dp.callback_query.outer_middleware(blocked_mw)

        presence_mw = AdminPresenceMiddleware(db)
        dp.message.outer_middleware(presence_mw)
        dp.callback_query.outer_middleware(presence_mw)

        force_join_mw = ForceJoinMiddleware(db)
        dp.message.outer_middleware(force_join_mw)
        dp.callback_query.outer_middleware(force_join_mw)

        dp.include_router(create_admin_router(db))
        dp.include_router(create_user_router(db))

        await bot.delete_webhook(drop_pending_updates=True)
        await self._sync_menu_button(bot)
        task = asyncio.create_task(dp.start_polling(bot))
        backup_task = asyncio.create_task(backup_loop(bot, db, db_path))
        # جلوگیری از فریز بات هنگام انقضای کش تنظیمات/ادمین‌ها (رجوع کنید
        # به توضیح داخل Database.cache_autorefresh_loop)
        cache_refresh_task = asyncio.create_task(db.cache_autorefresh_loop())

        self.instances[token] = {
            "bot": bot, "dp": dp, "task": task,
            "backup_task": backup_task, "cache_refresh_task": cache_refresh_task, "db_path": db_path,
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
        for key in ("backup_task", "cache_refresh_task"):
            t = inst.get(key)
            if t:
                t.cancel()
                try:
                    await t
                except Exception:
                    pass
        try:
            await inst["bot"].session.close()
        except Exception:
            pass
        try:
            await inst["dp"].storage.close()
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
        """تا وقتی بات در حال اجراست، برنامه را زنده نگه می‌دارد.
        وقتی تسک polling تمام شد (مثلاً با SIGTERM) برمی‌گردد تا main()
        بتواند shutdown تمیز را انجام دهد — حلقه روی تسک تمام‌شده
        اسپین نمی‌کند."""
        while True:
            pending = [inst["task"] for inst in self.instances.values() if not inst["task"].done()]
            if not pending:
                return
            done, _ = await asyncio.wait(pending, return_when=asyncio.FIRST_EXCEPTION)
            for d in done:
                exc = d.exception()
                if exc and not isinstance(exc, asyncio.CancelledError):
                    logger.error("بات با خطا متوقف شد: %s", exc)
