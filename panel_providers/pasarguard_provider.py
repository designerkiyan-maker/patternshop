"""
Provider پنل PasarGuard، با استفاده از کتابخانه‌ی رسمی async پایتون `pasarguard`
(pip install pasarguard). این کتابخانه خودش httpx + pydantic v2 را مدیریت
می‌کند؛ اینجا فقط یک لایه‌ی نازک روی آن می‌کشیم که با اینترفیس BasePanelProvider
پروژه هماهنگ باشد.
"""
from .base import BasePanelProvider, PanelUserResult, PanelError, PanelUsernameTakenError


class PasarguardProvider(BasePanelProvider):

    async def _get_client_and_token(self):
        try:
            from pasarguard import PasarguardAPI
        except ImportError as e:
            raise PanelError("کتابخانه‌ی pasarguard نصب نیست. دستور: pip install pasarguard") from e

        api = PasarguardAPI(base_url=self.server["api_url"], verify=True, timeout=20.0)
        try:
            token = await api.get_token(
                username=self.server["api_username"],
                password=self.server["api_password"],
            )
        except Exception as e:
            await api.close() if hasattr(api, "close") else None
            raise PanelError(f"خطا در احراز هویت پنل: {e}") from e
        return api, token.access_token

    async def create_user(self, username: str, volume_gb: int, duration_days: int) -> PanelUserResult:
        from pasarguard import Tools, UserCreate, UserStatus

        api, access_token = await self._get_client_and_token()
        try:
            payload = UserCreate(
                username=username,
                data_limit=Tools.gb(volume_gb),
                expire=Tools.days(duration_days),
                status=UserStatus.ACTIVE,
                note="ساخته‌شده توسط ShopVPN (کانفیگ شخصی)",
            )
            try:
                user = await api.create_user_in_all_groups(payload, token=access_token)
            except Exception as e:
                msg = str(e).lower()
                if "already" in msg or "exist" in msg or "409" in msg:
                    raise PanelUsernameTakenError(f"نام کاربری «{username}» روی پنل تکراری است") from e
                raise PanelError(f"خطا در ساخت کاربر روی پنل: {e}") from e

            return PanelUserResult(
                username=user.username,
                subscription_url=user.subscription_url,
                raw=user.model_dump() if hasattr(user, "model_dump") else None,
            )
        finally:
            if hasattr(api, "close"):
                await api.close()

    async def delete_user(self, username: str) -> bool:
        api, access_token = await self._get_client_and_token()
        try:
            try:
                await api.remove_user(username=username, token=access_token)
                return True
            except Exception as e:
                raise PanelError(f"خطا در حذف کاربر از پنل: {e}") from e
        finally:
            if hasattr(api, "close"):
                await api.close()

    async def get_user_usage(self, username: str) -> dict:
        api, access_token = await self._get_client_and_token()
        try:
            try:
                user = await api.get_user(username=username, token=access_token)
            except Exception as e:
                raise PanelError(f"خطا در دریافت اطلاعات کاربر از پنل: {e}") from e
            return {
                "used_bytes": getattr(user, "used_traffic", 0) or 0,
                "data_limit_bytes": getattr(user, "data_limit", 0) or 0,
                "status": str(getattr(user, "status", "")),
            }
        finally:
            if hasattr(api, "close"):
                await api.close()

    async def test_connection(self) -> bool:
        try:
            api, _ = await self._get_client_and_token()
            if hasattr(api, "close"):
                await api.close()
            return True
        except PanelError:
            return False
