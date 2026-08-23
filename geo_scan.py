# -*- coding: utf-8 -*-
"""
اسکن «لینک ساب مادر» و استخراج موقعیت جغرافیایی سرورهای پشت آن، برای نمایش
روی نقشه‌ی جهانِ داشبورد پنل وب.

این ماژول مستقل از هر پنل خاصی (Marzban/X-UI/Pasarguard/...) کار می‌کند چون
مستقیماً محتوای خروجیِ لینک ساب را می‌خواند: لیستی از کانفیگ‌های
vmess/vless/trojan/ss/hysteria2/tuic که هرکدام آدرس یک سرور را در خود دارند.

روند کار:
  1) دانلود متن ساب و پارس هر خط به {protocol, host, port, remark}
  2) resolve کردن دامنه‌ها به IP (اگر خودِ host از قبل IP باشد رد می‌شود)
  3) جئولوکیت IPها با batch endpoint سرویس رایگان ip-api.com
  4) یک تست سریع TCP connect برای تخمین آنلاین/آفلاین بودن هر سرور
  5) تجمیع نهایی: اول تلاش می‌شود کشور از روی پرچم/نام کشوری که در همان
     «remark» کانفیگ گنجانده شده تشخیص داده شود (چیزی که اپ‌هایی مثل
     v2Box هم نشان می‌دهند) و فقط وقتی چیزی در remark نبود از نتیجه‌ی
     جئولوکیت IP استفاده می‌شود. این‌کار لازم است چون خیلی از کانفیگ‌ها
     پشت CDN/دامنه‌ی فرانتینگ (مثلاً Cloudflare) هستند و IP واقعی‌شان به
     جای سرور اصلی، به یک edge مشترک resolve می‌شود که geoip آن کاملاً
     گمراه‌کننده است (مثلاً چند کشور مختلف همه زیر یک IP کلودفلر).

نتیجه در حافظه cache می‌شود تا هر بار دیده‌شدن داشبورد باعث اسکن کامل نشود.
"""

import asyncio
import re

import base64
import binascii
import ipaddress
import json
import time
from typing import Optional
from urllib.parse import urlparse, unquote

import aiohttp

_TIMEOUT = aiohttp.ClientTimeout(total=12)
_TCP_TIMEOUT = 1.8
_MAX_CONFIGS = 400
_DNS_CONCURRENCY = 25
_TCP_CONCURRENCY = 40
_CACHE_TTL = 600  # ثانیه — ۱۰ دقیقه
_GEOIP_BATCH_URL = "http://ip-api.com/batch?fields=status,country,countryCode,city,lat,lon,query"

_cache = {}  # link -> {"at": monotonic_ts, "data": {...}}


# ------------------------------------------------------ label→country --
# پرچم/نام کشوری که در «remark» خودِ کانفیگ گنجانده شده (کاری که اپ‌هایی
# مثل v2Box هم انجام می‌دهند) خیلی قابل‌اعتمادتر از geoip روی IP پشت CDN
# است، پس اول این را امتحان می‌کنیم.

_FLAG_RE = re.compile(r"[\U0001F1E6-\U0001F1FF]{2}")


def _flag_to_cc(pair: str) -> str:
    return "".join(chr(ord(ch) - 0x1F1E6 + ord("A")) for ch in pair)


