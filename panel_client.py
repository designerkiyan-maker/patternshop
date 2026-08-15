# -*- coding: utf-8 -*-
"""
ماژول اتصال به API پنل‌های Marzban و PasarGuard.

PasarGuard یک فورک از Marzban است و تقریباً همه‌ی endpoint ها یکسان‌اند
(/api/admin/token ، /api/user ، /api/system ، ...)، اما اسکیمای چند فیلد
در ورژن‌های جدیدتر (PasarGuard) تغییر کرده:

  - proxies            -> proxy_settings
  - inbounds           -> group_ids
  - expire (int epoch) -> expire (رشته‌ی ISO 8601)

به‌جای این‌که یک کلاس/ماژول جدا برای PasarGuard بسازیم، از همان یک کلاینت
با فلگ panel["is_pasarguard"] استفاده می‌کنیم؛ دقیقاً همان روشی که در
mirzabot (فایل Marzban.php، فیلد version_panel) پیاده شده است.

استفاده:
    from panel_client import PanelClient

    client = PanelClient(panel_row, db)   # panel_row = دیکشنری از جدول vpn_panels
    result = await client.add_user(
        username="user_123",
        data_limit_gb=30,
        expire_ts=1735689600,   # یونیکس تایم‌استمپ انقضا، یا 0 برای نامحدود
        note="سفارش #123",
    )
    if result["ok"]:
        print(result["subscription_url"], result["links"])
    else:
        print("خطا:", result["error"])
"""

import base64
import binascii
from datetime import datetime, timezone

import aiohttp

_TIMEOUT = aiohttp.ClientTimeout(total=15)
_TOKEN_TTL_SECONDS = 3600  # مثل mirzabot: توکن هر ۱ ساعت رفرش می‌شود

_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"


def _b64_decode_text(value: str) -> str:
    try:
        padded = value + "=" * (-len(value) % 4)
        return base64.b64decode(padded).decode("utf-8", errors="ignore")
    except (binascii.Error, ValueError):
        return value


def _is_probably_base64(value: str) -> bool:
    try:
        padded = value + "=" * (-len(value) % 4)
        return base64.b64encode(base64.b64decode(padded, validate=True)) == padded.encode()
    except Exception:
        return False


