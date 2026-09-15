# -*- coding: utf-8 -*-
"""
لایهی سازگاری Bale ↔ aiogram 3.x

هدف: اجرای بدون تغییر handlers_user.py / handlers_admin.py روی بات بله.
روش: یک بستهی ساختگیِ aiogram (pep-562 sub-module) مینویسیم که انواع
aiogram (Router, Message, CallbackQuery, F, StateFilter, CommandStart و …)
را از دادههای python-telegram-bot v22 میسازد.

چرا این روش؟
------------
کپی و بازنویسی ~۴۳۰۰ خط handler با سینتکس ptb حجم زیادی کار و ریسک باگ
میتواند داشته باشد. با یک لایهی سازگاری سبک، کدهای فعلی بدون تغییر و
فقط با runtime-wrapper اجرا میشوند.

محدودیتهای موجود:
- دکمههای copy_text bale بدون مشکل کار میکنند (ptb 22 پشتیبانی میکند).
- پرداخت in-chat با provider_token Bale فقط در صورت تنظیم provider_token
  در Bot constructor قابل تست است.
- دکمهی WebApp فقط با URL معتبر Bale Mini App کار میکند.
"""

from __future__ import annotations

import asyncio
import functools
import logging
import re
import sys
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, Union

logger = logging.getLogger(__name__)

# ===================================================================
# BotWrapper — wraps telegram.Bot and exposes aiogram-like interface
# ===================================================================

