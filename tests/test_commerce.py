# -*- coding: utf-8 -*-
"""تست‌های لایه‌ی تجارت یکپارچه (سبد/تسویه/موجودی/ارسال/مجوزها/تنظیمات).

همین تست‌ها رفتارِ مشترکِ بات و پنل وب را ثابت می‌کنند؛ همه‌ی مسیرها از لایه‌ی
سرویس (services.checkout / services.orders) عبور می‌کنند."""
import pytest

from database import Database, WEB_ADMIN_PERMISSIONS, ROLE_PERMISSION_PRESETS
from services import checkout as chk, orders as orders_svc, shipping as shipping_svc
from services import settings as store_settings, permissions as perms
from services.errors import (
    EmptyCartError, CheckoutError, DiscountError, InventoryError,
)


@pytest.fixture()
def db():
    d = Database(":memory:")
    d.init_db(owner_id=1)
    return d


def make_user(db, tg_id, referred_by=None):
    db.add_or_update_user(tg_id, "", f"U{tg_id}")
    if referred_by is not None:
        db.set_referred_by(tg_id, referred_by)


def add_digital(db, price=100000):
    cat = db.add_category("c")
    pid = db.add_product(cat, "digi", price, "", "")
    db.add_product_files(pid, ["F1", "F2"])
    return pid


def add_physical(db, price=50000, stock=10):
    cat = db.add_category("c")
    pid = db.add_product(cat, "phys", 0, "", "")
    db.set_product_type(pid, "physical")
    vid = db.add_variant(pid, "M", price=price)
    db.set_inventory(vid, stock, 2)
    return pid, vid


def add_ship(db, cost=15000):
    return db.add_shipping_method("پست", cost, "2-4 روز")


# ------------------------------------------------------------- دیجیتال

def test_legacy_digital_direct_order_flow_unbroken(db):
    """مسیر قدیمیِ سفارش مستقیم (بدون سبد) باید همچنان کار کند و ستون‌های
    جدید (payment_status و order_items) هم‌اهنگ شوند."""
    make_user(db, 1001)
    pid = add_digital(db, 50000)
    oid = db.create_order(1001, pid, base_price=50000, quantity=1)
    assert db.get_order(oid)["status"] == "pending"
    files = db.get_product_files(pid)
    assert db.approve_order(oid, [f["id"] for f in files]) is True
    order = db.get_order(oid)
    assert order["status"] == "approved"
    assert order["payment_status"] == "paid"
    # ردِ دوباره‌ی یک سفارشِ تأییدشده باید بدونِ اثر باشد
    assert db.reject_order(oid) is False


def test_checkout_digital_discount_wallet_and_claim(db):
    make_user(db, 1002)
    db.add_wallet_credit(1002, 20000)
    db.create_discount_code("SAVE10", percent=10, max_uses=0)
    pid = add_digital(db, 80000)
    db.set_cart_item(1002, pid, None, 1)

    res = chk.checkout_cart(db, 1002, discount_code="save10")
    assert res.status == "pending"
    assert res.base_total == 80000
    assert res.discount_amount == 8000
    assert res.wallet_used == 20000
    assert res.final_price == 52000
    assert res.order_type == "digital"
    assert res.items[0].product_type == "digital"

    # سبد خالی شد، کیف پول کسر شد، کد یک بار مصرف شد
    assert db.count_cart_items(1002) == 0
    assert db.get_wallet_credit(1002) == 0
    assert db.get_discount_code("SAVE10")["used_count"] == 1
    assert db.get_order_items(res.order_id)


def test_checkout_fully_covered_by_wallet_auto_approves(db):
    make_user(db, 1003)
    db.add_wallet_credit(1003, 100000)
    pid = add_digital(db, 80000)
    db.set_cart_item(1003, pid, None, 1)
    res = chk.checkout_cart(db, 1003)
    assert res.status == "approved"
    assert res.final_price == 0
    assert db.get_order(res.order_id)["payment_status"] == "paid"


