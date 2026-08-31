# -*- coding: utf-8 -*-
"""کاتالوگ - قواعد اشتراکی محصول/واریانت/موجودی برای همه‌ی رابط‌ها.

نوع محصول (products.type):
  digital   -> فروش نامحدود، نیاز به حداقل یک فایل الگو، واریانت ندارد، تعداد=1
  physical  -> فروش مبتنی بر موجودی، نیاز به واریانت فعال، تعداد تا موجودی
"""


def product_type(db, product_id: int) -> str:
    p = db.get_product(product_id)
    if not p:
        return "digital"
    return (p["type"] if "type" in p.keys() else "digital") or "digital"


def is_physical(db, product_id: int) -> bool:
    return product_type(db, product_id) == "physical"


def digital_available(db, product_id: int) -> bool:
    """محصول دیجیتال وقتی قابل فروش است که حداقل یک فایل الگو داشته باشد."""
    return db.has_product_files(product_id)


def variant_available(db, variant_id: int, quantity: int = 1) -> bool:
    """واریانت فعال و موجودی کافی؟ (فقط برای محصولات فیزیکی معنا دارد)"""
    v = db.get_variant(variant_id)
    if not v or not v["is_active"]:
        return False
    available = db.get_inventory(variant_id)
    on_hand = available["on_hand"] if available else 0
    reserved = available["reserved"] if available else 0
    return (on_hand - reserved) >= quantity


def effective_price(db, product, variant=None) -> int:
    """قیمت فروش: قیمت واریانت اگر تعریف شده باشد، وگرنه قیمت محصول."""
    if variant is not None and variant.get("price") is not None:
        return int(variant["price"])
    return int(product["price"])


def product_available(db, product, quantity: int = 1) -> bool:
    """آیا محصول به این تعداد هم‌اکنون قابل فروش است؟ (دیجیتال: فایل دارد؛
    فیزیکی: حداقل یک واریانت فعال با موجودی کافی)"""
    if not product or not product.get("is_active"):
        return False
    if product_type(db, product["id"]) == "physical":
        variants = db.list_variants(product["id"], active_only=True)
        return any(variant_available(db, v["id"], quantity) for v in variants)
    return db.has_product_files(product["id"])


def pick_variant(db, product_id: int):
    """یک واریانت فعال را (به‌ترتیب sort_order,id) برمی‌گرداند یا None."""
    variants = db.list_variants(product_id, active_only=True)
    return variants[0] if variants else None