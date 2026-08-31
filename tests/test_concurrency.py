# -*- coding: utf-8 -*-
"""تست‌های هم‌زمانی — آسیب‌های P0/P1 (شارژ دوباره، سفارش دوباره، تصمیم دوباره)
و درگیری‌های تسویه/موجودی/کد تخفیف با «دو نمونه‌ی Database روی یک فایل»
(شبیه‌سازی بات تلگرام + پنل وب / Mini App که هم‌زمان روی یک دیتابیس کار می‌کنند)."""
import threading

import pytest

from database import Database
from services import checkout as chk, orders as orders_svc, shipping as shipping_svc
from services.errors import DiscountError, InventoryError


@pytest.fixture()
def pair(tmp_path):
    path = str(tmp_path / "commerce.db")
    d1 = Database(path)
    d1.init_db(owner_id=1)
    d2 = Database(path)
    return d1, d2


def _run(worker, d1, d2, barrier=True):
    gate = threading.Barrier(3)
    results = []
    lock = threading.Lock()

    def wrap(db):
        try:
            if barrier:
                gate.wait()
            out = worker(db)
            with lock:
                results.append(out)
        except Exception as e:  # pragma: no cover
            with lock:
                results.append(("ERR", type(e).__name__, str(e)))

    t1 = threading.Thread(target=wrap, args=(d1,))
    t2 = threading.Thread(target=wrap, args=(d2,))
    t1.start(); t2.start()
    if barrier:
        gate.wait()
    t1.join(); t2.join()
    return results


def make_user(db, tg_id):
    db.add_or_update_user(tg_id, "", f"U{tg_id}")


def add_digital(db, price=100000):
    cat = db.add_category("c")
    pid = db.add_product(cat, "d", price, "", "")
    db.add_product_files(pid, ["F1", "F2"])
    return pid


# ------------------------------------------------------------- P0-1: شارژ دوباره

def test_concurrent_topup_approve_single_credit(pair):
    """بات و پنل وب هم‌زمان یک شارژ را تأیید می‌کنند -> فقط یک‌بار به کیف پول اضافه می‌شود."""
    d1, d2 = pair
    make_user(d1, 2001)
    tid = d1.create_topup(2001, 50000)
    results = _run(lambda db: db.approve_topup(tid), d1, d2)
    assert sum(1 for r in results if r is True) == 1
    assert sum(1 for r in results if r is False) == 1
    assert d1.get_wallet_credit(2001) == 50000


def test_concurrent_topup_approve_and_reject_single_effect(pair):
    """یک تأیید و یک ردِ هم‌زمان -> فقط یکی اثر دارد؛ کیف پول یا شارژ شده یا نه؛
    نه هر دو و نه بیش از یک اثر."""
    d1, d2 = pair
    make_user(d1, 2002)
    tid = d1.create_topup(2002, 30000)
    gate = threading.Barrier(3)
    results, lock = [], threading.Lock()

    def w(db, approve):
        try:
            gate.wait()
            r = db.approve_topup(tid) if approve else db.reject_topup(tid)
            with lock:
                results.append(r)
        except Exception as e:  # pragma: no cover
            with lock:
                results.append(("ERR", repr(e)))

    t1 = threading.Thread(target=w, args=(d1, True))
    t2 = threading.Thread(target=w, args=(d2, False))
    t1.start(); t2.start(); gate.wait(); t1.join(); t2.join()

    # یکی True (اثر کرد) و دیگری False (بدون اثر)
    assert len([r for r in results if r is True]) == 1
    assert len([r for r in results if r is False]) == 1
    topup = d1.get_topup(tid)
    assert topup["status"] in ("approved", "rejected")
    assert d1.get_wallet_credit(2002) == (30000 if topup["status"] == "approved" else 0)


# ------------------------------------------------------------- P1-2: تصمیمِ سفارش هم‌زمان

