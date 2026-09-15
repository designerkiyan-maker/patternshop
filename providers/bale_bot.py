# -*- coding: utf-8 -*-
"""
سازگارساز بات بله (Bale Bot Adapter).

بات بله از همان کتابخانهی python-telegram-bot استفاده میکند، فقط آدرس
پایهی API متفاوت است:
  - Bot API : https://tapi.bale.ai/bot<TOKEN>
  - File API: https://tapi.bale.ai/file/bot<TOKEN>

تمام فیلدهای update (message.chat_id, callback_query.from_user.id و …)
دقیقاً مشابه تلگرام هستند. تنها تفاوت عملیاتی:
  • دکمهی copy_text در bale پشتیبانی میشود (بدون نیاز به تغییر handler).
  • آدرس فایلها با base_file_url مشخص میشود.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# ثابتها
# ---------------------------------------------------------------------------
BALE_API_BASE = "https://tapi.bale.ai/bot"
BALE_FILE_BASE = "https://tapi.bale.ai/file/bot"

# URL منوی شیشهای باله برای منوی اصلی (در صورت تنظیم بودن).
# اگر خالی باشد، دکمهی منو نشان داده نمیشود.
BALE_MINIAPP_URL: str = ""


@dataclass
class BaleConfig:
    """تنظیمات یک بات بله."""

    token: str
    owner_id: int
    db_path: str
    miniapp_url: str = ""


def make_bot(token: str, *, proxy: Optional[str] = None):
    """یک نمونهی telegram.Bot آمادهی بله میسازد.

    proxy: آدرس پروکسی HTTP/SOCKS5 (اختیاری).
    """
    try:
        from telegram import Bot
    except ImportError:  # pragma: no cover
        raise RuntimeError(
            "برای اجرای بات بله لازم است python-telegram-bot نصب شود.\n"
            "  pip install \"python-telegram-bot>=20.0\""
        ) from None

    kwargs: dict = {"base_url": f"{BALE_API_BASE}/{token}"}
    if proxy:
        kwargs["proxy"] = proxy

    return Bot(**kwargs)


def get_peer_id(update) -> Optional[int]:
    """شناسهی عددی کاربر/چت فعال را از هر نوع updateای استخراج میکند.

    در bot-frameworkهای استاندارد (telegram + bale) این فیلد effective_user.id
    یا callback_query.from_user.id است. بازگشت None یعنی update فاقد فرستنده
    است (مثلاً چت anonymous).
    """
    if update is None:
        return None
    msg = getattr(update, "message", None)
    if msg is not None:
        user = getattr(msg, "effective_user", None) or getattr(msg, "from_user", None)
        if user is not None:
            return int(getattr(user, "id", 0) or 0)
    cb = getattr(update, "callback_query", None)
    if cb is not None:
        user = getattr(cb, "from_user", None)
        if user is not None:
            return int(getattr(user, "id", 0) or 0)
    # fallback: peer object (بعضی نسخههای SDK)
    peer = getattr(update, "effective_peer", None)
    if peer is not None:
        return int(getattr(peer, "id", 0) or 0)
    return None