class BotWrapper:
    """Wrapper around telegram.Bot providing aiogram-compatible API."""

    def __init__(self, bot, db_path: str = ""):
        self._bot = bot
        self._db_path = db_path
        self.startup_time = 0
        self.token = bot.token
        # For compatibility with code that does bot.session or similar
        self._session = getattr(bot, '_request', None)

    @property
    def session(self):
        return self._session

    async def _call(self, method, *args, **kwargs):
        """Call a Bot method, translating exceptions."""
        fn = getattr(self._bot, method)
        coro = fn(*args, **kwargs)
        try:
            return await coro
        except Exception as e:
            translated = _translate_ptb_exception(e)
            raise translated

    async def send_message(self, chat_id, text, parse_mode=None, entities=None,
                           reply_markup=None, protect_content=None,
                           message_thread_id=None, reply_parameters=None,
                           business_connection_id=None, disable_notification=None,
                           **kwargs):
        kwargs["text"] = text
        kwargs["chat_id"] = int(chat_id)
        if parse_mode: kwargs["parse_mode"] = parse_mode
        if reply_markup: kwargs["reply_markup"] = _mk(reply_markup)
        if protect_content is not None: kwargs["protect_content"] = protect_content
        if disable_notification is not None: kwargs["disable_notification"] = disable_notification
        if message_thread_id: kwargs["message_thread_id"] = int(message_thread_id)
        return await self._call("send_message", **kwargs)

    async def send_photo(self, chat_id, photo, caption=None, parse_mode=None,
                         reply_markup=None, protect_content=None, has_spoiler=None,
                         **kwargs):
        kwargs["photo"] = photo
        kwargs["chat_id"] = int(chat_id)
        if caption: kwargs["caption"] = caption
        if parse_mode: kwargs["parse_mode"] = parse_mode
        if reply_markup: kwargs["reply_markup"] = _mk(reply_markup)
        if protect_content is not None: kwargs["protect_content"] = protect_content
        if has_spoiler is not None: kwargs["has_spoiler"] = has_spoiler
        return await self._call("send_photo", **kwargs)

    async def send_document(self, chat_id, document, caption=None, parse_mode=None,
                            reply_markup=None, protect_content=None,
                            **kwargs):
        kwargs["document"] = document
        kwargs["chat_id"] = int(chat_id)
        if caption: kwargs["caption"] = caption
        if parse_mode: kwargs["parse_mode"] = parse_mode
        if reply_markup: kwargs["reply_markup"] = _mk(reply_markup)
        if protect_content is not None: kwargs["protect_content"] = protect_content
        return await self._call("send_document", **kwargs)

    async def send_dice(self, chat_id, emoji="🎲", reply_markup=None,
                        disable_notification=None, **kwargs):
        kwargs["emoji"] = emoji
        kwargs["chat_id"] = int(chat_id)
        if reply_markup: kwargs["reply_markup"] = _mk(reply_markup)
        if disable_notification is not None: kwargs["disable_notification"] = disable_notification
        return await self._call("send_dice", **kwargs)

    async def edit_message_text(self, text, chat_id=None, message_id=None,
                                inline_message_id=None, parse_mode=None,
                                reply_markup=None, **kwargs):
        kwargs["text"] = text
        if chat_id is not None: kwargs["chat_id"] = int(chat_id)
        if message_id is not None: kwargs["message_id"] = int(message_id)
        if inline_message_id: kwargs["inline_message_id"] = inline_message_id
        if parse_mode: kwargs["parse_mode"] = parse_mode
        if reply_markup: kwargs["reply_markup"] = _mk(reply_markup)
        return await self._call("edit_message_text", **kwargs)

    async def delete_message(self, chat_id, message_id, **kwargs):
        return await self._call("delete_message", chat_id=int(chat_id),
                                 message_id=int(message_id), **kwargs)

    async def get_updates(self, offset=None, limit=None, timeout=None,
                          allowed_updates=None, **kwargs):
        return await self._call("get_updates", offset=offset, limit=limit,
                                timeout=timeout, allowed_updates=allowed_updates, **kwargs)

    async def get_me(self, **kwargs):
        return await self._call("get_me", **kwargs)

    async def delete_webhook(self, drop_pending_updates=None, **kwargs):
        return await self._call("delete_webhook", drop_pending_updates=drop_pending_updates, **kwargs)

    async def set_webhook(self, url=None, certificate=None, ip_address=None,
                          max_connections=None, allowed_updates=None,
                          drop_pending_updates=None, secret_token=None, **kwargs):
        kwargs["url"] = url
        return await self._call("set_webhook", **kwargs)

    async def get_file(self, file_id, **kwargs):
        return await self._call("get_file", file_id=file_id, **kwargs)

    async def export_chat_invite_link(self, chat_id, **kwargs):
        return await self._call("export_chat_invite_link", chat_id=int(chat_id), **kwargs)

    async def get_chat_member(self, chat_id, user_id, **kwargs):
        """میانبر برای force_join middleware — وضعیت عضویت کاربر در چت/کانال."""
        from telegram import ChatMember
        result = await self._bot.get_chat_member(chat_id=int(chat_id), user_id=int(user_id))
        # برگرداندن یک شیء با خاصیت status (مشابه aiogram)
        class _Member:
            def __init__(self, m):
                self.status = m.status
                self.user = m.user
        return _Member(result)

    async def edit_message_caption(self, caption, chat_id=None, message_id=None,
                                    inline_message_id=None, reply_markup=None, **kwargs):
        args = {"caption": caption}
        if chat_id is not None: args["chat_id"] = int(chat_id)
        if message_id is not None: args["message_id"] = int(message_id)
        if inline_message_id: args["inline_message_id"] = inline_message_id
        if reply_markup: args["reply_markup"] = _mk(reply_markup)
        return await self._call("edit_message_caption", **args)

    async def answer_callback_query(self, text="", show_alert=False, url="",
                                     cache_time=0, **kwargs):
        """معادل call.answer() — از طریق bot.call_answer."""
        try:
            await self._bot.answer_callback_query(callback_query_id=kwargs.get("callback_query_id"),
                                                   text=text, show_alert=show_alert, url=url)
        except Exception:
            pass

    # --- Helper aliases ---
    @functools.cached_property
    def loop(self):
        return asyncio.get_event_loop()


def _mk(markup):
    """Convert fake keyboard objects → ptb dict/tuple format."""
    if markup is None:
        return None
    if hasattr(markup, "to_dict"):
        return markup.to_dict()
    if isinstance(markup, dict):
        return markup
    return markup


# ===================================================================
# PTB Exception translation
# ===================================================================

def _translate_ptb_exception(exc):
    """Convert a ptb exception to the nearest aiogram-equivalent."""
    try:
        from telegram import error as ptb_error
    except ImportError:
        return exc
    if isinstance(exc, ptb_error.RetryAfter):
        retry = getattr(exc, "retry_after", 30)
        return TelegramRetryAfter(retry)
    if isinstance(exc, ptb_error.Forbidden):
        return TelegramForbiddenError(str(exc))
    if isinstance(exc, ptb_error.BadRequest):
        return TelegramBadRequest(str(exc))
    if isinstance(exc, ptb_error.NetworkError):
        return TelegramNetworkError(str(exc))
    return exc


