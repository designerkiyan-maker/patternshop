# -*- coding: utf-8 -*-
"""
پیاده‌سازی ساده و سبک یک FSM Storage پایدار (روی دیسک، با SQLite) برای aiogram،
جایگزین MemoryStorage پیش‌فرض.

چرا لازم است؟
--------------
MemoryStorage تمام state‌های در حال انتظار (مثلاً «کاربر منتظر ارسال عکس
رسید پرداخت است») را فقط در RAM نگه می‌دارد. با هر ری‌استارت پروسه‌ی بات -
دیپلوی جدید، کرش، ری‌استارت سرویس توسط manage.sh، یا حتی استارت/استاپ یک
بات نمایندگی توسط BotManager.reconcile_resellers_loop - همه‌ی این state‌ها
یک‌جا پاک می‌شوند. اگر دقیقاً در آن لحظه کاربری عکس رسید پرداختش را بفرستد،
هیچ هندلری با state آن مطابقت پیدا نمی‌کند و پیام (بدون هیچ خطا یا لاگی)
نادیده گرفته می‌شود - از دید کاربر و ادمین انگار رسید اصلاً ارسال نشده.

این کلاس دقیقاً همان رفتار MemoryStorage (state + data به‌ازای هر
(bot, chat, user, ...)) را پیاده‌سازی می‌کند اما روی یک فایل SQLite کنار
دیتابیس اصلی همان بات ذخیره می‌شود، پس با ری‌استارت پروسه از بین نمی‌رود.

عمداً از sqlite3 استاندارد (synchronous) استفاده شده - دقیقاً هم‌سو با سبک
database.py در همین پروژه - چون عملیات‌های state (خواندن/نوشتن چند بایت)
آن‌قدر سریع هستند که مسدودکردن کوتاه event loop قابل چشم‌پوشی است، در حالی
که وابستگی جدید (مثل Redis) به پروژه اضافه نمی‌کند.
"""

import json
import sqlite3
from typing import Any, Dict, Optional

from aiogram.fsm.storage.base import BaseStorage, StorageKey


class SQLiteStorage(BaseStorage):
    def __init__(self, db_path: str):
        self._conn = sqlite3.connect(db_path, check_same_thread=False, timeout=30)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA busy_timeout=4000")
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS fsm_storage (
                bot_id INTEGER NOT NULL,
                chat_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                thread_id INTEGER,
                business_connection_id TEXT,
                destiny TEXT NOT NULL DEFAULT 'default',
                state TEXT,
                data TEXT,
                PRIMARY KEY (bot_id, chat_id, user_id, thread_id, business_connection_id, destiny)
            )
            """
        )
        self._conn.commit()

    @staticmethod
    def _key_tuple(key: StorageKey):
        # نکته‌ی مهم: در SQL دو مقدار NULL هیچ‌وقت «برابر» در نظر گرفته نمی‌شوند،
        # پس اگر thread_id/business_connection_id را NULL نگه داریم، تشخیص
        # تعارض PRIMARY KEY توسط ON CONFLICT کار نمی‌کند و هر بار یک ردیف
        # جدید insert می‌شود (به‌جای آپدیت همان ردیف) - این‌ها معمولاً NULL
        # هستند (چت خصوصی معمولی)، پس با یک مقدار جایگزین (0 / رشته‌ی خالی)
        # ذخیره می‌شوند تا مقایسه‌ی تساوی درست کار کند.
        thread_id = getattr(key, "thread_id", None)
        business_connection_id = getattr(key, "business_connection_id", None)
        return (
            key.bot_id,
            key.chat_id,
            key.user_id,
            thread_id if thread_id is not None else 0,
            business_connection_id if business_connection_id is not None else "",
            getattr(key, "destiny", "default"),
        )

    async def set_state(self, key: StorageKey, state: Any = None) -> None:
        state_value = state.state if hasattr(state, "state") else state
        row = self._key_tuple(key)
        self._conn.execute(
            "INSERT INTO fsm_storage "
            "(bot_id, chat_id, user_id, thread_id, business_connection_id, destiny, state) "
            "VALUES (?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT (bot_id, chat_id, user_id, thread_id, business_connection_id, destiny) "
            "DO UPDATE SET state=excluded.state",
            (*row, state_value),
        )
        self._conn.commit()

    async def get_state(self, key: StorageKey) -> Optional[str]:
        row = self._key_tuple(key)
        cur = self._conn.execute(
            "SELECT state FROM fsm_storage WHERE bot_id=? AND chat_id=? AND user_id=? "
            "AND thread_id=? AND business_connection_id=? AND destiny=?",
            row,
        )
        r = cur.fetchone()
        return r[0] if r else None

    async def set_data(self, key: StorageKey, data: Dict[str, Any]) -> None:
        row = self._key_tuple(key)
        payload = json.dumps(data or {}, ensure_ascii=False)
        self._conn.execute(
            "INSERT INTO fsm_storage "
            "(bot_id, chat_id, user_id, thread_id, business_connection_id, destiny, data) "
            "VALUES (?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT (bot_id, chat_id, user_id, thread_id, business_connection_id, destiny) "
            "DO UPDATE SET data=excluded.data",
            (*row, payload),
        )
        self._conn.commit()

    async def get_data(self, key: StorageKey) -> Dict[str, Any]:
        row = self._key_tuple(key)
        cur = self._conn.execute(
            "SELECT data FROM fsm_storage WHERE bot_id=? AND chat_id=? AND user_id=? "
            "AND thread_id=? AND business_connection_id=? AND destiny=?",
            row,
        )
        r = cur.fetchone()
        if not r or not r[0]:
            return {}
        try:
            return json.loads(r[0])
        except (TypeError, ValueError):
            return {}

    async def close(self) -> None:
        self._conn.close()
