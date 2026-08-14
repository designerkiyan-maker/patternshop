# -*- coding: utf-8 -*-
"""
نقطه ورود - اجرا با: python main.py

این فایل بات اصلی را با توکن داخل .env راه‌اندازی می‌کند و سپس تمام
بات‌های نمایندگی که قبلاً از پنل مدیریت ثبت و فعال شده‌اند را هم به‌صورت
هم‌زمان (هرکدام با دیتابیس کاملاً مستقل خودشان) اجرا می‌کند.
"""

import asyncio
import logging
import os
from logging.handlers import RotatingFileHandler

from config import BOT_TOKEN, OWNER_ID, DB_PATH, resolve_db_path
from database import Database
from bot_manager import BotManager

os.makedirs("logs", exist_ok=True)
_file_handler = RotatingFileHandler(
    "logs/bot.log", maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"
)
_file_handler.setFormatter(
    logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
)
logging.basicConfig(level=logging.INFO, handlers=[_file_handler, logging.StreamHandler()])
logger = logging.getLogger(__name__)


async def main():
    manager = BotManager()

    # ۱. بات اصلی
    await manager.start_bot(BOT_TOKEN, DB_PATH, OWNER_ID, is_main_bot=True)
    logger.info("بات اصلی راه‌اندازی شد.")

    # ۲. تمام بات‌های نمایندگیِ فعال (ثبت‌شده از پنل مدیریت بات اصلی)
    main_db = Database(DB_PATH)
    reseller_bots = main_db.list_reseller_bots(active_only=True)
    for rb in reseller_bots:
        resolved_path = resolve_db_path(rb["db_path"])
        # هماهنگ‌سازی شناسه‌ی تننت مینی‌اپ - باید قبل از start_bot باشد تا
        # لینک مینی‌اپ این نماینده از همون اول درست ساخته شود.
        try:
            reseller_db = Database(resolved_path)
            reseller_db.init_db(owner_id=rb["owner_telegram_id"])
            reseller_db.set_setting("miniapp_tenant_id", str(rb["id"]))
        except Exception:
            logger.exception("همگام‌سازی miniapp_tenant_id برای @%s ناموفق بود.", rb["bot_username"])

        started = await manager.start_bot(
            rb["bot_token"], resolved_path, rb["owner_telegram_id"], is_main_bot=False
        )
        if started:
            logger.info("بات نمایندگی @%s راه‌اندازی شد.", rb["bot_username"])

    reconcile_task = asyncio.create_task(
        manager.reconcile_resellers_loop(main_db, BOT_TOKEN, interval=10)
    )

    try:
        await manager.wait_all()
    finally:
        reconcile_task.cancel()
        try:
            await reconcile_task
        except Exception:
            pass
        await manager.stop_all()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nبرنامه با Ctrl+C متوقف شد.")
