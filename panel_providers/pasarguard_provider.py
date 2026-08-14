"""
Provider پنل PasarGuard.

طبق مستندات رسمی (https://docs.pasarguard.org/fa/panel/api_keys/) روش
پیشنهادی احراز هویت، کلید API ثابت (X-Api-Key) است - نه لاگین با یوزر/پس.
چون کتابخانه‌ی پایتونی رسمی `pasarguard` این روش را پشتیبانی نمی‌کند (فقط
Bearer token از طریق لاگین)، اینجا مستقیم با aiohttp روی REST API پنل کار
می‌کنیم.

نکته: مسیرهای زیر بر اساس الگوی REST خانواده‌ی Marzban/PasarGuard (که این
مستندات از آن مشتق شده) تنظیم شده‌اند. اگر پنل خاصی مسیر متفاوتی داشت، فقط
همین یک فایل نیاز به اصلاح دارد.
"""
import time
import aiohttp

from .base import BasePanelProvider, PanelUserResult, PanelError, PanelUsernameTakenError


class PasarguardProvider(BasePanelProvider):

    def _headers(self) -> dict:
        return {
            "X-Api-Key": self.server["api_key"],
            "Content-Type": "application/json",
        }

    def _base_url(self) -> str:
        return self.server["api_url"].rstrip("/")

    async def create_user(self, username: str, volume_gb: int, duration_days: int) -> PanelUserResult:
        payload = {
            "username": username,
            "data_limit": int(volume_gb * (1024 ** 3)),
            "expire": int(time.time()) + duration_days * 86400,
            "status": "active",
            "note": "ساخته‌شده توسط ShopVPN (کانفیگ شخصی)",
        }
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(
                    f"{self._base_url()}/api/admin/user",
                    json=payload, headers=self._headers(), timeout=aiohttp.ClientTimeout(total=20),
                ) as resp:
                    if resp.status == 409:
                        raise PanelUsernameTakenError(f"نام کاربری «{username}» روی پنل تکراری است")
                    if resp.status == 401:
                        raise PanelError("کلید API نامعتبر است.")
                    if resp.status >= 400:
                        text = await resp.text()
                        raise PanelError(f"خطا در ساخت کاربر روی پنل (کد {resp.status}): {text[:300]}")
                    data = await resp.json()
            except aiohttp.ClientError as e:
                raise PanelError(f"خطا در اتصال به پنل: {e}") from e

        sub_url = data.get("subscription_url") or ""
        if sub_url.startswith("/"):
            sub_url = self._base_url() + sub_url

        return PanelUserResult(username=data.get("username", username), subscription_url=sub_url, raw=data)

    async def delete_user(self, username: str) -> bool:
        async with aiohttp.ClientSession() as session:
            try:
                async with session.delete(
                    f"{self._base_url()}/api/admin/user/{username}",
                    headers=self._headers(), timeout=aiohttp.ClientTimeout(total=20),
                ) as resp:
                    if resp.status == 401:
                        raise PanelError("کلید API نامعتبر است.")
                    return resp.status < 400
            except aiohttp.ClientError as e:
                raise PanelError(f"خطا در اتصال به پنل: {e}") from e

    async def get_user_usage(self, username: str) -> dict:
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(
                    f"{self._base_url()}/api/admin/user/{username}",
                    headers=self._headers(), timeout=aiohttp.ClientTimeout(total=20),
                ) as resp:
                    if resp.status == 401:
                        raise PanelError("کلید API نامعتبر است.")
                    if resp.status >= 400:
                        text = await resp.text()
                        raise PanelError(f"خطا در دریافت اطلاعات کاربر (کد {resp.status}): {text[:300]}")
                    data = await resp.json()
            except aiohttp.ClientError as e:
                raise PanelError(f"خطا در اتصال به پنل: {e}") from e
        return {
            "used_bytes": data.get("used_traffic", 0) or 0,
            "data_limit_bytes": data.get("data_limit", 0) or 0,
            "status": data.get("status", ""),
        }

    async def test_connection(self) -> bool:
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(
                    f"{self._base_url()}/api/admin/users",
                    headers=self._headers(), timeout=aiohttp.ClientTimeout(total=15),
                    params={"offset": 0, "limit": 1},
                ) as resp:
                    return resp.status < 400
            except aiohttp.ClientError:
                return False
