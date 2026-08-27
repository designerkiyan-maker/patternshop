"""
Provider پنل 3X-UI (MHSanaei/3x-ui).

روش احراز هویت: Bearer API Token (نه لاگین با یوزر/پس روی /login).

چرا این تغییر لازم بود:
- نسخه‌های جدید 3X-UI (v3.x به بعد) یک لایه‌ی CSRF hardening روی /login
  اضافه کرده‌اند که لاگین برنامه‌نویسی (بدون مرورگر/کوکی از قبل) را با
  خطای 403 رد می‌کند (باگ شناخته‌شده‌ی خودِ پروژه‌ی 3x-ui، مثلاً ایشوهای
  #4227 و #5622). یعنی روش قدیمی «لاگین با یوزر/پس و گرفتن کوکی سشن» روی
  پنل‌های امروزی اصلاً کار نمی‌کند.
- خودِ 3X-UI رسمی برای همین حالت یک روش جایگزین دارد: از داخل پنل
  Settings ← Security یک «API Token» بساز و آن را به‌جای پسورد به‌صورت
  هدر Authorization: Bearer بفرست. تمام مسیرهای /panel/api/* هر دو روش
  (کوکی سشن یا Bearer Token) را قبول می‌کنند.
- پروژه‌ی mirzabot (فایل x-ui_single.php) هم دقیقاً همین روش را استفاده
  می‌کند: هیچ‌وقت /login صدا زده نمی‌شود؛ همان مقدار پسورد مستقیم به‌عنوان
  Bearer token فرستاده می‌شود. این provider هم برای هماهنگی و برای این‌که
  واقعاً کار کند، از همین روش پیروی می‌کند.

نکته‌ی مهم برای ادمین: توی فیلد «رمز عبور ادمین پنل» موقع افزودن سرور،
باید API Token (از Settings ← Security پنل 3X-UI) وارد شود، نه پسورد
واقعی ادمین. فیلد «نام کاربری» برای این نوع پنل استفاده نمی‌شود (هر
مقداری قابل قبول است).

بقیه‌ی جزئیات مثل قبل:
- هر «کلاینت» باید داخل یک inbound مشخص اضافه شود (نه مستقل)؛ به همین دلیل
  روی هر سرور یک xui_inbound_id ذخیره می‌کنیم (ادمین موقع افزودن سرور از
  بین inbound های موجود روی پنل انتخاب می‌کند).
- خودِ API لینک اشتراک برنمی‌گرداند؛ لینک از xui_sub_base_url (که ادمین وارد
  می‌کند) + یک subId تصادفی که خودمان موقع ساخت کلاینت تولید می‌کنیم ساخته
  می‌شود.
- شناسه‌ی یکتای کاربر «email» است (اینجا از همان username پروژه استفاده
  می‌شود)؛ خود کلاینت هم یک UUID جدا دارد که برای عملیات حذف لازم است.
"""
import json
import secrets
import time
import uuid
import aiohttp

from .base import BasePanelProvider, PanelUserResult, PanelError, PanelUsernameTakenError