# ===================================================================
# Types – wrappers around telegram.* objects
# ===================================================================

class _Proxy:
    """هر شیء wrapper از این مشتق شود، خاصیت getattr غریب → None برمیگرداند."""
    def __getattribute__(self, name: str) -> Any:
        if name.startswith("_"):
            return object.__getattribute__(self, name)
        try:
            return object.__getattribute__(self, name)
        except AttributeError:
            return None


# --- User ---
class User(_Proxy):
    __slots__ = ("id", "is_bot", "first_name", "last_name", "username",
                 "language_code", "_raw")

    def __init__(self, user):
        self._raw = user
        self.id = int(user.id)
        self.is_bot = bool(user.is_bot)
        self.first_name = user.first_name or ""
        self.last_name = user.last_name or ""
        self.username = user.username or ""
        self.language_code = user.language_code or ""

    def __repr__(self):
        return f"User(id={self.id}, first_name={self.first_name!r})"


# --- Chat ---
class Chat(_Proxy):
    __slots__ = ("id", "type", "title", "username", "_raw")

    def __init__(self, chat):
        self._raw = chat
        self.id = int(chat.id)
        self.type = chat.type
        self.title = chat.title or ""
        self.username = chat.username or ""

    def __repr__(self):
        return f"Chat(id={self.id}, type={self.type!r})"


# --- Message ---
class Message(_Proxy):
    __slots__ = (
        "message_id", "date", "chat", "from_user", "sender_chat",
        "text", "entities", "photo", "document", "voice", "video",
        "audio", "animation", "sticker", "contact", "location",
        "reply_markup", "reply_to_message", "forward_from",
        "forward_from_chat", "edit_date", "has_protected_content",
        "success_payment", "_raw",
    )

    def __init__(self, msg):
        self._raw = msg
        self.message_id = int(msg.message_id) if hasattr(msg, "message_id") else 0
        self.date = msg.date or 0
        self.chat = Chat(msg.chat) if hasattr(msg, "chat") and msg.chat else None
        self.from_user = User(msg.from_user) if hasattr(msg, "from_user") and msg.from_user else None
        self.sender_chat = Chat(msg.sender_chat) if hasattr(msg, "sender_chat") and msg.sender_chat else None
        self.text = msg.text or ""
        self.entities = [e.to_dict() for e in msg.entities] if hasattr(msg, "entities") and msg.entities else []
        self.photo = [p.to_dict() for p in msg.photo] if hasattr(msg, "photo") and msg.photo else []
        self.document = msg.document.to_dict() if hasattr(msg, "document") and msg.document else None
        self.voice = msg.voice.to_dict() if hasattr(msg, "voice") and msg.voice else None
        self.video = msg.video.to_dict() if hasattr(msg, "video") and msg.video else None
        self.audio = msg.audio.to_dict() if hasattr(msg, "audio") and msg.audio else None
        self.animation = msg.animation.to_dict() if hasattr(msg, "animation") and msg.animation else None
        self.sticker = msg.sticker.to_dict() if hasattr(msg, "sticker") and msg.sticker else None
        self.contact = msg.contact.to_dict() if hasattr(msg, "contact") and msg.contact else None
        self.location = msg.location.to_dict() if hasattr(msg, "location") and msg.location else None
        self.reply_markup = msg.reply_markup.to_dict() if hasattr(msg, "reply_markup") and msg.reply_markup else None
        if hasattr(msg, "reply_to_message") and msg.reply_to_message:
            self.reply_to_message = Message(msg.reply_to_message)
        else:
            self.reply_to_message = None
        self.forward_from = User(msg.forward_from) if hasattr(msg, "forward_from") and msg.forward_from else None
        self.forward_from_chat = Chat(msg.forward_from_chat) if hasattr(msg, "forward_from_chat") and msg.forward_from_chat else None
        self.edit_date = msg.edit_date or 0
        self.has_protected_content = bool(getattr(msg, "has_protected_content", False))
        # Successful payment (for invoice flow)
        sp = getattr(msg, "successful_payment", None)
        if sp is not None:
            self.successful_payment = _SuccessfulPayment(sp)
        else:
            self.successful_payment = None

    @property
    def effective_user(self):
        return self.from_user or self.sender_chat

    @property
    def effective_chat(self):
        return self.chat

    def answer(self, text, **kwargs):
        """shim: همان send_message با reply."""
        return self._raw.reply_text(text, **kwargs)

    def delete(self):
        return self._raw.delete()

    def edit_text(self, text, **kwargs):
        return self._raw.edit_text(text, **kwargs)

    def __repr__(self):
        return f"Message(id={self.message_id}, chat={self.chat}, text={self.text!r})"


