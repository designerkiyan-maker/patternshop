# -*- coding: utf-8 -*-
"""
دریافت خودکار نرخ لحظه‌ای دلار (بر پایه‌ی USDT) به تومان.

چند منبع به ترتیب امتحان می‌شوند (چون سرورهای خارج از ایران گاهی توسط
صرافی‌های داخلی مثل نوبیتکس بلاک/فیلتر می‌شوند و درخواست با تایم‌اوت یا
خطای اتصال مواجه می‌شود، نه یک خطای واضح). نتیجه با کش کوتاه‌مدت نگه
داشته می‌شود تا فشار زیاد روی این سرویس‌ها نیفتد.

اگر همه‌ی منابع زنده (و کش قدیمی) شکست بخورند، در نهایت یک «نرخ دستی
پشتیبان» که ادمین از تنظیمات پنل وارد کرده می‌تواند به‌عنوان آخرین راه‌حل
استفاده شود (به get_usd_to_toman_rate پاس داده می‌شود)، تا سایت کاملاً
از کار نیفتد.
"""

import time
import logging
import re
from typing import Optional

import aiohttp

logger = logging.getLogger("exchange_rate")

_cache = {"rate": None, "ts": 0.0, "source": None}
CACHE_TTL_SECONDS = 300  # ۵ دقیقه
REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=8)

# الگوی نوار قیمت لحظه‌ای پایین صفحات tgju.org، مثلا: "دلار</b> 1,878,000 (0%)"
# عدد بلافاصله با درصد تغییر داخل پرانتز همراه است که این را از اشاره‌های
# متنی دیگر به «دلار» داخل مقالات سایت متمایز می‌کند.
_TGJU_PATTERN = re.compile(r"دلار[^0-9]{0,20}([\d,]{4,10})\s*\([-\d.]+%\)")
# الگوی پشتیبان: ساختار جدول/کارت‌های tgju معمولاً data-price روی دلار آمریکا
# دارد؛ مستقل از متن اطراف و مقاوم‌تر در برابر تغییر چیدمان صفحه.
_TGJU_PATTERN_FALLBACK = re.compile(
    r'price_dollar_rl["\']?[^{}]{0,40}?["\']p["\']\s*:\s*["\']([\d,]{4,10})["\']'
)


def _fmt_err(name: str, e: Exception) -> str:
    """پیام خطای خوانا برای هر منبع؛ بعضی استثناها (مثل TimeoutError) متن
    خالی دارند، پس نوع خطا را هم اضافه می‌کنیم تا هیچ‌وقت پیام خالی نمایش
    داده نشود."""
    msg = str(e).strip()
    type_name = type(e).__name__
    return f"{name}: {type_name} - {msg}" if msg else f"{name}: {type_name}"


async def _from_tgju(session: aiohttp.ClientSession) -> float:
    async with session.get(
        "https://www.tgju.org/currency",
        timeout=REQUEST_TIMEOUT,
        headers={"User-Agent": "Mozilla/5.0"},
    ) as resp:
        if resp.status != 200:
            raise ValueError(f"HTTP {resp.status}")
        html = await resp.text()
    match = _TGJU_PATTERN.search(html) or _TGJU_PATTERN_FALLBACK.search(html)
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
    # ساختار پاسخ والکس چند بار در گذشته تغییر کرده؛ چند مسیر محتمل را
    # امتحان می‌کنیم تا فقط با یک تغییر جزئی در پاسخشان کل منبع از کار نیفتد.
    symbols = (data.get("result") or {}).get("symbols") or {}
    stats = None
    for key in ("USDTTMN", "USDT_TMN", "USDTIRT"):
        if key in symbols:
            stats = symbols[key].get("stats")
            break
    if stats is None:
        for sym_key, sym_val in symbols.items():
            if "USDT" in sym_key.upper() and ("TMN" in sym_key.upper() or "IRT" in sym_key.upper()):
                stats = sym_val.get("stats")
                break
    if not stats or not stats.get("lastPrice"):
        raise ValueError("جفت‌ارز USDT/TMN در پاسخ والکس پیدا نشد (شاید ساختار API تغییر کرده).")
    return round(float(stats["lastPrice"]))


