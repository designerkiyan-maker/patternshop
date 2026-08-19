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
from aiogram.types import MenuButtonWebApp, MenuButtonDefault, WebAppInfo, ErrorEvent

from database import Database
from handlers_user import create_user_router
from handlers_admin import create_admin_router
from renewal_reminders import renewal_reminder_loop
from backup import backup_loop
from force_join import ForceJoinMiddleware
from blocked_user import BlockedUserMiddleware
import keyboards as kb

logger = logging.getLogger(__name__)


class AdminPresenceMiddleware:
    """با هر پیام/کلیک یک ادمین در بات، حضور آنلاین او را ثبت می‌کند تا پیام‌های
    جدید پشتیبانی زنده به اولین ادمین/مالک آنلاین مسیریابی شوند (نه به همه)."""

    def __init__(self, db):
        self.db = db

    async def __call__(self, handler, event, data: dict):
        user = data.get("event_from_user")
        if user is not None and self.db.is_admin(user.id):
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
    دید کاربر دکمه فقط «لودینگ» می‌ماند و بعد بدون هیچ واکنشی متوقف می‌شود —
    یعنی دقیقاً همان «کلید کار نمی‌کند». این هندلر خطا را لاگ می‌کند و در صورت
    امکان همان callback را با یک پیام کوتاه answer می‌کند تا کاربر دست‌کم
    بفهمد خطایی رخ داده، نه اینکه بات فریز کرده.
    """
    logger.error("خطای پردازش‌نشده در آپدیت: %s", event.exception, exc_info=event.exception)
    cq = event.update.callback_query
    if cq is not None:
        try:
            await cq.answer("⚠️ خطایی رخ داد، دوباره تلاش کنید.", show_alert=False)
        except Exception:
            pass
    return True


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

        dp.include_router(create_admin_router(db, is_main_bot=is_main_bot, bot_manager=self))
        dp.include_router(create_user_router(db, is_main_bot=is_main_bot))

        await bot.delete_webhook(drop_pending_updates=True)
        await self._sync_menu_button(bot, db)
        task = asyncio.create_task(dp.start_polling(bot))
        reminder_task = asyncio.create_task(renewal_reminder_loop(bot, db))
        backup_task = asyncio.create_task(backup_loop(bot, db, db_path))

        self.instances[token] = {
            "bot": bot, "dp": dp, "task": task, "reminder_task": reminder_task,
            "backup_task": backup_task, "db_path": db_path,
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
        backup_task = inst.get("backup_task")
        if backup_task:
            backup_task.cancel()
            try:
                await backup_task
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

    async def reconcile_resellers_loop(self, main_db, main_bot_token: str, interval: int = 10):
        """هر چند ثانیه یک‌بار وضعیت بات‌های نمایندگی را با جدول reseller_bots
        (منبع حقیقت) مقایسه و همگام می‌کند. این باعث می‌شود تغییراتی که از طریق
        Mini App (که در یک پروسه‌ی جدا از این بات اجرا می‌شود و مستقیماً به
        BotManager دسترسی ندارد) روی دیتابیس اعمال می‌شوند - مثل افزودن،
        فعال/غیرفعال‌کردن یا حذف یک نماینده - با تأخیر کوتاهی خودکار اجرا شوند،
        بدون نیاز به ری‌استارت کل سرویس."""
        from config import resolve_db_path
        while True:
            await asyncio.sleep(interval)
            try:
                rows = main_db.list_reseller_bots()
                active_tokens = {r["bot_token"]: r for r in rows if r["is_active"]}
                all_tokens = {r["bot_token"] for r in rows}

                for token, row in active_tokens.items():
                    if token not in self.instances:
                        resolved_path = resolve_db_path(row["db_path"])
                        # قبل از استارت، شناسه‌ی تننت مینی‌اپ را sync کن - دقیقاً مثل
                        # حلقه‌ی استارتاپ در main.py - وگرنه اگر این تنظیم روی
                        # دیتابیس نماینده هنوز ست نشده باشد (مثلاً به‌خاطر تایمینگ
                        # ثبت از پنل یا ری‌استور بکاپ)، دکمه‌ی منوی بات با لینک
                        # مینی‌اپ بدون ?b= ساخته می‌شود و initData او با توکن بات
                        # اصلی چک می‌شود (نه توکن خودش) -> خطای «initData نامعتبر است».
                        try:
                            reseller_db = Database(resolved_path)
                            reseller_db.init_db(owner_id=row["owner_telegram_id"])
                            reseller_db.set_setting("miniapp_tenant_id", str(row["id"]))
                        except Exception:
                            logger.exception(
                                "همگام‌سازی miniapp_tenant_id برای @%s (reconcile) ناموفق بود.",
                                row["bot_username"],
                            )
                        started = await self.start_bot(
                            token, resolved_path, row["owner_telegram_id"], is_main_bot=False
                        )
                        if started:
                            logger.info("بات نمایندگی @%s توسط reconcile راه‌اندازی شد.", row["bot_username"])

                # ترمیم یک‌بارهی بات‌های نمایندگی که از قبل در حال اجرا بودند: اگر
                # miniapp_tenant_id روی دیتابیس‌شان درست نباشد یا Menu Button هنوز
                # هیچ‌وقت با موفقیت sync نشده باشد، همین‌جا درستش کن - بدون نیاز به
                # ری‌استارت بات. فقط یک‌بار به ازای هر توکن انجام می‌شود تا به
                # Telegram API فشار اضافه وارد نشود.
                for token, row in active_tokens.items():
                    inst = self.instances.get(token)
                    if not inst or inst.get("menu_checked"):
                        continue
                    try:
                        resolved_path = resolve_db_path(row["db_path"])
                        reseller_db = Database(resolved_path)
                        current = reseller_db.get_setting("miniapp_tenant_id", "")
                        if current != str(row["id"]):
                            reseller_db.set_setting("miniapp_tenant_id", str(row["id"]))
                            logger.warning(
                                "miniapp_tenant_id برای @%s نادرست/خالی بود (%r) و اصلاح شد.",
                                row["bot_username"], current,
                            )
                        await self._sync_menu_button(inst["bot"], reseller_db)
                        inst["menu_checked"] = True
                    except Exception:
                        logger.exception("ترمیم Menu Button برای @%s ناموفق بود.", row["bot_username"])

                for token in list(self.instances.keys()):
                    if token == main_bot_token:
                        continue
                    if token not in active_tokens:
                        # یا غیرفعال شده یا کاملاً حذف شده (دیگر در all_tokens هم نیست)
                        await self.stop_bot(token)
                        logger.info(
                            "بات نمایندگی (token=...%s) توسط reconcile متوقف شد (غیرفعال/حذف‌شده).", token[-6:]
                        )
            except Exception:
                logger.exception("خطا در حلقه‌ی reconcile نمایندگی‌ها.")
