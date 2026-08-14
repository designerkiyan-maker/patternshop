# -*- coding: utf-8 -*-
"""
کلاینت سبک برای درگاه پرداخت کریپتو Plisio (https://plisio.net)
فقط دو کار انجام می‌دهد: ساخت فاکتور (invoice) و اعتبارسنجی امضای کال‌بک.
مستندات: https://plisio.net/documentation
"""

import hmac
import hashlib
import json
import logging

import aiohttp

PLISIO_BASE_URL = "https://api.plisio.net/api/v1"
logger = logging.getLogger("plisio")


class PlisioError(Exception):
    pass


async def create_invoice(
    api_key: str,
    order_number: str,
    order_name: str,
    source_amount_usd: float,
    callback_url: str,
    email: str = None,
    currency: str = None,
    expire_min: int = None,
) -> dict:
    """یک فاکتور پرداخت کریپتو در Plisio می‌سازد.
    اگر currency مشخص نشود، کاربر خودش داخل صفحه‌ی Plisio ارز را انتخاب می‌کند.
    خروجی: dict شامل txn_id و invoice_url.
    """
    if not api_key:
        raise PlisioError("PLISIO_API_KEY تنظیم نشده است.")

    params = {
        "source_currency": "USD",
        "source_amount": f"{source_amount_usd:.2f}",
        "order_number": order_number,
        "order_name": order_name,
        "callback_url": callback_url,
        "api_key": api_key,
    }
    if currency:
        params["currency"] = currency
    if email:
        params["email"] = email
    if expire_min is not None:
        params["expire_min"] = str(int(expire_min))

    async with aiohttp.ClientSession() as session:
        async with session.get(f"{PLISIO_BASE_URL}/invoices/new", params=params, timeout=15) as resp:
            data = await resp.json()

    if data.get("status") != "success":
        message = (data.get("data") or {}).get("message") or data.get("message") or "خطای نامشخص از Plisio"
        logger.warning("ساخت فاکتور Plisio ناموفق بود: %s", message)
        raise PlisioError(str(message))

    return data["data"]


def verify_callback(api_key: str, data: dict) -> bool:
    """امضای verify_hash کال‌بک Plisio را طبق مستندات رسمی (نمونه‌ی Node.js) بررسی می‌کند:
    فیلد verify_hash را جدا می‌کنیم، بقیه‌ی دیکشنری را دقیقاً با همان ترتیبی که از JSON
    دریافت شده به رشته تبدیل می‌کنیم و HMAC-SHA1 با کلید api_key می‌گیریم.
    مهم: باید callback_url شامل ?json=true باشد تا Plisio بدنه را به‌صورت JSON بفرستد.
    """
    if not api_key:
        return False
    ordered = dict(data)
    verify_hash = ordered.pop("verify_hash", None)
    if not verify_hash:
        return False
    payload = json.dumps(ordered, separators=(",", ":"))
    computed = hmac.new(api_key.encode(), payload.encode(), hashlib.sha1).hexdigest()
    return hmac.compare_digest(computed, verify_hash)