def test_checkout_auto_approve_can_be_disabled(db):
    db.set_setting("checkout_auto_approve_wallet", "0")
    make_user(db, 1004)
    db.add_wallet_credit(1004, 100000)
    pid = add_digital(db, 80000)
    db.set_cart_item(1004, pid, None, 1)
    res = chk.checkout_cart(db, 1004)
    # حتی با پوشش کاملِ کیف پول، چون تنظیم غیرفعال است، سفارش منتظر بررسی می‌ماند
    assert res.status == "pending"
    assert res.final_price == 0


# ------------------------------------------------------------- فیزیکی

def test_checkout_physical_full_reserve_and_snapshot(db):
    make_user(db, 1005)
    pid, vid = add_physical(db, price=50000, stock=10)
    ship_id = add_ship(db, 15000)
    addr = shipping_svc.add_address(db, 1005, "علی", "0912", "تهران", "تهران", "خیابان ۱")

    db.set_cart_item(1005, pid, vid, 2)
    res = chk.checkout_cart(db, 1005, shipping_method_id=ship_id, address_id=addr)

    assert res.order_type == "physical"
    assert res.base_total == 100000
    assert res.shipping_cost == 15000
    assert res.final_price == 115000
    assert res.items[0].variant_id == vid

    inv = db.get_inventory(vid)
    assert inv["on_hand"] == 10 and inv["reserved"] == 2
    order = db.get_order(res.order_id)
    assert order["recipient_name"] == "علی"
    assert order["recipient_address"]  # snapshot ساخته شد
    assert order["shipping_method_id"] == ship_id


def test_checkout_physical_requires_address_and_method(db):
    make_user(db, 1006)
    pid, vid = add_physical(db)
    addr = shipping_svc.add_address(db, 1006, "علی", "0912", "ت", "ت", "خ")
    db.set_cart_item(1006, pid, vid, 1)
    with pytest.raises(CheckoutError) as e1:
        chk.checkout_cart(db, 1006)  # بدون روش ارسال
    assert e1.value.code == "shipping_required"
    ship_id = add_ship(db)
    with pytest.raises(CheckoutError) as e2:
        chk.checkout_cart(db, 1006, shipping_method_id=ship_id)  # بدون آدرس
    assert e2.value.code == "address_required"
    # سبد سالم باقی مانده
    assert db.count_cart_items(1006) == 1


def test_checkout_last_unit_enforced_and_rolls_back(db):
    make_user(db, 1007)
    pid, vid = add_physical(db, price=50000, stock=1)
    ship_id = add_ship(db)
    addr = shipping_svc.add_address(db, 1007, "ب", "0912", "ت", "ت", "خ")
    db.set_cart_item(1007, pid, vid, 2)  # فقط ۱ موجود است
    with pytest.raises(InventoryError):
        chk.checkout_cart(db, 1007, shipping_method_id=ship_id, address_id=addr)
    # برگشتِ تراکنش سبد و موجودی را دست‌نخورده نگه داشته
    assert db.count_cart_items(1007) == 1
    assert db.get_cart_items(1007)[0]["quantity"] == 2
    assert db.get_inventory(vid)["reserved"] == 0


def test_checkout_mixed_order_type(db):
    make_user(db, 1008)
    dpid = add_digital(db, 80000)
    ppid, vid = add_physical(db, price=50000)
    ship_id = add_ship(db, 15000)
    addr = shipping_svc.add_address(db, 1008, "س", "0912", "ت", "ت", "خ")
    db.set_cart_item(1008, dpid, None, 1)
    db.set_cart_item(1008, ppid, vid, 2)
    res = chk.checkout_cart(db, 1008, shipping_method_id=ship_id, address_id=addr)
    assert res.order_type == "mixed"
    assert res.base_total == 80000 + 2 * 50000
    assert res.final_price == res.base_total + 15000


# ------------------------------------------------------------- محک‌ها

def test_checkout_empty_cart(db):
    make_user(db, 1009)
    with pytest.raises(EmptyCartError):
        chk.checkout_cart(db, 1009)


def test_checkout_invalid_code_keeps_cart(db):
    make_user(db, 1010)
    pid = add_digital(db)
    db.set_cart_item(1010, pid, None, 1)
    with pytest.raises(DiscountError):
        chk.checkout_cart(db, 1010, discount_code="NOPE")
    assert db.count_cart_items(1010) == 1
    assert db.get_wallet_credit(1010) == 0