class PanelClient:
    """کلاینت async برای یک ردیف پنل (دیکشنری جدول vpn_panels)."""

    def __init__(self, panel: dict, db=None):
        self.panel = panel
        self.db = db
        self.panel_id = panel.get("id")
        self.base_url = (panel.get("url") or "").rstrip("/")
        self.username = panel.get("username")
        self.password = panel.get("password")
        self.is_pasarguard = bool(panel.get("is_pasarguard"))

    # ------------------------------------------------------------------ #
    # توکن ادمین
    # ------------------------------------------------------------------ #

    async def _get_token(self) -> dict:
        """توکن معتبر را برمی‌گرداند (کش‌شده در دیتابیس تا ۱ ساعت)، یا
        {"error": "..."} در صورت شکست لاگین."""
        token = self.panel.get("access_token")
        updated_at = self.panel.get("token_updated_at")
        if token and updated_at:
            try:
                age = (datetime.utcnow() - datetime.fromisoformat(updated_at)).total_seconds()
                if age < _TOKEN_TTL_SECONDS:
                    return {"access_token": token}
            except ValueError:
                pass

        url = f"{self.base_url}/api/admin/token"
        data = {"username": self.username, "password": self.password}
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        }
        try:
            async with aiohttp.ClientSession(timeout=_TIMEOUT) as session:
                async with session.post(url, data=data, headers=headers, ssl=False) as resp:
                    body = await resp.json(content_type=None)
        except Exception as e:
            return {"error": str(e)}

        if not isinstance(body, dict) or "access_token" not in body:
            detail = body.get("detail") if isinstance(body, dict) else body
            return {"error": detail or "login_failed"}

        access_token = body["access_token"]
        if self.db and self.panel_id:
            self.db.update_vpn_panel_token(self.panel_id, access_token)
            self.panel["access_token"] = access_token
            self.panel["token_updated_at"] = datetime.utcnow().isoformat()
        return {"access_token": access_token}

    async def _request(self, method: str, path: str, json_body: dict | None = None) -> dict:
        """درخواست عمومی به API پنل. خروجی همیشه دیکشنری:
        {"ok": True, "status": int, "body": dict|None} یا {"ok": False, "error": "..."}."""
        token_res = await self._get_token()
        if "error" in token_res:
            return {"ok": False, "error": token_res["error"]}

        url = f"{self.base_url}{path}"
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {token_res['access_token']}",
        }
        if json_body is not None:
            headers["Content-Type"] = "application/json"

        try:
            async with aiohttp.ClientSession(timeout=_TIMEOUT) as session:
                async with session.request(method, url, json=json_body, headers=headers, ssl=False) as resp:
                    status = resp.status
                    try:
                        body = await resp.json(content_type=None)
                    except Exception:
                        body = None
        except Exception as e:
            return {"ok": False, "error": str(e)}

        if status >= 400:
            detail = None
            if isinstance(body, dict):
                detail = body.get("detail")
            return {"ok": False, "error": detail or f"http_{status}", "status": status, "body": body}

        return {"ok": True, "status": status, "body": body}

    # ------------------------------------------------------------------ #
    # کمکی‌های تبدیل فرمت (تفاوت بین Marzban قدیمی و PasarGuard)
    # ------------------------------------------------------------------ #

    def _expire_to_payload(self, expire_ts: int):
        """۰ یعنی نامحدود. برای PasarGuard رشته‌ی ISO 8601، برای Marzban قدیمی
        همان یونیکس‌تایم خام لازم است."""
        if not expire_ts:
            return 0
        if self.is_pasarguard:
            return datetime.fromtimestamp(expire_ts, tz=timezone.utc).isoformat()
        return expire_ts

    def _expire_from_payload(self, value):
        if not value:
            return None
        if self.is_pasarguard:
            try:
                v = str(value).replace("Z", "+00:00")
                return int(datetime.fromisoformat(v).timestamp())
            except (ValueError, TypeError):
                return None
        try:
            return int(value)
        except (ValueError, TypeError):
            return None

    @property
    def _proxy_key(self) -> str:
        return "proxy_settings" if self.is_pasarguard else "proxies"

    @property
    def _inbound_key(self) -> str:
        return "group_ids" if self.is_pasarguard else "inbounds"

    # ------------------------------------------------------------------ #
    # عملیات کاربر
    # ------------------------------------------------------------------ #

    async def add_user(self, username: str, data_limit_gb: float, expire_ts: int,
                        note: str = "", data_limit_reset_strategy: str = "no_reset",
                        proxies: dict | None = None, inbounds=None) -> dict:
        """کاربر جدید در پنل می‌سازد. data_limit_gb=0 یعنی نامحدود."""
        import json as _json

        proxies = proxies if proxies is not None else _json.loads(self.panel.get("default_proxies") or "{}")
        inbounds = inbounds if inbounds is not None else _json.loads(self.panel.get("default_inbounds") or "[]")

        payload = {
            self._proxy_key: proxies,
            "data_limit": int(data_limit_gb * (1024 ** 3)) if data_limit_gb else 0,
            "username": username,
            "note": note,
            "data_limit_reset_strategy": data_limit_reset_strategy,
            "expire": self._expire_to_payload(expire_ts),
        }
        if inbounds:
            payload[self._inbound_key] = inbounds

        res = await self._request("POST", "/api/user", payload)
        if not res["ok"]:
            return {"ok": False, "error": res["error"]}

        return await self._format_user_output(res["body"])

    async def get_user(self, username: str) -> dict:
        res = await self._request("GET", f"/api/user/{username}")
        if not res["ok"]:
            return {"ok": False, "error": res["error"]}
        return await self._format_user_output(res["body"])

    async def modify_user(self, username: str, **fields) -> dict:
        """فیلدهای رایج: data_limit_gb, expire_ts, status ('active'/'disabled')."""
        payload = {}
        if "data_limit_gb" in fields:
            gb = fields["data_limit_gb"]
            payload["data_limit"] = int(gb * (1024 ** 3)) if gb else 0
        if "expire_ts" in fields:
            payload["expire"] = self._expire_to_payload(fields["expire_ts"])
        if "status" in fields:
            payload["status"] = fields["status"]
        if "note" in fields:
            payload["note"] = fields["note"]

        res = await self._request("PUT", f"/api/user/{username}", payload)
        if not res["ok"]:
            return {"ok": False, "error": res["error"]}
        return await self._format_user_output(res["body"])

    async def remove_user(self, username: str) -> dict:
        res = await self._request("DELETE", f"/api/user/{username}")
        if not res["ok"]:
            return {"ok": False, "error": res["error"]}
        return {"ok": True}

    async def revoke_sub(self, username: str) -> dict:
        """لینک ساب کاربر را ابطال و یک لینک جدید صادر می‌کند (مثلاً بعد از لو رفتن)."""
        res = await self._request("POST", f"/api/user/{username}/revoke_sub", {})
        if not res["ok"]:
            return {"ok": False, "error": res["error"]}
        return await self._format_user_output(res["body"])

    async def get_system_stats(self) -> dict:
        res = await self._request("GET", "/api/system")
        if not res["ok"]:
            return {"ok": False, "error": res["error"]}
        body = res["body"] or {}
        active_users = (
            body.get("active_users") if self.is_pasarguard else body.get("users_active")
        )
        if active_users is None:
            active_users = body.get("users_active") or body.get("active_users") or body.get("online_users") or 0
        return {
            "ok": True,
            "version": body.get("version"),
            "total_user": body.get("total_user"),
            "active_users": active_users,
            "mem_total": body.get("mem_total"),
            "mem_used": body.get("mem_used"),
            "incoming_bandwidth": body.get("incoming_bandwidth"),
            "outgoing_bandwidth": body.get("outgoing_bandwidth"),
        }

    # ------------------------------------------------------------------ #
    # خروجی یکسان‌شده‌ی کاربر (صرف‌نظر از این‌که Marzban قدیمی یا PasarGuard باشد)
    # ------------------------------------------------------------------ #

    async def _format_user_output(self, body: dict | None) -> dict:
        if not body:
            return {"ok": False, "error": "empty_response"}
        if body.get("detail"):
            return {"ok": False, "error": body["detail"]}

        sub_url = body.get("subscription_url") or ""
        if sub_url and not sub_url.startswith("http"):
            sub_url = f"{self.base_url}/{sub_url.lstrip('/')}"

        links = body.get("links")
        if not links and sub_url:
            # لینک‌های خام (کانفیگ‌ها) داخل خود پاسخ نبودند؛ باید از روی
            # subscription_url خودمان بخوانیم (رفتار PasarGuard)
            links = await self._fetch_subscription_configs(sub_url)

        return {
            "ok": True,
            "username": body.get("username"),
            "status": body.get("status"),
            "data_limit": body.get("data_limit"),
            "used_traffic": body.get("used_traffic"),
            "expire": self._expire_from_payload(body.get("expire")),
            "subscription_url": sub_url,
            "links": links or [],
            "raw": body,
        }

    async def _fetch_subscription_configs(self, sub_url: str) -> list:
        """محتوای لینک ساب را می‌گیرد و اگر base64 بود دیکد می‌کند (دقیقاً
        معادل outputlink()+isBase64() در mirzabot)."""
        try:
            async with aiohttp.ClientSession(timeout=_TIMEOUT) as session:
                async with session.get(sub_url, headers={"User-Agent": _UA}, ssl=False) as resp:
                    text = await resp.text()
        except Exception:
            return []

        content = _b64_decode_text(text) if _is_probably_base64(text.strip()) else text
        return [line.strip() for line in content.splitlines() if line.strip()]


