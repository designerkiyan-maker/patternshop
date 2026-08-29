# -*- coding: utf-8 -*-
"""تست‌های باشگاه مشتریان — ماتریس اسپک: خرید/برگشت/ثبت‌نام/معرفی/تبدیل/سطح/دفتر کل/امنیت.

همه‌ی تست‌ها روی SQLite درون‌حافظه‌ای (یا فایل موقت برای تست هم‌زمانی) اجرا
می‌شوند و به تلگرام یا هندلرها وابسته نیستند — فقط لایه‌ی سرویس و داده."""
import sqlite3
import threading

import pytest

from database import Database
import loyalty
from loyalty import LoyaltyError


@pytest.fixture()
def db():
    d = Database(":memory:")
    d.init_db(owner_id=1)
    return d


def make_user(db, tg_id):
    db.add_or_update_user(tg_id, "", f"U{tg_id}")


def pts(db, tg_id):
    """موجودی فعلی؛ کاربر بدون ردیف state یعنی ۰."""
    s = db.get_loyalty_state(tg_id)
    return s["current_points"] if s else 0


def make_approved_order(db, user_tg_id, price, discount=0, wallet_used=0):
    """سفارش تاییدشده‌ی واقعی: دسته + محصول + فایل + سفارش + تایید."""
    make_user(db, user_tg_id)
    cat = db.add_category("تست")
    pid = db.add_product(cat, "الگوی تست", price, "", "")
    db.add_product_files(pid, [f"FILE_{pid}"])
    oid = db.create_order(user_tg_id, pid, base_price=price, wallet_used=wallet_used,
                          discount_code_id=None, discount_amount=discount, quantity=1)
    files = db.get_product_files(pid)
    db.approve_order(oid, [f["id"] for f in files])
    return oid


# ---------------------------------------------------------------- خرید

def test_purchase_awards_points_by_rate(db):
    """نرخ پیش‌فرض: هر ۱۰٬۰۰۰ تومان = ۱ امتیاز (روی مبلغ نهایی)."""
    oid = make_approved_order(db, 1001, 50000)  # ۵۰٬۰۰۰ → ۵ امتیاز
    awarded = loyalty.award_purchase(db, oid)
    assert awarded == 5
    s = db.get_loyalty_state(1001)
    assert s["current_points"] == 5
    assert s["lifetime_earned"] == 5


def test_purchase_uses_final_price_after_discount(db):
    make_user(db, 1002)
    cat = db.add_category("تست")
    pid = db.add_product(cat, "الگو", 60000, "", "")
    db.add_product_files(pid, ["F"])
    oid = db.create_order(1002, pid, base_price=60000, wallet_used=0,
                          discount_code_id=None, discount_amount=10000, quantity=1)
    files = db.get_product_files(pid)
    db.approve_order(oid, [f["id"] for f in files])
    # 60,000 - 10,000 = 50,000 → ۵ امتیاز
    assert loyalty.award_purchase(db, oid) == 5


def test_duplicate_award_is_idempotent(db):
    oid = make_approved_order(db, 1003, 50000)
    assert loyalty.award_purchase(db, oid) == 5
    assert loyalty.award_purchase(db, oid) == 0  # دوباره‌کاری هیچ امتیازی نمی‌دهد
    assert db.get_loyalty_state(1003)["current_points"] == 5


def test_pending_or_rejected_order_awards_nothing(db):
    make_user(db, 1004)
    cat = db.add_category("تست")
    pid = db.add_product(cat, "الگو", 50000, "", "")
    db.add_product_files(pid, ["F"])
    oid = db.create_order(1004, pid, base_price=50000, wallet_used=0,
                          discount_code_id=None, discount_amount=0, quantity=1)
    assert loyalty.award_purchase(db, oid) == 0  # هنوز pending است
    db.reject_order(oid)
    assert loyalty.award_purchase(db, oid) == 0


def test_max_per_order_cap(db):
    db.set_setting("loyalty_max_per_order", "3")
    oid = make_approved_order(db, 1005, 100000)  # بدون سقف می‌شد ۱۰
    assert loyalty.award_purchase(db, oid) == 3


def test_disabled_system_awards_nothing(db):
    db.set_setting("loyalty_enabled", "0")
    oid = make_approved_order(db, 1006, 50000)
    assert loyalty.award_purchase(db, oid) == 0


# ---------------------------------------------------------------- برگشت

def test_refund_reverses_points(db):
    oid = make_approved_order(db, 2001, 50000)
    loyalty.award_purchase(db, oid)
    assert db.get_loyalty_state(2001)["current_points"] == 5
    reversed_points = loyalty.reverse_purchase(db, oid)
    assert reversed_points == 5
    assert db.get_loyalty_state(2001)["current_points"] == 0