# کد کشور -> (نام نمایشی انگلیسی، lat، lon پایتخت) — برای پین‌گذاری وقتی
# geoip در دسترس نیست یا گمراه‌کننده است (فرانتینگ/CDN).
COUNTRY_INFO = {
    "DE": ("Germany", 52.52, 13.405), "TR": ("Turkey", 39.93, 32.86),
    "NL": ("Netherlands", 52.37, 4.895), "FI": ("Finland", 60.17, 24.94),
    "US": ("United States", 38.90, -77.04), "GB": ("United Kingdom", 51.51, -0.13),
    "FR": ("France", 48.86, 2.35), "CA": ("Canada", 45.42, -75.70),
    "JP": ("Japan", 35.68, 139.69), "SG": ("Singapore", 1.35, 103.82),
    "HK": ("Hong Kong", 22.32, 114.17), "AE": ("United Arab Emirates", 24.47, 54.37),
    "RU": ("Russia", 55.76, 37.62), "KR": ("South Korea", 37.57, 126.98),
    "IN": ("India", 28.61, 77.21), "AU": ("Australia", -35.28, 149.13),
    "IT": ("Italy", 41.90, 12.50), "ES": ("Spain", 40.42, -3.70),
    "SE": ("Sweden", 59.33, 18.07), "NO": ("Norway", 59.91, 10.75),
    "DK": ("Denmark", 55.68, 12.57), "PL": ("Poland", 52.23, 21.01),
    "CH": ("Switzerland", 46.95, 7.45), "AT": ("Austria", 48.21, 16.37),
    "BE": ("Belgium", 50.85, 4.35), "IE": ("Ireland", 53.35, -6.26),
    "PT": ("Portugal", 38.72, -9.14), "CZ": ("Czechia", 50.09, 14.42),
    "RO": ("Romania", 44.43, 26.10), "GR": ("Greece", 37.98, 23.73),
    "IL": ("Israel", 31.77, 35.21), "BR": ("Brazil", -15.79, -47.88),
    "UA": ("Ukraine", 50.45, 30.52), "LT": ("Lithuania", 54.69, 25.28),
    "LV": ("Latvia", 56.95, 24.11), "EE": ("Estonia", 59.44, 24.75),
    "BG": ("Bulgaria", 42.70, 23.32), "HU": ("Hungary", 47.50, 19.04),
    "CY": ("Cyprus", 35.19, 33.38), "LU": ("Luxembourg", 49.61, 6.13),
    "MT": ("Malta", 35.90, 14.51), "IS": ("Iceland", 64.15, -21.94),
    "HR": ("Croatia", 45.81, 15.98), "RS": ("Serbia", 44.79, 20.45),
    "MD": ("Moldova", 47.01, 28.86), "GE": ("Georgia", 41.72, 44.79),
    "AZ": ("Azerbaijan", 40.41, 49.87), "KZ": ("Kazakhstan", 51.16, 71.47),
    "TH": ("Thailand", 13.75, 100.50), "MY": ("Malaysia", 3.14, 101.69),
    "ID": ("Indonesia", -6.21, 106.85), "PH": ("Philippines", 14.60, 120.98),
    "VN": ("Vietnam", 21.03, 105.85), "TW": ("Taiwan", 25.03, 121.57),
    "CN": ("China", 39.90, 116.40), "MX": ("Mexico", 19.43, -99.13),
    "AR": ("Argentina", -34.60, -58.38), "CL": ("Chile", -33.45, -70.67),
    "ZA": ("South Africa", -25.75, 28.19), "EG": ("Egypt", 30.04, 31.24),
    "SA": ("Saudi Arabia", 24.71, 46.68), "QA": ("Qatar", 25.29, 51.53),
    "KW": ("Kuwait", 29.38, 47.99), "BH": ("Bahrain", 26.23, 50.59),
    "OM": ("Oman", 23.59, 58.41), "JO": ("Jordan", 31.95, 35.93),
    "PK": ("Pakistan", 33.68, 73.05), "BD": ("Bangladesh", 23.81, 90.41),
    "LK": ("Sri Lanka", 6.93, 79.85), "NZ": ("New Zealand", -41.29, 174.78),
    "IR": ("Iran", 35.70, 51.42), "AM": ("Armenia", 40.18, 44.51),
}