def test_checkout_code_cannot_be_used_twice(db):
    make_user(db, 1011)
    db.create_discount_code("ONESHOT", percent=20, max_uses=1)
    pid = add_digital(db, 50000)
    db.set_cart_item(1011, pid, None, 1)
    res = chk.checkout_cart(db, 1011, discount_code="oneshot")
    assert res.discount_amount == 10000
    # نفر دوم همان کد را نمی‌تواند مصرف کند
    make_user(db, 1012)
    db.set_cart_item(1012, pid, None, 1)
    with pytest.raises(DiscountError):
        chk.checkout_cart(db, 1012, discount_code="oneshot")
    assert db.count_cart_items(1012) == 1


def test_checkout_idempotent_replay_same_order(db):
    make_user(db, 1013)
    db.add_wallet_credit(1013, 50000)
    pid = add_digital(db, 50000)
    db.set_cart_item(1013, pid, None, 1)
    r1 = chk.checkout_cart(db, 1013)
    key = r1.idem_key
    # بازپخش با همان کلید -> همان سفارش؛ بدون هیچ اثر دوباره
    r2 = chk.checkout_cart(db, 1013, idem_key=key)
    assert r2.order_id == r1.order_id
    assert db.get_wallet_credit(1013) == 50000 - r1.wallet_used
    # نسخه‌ی جدید سبد -> کلید جدید -> سفارش جدید (و نه همان قبلی)
    db.set_cart_item(1013, pid, None, 1)
    r3 = chk.checkout_cart(db, 1013)
    assert r3.order_id != r1.order_id


# ------------------------------------------------------------- ارسال فیزیکی

def test_fulfillment_status_flow_and_cancel_releases(db):
    make_user(db, 1014)
    pid, vid = add_physical(db, price=50000, stock=5)
    ship_id = add_ship(db)
    addr = shipping_svc.add_address(db, 1014, "م", "0912", "ت", "ت", "خ")
    db.set_cart_item(1014, pid, vid, 2)
    res = chk.checkout_cart(db, 1014, shipping_method_id=ship_id, address_id=addr)
    oid = res.order_id

    assert db.get_order(oid)["physical_fulfillment_status"] == "processing"
    # انتقال غیرمجاز مستقیم از processing به delivered
    ok, reason = orders_svc.set_fulfillment_status(db, oid, "delivered", actor="adm")
    assert not ok and reason == "invalid_transition"
    ok, reason = orders_svc.set_fulfillment_status(db, oid, "packed", actor="adm")
    assert ok
    ok, reason = orders_svc.set_fulfillment_status(db, oid, "shipped", actor="adm")
    assert ok
    ok, reason = orders_svc.set_fulfillment_status(db, oid, "delivered", actor="adm")
    assert ok
    assert db.get_order(oid)["physical_fulfillment_status"] == "delivered"

    # تحویل‌دادن روی یک سفارش دیجیتال ممکن نیست
    make_user(db, 1015)
    dpid = add_digital(db)
    db.set_cart_item(1015, dpid, None, 1)
    r2 = chk.checkout_cart(db, 1015)
    ok, reason = orders_svc.set_fulfillment_status(db, r2.order_id, "shipped", actor="adm")
    assert not ok and reason == "not_physical"


def test_fulfillment_cancel_releases_reserved(db):
    make_user(db, 1016)
    pid, vid = add_physical(db, price=50000, stock=5)
    ship_id = add_ship(db)
    addr = shipping_svc.add_address(db, 1016, "ن", "0912", "ت", "ت", "خ")
    db.set_cart_item(1016, pid, vid, 2)
    res = chk.checkout_cart(db, 1016, shipping_method_id=ship_id, address_id=addr)
    assert db.get_inventory(vid)["reserved"] == 2
    ok, _ = orders_svc.set_fulfillment_status(db, res.order_id, "cancelled", actor="adm")
    assert ok
    assert db.get_inventory(vid)["reserved"] == 0
    assert db.get_order(res.order_id)["physical_fulfillment_status"] == "cancelled"


