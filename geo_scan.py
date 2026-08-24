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
import hashlib
import ipaddress
import json
import os
import ssl
import struct
import time
import uuid as uuid_mod
from typing import Optional
from urllib.parse import urlparse, unquote, parse_qs

import aiohttp

_TIMEOUT = aiohttp.ClientTimeout(total=12)
_TCP_TIMEOUT = 7.0  # چک واقعی تونل؛ نزدیک به timeout پیش‌فرض کلاینت‌های Xray/V2Box
TCP_TIMEOUT_BACKGROUND = 7.0  # چک پس‌زمینه‌ی دوره‌ای — false-positive مهم‌تر از سرعت است
_MAX_CONFIGS = 400
_DNS_CONCURRENCY = 25
_TCP_CONCURRENCY = 40
# مقصد تست واقعی تونل؛ فقط باز بودن پورت کافی نیست. مشابه تست‌های Xray/libXray،
# بعد از برقراری تونل یک HTTP request واقعی از داخل پروکسی عبور داده می‌شود.
_PROBE_HOST = "www.gstatic.com"
_PROBE_PORT = 80
_PROBE_PATH = "/generate_204"
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


_INVISIBLE_RE = re.compile(r"[\u200b\u200c\u200d\ufe0f\u2060]")


def detect_label_country(remark: str):
    """کد دو حرفی کشور را از روی پرچم یونیکد یا نام کشور داخل remark پیدا می‌کند."""
    if not remark:
        return None
    remark = _INVISIBLE_RE.sub("", remark)
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


def _unquote_fully(s: str) -> str:
    """بعضی پنل‌ها fragment را دوبار percent-encode می‌کنند (مثلاً پرچم یونیکد
    به‌صورت %25F0%259F... درمی‌آید)؛ یک بار unquote آن را کاملاً باز نمی‌کند
    و پرچم/نام کشور برای تشخیص کشور در remark ناقص/خراب می‌ماند. اینجا تا
    وقتی unquote چیزی تغییر می‌دهد ادامه می‌دهیم (حداکثر ۳ بار، کافی برای
    دوبل/سه‌بل‌انکود و بی‌خطر برای متن عادی چون دیگر تغییری نمی‌کند)."""
    prev = s
    for _ in range(3):
        cur = unquote(prev)
        if cur == prev:
            break
        prev = cur
    return prev


def _parse_generic(uri: str, protocol: str) -> Optional[dict]:
    """vless / trojan / hysteria2 / hy2 / hysteria / tuic — همه URI-shaped‌اند.

    برای vless/trojan علاوه بر host/port، بخش userinfo (UUID یا پسورد) و
    پارامترهای کوئری (security/type/sni/path/host/...) هم استخراج می‌شود
    چون برای «چک واقعی سطح پروتکل» (نه فقط TCP خام) لازم‌اند — بدون این‌ها
    فقط می‌شد فهمید پورت باز است یا نه، نه اینکه خودِ کانفیگ/کاربر همچنان
    روی پنل فعال است یا غیرفعال شده."""
    try:
        p = urlparse(uri)
        host = p.hostname
        if not host:
            return None
        remark = _unquote_fully(p.fragment) if p.fragment else host
        item = {"protocol": protocol, "host": host, "port": str(p.port or ""), "remark": remark}
        if protocol in ("vless", "trojan"):
            item["auth"] = unquote(p.username) if p.username else None
            qs = {k: v[0] for k, v in parse_qs(p.query or "").items()}
            item["net_params"] = {
                "security": (qs.get("security") or "none").lower(),
                "network": (qs.get("type") or "tcp").lower(),
                "sni": qs.get("sni") or qs.get("host") or host,
                "ws_path": qs.get("path") or "/",
                "ws_host": qs.get("host") or host,
            }
        return item
    except Exception:
        return None


def _parse_ss(uri: str) -> Optional[dict]:
    body = uri[len("ss://"):]
    frag = ""
    if "#" in body:
        body, frag = body.split("#", 1)
    remark = _unquote_fully(frag) if frag else None
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


async def _tcp_check(host: str, port: int, sem: asyncio.Semaphore, timeout: float = _TCP_TIMEOUT) -> str:
    if not port:
        return "unknown"
    async with sem:
        try:
            reader, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout=timeout)
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


