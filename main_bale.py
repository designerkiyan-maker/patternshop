# -*- coding: utf-8 -*-
"""
نقطهی ورود بات بله (Bale) — نسخهی مستقل با python-telegram-bot v22.

تفاوت با نسخه‌ی قبلی:
  - هیچ fake module ای وجود ندارد؛ دستورها مستقیم با ptb نوشته شدهاند.
  - state/fsm از طریق state_dict داخلی مدیریت میشود.
  - database، keyboards، services کاملاً مشترک با بات تلگرام هستند.
"""

import asyncio
import logging
import os
import sys
from logging.handlers import RotatingFileHandler

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)

# ─── مسیر پروژه ────────────────────────────────────────────────
_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from config import OWNER_ID, DB_PATH, MINIAPP_URL, BALE_TOKEN, BALE_OWNER_ID_RAW
from handlers_bale import create_user_router, create_admin_router
from database import Database
from fsm_storage import SQLiteStorage

os.makedirs("logs", exist_ok=True)
_file_handler = RotatingFileHandler(
    "logs/bale_bot.log", maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"
)
_file_handler.setFormatter(
    logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
)
logging.basicConfig(level=logging.INFO, handlers=[_file_handler, logging.StreamHandler()])
logger = logging.getLogger(__name__)


def _error_handler(update: object, context):
    logger.error("Unhandled exception: %s", context.error, exc_info=context.error)


async def _pre_process(update: Update, context):
    """Set bot reference on context for handlers to use."""
    pass


async def main():
    token = os.getenv("BALE_TOKEN") or BALE_TOKEN
    if not token:
        logger.error("متغیر محیطی BALE_TOKEN تنظیم نشده است.")
        return

    owner_id = int(os.getenv("BALE_OWNER_ID") or BALE_OWNER_ID_RAW or OWNER_ID)
    miniapp_url = os.getenv("BALE_MINIAPP_URL") or MINIAPP_URL

    logger.info("=" * 50)
    logger.info("بات بله PatternShop در حال راهاندازی...")
    logger.info("  TOKEN  : %s...", token[:10])
    logger.info("  OWNER  : %s", owner_id)
    if miniapp_url:
        logger.info("  MiniApp: %s", miniapp_url)
    logger.info("=" * 50)

    # تست اتصال
    app = ApplicationBuilder().token(token).build()
    bot = app.bot
    try:
        me = await bot.get_me()
        logger.info("اتصال برقرار شد. بات: %s (@%s)", me.first_name, me.username or "(بدون username)")
    except Exception as e:
        logger.error("خطا در تست اتصال: %s", e)
        return

    # دیتابیس و FSM
    db_path = os.getenv("BALE_DB_PATH") or DB_PATH
    db_obj = Database(db_path)
    db_obj.init_db(owner_id=owner_id)

    fsm_db_path = f"{db_path}.fsm.sqlite3"
    try:
        fsm_storage = SQLiteStorage(fsm_db_path)
    except Exception:
        logger.exception("ساخت SQLiteStorage ناموفق; استفاده از حافظه موقت.")
        from handlers_bale import _temp_storage
        fsm_storage = _temp_storage

    # ساخت روترها
    user_router = create_user_router(db_obj, token)
    admin_router = create_admin_router(db_obj, token)

    # نصب handlerها
    user_router.install(app)
    admin_router.install(app)

    app.add_error_handler(_error_handler)
    app.add_handler(CommandHandler("start", lambda update, ctx: asyncio.create_task(create_user_router(db_obj, token)._handlers[0][1](update, ctx))))

    logger.info("ربات بله آماده شد. شروع polling...")

    await app.initialize()
    await app.start()

    updater = app.updater
    if updater:
        await updater.start_polling(timeout=10, bootstrap_retries=-1)
    else:
        # fallback: manual polling loop if no updater
        logger.warning("Updater not available, falling back to manual polling.")
        await _manual_polling_loop(bot, db_obj, user_router, admin_router, fsm_storage)

    try:
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        pass
    finally:
        await app.stop()
        await app.shutdown()
        try:
            await fsm_storage.close()
        except Exception:
            pass
        logger.info("بات بله متوقف شد.")


async def _manual_polling_loop(bot, db_obj, user_router, admin_router, fsm_storage):
    """Fallback polling when Updater is unavailable (rare edge case)."""
    offset = -1
    logger.info("شروع polling دستی...")
    while True:
        try:
            updates = await bot.get_updates(offset=offset, limit=100, timeout=10)
            if updates:
                for raw_upd in updates:
                    if hasattr(raw_upd, 'update_id'):
                        offset = max(offset, raw_upd.update_id) + 1
                    # Create minimal Update object for ptb
                    from telegram import Update as TgUpdate
                    update = TgUpdate.de_json(raw_upd.to_dict(), bot)
                    if update:
                        msg = update.effective_message
                        if msg:
                            logger.info(
                                "آپدیت #%s | msg=%s text=%r chat=%s user=%s",
                                update.update_id,
                                bool(msg),
                                (msg.text or "")[:60] if msg else None,
                                msg.chat.id if msg else None,
                                msg.from_user.id if msg else None,
                            )
                        await _dispatch_update(bot, update, user_router, admin_router, fsm_storage)
            else:
                await asyncio.sleep(0.5)
        except KeyboardInterrupt:
            break
        except Exception as e:
            logger.error("خطای polling: %s", e, exc_info=True)
            await asyncio.sleep(2)


async def _dispatch_update(bot, update, user_router, admin_router, fsm_storage):
    """Minimal dispatch for manual polling fallback."""
    if update.callback_query:
        # Try each router's callback handlers
        for pred, fn, args, kwargs in user_router._handlers + admin_router._handlers:
            if callable(pred) and pred(update):
                await fn(update, None)
                return
    elif update.message:
        for pred, fn, args, kwargs in user_router._handlers + admin_router._handlers:
            if isinstance(pred, MessageHandler) and pred.filter.check(update):
                await fn(update, None)
                return


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nبات بله متوقف شد.")
