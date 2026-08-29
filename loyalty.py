# -*- coding: utf-8 -*-
"""
سرویس باشگاه مشتریان (Loyalty) — تمام منطق کسب‌وکار امتیاز اینجاست.

هندلرهای تلگرام و سرویس‌های وب فقط توابع این ماژول را صدا می‌زنند و هیچ منطق
امتیازی داخل هندلرها نیست. لایه‌ی داده (جداول loyalty_state / loyalty_ledger
و عملیات اتمیک) در database.py است و این ماژول قواعد را روی آن پیاده می‌کند:

  هندلر / Endpoint
        ↓
  loyalty.py (این فایل — قواعد + سطح‌ها + idempotency)
        ↓
  database.py (عملیات اتمیک روی loyalty_state / loyalty_ledger)
        ↓
  SQLite

اصول کلیدی:
- هر تغییر موجودی = یک رکورد جدید و غیرقابل‌تغییر در دفتر کل (Ledger).
- هر رویداد یک کلید idempotency دارد (مثلاً purchase:{order_id})؛ ایندکس
  یکتای دیتابیس جلوی اعطای دوباره‌ی امتیاز برای همان رویداد را می‌گیرد —
  حتی اگر callback/وب‌هوک تکراری برسد یا هم‌زمان دو درخواست برسد.
- امتیاز فقط پس از تایید واقعی سفارش اعطا می‌شود؛ برگشت سفارش، امتیاز همان
  سفارش را برمی‌گرداند (رکورد جدا، بدون دست‌زدن به رکورد قبلی).
- موجودی منفی در سطح دیتابیس غیرممکن است.
"""

import json
import logging
import uuid
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# انواع تراکنش دفتر کل
TX_PURCHASE = "PURCHASE"
TX_PURCHASE_REFUND = "PURCHASE_REFUND"
TX_REGISTRATION = "REGISTRATION_BONUS"
TX_REFERRAL = "REFERRAL_BONUS"
TX_CAMPAIGN = "CAMPAIGN_BONUS"
TX_TIER_BONUS = "TIER_BONUS"
TX_ADMIN_ADJUSTMENT = "ADMIN_ADJUSTMENT"
TX_POINTS_REDEEM = "POINTS_REDEEM"
TX_POINTS_EXPIRE = "POINTS_EXPIRE"
TX_REVERSAL = "REVERSAL"

TX_LABELS_FA = {
    TX_PURCHASE: "خرید",
    TX_PURCHASE_REFUND: "برگشت امتیاز خرید",
    TX_REGISTRATION: "هدیه‌ی ثبت‌نام",
    TX_REFERRAL: "پاداش معرفی",
    TX_CAMPAIGN: "کمپین",
    TX_TIER_BONUS: "پاداش سطح",
    TX_ADMIN_ADJUSTMENT: "تعدیل ادمین",
    TX_POINTS_REDEEM: "تبدیل به کیف پول",
    TX_POINTS_EXPIRE: "انقضای امتیاز",
    TX_REVERSAL: "اصلاحیه",
}


class LoyaltyError(Exception):
    """خطای عمومی باشگاه مشتریان (پیام فارسی برای نمایش به کاربر)."""


def load_tiers(db) -> list:
    """خواندن و اعتبارسنجی سطوح از تنظیمات. خروجی لیستی مرتب‌شده بر اساس min:
    [{"id","name","min","mult"}] — mult درصدی است (100 یعنی ×۱)."""
    raw = db.get_setting("loyalty_tiers", "") or "[]"
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        logger.error("loyalty_tiers نامعتبر است؛ سطوح خالی در نظر گرفته می‌شود.")
        return []
    tiers = []
    for t in data:
        try:
            tiers.append({
                "id": str(t["id"]),
                "name": str(t["name"]),
                "min": int(t["min"]),
                "mult": int(t["mult"]),
            })
        except (KeyError, TypeError, ValueError):
            logger.warning("ردیف سطح نامعتبر رد شد: %r", t)
    tiers.sort(key=lambda t: t["min"])
    return tiers