def test_concurrent_order_approve_vs_reject_single_effect(pair):
    """تأیید و ردِ هم‌زمانِ یک سفارش -> فقط یکی اعمال می‌شود؛ تضمینِ انصاف و
    عدمِ ترکیب (approve بعد از reject یا برعکس)."""
    d1, d2 = pair
    make_user(d1, 2003)
    pid = add_digital(d1, 50000)
    oid = d1.create_order(2003, pid, base_price=50000)

    def wd(db, approved):
        if approved:
            return orders_svc.decide_order(db, oid, approve=True, file_ids=[], actor=str(id(db)))
        return (db.reject_order(oid), None)

    gate = threading.Barrier(3)
    results, lock = [], threading.Lock()

    def w(db, approved):
        try:
            gate.wait()
            r = wd(db, approved)
            with lock:
                results.append(r)
        except Exception as e:  # pragma: no cover
            with lock:
                results.append(("ERR", repr(e)))

    t1 = threading.Thread(target=w, args=(d1, True))
    t2 = threading.Thread(target=w, args=(d2, False))
    t1.start(); t2.start(); gate.wait(); t1.join(); t2.join()

    order = d1.get_order(oid)
    # دقیقاً یکی موفق شد: یا approved یا rejected
    assert order["status"] in ("approved", "rejected")
    assert len([r for r in results if isinstance(r, tuple) and r and r[0] is True]) == 1
    if order["status"] == "approved":
        assert order["payment_status"] == "paid"
    else:
        assert order["payment_status"] == "refunded"


# ------------------------------------------------------------- تسویه‌ی هم‌زمان سبد

def test_concurrent_same_cart_checkout_single_order_and_single_wallet_debit(pair):
    """بات و Mini App هم‌زمان همان سبد را تسویه می‌کنند -> یک سفارش، یک بار کسر
    کیف پول؛ دومین‌فراخوانی همان نتیجه را می‌گیرد (نه سفارشِ دوم، نه کسرِ دوم)."""
    d1, d2 = pair
    make_user(d1, 2004)
    d1.add_wallet_credit(2004, 50000)
    pid = add_digital(d1, 30000)
    d1.set_cart_item(2004, pid, None, 1)
    key = chk._default_idem_key(d1, 2004)

    def wd(db):
        r = chk.checkout_cart(db, 2004, idem_key=key)
        return (r.order_id, r.wallet_used)

    results = _run(wd, d1, d2)
    ids = [r[0] for r in results]
    assert len(set(ids)) == 1       # هر دو همان یک سفارش را گرفتند
    assert d1.count_cart_items(2004) == 0
    # کیف پول فقط یک‌بار کسر شد (نه دوبار)
    assert d1.get_wallet_credit(2004) == 20000
    assert len(d1.get_order_items(ids[0])) == 1


# ------------------------------------------------------------- کد تخفیف تک‌مصرفی

def test_concurrent_discount_single_use(pair):
    """دو کاربر با یک کدِ تک‌مصرفی هم‌زمان تسویه می‌کنند -> فقط یکی کد را مصرف
    می‌کند؛ دیگری خطای ظرفیت می‌گیرد (و سبدش دست‌نخورده می‌ماند)."""
    d1, d2 = pair
    make_user(d1, 2005)
    make_user(d1, 2006)
    d1.create_discount_code("ONCE", percent=20, max_uses=1)
    pid = add_digital(d1, 50000)
    d1.set_cart_item(2005, pid, None, 1)
    d1.set_cart_item(2006, pid, None, 1)

    def wd(db, uid):
        r = chk.checkout_cart(db, uid, discount_code="once")
        return (uid, r.order_id)

    gate = threading.Barrier(3)
    results, lock = [], threading.Lock()

    def w(db, uid):
        try:
            gate.wait()
            r = wd(db, uid)
            with lock:
                results.append(r)
        except DiscountError as e:
            with lock:
                results.append(("DENY", uid, e.code))
        except Exception as e:  # pragma: no cover
            with lock:
                results.append(("ERR", uid, repr(e)))

    t1 = threading.Thread(target=w, args=(d1, 2005))
    t2 = threading.Thread(target=w, args=(d2, 2006))
    t1.start(); t2.start(); gate.wait(); t1.join(); t2.join()

    ok = [r for r in results if isinstance(r, tuple) and r[0] != "DENY" and r[0] != "ERR"]
    denied = [r for r in results if isinstance(r, tuple) and r[0] == "DENY"]
    assert len(ok) == 1 and len(denied) == 1
    # کدِ دوم یا از پیشِ تراکنش نامعتبر دیده می‌شود یا داخلِ تراکنش ظرفیت نمی‌گیرد
    assert denied[0][2] in ("discount_invalid", "discount_exhausted")
    assert d1.get_discount_code("once")["used_count"] == 1


# ------------------------------------------------------------- آخرین موجودی