class _SuccessfulPayment:
    """Wrapper around telegram.SuccessfulPayment for handler compatibility."""
    def __init__(self, raw):
        self._raw = raw
        self.invoice_payload = getattr(raw, "invoice_payload", "")
        self.telegram_payment_charge_id = getattr(raw, "telegram_payment_charge_id", "")
        self.provider_payment_charge_id = getattr(raw, "provider_payment_charge_id", "")
        self.currency = getattr(raw, "currency", "")
        self.total_amount = getattr(raw, "total_amount", 0)
        self.invoice_payload = getattr(raw, "invoice_payload", "")
        self.shipping_option_id = getattr(raw, "shipping_option_id", None)
        self.order_info = getattr(raw, "order_info", None)

    def __repr__(self):
        return f"SuccessfulPayment(payload={self.invoice_payload!r})"


# --- CallbackQuery ---
class CallbackQuery(_Proxy):
    __slots__ = ("id", "data", "message", "from_user", "chat_instance", "_raw")

    def __init__(self, cb):
        self._raw = cb
        self.id = cb.id or ""
        self.data = cb.data or ""
        raw_msg = getattr(cb, "message", None)
        self.message = Message(raw_msg) if raw_msg is not None else None
        self.from_user = User(cb.from_user) if hasattr(cb, "from_user") and cb.from_user else None
        self.chat_instance = cb.chat_instance or ""

    async def answer(self, text="", show_alert=False, url="", **kwargs):
        await self._raw.answer(text=text, show_alert=show_alert, url=url, **kwargs)

    def __repr__(self):
        return f"CallbackQuery(id={self.id!r}, data={self.data!r})"


# --- Update ---
class Update:
    __slots__ = ("update_id", "message", "edited_message", "callback_query", "_raw", "_fsm_key")

    def __init__(self, raw_update):
        self._raw = raw_update
        self.update_id = int(raw_update.update_id)
        raw_msg = getattr(raw_update, "message", None)
        self.message = Message(raw_msg) if raw_msg else None
        raw_cb = getattr(raw_update, "callback_query", None)
        self.callback_query = CallbackQuery(raw_cb) if raw_cb else None

    @property
    def effective_message(self):
        return self.message or (self.callback_query.message if self.callback_query else None)

    @property
    def effective_user(self):
        if self.message and self.message.from_user:
            return self.message.from_user
        if self.callback_query and self.callback_query.from_user:
            return self.callback_query.from_user
        return None

    @property
    def effective_chat(self):
        if self.message and self.message.chat:
            return self.message.chat
        return None


# --- MenuButton, WebAppInfo, etc. ---
class MenuButtonWebApp:
    __slots__ = ("text", "web_app")
    def __init__(self, text: str, web_app: "WebAppInfo"):
        self.text = text
        self.web_app = web_app

class WebAppInfo:
    __slots__ = ("url",)
    def __init__(self, url: str):
        self.url = url

class MenuButtonDefault:
    pass


# ===================================================================
# Keyboard types
# ===================================================================

class InlineKeyboardMarkup:
    __slots__ = ("inline_keyboard",)
    def __init__(self, inline_keyboard: list):
        self.inline_keyboard = inline_keyboard
    def to_dict(self):
        return {"inline_keyboard": self.inline_keyboard}

class InlineKeyboardButton:
    __slots__ = ("text", "callback_data", "url", "web_app", "copy_text", "style")
    def __init__(self, text: str, callback_data=None, url=None,
                 web_app=None, copy_text=None, style=None):
        self.text = text
        self.callback_data = callback_data
        self.url = url
        self.web_app = web_app
        self.copy_text = copy_text
        self.style = style
    def to_dict(self):
        d = {"text": self.text}
        if self.callback_data is not None:
            d["callback_data"] = self.callback_data
        if self.url is not None:
            d["url"] = self.url
        if self.web_app is not None:
            d["web_app"] = {"url": self.web_app.url}
        if self.copy_text is not None:
            d["copy_text"] = self.copy_text
        if self.style:
            d["style"] = self.style
        return d

