# -*- coding: utf-8 -*-
"""پرداخت‌ها - شارژ کیف پول و تصمیم روی آن، مشترک بین بات و پنل وب.

همه‌ی گذارهای مالیِ توپاپ به‌وسیله‌ی این ماژول انجام می‌شوند تا «یک» رفتار
اتمیک (با قفل تراکنش و شرطِ status='pending') در همه‌ی رابط‌ها حاکم باشد.
"""

from dataclasses import dataclass

from services.errors import PaymentError, AlreadyDecidedError


@dataclass
class TopupDecision:
    success: bool
    reason: str = ""          # None در صورت موفقیت؛ کدِ خطا در غیر این صورت
    applied: bool = True      # False = تصمیم قبلاً گرفته شده و بدونِ اثر بود


def approval_hooks_ok(db) -> dict:
    """بررسی‌های سلامت پیش از تأیید یک شارژ (هیچ‌چیز را تغییر نمی‌دهد)."""
    return {"enabled": True}


def approve_topup(db, topup_id: int, actor: str = "") -> TopupDecision:
    """تأیید شارژ کیف پول به‌صورت اتمیک. اگر شارژ قبلاً تأیید/رد شده باشد
    (اعمالِ هم‌زمان وب + بات) هیچ اثری ندارد و applied=False برمی‌گرداند."""
    ok = db.approve_topup(topup_id)
    if not ok:
        return TopupDecision(success=False, reason="already_decided", applied=False)
    return TopupDecision(success=True)


def reject_topup(db, topup_id: int, actor: str = "") -> TopupDecision:
    ok = db.reject_topup(topup_id)
    if not ok:
        return TopupDecision(success=False, reason="already_decided", applied=False)
    return TopupDecision(success=True)


def get_topup(db, topup_id: int):
    return db.get_topup(topup_id)


def list_topups(db, status: str = "pending"):
    return db.get_topups_by_status(status)