async def _from_coingecko(session: aiohttp.ClientSession) -> float:
    """منبع جهانی (غیر ایرانی) به‌عنوان آخرین پشتیبان پیش از نرخ دستی؛ چون
    زیرساخت جهانی دارد معمولاً از داخل ایران/فیلترشکن هم در دسترس است، اما
    نرخش لزوماً با نرخ آزاد بازار ایران یکی نیست و باید صرفاً best-effort
    در نظر گرفته شود."""
    async with session.get(
        "https://api.coingecko.com/api/v3/simple/price",
        params={"ids": "tether", "vs_currencies": "irr"},
        timeout=REQUEST_TIMEOUT,
    ) as resp:
        if resp.status != 200:
            raise ValueError(f"HTTP {resp.status}")
        data = await resp.json(content_type=None)
    rial = float(data["tether"]["irr"])
    if rial <= 0:
        raise ValueError("مقدار نامعتبر.")
    return round(rial / 10)


# ترتیب امتحان منابع؛ اولین موردی که جواب معتبر بدهد استفاده می‌شود.
# tgju.org اول امتحان می‌شود (طبق درخواست)، بعد نوبیتکس/والکس به‌عنوان
# پشتیبان داخلی، و در نهایت coingecko به‌عنوان پشتیبان جهانی.
_PROVIDERS = [
    ("tgju", _from_tgju),
    ("nobitex", _from_nobitex),
    ("wallex", _from_wallex),
    ("coingecko", _from_coingecko),
]


async def get_usd_to_toman_rate(manual_fallback: Optional[float] = None) -> float:
    """نرخ لحظه‌ای هر ۱ دلار (USDT) به تومان را برمی‌گرداند.
    به‌ترتیب چند منبع را امتحان می‌کند؛ در صورت شکست همه:
    ۱) اگر کش قدیمی موجود باشد همان را برمی‌گرداند،
    ۲) وگرنه اگر manual_fallback (نرخ دستی تنظیم‌شده در پنل) عدد معتبری
       باشد همان استفاده می‌شود (و به‌عنوان منبع 'manual' کش می‌شود)،
    ۳) وگرنه استثنا صادر می‌شود (با پیام دقیق‌تر شامل خطای هر منبع)."""
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
                errors.append(_fmt_err(name, e))
                logger.warning("دریافت نرخ از منبع '%s' ناموفق بود: %s", name, e)
                continue

    logger.error("دریافت نرخ دلار از همه‌ی منابع ناموفق بود: %s", " | ".join(errors))
    if _cache["rate"]:
        logger.warning("استفاده از آخرین نرخ کش‌شده (منبع: %s) به‌دلیل شکست همه‌ی منابع.", _cache["source"])
        return _cache["rate"]
    if manual_fallback and manual_fallback > 0:
        logger.warning("استفاده از نرخ دستی پشتیبان (%s تومان) به‌دلیل شکست همه‌ی منابع زنده.", manual_fallback)
        _cache["rate"] = manual_fallback
        _cache["ts"] = now
        _cache["source"] = "manual"
        return manual_fallback
    raise RuntimeError(
        "دریافت نرخ خودکار از همه‌ی منابع (tgju/نوبیتکس/والکس/coingecko) ناموفق بود. "
        "احتمالاً IP سرور توسط این سرویس‌ها بلاک/فیلتر شده — می‌توانید در تنظیمات یک «نرخ دستی "
        "پشتیبان» وارد کنید تا در چنین مواقعی سایت از کار نیفتد. جزئیات: " + " | ".join(errors)
    )


def get_cache_status() -> dict:
    """برای دیباگ: وضعیت فعلی کش نرخ را برمی‌گرداند."""
    return dict(_cache)


async def refresh_rate(manual_fallback: Optional[float] = None) -> dict:
    """کش فعلی را نادیده می‌گیرد و نرخ را دوباره از منابع خارجی می‌گیرد
    (برای دکمه‌ی «رفرش کش» در پنل وب). خروجی همان دیکشنری get_cache_status()
    است، بعد از تلاش برای به‌روزرسانی. اگر همه‌ی منابع زنده و نرخ دستی هم
    شکست بخورند، استثنای get_usd_to_toman_rate بالا می‌رود."""
    _cache["ts"] = 0.0  # کش را باطل کن تا get_usd_to_toman_rate مجبور به فراخوانی منابع شود
    await get_usd_to_toman_rate(manual_fallback=manual_fallback)
    return get_cache_status()