def test_set_tracking_recorded(db):
    make_user(db, 1017)
    pid = add_digital(db)
    db.set_cart_item(1017, pid, None, 1)
    res = chk.checkout_cart(db, 1017)
    assert orders_svc.set_tracking(db, res.order_id, "TRACK-1", actor="adm") is True
    assert db.get_order(res.order_id)["tracking_number"] == "TRACK-1"


# ------------------------------------------------------------- جایزه بعد از تأیید

def test_approve_awards_loyalty_excluding_shipping(db):
    make_user(db, 1018)
    pid, vid = add_physical(db, price=50000, stock=5)
    ship_id = add_ship(db, 15000)
    addr = shipping_svc.add_address(db, 1018, "ک", "0912", "ت", "ت", "خ")
    db.set_cart_item(1018, pid, vid, 1)
    res = chk.checkout_cart(db, 1018, shipping_method_id=ship_id, address_id=addr)
    files = []
    ok, reason = orders_svc.decide_order(db, res.order_id, approve=True,
                                         file_ids=files, actor="adm")
    assert ok
    awarded = orders_svc.award_after_approve(db, res.order_id)
    # امتیاز فقط روی ۵۰٬۰۰۰ تومانِ کالا (نه روی ۱۵٬۰۰۰ ارسال)
    assert awarded["loyalty_points"] == 5


def test_order_decide_idempotent_on_already_decided(db):
    make_user(db, 1019)
    pid = add_digital(db)
    db.set_cart_item(1019, pid, None, 1)
    res = chk.checkout_cart(db, 1019)
    ok1, _ = orders_svc.decide_order(db, res.order_id, approve=True, file_ids=[], actor="a")
    ok2, reason = orders_svc.decide_order(db, res.order_id, approve=False, actor="b")
    assert ok1 is True
    assert ok2 is False and reason == "already_decided"
    assert db.get_order(res.order_id)["status"] == "approved"


# ------------------------------------------------------------- مجوزها / نقش‌ها

def test_permission_matrix_tg_web_parity(db):
    """یک ماتریس کانونیکال هم برای پنل وب و هم برای بات استفاده می‌شود."""
    # پشتیبان دقیقاً همان اختیار را در هر دو سطح دارد (تیکت) نه تصمیم مالی
    assert perms.telegram_role_permissions("support") == ["tickets"]
    assert ROLE_PERMISSION_PRESETS["support"] == ["tickets"]
    # نقش mid به موجودی/ارسال هم دسترسی دارد
    assert "inventory" in perms.telegram_role_permissions("mid")
    assert "shipping" in perms.telegram_role_permissions("admin")
    assert set(WEB_ADMIN_PERMISSIONS) >= {"inventory", "shipping"}
    # owner همه‌چیز دارد
    assert perms.telegram_role_permissions("owner") == list(WEB_ADMIN_PERMISSIONS)


def test_tg_gate_matches_canonical_matrix(db):
    owner_tg = 1  # مالکِ init_db
    assert perms.telegram_can_manage_orders(db, owner_tg) is True
    assert perms.telegram_can_manage_discounts(db, owner_tg) is True


# ------------------------------------------------------------- تنظیمات

def test_commerce_settings_registered_on_fresh_db(db):
    assert db.get_setting("btn_cart") == "🛒 سبد خرید"
    assert db.get_setting("cart_enabled") == "1"
    assert db.get_setting("physical_products_enabled") == "1"
    assert db.get_setting("checkout_auto_approve_wallet") == "1"


def test_setting_validation_allowlist_and_types(db):
    # کلید ناشناخته رد می‌شود
    with pytest.raises(Exception):
        store_settings.validate_setting("evil_key", "1")
    # نوع عددی/بولی/JSON اعمال می‌شود
    assert store_settings.validate_setting("loyalty_redeem_points", "100") == "100"
    with pytest.raises(Exception):
        store_settings.validate_setting("cart_enabled", "yes")
    with pytest.raises(Exception):
        store_settings.validate_setting("referral_percent", "abc")
    store_settings.set_setting(db, "cart_enabled", "0", actor="tester")
    assert db.get_setting("cart_enabled") == "0"
    assert store_settings.get_bool(db, "cart_enabled", True) is False
    assert store_settings.get_int(db, "referral_percent", 10) == 10