class ReplyKeyboardMarkup:
    __slots__ = ("keyboard", "resize_keyboard", "one_time_keyboard",
                 "input_field_placeholder", "is_persistent")
    def __init__(self, keyboard=None, resize_keyboard=False,
                 one_time_keyboard=False, input_field_placeholder=None,
                 is_persistent=None):
        self.keyboard = keyboard or []
        self.resize_keyboard = resize_keyboard
        self.one_time_keyboard = one_time_keyboard
        self.input_field_placeholder = input_field_placeholder
        self.is_persistent = is_persistent
    def to_dict(self):
        d = {"keyboard": self.keyboard}
        if self.resize_keyboard: d["resize_keyboard"] = True
        if self.one_time_keyboard: d["one_time_keyboard"] = True
        if self.input_field_placeholder:
            d["input_field_placeholder"] = self.input_field_placeholder
        if self.is_persistent: d["is_persistent"] = True
        return d

class KeyboardButton:
    __slots__ = ("text", "url", "web_app", "request_contact",
                 "request_location", "style")
    def __init__(self, text: str, userinfo=None, url=None, web_app=None,
                 request_contact=False, request_location=False, style=None):
        self.text = text
        self.userinfo = userinfo
        self.url = url
        self.web_app = web_app
        self.request_contact = request_contact
        self.request_location = request_location
        self.style = style
    def to_dict(self):
        d = {"text": self.text}
        if self.url: d["url"] = self.url
        if self.web_app: d["web_app"] = {"url": self.web_app.url}
        if self.request_contact: d["request_contact"] = True
        if self.request_location: d["request_location"] = True
        if self.style: d["style"] = self.style
        return d

class ReplyKeyboardRemove:
    def __init__(self, selective=False):
        self.selective = selective
    def to_dict(self):
        return {"remove_keyboard": True, "selective": self.selective}

class ForceReply:
    def __init__(self, selective=False):
        self.selective = selective
    def to_dict(self):
        return {"force_reply": True, "selective": self.selective}


# ===================================================================
# FSM types
# ===================================================================

class State:
    __slots__ = ("state",)
    def __init__(self, state: str = "default"):
        self.state = state
    def __repr__(self):
        return f"State({self.state!r})"
    def __eq__(self, other):
        if isinstance(other, State):
            return self.state == other.state
        return False
    def __hash__(self):
        return hash(self.state)

class StatesGroup:
    """Namespace برای Stateها."""
    pass

class FSMContext:
    """نسخهی ساده FSMContext — state + data روی dict external ذخیره میشود."""

    def __init__(self, storage: "BaseStorage", key: tuple):
        self._storage = storage
        self._key = key

    async def set_state(self, state: Optional[Union[State, str]] = None):
        s = state.state if isinstance(state, State) else state
        await self._storage.set_state(self._key, s)

    async def get_state(self) -> Optional[str]:
        return await self._storage.get_state(self._key)

    async def set_data(self, data: dict):
        await self._storage.set_data(self._key, data)

    async def get_data(self) -> dict:
        return await self._storage.get_data(self._key)

    async def update_data(self, data: dict):
        cur = await self._storage.get_data(self._key)
        cur.update(data)
        await self._storage.set_data(self._key, cur)

    async def clear(self):
        await self._storage.set_state(self._key, None)
        await self._storage.set_data(self._key, {})

    def __repr__(self):
        return f"FSMContext(key={self._key!r})"


# ===================================================================
# Filters
# ===================================================================

class Filter:
    async def check(self, update: Update) -> bool:
        raise NotImplementedError
    def __or__(self, other):
        return OrFilter(self, other)
    def __and__(self, other):
        import asyncio as _asyncio
        class _AndFilter(Filter):
            def __init__(a, f1, f2):
                a.f1 = f1
                a.f2 = f2
            async def check(a, update):
                r1 = a.f1.check(update)
                r2 = a.f2.check(update)
                if _asyncio.iscoroutine(r1): r1 = await r1
                if _asyncio.iscoroutine(r2): r2 = await r2
                return r1 and r2
        return _AndFilter(self, other)
    def __invert__(self):
        import asyncio as _asyncio
        class _NotFilter(Filter):
            def __init__(inner_self, f):
                inner_self.f = f
            async def check(inner_self, update):
                r = inner_self.f.check(update)
                if _asyncio.iscoroutine(r): r = await r
                return not r
        return _NotFilter(self)

