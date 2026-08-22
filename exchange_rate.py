# -*- coding: utf-8 -*-
"""
دریافت خودکار نرخ لحظه‌ای دلار (بر پایه‌ی USDT) به تومان.

چند منبع به ترتیب امتحان می‌شوند (چون سرورهای خارج از ایران گاهی توسط
صرافی‌های داخلی مثل نوبیتکس بلاک/فیلتر می‌شوند و درخواست با تایم‌اوت یا
خطای اتصال مواجه می‌شود، نه یک خطای واضح). نتیجه با کش کوتاه‌مدت نگه
داشته می‌شود تا فشار زیاد روی این سرویس‌ها نیفتد.
"""

import time
import logging
import re

import aiohttp

logger = logging.getLogger("exchange_rate")

_cache = {"rate": None, "ts": 0.0, "source": None}
CACHE_TTL_SECONDS = 300  # ۵ دقیقه
REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=8)

# الگوی نوار قیمت لحظه‌ای پایین صفحات tgju.org، مثلا: "دلار</b> 1,878,000 (0%)"
# عدد بلافاصله با درصد تغییر داخل پرانتز همراه است که این را از اشاره‌های
# متنی دیگر به «دلار» داخل مقالات سایت متمایز می‌کند.
_TGJU_PATTERN = re.compile(r"دلار[^0-9]{0,20}([\d,]{4,10})\s*\([-\d.]+%\)")


async def _from_tgju(session: aiohttp.ClientSession) -> float:
    async with session.get(
        "https://www.tgju.org/currency",
        timeout=REQUEST_TIMEOUT,
        headers={"User-Agent": "Mozilla/5.0"},
    ) as resp:
        if resp.status != 200:
            raise ValueError(f"HTTP {resp.status}")
        html = await resp.text()
    match = _TGJU_PATTERN.search(html)
    if not match:
        raise ValueError("الگوی قیمت دلار در صفحه tgju.org پیدا نشد (شاید ساختار سایت تغییر کرده).")
    rial = int(match.group(1).replace(",", ""))
    if rial <= 0:
        raise ValueError("مقدار نامعتبر.")
    return round(rial / 10)  # ریال به تومان


async def _from_nobitex(session: aiohttp.ClientSession) -> float:
    async with session.post(
        "https://api.nobitex.ir/market/stats",
        json={"srcCurrency": "usdt", "dstCurrency": "rls"},
        timeout=REQUEST_TIMEOUT,
    ) as resp:
        if resp.status != 200:
            raise ValueError(f"HTTP {resp.status}")
        data = await resp.json(content_type=None)
    latest_rial = float(data["stats"]["usdt-rls"]["latest"])
    return round(latest_rial / 10)


async def _from_wallex(session: aiohttp.ClientSession) -> float:
    async with session.get(
        "https://api.wallex.ir/v1/markets",
        timeout=REQUEST_TIMEOUT,
    ) as resp:
        if resp.status != 200:
            raise ValueError(f"HTTP {resp.status}")
        data = await resp.json(content_type=None)
    stats = data["result"]["symbols"]["USDTTMN"]["stats"]
    latest_toman = float(stats["lastPrice"])
    return round(latest_toman)


async def _from_arzdigital(session: aiohttp.ClientSession) -> float:
    # صرافی ارزدیجیتال؛ به‌عنوان سومین منبع پشتیبان (best effort).
    async with session.get(
        "https://api.arzdigital.com/v1/tickers?slugs=tether",
        timeout=REQUEST_TIMEOUT,
    ) as resp:
        if resp.status != 200:
            raise ValueError(f"HTTP {resp.status}")
        data = await resp.json(content_type=None)
    item = data[0] if isinstance(data, list) else data["data"][0]
    latest_toman = float(item["price_toman"])
    return round(latest_toman)


# ترتیب امتحان منابع؛ اولین موردی که جواب معتبر بدهد استفاده می‌شود.
# tgju.org اول امتحان می‌شود (طبق درخواست)، بعد نوبیتکس/والکس/ارزدیجیتال به‌عنوان پشتیبان.
_PROVIDERS = [
    ("tgju", _from_tgju),
    ("nobitex", _from_nobitex),
    ("wallex", _from_wallex),
    ("arzdigital", _from_arzdigital),
]


async def get_usd_to_toman_rate() -> float:
    """نرخ لحظه‌ای هر ۱ دلار (USDT) به تومان را برمی‌گرداند.
    به‌ترتیب چند منبع را امتحان می‌کند؛ در صورت شکست همه، اگر کش قدیمی
    موجود باشد همان را برمی‌گرداند، وگرنه استثنا صادر می‌شود (با پیام
    دقیق‌تر شامل خطای هر منبع، برای دیباگ راحت‌تر)."""
    now = time.time()
    if _cache["rate"] and (now - _cache["ts"]) < CACHE_TTL_SECONDS:
        return _cache["rate"]

    errors = []
    async with aiohttp.ClientSession() as session:
        for name, provider in _PROVIDERS:
            try:
                toman = await provider(session)
                if toman <= 0:
                    raise ValueError("نرخ دریافتی نامعتبر است (<= 0).")
                _cache["rate"] = toman
                _cache["ts"] = now
                _cache["source"] = name
                logger.info("نرخ دلار از منبع '%s' دریافت شد: %s تومان", name, toman)
                return toman
            except Exception as e:
                errors.append(f"{name}: {e}")
                logger.warning("دریافت نرخ از منبع '%s' ناموفق بود: %s", name, e)
                continue

    logger.error("دریافت نرخ دلار از همه‌ی منابع ناموفق بود: %s", " | ".join(errors))
    if _cache["rate"]:
        logger.warning("استفاده از آخرین نرخ کش‌شده (منبع: %s) به‌دلیل شکست همه‌ی منابع.", _cache["source"])
        return _cache["rate"]
    raise RuntimeError(
        "دریافت نرخ خودکار از همه‌ی منابع (tgju/نوبیتکس/والکس/ارزدیجیتال) ناموفق بود. "
        "احتمالاً IP سرور توسط این سرویس‌ها بلاک/فیلتر شده. جزئیات: " + " | ".join(errors)
    )


def get_cache_status() -> dict:
    """برای دیباگ: وضعیت فعلی کش نرخ را برمی‌گرداند."""
    return dict(_cache)


async def refresh_rate() -> dict:
    """کش فعلی را نادیده می‌گیرد و نرخ را دوباره از منابع خارجی می‌گیرد
    (برای دکمه‌ی «رفرش کش» در پنل وب). خروجی همان دیکشنری get_cache_status()
    است، بعد از تلاش برای به‌روزرسانی. اگر همه‌ی منابع شکست بخورند، استثنای
    get_usd_to_toman_rate بالا می‌رود (که اگر کش قدیمی موجود باشد به‌جایش
    همان را برمی‌گرداند و استثنا صادر نمی‌کند)."""
    _cache["ts"] = 0.0  # کش را باطل کن تا get_usd_to_toman_rate مجبور به فراخوانی منابع شود
    await get_usd_to_toman_rate()
    return get_cache_status()
