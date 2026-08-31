# -*- coding: utf-8 -*-
"""ارسال - مدیریت روش‌های ارسال و آدرس‌ها (مشترک بات و وب).

هزینه‌ی ارسال یک هزینه‌ی «عبوری» است و در محاسبات تخفیف/کیف پول/پورسانت/
امتیاز لحاظ نمی‌شود (فقط در مبلغ نهاییِ پرداختی می‌آید).
"""

from services.errors import CheckoutError


def list_methods(db, active_only: bool = False):
    return db.list_shipping_methods(active_only=active_only)


def get_method(db, method_id: int):
    return db.get_shipping_method(method_id)


def add_method(db, name: str, cost: int, delivery_note: str = "", position: int = 0) -> int:
    if cost < 0:
        raise CheckoutError("هزینه‌ی ارسال نمی‌تواند منفی باشد.", code="invalid_shipping_cost")
    return db.add_shipping_method(name, cost, delivery_note, position)


def edit_method(db, method_id: int, **fields) -> bool:
    if fields.get("cost") is not None and int(fields["cost"]) < 0:
        raise CheckoutError("هزینه‌ی ارسال نمی‌تواند منفی باشد.", code="invalid_shipping_cost")
    db.edit_shipping_method(method_id, **fields)
    return True


def toggle_method(db, method_id: int):
    db.toggle_shipping_method(method_id)


def delete_method(db, method_id: int):
    db.delete_shipping_method(method_id)


def resolve_cost(db, method_id: int) -> int:
    method = db.get_shipping_method(method_id)
    if not method or not method["is_active"]:
        raise CheckoutError("روش ارسال انتخابی معتبر نیست.", code="shipping_invalid")
    return int(method["cost"] or 0)


# ---------------------------------------------------------------------------
# آدرس‌های مشتری
# ---------------------------------------------------------------------------

def add_address(db, tg_id: int, recipient_name: str, mobile: str, province: str,
                city: str, address: str, postal_code: str = "") -> int:
    if not recipient_name.strip() or not mobile.strip() or not city.strip() or not address.strip():
        raise CheckoutError("نام، موبایل، شهر و آدرس الزامی است.", code="address_incomplete")
    return db.add_address(tg_id, recipient_name.strip(), mobile.strip(),
                          province.strip(), city.strip(), address.strip(), postal_code.strip())


def list_addresses(db, tg_id: int):
    return db.list_addresses(tg_id)


def get_address(db, tg_id: int, address_id: int):
    return db.get_address(address_id)


def delete_address(db, tg_id: int, address_id: int) -> bool:
    return db.delete_address(address_id, tg_id)


def set_default(db, tg_id: int, address_id: int) -> bool:
    return db.set_default_address(address_id, tg_id)