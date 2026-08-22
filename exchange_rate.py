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

import asyncio
import socket
import time
import logging
import re
from typing import Optional

import aiohttp

logger = logging.getLogger("exchange_rate")

_cache = {"rate": None, "ts": 0.0, "source": None}
CACHE_TTL_SECONDS = 300  # ۵ دقیقه
REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=10)
RETRY_COUNT = 2  # هر منبع تا این تعداد بار تلاش می‌شود قبل از رد شدن به منبع بعدی

# هدر مرورگر واقعی؛ چون بدون این هدرها بعضی سایت‌ها (مثل tgju پشت Cloudflare)
# درخواست‌های خالی/کتابخانه‌ای را بلاک یا با صفحه‌ی چلنج پاسخ می‌دهند.
BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "fa-IR,fa;q=0.9,en-US;q=0.8,en;q=0.7",
}


class _DoHResolver(aiohttp.abc.AbstractResolver):
    """Resolver مبتنی بر DNS-over-HTTPS کلودفلر (به IP لیترال 1.1.1.1 وصل
    می‌شود، پس خودش نیازی به DNS سیستم ندارد). جایگزین aiohttp.AsyncResolver
    شد چون آن یکی هم به نصب بودن پکیج aiodns وابسته است و هم در نهایت از
    همان resolver سیستم عامل استفاده می‌کند - اگر resolv.conf سرور دامنه‌های
    .ir را درست resolve نکند (مورد رایج روی سرورهای خارج از ایران)، همان
    خطای 'Name or service not known' باز هم رخ می‌دهد. DoH این مشکل را کامل
    دور می‌زند."""

    def __init__(self):
        self._cache: dict[str, str] = {}

    async def _lookup(self, host: str) -> str:
        if host in self._cache:
            return self._cache[host]
        async with aiohttp.ClientSession() as s:
            async with s.get(
                "https://1.1.1.1/dns-query",
                params={"name": host, "type": "A"},
                headers={"Accept": "application/dns-json"},
                timeout=aiohttp.ClientTimeout(total=5),
            ) as resp:
                data = await resp.json(content_type=None)
        for ans in data.get("Answer", []):
            if ans.get("type") == 1:  # A record
                ip = ans["data"]
                self._cache[host] = ip
                return ip
        raise socket.gaierror(f"DoH: هیچ A record برای {host} پیدا نشد")

    async def resolve(self, host: str, port: int = 0, family: int = socket.AF_INET):
        ip = await self._lookup(host)
        return [{
            "hostname": host, "host": ip, "port": port,
            "family": family, "proto": 0, "flags": 0,
        }]

    async def close(self) -> None:
        pass


def _make_connector() -> aiohttp.TCPConnector:
    """از DoH برای resolve دامنه‌ها استفاده می‌کند تا مشکل معمول 'Name or
    service not known' روی سرورهایی که resolver سیستمشان دامنه‌های .ir را
    درست resolve نمی‌کند دور زده شود؛ بدون وابستگی به نصب بودن aiodns."""
    return aiohttp.TCPConnector(resolver=_DoHResolver())

# مجموعه‌ای از الگوهای احتمالی برای استخراج نرخ دلار از tgju.org.
# ⚠️ tgju به‌مرور ساختار صفحه‌اش را عوض می‌کند و هر الگوی تکی دیر یا زود
# می‌شکند؛ به‌جای یک regex، چند الگوی مستقل از هم را امتحان می‌کنیم تا با
# یک تغییر جزئی در HTML کل منبع از کار نیفتد. هر الگو یک اسم دارد تا در
# لاگ مشخص شود کدام‌یک (اگر هیچ‌کدام) جواب داده — این برای دیباگ سریع‌تر
# دفعه‌ی بعدی که سایت دوباره عوض شود ضروری است.
_TGJU_PATTERNS = [
    # ۱) نوار قیمت لحظه‌ای بالای صفحه، مثلا: "دلار</b> 1,878,000 (0%)"
    ("inline_change", re.compile(r"دلار[^0-9]{0,20}([\d,]{4,10})\s*\([-\d.]+%\)")),
    # ۲) دیتای JSON تعبیه‌شده در صفحه با کلید price_dollar_rl و فیلد p (قیمت)
    #    - چه با کوتیشن تک/دوتایی، چه با فاصله‌ی متفاوت بین کلید/مقدار.
    ("embedded_json_p", re.compile(
        r'price_dollar_rl["\']?\s*[:,][^{}]{0,60}?["\']p["\']\s*:\s*["\']?([\d,]{4,10})["\']?'
    )),
    # ۳) ویجت/جدول‌های جدیدتر که data-price روی خود تگ می‌گذارند، معمولاً
    #    نزدیک یک لینک یا سطر مربوط به price_dollar_rl.
    ("data_price_attr", re.compile(
        r'price_dollar_rl["\'][^>]{0,200}?data-price=["\']([\d,]{4,10})["\']'
    )),
    ("data_price_attr_reverse", re.compile(
        r'data-price=["\']([\d,]{4,10})["\'][^>]{0,200}?price_dollar_rl'
    )),
    # ۴) span/div با کلاس رایج قیمت، بلافاصله بعد از کلمه‌ی «دلار» (بدون
    #    وابستگی به وجود درصد تغییر جلوی آن).
    ("class_price_span", re.compile(
        r'دلار[^<]{0,10}<[^>]+class=["\'][^"\']*(?:info-price|price)[^"\']*["\'][^>]*>\s*([\d,]{4,10})'
    )),
    # ۵) ردیف جدول/کارت با id یا data-market-row مربوط به price_dollar_rl،
    #    مستقل از نام کلاس دقیق ستون قیمت (پوشش تغییرات آینده‌ی مارک‌آپ).
    ("row_id_nearby", re.compile(
        r'(?:id|data-market-row)=["\']price_dollar_rl["\'][^>]{0,400}?>\s*([\d,]{4,10})'
    )),
    # ۶) آخرین راه‌حل عمومی: اولین عدد شبیه قیمت بلافاصله بعد از عبارت
    #    «قیمت دلار» یا «دلار آمریکا» در هر جای صفحه.
    ("generic_after_label", re.compile(
        r'(?:قیمت\s*دلار|دلار\s*آمریکا)[^\d]{0,40}([\d,]{4,10})'
    )),
]


