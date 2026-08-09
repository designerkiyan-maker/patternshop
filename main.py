# -*- coding: utf-8 -*-
"""
نقطه ورود - اجرا با: python main.py

این فایل بات اصلی را با توکن داخل .env راه‌اندازی می‌کند و سپس تمام
بات‌های نمایندگی که قبلاً از پنل مدیریت ثبت و فعال شده‌اند را هم به‌صورت
هم‌زمان (هرکدام با دیتابیس کاملاً مستقل خودشان) اجرا می‌کند.
"""

import asyncio
import logging

from config import BOT_TOKEN, OWNER_ID, DB_PATH
from database import Database
from bot_manager import BotManager

logging.basicConfig(level=logging.INFO)
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
        started = await manager.start_bot(
            rb["bot_token"], rb["db_path"], rb["owner_telegram_id"], is_main_bot=False
        )
        if started:
            logger.info("بات نمایندگی @%s راه‌اندازی شد.", rb["bot_username"])
        # هماهنگ‌سازی شناسه‌ی تننت مینی‌اپ (برای نماینده‌های قدیمی‌تر که قبل از
        # افزودن این قابلیت ثبت شده‌اند، و برای اطمینان همیشگی از تازه بودن آن)
        try:
            reseller_db = Database(rb["db_path"])
            reseller_db.set_setting("miniapp_tenant_id", str(rb["id"]))
        except Exception:
            logger.warning("همگام‌سازی miniapp_tenant_id برای @%s ناموفق بود.", rb["bot_username"])

    try:
        await manager.wait_all()
    finally:
        await manager.stop_all()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nبرنامه با Ctrl+C متوقف شد.")
