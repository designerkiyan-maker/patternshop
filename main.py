# -*- coding: utf-8 -*-
"""
نقطه ورود - اجرا با: python main.py

این فایل بات فروش الگو را با توکن داخل .env راه‌اندازی می‌کند.
"""

import asyncio
import logging
import os
from logging.handlers import RotatingFileHandler

from config import BOT_TOKEN, OWNER_ID, DB_PATH
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
    await manager.start_bot(BOT_TOKEN, DB_PATH, OWNER_ID)
    logger.info("بات راه‌اندازی شد.")

    try:
        await manager.wait_all()
    finally:
        await manager.stop_all()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nبرنامه با Ctrl+C متوقف شد.")
