# -*- coding: utf-8 -*-
"""
تحویل حرفه‌ای کانفیگ به کاربر

این ماژول یک تابع مشترک برای هر دو مسیر تحویل کانفیگ فراهم می‌کند:
  ۱) خرید از کیف پول/کد تخفیف که به‌صورت خودکار تایید می‌شود (handlers_user.py)
  ۲) خرید با رسید کارت‌به‌کارت که ادمین دستی تایید می‌کند (handlers_admin.py)

خروجی شامل: عکس QR کد لینک اشتراک، مشخصات کامل سفارش، و پیام تشکر است.
"""

from datetime import datetime
from io import BytesIO

import qrcode
from aiogram import Bot
from aiogram.types import BufferedInputFile


def _build_qr_photo(link: str, filename: str = "config_qr.png") -> BufferedInputFile:
    """ساخت عکس QR کد از روی لینک اشتراک و برگرداندن آن به‌صورت فایل قابل ارسال در تلگرام."""
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=8,
        border=3,
    )
    qr.add_data(link)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    buffer = BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return BufferedInputFile(buffer.read(), filename=filename)


async def deliver_config_to_user(
    bot: Bot,
    user_tg_id: int,
    product_name: str,
    link: str,
    final_price: int = None,
    order_id: int = None,
) -> None:
    """
    ارسال حرفه‌ای کانفیگ خریداری‌شده به کاربر: عکس QR کد لینک اشتراک + مشخصات
    کامل سفارش + پیام تشکر، و در پیام بعدی خودِ لینک به‌صورت متنی و قابل کپی.
    """
    jalali_ready_date = datetime.now().strftime("%Y-%m-%d %H:%M")

    caption = "🎉 با تشکر از خرید شما!\n\n"
    caption += "✅ کانفیگ شما با موفقیت صادر و آماده استفاده است.\n\n"
    caption += "🧾 مشخصات سفارش\n"
    if order_id:
        caption += f"┣ 🆔 شماره سفارش: #{order_id}\n"
    caption += f"┣ 📦 محصول: {product_name}\n"
    if final_price is not None:
        caption += f"┣ 💰 مبلغ پرداخت‌شده: {final_price:,} تومان\n"
    caption += f"┗ 📅 تاریخ تحویل: {jalali_ready_date}\n\n"
    caption += (
        "📱 برای اتصال، کافیست تصویر QR بالا را با اپلیکیشن V2Ray خود اسکن کنید؛ "
        "یا لینک اشتراک را که در پیام بعدی برایتان ارسال می‌شود، کپی و در بخش "
        "«افزودن اشتراک/Subscription» اپلیکیشن وارد نمایید.\n\n"
        "🔒 این کانفیگ به‌صورت اختصاصی فقط برای شما صادر شده؛ لطفاً آن را با دیگران به اشتراک نگذارید "
        "تا کیفیت اتصال شما حفظ شود.\n\n"
        "📞 در صورت بروز هرگونه مشکل در اتصال، از بخش «ارتباط با پشتیبانی» با ما در تماس باشید.\n\n"
        "🙏 از اعتماد شما سپاسگزاریم و امیدواریم از سرویس‌مان راضی باشید."
    )

    try:
        qr_photo = _build_qr_photo(link)
        await bot.send_photo(user_tg_id, qr_photo, caption=caption)
    except Exception:
        # اگر ساخت/ارسال QR به هر دلیلی ناموفق بود، حداقل متن اطلاعات برای کاربر ارسال شود
        await bot.send_message(user_tg_id, caption)

    await bot.send_message(
        user_tg_id,
        f"🔗 لینک اشتراک شما (برای کپی):\n`{link}`",
        parse_mode="Markdown",
    )
