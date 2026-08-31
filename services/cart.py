# -*- coding: utf-8 -*-
"""سبد خرید - عملیات سمت سرور (سبدِ محصولات دیجیتال + فیزیکی).

قواعد:
  - محصول دیجیتال: واریانت ندارد (variant_id=None)، تعداد همیشه 1.
  - محصول فیزیکی: واریانت الزامی است، تعداد می‌تواند >1 باشد (تا موجودی).
  - upsert بر اساس (user_id, product_id, variant) در دیتابیس انجام می‌شود.
"""

from services import catalog
from services.errors import CartError, CatalogError


def add_to_cart(db, tg_id: int, product_id: int, variant_id=None,
                quantity: int = 1, add: bool = False) -> int:
    """یک قلم به سبد اضافه/به‌روز می‌کند و تعداد اقلام سبد را برمی‌گرداند.
    add=True یعنی جمع با مقدار قبلی (دکمه‌ی «یکی دیگر»)."""
    product = db.get_product(product_id)
    if not product or not product["is_active"]:
        raise CatalogError("محصول یافت نشد یا غیرفعال است.", code="product_unavailable")

    if catalog.product_type(db, product_id) == "physical":
        if not variant_id:
            v = catalog.pick_variant(db, product_id)
            if not v:
                raise CatalogError("این محصول واریانت فعالی ندارد.", code="no_variant")
            variant_id = v["id"]
        else:
            v = db.get_variant(variant_id)
            if not v or v["is_active"] != 1 or v["product_id"] != product_id:
                raise CatalogError("واریانت معتبر نیست.", code="no_variant")
        if quantity < 1:
            raise CartError("تعداد باید حداقل 1 باشد.", code="invalid_quantity")
    else:
        # دیجیتال: تک‌عددی؛ واریانت صرفاً نادیده گرفته می‌شود
        if not catalog.digital_available(db, product_id):
            raise CatalogError("برای این محصول هنوز فایل الگو ثبت نشده است.", code="no_files")
        variant_id = None
        quantity = 1

    if add and variant_id:
        current = _current_qty(db, tg_id, product_id, variant_id)
        quantity += current

    db.set_cart_item(tg_id, product_id, variant_id, quantity)
    return db.count_cart_items(tg_id)


def _current_qty(db, tg_id, product_id, variant_id) -> int:
    for item in db.get_cart_items(tg_id):
        if item["product_id"] == product_id and item["variant_id"] == variant_id:
            return item["quantity"]
    return 0


def update_quantity(db, tg_id: int, item_id: int, quantity: int) -> bool:
    """تعداد یک قلم را تغییر می‌دهد (دیجیتال همیشه 1)."""
    items = db.get_cart_items(tg_id)
    target = next((i for i in items if i["id"] == item_id), None)
    if not target:
        raise CartError("قلم سبد پیدا نشد.", code="item_not_found")
    if target["product_type"] == "digital":
        quantity = 1
    if quantity < 1:
        raise CartError("تعداد باید حداقل 1 باشد.", code="invalid_quantity")
    return db.change_cart_quantity(tg_id, item_id, quantity)


def remove_from_cart(db, tg_id: int, item_id: int) -> bool:
    return db.remove_cart_item(tg_id, item_id)


def clear_cart(db, tg_id: int):
    db.clear_cart(tg_id)


def cart_summary(db, tg_id: int) -> dict:
    """خلاصه‌ی سبد: اقلام، جمع اقلام، تعداد کل، flag فیزیکی بودن و تناسبِ موجودی."""
    items = db.get_cart_items(tg_id)
    subtotal = 0
    total_qty = 0
    physical = False
    for i in items:
        unit_price = i["variant_price"] if i["variant_price"] is not None else i["product_price"]
        total_qty += i["quantity"]
        if i["product_type"] == "physical":
            physical = True
        subtotal += unit_price * i["quantity"]
    return {
        "items": items,
        "subtotal": int(subtotal),
        "total_qty": total_qty,
        "count": len(items),
        "has_physical": physical,
        "wallet_credit": db.get_wallet_credit(tg_id),
    }


def cart_total_for(db, tg_id: int) -> int:
    return cart_summary(db, tg_id)["subtotal"]