def test_concurrent_last_unit_inventory(pair):
    """دو کاربر آخرین واحدِ یک واریانت را هم‌زمان می‌خواهند -> فقط یکی می‌گیرد،
    دیگری با خطای موجودی رد می‌شود (روی‌فروشی غیرممکن است)."""
    d1, d2 = pair
    make_user(d1, 2007)
    make_user(d1, 2008)
    cat = d1.add_category("c")
    ppid = d1.add_product(cat, "phys", 0, "", "")
    d1.set_product_type(ppid, "physical")
    vid = d1.add_variant(ppid, "M", price=50000)
    d1.set_inventory(vid, 1, 0)
    ship = d1.add_shipping_method("پست", 15000, "")
    a1 = shipping_svc.add_address(d1, 2007, "a", "0912", "ت", "ت", "خ")
    a2 = shipping_svc.add_address(d1, 2008, "b", "0912", "ت", "ت", "خ")
    d1.set_cart_item(2007, ppid, vid, 1)
    d1.set_cart_item(2008, ppid, vid, 1)

    def wd(db, uid, addr):
        r = chk.checkout_cart(db, uid, shipping_method_id=ship, address_id=addr)
        return (uid, r.order_id)

    gate = threading.Barrier(3)
    results, lock = [], threading.Lock()

    def w(db, uid, addr):
        try:
            gate.wait()
            r = wd(db, uid, addr)
            with lock:
                results.append(r)
        except InventoryError:
            with lock:
                results.append(("DENY", uid))
        except Exception as e:  # pragma: no cover
            with lock:
                results.append(("ERR", uid, repr(e)))

    t1 = threading.Thread(target=w, args=(d1, 2007, a1))
    t2 = threading.Thread(target=w, args=(d2, 2008, a2))
    t1.start(); t2.start(); gate.wait(); t1.join(); t2.join()

    ok = [r for r in results if isinstance(r, tuple) and r[0] != "DENY" and r[0] != "ERR"]
    denied = [r for r in results if r[0] == "DENY"]
    assert len(ok) == 1 and len(denied) == 1
    assert d1.get_inventory(vid)["reserved"] == 1


# ------------------------------------------------------------- جایزه‌ی تک‌بارِ پس از تأیید

def test_concurrent_post_approve_awards_once(pair):
    """امتیاز باشگاه + پورسانت زیرمجموعه بعد از تأیید، هم‌زمان از بات و وب ->
    فقط یک‌بار اعطا می‌شود (idempotent)."""
    d1, d2 = pair
    make_user(d1, 2009)
    d1.set_referred_by(2009, 1)   # کاربرِ معرفی‌شده
    pid = add_digital(d1, 100000)
    d1.set_cart_item(2009, pid, None, 1)
    res = chk.checkout_cart(d1, 2009)
    # سفارش باید واقعاً تأیید شده باشد تا جایزه‌دهی فعال شود
    ok, _ = orders_svc.decide_order(d1, res.order_id, approve=True, file_ids=[], actor="adm")
    assert ok

    def wd(db):
        return orders_svc.award_after_approve(db, res.order_id)

    results = _run(wd, d1, d2)
    state = d1.get_loyalty_state(2009)
    assert state["current_points"] == 10  # فقط یک‌بار (۱۰۰٬۰۰۰ -> ۱۰ امتیاز)


# ------------------------------------------------------------- تصمیمِ مالیِ تکراری پنل/بات

def test_concurrent_decide_same_order_no_double_worker(pair):
    """دو ادمینِ هم‌زمان همان سفارش را تأیید می‌کنند -> یک رویداد و بدونِ اثرِ دوم؛
    امتیاز/پورسانت هم فقط یک‌بار (idempotent)."""
    d1, d2 = pair
    make_user(d1, 2010)
    pid = add_digital(d1, 40000)
    d1.set_cart_item(2010, pid, None, 1)
    res = chk.checkout_cart(d1, 2010)

    def wd(db):
        return orders_svc.decide_order(db, res.order_id, approve=True,
                                       file_ids=[], actor="a1")

    results = _run(wd, d1, d2)
    assert len([r for r in results if r[0] is True]) == 1
    assert d1.get_order(res.order_id)["status"] == "approved"
    aw = orders_svc.award_after_approve(d1, res.order_id)
    assert aw["loyalty_points"] == 4  # هنوز فقط یک جایزهٔ معتبر
    state = d1.get_loyalty_state(2010)
    assert state["current_points"] == 4