def _vless_header(uuid_str: str, dst_host: str, dst_port: int) -> Optional[bytes]:
    """VLESS request header with a real domain destination.

    Using a domain destination instead of the old hard-coded 1.1.1.1:80 makes
    the health-check much closer to what an Xray/libXray client does: the
    outbound is asked to open the same HTTP URL that we are about to probe.
    """
    try:
        u = uuid_mod.UUID(uuid_str).bytes
        host = dst_host.encode("idna")
    except (ValueError, AttributeError, UnicodeError):
        return None
    if not host or len(host) > 255 or not (1 <= int(dst_port) <= 65535):
        return None
    # VLESS: version + UUID + addons length + command + port + address type
    # + domain length + domain. Address type 0x02 means domain name.
    return (
        b"\x00" + u + b"\x00" + b"\x01"
        + struct.pack(">H", int(dst_port))
        + b"\x02" + bytes([len(host)]) + host
    )


def _trojan_header(password: str, dst_port: int = 80) -> bytes:
    pwd_hash = hashlib.sha224(password.encode("utf-8")).hexdigest().encode("ascii")
    return (
        pwd_hash + b"\r\n"
        + b"\x01" + b"\x01" + bytes([1, 1, 1, 1]) + struct.pack(">H", dst_port)
        + b"\r\n"
    )


def _ws_frame(payload: bytes) -> bytes:
    """فریم WebSocket باینری از سمت کلاینت — طبق RFC باید masked باشد."""
    mask = os.urandom(4)
    masked = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
    length = len(payload)
    if length < 126:
        header = bytes([0x82, 0x80 | length])
    elif length < 65536:
        header = bytes([0x82, 0x80 | 126]) + struct.pack(">H", length)
    else:
        header = bytes([0x82, 0x80 | 127]) + struct.pack(">Q", length)
    return header + mask + masked


async def _ws_upgrade(reader, writer, host: str, path: str) -> bool:
    key = base64.b64encode(os.urandom(16)).decode()
    req = (
        f"GET {path} HTTP/1.1\r\n"
        f"Host: {host}\r\n"
        f"Upgrade: websocket\r\nConnection: Upgrade\r\n"
        f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n"
    ).encode()
    writer.write(req)
    await writer.drain()
    resp = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), timeout=4.0)
    return b"101" in resp.split(b"\r\n", 1)[0]


def _extract_ws_payloads(data: bytes) -> list[bytes]:
    """فریم‌های WebSocket دریافتی را به payload تبدیل می‌کند.

    برای health-check فقط فریم‌های text/binary را لازم داریم؛ ping/pong/close
    نادیده گرفته می‌شوند. اگر یک فریم ناقص برسد، payload همان chunk را نمی‌توان
    با اطمینان استخراج کرد، پس [] برمی‌گردانیم و در دور بعد داده‌ی جدید می‌گیریم.
    این تابع برای چک سبک است و برای parser کامل WebSocket طراحی نشده.
    """
    out = []
    i = 0
    n = len(data)
    while i + 2 <= n:
        b1, b2 = data[i], data[i + 1]
        fin = (b1 & 0x80) != 0
        opcode = b1 & 0x0F
        masked = (b2 & 0x80) != 0
        length = b2 & 0x7F
        j = i + 2
        if length == 126:
            if j + 2 > n: return out
            length = struct.unpack(">H", data[j:j+2])[0]
            j += 2
        elif length == 127:
            if j + 8 > n: return out
            length = struct.unpack(">Q", data[j:j+8])[0]
            j += 8
        if length > 1024 * 1024:
            return out
        mask = None
        if masked:
            if j + 4 > n: return out
            mask = data[j:j+4]
            j += 4
        if j + length > n:
            return out
        payload = data[j:j+length]
        if masked and mask:
            payload = bytes(v ^ mask[k % 4] for k, v in enumerate(payload))
        if opcode in (0x1, 0x2, 0x0):
            out.append(payload)
        if not fin:
            # Fragmentation برای health-check ضروری نیست؛ chunk ناقص را
            # عمداً نادیده می‌گیریم تا false-positive ندهیم.
            return out
        i = j + length
    return out


