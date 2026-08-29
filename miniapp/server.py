# -*- coding: utf-8 -*-
"""
بک‌اند مینی‌اپ - تک‌فروشنده (تک دیتابیس)

فروشگاه الگوی خیاطی: این سرور فقط به همان یک دیتابیسِ بات اصلی وصل است و
هیچ تفکیک مستأجری (پارامتر ?b=) وجود ندارد. همه‌ی عملیات خرید/تحویل فایل
از طریق «رسید کارت‌به‌کارت + تایید دستی ادمین در بات» انجام می‌شود؛ یعنی
تایید/رد سفارش‌ها و شارژ کیف پول فقط با دکمه‌های داخل بات (callback های
order_approve/order_reject و topup_approve/topup_reject) انجام می‌شود و
این سرور فقط رسید را به ادمین‌ها گزارش می‌دهد.

اجرا (جدا از پروسه‌ی اصلی بات): uvicorn miniapp.server:app --host 127.0.0.1 --port 8001
سپس nginx مسیر / را به این پورت proxy می‌کند.
"""

import sys
import os
import json
import random
import html as html_lib
import asyncio
import logging
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import aiohttp
from fastapi import FastAPI, Header, HTTPException, UploadFile, File, Form, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("miniapp")

from config import BOT_TOKEN, DB_PATH, OWNER_ID, MAX_TEST_PER_USER
from database import Database
from miniapp.auth import validate_init_data
import loyalty

app = FastAPI(title="Pattern Shop Mini App API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")

# دیتابیس بات اصلی (تک دیتابیس - بدون نمایندگی)
db = Database(DB_PATH)
try:
    # اگر این پروسه (uvicorn مینی‌اپ) قبل از بات اصلی اجرا شده و فایل دیتابیس
    # هنوز جدول ندارد، این‌جا هم می‌سازیمش تا هیچ درخواستی با خطای ۵۰۰ مواجه نشود.
    db.init_db(owner_id=OWNER_ID)
except Exception:
    logging.getLogger("miniapp").exception("مقداردهی اولیه دیتابیس ناموفق بود.")


# ---------------------------------------------------------------------------
# ابزارهای تماس با Bot API (همان سبک اعلان‌های نسخه‌ی قبلی)
# ---------------------------------------------------------------------------

_bot_username_cache: Optional[str] = None


async def get_bot_username() -> str:
    """یوزرنیم بات (برای ساخت لینک دعوت زیرمجموعه‌گیری) را با getMe می‌گیرد و کش می‌کند."""
    global _bot_username_cache
    if _bot_username_cache:
        return _bot_username_cache
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getMe") as resp:
                data = await resp.json()
                if data.get("ok"):
                    _bot_username_cache = data["result"]["username"]
    except Exception:
        pass
    return _bot_username_cache or ""