def tier_for(lifetime_earned: int, tiers: list) -> dict:
    """سطح جواب بر اساس کل امتیازهای کسب‌شده — تابع خالص و قطعی.
    بالاترین سطحی که آستانه‌اش ≤ امتیاز باشد برگردانده می‌شود."""
    current = None
    for t in tiers:
        if lifetime_earned >= t["min"]:
            current = t
    return current


def next_tier(lifetime_earned: int, tiers: list) -> dict:
    """نزدیک‌ترین سطح بالاتر از امتیاز فعلی؛ اگر بالاترین سطح باشد None."""
    for t in tiers:
        if t["min"] > lifetime_earned:
            return t
    return None


def is_enabled(db) -> bool:
    return db.get_setting("loyalty_enabled", "1") == "1"


def _tier_after(db, lifetime_earned_after: int) -> str:
    t = tier_for(lifetime_earned_after, load_tiers(db))
    return t["id"] if t else ""


def _purchase_points(db, paid_amount: int, lifetime_earned: int) -> int:
    """قاعده‌ی مرکزی امتیاز خرید: مبلغ پرداختی ÷ نرخ × ضریب سطح (با سقف اختیاری)."""
    if paid_amount <= 0:
        return 0
    per_toman = int(db.get_setting("loyalty_points_per_toman", "10000") or 0)
    if per_toman <= 0:
        return 0
    tiers = load_tiers(db)
    tier = tier_for(lifetime_earned, tiers)
    mult = (tier["mult"] if tier else 100)
    points = paid_amount * mult // (per_toman * 100)
    max_per_order = int(db.get_setting("loyalty_max_per_order", "0") or 0)
    if max_per_order > 0:
        points = min(points, max_per_order)
    return max(points, 0)


