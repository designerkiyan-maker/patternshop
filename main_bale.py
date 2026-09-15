# -*- coding: utf-8 -*-
"""
نقطهی ورود بات بله (Bale).

این فایل از همان منطق کسب‌وکارِ handlers_user / handlers_admin استفاده میکند
بدون هیچ تغییری — صرفاُ با یک لایهی سازگاری (`aiogram/` ساختگی در ریشهی پروژه)
نسخهی aiogram 3.x به python-telegram-bot v22 مترجم میشود.

اجرا:
  BALE_TOKEN=<token> python main_bale.py
"""

import asyncio
import logging
import os
import sys
import time
from logging.handlers import RotatingFileHandler

# ─── مسیر پروژه را اول از همه به sys.path اضافه میکنیم ───────────────
_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# ─── fake-aiogram shim: قبل از هر import aiogram، ماژول‌های ساختگی را در sys.modules قرار میدهیم
# تا handlers_user/handlers_admin بدون تغییر به aiogram 3.x فکر کنند ولی در واقعیت
# از python-telegram-bot v22 روی tapi.bale.ai استفاده کنند.
FAKE_AIOPATH = os.path.join(_PROJECT_ROOT, 'providers')
_fake_modules = {
    'aiogram': FAKE_AIOPATH,
    'aiogram.types': FAKE_AIOPATH + '/__fake_aiogram',
    'aiogram.filters': FAKE_AIOPATH + '/__fake_aiogram',
    'aiogram.fsm.context': FAKE_AIOPATH + '/__fake_aiogram',
    'aiogram.fsm.state': FAKE_AIOPATH + '/__fake_aiogram',
    'aiogram.fsm.storage.memory': FAKE_AIOPATH + '/__fake_aiogram',
    'aiogram.fsm.storage.base': FAKE_AIOPATH + '/__fake_aiogram',
    'aiogram.client.default': FAKE_AIOPATH + '/__fake_aiogram',
    'aiogram.enums': FAKE_AIOPATH + '/__fake_aiogram',
    'aiogram.exceptions': FAKE_AIOPATH + '/__fake_aiogram',
}
for _mod_name, _mod_path in _fake_modules.items():
    if _mod_name not in sys.modules:
        import importlib.util, types
        spec = importlib.util.spec_from_file_location(
            _mod_name,
            os.path.join(_PROJECT_ROOT, 'providers', '__fake_aiogram.py'),
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        sys.modules[_mod_name] = mod

from config import OWNER_ID, DB_PATH, MINIAPP_URL, BALE_TOKEN, BALE_OWNER_ID_RAW
from providers.bale_bot import BALE_API_BASE, BALE_FILE_BASE

os.makedirs("logs", exist_ok=True)
_file_handler = RotatingFileHandler(
    "logs/bale_bot.log", maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"
)
_file_handler.setFormatter(
    logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
)
logging.basicConfig(level=logging.INFO, handlers=[_file_handler, logging.StreamHandler()])
logger = logging.getLogger(__name__)


# ===================================================================
# BotWrapper — bridge بین ptb Bot و interface مورد نیاز handlerها
# ===================================================================

class BotWrapper:
    """نمونهی Bot wrapper که متدهای مورد نیاز handlerها را از ptb Bot میگیرد."""

    def __init__(self, token: str):
        self.token = token
        # ptb خودش /{token} را به base_url میچسباند → https://tapi.bale.ai/{token}/method
        self._base_url = f"https://tapi.bale.ai/"
        self._base_file_url = f"https://tapi.bale.ai/"
        self._ptb = None

    def _get_ptb(self):
        if self._ptb is None:
            from telegram import Bot
            self._ptb = Bot(
                token=self.token,
                base_url=self._base_url,
                base_file_url=self._base_file_url,
            )
        return self._ptb

    async def _call(self, method, **kwargs):
        fn = getattr(self._get_ptb(), method)
        try:
            return await fn(**kwargs)
        except Exception as e:
            from providers.__fake_aiogram import _translate_ptb_exception
            raise _translate_ptb_exception(e)

    async def send_message(self, chat_id, text, parse_mode=None, reply_markup=None,
                           protect_content=None, disable_notification=None, **kwargs):
        args = {"chat_id": int(chat_id), "text": text}
        if parse_mode: args["parse_mode"] = parse_mode
        if reply_markup: args["reply_markup"] = _mk_reply_markup(reply_markup)
        if protect_content is not None: args["protect_content"] = protect_content
        if disable_notification is not None: args["disable_notification"] = disable_notification
        return await self._call("send_message", **args)

    async def send_photo(self, chat_id, photo, caption=None, parse_mode=None,
                         reply_markup=None, protect_content=None, **kwargs):
        args = {"chat_id": int(chat_id), "photo": photo}
        if caption: args["caption"] = caption
        if parse_mode: args["parse_mode"] = parse_mode
        if reply_markup: args["reply_markup"] = _mk_reply_markup(reply_markup)
        if protect_content is not None: args["protect_content"] = protect_content
        return await self._call("send_photo", **args)

    async def send_document(self, chat_id, document, caption=None, parse_mode=None,
                            reply_markup=None, protect_content=None, **kwargs):
        args = {"chat_id": int(chat_id), "document": document}
        if caption: args["caption"] = caption
        if parse_mode: args["parse_mode"] = parse_mode
        if reply_markup: args["reply_markup"] = _mk_reply_markup(reply_markup)
        if protect_content is not None: args["protect_content"] = protect_content
        return await self._call("send_document", **args)

    async def send_dice(self, chat_id, emoji="🎲", reply_markup=None, **kwargs):
        args = {"chat_id": int(chat_id), "emoji": emoji}
        if reply_markup: args["reply_markup"] = _mk_reply_markup(reply_markup)
        return await self._call("send_dice", **args)

    async def edit_message_text(self, text, chat_id=None, message_id=None,
                                inline_message_id=None, parse_mode=None,
                                reply_markup=None, **kwargs):
        args = {"text": text}
        if chat_id is not None: args["chat_id"] = int(chat_id)
        if message_id is not None: args["message_id"] = int(message_id)
        if inline_message_id: args["inline_message_id"] = inline_message_id
        if parse_mode: args["parse_mode"] = parse_mode
        if reply_markup: args["reply_markup"] = _mk_reply_markup(reply_markup)
        return await self._call("edit_message_text", **args)

    async def delete_message(self, chat_id, message_id, **kwargs):
        return await self._call("delete_message", chat_id=int(chat_id), message_id=int(message_id))

    async def get_updates(self, offset=None, limit=None, timeout=None, allowed_updates=None, **kwargs):
        return await self._call("get_updates", offset=offset, limit=limit, timeout=timeout, allowed_updates=allowed_updates)

    async def get_me(self, **kwargs):
        return await self._call("get_me")

    async def delete_webhook(self, drop_pending_updates=None, **kwargs):
        return await self._call("delete_webhook", drop_pending_updates=drop_pending_updates)

    async def set_webhook(self, url=None, **kwargs):
        return await self._call("set_webhook", url=url, **kwargs)

    async def get_file(self, file_id, **kwargs):
        return await self._call("get_file", file_id=file_id)


def _mk_reply_markup(markup):
    if markup is None:
        return None
    if hasattr(markup, "to_dict"):
        return markup.to_dict()
    if isinstance(markup, dict):
        return markup
    return markup


# ===================================================================
# Fake Dispatcher — long-polling loop با ptb Bot
# ===================================================================

async def _dispatch_loop(bot_wrapper, owner_id: int):
    from database import Database
    from aiogram import Dispatcher
    from aiogram.fsm.storage.memory import MemoryStorage
    from fsm_storage import SQLiteStorage
    from handlers_user import create_user_router
    from handlers_admin import create_admin_router
    from blocked_user import BlockedUserMiddleware as _BUM
    from force_join import ForceJoinMiddleware as _FJM

    # AdminPresenceMiddleware — نسخه سادهشده بدون وابستگی به bot_manager
    class _AdminPresenceMiddleware:
        PRESENCE_WRITE_INTERVAL = 20  # ثانیه
        def __init__(self, db):
            self.db = db
            self._last_write = {}
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

    _APM = _AdminPresenceMiddleware

    db_path = os.getenv("BALE_DB_PATH") or DB_PATH
    db_obj = Database(db_path)
    db_obj.init_db(owner_id=owner_id)

    fsm_db_path = f"{db_path}.fsm.sqlite3"
    try:
        fsm_storage = SQLiteStorage(fsm_db_path)
    except Exception:
        logger.exception("ساخت SQLiteStorage ناموفق؛ استفاده از MemoryStorage.")
        fsm_storage = MemoryStorage()

    dp = Dispatcher(storage=fsm_storage)
    dp._bot = bot_wrapper  # تزریق bot به روترها
    dp.include_router(create_user_router(db_obj))
    dp.include_router(create_admin_router(db_obj))

    blocked_mw = _BUM(db_obj)
    presence_mw = _APM(db_obj)
    force_join_mw = _FJM(db_obj)
    # Middleware روی Dispatcher ثبت میشود نه Router
    dp.outer_middleware(blocked_mw)
    dp.outer_middleware(presence_mw)
    dp.outer_middleware(force_join_mw)

    @dp.errors.register
    async def error_handler(error, update):
        logger.error("خطای پردازشنشده: %s", error, exc_info=error)
        cb = update.callback_query if update else None
        if cb:
            try:
                await cb.answer("⚠️ خطایی رخ داد، دوباره تلاش کنید.", show_alert=True)
            except Exception:
                pass

    logger.info("ربات بله آماده شد. شروع polling…")

    offset = -1  # -1 bootstrap: first poll fetches last known ID, no updates lost
    while True:
        try:
            updates = await bot_wrapper.get_updates(offset=offset, limit=100, timeout=10)
            if updates:
                for raw_upd in updates:
                    update = _fake_update(raw_upd)
                    offset = max(offset, raw_upd.update_id) + 1
                    msg = update.effective_message
                    logger.info(
                        "آپدیت #%s | msg=%s text=%r chat=%s user=%s",
                        update.update_id,
                        bool(msg),
                        (msg.text or "")[:60] if msg else None,
                        msg.chat.id if msg else None,
                        msg.from_user.id if msg else None,
                    )
                    await dp._dispatch(update)
            else:
                await asyncio.sleep(0.5)
        except KeyboardInterrupt:
            break
        except Exception as e:
            logger.error("خطای polling: %s", e, exc_info=True)
            await asyncio.sleep(2)

    try:
        await fsm_storage.close()
    except Exception:
        pass
    logger.info("بات بله متوقف شد.")


def _fake_update(raw):
    """تبدیل ptb Update به fake aiogram Update."""
    from providers.__fake_aiogram import Update as FakeUpdate
    return FakeUpdate(raw)


# ===================================================================
# Main
# ===================================================================

async def main():
    token = os.getenv("BALE_TOKEN") or BALE_TOKEN
    if not token:
        logger.error("متغیر محیطی BALE_TOKEN تنظیم نشده است.")
        logger.error("لطفاً BALE_TOKEN=<your-bale-bot-token> را در .env ست کنید.")
        return

    owner_id = int(os.getenv("BALE_OWNER_ID") or BALE_OWNER_ID_RAW or OWNER_ID)
    miniapp_url = os.getenv("BALE_MINIAPP_URL") or MINIAPP_URL

    logger.info("=" * 50)
    logger.info("بات بله PatternShop در حال راهاندازی...")
    logger.info("  TOKEN  : %s…", token[:10])
    logger.info("  OWNER  : %s", owner_id)
    if miniapp_url:
        logger.info("  MiniApp: %s", miniapp_url)
    logger.info("=" * 50)

    bot = BotWrapper(token)

    try:
        me = await bot.get_me()
        logger.info("اتصال برقرار شد. بات: %s (@%s)", me.first_name, me.username or "(بدون username)")
        await bot.delete_webhook(drop_pending_updates=True)
    except Exception as e:
        logger.error("خطا در تست اتصال: %s", e)
        return

    await _dispatch_loop(bot, owner_id)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nبات بله متوقف شد.")