async def _tg_get_file_path(bot_token: str, file_id: str) -> Optional[str]:
    """file_id تلگرام را با getFile به file_path قابل دانلود تبدیل می‌کند."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"https://api.telegram.org/bot{bot_token}/getFile",
                json={"file_id": file_id},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                data = await resp.json()
        if data.get("ok"):
            return (data.get("result") or {}).get("file_path")
    except Exception:
        logging.getLogger("miniapp.telegram").exception("getFile ناموفق بود.")
    return None


async def _tg_download_file(bot_token: str, file_id: str) -> Optional[bytes]:
    """محتوای واقعی یک فایل تلگرامی را دانلود می‌کند (پروکسی getFile + file/bot<token>/<path>)."""
    file_path = await _tg_get_file_path(bot_token, file_id)
    if not file_path:
        return None
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"https://api.telegram.org/file/bot{bot_token}/{file_path}",
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status != 200:
                    return None
                return await resp.read()
    except Exception:
        logging.getLogger("miniapp.telegram").exception("دانلود فایل از تلگرام ناموفق بود.")
        return None


async def send_receipt_media_to_admins(db: Database, bot_token: str, caption: str, reply_markup: str,
                                       file_bytes: bytes, filename: str, content_type: str,
                                       as_document: bool):
    """رسید (عکس یا PDF) را برای همه‌ی ادمین‌ها ارسال می‌کند. (file_id, تعداد تحویل موفق، نتایج) را برمی‌گرداند."""
    admin_ids = db.list_admins()
    sent_file_id = None
    delivered = 0
    results = []
    method = "sendDocument" if as_document else "sendPhoto"
    field = "document" if as_document else "photo"
    async with aiohttp.ClientSession() as session:
        for admin_id in admin_ids:
            form = aiohttp.FormData()
            form.add_field("chat_id", str(admin_id))
            form.add_field("caption", caption)
            form.add_field("reply_markup", reply_markup)
            form.add_field(field, file_bytes, filename=filename, content_type=content_type)
            try:
                async with session.post(
                    f"https://api.telegram.org/bot{bot_token}/{method}", data=form
                ) as resp:
                    data = await resp.json()
                    if data.get("ok"):
                        delivered += 1
                        msg = data["result"]
                        results.append((admin_id, msg["message_id"]))
                        if not sent_file_id:
                            if as_document:
                                sent_file_id = msg["document"]["file_id"]
                            else:
                                sent_file_id = msg["photo"][-1]["file_id"]
            except Exception:
                pass
    return sent_file_id, delivered, results


# ---------------------------------------------------------------------------
# احراز هویت (initData)
# ---------------------------------------------------------------------------

def get_verified_user(x_init_data: str = Header(...)):
    """initData را با توکن بات تایید می‌کند. خروجی: (tg_id, db)

    نکته: کاربر را همین‌جا هم در جدول users ثبت/به‌روز می‌کنیم (نه فقط داخل
    هندلر /start بات)، چون کاربر می‌تواند مستقیماً وارد مینی‌اپ شود بدون آن‌که
    قبلاً /start را در بات زده باشد. بدون این کار، پیام‌های چت زنده/تیکت چنین
    کاربری در دیتابیس ثبت می‌شد ولی چون ردیفی در users نداشت، سمت ادمین با
    خطای «کاربر یافت نشد» مواجه می‌شد."""
    result = validate_init_data(x_init_data, BOT_TOKEN)
    if not result or "user" not in result:
        raise HTTPException(status_code=401, detail="initData نامعتبر است.")
    tg_user = result["user"]
    try:
        db.add_or_update_user(tg_user["id"], tg_user.get("username"), tg_user.get("first_name"))
    except Exception:
        logging.getLogger("miniapp.auth").exception("ثبت/به‌روزرسانی کاربر %s ناموفق بود.", tg_user.get("id"))
    return tg_user["id"], db


# ---------------------------------------------------------------------------
# عضویت اجباری در کانال - هماهنگ با force_join.py که در ربات اصلی اجرا می‌شود.
# در ربات این چک قبل از هر هندلر (میدل‌ور) اجرا می‌شود؛ این‌جا هم باید همان
# منطق قبل از هر اکشن نوشتنی (خرید/تاپ‌آپ/الگوی نمونه/گردونه) اجرا شود تا
# کاربر نتواند صرفاً با استفاده از مینی‌اپ این محدودیت را دور بزند.
async def _is_channel_member_http(bot_token: str, channel: str, tg_id: int) -> bool:
    """مثل force_join.is_channel_member ولی بدون وابستگی به شیء Bot آیوگرم
    (چون این پروسه‌ی fastapi جدا از پروسه‌ی بات است)؛ fail-open در صورت خطا."""
    if not bot_token:
        return True
    url = f"https://api.telegram.org/bot{bot_token}/getChatMember"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url, params={"chat_id": channel, "user_id": tg_id},
                timeout=aiohttp.ClientTimeout(total=8),
            ) as resp:
                data = await resp.json()
    except Exception:
        logging.getLogger("miniapp.forcejoin").exception("بررسی عضویت کانال ناموفق بود.")
        return True
    if not data.get("ok"):
        return True
    status = (data.get("result") or {}).get("status")
    return status not in ("left", "kicked")


async def _force_join_check(tg_id: int, db: Database):
    """اگر عضویت لازم باشد و کاربر عضو نباشد، خطای ۴۰۳ با جزئیات کانال می‌دهد."""
    settings = db.get_force_join_settings()
    if not settings.get("enabled") or not settings.get("channel"):
        return
    if db.is_admin(tg_id):
        return
    member = await _is_channel_member_http(BOT_TOKEN, settings["channel"], tg_id)
    if member:
        return
    channel_display = str(settings["channel"]).lstrip("@")
    raise HTTPException(
        status_code=403,
        detail={
            "code": "force_join",
            "message": "برای ادامه، ابتدا باید در کانال زیر عضو شوید.",
            "channel": settings["channel"],
            "join_link": f"https://t.me/{channel_display}",
        },
    )


async def require_joined(auth=Depends(get_verified_user)):
    """مثل get_verified_user، به‌علاوه‌ی چک عضویت اجباری کانال - برای همه‌ی
    اکشن‌های نوشتنی/خرید (سفارش، تاپ‌آپ، الگوی نمونه، گردونه)."""
    tg_id, db = auth
    await _force_join_check(tg_id, db)
    return auth


@app.get("/api/force-join-status")
async def api_force_join_status(auth=Depends(get_verified_user)):
    """فرانت قبل از نمایش دکمه‌های خرید، این را چک می‌کند تا در صورت لزوم
    بنر عضویت در کانال را نشان دهد (هم‌تراز با رفتار ربات اصلی)."""
    tg_id, db = auth
    settings = db.get_force_join_settings()
    if not settings.get("enabled") or not settings.get("channel") or db.is_admin(tg_id):
        return {"required": False, "member": True}
    member = await _is_channel_member_http(BOT_TOKEN, settings["channel"], tg_id)
    channel_display = str(settings["channel"]).lstrip("@")
    return {
        "required": True, "member": member,
        "channel": settings["channel"], "join_link": f"https://t.me/{channel_display}",
    }


# ---------------------------------------------------------------------------
# فایل‌های استاتیک
# ---------------------------------------------------------------------------

def get_asset_version() -> str:
    """نسخه‌ی خودکار برای cache-busting، بر اساس آخرین زمان تغییر فایل‌های استاتیک."""
    try:
        mtimes = [
            os.path.getmtime(os.path.join(STATIC_DIR, "style.css")),
            os.path.getmtime(os.path.join(STATIC_DIR, "app.js")),
        ]
        return str(int(max(mtimes)))
    except OSError:
        return "1"


@app.get("/", response_class=HTMLResponse)
def serve_index():
    with open(os.path.join(STATIC_DIR, "index.html"), encoding="utf-8") as f:
        html = f.read()
    version = get_asset_version()
    html = html.replace("{{VERSION}}", version)

    # بنر قدیمی حذف شده است؛ متن بالای صفحه همان نام فروشگاه است.
    store_name = db.get_setting("store_name", "🧵 الگوشاپ")
    html = html.replace("{{STORE_NAME}}", html_lib.escape(store_name))
    html = html.replace("{{BANNER_TEXT}}", html_lib.escape(store_name))

    # تم و لوگوی هدر دیگر از پنل وب مدیریت نمی‌شوند؛ مقادیر پیش‌فرض خنثی تزریق می‌شود.
    html = html.replace("{{THEME}}", "clean-light")
    html = html.replace("{{HEADER_LOGO_CLASS}}", "")
    html = html.replace("{{HEADER_LOGO_HTML}}", "")

    return HTMLResponse(html)


# ---------------------------------------------------------------------------
# حساب کاربری
# ---------------------------------------------------------------------------

@app.get("/api/me")
def api_me(auth=Depends(get_verified_user)):
    tg_id, db = auth
    user = db.get_user(tg_id)
    if not user:
        raise HTTPException(status_code=404, detail="کاربر یافت نشد. ابتدا /start را در بات بزنید.")
    wallet = db.get_wallet_credit(tg_id)
    referral = db.get_referral_stats(tg_id)
    orders = db.get_user_orders(tg_id)
    loyalty_summary = None
    try:
        s = loyalty.get_summary(db, tg_id)
        loyalty_summary = {
            "points": s["current"],
            "tier": s["tier"]["name"] if s["tier"] else None,
            "lifetime_earned": s["lifetime_earned"],
        }
    except Exception:
        logger.exception("خلاصه‌ی باشگاه وفاداری کاربر %s دریافت نشد.", tg_id)
    return {
        "telegram_id": tg_id,
        "first_name": user["first_name"],
        "username": user["username"] if "username" in user.keys() else None,
        "joined_at": user["joined_at"] if "joined_at" in user.keys() else None,
        "wallet_credit": wallet,
        "referral_count": referral["count"],
        "orders_count": len(orders),
        "is_admin": db.is_admin(tg_id),
        "admin_role": db.get_admin_role(tg_id),
        "loyalty": loyalty_summary,
    }


# ---------------------------------------------------------------------------
# کاتالوگ و محصولات
# ---------------------------------------------------------------------------

def _product_public(db: Database, p) -> dict:
    """شکل عمومی محصول برای کاتالوگ/جزئیات. available یعنی حداقل یک فایل الگو
    در بانک فایل‌ها ثبت شده است (فروش نامحدود است)."""
    return {
        "id": p["id"],
        "name": p["name"],
        "price": p["price"],
        "description": p["description"],
        "available": db.has_product_files(p["id"]),
        "has_preview": bool((p["preview_file_id"] or "").strip()),
        "category_id": p["category_id"],
    }


@app.get("/api/catalog")
def api_catalog(auth=Depends(get_verified_user)):
    tg_id, db = auth
    categories = db.get_categories(active_only=True)
    result = []
    for c in categories:
        products = db.get_products(c["id"], active_only=True)
        result.append({
            "id": c["id"],
            "name": c["name"],
            "products": [_product_public(db, p) for p in products],
        })
    return result


@app.get("/api/products/{product_id}")
def api_product_detail(product_id: int, auth=Depends(get_verified_user)):
    tg_id, db = auth
    p = db.get_product(product_id)
    if not p or not p["is_active"]:
        raise HTTPException(status_code=404, detail="محصول یافت نشد.")
    return _product_public(db, p)


@app.get("/api/products/{product_id}/preview")
async def api_product_preview(product_id: int):
    # عکس پیش‌نمایش محصول عمداً بدون احراز هویت (عمومی) سرو می‌شود تا هم با
    # <img src="..."> مستقیم کار کند و هم با fetch همراه همان هدرهای بقیه‌ی
    # API ها (هدر اضافه نادیده گرفته می‌شود). محتوای آن فقط یک عکس نمایشی
    # از الگو است و اطلاعات حساسی ندارد.
    p = db.get_product(product_id)
    if not p or not (p["preview_file_id"] or "").strip():
        raise HTTPException(status_code=404, detail="پیش‌نمایشی برای این محصول ثبت نشده است.")
    data = await _tg_download_file(BOT_TOKEN, p["preview_file_id"])
    if not data:
        raise HTTPException(status_code=502, detail="دانلود پیش‌نمایش از تلگرام ناموفق بود.")
    # عکس‌های تلگرام JPEG هستند؛ کش مرورگر یک‌ساعته چون تغییر پیش‌نمایش نادر است.
    return Response(
        content=data,
        media_type="image/jpeg",
        headers={"Cache-Control": "public, max-age=3600"},
    )


# ---------------------------------------------------------------------------
# سفارش‌ها (رسید کارت‌به‌کارت + تایید دستی ادمین در بات)
# ---------------------------------------------------------------------------

class OrderCreate(BaseModel):
    product_id: int
    discount_code: Optional[str] = None  # کد تخفیف اختیاری است


def _order_record_ids(order) -> list:
    """CSV شناسه‌های رکورد product_files ذخیره‌شده در سفارش را به لیست int تبدیل می‌کند."""
    raw = order["file_ids"] or ""
    return [int(s) for s in raw.split(",") if s.strip().isdigit()]


async def _order_admin_caption(db: Database, order_id: int, auto_approved: bool) -> str:
    """کپشن گزارش سفارش برای ادمین - هم‌تراز با _notify_admins_of_order ربات."""
    order = db.get_order(order_id)
    product = db.get_product(order["product_id"])
    user_row = db.get_user(order["user_id"])
    username = user_row["username"] if user_row else ""
    first_name = user_row["first_name"] if user_row else ""
    caption = (
        f"🧾 سفارش #{order_id}\n"
        f"👤 کاربر: {first_name or ''} (@{username or '---'})\n"
        f"🆔 آیدی عددی: {order['user_id']}\n"
        f"🧵 محصول: {product['name'] if product else '---'}\n"
        f"💰 قیمت پایه: {order['base_price']:,} تومان\n"
    )
    if order["discount_amount"]:
        caption += f"🎟 تخفیف کد: {order['discount_amount']:,} تومان\n"
    if order["wallet_used"]:
        caption += f"👛 استفاده از کیف پول: {order['wallet_used']:,} تومان\n"
    caption += f"💵 مبلغ قابل پرداخت: {order['final_price']:,} تومان"
    if auto_approved:
        caption += "\n\n✅ این سفارش به‌طور خودکار تایید و فایل‌های الگو برای کاربر ارسال شد (پرداخت کامل از کیف پول/کد تخفیف)."
    return caption


async def _notify_admins_of_auto_order(db: Database, order_id: int):
    """سفارش‌هایی که کامل از کیف پول/کد تخفیف پوشش داده شده‌اند نیازی به تایید
    دستی ندارند؛ فقط یک پیام اطلاع‌رسانی بدون دکمه برای ادمین‌ها می‌رود."""
    try:
        caption = await _order_admin_caption(db, order_id, auto_approved=True)
        async with aiohttp.ClientSession() as session:
            for admin_id in db.list_admins():
                try:
                    await session.post(
                        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                        json={"chat_id": admin_id, "text": caption},
                    )
                except Exception:
                    pass
    except Exception:
        logging.getLogger("miniapp.orders").exception("اطلاع‌رسانی سفارش خودکار به ادمین‌ها ناموفق بود.")


@app.post("/api/orders")
async def api_create_order(body: OrderCreate, auth=Depends(require_joined)):
    """ایجاد سفارش - آینه‌ی منطق cb_buy_start ربات: اعتبار کد تخفیف، اعمال
    خودکار کیف پول، و اگر مبلغ نهایی صفر شد تایید خودکار سفارش."""
    tg_id, db = auth
    user_row = db.get_user(tg_id)
    if user_row and user_row["is_blocked"]:
        raise HTTPException(status_code=403, detail="حساب شما مسدود شده است.")

    product = db.get_product(body.product_id)
    if not product or not product["is_active"] or not db.has_product_files(body.product_id):
        raise HTTPException(status_code=409, detail="این الگو در حال حاضر موجود نیست.")

    total_price = product["price"]
    discount_code_id = None
    discount_amount = 0
    if body.discount_code:
        code_row = db.get_discount_code(body.discount_code)
        if not db.is_discount_code_valid(code_row):
            raise HTTPException(status_code=400, detail="کد تخفیف نامعتبر است.")
        discount_amount = db.compute_discount_amount(code_row, total_price)
        discount_code_id = code_row["id"]

    wallet_credit = db.get_wallet_credit(tg_id)
    price_after_code = max(total_price - discount_amount, 0)
    wallet_used = min(wallet_credit, price_after_code)

    if wallet_used > 0:
        db.add_wallet_credit(tg_id, -wallet_used)
    if discount_code_id:
        db.increment_discount_usage(discount_code_id)

    order_id = db.create_order(
        tg_id, body.product_id, base_price=total_price,
        wallet_used=wallet_used, discount_code_id=discount_code_id,
        discount_amount=discount_amount,
    )
    order = db.get_order(order_id)

    if order["final_price"] <= 0:
        files = db.get_product_files(body.product_id)
        if not files:
            # الگو بدون فایل شده؛ سفارش را رد کن تا مبلغ کسرشده از کیف پول/تخفیف برگردد
            db.reject_order(order_id)
            try:
                loyalty.reverse_purchase(db, order_id)
            except Exception:
                logger.exception("برگشت امتیاز وفاداری سفارش %s ناموفق بود.", order_id)
            raise HTTPException(
                status_code=409,
                detail="این الگو در حال حاضر موجود نیست؛ مبلغ کسرشده از کیف پول شما به‌طور کامل بازگردانده شد.",
            )
        db.approve_order(order_id, [f["id"] for f in files])
        awarded = 0
        try:
            awarded = loyalty.award_purchase(db, order_id)
        except Exception:
            logger.exception("اعطای امتیاز وفاداری سفارش %s ناموفق بود.", order_id)
        try:
            db.reward_referrer_if_first_purchase(tg_id, order["base_price"])
        except Exception:
            pass
        await _notify_admins_of_auto_order(db, order_id)
        result = {
            "status": "approved", "order_id": order_id,
            "files": [{"record_id": f["id"]} for f in files],
        }
        if awarded > 0:
            result["loyalty_awarded"] = awarded
        return result

    # مبلغی باقی مانده - کاربر باید رسید کارت‌به‌کارت آپلود کند تا ادمین در بات تایید کند
    return {
        "status": "pending", "order_id": order_id, "final_price": order["final_price"],
        "wallet_used": wallet_used, "discount_amount": discount_amount,
        "card_number": db.get_setting("card_number"), "card_holder": db.get_setting("card_holder"),
    }


@app.get("/api/orders")
def api_orders(auth=Depends(get_verified_user)):
    """لیست سفارش‌های کاربر (بدون سفارش‌های حذف‌شده توسط خودش)."""
    tg_id, db = auth
    result = []
    for o in db.get_user_orders(tg_id):
        item = {
            "id": o["id"],
            "product_name": o["product_name"] or "نامشخص",
            "status": o["status"],
            "final_price": o["final_price"],
            "created_at": o["created_at"],
        }
        if o["status"] == "approved":
            # تعداد فایل‌های الگوی تحویلی فقط برای سفارش تاییدشده معنا دارد
            item["file_count"] = len(_order_record_ids(o))
        result.append(item)
    return result


@app.get("/api/orders/{order_id}")
def api_order_detail(order_id: int, auth=Depends(get_verified_user)):
    tg_id, db = auth
    order = db.get_order(order_id)
    if not order or order["user_id"] != tg_id:
        raise HTTPException(status_code=404, detail="سفارش یافت نشد.")
    product = db.get_product(order["product_id"])
    detail = {
        "id": order["id"],
        "product_name": product["name"] if product else "نامشخص",
        "status": order["status"],
        "final_price": order["final_price"],
        "base_price": order["base_price"],
        "wallet_used": order["wallet_used"],
        "discount_amount": order["discount_amount"],
        "created_at": order["created_at"],
    }
    if order["status"] == "approved":
        detail["files"] = [{"record_id": rid} for rid in _order_record_ids(order)]
    return detail


@app.delete("/api/orders/{order_id}")
def api_delete_order(order_id: int, auth=Depends(get_verified_user)):
    """حذف (مخفی‌کردن) یک سفارش از لیست «سفارش‌های من» توسط خود کاربر؛ همان
    رفتار بات - رکورد برای گزارش‌های ادمین دست‌نخورده می‌ماند."""
    tg_id, db = auth
    removed = db.delete_owned_order(order_id, tg_id)
    if not removed:
        raise HTTPException(status_code=404, detail="سفارش یافت نشد یا متعلق به شما نیست.")
    return {"status": "ok"}


@app.post("/api/orders/{order_id}/receipt")
async def api_order_receipt(
    order_id: int,
    photo: UploadFile = File(None),
    file: UploadFile = File(None),
    auth=Depends(get_verified_user),
):
    """آپلود رسید کارت‌به‌کارت سفارش (عکس یا PDF). فایل برای همه‌ی ادمین‌ها با
    دکمه‌های تایید/رد ارسال می‌شود؛ تایید نهایی فقط با دکمه‌های داخل بات انجام
    می‌شود (callback های order_approve/order_reject - این‌جا هیچ تاییدی انجام
    نمی‌شود). فیلد multipart هم «photo» (سازگار با نسخه‌ی قبلی فرانت) و هم
    «file» پذیرفته می‌شود."""
    tg_id, db = auth
    order = db.get_order(order_id)
    if not order or order["user_id"] != tg_id:
        raise HTTPException(status_code=404, detail="سفارش یافت نشد.")
    if order["status"] != "pending":
        raise HTTPException(status_code=400, detail="این سفارش قبلاً بررسی شده است.")

    upload = photo or file
    if upload is None:
        raise HTTPException(status_code=400, detail="فایل رسید ارسال نشده است.")
    content_type = upload.content_type or ""
    as_document = not content_type.startswith("image/")
    if not (content_type.startswith("image/") or content_type == "application/pdf"):
        raise HTTPException(status_code=400, detail="فقط عکس یا فایل PDF رسید پذیرفته می‌شود.")

    file_bytes = await upload.read()
    if len(file_bytes) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="حجم فایل بیش از حد مجاز است.")

    user = db.get_user(tg_id)
    product = db.get_product(order["product_id"])
    # کپشن هم‌تراز با _notify_admins_of_order ربات
    caption = (
        f"🧾 سفارش #{order_id}\n"
        f"👤 کاربر: {(user['first_name'] if user else '') or ''} (@{(user['username'] if user else '') or '---'})\n"
        f"🆔 آیدی عددی: {tg_id}\n"
        f"🧵 محصول: {product['name'] if product else '---'}\n"
        f"💰 قیمت پایه: {order['base_price']:,} تومان\n"
    )
    if order["discount_amount"]:
        caption += f"🎟 تخفیف کد: {order['discount_amount']:,} تومان\n"
    if order["wallet_used"]:
        caption += f"👛 استفاده از کیف پول: {order['wallet_used']:,} تومان\n"
    caption += f"💵 مبلغ قابل پرداخت: {order['final_price']:,} تومان"

    reply_markup = json.dumps({
        "inline_keyboard": [[
            {"text": "✅ تایید و ارسال فایل‌ها", "callback_data": f"order_approve:{order_id}"},
            {"text": "❌ رد کردن", "callback_data": f"order_reject:{order_id}"},
        ]]
    })

    admin_ids = db.list_admins()
    if not admin_ids:
        raise HTTPException(status_code=500, detail="هیچ ادمینی برای بررسی رسید ثبت نشده است.")

    sent_file_id, delivered, results = await send_receipt_media_to_admins(
        db, BOT_TOKEN, caption, reply_markup, file_bytes,
        upload.filename or ("receipt.pdf" if as_document else "receipt.jpg"),
        content_type or ("application/pdf" if as_document else "image/jpeg"),
        as_document,
    )
    if delivered == 0:
        raise HTTPException(status_code=502, detail="ارسال رسید به ادمین ناموفق بود. دوباره تلاش کنید.")

    for admin_id, message_id in results:
        db.set_order_admin_message(order_id, admin_id, message_id)
    if sent_file_id:
        db.set_order_receipt(order_id, sent_file_id, "document" if as_document else "photo")

    return {"ok": True, "status": "sent"}


@app.get("/api/orders/{order_id}/files/{record_id}")
async def api_order_file(order_id: int, record_id: int, auth=Depends(get_verified_user)):
    """دانلود مستقیم یکی از فایل‌های الگوی یک سفارش تاییدشده. فقط مالک سفارش،
    فقط سفارش تاییدشده و فقط رکوردی که واقعاً در file_ids همان سفارش است."""
    tg_id, db = auth
    order = db.get_order(order_id)
    if not order or order["user_id"] != tg_id:
        raise HTTPException(status_code=404, detail="سفارش یافت نشد.")
    if order["status"] != "approved":
        raise HTTPException(status_code=400, detail="فایل‌های این سفارش هنوز تایید نشده‌اند.")
    if record_id not in _order_record_ids(order):
        raise HTTPException(status_code=404, detail="این فایل متعلق به این سفارش نیست.")

    row = next((r for r in db.get_product_files(order["product_id"]) if r["id"] == record_id), None)
    if not row:
        raise HTTPException(status_code=404, detail="فایل الگو یافت نشد.")

    data = await _tg_download_file(BOT_TOKEN, row["file_id"])
    if not data:
        raise HTTPException(status_code=502, detail="دانلود فایل از تلگرام ناموفق بود. دوباره تلاش کنید.")

    # محتوای خصوصی کاربر است؛ کش نشود. فایل‌های الگو PDF هستند.
    return Response(
        content=data,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="pattern-{record_id}.pdf"',
            "Cache-Control": "no-store",
        },
    )


# ---------------------------------------------------------------------------
# الگوی نمونه‌ی رایگان
# ---------------------------------------------------------------------------

@app.get("/api/sample")
def api_sample_status(auth=Depends(get_verified_user)):
    """وضعیت الگوی نمونه برای فرانت (جایگزین endpoint وضعیت نسخه‌ی قبلی)."""
    tg_id, db = auth
    user = db.get_user(tg_id)
    return {
        "enabled": db.get_setting("test_enabled", "1") == "1",
        "used": bool(user and user["test_used"] >= MAX_TEST_PER_USER),
        "available": db.count_sample_files(),
    }


@app.post("/api/sample")
async def api_sample_claim(auth=Depends(require_joined)):
    """دریافت الگوی نمونه‌ی رایگان. فایل مصرف نمی‌شود (همیشه همان اولین رکورد
    مخزن sample_files برگردانده می‌شود)؛ شمارنده‌ی test_used کاربر کنترل می‌کند."""
    tg_id, db = auth
    if db.get_setting("test_enabled", "1") != "1":
        raise HTTPException(status_code=400, detail="در حال حاضر امکان دریافت الگوی نمونه غیرفعال است.")
    user = db.get_user(tg_id)
    if user and user["test_used"] >= MAX_TEST_PER_USER:
        raise HTTPException(status_code=400, detail="شما قبلاً الگوی نمونه‌ی رایگان خود را دریافت کرده‌اید.")
    row = db.take_unused_sample_file()
    if not row:
        raise HTTPException(status_code=400, detail="متاسفانه موجودی الگوی نمونه تمام شده است.")
    db.mark_test_used(tg_id)
    return {"ok": True, "download": "/api/sample/file"}


@app.get("/api/sample/file")
async def api_sample_file(auth=Depends(get_verified_user)):
    """دانلود فایل الگوی نمونه. فقط کاربرِ احراز‌هویت‌شده (tg_id فقط برای احراز
    هویت است؛ همه‌ی کاربران همان فایل نمونه‌ی اول مخزن را می‌گیرند)."""
    tg_id, db = auth
    row = db.take_unused_sample_file()
    if not row:
        raise HTTPException(status_code=404, detail="الگوی نمونه‌ای موجود نیست.")
    data = await _tg_download_file(BOT_TOKEN, row["file_id"])
    if not data:
        raise HTTPException(status_code=502, detail="دانلود فایل از تلگرام ناموفق بود. دوباره تلاش کنید.")
    return Response(
        content=data,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="sample-{row["id"]}.pdf"',
            "Cache-Control": "no-store",
        },
    )


# ---------------------------------------------------------------------------
# گردونه‌ی شانس
# ---------------------------------------------------------------------------

@app.get("/api/wheel")
def api_wheel_status(auth=Depends(get_verified_user)):
    tg_id, db = auth
    settings = db.get_wheel_settings()
    can_spin, remaining_hours = db.can_spin_wheel(tg_id)
    return {
        "enabled": settings["enabled"], "can_spin": can_spin,
        "remaining_hours": round(remaining_hours, 1) if remaining_hours else 0,
        "prizes": settings["prizes"],
    }


@app.post("/api/wheel/spin")
def api_wheel_spin(auth=Depends(require_joined)):
    tg_id, db = auth
    settings = db.get_wheel_settings()
    if not settings["enabled"]:
        raise HTTPException(status_code=400, detail="گردونه غیرفعال است.")
    can_spin, remaining_hours = db.can_spin_wheel(tg_id)
    if not can_spin:
        raise HTTPException(status_code=429, detail=f"حدود {int(remaining_hours)+1} ساعت دیگر دوباره امتحان کن.")

    db.record_wheel_spin(tg_id)
    won = random.randint(1, 100) <= settings["win_percent"]
    if won and settings["prizes"]:
        percent = random.choice(settings["prizes"])
        code, expires_at = db.generate_wheel_prize_code(tg_id, percent)
        return {"won": True, "percent": percent, "code": code, "expires_at": expires_at}
    return {"won": False}


# ---------------------------------------------------------------------------
# کیف پول
# ---------------------------------------------------------------------------

class TopupCreate(BaseModel):
    amount: int


@app.post("/api/wallet/topup-request")
def api_topup_request(body: TopupCreate, auth=Depends(require_joined)):
    tg_id, db = auth
    user_row = db.get_user(tg_id)
    if user_row and user_row["is_blocked"]:
        raise HTTPException(status_code=403, detail="حساب شما مسدود شده است.")
    if body.amount < 1000:
        raise HTTPException(status_code=400, detail="حداقل مبلغ ۱۰۰۰ تومان است.")
    topup_id = db.create_topup(tg_id, body.amount)
    return {
        "topup_id": topup_id, "card_number": db.get_setting("card_number"),
        "card_holder": db.get_setting("card_holder"),
        "note": "مبلغ را واریز کرده و عکس رسید را همینجا ارسال کنید.",
    }


@app.post("/api/wallet/topup-receipt")
async def api_topup_receipt(
    topup_id: int = Form(...),
    photo: UploadFile = File(...),
    auth=Depends(get_verified_user),
):
    """آپلود رسید شارژ کیف پول (فقط عکس، مثل نسخه‌ی قبل). تایید/رد فقط با
    دکمه‌های داخل بات (callback های topup_approve/topup_reject) انجام می‌شود."""
    tg_id, db = auth
    topup = db.get_topup(topup_id)
    if not topup or topup["user_id"] != tg_id:
        raise HTTPException(status_code=404, detail="درخواست شارژ یافت نشد.")
    if topup["status"] != "pending":
        raise HTTPException(status_code=400, detail="این درخواست قبلاً بررسی شده است.")
    if not photo.content_type or not photo.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="فقط عکس رسید پذیرفته می‌شود.")

    photo_bytes = await photo.read()
    if len(photo_bytes) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="حجم عکس بیش از حد مجاز است.")

    user = db.get_user(tg_id)
    caption = (
        f"👛 درخواست شارژ کیف پول #{topup_id}\n"
        f"👤 کاربر: {(user['first_name'] if user else '') or ''} (@{(user['username'] if user else '') or '---'})\n"
        f"🆔 آیدی عددی: {tg_id}\n"
        f"💰 مبلغ: {topup['amount']:,} تومان"
    )
    reply_markup = json.dumps({
        "inline_keyboard": [[
            {"text": "✅ تایید و شارژ کیف پول", "callback_data": f"topup_approve:{topup_id}"},
            {"text": "❌ رد کردن", "callback_data": f"topup_reject:{topup_id}"},
        ]]
    })

    admin_ids = db.list_admins()
    if not admin_ids:
        raise HTTPException(status_code=500, detail="هیچ ادمینی برای بررسی رسید ثبت نشده است.")

    sent_file_id, delivered, results = await send_receipt_media_to_admins(
        db, BOT_TOKEN, caption, reply_markup, photo_bytes, photo.filename or "receipt.jpg",
        photo.content_type, as_document=False,
    )
    if delivered == 0:
        raise HTTPException(status_code=502, detail="ارسال رسید به ادمین ناموفق بود. دوباره تلاش کنید.")

    for admin_id, message_id in results:
        db.set_topup_admin_message(topup_id, admin_id, message_id)
    if sent_file_id:
        db.set_topup_receipt(topup_id, sent_file_id)

    return {"ok": True, "status": "sent"}


# ---------------------------------------------------------------------------
# زیرمجموعه‌گیری
# ---------------------------------------------------------------------------

@app.get("/api/referral")
async def api_referral(auth=Depends(get_verified_user)):
    tg_id, db = auth
    if db.get_setting("referral_button_enabled", "1") != "1":
        return {"enabled": False}
    commission_on = db.get_setting("referral_enabled", "1") == "1"
    fc_on = db.get_setting("referral_free_config_enabled", "0") == "1"
    ib_on = db.get_setting("referral_invite_bonus_enabled", "0") == "1"
    if not (commission_on or fc_on or ib_on):
        return {"enabled": False}
    username = await get_bot_username()
    ref_start = f"ref{tg_id}"
    link = f"https://t.me/{username}?start={ref_start}" if username else None
    stats = db.get_referral_stats(tg_id)
    return {
        "enabled": True,
        "link": link,
        "count": stats["count"],
        "credit": stats["credit"],
        "commission_enabled": commission_on,
        "percent": db.get_setting("referral_percent", "10"),
        "commission_max_count": int(db.get_setting("referral_commission_max_count", "0") or 0),
        "free_config_enabled": fc_on,
        "free_config_threshold": int(db.get_setting("referral_free_config_threshold", "10") or 0),
        "invite_bonus_enabled": ib_on,
        "invite_bonus_amount": int(db.get_setting("referral_invite_bonus_amount", "0") or 0),
        "invite_bonus_max_count": int(db.get_setting("referral_invite_bonus_max_count", "0") or 0),
    }


# ---------------------------------------------------------------------------
# چت پشتیبانی
# ---------------------------------------------------------------------------

@app.get("/api/support/messages")
def api_support_messages(since_id: int = 0, auth=Depends(get_verified_user)):
    tg_id, db = auth
    db.mark_support_read_by_user(tg_id)
    rows = db.get_support_messages(tg_id, since_id=since_id)
    return [
        {"id": m["id"], "sender": m["sender"], "message": m["message"], "created_at": m["created_at"]}
        for m in rows
    ]


class SupportMessageCreate(BaseModel):
    message: str


@app.post("/api/support/messages")
async def api_support_send(body: SupportMessageCreate, auth=Depends(get_verified_user)):
    tg_id, db = auth
    text = (body.message or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="پیام نمی‌تواند خالی باشد.")
    if len(text) > 2000:
        raise HTTPException(status_code=400, detail="پیام بیش از حد طولانی است.")

    msg_id = db.add_support_message(tg_id, "user", text)

    user = db.get_user(tg_id)
    caption = (
        f"📩 پیام جدید از کاربر (مینی‌اپ)\n"
        f"👤 {(user['first_name'] if user else '') or ''} (@{(user['username'] if user else '') or '---'})\n"
        f"🆔 `{tg_id}`\n\n"
        f"✉️ {text}"
    )
    reply_markup = {
        "inline_keyboard": [[{"text": "↩️ پاسخ", "callback_data": f"reply_user:{tg_id}"}]]
    }
    # فقط به اولین ادمین/مالک آنلاین اطلاع بده تا مکالمه به او اختصاص یابد؛
    # اگر هیچ‌کس آنلاین نبود، طبق روال قدیم به همه‌ی ادمین‌ها اطلاع بده.
    target_admin = db.resolve_support_admin_for_message(tg_id)
    admin_ids = [target_admin] if target_admin else db.list_admins()
    async with aiohttp.ClientSession() as session:
        for admin_id in admin_ids:
            try:
                await session.post(
                    f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                    json={
                        "chat_id": admin_id, "text": caption,
                        "parse_mode": "Markdown", "reply_markup": reply_markup,
                    },
                )
            except Exception:
                pass

    return {"id": msg_id, "sender": "user", "message": text}


# ---------------------------------------------------------------------------
# سیستم تیکت (جدا از چت مستقیم بالا)
# ---------------------------------------------------------------------------

class TicketCreate(BaseModel):
    subject: str
    message: str


class TicketMessageCreate(BaseModel):
    message: str


def _ticket_to_dict(t):
    return {
        "id": t["id"], "subject": t["subject"], "status": t["status"],
        "claimed_by": t["claimed_by"],
        "created_at": t["created_at"], "updated_at": t["updated_at"],
    }


@app.get("/api/tickets")
def api_list_my_tickets(auth=Depends(get_verified_user)):
    tg_id, db = auth
    return [_ticket_to_dict(t) for t in db.get_user_tickets(tg_id)]


@app.post("/api/tickets")
async def api_create_ticket(body: TicketCreate, auth=Depends(get_verified_user)):
    tg_id, db = auth
    subject = (body.subject or "").strip()
    message = (body.message or "").strip()
    if not subject or not message:
        raise HTTPException(status_code=400, detail="موضوع و متن پیام نمی‌تواند خالی باشد.")
    if len(subject) > 150 or len(message) > 2000:
        raise HTTPException(status_code=400, detail="متن وارد شده بیش از حد طولانی است.")

    ticket_id = db.create_ticket(tg_id, subject, message)

    user = db.get_user(tg_id)
    caption = (
        f"🎫 تیکت جدید #{ticket_id}\n"
        f"👤 {(user['first_name'] if user else '') or ''} (@{(user['username'] if user else '') or '---'})\n"
        f"🆔 `{tg_id}`\n\n"
        f"📌 {subject}\n✉️ {message}"
    )
    admin_ids = db.list_admins()
    async with aiohttp.ClientSession() as session:
        for admin_id in admin_ids:
            try:
                await session.post(
                    f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                    json={"chat_id": admin_id, "text": caption, "parse_mode": "Markdown"},
                )
            except Exception:
                pass

    return _ticket_to_dict(db.get_ticket(ticket_id))


@app.get("/api/tickets/{ticket_id}/messages")
def api_get_my_ticket_messages(ticket_id: int, since_id: int = 0, auth=Depends(get_verified_user)):
    tg_id, db = auth
    ticket = db.get_ticket(ticket_id)
    if not ticket or ticket["user_id"] != tg_id:
        raise HTTPException(status_code=404, detail="تیکت یافت نشد.")
    db.mark_ticket_read_by_user(ticket_id)
    rows = db.get_ticket_messages(ticket_id, since_id=since_id)
    return {
        "ticket": _ticket_to_dict(ticket),
        "messages": [
            {"id": m["id"], "sender": m["sender"], "message": m["message"], "created_at": m["created_at"]}
            for m in rows
        ],
    }


@app.post("/api/tickets/{ticket_id}/messages")
async def api_send_my_ticket_message(ticket_id: int, body: TicketMessageCreate, auth=Depends(get_verified_user)):
    tg_id, db = auth
    ticket = db.get_ticket(ticket_id)
    if not ticket or ticket["user_id"] != tg_id:
        raise HTTPException(status_code=404, detail="تیکت یافت نشد.")
    if ticket["status"] == "closed":
        raise HTTPException(status_code=400, detail="این تیکت بسته شده است.")
    text = (body.message or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="پیام نمی‌تواند خالی باشد.")
    if len(text) > 2000:
        raise HTTPException(status_code=400, detail="پیام بیش از حد طولانی است.")

    msg_id = db.add_ticket_message(ticket_id, "user", text)

    user = db.get_user(tg_id)
    caption = (
        f"🎫 پیام جدید در تیکت #{ticket_id} ({ticket['subject']})\n"
        f"👤 {(user['first_name'] if user else '') or ''} (@{(user['username'] if user else '') or '---'})\n\n"
        f"✉️ {text}"
    )
    admin_ids = db.list_admins()
    async with aiohttp.ClientSession() as session:
        for admin_id in admin_ids:
            try:
                await session.post(
                    f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                    json={"chat_id": admin_id, "text": caption, "parse_mode": "Markdown"},
                )
            except Exception:
                pass

    return {"id": msg_id, "sender": "user", "message": text}


@app.post("/api/tickets/{ticket_id}/close")
def api_close_my_ticket(ticket_id: int, auth=Depends(get_verified_user)):
    tg_id, db = auth
    ticket = db.get_ticket(ticket_id)
    if not ticket or ticket["user_id"] != tg_id:
        raise HTTPException(status_code=404, detail="تیکت یافت نشد.")
    db.close_ticket(ticket_id)
    return {"status": "ok"}


# فایل‌های استاتیک (فرانت مینی‌اپ) - همیشه آخرین route باشد
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8001)