# مترادف‌های فارسی/انگلیسی نام کشور که معمولاً در remark کانفیگ‌ها می‌آید
# (چون خیلی از ساب‌ها به‌جای پرچم یونیکد از متن استفاده می‌کنند).
_COUNTRY_NAME_MAP = {
    "germany": "DE", "deutschland": "DE", "almanya": "DE", "آلمان": "DE",
    "turkey": "TR", "türkiye": "TR", "turkiye": "TR", "ترکیه": "TR",
    "netherlands": "NL", "holland": "NL", "هلند": "NL",
    "finland": "FI", "فنلاند": "FI",
    "united states": "US", "usa": "US", "america": "US", "آمریکا": "US", "امریکا": "US",
    "united kingdom": "GB", "england": "GB", "britain": "GB", "انگلیس": "GB", "انگلستان": "GB",
    "france": "FR", "فرانسه": "FR",
    "canada": "CA", "کانادا": "CA",
    "japan": "JP", "ژاپن": "JP",
    "singapore": "SG", "سنگاپور": "SG",
    "hongkong": "HK", "hong kong": "HK", "هنگ کنگ": "HK",
    "uae": "AE", "dubai": "AE", "emirates": "AE", "امارات": "AE", "دبی": "AE",
    "russia": "RU", "روسیه": "RU",
    "south korea": "KR", "korea": "KR", "کره": "KR",
    "india": "IN", "هند": "IN",
    "australia": "AU", "استرالیا": "AU",
    "italy": "IT", "ایتالیا": "IT",
    "spain": "ES", "اسپانیا": "ES",
    "sweden": "SE", "سوئد": "SE",
    "norway": "NO", "نروژ": "NO",
    "denmark": "DK", "دانمارک": "DK",
    "poland": "PL", "لهستان": "PL",
    "switzerland": "CH", "سوئیس": "CH",
    "austria": "AT", "اتریش": "AT",
    "belgium": "BE", "بلژیک": "BE",
    "ireland": "IE", "ایرلند": "IE",
    "portugal": "PT", "پرتغال": "PT",
    "czech": "CZ", "چک": "CZ",
    "romania": "RO", "رومانی": "RO",
    "greece": "GR", "یونان": "GR",
    "israel": "IL", "اسرائیل": "IL",
    "brazil": "BR", "برزیل": "BR",
    "ukraine": "UA", "اوکراین": "UA",
    "hungary": "HU", "مجارستان": "HU",
    "cyprus": "CY", "قبرس": "CY",
    "iceland": "IS", "ایسلند": "IS",
    "serbia": "RS", "صربستان": "RS",
    "georgia": "GE", "گرجستان": "GE",
    "azerbaijan": "AZ", "آذربایجان": "AZ",
    "kazakhstan": "KZ", "قزاقستان": "KZ",
    "thailand": "TH", "تایلند": "TH",
    "malaysia": "MY", "مالزی": "MY",
    "indonesia": "ID", "اندونزی": "ID",
    "vietnam": "VN", "ویتنام": "VN",
    "taiwan": "TW", "تایوان": "TW",
    "china": "CN", "چین": "CN",
    "mexico": "MX", "مکزیک": "MX",
    "argentina": "AR", "آرژانتین": "AR",
    "chile": "CL", "شیلی": "CL",
    "egypt": "EG", "مصر": "EG",
    "saudi": "SA", "عربستان": "SA",
    "qatar": "QA", "قطر": "QA",
    "kuwait": "KW", "کویت": "KW",
    "bahrain": "BH", "بحرین": "BH",
    "oman": "OM", "عمان": "OM",
    "jordan": "JO", "اردن": "JO",
    "pakistan": "PK", "پاکستان": "PK",
    "new zealand": "NZ", "نیوزیلند": "NZ",
    "iran": "IR", "ایران": "IR",
    "armenia": "AM", "ارمنستان": "AM",
}
_COUNTRY_NAMES_SORTED = sorted(_COUNTRY_NAME_MAP, key=len, reverse=True)


def detect_label_country(remark: str):
    """کد دو حرفی کشور را از روی پرچم یونیکد یا نام کشور داخل remark پیدا می‌کند."""
    if not remark:
        return None
    m = _FLAG_RE.search(remark)
    if m:
        cc = _flag_to_cc(m.group(0))
        if cc in COUNTRY_INFO:
            return cc
    low = remark.lower()
    for name in _COUNTRY_NAMES_SORTED:
        if name in low:
            return _COUNTRY_NAME_MAP[name]
    return None



# --------------------------------------------------------------- parsing --

def _b64pad(s: str) -> str:
    s = s.strip().replace("-", "+").replace("_", "/")
    return s + "=" * (-len(s) % 4)


def _b64_decode_text(s: str) -> Optional[str]:
    try:
        return base64.b64decode(_b64pad(s)).decode("utf-8", errors="ignore")
    except (binascii.Error, ValueError):
        return None


def _parse_vmess(uri: str) -> Optional[dict]:
    decoded = _b64_decode_text(uri[len("vmess://"):])
    if not decoded:
        return None
    try:
        data = json.loads(decoded)
    except ValueError:
        return None
    host = str(data.get("add") or "").strip()
    port = str(data.get("port") or "").strip()
    if not host:
        return None
    remark = str(data.get("ps") or host)
    return {"protocol": "vmess", "host": host, "port": port, "remark": remark}


