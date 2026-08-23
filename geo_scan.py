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
  5) تجمیع بر اساس IP (چون معمولاً چند کانفیگ به یک سرور اشاره می‌کنند)

نتیجه در حافظه cache می‌شود تا هر بار دیده‌شدن داشبورد باعث اسکن کامل نشود.
"""

import asyncio
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
        if not ip or ip not in geo:
            continue
        g = geo[ip]
        entry = grouped.setdefault(ip, {
            "ip": ip,
            "country": g["country"], "country_code": g["country_code"],
            "city": g["city"], "lat": g["lat"], "lon": g["lon"],
            "protocols": {}, "configs_count": 0,
            "status": status_map.get(ip, "unknown"),
            "sample_remarks": [],
        })
        entry["configs_count"] += 1
        entry["protocols"][c["protocol"]] = entry["protocols"].get(c["protocol"], 0) + 1
        if c.get("remark") and len(entry["sample_remarks"]) < 3 and c["remark"] not in entry["sample_remarks"]:
            entry["sample_remarks"].append(c["remark"])

    servers = []
    for e in grouped.values():
        e["protocols"] = [{"name": k, "count": v} for k, v in sorted(e["protocols"].items(), key=lambda x: -x[1])]
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