async def _protocol_probe(cfg: dict, ip: str, timeout: float) -> Optional[str]:
    """چک سطح پروتکل: آیا خودِ کانفیگ (UUID/پسورد) هنوز روی پنل فعال است —
    نه صرفاً اینکه پورت باز است. برمی‌گرداند 'online' / 'offline' یا None
    (یعنی برای این ترکیب پروتکل/امنیت/شبکه پشتیبانی نمی‌شود و باید از چک
    TCP خام به‌عنوان fallback استفاده شود).

    منطق: بعد از هندشیک TCP/TLS/WS، هدر پروتکل با UUID/پسورد واقعیِ کانفیگ
    فرستاده می‌شود. روی Xray/Trojan-core، اگر UUID/پسورد نامعتبر باشد
    (یعنی آن کاربر/کلاینت خاص از پنل حذف یا غیرفعال شده)، سرور معمولاً
    خیلی سریع کانکشن را می‌بندد. اگر معتبر باشد، سرور کانکشن را باز نگه
    می‌دارد (منتظر دیتای بعدی از کلاینت) — همین تفاوت رفتار signal ماست.
    """
    protocol = cfg.get("protocol")
    auth = cfg.get("auth")
    net = cfg.get("net_params") or {}
    if protocol not in ("vless", "trojan") or not auth:
        return None

    security = net.get("security", "none")
    network = net.get("network", "tcp")
    if security == "reality":
        # با reality، TLS ساده (بدون fingerprint واقعی کلاینت) معمولاً به
        # سایتِ دکوی fallback می‌رود نه به خودِ سرویس پروکسی — این چک برای
        # reality قابل‌اعتماد نیست، پس صادقانه fallback به TCP می‌کنیم.
        return None
    if network not in ("tcp", "ws", "httpupgrade"):
        # grpc/... فعلاً پیاده‌سازی نشده
        return None
    if protocol == "trojan" and security != "tls":
        # trojan بدون TLS عملاً استاندارد نیست/به‌ندرت پیش می‌آید
        return None

    port_i = int(cfg["port"]) if str(cfg.get("port") or "").isdigit() else None
    if not port_i:
        return None

    writer = None
    try:
        if security == "tls":
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(ip, port_i, ssl=ctx, server_hostname=net.get("sni") or ip),
                timeout=timeout,
            )
        else:
            reader, writer = await asyncio.wait_for(asyncio.open_connection(ip, port_i), timeout=timeout)

        if network in ("ws", "httpupgrade"):
            ok = await _ws_upgrade(reader, writer, net.get("ws_host") or ip, net.get("ws_path") or "/")
            if not ok:
                # یک پاسخ HTTP کامل گرفتیم ولی 101 نبود — یعنی سرور روی این
                # هاست/مسیر واقعاً درخواست را آپگرید نکرد. برخلاف تایم‌اوت/قطع
                # کانکشن (که در بلوک except پایین به "offline" می‌رسد و مبهم
                # است)، این یک پاسخ صریح و قطعی است، مخصوصاً برای کانفیگ‌های
                # پشتِ دامنه‌ی کاور (مثل www.speedtest.net با
                # Host: <دامنه‌ی واقعی>) که TCP خامِ آن‌ها ممکن است همیشه باز
                # بماند حتی وقتی بک‌اند واقعی خاموش است. قبلاً اینجا None
                # برمی‌گشت که باعث می‌شد کد به‌جای این نتیجه‌ی قطعی، به نتیجه‌ی
                # نادرستِ TCP خام ("online") fallback کند.
                return "offline"

        if protocol == "vless":
            # مثل URL-Test کلاینت‌های Xray/libXray، مقصد واقعیِ تست را در خودِ
            # VLESS destination می‌گذاریم؛ سپس یک HEAD از همان مقصد می‌فرستیم.
            # این مهم است چون صرفاً نگه داشتن socket باز، سالم بودن outbound را
            # ثابت نمی‌کند.
            header = _vless_header(auth, _PROBE_HOST, _PROBE_PORT)
            if not header:
                return None
        else:
            header = _trojan_header(auth, dst_port=_PROBE_PORT)

        # تا اینجا فقط inbound/transport را تست کرده بودیم. حالا یک درخواست
        # HTTP واقعی از داخل همان تونل عبور می‌دهیم؛ این همان بخش مهمی است که
        # وضعیت «TCP باز ولی اینترنت/route خراب» را از ONLINE جدا می‌کند.
        payload = _ws_frame(header) if network == "ws" else header
        writer.write(payload)
        await writer.drain()

        # URL-test سبک: HEAD روی generate_204. هر پاسخ معتبر HTTP (حتی 4xx/5xx)
        # نشان می‌دهد تونل تا مقصد رسیده؛ خطای socket/timeout یعنی OFFLINE.
        http_req = (
            f"HEAD {_PROBE_PATH} HTTP/1.1\r\n"
            f"Host: {_PROBE_HOST}\r\n"
            "Connection: close\r\n"
            "User-Agent: ShopVPN-ConfigHealth/1.0\r\n\r\n"
        ).encode("ascii")
        writer.write(_ws_frame(http_req) if network == "ws" else http_req)
        await writer.drain()

        # در VLESS response header ممکن است قبل از HTTP response چند بایت
        # پروتکلی بیاید؛ بنابراین صرفاً startswith("HTTP/") نکن و تا پیدا شدن
        # status-line یا پایان مهلت، داده را جمع کن.
        deadline = time.monotonic() + timeout
        buf = b""
        while time.monotonic() < deadline and len(buf) < 16384:
            remaining = max(0.05, deadline - time.monotonic())
            chunk = await asyncio.wait_for(reader.read(2048), timeout=remaining)
            if not chunk:
                return "offline"
            if network == "ws":
                # بعد از handshake، WebSocket framing فعال است؛ برای health
                # check باید payload فریم‌های دریافتی را استخراج کنیم.
                frames = _extract_ws_payloads(chunk)
                if frames:
                    buf += b"".join(frames)
            else:
                buf += chunk

            if re.search(rb"HTTP/1\.[01]\s+[1-5][0-9][0-9](?:\s|\r|$)", buf):
                return "online"

        return "offline"
    except (asyncio.TimeoutError, OSError, ConnectionError, ssl.SSLError):
        return "offline"
    except Exception:
        return None
    finally:
        if writer is not None:
            try:
                writer.close()
            except Exception:
                pass


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