class TextFilter(Filter):
    def __init__(self, keywords=None, ignore_case=False):
        self.keywords = keywords or []
        self.ignore_case = ignore_case
    async def check(self, update):
        msg = update.effective_message
        if not msg or not msg.text:
            return False
        t = msg.text if not self.ignore_case else msg.text.lower()
        for kw in self.keywords:
            if self.ignore_case:
                kw = kw.lower()
            if kw in t:
                return True
        return False

class CommandFilter(Filter):
    def __init__(self, commands):
        self.commands = set(commands) if isinstance(commands, (list, tuple, set)) else {commands}
    async def check(self, update):
        msg = update.effective_message
        if not msg or not msg.text:
            return False
        parts = msg.text.split(maxsplit=1)
        cmd = parts[0].lstrip("/")
        if "@" in cmd:
            cmd = cmd.split("@", 1)[0]
        return cmd.lower() in self.commands

class StateFilter(Filter):
    def __init__(self, *states):
        self.states = states
    async def check(self, update):
        fsm_key = getattr(update, "_fsm_key", None)
        if not fsm_key:
            return False
        state = await fsm_key.get_state()
        for s in self.states:
            if isinstance(s, State):
                if state == s.state:
                    return True
            elif state == s:
                return True
        return False

class PhotoFilter(Filter):
    async def check(self, update):
        msg = update.effective_message
        return bool(msg and msg.photo)

class DocumentFilter(Filter):
    async def check(self, update):
        msg = update.effective_message
        return bool(msg and msg.document)

class RegexFilter(Filter):
    def __init__(self, pattern):
        self._re = re.compile(pattern)
    async def check(self, update):
        msg = update.effective_message
        if not msg or not msg.text:
            return False
        return bool(self._re.match(msg.text))

class CallbackDataFilter(Filter):
    def __init__(self, value_or_prefix):
        self.value = value_or_prefix
    async def check(self, update):
        cb = update.callback_query
        if not cb or not cb.data:
            return False
        if ":" in self.value:
            prefix = self.value.split(":")[0]
            return cb.data.startswith(prefix + ":")
        return cb.data == self.value
    def __or__(self, other):
        return OrFilter(self, other)
    def __and__(self, other):
        class _AndFilter(Filter):
            def __init__(inner_self, a, b):
                inner_self.a = a
                inner_self.b = b
            async def check(inner_self, update):
                r1 = self.a.check(update)
                r2 = self.b.check(update)
                import asyncio
                if asyncio.iscoroutine(r1): r1 = await r1
                if asyncio.iscoroutine(r2): r2 = await r2
                return r1 and r2
        return _AndFilter(self, other)

class OrFilter(Filter):
    def __init__(self, *filters):
        self.filters = filters
    async def check(self, update):
        results = await asyncio.gather(*[f.check(update) for f in self.filters])
        return any(results)

# --- F namespace ---
class _FDataAttr:
    def __eq__(self, value):
        return CallbackDataFilter(value)
    def startswith(self, prefix):
        return CallbackDataFilter(prefix + ":")
    def __or__(self, other):
        return OrFilter(CallbackDataFilter(self._val) if hasattr(self, '_val') else self,
                        CallbackDataFilter(other) if hasattr(other, '_val') else other)

class _FTxtAttr:
    def func(self, fn):
        class _FuncFilter(Filter):
            async def check(self, update):
                msg = update.effective_message
                if not msg or not msg.text:
                    return False
                return fn(msg.text)
        return _FuncFilter()
    def startswith(self, prefix):
        class _StartsWithFilter(Filter):
            def __init__(inner_self, p):
                inner_self.p = p
            async def check(inner_self, update):
                msg = update.effective_message
                if not msg or not msg.text:
                    return False
                return msg.text.startswith(p)
        return _StartsWithFilter(prefix)
    @property
    def not_startswith(self):
        """معادل F.text ~F.text.startswith(...)"""
        class _NotStartsWithFilter(Filter):
            def __init__(inner_self, p):
                inner_self.p = p
            async def check(inner_self, update):
                msg = update.effective_message
                if not msg or not msg.text:
                    return False
                return not msg.text.startswith(self.p)
        # This won't work properly; use the ~ operator on a StartsWith filter instead
        raise NotImplementedError("use ~F.text.startswith(...) not F.text.not_startswith")

