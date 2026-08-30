# -*- coding: utf-8 -*-
"""سفارش‌ها - هماهنگیِ پس از تصمیمِ مالی (تأیید/رد) برای هر دو رابط.

این ماژول فقط منطقِ داده‌محور را پوشش می‌دهد؛ تحویلِ فایل‌ها / ارسالِ پیامِ
تلگرامی / پاسخِ HTTP (I/O) همیشه در رابطِ فراخواننده می‌ماند.

قاعده‌ی استانداردشده: مبلغِ «پرداخت‌شده» برای پورسانت زیرمجموعه‌گیری و امتیازِ
باشگاه مشتریان = final_price (چیزی که واقعاً پرداخت شده) منهای هزینه‌ی ارسال
(ارسال یک هزینه‌ی عبوری است، بدون پورسانت/امتیاز). برای سفارش‌های تمام‌دیجیتالِ
قدیمی هزینه‌ی ارسال صفر است و رفتار عیناً مثل قبل می‌شود."""

from services import settings as store_settings
import loyalty as loyalty_module


def order_paid_amount(order) -> int:
    """مبلغ کالایِ پرداخت‌شده برای اهداف پورسانت/امتیاز (بدون ارسال)."""
    if not order:
        return 0
    final_price = 0
    try:
        final_price = int(order["final_price"] or 0)
    except (ValueError, TypeError):
        final_price = 0
    shipping = 0
    try:
        shipping = int(order["shipping_cost"] or 0)
    except (ValueError, TypeError):
        shipping = 0
    return max(final_price - shipping, 0)


def decide_order(db, order_id: int, approve: bool, file_ids=None,
                 actor: str = "") -> tuple:
    """تصمیمِ اتمیک روی سفارش (تأیید یا رد). خروجی: (success, reason).
    reason در صورت ناکامی، کدِ خرابی است ('already_decided' = سفارش قبلاً
    بررسی شده و این فراخوانی هیچ اثری نداشت)."""
    if approve:
        ok = db.approve_order(order_id, file_ids or [])
    else:
        ok = db.reject_order(order_id)
    if not ok:
        return False, "already_decided"
    from_status = "pending"
    to_status = "approved" if approve else "rejected"
    try:
        order = db.get_order(order_id)
        if order and "physical_fulfillment_status" in order.keys():
            from_status = order["physical_fulfillment_status"] or "processing"
        db.add_fulfillment_event(
            order_id, from_status=from_status, to_status=to_status,
            actor_type="admin", actor_id=str(actor) or "",
            note=("تأیید سفارش" if approve else "رد سفارش"),
        )
    except Exception:
        # ثبت رویداد فقط جنبه‌ی گزارش دارد؛ ناکامیِ آن تصمیمِ مالی را برنمی‌گرداند
        pass
    return True, None


def award_after_approve(db, order_id: int) -> dict:
    """پس از تأیید واقعیِ سفارش: امتیاز باشگاه مشتریان + پورسانت زیرمجموعه.
    هردو idempotent هستند (اعطای دوباره برای همان سفارش/زیرمجموعه ممکن نیست).
    فراخوانی از پنل وب و بات و Mini App یکسان است."""
    result = {"loyalty_points": 0, "referral": None}
    order = db.get_order(order_id)
    if not order or order["status"] != "approved":
        return result
    result["loyalty_points"] = loyalty_module.award_purchase(db, order_id)
    paid = order_paid_amount(order)
    if paid > 0:
        result["referral"] = db.reward_referrer_if_first_purchase(
            order["user_id"], paid)
    return result


def award_invite_bonus(db, referred_user_tg_id: int, referrer_tg_id: int) -> dict:
    return db.apply_referral_invite_rewards(referred_user_tg_id, referrer_tg_id)


def refund_loyalty_for_rejected(db, order_id: int) -> int:
    """برگرداندن امتیازِ (در صورت وجودِ) سفارشِ ردشده. idempotent."""
    return loyalty_module.reverse_purchase(db, order_id)


def set_fulfillment_status(db, order_id: int, new_status: str, actor: str = "",
                           note: str = "") -> tuple:
    """انتقال وضعیت ارسال فیزیکی با ثبت رویداد و آزادسازی/کاهش موجودی.
    انتقال‌های مجاز: processing -> packed -> shipped -> delivered ؛ و هر به
    cancelled (با آزادسازی رزرو). خروجی: (success, reason)."""
    valid = ("processing", "packed", "shipped", "delivered")
    if new_status not in valid + ("cancelled",):
        return False, "invalid_status"
    order = db.get_order(order_id)
    if not order:
        return False, "not_found"
    if order["order_type"] == "digital" and new_status in ("packed", "shipped", "delivered"):
        return False, "not_physical"
    current = (order["physical_fulfillment_status"] or "processing")
    if current == new_status:
        return True, None

    if new_status in ("packed", "shipped", "delivered"):
        # گذار فقط «یک قدم» مجاز است: processing->packed->shipped->delivered
        order_index = valid.index(current) if current in valid else 0
        if valid.index(new_status) != order_index + 1:
            return False, "invalid_transition"
        ok = db.set_physical_fulfillment_status(order_id, new_status)
        if not ok:
            return False, "order_state"
    elif new_status == "cancelled":
        ok = db.cancel_physical_fulfillment(order_id)
        if not ok:
            return False, "order_state"
    else:
        return False, "invalid_status"

    db.add_fulfillment_event(
        order_id, from_status=current, to_status=new_status,
        actor_type="admin", actor_id=str(actor) or "", note=note or "",
    )
    return True, None


def set_tracking(db, order_id: int, tracking_number: str, actor: str = "") -> bool:
    ok = db.set_order_tracking(order_id, tracking_number)
    if ok:
        db.add_fulfillment_event(
            order_id, from_status="", to_status="tracking",
            actor_type="admin", actor_id=str(actor) or "",
            note=f"ثبت شماره‌ی پیگیری: {tracking_number}",
        )
    return ok