def get_summary(db, user_tg_id: int) -> dict:
    """خلاصه‌ی باشگاه برای UI: امتیاز فعلی، سطح، امتیاز تا سطح بعد و ارزش تبدیل."""
    state = db.ensure_loyalty_state(user_tg_id)
    current = state["current_points"]
    lifetime = state["lifetime_earned"]
    tiers = load_tiers(db)
    tier = tier_for(lifetime, tiers)
    nxt = next_tier(lifetime, tiers)
    redeem_points = int(db.get_setting("loyalty_redeem_points", "100") or 0)
    redeem_toman = int(db.get_setting("loyalty_redeem_toman", "0") or 0)
    per_value = (redeem_toman // redeem_points) if redeem_points > 0 else 0
    return {
        "current": current,
        "lifetime_earned": lifetime,
        "lifetime_spent": state["lifetime_spent"],
        "tier": tier,
        "next_tier": nxt,
        "points_to_next": (nxt["min"] - lifetime) if nxt else 0,
        "redeem_enabled": redeem_points > 0 and redeem_toman > 0,
        "redeem_points": redeem_points,
        "redeem_toman": redeem_toman,
        "point_value_toman": per_value,
        "min_redeem": int(db.get_setting("loyalty_min_redeem", "0") or 0),
    }


def award_purchase(db, order_id: int) -> int:
    """اعطای امتیاز خرید پس از تایید واقعی سفارش. کاملاً idempotent —
    فراخوانی تکراری برای همان سفارش هیچ امتیاز اضافه‌ای نمی‌دهد.
    خروجی: امتیاز اعطاشده (0 = چیزی اعطا نشده)."""
    try:
        order = db.get_order(order_id)
    except Exception:
        logger.exception("خواندن سفارش %s برای امتیازدهی ناموفق بود.", order_id)
        return 0
    if not order or order["status"] != "approved":
        return 0
    if not is_enabled(db):
        return 0

    user_id = order["user_id"]
    paid = order["final_price"] if order["final_price"] else order["base_price"]
    state = db.ensure_loyalty_state(user_id)
    points = _purchase_points(db, paid, state["lifetime_earned"])
    if points <= 0:
        return 0

    tier_after = _tier_after(db, state["lifetime_earned"] + points)
    try:
        tx = db.apply_loyalty_mutation(
            user_id, TX_PURCHASE, points,
            tier=tier_after,
            idem_key=f"purchase:{order_id}",
            reference_type="order",
            reference_id=order_id,
            description=f"امتیاز خرید سفارش #{order_id}",
        )
    except ValueError:
        logger.exception("اعطای امتیاز سفارش %s با موجودی منفی روبه‌رو شد.", order_id)
        return 0
    if tx:
        logger.info("Loyalty: %s امتیاز بابت سفارش #%s به کاربر %s اعطا شد.", points, order_id, user_id)
        return points
    return 0


def reverse_purchase(db, order_id: int) -> int:
    """برگشت امتیاز یک سفارش ردشده. فقط اگر قبلاً برای همان سفارش امتیاز
    اعطا شده باشد؛ خودِ برگشت هم idempotent است (دوباره برگشت نمی‌زند)."""
    award = db.find_loyalty_tx(f"purchase:{order_id}")
    if not award:
        return 0
    try:
        tx = db.apply_loyalty_mutation(
            award["user_id"], TX_PURCHASE_REFUND, -award["amount"],
            idem_key=f"refund:{order_id}",
            reference_type="order",
            reference_id=order_id,
            description=f"برگشت امتیاز سفارش ردشده #{order_id}",
        )
    except ValueError:
        logger.exception("برگشت امتیاز سفارش %s با خطا روبه‌رو شد.", order_id)
        return 0
    if tx:
        logger.info("Loyalty: %s امتیاز سفارش #%s برگشت داده شد.", award["amount"], order_id)
        return award["amount"]
    return 0


def award_registration(db, user_tg_id: int) -> int:
    """هدیه‌ی ثبت‌نام — فقط یک‌بار برای هر کاربر، حتی اگر /start تکرار شود."""
    if not is_enabled(db):
        return 0
    bonus = int(db.get_setting("loyalty_reg_bonus", "0") or 0)
    if bonus <= 0:
        return 0
    try:
        tx = db.apply_loyalty_mutation(
            user_tg_id, TX_REGISTRATION, bonus,
            idem_key=f"registration:{user_tg_id}",
            reference_type="registration",
            reference_id=user_tg_id,
            description="هدیه‌ی خوش‌آمدگویی ثبت‌نام",
        )
    except ValueError:
        return 0
    return bonus if tx else 0


def award_referral(db, referrer_tg_id: int, referred_tg_id: int) -> int:
    """امتیاز معرفی برای دعوت‌کننده وقتی نفر جدید واقعاً از لینک دعوت وارد می‌شود.
    برای هر جفت دعوت‌کننده/دعوت‌شده فقط یک‌بار."""
    if not is_enabled(db):
        return 0
    if not referrer_tg_id or not referred_tg_id or referrer_tg_id == referred_tg_id:
        return 0
    bonus = int(db.get_setting("loyalty_referral_bonus", "0") or 0)
    if bonus <= 0:
        return 0
    try:
        tx = db.apply_loyalty_mutation(
            referrer_tg_id, TX_REFERRAL, bonus,
            idem_key=f"referral:{referrer_tg_id}:{referred_tg_id}",
            reference_type="user",
            reference_id=referred_tg_id,
            description=f"پاداش معرفی کاربر {referred_tg_id}",
        )
    except ValueError:
        return 0
    return bonus if tx else 0


def redeem(db, user_tg_id: int, points: int) -> dict:
    """تبدیل امتیاز به اعتبار کیف پول با جریان تراکنشی امن.

    خروجی: {"points", "toman", "balance_after"}
    LoyaltyError با پیام فارسی در صورت نامعتبر بودن درخواست یا کمبود موجودی."""
    if not is_enabled(db):
        raise LoyaltyError("باشگاه مشتریان در حال حاضر غیرفعال است.")
    try:
        points = int(points)
    except (TypeError, ValueError):
        raise LoyaltyError("تعداد امتیاز باید عدد باشد.")
    if points <= 0:
        raise LoyaltyError("تعداد امتیاز باید عددی مثبت باشد.")

    summary = get_summary(db, user_tg_id)
    if not summary["redeem_enabled"]:
        raise LoyaltyError("تبدیل امتیاز در حال حاضر فعال نیست.")
    min_redeem = summary["min_redeem"]
    if min_redeem > 0 and points < min_redeem:
        raise LoyaltyError(f"حداقل امتیاز قابل تبدیل {min_redeem} امتیاز است.")
    redeem_points = summary["redeem_points"]
    redeem_toman = summary["redeem_toman"]
    if points % redeem_points != 0:
        raise LoyaltyError(f"تعداد امتیاز باید مضربی از {redeem_points} باشد.")
    toman = (points // redeem_points) * redeem_toman

    idem_key = f"redeem:{user_tg_id}:{uuid.uuid4().hex[:12]}"
    tx = db.redeem_points_for_wallet(user_tg_id, points, toman, idem_key)
    if tx is None:
        raise LoyaltyError("موجودی امتیاز شما کافی نیست.")
    logger.info("Loyalty: کاربر %s، %s امتیاز را به %s تومان تبدیل کرد.", user_tg_id, points, toman)
    return {"points": points, "toman": toman, "balance_after": tx["balance_after"]}


def admin_adjust(db, admin_tg_id: int, user_tg_id: int, amount: int, reason: str) -> int:
    """تعدیل دستی امتیاز توسط ادمین — همیشه یک رکورد جدید با ثبت ادمین و دلیل.
    خروجی: موجودی جدید. مقدار منفی تا سقف موجودی مجاز است؛ بیشتر از آن خطا."""
    try:
        amount = int(amount)
    except (TypeError, ValueError):
        raise LoyaltyError("مقدار تعدیل باید عدد باشد.")
    if amount == 0:
        raise LoyaltyError("مقدار تعدیل نمی‌تواند صفر باشد.")
    reason = (reason or "").strip()
    if not reason:
        raise LoyaltyError("دلیل تعدیل الزامی است.")

    state = db.ensure_loyalty_state(user_tg_id)
    tier_after = _tier_after(db, state["lifetime_earned"] + (amount if amount > 0 else 0))
    try:
        tx = db.apply_loyalty_mutation(
            user_tg_id, TX_ADMIN_ADJUSTMENT, amount,
            tier=tier_after,
            reference_type="admin",
            reference_id=admin_tg_id,
            description=f"تعدیل توسط ادمین: {reason}",
            metadata=json.dumps({"admin_id": admin_tg_id, "reason": reason}, ensure_ascii=False),
        )
    except ValueError:
        raise LoyaltyError("این تعدیل موجودی امتیاز کاربر را منفی می‌کند و مجاز نیست.")
    logger.info("Loyalty: ادمین %s امتیاز کاربر %s را %+d تعدیل کرد (%s).", admin_tg_id, user_tg_id, amount, reason)
    return tx["balance_after"]


def expire_due(db, now: datetime = None) -> int:
    """انقضای امتیازهای سررسیده — در نسخه‌ی ۱ فعال نیست و توسط هیچ زمان‌بندی
    فراخوانی نمی‌شود؛ فقط معماری برای آن آماده است:

    - ستون expires_at در دفتر کل از الان وجود دارد (اعطاهای آینده می‌توانند
      تاریخ انقضا ثبت کنند).
    - انقضا باید «رکورد جدید POINTS_EXPIRE» بسازد (هرگز رکورد قبلی را حذف یا
      تغییر ندهد) و مصرف از قدیمی‌ترین رکوردها (FIFO) انجام شود.
    - اتصال آن به حلقه‌ی پس‌زمینه (مثل backup_loop در bot_manager) کار نسخه‌ی
      بعد است؛ فعال‌سازی‌اش نیازی به بازنویسی ندارد."""
    raise NotImplementedError("point expiration is designed but not enabled in v1")
