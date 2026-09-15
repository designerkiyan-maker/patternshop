# -*- coding: utf-8 -*-
"""
نقطهی ورود بات بله — python-telegram-bot v22 مستقیم، بدون fake module.
"""

import asyncio
import logging
import os
import sys
from logging.handlers import RotatingFileHandler

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters

_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from config import OWNER_ID, DB_PATH, BALE_TOKEN, BALE_OWNER_ID_RAW
from handlers_bale import make_user_handlers, make_admin_handlers
from database import Database

os.makedirs("logs", exist_ok=True)
_fh = RotatingFileHandler("logs/bale_bot.log", maxBytes=5*1024*1024, backupCount=5, encoding="utf-8")
_fh.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s"))
logging.basicConfig(level=logging.INFO, handlers=[_fh, logging.StreamHandler()])
logger = logging.getLogger(__name__)


def _error_handler(update: object, context):
    logger.error("Unhandled: %s", context.error, exc_info=context.error)


async def main():
    token = os.getenv("BALE_TOKEN") or BALE_TOKEN
    if not token:
        logger.error("BALE_TOKEN تنظیم نشده است.")
        return

    owner_id = int(os.getenv("BALE_OWNER_ID") or BALE_OWNER_ID_RAW or OWNER_ID)
    logger.info("=" * 50)
    logger.info("بات بله PatternShop در حال راهاندازی...")
    logger.info("  TOKEN  : %s...", token[:10])
    logger.info("  OWNER  : %s", owner_id)
    logger.info("=" * 50)

    app = ApplicationBuilder().token(token).base_url("https://tapi.bale.ai/").connect_timeout(30).read_timeout(30).write_timeout(30).build()
    bot = app.bot

    try:
        me = await bot.get_me()
        logger.info("اتصال: %s (@%s)", me.first_name, me.username or "")
    except Exception as e:
        logger.error("خطای اتصال: %s", e); return

    db_path = os.getenv("BALE_DB_PATH") or DB_PATH
    db = Database(db_path)
    db.init_db(owner_id=owner_id)

    # نصب handlerها
    for h in await make_user_handlers(db, token):
        app.add_handler(h)
    for h in await make_admin_handlers(db, token):
        app.add_handler(h)
    app.add_error_handler(_error_handler)

    logger.info("ربات بله آماده شد.")
    await app.initialize()
    await app.start()
    await app.updater.start_polling(timeout=10, bootstrap_retries=-1)

    try:
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        pass
    finally:
        await app.stop()
        await app.shutdown()
        logger.info("بات بله متوقف شد.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nمتوقف شد.")