async def scan_subscription(
    link: str,
    *,
    force_refresh: bool = False,
    check_status: bool = True,
    tcp_timeout: float = _TCP_TIMEOUT,
) -> dict:
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
    proto_status_map = {}
    if check_status and ips:
        tcp_sem = asyncio.Semaphore(_TCP_CONCURRENCY)
        pairs = list({(c["ip"], int(c["port"])) for c in configs if c["ip"] and str(c["port"]).isdigit()})
        results = await asyncio.gather(*(_tcp_check(ip, port, tcp_sem, timeout=tcp_timeout) for ip, port in pairs))
        for (ip, port), st in zip(pairs, results):
            # کلید (ip, port) نه فقط ip — وگرنه اگه چند کانفیگ روی یک IP با
            # پورت‌های متفاوت باشن (مثلاً 443 و 8443)، آنلاین‌بودن یکی باعث
            # می‌شد همه‌ی کانفیگ‌های همون IP «آنلاین» نشون داده بشن، حتی
            # اونی که پورتش واقعاً بسته‌ست.
            status_map[(ip, port)] = st

        # چک سطح پروتکل (نه فقط TCP): کلید (ip, port, auth) چون ممکنه چند
        # کلاینت/کانفیگ مختلف روی همون inbound (همون ip+port) باشن — یکی
        # روی پنل غیرفعال شده باشه و بقیه فعال؛ TCP به‌تنهایی این‌ها رو از
        # هم تشخیص نمی‌ده چون پورت خودش هنوز بازه.
        proto_keys = list({
            (c["ip"], int(c["port"]), c.get("auth"))
            for c in configs
            if c["ip"] and str(c.get("port") or "").isdigit() and c.get("auth")
            and status_map.get((c["ip"], int(c["port"]))) == "online"  # اگه پورت خودش بسته‌ست، چک پروتکل لازم نیست
        })
        proto_sem = asyncio.Semaphore(_TCP_CONCURRENCY)
        proto_results = await asyncio.gather(*(
            _protocol_probe(
                next(c for c in configs if c["ip"] == ip and str(c["port"]) == str(port) and c.get("auth") == auth),
                ip, timeout=tcp_timeout,
            )
            for ip, port, auth in proto_keys
        ))
        for (ip, port, auth), st in zip(proto_keys, proto_results):
            if st is not None:
                proto_status_map[(ip, port, auth)] = st

    servers = build_servers(configs, geo, status_map, proto_status_map)

    result = {
        "ok": True,
        "generated_at": int(time.time()),
        "total_configs": len(configs),
        "resolved_configs": sum(1 for c in configs if c.get("ip")),
        "total_servers": _count_distinct_servers(servers),
        "total_countries": len({s["country_code"] for s in servers if s["country_code"]}),
        "servers": servers,
    }
    _cache[link] = {"at": now, "data": result}
    return result