def test_duplicate_refund_reverses_once(db):
    oid = make_approved_order(db, 2002, 50000)
    loyalty.award_purchase(db, oid)
    loyalty.reverse_purchase(db, oid)
    assert loyalty.reverse_purchase(db, oid) == 0  # برگشت دوباره ممنوع
    assert db.get_loyalty_state(2002)["current_points"] == 0


def test_refund_without_award_is_safe(db):
    oid = make_approved_order(db, 2003, 50000)
    assert loyalty.reverse_purchase(db, oid) == 0  # امتیازی نبوده؛ بدون خطا
    assert pts(db, 2003) == 0


def test_refund_does_not_reduce_lifetime_earned(db):
    """سطح بر اساس امتیاز عمر است؛ برگشت، سابقه‌ی کسب را پاک نمی‌کند."""
    oid = make_approved_order(db, 2004, 50000)
    loyalty.award_purchase(db, oid)
    loyalty.reverse_purchase(db, oid)
    s = db.get_loyalty_state(2004)
    assert s["lifetime_earned"] == 5
    assert s["current_points"] == 0


# ---------------------------------------------------------------- ثبت‌نام

def test_registration_bonus_awarded_once(db):
    make_user(db, 3001)
    assert loyalty.award_registration(db, 3001) == 50
    assert loyalty.award_registration(db, 3001) == 0  # دوباره‌کاری ممنوع
    assert db.get_loyalty_state(3001)["current_points"] == 50


def test_registration_bonus_disabled(db):
    db.set_setting("loyalty_reg_bonus", "0")
    make_user(db, 3002)
    assert loyalty.award_registration(db, 3002) == 0


# ---------------------------------------------------------------- معرفی

def test_referral_bonus_awarded_once_per_pair(db):
    make_user(db, 4001)  # دعوت‌کننده
    make_user(db, 4002)  # دعوت‌شده
    assert loyalty.award_referral(db, 4001, 4002) == 20
    assert loyalty.award_referral(db, 4001, 4002) == 0  # همان جفت دوباره
    assert db.get_loyalty_state(4001)["current_points"] == 20


def test_referral_self_invitation_ignored(db):
    make_user(db, 4003)
    assert loyalty.award_referral(db, 4003, 4003) == 0


# ---------------------------------------------------------------- تبدیل

def test_valid_redeem_converts_to_wallet(db):
    make_user(db, 5001)
    loyalty.award_registration(db, 5001)  # ۵۰ امتیاز
    # ۵۰ امتیاز کمتر از حداقل ۱۰۰ است → شارژ مستقیم state برای تست
    db.apply_loyalty_mutation(5001, "PURCHASE", 150, idem_key="seed:5001",
                              description="seed")
    res = loyalty.redeem(db, 5001, 100)
    assert res["points"] == 100
    assert res["toman"] == 10000
    assert res["balance_after"] == 100  # 200 - 100
    assert db.get_wallet_credit(5001) == 10000


def test_redeem_insufficient_balance_fails_clean(db):
    make_user(db, 5002)
    db.apply_loyalty_mutation(5002, "PURCHASE", 50, idem_key="seed:5002", description="")
    with pytest.raises(LoyaltyError):
        loyalty.redeem(db, 5002, 100)
    assert db.get_loyalty_state(5002)["current_points"] == 50  # دست‌نخورده
    assert db.get_wallet_credit(5002) == 0


def test_redeem_zero_and_negative_fail(db):
    make_user(db, 5003)
    db.apply_loyalty_mutation(5003, "PURCHASE", 200, idem_key="seed:5003", description="")
    with pytest.raises(LoyaltyError):
        loyalty.redeem(db, 5003, 0)
    with pytest.raises(LoyaltyError):
        loyalty.redeem(db, 5003, -50)
    assert db.get_loyalty_state(5003)["current_points"] == 200


def test_redeem_below_minimum_fails(db):
    make_user(db, 5004)
    db.apply_loyalty_mutation(5004, "PURCHASE", 150, idem_key="seed:5004", description="")
    with pytest.raises(LoyaltyError):
        loyalty.redeem(db, 5004, 50)  # کمتر از حداقل ۱۰۰
    assert db.get_loyalty_state(5004)["current_points"] == 150