class _FNamespace:
    data = _FDataAttr()
    text = _FTxtAttr()
    photo = PhotoFilter()
    document = DocumentFilter()

F = _FNamespace()

def CommandStart():
    return CommandFilter(["start"])

def Command(cmd):
    return CommandFilter(cmd)


# ===================================================================
# Dispatcher / Router
# ===================================================================

class Handler:
    def __init__(self, callback, filters: Optional[List[Filter]] = None):
        self.callback = callback
        self.filters = filters or []

    async def check(self, update: Update) -> bool:
        for f in self.filters:
            ok = f.check(update)
            if asyncio.iscoroutine(ok):
                ok = await ok
            if not ok:
                return False
        return True

class Router:
    def __init__(self):
        self._message_handlers: List[Handler] = []
        self._cb_handlers: List[Handler] = []
        self._child_routers: List[Router] = []
        self._error_handler = None

    def message(self, *filters):
        def decorator(func):
            self._message_handlers.append(Handler(func, list(filters)))
            return func
        return decorator

    def callback_query(self, *filters):
        def decorator(func):
            self._cb_handlers.append(Handler(func, list(filters)))
            return func
        return decorator

    def error(self, func):
        self._error_handler = func
        return func

    def include_router(self, router: "Router"):
        self._child_routers.append(router)

class Dispatcher:
    def __init__(self, storage=None):
        self._router = Router()
        self._storage = storage
        self._message_outer_middlewares: List[Callable] = []
        self._cb_outer_middlewares: List[Callable] = []
        self._error_handlers: List[Callable] = []
        self._bot = None  # Set by main_bale.py before starting polling

    @property
    def router(self):
        return self._router

    def include_router(self, router: Router):
        self._router.include_router(router)

    def message(self):
        return self._router

    def callback_query(self):
        return self._router

    @property
    def errors(self):
        class ErrRegistry:
            def __init__(inner_self):
                inner_self._dp = self
            def register(inner_self, func):
                self._error_handlers.append(func)
                return func
        return ErrRegistry()

    def outer_middleware(self, mw):
        self._message_outer_middlewares.append(mw)
        self._cb_outer_middlewares.append(mw)

    @staticmethod
    def _make_handler(handler_fn):
        """Wraps a handler to inject (event, fsm_ctx, bot) regardless of its signature.
        Handlers may accept 1, 2 or 3 args — we always pass exactly 3."""
        @functools.wraps(handler_fn)
        async def _wrapped(event, fsm_ctx, bot):
            return await handler_fn(event, fsm_ctx, bot)
        return _wrapped

    async def _run_mws(self, mws, handler_fn, event, update):
        idx = [0]
        fsm_ctx = update._fsm_key if hasattr(update, "_fsm_key") else None
        bot = self._bot
        wrapped = self._make_handler(handler_fn)
        async def _inner():
            if idx[0] >= len(mws):
                return await wrapped(event, fsm_ctx, bot)
            mw = mws[idx[0]]
            idx[0] += 1
            try:
                result = await mw(
                    handler=lambda e, d: _inner(),
                    event=event,
                    data={"event_from_user": update.effective_user}
                )
                return result
            except Exception as e:
                logger.error("Middleware error: %s", e, exc_info=True)
                return await wrapped(event, fsm_ctx, bot)
        return await _inner()

    async def _dispatch(self, update: Update):
        if update.effective_user:
            key = (update.effective_user.id,
                   update.effective_chat.id if update.effective_chat else 0)
            fsm_ctx = FSMContext(self._storage, key) if self._storage else None
            update._fsm_key = fsm_ctx  # type: ignore[attr-defined]

        # callback_query
        if update.callback_query:
            cb = update.callback_query
            for router in self._router._child_routers + [self._router]:
                for h in router._cb_handlers:
                    ok = h.check(update)
                    if asyncio.iscoroutine(ok):
                        ok = await ok
                    if ok:
                        try:
                            await self._run_mws(self._cb_outer_middlewares,
                                                h.callback, cb, update)
                        except Exception as e:
                            await self._handle_error(e, update)
                        return

        # message
        if update.message:
            msg = update.message
            for router in self._router._child_routers + [self._router]:
                for h in router._message_handlers:
                    ok = h.check(update)
                    if asyncio.iscoroutine(ok):
                        ok = await ok
                    if ok:
                        try:
                            await self._run_mws(self._message_outer_middlewares,
                                                h.callback, msg, update)
                        except Exception as e:
                            await self._handle_error(e, update)
                        return

    async def _handle_error(self, error, update):
        for eh in self._error_handlers:
            try:
                result = eh(error, update)
                if asyncio.iscoroutine(result):
                    await result
            except Exception:
                logger.exception("Error handler failed")

    async def start_polling(self, bot, allowed_updates=None, timeout=10,
                            bootstrap_retries=0, drop_pending_updates=None):
        logger.info("شروع polling بله…")
        offset = 0
        limit = 100
        while True:
            try:
                params = {"offset": offset, "limit": limit, "timeout": timeout}
                if allowed_updates:
                    params["allowed_updates"] = allowed_updates
                updates = await bot.get_updates(**params)
                if updates:
                    for raw_upd in updates:
                        update = Update(raw_upd)
                        offset = max(offset, raw_upd.update_id) + 1
                        await self._dispatch(update)
                else:
                    await asyncio.sleep(0.5)
            except Exception as e:
                logger.error("Polling error: %s", e, exc_info=True)
                await asyncio.sleep(2)