# ------------------------------------------------------------- تسویه و شارژ

def test_topup_approve_single_credit(db):
    make_user(db, 1020)
    tid = db.create_topup(1020, 50000)
    assert db.approve_topup(tid) is True
    assert db.approve_topup(tid) is False  # دوباره اثری ندارد (P0-1)
    assert db.get_wallet_credit(1020) == 50000
    assert db.reject_topup(tid) is False  # تأییدشده را نمی‌توان رد کرد
    assert db.get_wallet_credit(1020) == 50000


def test_topup_reject_refunds_nothing_and_approve_after_reject_blocked(db):
    make_user(db, 1021)
    tid = db.create_topup(1021, 20000)
    assert db.reject_topup(tid) is True
    assert db.approve_topup(tid) is False
    assert db.get_wallet_credit(1021) == 0


def test_reject_order_refunds_wallet_and_restores_discount(db):
    make_user(db, 1022)
    db.add_wallet_credit(1022, 30000)
    db.create_discount_code("REDEM", fixed_amount=10000, max_uses=0)
    pid = add_digital(db, 50000)
    # سفارش مستقیمِ قدیمی برای تستِ رفتارِ رد
    oid = db.create_order(1022, pid, base_price=50000, wallet_used=20000,
                          discount_code_id=db.get_discount_code("REDEM")["id"],
                          discount_amount=10000)
    assert db.reject_order(oid) is True
    assert db.get_wallet_credit(1022) == 30000 + 20000  # کیف پول برگشت خورد
    assert db.get_discount_code("REDEM")["used_count"] == 0  # مصرف کد برگشت
    assert db.get_order(oid)["payment_status"] == "refunded"


def test_estimate_summary_shape(db):
    make_user(db, 1023)
    pid = add_digital(db, 100000)
    db.set_cart_item(1023, pid, None, 1)
    s = chk.estimate_summary(db, 1023)
    assert s["base_total"] == 100000
    assert s["final_price"] == 100000
    assert {"count", "discount_amount", "wallet_used", "shipping_cost",
            "has_physical"} <= set(s.keys())


def test_reject_physical_order_releases_reservation(db):
    """ردِ سفارشِ فیزیکی (مسیرِ کاربرِ انصراف / تصمیمِ رد در بات و وب) باید رزروِ
    موجودی را در همان تراکنش آزاد کند - درست مثل لغوِ وضعیت فیزیکی."""
    make_user(db, 1024)
    pid, vid = add_physical(db, price=50000, stock=5)
    ship_id = add_ship(db, 15000)
    addr = shipping_svc.add_address(db, 1024, "ر", "0912", "ت", "ت", "خ")
    db.set_cart_item(1024, pid, vid, 1)
    res = chk.checkout_cart(db, 1024, shipping_method_id=ship_id, address_id=addr)
    assert db.get_inventory(vid)["reserved"] == 1
    # رد از طریق لایه‌ی سرویس (همان مسیر بات و پنل وب)
    ok, reason = orders_svc.decide_order(db, res.order_id, False, actor="adm")
    assert ok and reason is None
    assert db.get_order(res.order_id)["status"] == "rejected"
    inv = db.get_inventory(vid)
    assert inv["reserved"] == 0  # رزرو آزاد شد
    assert inv["on_hand"] == 5


def test_cart_update_quantity_uses_item_row_id(db):
    """services.cart.update_quantity باید با کلیدِ ردیف سبد (id) کار کند -
    رگرسیونِ کلید `item_id` که در get_cart_items وجود ندارد."""
    from services import cart as cart_svc
    make_user(db, 1025)
    pid = add_digital(db, 100000)
    cart_svc.add_to_cart(db, 1025, pid, None, 1)
    item = db.get_cart_items(1025)[0]
    # دیجیتال همیشه ۱ است
    assert cart_svc.update_quantity(db, 1025, item["id"], 5) is True
    assert db.get_cart_items(1025)[0]["quantity"] == 1