def test_redeem_non_multiple_fails(db):
    make_user(db, 5005)
    db.apply_loyalty_mutation(5005, "PURCHASE", 250, idem_key="seed:5005", description="")
    with pytest.raises(LoyaltyError):
        loyalty.redeem(db, 5005, 150)  # مضرب ۱۰۰ نیست
    assert db.get_loyalty_state(5005)["current_points"] == 250


def test_concurrent_redeem_cannot_overdraw(db, tmp_path):
    """دو نمونه‌ی Database روی یک فایل (مثل بات و مینی‌اپ) — تبدیل هم‌زمان
    نباید موجودی منفی بسازد یا یک امتیاز را دو بار خرج کند."""
    path = str(tmp_path / "loy.db")
    d1 = Database(path)
    d1.init_db(owner_id=1)
    d2 = Database(path)
    make_user(d1, 6001)
    d1.apply_loyalty_mutation(6001, "PURCHASE", 100, idem_key="seed:6001", description="")

    results = []
    lock = threading.Lock()

    def worker(instance):
        try:
            r = instance.redeem_points_for_wallet(6001, 100, 10000, f"redeem:test:{id(instance)}")
            with lock:
                results.append(r)
        except Exception as e:  # pragma: no cover
            with lock:
                results.append(("ERR", str(e)))

    t1 = threading.Thread(target=worker, args=(d1,))
    t2 = threading.Thread(target=worker, args=(d2,))
    t1.start(); t2.start(); t1.join(); t2.join()

    ok = [r for r in results if isinstance(r, dict)]
    assert len(ok) == 1  # فقط یکی موفق شده
    final = d1.get_loyalty_state(6001)
    assert final["current_points"] == 0  # منفی نشده
    assert d1.get_wallet_credit(6001) == 10000


# ---------------------------------------------------------------- سطح‌ها

def test_tier_thresholds_and_multiplier(db):
    make_user(db, 7001)
    # ۴۰۰٬۰۰۰ تومان خرید → ۴۰ امتیاز پایه؛ ضریب برنز ×۱ → ۴۰
    oid = make_approved_order(db, 7001, 400000)
    assert loyalty.award_purchase(db, oid) == 40
    assert db.get_loyalty_state(7001)["tier"] == "bronze"

    # +۴٬۶۰۰٬۰۰۰ تومان → ۴۶۰ امتیاز پایه؛ مجموع عمر = ۵۰۰ → عبور دقیق از مرز نقره‌ای
    oid2 = make_approved_order(db, 7001, 4600000)
    loyalty.award_purchase(db, oid2)
    assert db.get_loyalty_state(7001)["tier"] == "silver"

    # ضریب نقره‌ای ۱۱۰: ۱۰۰٬۰۰۰ تومان → ۱۰ × ۱.۱ = ۱۱ امتیاز
    oid3 = make_approved_order(db, 7001, 100000)
    assert loyalty.award_purchase(db, oid3) == 11


def test_tier_exact_boundary(db):
    tiers = loyalty.load_tiers(db)
    assert loyalty.tier_for(0, tiers)["id"] == "bronze"
    assert loyalty.tier_for(499, tiers)["id"] == "bronze"
    assert loyalty.tier_for(500, tiers)["id"] == "silver"  # مرز دقیق
    assert loyalty.tier_for(999999, tiers)["id"] == "platinum"


def test_next_tier_and_points_to_next(db):
    s = loyalty.get_summary(db) if False else None  # noqa (ساختار پایین)
    make_user(db, 7002)
    summary = loyalty.get_summary(db, 7002)
    assert summary["tier"]["id"] == "bronze"
    assert summary["next_tier"]["id"] == "silver"
    assert summary["points_to_next"] == 500


def test_custom_tiers_from_settings(db):
    db.set_setting("loyalty_tiers", '[{"id":"a","name":"A","min":0,"mult":100},{"id":"b","name":"B","min":10,"mult":200}]')
    make_user(db, 7003)
    # اول کاربر را به سطح B می‌رسانیم (۱۵ امتیاز عمر) — ضریبِ «سطح فعلی» اعمال می‌شود
    db.apply_loyalty_mutation(7003, "PURCHASE", 15, idem_key="seed:7003", description="")
    oid = make_approved_order(db, 7003, 100000)  # ۱۰ امتیاز پایه × ۲ (سطح B) = ۲۰
    assert loyalty.award_purchase(db, oid) == 20
    assert db.get_loyalty_state(7003)["tier"] == "b"  # ست از مسیر سرویس


# ---------------------------------------------------------------- دفتر کل