def build_servers(configs: list, geo: dict, status_map: dict, proto_status_map: Optional[dict] = None) -> list:
    """هر کانفیگ یک entry/پین کاملاً جدای خودش می‌شود — حتی اگر چند کانفیگ
    دقیقاً روی یک IP/سرور باشند، دیگر زیر یک عدد جمع نمی‌شوند (طبق خواسته:
    «همه‌ی کانفیگ‌ها نمایش داده بشن، نه مثلاً ۲ سرور ۳ کانفیگ»)."""
    proto_status_map = proto_status_map or {}
    servers = []
    for c in configs:
        ip = c["ip"]
        label_cc = detect_label_country(c.get("remark") or "")
        geo_entry = geo.get(ip) if ip else None

        if label_cc:
            # اولویت با کشوری که خودِ کانفیگ در نامش گفته — چون IP واقعاً
            # ممکن است پشت CDN/فرانتینگ باشد و geoip آن گمراه‌کننده باشد.
            name, lat, lon = COUNTRY_INFO[label_cc]
            cc, country, source = label_cc, name, "label"
            city = ""
            if geo_entry and geo_entry["country_code"] == label_cc:
                # geoip هم روی همان کشور توافق دارد یعنی IP پشت یک CDN
                # گمراه‌کننده نیست — پس مختصات دقیق‌تر (سطح شهر) آن را به‌جای
                # مرکز/پایتخت کشور استفاده می‌کنیم تا پین روی نقشه دقیق‌تر بیفتد.
                lat, lon, city, source = geo_entry["lat"], geo_entry["lon"], geo_entry["city"], "label+geoip"
        elif geo_entry:
            cc, country = geo_entry["country_code"], geo_entry["country"]
            lat, lon, city, source = geo_entry["lat"], geo_entry["lon"], geo_entry["city"], "geoip"
        else:
            continue  # نه در remark و نه با geoip چیزی معلوم نشد

        port_i = int(c["port"]) if str(c.get("port") or "").isdigit() else None
        tcp_status = status_map.get((ip, port_i), "unknown") if ip and port_i is not None else "unknown"
        check_method = "tcp"
        status = tcp_status
        if tcp_status == "online" and ip and port_i is not None and c.get("auth"):
            proto_status = proto_status_map.get((ip, port_i, c.get("auth")))
            if proto_status is not None:
                # پورت باز است (TCP آنلاین) اما نتیجه‌ی نهایی از چک سطح
                # پروتکل (auth واقعی همین کانفیگ) می‌آید — این همان چیزی‌ست
                # که تشخیص می‌دهد «این کانفیگ خاص» روی پنل غیرفعال شده یا نه.
                status = proto_status
                check_method = "protocol"
        remark = c.get("remark") or ""
        servers.append({
            "country": country, "country_code": cc, "city": city,
            "lat": lat, "lon": lon,
            "protocols": [{"name": c["protocol"], "count": 1}],
            "configs_count": 1,
            "status": status, "source": source, "check_method": check_method,
            "ip": ip or "", "ip_count": 1 if ip else 0,
            "sample_remarks": [remark] if remark else [],
            "remark": remark,
        })

    servers.sort(key=lambda s: (s["country"] or "", s["remark"]))
    return servers


def _count_distinct_servers(servers: list) -> int:
    """«سرور» یعنی تعداد سرورهای فیزیکی متمایز (بر اساس IP)، نه تعداد پین‌های
    روی نقشه — چون هر کانفیگ پین جدای خودش را دارد، حتی اگر چند کانفیگ
    دقیقاً روی یک سرور باشند."""
    ips_with_val = [s["ip"] for s in servers if s["ip"]]
    return len(set(ips_with_val)) + sum(1 for s in servers if not s["ip"])