# ===================================================================
# Exceptions
# ===================================================================

class TelegramException(Exception): pass

class TelegramRetryAfter(TelegramException):
    def __init__(self, retry_after):
        self.retry_after = retry_after
        super().__init__(f"Flood control: retry after {retry_after}s")

class TelegramForbiddenError(TelegramException): pass
class TelegramBadRequest(TelegramException): pass
class TelegramNetworkError(TelegramException): pass


# ===================================================================
# Storage shims
# ===================================================================

class BaseStorage:
    """Shim for aiogram.fsm.storage.base.BaseStorage."""
    pass

class StorageKey:
    def __init__(self, bot_id: int, chat_id: int, user_id: int):
        self.bot_id = bot_id
        self.chat_id = chat_id
        self.user_id = user_id
    def __hash__(self):
        return hash((self.bot_id, self.chat_id, self.user_id))
    def __eq__(self, other):
        return (isinstance(other, StorageKey) and self.bot_id == other.bot_id
                and self.chat_id == other.chat_id and self.user_id == other.user_id)


# ===================================================================
# Middleware base class
# ===================================================================

class BaseMiddleware:
    """پایه میدلوییر — مشتق‌ها فقط __call__ را پیاده میکنند.
    در Bale نیازی به init اختیاری superclass نیست."""
    def __init__(self):
        pass


# ===================================================================
# Misc
# ===================================================================

_global_dispatcher: Optional[Dispatcher] = None

def set_global_dispatcher(dp: Dispatcher) -> None:
    global _global_dispatcher
    _global_dispatcher = dp

def get_global_dispatcher() -> Dispatcher:
    return _global_dispatcher


# ===================================================================
# Memory storage (simple in-memory FSM for Bale bot)
# ===================================================================

class MemoryStorage:
    """نسخهی سادهی FSM Storage — state + data در RAM ذخیره میشود."""
    def __init__(self):
        self._states = {}
        self._data = {}
    async def set_state(self, key, state=None):
        self._states[key] = state
    async def get_state(self, key):
        return self._states.get(key)
    async def set_data(self, key, data=None):
        if data is not None:
            self._data[key] = data
    async def get_data(self, key):
        return self._data.get(key, {})
    async def close(self):
        pass


# ===================================================================
# Final re-export aliases (must be last for `from aiogram import X` to work)
# ===================================================================

Bot = BotWrapper          # from aiogram import Bot
TelegramObject = object   # base type placeholder
FSInputFile = str         # simple alias (Bale handles file uploads natively)

# Dummy providers for unused Telegram-specific symbols
class DefaultBotProperties:
    parse_mode: str = "HTML"
    protect_content: bool = False
    link_preview_is_disabled: bool = False
    allow_sending_without_reply: bool = False

class ParseMode:
    HTML = "HTML"
    MARKDOWN = "Markdown"
    MARKDOWNV2 = "MarkdownV2"

# ErrorEvent used for Telegram bot global error handler; Bale bot ignores it
class ErrorEvent:
    """Fake ErrorEvent type annotation holder."""
    def __init__(self, update=None):
        self.update = update
    def __repr__(self):
        return "ErrorEvent"
