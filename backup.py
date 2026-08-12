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
import shutil
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


def is_valid_sqlite_db(file_path: str) -> bool:
    """بررسی سطحی که فایل آپلودشده واقعاً یک دیتابیس sqlite سالم است، نه یک
    فایل دلخواه/خراب. برای جلوگیری از این‌که یک فایل اشتباه جایگزین دیتابیس
    اصلی شود و کل بات را از کار بیندازد."""
    if not os.path.exists(file_path) or os.path.getsize(file_path) < 100:
        return False
    try:
        with open(file_path, "rb") as f:
            header = f.read(16)
        if header != b"SQLite format 3\x00":
            return False
        conn = sqlite3.connect(file_path)
        try:
            # integrity_check کامل روی فایل‌های بزرگ کند است؛ همین که فایل
            # باز می‌شود و حداقل یک جدول قابل‌خواندن دارد کافی است.
            conn.execute("SELECT name FROM sqlite_master LIMIT 1")
            return True
        finally:
            conn.close()
    except sqlite3.Error:
        return False


def restore_backup(db, db_path: str, uploaded_file_path: str) -> str:
    """دیتابیس فعلی را با فایل بکاپ آپلودشده جایگزین می‌کند.

    قبل از جایگزینی، از دیتابیس فعلی هم یک نسخه‌ی «قبل از بازیابی» گرفته
    می‌شود تا در صورت اشتباه قابل برگشت باشد. مسیر همان نسخه‌ی پیشین را
    برمی‌گرداند.
    """
    if not is_valid_sqlite_db(uploaded_file_path):
        raise ValueError("فایل ارسالی یک دیتابیس sqlite معتبر نیست.")

    backup_dir = os.path.join(os.path.dirname(os.path.abspath(db_path)), "backups")
    os.makedirs(backup_dir, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    pre_restore_path = os.path.join(backup_dir, f"pre_restore_{timestamp}.db")

    # اتصال persistent باز فعلی را می‌بندیم تا فایل دیتابیس قفل نباشد و
    # جایگزینی فایل با خطا مواجه نشود.
    db.close()

    if os.path.exists(db_path):
        src = sqlite3.connect(db_path)
        try:
            dst = sqlite3.connect(pre_restore_path)
            try:
                src.backup(dst)
            finally:
                dst.close()
        finally:
            src.close()

    # پاک‌کردن فایل‌های کمکی WAL دیتابیس فعلی، وگرنه ممکن است داده‌ی commit‌نشده
    # قدیمی با دیتابیس جدید قاطی شود
    for suffix in ("-wal", "-shm"):
        stale = db_path + suffix
        if os.path.exists(stale):
            os.remove(stale)

    shutil.copyfile(uploaded_file_path, db_path)

    # اتصال بعدی که db._get_conn() صدا زده شود، خودش یک اتصال تازه به فایل
    # جدید باز می‌کند (چون db.close() آن را None کرده).
    return pre_restore_path