def _parse_generic(uri: str, protocol: str) -> Optional[dict]:
    """vless / trojan / hysteria2 / hy2 / hysteria / tuic — همه URI-shaped‌اند."""
    try:
        p = urlparse(uri)
        host = p.hostname
        if not host:
            return None
        remark = unquote(p.fragment) if p.fragment else host
        return {"protocol": protocol, "host": host, "port": str(p.port or ""), "remark": remark}
    except Exception:
        return None


def _parse_ss(uri: str) -> Optional[dict]:
    body = uri[len("ss://"):]
    frag = ""
    if "#" in body:
        body, frag = body.split("#", 1)
    remark = unquote(frag) if frag else None
    if "@" in body:
        _, hostport = body.rsplit("@", 1)
        host, _, port = hostport.partition(":")
        if host:
            return {"protocol": "ss", "host": host, "port": port, "remark": remark or host}
    decoded = _b64_decode_text(body)
    if decoded and "@" in decoded:
        _, hostport = decoded.rsplit("@", 1)
        host, _, port = hostport.partition(":")
        if host:
            return {"protocol": "ss", "host": host, "port": port, "remark": remark or host}
    return None


_PARSERS = {
    "vmess://": _parse_vmess,
    "vless://": lambda u: _parse_generic(u, "vless"),
    "trojan://": lambda u: _parse_generic(u, "trojan"),
    "hysteria2://": lambda u: _parse_generic(u, "hysteria2"),
    "hy2://": lambda u: _parse_generic(u, "hysteria2"),
    "hysteria://": lambda u: _parse_generic(u, "hysteria"),
    "tuic://": lambda u: _parse_generic(u, "tuic"),
    "ss://": _parse_ss,
}


def parse_subscription_text(text: str) -> list:
    body = text.strip()
    decoded = _b64_decode_text(body)
    candidate = decoded if decoded and "://" in decoded else body
    out = []
    for raw_line in candidate.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        for prefix, parser in _PARSERS.items():
            if line.startswith(prefix):
                item = parser(line)
                if item:
                    out.append(item)
                break
        if len(out) >= _MAX_CONFIGS:
            break
    return out


# ------------------------------------------------------------- resolving --

def _is_ip(host: str) -> Optional[str]:
    try:
        ipaddress.ip_address(host)
        return host
    except ValueError:
        return None


async def _resolve(host: str, sem: asyncio.Semaphore) -> Optional[str]:
    ip = _is_ip(host)
    if ip:
        return ip
    loop = asyncio.get_event_loop()
    async with sem:
        try:
            infos = await asyncio.wait_for(loop.getaddrinfo(host, None), timeout=3.0)
            for info in infos:
                addr = info[4][0]
                if _is_ip(addr):
                    return addr
        except Exception:
            return None
    return None


async def _tcp_check(host: str, port: int, sem: asyncio.Semaphore) -> str:
    if not port:
        return "unknown"
    async with sem:
        try:
            reader, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout=_TCP_TIMEOUT)
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass
            return "online"
        except (asyncio.TimeoutError, OSError):
            return "offline"
        except Exception:
            return "unknown"


async def _geolocate(ips: list) -> dict:
    result = {}
    chunks = [ips[i:i + 100] for i in range(0, len(ips), 100)]
    async with aiohttp.ClientSession(timeout=_TIMEOUT) as session:
        for chunk in chunks:
            payload = [{"query": ip} for ip in chunk]
            try:
                async with session.post(_GEOIP_BATCH_URL, json=payload) as resp:
                    data = await resp.json(content_type=None)
                for row in data:
                    if row.get("status") == "success" and row.get("lat") is not None:
                        result[row["query"]] = {
                            "country": row.get("country") or "",
                            "country_code": row.get("countryCode") or "",
                            "city": row.get("city") or "",
                            "lat": row.get("lat"),
                            "lon": row.get("lon"),
                        }
            except Exception:
                continue
    return result


# --------------------------------------------------------------- scanning --

