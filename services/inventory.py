# -*- coding: utf-8 -*-
"""موجودی - عملیات سطحِ سرویس برای واریانت‌های فیزیکی (مشترک بات/وب).

مقدارِ «موجود برای فروش» همیشه (on_hand - reserved) است. رزرو فقط داخلِ
تسویه‌ی سفارشِ اتمیک انجام می‌شود؛ این ماژول بررسی/گزارش و تنظیم دستی را
می‌پوشاند.
"""

from services.errors import InventoryError


def stock(db, variant_id: int) -> int:
    row = db.get_inventory(variant_id)
    if not row:
        return 0
    return int(row["on_hand"] or 0) - int(row["reserved"] or 0)


def reserve(db, variant_id: int, qty: int, **kw) -> bool:
    """رزرو با شرط موجودی (مناسبِ فراخوانی‌های مستقیمِ خارج از تسویه)."""
    if qty <= 0:
        return False
    return db.reserve_inventory(variant_id, qty, **kw)


def release(db, variant_id: int, qty: int, **kw):
    db.release_inventory(variant_id, qty, **kw)


def commit(db, variant_id: int, qty: int, **kw) -> bool:
    """هنگامِ ارسال واقعی: کاهش on_hand و آزادسازیِ رزرو هم‌زمان."""
    if qty <= 0:
        return False
    return db.commit_inventory(variant_id, qty, **kw)


def adjust(db, variant_id: int, delta: int, **kw) -> bool:
    """تصحیح دستی موجودی (مثلاً موجودی‌شماری). اگر نتیجه منفی گردد برنمی‌گردد."""
    if delta == 0:
        return True
    return db.adjust_inventory(variant_id, delta, **kw)


def set_quantity(db, variant_id: int, on_hand: int, threshold: int = 0) -> bool:
    if on_hand < 0 or threshold < 0:
        raise InventoryError("مقادیر موجودی نمی‌توانند منفی باشند.", code="negative_qty")
    return db.set_inventory(variant_id, on_hand, threshold)


def ensure(db, variant_id: int) -> bool:
    """اطمینان از وجودِ ردیف موجودی (بدون تغییر مقدار)."""
    row = db.get_inventory(variant_id)
    if row:
        return True
    db.set_inventory(variant_id, 0, 0)
    return True


def require_stock(db, variant_id: int, qty: int, product_name: str = ""):
    if stock(db, variant_id) < qty:
        raise InventoryError(
            f"موجودی «{product_name or 'محصول'}» کافی نیست.",
            code="stock_unavailable")