def test_every_mutation_creates_ledger_with_balance_after(db):
    make_user(db, 8001)
    oid = make_approved_order(db, 8001, 50000)
    loyalty.award_purchase(db, oid)
    loyalty.reverse_purchase(db, oid)
    rows, total = db.get_loyalty_history(8001, 10, 0)
    assert total == 2
    by_type = {r["tx_type"]: r for r in rows}
    assert by_type["PURCHASE"]["amount"] == 5
    assert by_type["PURCHASE"]["balance_after"] == 5
    assert by_type["PURCHASE_REFUND"]["amount"] == -5
    assert by_type["PURCHASE_REFUND"]["balance_after"] == 0


def test_history_pagination(db):
    make_user(db, 8002)
    for i in range(7):
        db.apply_loyalty_mutation(8002, "PURCHASE", 1, idem_key=f"seed:8002:{i}", description=f"t{i}")
    rows, total = db.get_loyalty_history(8002, 5, 0)
    assert total == 7 and len(rows) == 5
    rows2, _ = db.get_loyalty_history(8002, 5, 5)
    assert len(rows2) == 2
    # جدیدترین اول
    assert rows[0]["description"] == "t6"


def test_ledger_records_are_immutable(db):
    """رکوردهای قبلی بعد از عملیات بعدی تغییر نمی‌کنند (فقط رکورد جدید اضافه می‌شود)."""
    make_user(db, 8003)
    oid = make_approved_order(db, 8003, 50000)
    loyalty.award_purchase(db, oid)
    before = db.find_loyalty_tx("purchase:%d" % oid)
    loyalty.redeem = loyalty.redeem  # no-op
    db.apply_loyalty_mutation(8003, "PURCHASE", 10, idem_key="seed:8003", description="")
    after = db.find_loyalty_tx("purchase:%d" % oid)
    assert dict(before) == dict(after)
    # و هیچ API حذف/ویرایش رکورد دفتر کل وجود ندارد
    assert not hasattr(db, "delete_loyalty_tx")
    assert not hasattr(db, "update_loyalty_tx")


def test_duplicate_idem_key_rejected_at_db_level(db):
    make_user(db, 8004)
    r1 = db.apply_loyalty_mutation(8004, "PURCHASE", 5, idem_key="dup:1", description="")
    r2 = db.apply_loyalty_mutation(8004, "PURCHASE", 5, idem_key="dup:1", description="")
    assert r1 is not None and r2 is None
    assert db.get_loyalty_state(8004)["current_points"] == 5


def test_negative_balance_impossible_at_db_level(db):
    make_user(db, 8005)
    with pytest.raises(ValueError):
        db.apply_loyalty_mutation(8005, "PURCHASE", -10, idem_key="neg:1", description="")
    assert pts(db, 8005) == 0


# ---------------------------------------------------------------- امنیت

def test_admin_adjust_requires_reason(db):
    make_user(db, 9001)
    with pytest.raises(LoyaltyError):
        loyalty.admin_adjust(db, 999, 9001, 10, "  ")


def test_admin_adjust_zero_amount_rejected(db):
    make_user(db, 9002)
    with pytest.raises(LoyaltyError):
        loyalty.admin_adjust(db, 999, 9002, 0, "test")


def test_admin_adjust_negative_beyond_balance_rejected(db):
    make_user(db, 9003)
    with pytest.raises(LoyaltyError):
        loyalty.admin_adjust(db, 999, 9003, -5, "سرقت")


def test_admin_adjust_records_admin_and_reason(db):
    make_user(db, 9004)
    loyalty.admin_adjust(db, 777, 9004, 25, "جبران مشکل ارسال")
    rows, _ = db.get_loyalty_history(9004, 5, 0)
    tx = rows[0]
    assert tx["tx_type"] == "ADMIN_ADJUSTMENT"
    assert tx["amount"] == 25
    assert tx["reference_type"] == "admin"
    assert tx["reference_id"] == "777"
    assert "جبران مشکل ارسال" in tx["description"]


def test_redeem_disabled_system_fails(db):
    db.set_setting("loyalty_enabled", "0")
    make_user(db, 9005)
    db.apply_loyalty_mutation(9005, "PURCHASE", 200, idem_key="seed:9005", description="")
    with pytest.raises(LoyaltyError):
        loyalty.redeem(db, 9005, 100)


def test_summary_shape(db):
    make_user(db, 9006)
    s = loyalty.get_summary(db, 9006)
    assert {"current", "lifetime_earned", "lifetime_spent", "tier", "next_tier",
            "points_to_next", "redeem_enabled", "min_redeem"} <= set(s.keys())
    assert s["redeem_enabled"] is True
    assert s["point_value_toman"] == 100  # هر امتیاز = ۱۰۰ تومان