def _sanity_check_toman(rial_or_toman_raw: int, divide_by_10: bool) -> Optional[float]:
    """بررسی می‌کند عدد استخراج‌شده واقعاً می‌تواند نرخ دلار به تومان باشد
    (رد کردن اعداد بی‌ربط مثل شناسه‌ها یا کدهای دیگر که گاهی الگوهای عمومی
    اشتباهی می‌گیرند). بازه‌ی عمدا وسیع تا با نوسان نرخ نیازی به آپدیت مکرر
    این حد و مرز نباشد."""
    toman = round(rial_or_toman_raw / 10) if divide_by_10 else rial_or_toman_raw
    if 10_000 <= toman <= 100_000_000:
        return toman
    return None


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
        headers=BROWSER_HEADERS,
    ) as resp:
        if resp.status != 200:
            raise ValueError(f"HTTP {resp.status}")
        html = await resp.text()

    for pattern_name, pattern in _TGJU_PATTERNS:
        for match in pattern.finditer(html):
            raw = int(match.group(1).replace(",", ""))
            if raw <= 0:
                continue
            # صفحه‌ی tgju نرخ را به ریال می‌دهد؛ چون همه‌ی الگوها از یک واحد
            # (ریال) می‌خوانند، همیشه بر ۱۰ تقسیم می‌کنیم تا به تومان برسیم.
            toman = _sanity_check_toman(raw, divide_by_10=True)
            if toman is not None:
                logger.info("نرخ دلار از tgju با الگوی '%s' استخراج شد: %s تومان", pattern_name, toman)
                return toman
        # این الگو یا اصلاً چیزی پیدا نکرد یا هرچی پیدا کرد از بازه‌ی
        # منطقی خارج بود؛ برو سراغ الگوی بعدی.

    # هیچ‌کدام از الگوها جواب نداد: برای دیباگ سریع‌تر دفعه‌ی بعد، یک تکه
    # از HTML اطراف اولین اشاره به «دلار» را در لاگ (نه در پیام خطای کاربر)
    # ثبت می‌کنیم تا بشود الگوی جدید سایت را از روی آن نوشت.
    idx = html.find("دلار")
    if idx != -1:
        snippet = html[max(0, idx - 100): idx + 300].replace("\n", " ")
        logger.warning("tgju: هیچ الگویی جواب نداد؛ تکه‌ی HTML اطراف 'دلار' برای دیباگ: %s", snippet)
    else:
        logger.warning("tgju: کلمه‌ی 'دلار' اصلاً در HTML دریافتی پیدا نشد (شاید صفحه‌ی بلاک/چلنج برگشته).")

    raise ValueError(
        "الگوی قیمت دلار در صفحه tgju.org پیدا نشد (شاید ساختار سایت تغییر کرده، یا سرور "
        "به‌جای صفحه‌ی واقعی یک صفحه‌ی بلاک/چلنج ربات گرفته). جزئیات بیشتر در لاگ سرور."
    )


async def _from_nobitex(session: aiohttp.ClientSession) -> float:
    async with session.post(
        "https://api.nobitex.ir/market/stats",
        json={"srcCurrency": "usdt", "dstCurrency": "rls"},
        timeout=REQUEST_TIMEOUT,
        headers=BROWSER_HEADERS,
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
        headers=BROWSER_HEADERS,
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
        headers=BROWSER_HEADERS,
    ) as resp:
        if resp.status != 200:
            raise ValueError(f"HTTP {resp.status}")
        data = await resp.json(content_type=None)
    tether = data.get("tether") or {}
    if "irr" not in tether:
        raise ValueError("coingecko برای جفت tether/irr مقداری برنگرداند (شاید این جفت‌ارز دیگر پشتیبانی نمی‌شود).")
    rial = float(tether["irr"])
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
    async with aiohttp.ClientSession(connector=_make_connector()) as session:
        for name, provider in _PROVIDERS:
            last_err = None
            for attempt in range(1, RETRY_COUNT + 1):
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
                    last_err = e
                    if attempt < RETRY_COUNT:
                        logger.warning("تلاش %s/%s برای منبع '%s' ناموفق بود، تلاش دوباره: %s", attempt, RETRY_COUNT, name, e)
                        await asyncio.sleep(1)
                    continue
            errors.append(_fmt_err(name, last_err))
            logger.warning("دریافت نرخ از منبع '%s' ناموفق بود: %s", name, last_err)

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
