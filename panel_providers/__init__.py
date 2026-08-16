"""
نقطه‌ی ورود مشترک: get_provider(server) بر اساس server["panel_type"] نمونه‌ی
provider مناسب را برمی‌گرداند. برای اضافه‌کردن پنل جدید (Marzban، Marzneshin،
X-UI و ...):
  ۱. یک فایل جدید مثل marzban_provider.py بساز که BasePanelProvider را پیاده کند
  ۲. اینجا در PROVIDERS رجیسترش کن
همین. بقیه‌ی کد پروژه بدون تغییر کار می‌کند.
"""
from .base import BasePanelProvider, PanelUserResult, PanelError, PanelUsernameTakenError
from .pasarguard_provider import PasarguardProvider
from .threexui_provider import ThreeXUIProvider

PROVIDERS = {
    "pasarguard": PasarguardProvider,
    "3xui": ThreeXUIProvider,
}

PANEL_TYPE_LABELS = {
    "pasarguard": "PasarGuard",
    "3xui": "3X-UI",
}


def get_provider(server) -> BasePanelProvider:
    panel_type = server["panel_type"]
    cls = PROVIDERS.get(panel_type)
    if cls is None:
        raise PanelError(f"نوع پنل «{panel_type}» پشتیبانی نمی‌شود")
    return cls(server)
