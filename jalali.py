# -*- coding: utf-8 -*-
"""
تبدیل تاریخ میلادی به شمسی (جلالی) - بدون وابستگی به کتابخانه‌ی خارجی.

نکته‌ی مهم: این ماژول فقط برای «نمایش» تاریخ استفاده می‌شود. تمام محاسبات و
مقایسه‌های داخلی (انقضای سرویس، بازه‌های آماری و ...) همچنان روی تاریخ
میلادی/ISO انجام می‌شود؛ فقط زمان نمایش به کاربر/ادمین، این ماژول رشته‌ی
شمسی می‌سازد.
"""

from datetime import datetime, date

JALALI_MONTHS = [
    "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
    "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند",
]


def _div(a, b):
    return a // b


def gregorian_to_jalali(gy: int, gm: int, gd: int):
    g_days_in_month = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    j_days_in_month = [31, 31, 31, 31, 31, 31, 30, 30, 30, 30, 30, 29]

    gy2 = gy - 1600
    gm2 = gm - 1
    gd2 = gd - 1

    g_day_no = 365 * gy2 + _div(gy2 + 3, 4) - _div(gy2 + 99, 100) + _div(gy2 + 399, 400)
    for i in range(gm2):
        g_day_no += g_days_in_month[i]
    if gm2 > 1 and ((gy % 4 == 0 and gy % 100 != 0) or (gy % 400 == 0)):
        g_day_no += 1
    g_day_no += gd2

    j_day_no = g_day_no - 79

    j_np = _div(j_day_no, 12053)
    j_day_no %= 12053

    jy = 979 + 33 * j_np + 4 * _div(j_day_no, 1461)
    j_day_no %= 1461

    if j_day_no >= 366:
        jy += _div(j_day_no - 1, 365)
        j_day_no = (j_day_no - 1) % 365

    jm, jd = 12, j_day_no + 1
    for i in range(11):
        if j_day_no < j_days_in_month[i]:
            jm = i + 1
            jd = j_day_no + 1
            break
        j_day_no -= j_days_in_month[i]

    return jy, jm, jd


def jalali_to_gregorian(jy: int, jm: int, jd: int):
    """معکوس gregorian_to_jalali؛ برای تبدیل تاریخ انتخاب‌شده‌ی شمسی (مثلاً در فیلتر
    بازه‌ی زمانی) به میلادی، جهت استفاده در پرس‌وجوهای دیتابیس."""
    j_days_in_month = [31, 31, 31, 31, 31, 31, 30, 30, 30, 30, 30, 29]
    g_days_in_month = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]

    jy2 = jy - 979
    jm2 = jm - 1
    jd2 = jd - 1

    j_day_no = 365 * jy2 + _div(jy2, 33) * 8 + _div(jy2 % 33 + 3, 4)
    for i in range(jm2):
        j_day_no += j_days_in_month[i]
    j_day_no += jd2

    g_day_no = j_day_no + 79

    gy = 1600 + 400 * _div(g_day_no, 146097)
    g_day_no %= 146097

    leap = True
    if g_day_no >= 36525:
        g_day_no -= 1
        gy += 100 * _div(g_day_no, 36524)
        g_day_no %= 36524
        if g_day_no >= 365:
            g_day_no += 1
        else:
            leap = False

    gy += 4 * _div(g_day_no, 1461)
    g_day_no %= 1461

    if g_day_no >= 366:
        leap = False
        g_day_no -= 1
        gy += _div(g_day_no, 365)
        g_day_no %= 365

    gm, gd = 1, g_day_no + 1
    days = g_day_no
    for i in range(12):
        dim = g_days_in_month[i] + (1 if i == 1 and ((gy % 4 == 0 and gy % 100 != 0) or gy % 400 == 0) else 0)
        if days < dim:
            gm = i + 1
            gd = days + 1
            break
        days -= dim

    return gy, gm, gd


def _coerce_datetime(value):
    if value is None or value == "":
        return None
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00").replace(" ", "T", 1) if "T" not in value else value.replace("Z", "+00:00"))
        except ValueError:
            try:
                return datetime.strptime(value[:19], "%Y-%m-%d %H:%M:%S")
            except ValueError:
                return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day)
    return None


def to_jalali_str(value, with_time: bool = False) -> str:
    """value: datetime | date | رشته‌ی ISO | None -> رشته‌ی تاریخ شمسی «۱۴۰۵/۰۵/۲۱»."""
    dt = _coerce_datetime(value)
    if dt is None:
        return "-"
    jy, jm, jd = gregorian_to_jalali(dt.year, dt.month, dt.day)
    date_part = f"{jy:04d}/{jm:02d}/{jd:02d}"
    if with_time:
        return f"{date_part} - {dt.strftime('%H:%M')}"
    return date_part


def to_jalali_month_day(value) -> str:
    """فقط روز/ماه شمسی، برای لیبل نمودار (مثل «۰۵/۲۱»)."""
    dt = _coerce_datetime(value)
    if dt is None:
        return "-"
    jy, jm, jd = gregorian_to_jalali(dt.year, dt.month, dt.day)
    return f"{jm:02d}/{jd:02d}"
