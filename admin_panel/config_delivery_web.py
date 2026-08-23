# -*- coding: utf-8 -*-
"""
معادل admin_panel-ی تابع deliver_config_to_user در config_delivery.py؛ همان
پیام «شیک» (عکس QR + مشخصات کامل سفارش + پیام تشکر) را برای کاربر می‌فرستد،
اما چون پنل وب مستقل نمونه‌ای از Bot در اختیار ندارد، مستقیم با Bot API خام
(از طریق admin_panel.telegram_notify) کار می‌کند.
"""

from config_delivery import build_qr_bytes, build_delivery_caption, build_summary_text
from admin_panel.telegram_notify import send_message as tg_send, send_photo as tg_send_photo
from config import BOT_TOKEN


async def deliver_config_to_user_web(
    user_tg_id: int,
    product_name: str,
    links,
    final_price: int = None,
    order_id: int = None,
) -> None:
    """نسخه‌ی پنل وب مستقل از تحویل حرفه‌ای کانفیگ؛ همان خروجی‌ای که کاربر از خودِ بات می‌بیند."""
    if isinstance(links, str):
        links = [links]
    total = len(links)

    for idx, link in enumerate(links, start=1):
        caption = build_delivery_caption(product_name, idx, total, order_id)

        sent = False
        try:
            qr_bytes = build_qr_bytes(link)
            sent = await tg_send_photo(BOT_TOKEN, user_tg_id, qr_bytes, "config_qr.png", caption)
        except Exception:
            sent = False
        if not sent:
            # اگر ساخت/ارسال QR به هر دلیلی ناموفق بود، حداقل متن اطلاعات برای کاربر ارسال شود
            await tg_send(BOT_TOKEN, user_tg_id, caption)

        await tg_send(BOT_TOKEN, user_tg_id, f"🔗 لینک اشتراک شما (برای کپی):\n`{link}`", parse_mode="Markdown")

    if final_price is not None:
        await tg_send(BOT_TOKEN, user_tg_id, build_summary_text(final_price, total))
