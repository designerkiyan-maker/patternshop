# -*- coding: utf-8 -*-
"""
هشدار اتمام موجودی کانفیگ.

بعد از هر بار مصرف یک کانفیگ (فروش/تحویل)، این تابع بررسی می‌کند که آیا موجودی
باقی‌مانده‌ی آن محصول به آستانه‌ی هشدار (تنظیم «low_stock_threshold») رسیده یا نه.
اگر رسیده باشد و قبلاً برای همین افت هشدار داده نشده باشد، به همه‌ی ادمین‌های همان
بات پیام هشدار می‌فرستد. وقتی موجودی دوباره بالای آستانه برود، وضعیت ریست می‌شود
تا برای افت بعدی دوباره هشدار بدهد.

send_fn باید یک تابع async باشد که (admin_telegram_id, text) می‌گیرد؛ این کار
باعث می‌شود این ماژول هم در بات (aiogram) و هم در Mini App (aiohttp خام) قابل
استفاده باشد بدون وابستگی به یک ترنسپورت خاص.
"""

import logging

logger = logging.getLogger(__name__)


async def check_and_notify_low_stock(send_fn, db, product_id: int) -> None:
    try:
        stock = db.count_available_configs(product_id)
        threshold = int(db.get_setting("low_stock_threshold", "3") or 3)
    except Exception:
        return

    should_alert = db.check_low_stock_alert_state(product_id, stock, threshold)
    if not should_alert:
        return

    product = db.get_product(product_id)
    product_name = product["name"] if product else "نامشخص"
    text = (
        "⚠️ هشدار اتمام موجودی\n\n"
        f"📦 محصول «{product_name}» فقط {stock} کانفیگ آزاد باقی مانده "
        f"(آستانه‌ی هشدار: {threshold}).\n"
        "لطفاً هرچه زودتر کانفیگ جدید به انبار اضافه کنید."
    )

    for admin_id in db.list_admins():
        try:
            await send_fn(admin_id, text)
        except Exception:
            logger.warning("ارسال هشدار موجودی کم به ادمین %s ناموفق بود.", admin_id)