class ThreeXUIProvider(BasePanelProvider):

    def _base_url(self) -> str:
        return self.server["api_url"].rstrip("/")

    def _session(self) -> aiohttp.ClientSession:
        """یک ClientSession با هدر Bearer token می‌سازد (بدون کوکی/لاگین).

        نکته: پنل‌های 3X-UI تقریباً همیشه با گواهی self-signed یا روی http
        بالا می‌آیند (خودِ نصب‌کننده‌ی رسمی هم گزینه‌ی رد کردن SSL را می‌دهد؛
        مثل mirzabot که در CurlRequest همه‌جا CURLOPT_SSL_VERIFYPEER را
        false می‌گذارد)، پس اینجا هم verify گواهی را غیرفعال می‌کنیم."""
        token = self.server["api_password"]
        connector = aiohttp.TCPConnector(ssl=False)
        return aiohttp.ClientSession(
            connector=connector,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            timeout=aiohttp.ClientTimeout(total=20),
        )

    async def list_inbounds(self) -> list:
        """برای فلوی افزودن سرور: لیست inbound های پنل را برمی‌گرداند تا ادمین
        یکی را انتخاب کند. هر آیتم: {id, remark, protocol, port}."""
        async with self._session() as session:
            try:
                async with session.get(f"{self._base_url()}/panel/api/inbounds/list") as resp:
                    if resp.status in (401, 403):
                        raise PanelError(
                            f"خطا در احراز هویت (کد {resp.status}): API Token اشتباه است یا "
                            "هنوز از داخل پنل (Settings ← Security) API Token نساخته‌ای."
                        )
                    if resp.status >= 400:
                        text = await resp.text()
                        raise PanelError(f"خطا در دریافت لیست inbound (کد {resp.status}): {text[:300]}")
                    data = await resp.json()
            except aiohttp.ClientError as e:
                raise PanelError(f"خطا در اتصال به پنل: {e}") from e

        if data.get("success") is False:
            raise PanelError(data.get("msg") or "دریافت لیست inbound ناموفق بود.")
        inbounds = data.get("obj") or []
        return [
            {"id": ib["id"], "remark": ib.get("remark", ""), "protocol": ib.get("protocol", ""), "port": ib.get("port")}
            for ib in inbounds
        ]

    async def _get_inbound(self, session: aiohttp.ClientSession, inbound_id: int) -> dict:
        async with session.get(f"{self._base_url()}/panel/api/inbounds/get/{inbound_id}") as resp:
            if resp.status in (401, 403):
                raise PanelError(f"خطا در احراز هویت (کد {resp.status}): API Token را بررسی کن.")
            if resp.status >= 400:
                text = await resp.text()
                raise PanelError(f"خطا در دریافت inbound (کد {resp.status}): {text[:300]}")
            data = await resp.json()
        obj = data.get("obj")
        if not obj:
            raise PanelError("inbound تنظیم‌شده روی این سرور دیگر پیدا نشد.")
        return obj

    def _build_client(self, username: str, protocol: str, volume_gb: int, duration_days: int) -> tuple:
        """کلاینت مناسب پروتکل را می‌سازد؛ خروجی: (client_dict, sub_id)"""
        sub_id = secrets.token_hex(8)
        client_uuid = str(uuid.uuid4())
        expiry_ms = int((time.time() + duration_days * 86400) * 1000)
        data_limit_bytes = int(volume_gb * (1024 ** 3))
        client = {
            "email": username,
            "enable": True,
            "expiryTime": expiry_ms,
            "totalGB": data_limit_bytes,
            "limitIp": 0,
            "subId": sub_id,
            "tgId": "",
        }
        if protocol in ("vless", "vmess"):
            client["id"] = client_uuid
        elif protocol == "trojan":
            client["password"] = client_uuid
        elif protocol in ("shadowsocks", "shadowsocks-2022"):
            client["password"] = client_uuid
        else:
            client["id"] = client_uuid
        return client, sub_id

    async def create_user(self, username: str, volume_gb: int, duration_days: int) -> PanelUserResult:
        inbound_id = self.server["xui_inbound_id"]
        sub_base_url = self.server["xui_sub_base_url"]
        if not inbound_id or not sub_base_url:
            raise PanelError("این سرور هنوز کامل تنظیم نشده (inbound یا آدرس Subscription خالی است).")

        async with self._session() as session:
            inbound = await self._get_inbound(session, inbound_id)
            client, sub_id = self._build_client(username, inbound.get("protocol", "vless"), volume_gb, duration_days)
            payload = {"id": inbound_id, "settings": json.dumps({"clients": [client]})}
            try:
                async with session.post(f"{self._base_url()}/panel/api/inbounds/addClient", json=payload) as resp:
                    if resp.status in (401, 403):
                        raise PanelError(f"خطا در احراز هویت (کد {resp.status}): API Token را بررسی کن.")
                    if resp.status >= 400:
                        text = await resp.text()
                        raise PanelError(f"خطا در ساخت کاربر (کد {resp.status}): {text[:300]}")
                    data = await resp.json()
            except aiohttp.ClientError as e:
                raise PanelError(f"خطا در اتصال به پنل: {e}") from e
            if data.get("success") is False:
                msg = data.get("msg") or ""
                if "duplicate" in msg.lower() or "exist" in msg.lower():
                    raise PanelUsernameTakenError(f"نام کاربری «{username}» روی پنل تکراری است")
                raise PanelError(msg or "ساخت کاربر روی پنل ناموفق بود.")

        sub_url = f"{sub_base_url.rstrip('/')}/{sub_id}"
        return PanelUserResult(username=username, subscription_url=sub_url, raw=client)

    async def delete_user(self, username: str) -> bool:
        inbound_id = self.server["xui_inbound_id"]
        async with self._session() as session:
            inbound = await self._get_inbound(session, inbound_id)
            settings = json.loads(inbound.get("settings") or "{}")
            client_id = None
            for c in settings.get("clients", []):
                if c.get("email") == username:
                    client_id = c.get("id") or c.get("password")
                    break
            if not client_id:
                return False
            try:
                async with session.post(
                    f"{self._base_url()}/panel/api/inbounds/{inbound_id}/delClient/{client_id}"
                ) as resp:
                    return resp.status < 400
            except aiohttp.ClientError as e:
                raise PanelError(f"خطا در اتصال به پنل: {e}") from e

    async def get_user_usage(self, username: str) -> dict:
        async with self._session() as session:
            try:
                async with session.get(f"{self._base_url()}/panel/api/inbounds/getClientTraffics/{username}") as resp:
                    if resp.status in (401, 403):
                        raise PanelError(f"خطا در احراز هویت (کد {resp.status}): API Token را بررسی کن.")
                    if resp.status >= 400:
                        text = await resp.text()
                        raise PanelError(f"خطا در دریافت اطلاعات کاربر (کد {resp.status}): {text[:300]}")
                    data = await resp.json()
            except aiohttp.ClientError as e:
                raise PanelError(f"خطا در اتصال به پنل: {e}") from e

        obj = data.get("obj") or {}
        used = (obj.get("up") or 0) + (obj.get("down") or 0)
        return {
            "used_bytes": used,
            "data_limit_bytes": obj.get("total", 0) or 0,
            "status": "active" if obj.get("enable") else "disabled",
        }

    async def test_connection(self) -> bool:
        try:
            async with self._session() as session:
                async with session.get(f"{self._base_url()}/panel/api/inbounds/list") as resp:
                    if resp.status in (401, 403):
                        return False
                    if resp.status >= 400:
                        return False
                    data = await resp.json()
                    return bool(data.get("success", True))
        except (aiohttp.ClientError, PanelError):
            return False
