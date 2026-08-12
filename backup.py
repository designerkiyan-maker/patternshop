# -*- coding: utf-8 -*-
"""
بکاپ خودکار دیتابیس.

هر بات (اصلی یا نمایندگی)، به‌طور دوره‌ای از دیتابیس خودش یک بکاپ امن می‌گیرد
(با استفاده از SQLite Backup API، که برخلاف کپی‌کردن ساده‌ی فایل، حتی اگر
دیتابیس در حال استفاده باشد باعث خرابی نمی‌شود)، آن را در پوشه‌ی «backups» کنار
همان دیتابیس ذخیره می‌کند (و فقط چند نسخه‌ی آخر را نگه می‌دارد)، و آخرین بکاپ را
برای همه‌ی ادمین‌های همان بات به‌عنوان فایل تلگرامی می‌فرستد — تا حتی اگر خود
سرور/هارد از بین برود، یک نسخه‌ی جدا هم روی تلگرام موجود باشد.
"""

import os
import glob
import sqlite3
import asyncio
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


def create_backup(db_path: str, backup_dir: str, keep: int = 14) -> Optional[str]:
    """یک بکاپ امن از دیتابیس می‌سازد و بکاپ‌های قدیمی‌تر از `keep` نسخه‌ی آخر را
    حذف می‌کند. مسیر فایل بکاپ ساخته‌شده را برمی‌گرداند، یا None اگر دیتابیس
    وجود نداشت."""
    if not os.path.exists(db_path):
        return None

    os.makedirs(backup_dir, exist_ok=True)
    base_name = os.path.splitext(os.path.basename(db_path))[0]
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(backup_dir, f"{base_name}_{timestamp}.db")

    src = sqlite3.connect(db_path)
    try:
        dst = sqlite3.connect(backup_path)
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()

    pattern = os.path.join(backup_dir, f"{base_name}_*.db")
    existing = sorted(glob.glob(pattern))
    for old_file in existing[:-keep]:
        try:
            os.remove(old_file)
        except OSError:
            pass

    return backup_path


async def backup_and_notify(bot, db, db_path: str, backup_dir: str, keep: int = 14) -> None:
    """یک بکاپ می‌گیرد و آن را برای همه‌ی ادمین‌های همین بات ارسال می‌کند."""
    try:
        backup_path = await asyncio.to_thread(create_backup, db_path, backup_dir, keep)
    except Exception:
        logger.exception("بکاپ‌گیری از %s ناموفق بود.", db_path)
        return
    if not backup_path:
        return

    try:
        from aiogram.types import FSInputFile
    except ImportError:
        return

    file_size_mb = os.path.getsize(backup_path) / (1024 * 1024)
    caption = (
        "🗄 بکاپ خودکار دیتابیس\n"
        f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
        f"📦 حجم: {file_size_mb:.1f} مگابایت"
    )

    for admin_id in db.list_admins():
        try:
            await bot.send_document(admin_id, FSInputFile(backup_path), caption=caption)
        except Exception:
            logger.warning("ارسال بکاپ به ادمین %s ناموفق بود.", admin_id)


async def backup_loop(bot, db, db_path: str, interval_seconds: int = 86400, keep: int = 14) -> None:
    """هر `interval_seconds` (پیش‌فرض: هر ۲۴ ساعت) یک بکاپ می‌گیرد و می‌فرستد."""
    backup_dir = os.path.join(os.path.dirname(os.path.abspath(db_path)), "backups")
    # قبل از اولین چرخه کمی صبر می‌کنیم تا بات کاملاً بالا بیاید
    await asyncio.sleep(60)
    while True:
        try:
            await backup_and_notify(bot, db, db_path, backup_dir, keep=keep)
        except Exception:
            logger.exception("خطا در چرخه‌ی بکاپ‌گیری خودکار برای %s", db_path)
        await asyncio.sleep(interval_seconds)
