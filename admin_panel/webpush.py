# -*- coding: utf-8 -*-
"""
ارسال اعلان Push به مرورگر ادمین‌های پنل وب، حتی وقتی مرورگر کاملاً بسته باشد
(از طریق سرویس Push خودِ مرورگر - FCM برای Chrome/Edge، Mozilla Push برای
Firefox و غیره؛ پنل وب هیچ ارتباط مستقیمی با دستگاه ادمین ندارد و فقط یک بار
پیام را برای این سرویس‌ها می‌فرستد).

نیاز به کلیدهای VAPID دارد (بساز با: python -m admin_panel.generate_vapid_keys).
اگر تنظیم نشده باشند PUSH_ENABLED برابر False است و کل قابلیت به‌آرامی غیرفعال
می‌ماند؛ بقیه‌ی پنل بدون تغییر کار می‌کند.
"""

import asyncio
import json
import logging

from pywebpush import webpush, WebPushException

from config import VAPID_PUBLIC_KEY, VAPID_PRIVATE_KEY, VAPID_CLAIM_EMAIL

logger = logging.getLogger("admin_panel.webpush")

PUSH_ENABLED = bool(VAPID_PUBLIC_KEY and VAPID_PRIVATE_KEY)


def _send_sync(subscription_info: dict, payload: dict) -> str:
    """pywebpush بلاک‌کننده است، پس این تابع باید در یک ترد جدا اجرا شود.
    خروجی: 'ok' (ارسال شد) | 'gone' (subscription دیگر معتبر نیست، باید حذف شود) | 'error'."""
    try:
        webpush(
            subscription_info=subscription_info,
            data=json.dumps(payload, ensure_ascii=False),
            vapid_private_key=VAPID_PRIVATE_KEY,
            vapid_claims={"sub": f"mailto:{VAPID_CLAIM_EMAIL}"},
        )
        return "ok"
    except WebPushException as e:
        status = getattr(e.response, "status_code", None)
        if status in (404, 410):
            return "gone"
        logger.warning("ارسال Web Push ناموفق بود (status=%s): %s", status, e)
        return "error"
    except Exception:
        logger.exception("خطای غیرمنتظره در ارسال Web Push")
        return "error"


async def send_push(sub_row, payload: dict) -> str:
    """sub_row باید کلیدهای endpoint/p256dh/auth داشته باشد (sqlite Row یا dict)."""
    if not PUSH_ENABLED:
        return "error"
    subscription_info = {
        "endpoint": sub_row["endpoint"],
        "keys": {"p256dh": sub_row["p256dh"], "auth": sub_row["auth"]},
    }
    return await asyncio.to_thread(_send_sync, subscription_info, payload)