# ---------------------------------------------------------------------------
# تحویل خودکار از طریق پنل (ساخت کاربر واقعی روی Marzban/PasarGuard)
# ---------------------------------------------------------------------------

import secrets


def _row_get(row, key, default=None):
    """دسترسی امن به یک فیلد، چه row یک dict باشد چه sqlite3.Row (که .get ندارد)."""
    try:
        value = row[key]
        return value if value is not None else default
    except (KeyError, IndexError, TypeError):
        return default


async def provision_panel_configs(db, product: dict, user_tg_id: int, quantity: int = 1):
    """برای محصولی که به یک پنل VPN وصل است (product["panel_id"])، به تعداد
    quantity کاربر واقعی روی پنل می‌سازد و رکورد متناظرش را در جدول configs
    (دقیقاً هم‌شکل خروجی db.take_unused_configs) ثبت می‌کند تا بقیه‌ی سیستم
    (تحویل به کاربر، یادآوری تمدید، نمایش سفارش‌ها) بدون تغییر کار کنند.

    خروجی: (results, error)
      - موفق: (لیستی از {"id","link","expires_at"}, None)
      - ناموفق: (None, "پیام خطای فارسی برای نمایش به کاربر/ادمین")
    """
    panel = db.get_vpn_panel(product["panel_id"])
    if not panel or not panel.get("is_active"):
        return None, "پنل متصل به این محصول یافت نشد یا غیرفعال است. با ادمین تماس بگیرید."

    client = PanelClient(panel, db)
    duration_days = _row_get(product, "duration_days") or 30
    data_limit_gb = _row_get(product, "panel_data_limit_gb") or 0
    expire_ts = int(datetime.now(timezone.utc).timestamp()) + duration_days * 86400

    created_usernames = []
    results = []
    for _ in range(max(1, quantity)):
        username = f"tg{user_tg_id}_{secrets.token_hex(3)}"
        res = await client.add_user(
            username=username,
            data_limit_gb=data_limit_gb,
            expire_ts=expire_ts,
            note=f"ShopVPN | telegram:{user_tg_id}",
        )
        if not res.get("ok"):
            for done_username in created_usernames:
                try:
                    await client.remove_user(done_username)
                except Exception:
                    pass
            return None, f"ساخت کاربر روی پنل ناموفق بود: {res.get('error', 'خطای نامشخص')}"

        link = res.get("subscription_url") or (res.get("links") or [None])[0]
        if not link:
            for done_username in created_usernames:
                try:
                    await client.remove_user(done_username)
                except Exception:
                    pass
            return None, "کاربر روی پنل ساخته شد اما لینک اشتراک دریافت نشد."

        created_usernames.append(username)
        config_row = db.create_provisioned_config(product["id"], user_tg_id, link, expire_ts)
        results.append(config_row)

    return results, None


async def fulfill_order_configs(db, product: dict, user_tg_id: int, quantity: int = 1):
    """نقطه‌ی واحد تصمیم‌گیری برای تحویل کانفیگ سفارش: اگر محصول به پنل وصل است
    از پنل واقعی ساخته می‌شود، در غیر این صورت از انبار دستی configs برداشته
    می‌شود. جایگزین صدا زدن مستقیم db.take_unused_configs در همه‌ی مسیرهای
    تسویه‌ی سفارش (بات اصلی/نمایندگی، مینی‌اپ، پرداخت کریپتو).

    خروجی: (results, error) — همان قرارداد provision_panel_configs.
    """
    if product and _row_get(product, "panel_id"):
        return await provision_panel_configs(db, product, user_tg_id, quantity)

    results = db.take_unused_configs(product["id"], user_tg_id, quantity)
    if not results:
        return None, "موجودی این محصول تمام شده است."
    return results, None
