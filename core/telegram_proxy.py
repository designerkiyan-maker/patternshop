# -*- coding: utf-8 -*-

"""
PatternShop Telegram transport.

Telegram traffic is routed exclusively through the local Xray client.
There is no public HTTP proxy pool or external proxy fallback here.
"""

import asyncio
import logging
from typing import Optional

import aiohttp

from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.session.base import BaseSession
from aiogram.client.telegram import TelegramAPIServer
from aiogram.methods.base import TelegramMethod, TelegramType


logger = logging.getLogger("telegram_proxy")

XRAY_HTTP_PROXY = "http://127.0.0.1:18080"


class ProxiedClientSession(aiohttp.ClientSession):
    """aiohttp.ClientSession با پروکسی پیش‌فرض Xray — سازگار با همه‌ی نسخه‌های aiohttp.

    پارامتر proxy سازنده‌ی ClientSession در aiohttp 3.9 (نسخه‌ای که aiogram پین
    کرده) وجود ندارد و از 3.10 اضافه شده؛ پس ClientSession(proxy=...) با
    TypeError می‌شکند و تماس‌های HTTP سرویس‌های FastAPI (پنل/مینی‌اپ) با
    api.telegram.org بی‌صدا شکست می‌خورند (خطای 502 آپلود/پیش‌نمایش). برای
    همین پروکسی به‌صورت per-request داخل _request تزریق می‌شود؛ مقدار
    per-request در صورت پاس‌دادن صریح، بر این پیش‌فرض مقدم است."""

    def _request(self, method, str_or_url, **kwargs):
        kwargs.setdefault("proxy", XRAY_HTTP_PROXY)
        return super()._request(method, str_or_url, **kwargs)


class TelegramProxyManager:
    """
    Compatibility wrapper kept for existing imports.

    The only available Telegram transport is the local Xray HTTP
    inbound. Xray itself manages the VLESS node pool.
    """

    def __init__(self):
        self.current_proxy: str = XRAY_HTTP_PROXY

    def available_proxies(self):
        return [XRAY_HTTP_PROXY]

    def mark_failed(self, proxy: str):
        logger.warning(
            "Local Xray proxy reported failed: %s",
            proxy,
        )

    def mark_success(self, proxy: str):
        self.current_proxy = XRAY_HTTP_PROXY

    async def find_working_proxy(
        self,
        token: str,
        force: bool = False,
    ) -> str:
        return XRAY_HTTP_PROXY

    async def test_proxy(
        self,
        proxy: str,
        token: str,
    ) -> bool:
        session = None

        try:
            session = AiohttpSession(
                proxy=XRAY_HTTP_PROXY,
                timeout=20,
            )

            from aiogram import Bot

            bot = Bot(
                token=token,
                session=session,
            )

            await bot.get_me()

            logger.info(
                "Telegram via local Xray test successful"
            )

            return True

        except Exception as exc:
            logger.warning(
                "Telegram via local Xray test failed: %s: %s",
                type(exc).__name__,
                str(exc),
            )
            return False

        finally:
            if session is not None:
                try:
                    await session.close()
                except Exception:
                    pass


_manager = TelegramProxyManager()


class TelegramFailoverSession(BaseSession):

    def __init__(
        self,
        timeout: float = 60.0,
        api: TelegramAPIServer | None = None,
    ):
        super().__init__(
            timeout=timeout,
            api=api or TelegramAPIServer(
                base="https://api.telegram.org/bot{token}/{method}",
                file="https://api.telegram.org/file/bot{token}/{path}",
            ),
        )

        self._session: Optional[AiohttpSession] = None
        self._lock = asyncio.Lock()

    async def _ensure_session(self):
        async with self._lock:

            if self._session is not None:
                return self._session

            self._session = AiohttpSession(
                proxy=XRAY_HTTP_PROXY,
                timeout=self.timeout,
                api=self.api,
            )

            logger.info(
                "Telegram session using local Xray: %s",
                XRAY_HTTP_PROXY,
            )

            return self._session

    async def make_request(
        self,
        bot,
        method: TelegramMethod[TelegramType],
        timeout: int | None = None,
    ) -> TelegramType:

        session = await self._ensure_session()

        try:
            return await session.make_request(
                bot=bot,
                method=method,
                timeout=timeout,
            )

        except Exception:
            logger.exception(
                "Telegram request through local Xray failed"
            )
            raise

    async def stream_content(
        self,
        url: str,
        headers=None,
        timeout: int = 30,
        chunk_size: int = 65536,
        raise_for_status: bool = True,
    ):

        session = await self._ensure_session()

        async for chunk in session.stream_content(
            url=url,
            headers=headers,
            timeout=timeout,
            chunk_size=chunk_size,
            raise_for_status=raise_for_status,
        ):
            yield chunk

    async def close(self):
        async with self._lock:

            if self._session is not None:
                try:
                    await self._session.close()
                except Exception:
                    pass

            self._session = None


def create_telegram_session():
    return TelegramFailoverSession()


async def get_telegram_proxy(token: str):
    return XRAY_HTTP_PROXY


def get_current_proxy():
    return XRAY_HTTP_PROXY