async def scan_subscription(link: str, *, force_refresh: bool = False, check_status: bool = True) -> dict:
    now = time.monotonic()
    cached = _cache.get(link)
    if cached and not force_refresh and (now - cached["at"]) < _CACHE_TTL:
        return cached["data"]

    try:
        async with aiohttp.ClientSession(timeout=_TIMEOUT) as session:
            async with session.get(link, headers={"User-Agent": "v2rayNG/1.8.29"}) as resp:
                text = await resp.text(errors="ignore")
    except Exception as e:
        return {"ok": False, "error": f"دریافت لینک ساب ناموفق بود: {e}"}

    configs = parse_subscription_text(text)
    if not configs:
        return {"ok": False, "error": "هیچ کانفیگ قابل‌شناسایی‌ای در این لینک ساب پیدا نشد."}

    dns_sem = asyncio.Semaphore(_DNS_CONCURRENCY)
    hosts = list({c["host"] for c in configs})
    resolved = await asyncio.gather(*(_resolve(h, dns_sem) for h in hosts))
    host_ip = {h: ip for h, ip in zip(hosts, resolved) if ip}
    for c in configs:
        c["ip"] = host_ip.get(c["host"])

    ips = sorted({c["ip"] for c in configs if c["ip"]})
    geo = await _geolocate(ips) if ips else {}

    status_map = {}
    if check_status and ips:
        tcp_sem = asyncio.Semaphore(_TCP_CONCURRENCY)
        pairs = list({(c["ip"], int(c["port"])) for c in configs if c["ip"] and str(c["port"]).isdigit()})
        results = await asyncio.gather(*(_tcp_check(ip, port, tcp_sem) for ip, port in pairs))
        for (ip, _port), st in zip(pairs, results):
            if status_map.get(ip) != "online":
                status_map[ip] = st

    grouped = {}
    for c in configs:
        ip = c["ip"]
        label_cc = detect_label_country(c.get("remark") or "")
        geo_entry = geo.get(ip) if ip else None

        if label_cc:
            # اولویت با کشوری که خودِ کانفیگ در نامش گفته — چون IP واقعاً
            # ممکن است پشت CDN/فرانتینگ باشد و geoip آن گمراه‌کننده باشد.
            name, lat, lon = COUNTRY_INFO[label_cc]
            cc, country, source = label_cc, name, "label"
            city = geo_entry["city"] if geo_entry and geo_entry["country_code"] == label_cc else ""
        elif geo_entry:
            cc, country = geo_entry["country_code"], geo_entry["country"]
            lat, lon, city, source = geo_entry["lat"], geo_entry["lon"], geo_entry["city"], "geoip"
        else:
            continue  # نه در remark و نه با geoip چیزی معلوم نشد

        key = cc or f"ip:{ip}"
        entry = grouped.setdefault(key, {
            "country": country, "country_code": cc, "city": city,
            "lat": lat, "lon": lon, "protocols": {}, "configs_count": 0,
            "status": "unknown", "source": source, "ips": set(), "sample_remarks": [],
        })
        entry["configs_count"] += 1
        if ip:
            entry["ips"].add(ip)
            st = status_map.get(ip)
            if st == "online":
                entry["status"] = "online"
            elif st == "offline" and entry["status"] != "online":
                entry["status"] = "offline"
        entry["protocols"][c["protocol"]] = entry["protocols"].get(c["protocol"], 0) + 1
        if c.get("remark") and len(entry["sample_remarks"]) < 3 and c["remark"] not in entry["sample_remarks"]:
            entry["sample_remarks"].append(c["remark"])

    servers = []
    for e in grouped.values():
        e["protocols"] = [{"name": k, "count": v} for k, v in sorted(e["protocols"].items(), key=lambda x: -x[1])]
        ips_sorted = sorted(e.pop("ips"))
        e["ip"] = ips_sorted[0] if ips_sorted else ""
        e["ip_count"] = len(ips_sorted)
        servers.append(e)
    servers.sort(key=lambda s: -s["configs_count"])

    result = {
        "ok": True,
        "generated_at": int(time.time()),
        "total_configs": len(configs),
        "resolved_configs": sum(1 for c in configs if c.get("ip")),
        "total_servers": len(servers),
        "total_countries": len({s["country_code"] for s in servers if s["country_code"]}),
        "servers": servers,
    }
    _cache[link] = {"at": now, "data": result}
    return result
