# -*- coding: utf-8 -*-
"""
دریافت خودکار نرخ لحظه‌ای دلار (بر پایه‌ی USDT) به تومان از API عمومی نوبیتکس،
با کش کوتاه‌مدت که از درخواست زیاد به نوبیتکس جلوگیری می‌کند.
"""

import time
import logging

import aiohttp

logger = logging.getLogger("exchange_rate")

_cache = {"rate": None, "ts": 0.0}
CACHE_TTL_SECONDS = 300  # ۵ دقیقه


async def get_usd_to_toman_rate() -> float:
    """نرخ لحظه‌ای هر ۱ دلار (USDT) به تومان را برمی‌گرداند. در صورت خطا، اگر کش قدیمی
    موجود باشد همان را برمی‌گرداند، وگرنه استثنا صادر می‌شود."""
    now = time.time()
    if _cache["rate"] and (now - _cache["ts"]) < CACHE_TTL_SECONDS:
        return _cache["rate"]

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.nobitex.ir/market/stats",
                json={"srcCurrency": "usdt", "dstCurrency": "rls"},
                timeout=aiohttp.ClientTimeout(total=8),
            ) as resp:
                data = await resp.json()
        latest_rial = float(data["stats"]["usdt-rls"]["latest"])
        toman = round(latest_rial / 10)
        if toman <= 0:
            raise ValueError("نرخ دریافتی نامعتبر است.")
        _cache["rate"] = toman
        _cache["ts"] = now
        return toman
    except Exception:
        logger.exception("دریافت نرخ خودکار دلار از نوبیتکس ناموفق بود.")
        if _cache["rate"]:
            return _cache["rate"]
        raise
