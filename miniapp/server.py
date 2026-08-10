# -*- coding: utf-8 -*-
"""
بک‌اند مینی‌اپ - چندمستأجر (Multi-tenant)

یک سرور واحد، هم برای بات اصلی و هم برای همه‌ی بات‌های نمایندگی.
شناسه‌ی نماینده از طریق کوئری‌پارامتر ?b=<reseller_id> در URL مینی‌اپ مشخص
می‌شود (که هنگام ساخت دکمه‌ی مینی‌اپ در keyboards.py به‌صورت خودکار اضافه می‌شود).
اگر ?b وجود نداشته باشد یا خالی/۰ باشد، یعنی بات اصلی.

هر درخواست بر اساس همین شناسه، دیتابیس و توکن بات درست را resolve می‌کند؛
یعنی هر نماینده کاملاً مستقل و ایزوله (دیتابیس خودش) از مینی‌اپ استفاده می‌کند.

اجرا (جدا از پروسه‌ی اصلی بات): uvicorn miniapp.server:app --host 127.0.0.1 --port 8001
سپس nginx مسیر / را به این پورت proxy می‌کند.
"""

import sys
import os
import json
import random
from dataclasses import dataclass
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import aiohttp
from fastapi import FastAPI, Header, HTTPException, UploadFile, File, Form, Depends, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import logging
import sqlite3

logging.basicConfig(level=logging.INFO)

from config import BOT_TOKEN, DB_PATH, OWNER_ID, MAX_TEST_PER_USER, resolve_db_path, RESELLER_DBS_DIR
from database import Database, MENU_BUTTON_META, DEFAULT_MENU_ORDER
from miniapp.auth import validate_init_data

app = FastAPI(title="V2Ray Shop Mini App API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")

# دیتابیس بات اصلی - هم برای سرویس‌دهی مستقیم به بات اصلی، هم برای پیدا کردن
# دیتابیس/توکن بات‌های نمایندگی از روی جدول reseller_bots استفاده می‌شود.
main_db = Database(DB_PATH)
try:
    # اگر این پروسه (uvicorn مینی‌اپ) قبل از بات اصلی اجرا شده و فایل دیتابیس
    # هنوز جدول ندارد، این‌جا هم می‌سازیمش تا هیچ درخواستی با خطای ۵۰۰ مواجه نشود.
    main_db.init_db(owner_id=OWNER_ID)
except Exception:
    logging.getLogger("miniapp.tenant").exception("مقداردهی اولیه دیتابیس اصلی ناموفق بود.")

_bot_username_cache: dict[str, str] = {}  # bot_token -> username


# ---------------------------------------------------------------------------
# تشخیص مستأجر (بات اصلی یا یک نماینده‌ی مشخص)
# ---------------------------------------------------------------------------

@dataclass
class Tenant:
    db: Database
    bot_token: str
    tenant_id: str  # "" برای بات اصلی، در غیر این صورت id عددی نماینده به‌صورت رشته


_tenant_logger = logging.getLogger("miniapp.tenant")


def get_tenant(b: str = Query("", description="شناسه‌ی نماینده؛ خالی یعنی بات اصلی")) -> Tenant:
    b = (b or "").strip()
    if not b or b == "0":
        return Tenant(db=main_db, bot_token=BOT_TOKEN, tenant_id="")
    if not b.isdigit():
        raise HTTPException(status_code=400, detail="شناسه‌ی فروشگاه نامعتبر است.")

    try:
        row = main_db.get_reseller_bot(int(b))
    except sqlite3.OperationalError:
        _tenant_logger.exception(
            "خطای دیتابیس اصلی هنگام خواندن reseller_bots (b=%s). db_path=%s - احتمالاً جدول‌ها هنوز ساخته نشده‌اند.",
            b, DB_PATH,
        )
        raise HTTPException(status_code=503, detail="سرور موقتاً در دسترس نیست، دوباره تلاش کنید.")

    if not row or not row["is_active"]:
        _tenant_logger.warning(
            "تننت b=%s پیدا نشد یا غیرفعال است. row=%s", b, dict(row) if row else None
        )
        raise HTTPException(status_code=404, detail="این فروشگاه در دسترس نیست.")

    resolved_path = resolve_db_path(row["db_path"])
    if not os.path.exists(resolved_path):
        _tenant_logger.error(
            "تننت b=%s معتبر است ولی فایل دیتابیسش پیدا نشد. stored_path=%s resolved_path=%s",
            b, row["db_path"], resolved_path,
        )
        raise HTTPException(status_code=503, detail="دیتابیس این فروشگاه در دسترس نیست.")

    tenant_db = Database(resolved_path)
    try:
        tenant_db.get_all_settings()
    except sqlite3.OperationalError:
        _tenant_logger.exception(
            "تننت b=%s: خواندن settings از %s ناموفق بود (جدول‌ها ساخته نشده؟).", b, resolved_path
        )
        raise HTTPException(status_code=503, detail="دیتابیس این فروشگاه هنوز آماده نیست.")

    _tenant_logger.info(
        "تننت b=%s resolve شد -> bot_username=%s token=...%s db_path=%s",
        b, row["bot_username"], row["bot_token"][-6:], resolved_path,
    )
    return Tenant(db=tenant_db, bot_token=row["bot_token"], tenant_id=b)


def get_verified_user(x_init_data: str = Header(...), tenant: Tenant = Depends(get_tenant)):
    """initData را با توکن همان مستأجر تایید می‌کند. خروجی: (tg_id, db, tenant)"""
    result = validate_init_data(x_init_data, tenant.bot_token)
    if not result or "user" not in result:
        raise HTTPException(status_code=401, detail="initData نامعتبر است.")
    return result["user"]["id"], tenant.db, tenant


def require_admin(auth=Depends(get_verified_user)):
    """مثل get_verified_user، ولی فقط اگر کاربر ادمین همان مستأجر باشد اجازه می‌دهد."""
    tg_id, db, tenant = auth
    if not db.is_admin(tg_id):
        raise HTTPException(status_code=403, detail="دسترسی ادمین لازم است.")
    return auth


def require_main_admin(auth=Depends(get_verified_user)):
    """مثل require_admin، ولی فقط برای بات اصلی مجاز است (نه بات‌های نمایندگی)."""
    tg_id, db, tenant = auth
    if tenant.tenant_id:
        raise HTTPException(status_code=403, detail="این بخش فقط در بات اصلی در دسترس است.")
    if not db.is_admin(tg_id):
        raise HTTPException(status_code=403, detail="دسترسی ادمین لازم است.")
    return auth


async def get_bot_username(tenant: Tenant) -> str:
    """یوزرنیم همان بات (برای ساخت لینک دعوت زیرمجموعه‌گیری) را می‌گیرد و کش می‌کند."""
    cached = _bot_username_cache.get(tenant.bot_token)
    if cached:
        return cached
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://api.telegram.org/bot{tenant.bot_token}/getMe") as resp:
                data = await resp.json()
                if data.get("ok"):
                    _bot_username_cache[tenant.bot_token] = data["result"]["username"]
    except Exception:
        pass
    return _bot_username_cache.get(tenant.bot_token, "")


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
    return HTMLResponse(html)


# ---------------------------------------------------------------------------
# حساب کاربری
# ---------------------------------------------------------------------------

@app.get("/api/me")
def api_me(auth=Depends(get_verified_user)):
    tg_id, db, _ = auth
    user = db.get_user(tg_id)
    if not user:
        raise HTTPException(status_code=404, detail="کاربر یافت نشد. ابتدا /start را در بات بزنید.")
    wallet = db.get_wallet_credit(tg_id)
    referral = db.get_referral_stats(tg_id)
    orders = db.get_user_orders(tg_id)
    return {
        "telegram_id": tg_id,
        "first_name": user["first_name"],
        "wallet_credit": wallet,
        "referral_count": referral["count"],
        "orders_count": len(orders),
        "is_admin": db.is_admin(tg_id),
    }


@app.get("/api/orders")
def api_orders(auth=Depends(get_verified_user)):
    tg_id, db, _ = auth
    orders = db.get_user_orders(tg_id)
    result = []
    for o in orders:
        product = db.get_product(o["product_id"])
        cfg = db.get_config_by_id(o["config_id"]) if o["config_id"] else None
        result.append({
            "id": o["id"],
            "product_name": product["name"] if product else "نامشخص",
            "status": o["status"],
            "final_price": o["final_price"],
            "expires_at": cfg["expires_at"] if cfg else None,
            "link": cfg["link"] if cfg else None,
        })
    return result


@app.get("/api/catalog")
def api_catalog(auth=Depends(get_verified_user)):
    tg_id, db, _ = auth
    categories = db.get_categories(active_only=True)
    result = []
    for c in categories:
        products = db.get_products(c["id"], active_only=True)
        result.append({
            "id": c["id"],
            "name": c["name"],
            "products": [
                {
                    "id": p["id"],
                    "name": p["name"],
                    "price": p["price"],
                    "description": p["description"],
                    "stock": db.count_available_configs(p["id"]),
                }
                for p in products
            ],
        })
    return result


# ---------------------------------------------------------------------------
# کانفیگ تست
# ---------------------------------------------------------------------------

@app.get("/api/test-config")
def api_test_config_status(auth=Depends(get_verified_user)):
    tg_id, db, _ = auth
    user = db.get_user(tg_id)
    used = bool(user and user["test_used"] >= MAX_TEST_PER_USER)
    link = None
    if used:
        row = db.get_assigned_test_config(tg_id)
        link = row["link"] if row else None
    return {
        "enabled": db.get_setting("test_enabled", "1") == "1",
        "used": used,
        "available": db.count_available_test_configs(),
        "link": link,
    }


@app.post("/api/test-config/claim")
def api_test_config_claim(auth=Depends(get_verified_user)):
    tg_id, db, _ = auth
    if db.get_setting("test_enabled", "1") != "1":
        raise HTTPException(status_code=400, detail="در حال حاضر امکان دریافت کانفیگ تست غیرفعال است.")
    user = db.get_user(tg_id)
    if user and user["test_used"] >= MAX_TEST_PER_USER:
        raise HTTPException(status_code=400, detail="شما قبلاً کانفیگ تست خود را دریافت کرده‌اید.")
    result = db.take_unused_test_config(tg_id)
    if not result:
        raise HTTPException(status_code=400, detail="متاسفانه موجودی کانفیگ تست تمام شده است.")
    db.mark_test_used(tg_id)
    return {"link": result["link"]}


# ---------------------------------------------------------------------------
# زیرمجموعه‌گیری
# ---------------------------------------------------------------------------

@app.get("/api/referral")
async def api_referral(auth=Depends(get_verified_user)):
    tg_id, db, tenant = auth
    if db.get_setting("referral_enabled", "1") != "1":
        return {"enabled": False}
    username = await get_bot_username(tenant)
    ref_start = f"ref{tg_id}"
    link = f"https://t.me/{username}?start={ref_start}" if username else None
    stats = db.get_referral_stats(tg_id)
    return {
        "enabled": True,
        "link": link,
        "count": stats["count"],
        "credit": stats["credit"],
        "percent": db.get_setting("referral_percent", "10"),
    }


# ---------------------------------------------------------------------------
# هشدار انقضا
# ---------------------------------------------------------------------------

@app.get("/api/expiring")
def api_expiring(auth=Depends(get_verified_user)):
    tg_id, db, _ = auth
    rows = db.get_expiring_configs_for_user(tg_id)
    result = []
    for r in rows:
        product = db.get_product(r["product_id"])
        result.append({
            "product_name": product["name"] if product else "نامشخص",
            "expires_at": r["expires_at"],
            "link": r["link"],
        })
    return result


# ---------------------------------------------------------------------------
# چت پشتیبانی
# ---------------------------------------------------------------------------

@app.get("/api/support/messages")
def api_support_messages(since_id: int = 0, auth=Depends(get_verified_user)):
    tg_id, db, _ = auth
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
    tg_id, db, tenant = auth
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
    admin_ids = db.list_admins()
    reply_markup = {
        "inline_keyboard": [[{"text": "↩️ پاسخ", "callback_data": f"reply_user:{tg_id}"}]]
    }
    async with aiohttp.ClientSession() as session:
        for admin_id in admin_ids:
            try:
                await session.post(
                    f"https://api.telegram.org/bot{tenant.bot_token}/sendMessage",
                    json={
                        "chat_id": admin_id, "text": caption,
                        "parse_mode": "Markdown", "reply_markup": reply_markup,
                    },
                )
            except Exception:
                pass

    return {"id": msg_id, "sender": "user", "message": text}


async def send_photo_to_admins(db: Database, bot_token: str, caption: str, reply_markup: str,
                                photo_bytes: bytes, filename: str, content_type: str):
    """رسید را برای همه‌ی ادمین‌های همین مستأجر ارسال می‌کند. (file_id, تعداد تحویل موفق، نتایج) را برمی‌گرداند."""
    admin_ids = db.list_admins()
    sent_file_id = None
    delivered = 0
    results = []
    async with aiohttp.ClientSession() as session:
        for admin_id in admin_ids:
            form = aiohttp.FormData()
            form.add_field("chat_id", str(admin_id))
            form.add_field("caption", caption)
            form.add_field("reply_markup", reply_markup)
            form.add_field("photo", photo_bytes, filename=filename, content_type=content_type)
            try:
                async with session.post(
                    f"https://api.telegram.org/bot{bot_token}/sendPhoto", data=form
                ) as resp:
                    data = await resp.json()
                    if data.get("ok"):
                        delivered += 1
                        msg = data["result"]
                        results.append((admin_id, msg["message_id"]))
                        if not sent_file_id:
                            sent_file_id = msg["photo"][-1]["file_id"]
            except Exception:
                pass
    return sent_file_id, delivered, results


# ---------------------------------------------------------------------------
# سفارش‌ها
# ---------------------------------------------------------------------------

class OrderCreate(BaseModel):
    product_id: int
    discount_code: Optional[str] = None


@app.post("/api/orders")
def api_create_order(body: OrderCreate, auth=Depends(get_verified_user)):
    tg_id, db, _ = auth
    product = db.get_product(body.product_id)
    if not product or db.count_available_configs(body.product_id) <= 0:
        raise HTTPException(status_code=400, detail="این محصول موجود نیست.")

    discount_code_id = None
    discount_amount = 0
    if body.discount_code:
        code_row = db.get_discount_code(body.discount_code)
        if not db.is_discount_code_valid(code_row):
            raise HTTPException(status_code=400, detail="کد تخفیف نامعتبر است.")
        discount_amount = db.compute_discount_amount(code_row, product["price"])
        discount_code_id = code_row["id"]

    wallet_credit = db.get_wallet_credit(tg_id)
    price_after_code = max(product["price"] - discount_amount, 0)
    wallet_used = min(wallet_credit, price_after_code)

    if wallet_used > 0:
        db.add_wallet_credit(tg_id, -wallet_used)
    if discount_code_id:
        db.increment_discount_usage(discount_code_id)

    order_id = db.create_order(
        tg_id, body.product_id, base_price=product["price"],
        wallet_used=wallet_used, discount_code_id=discount_code_id, discount_amount=discount_amount,
    )
    order = db.get_order(order_id)

    if order["final_price"] <= 0:
        result = db.take_unused_config(body.product_id, tg_id)
        if not result:
            db.reject_order(order_id)
            raise HTTPException(status_code=409, detail="موجودی هم‌زمان تمام شد؛ مبلغ بازگردانده شد.")
        db.approve_order(order_id, result["id"])
        db.reward_referrer_if_first_purchase(tg_id, order["final_price"] or product["price"])
        order = db.get_order(order_id)
        cfg = db.get_config_by_id(order["config_id"])
        return {"status": "approved", "order_id": order_id, "link": cfg["link"], "expires_at": cfg["expires_at"]}

    # مبلغی باقی مانده - کاربر باید مثل قبل از طریق بات رسید کارت‌به‌کارت بفرستد
    return {
        "status": "pending_payment", "order_id": order_id, "final_price": order["final_price"],
        "card_number": db.get_setting("card_number"), "card_holder": db.get_setting("card_holder"),
    }


# ---------------------------------------------------------------------------
# گردونه‌ی شانس
# ---------------------------------------------------------------------------

@app.get("/api/wheel")
def api_wheel_status(auth=Depends(get_verified_user)):
    tg_id, db, _ = auth
    settings = db.get_wheel_settings()
    can_spin, remaining_hours = db.can_spin_wheel(tg_id)
    return {
        "enabled": settings["enabled"], "can_spin": can_spin,
        "remaining_hours": round(remaining_hours, 1) if remaining_hours else 0,
        "prizes": settings["prizes"],
    }


@app.post("/api/wheel/spin")
def api_wheel_spin(auth=Depends(get_verified_user)):
    tg_id, db, _ = auth
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
def api_topup_request(body: TopupCreate, auth=Depends(get_verified_user)):
    tg_id, db, _ = auth
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
    x_init_data: str = Header(...),
    tenant: Tenant = Depends(get_tenant),
):
    tg_id, db, tenant = get_verified_user(x_init_data, tenant)
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

    sent_file_id, delivered, results = await send_photo_to_admins(
        db, tenant.bot_token, caption, reply_markup, photo_bytes, photo.filename or "receipt.jpg", photo.content_type
    )
    if delivered == 0:
        raise HTTPException(status_code=502, detail="ارسال رسید به ادمین ناموفق بود. دوباره تلاش کنید.")

    for admin_id, message_id in results:
        db.set_topup_admin_message(topup_id, admin_id, message_id)
    if sent_file_id:
        db.set_topup_receipt(topup_id, sent_file_id)

    return {"status": "sent"}


@app.post("/api/orders/{order_id}/receipt")
async def api_order_receipt(
    order_id: int,
    photo: UploadFile = File(...),
    x_init_data: str = Header(...),
    tenant: Tenant = Depends(get_tenant),
):
    tg_id, db, tenant = get_verified_user(x_init_data, tenant)
    order = db.get_order(order_id)
    if not order or order["user_id"] != tg_id:
        raise HTTPException(status_code=404, detail="سفارش یافت نشد.")
    if order["status"] != "pending":
        raise HTTPException(status_code=400, detail="این سفارش قبلاً بررسی شده است.")
    if not photo.content_type or not photo.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="فقط عکس رسید پذیرفته می‌شود.")

    photo_bytes = await photo.read()
    if len(photo_bytes) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="حجم عکس بیش از حد مجاز است.")

    product = db.get_product(order["product_id"])
    user = db.get_user(tg_id)
    caption = (
        f"🧾 سفارش #{order_id}\n"
        f"👤 کاربر: {(user['first_name'] if user else '') or ''} (@{(user['username'] if user else '') or '---'})\n"
        f"🆔 آیدی عددی: {tg_id}\n"
        f"📦 محصول: {product['name'] if product else '---'}\n"
        f"💰 قیمت پایه: {order['base_price']:,} تومان\n"
    )
    if order["discount_amount"]:
        caption += f"🎟 تخفیف کد: {order['discount_amount']:,} تومان\n"
    if order["wallet_used"]:
        caption += f"👛 استفاده از کیف پول: {order['wallet_used']:,} تومان\n"
    caption += f"💵 مبلغ قابل پرداخت: {order['final_price']:,} تومان"

    reply_markup = json.dumps({
        "inline_keyboard": [[
            {"text": "✅ تایید و ارسال کانفیگ", "callback_data": f"order_approve:{order_id}"},
            {"text": "❌ رد کردن", "callback_data": f"order_reject:{order_id}"},
        ]]
    })

    admin_ids = db.list_admins()
    if not admin_ids:
        raise HTTPException(status_code=500, detail="هیچ ادمینی برای بررسی رسید ثبت نشده است.")

    sent_file_id, delivered, results = await send_photo_to_admins(
        db, tenant.bot_token, caption, reply_markup, photo_bytes, photo.filename or "receipt.jpg", photo.content_type
    )
    if delivered == 0:
        raise HTTPException(status_code=502, detail="ارسال رسید به ادمین ناموفق بود. دوباره تلاش کنید.")

    for admin_id, message_id in results:
        db.set_order_admin_message(order_id, admin_id, message_id)
    if sent_file_id:
        db.set_order_receipt(order_id, sent_file_id)

    return {"status": "sent"}


# ---------------------------------------------------------------------------
# مدیریت (فقط ادمین) - چیدمان دکمه‌های منوی اصلی
# ---------------------------------------------------------------------------

class MenuButtonUpdate(BaseModel):
    key: str
    text: Optional[str] = None
    style: Optional[str] = None
    enabled: Optional[bool] = None


class MenuLayoutUpdate(BaseModel):
    order: list[str]
    buttons: list[MenuButtonUpdate]


@app.get("/api/admin/check")
def api_admin_check(auth=Depends(get_verified_user)):
    tg_id, db, _ = auth
    return {"is_admin": db.is_admin(tg_id)}


@app.get("/api/admin/menu")
def api_admin_get_menu(auth=Depends(require_admin)):
    _, db, _ = auth
    settings = db.get_all_settings()
    order = db.get_menu_order()
    result = []
    for key in order:
        meta = MENU_BUTTON_META.get(key)
        if not meta:
            continue
        item = {
            "key": key,
            "label": meta["label"],
            "admin_only": meta["admin_only"],
            "has_text": meta["has_text"],
            "has_style": meta["has_style"],
            "togglable": meta["toggle_key"] is not None,
        }
        if meta["has_text"]:
            item["text"] = settings.get(key, "")
        if meta["has_style"]:
            item["style"] = settings.get(f"{key}_style", "")
        if meta["toggle_key"]:
            item["enabled"] = settings.get(meta["toggle_key"], "1") == "1"
        result.append(item)
    return result


@app.post("/api/admin/menu")
def api_admin_save_menu(body: MenuLayoutUpdate, auth=Depends(require_admin)):
    _, db, _ = auth
    for btn in body.buttons:
        meta = MENU_BUTTON_META.get(btn.key)
        if not meta:
            continue
        if meta["has_text"] and btn.text is not None and btn.text.strip():
            db.set_setting(btn.key, btn.text.strip())
        if meta["has_style"] and btn.style is not None:
            style = btn.style if btn.style in ("primary", "success", "danger") else ""
            db.set_setting(f"{btn.key}_style", style)
        if meta["toggle_key"] and btn.enabled is not None:
            db.set_setting(meta["toggle_key"], "1" if btn.enabled else "0")
    db.set_menu_order(body.order)
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# مدیریت (فقط ادمین) - دسته‌بندی‌ها و محصولات
# ---------------------------------------------------------------------------

class CategoryCreate(BaseModel):
    name: str


class CategoryUpdate(BaseModel):
    name: str


class ProductCreate(BaseModel):
    category_id: int
    name: str
    price: int
    description: str = ""
    duration_days: int = 30


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    price: Optional[int] = None
    description: Optional[str] = None
    duration_days: Optional[int] = None


class ConfigsAdd(BaseModel):
    links: list[str]


@app.get("/api/admin/categories")
def api_admin_list_categories(auth=Depends(require_admin)):
    _, db, _ = auth
    cats = db.get_categories(active_only=False)
    result = []
    for c in cats:
        products = db.get_products(c["id"], active_only=False)
        result.append({
            "id": c["id"], "name": c["name"], "is_active": bool(c["is_active"]),
            "product_count": len(products),
        })
    return result


@app.post("/api/admin/categories")
def api_admin_create_category(body: CategoryCreate, auth=Depends(require_admin)):
    _, db, _ = auth
    if not body.name.strip():
        raise HTTPException(status_code=400, detail="نام دسته‌بندی نمی‌تواند خالی باشد.")
    cat_id = db.add_category(body.name.strip())
    return {"id": cat_id}


@app.patch("/api/admin/categories/{cat_id}")
def api_admin_edit_category(cat_id: int, body: CategoryUpdate, auth=Depends(require_admin)):
    _, db, _ = auth
    if not db.get_category(cat_id):
        raise HTTPException(status_code=404, detail="دسته‌بندی یافت نشد.")
    if not body.name.strip():
        raise HTTPException(status_code=400, detail="نام دسته‌بندی نمی‌تواند خالی باشد.")
    db.edit_category(cat_id, body.name.strip())
    return {"status": "ok"}


@app.post("/api/admin/categories/{cat_id}/toggle")
def api_admin_toggle_category(cat_id: int, auth=Depends(require_admin)):
    _, db, _ = auth
    if not db.get_category(cat_id):
        raise HTTPException(status_code=404, detail="دسته‌بندی یافت نشد.")
    db.toggle_category(cat_id)
    return {"status": "ok"}


@app.delete("/api/admin/categories/{cat_id}")
def api_admin_delete_category(cat_id: int, auth=Depends(require_admin)):
    _, db, _ = auth
    if not db.get_category(cat_id):
        raise HTTPException(status_code=404, detail="دسته‌بندی یافت نشد.")
    db.delete_category(cat_id)
    return {"status": "ok"}


@app.get("/api/admin/categories/{cat_id}/products")
def api_admin_list_products(cat_id: int, auth=Depends(require_admin)):
    _, db, _ = auth
    products = db.get_products(cat_id, active_only=False)
    return [
        {
            "id": p["id"], "name": p["name"], "price": p["price"],
            "description": p["description"], "duration_days": p["duration_days"],
            "is_active": bool(p["is_active"]), "stock": db.count_available_configs(p["id"]),
        }
        for p in products
    ]


@app.post("/api/admin/products")
def api_admin_create_product(body: ProductCreate, auth=Depends(require_admin)):
    _, db, _ = auth
    if not db.get_category(body.category_id):
        raise HTTPException(status_code=404, detail="دسته‌بندی یافت نشد.")
    if not body.name.strip():
        raise HTTPException(status_code=400, detail="نام محصول نمی‌تواند خالی باشد.")
    if body.price < 0:
        raise HTTPException(status_code=400, detail="قیمت نامعتبر است.")
    product_id = db.add_product(body.category_id, body.name.strip(), body.price, body.description, body.duration_days)
    return {"id": product_id}


@app.patch("/api/admin/products/{product_id}")
def api_admin_edit_product(product_id: int, body: ProductUpdate, auth=Depends(require_admin)):
    _, db, _ = auth
    if not db.get_product(product_id):
        raise HTTPException(status_code=404, detail="محصول یافت نشد.")
    if body.price is not None and body.price < 0:
        raise HTTPException(status_code=400, detail="قیمت نامعتبر است.")
    db.edit_product(
        product_id,
        name=body.name.strip() if body.name else None,
        price=body.price,
        description=body.description,
        duration_days=body.duration_days,
    )
    return {"status": "ok"}


@app.post("/api/admin/products/{product_id}/toggle")
def api_admin_toggle_product(product_id: int, auth=Depends(require_admin)):
    _, db, _ = auth
    if not db.get_product(product_id):
        raise HTTPException(status_code=404, detail="محصول یافت نشد.")
    db.toggle_product(product_id)
    return {"status": "ok"}


@app.delete("/api/admin/products/{product_id}")
def api_admin_delete_product(product_id: int, auth=Depends(require_admin)):
    _, db, _ = auth
    if not db.get_product(product_id):
        raise HTTPException(status_code=404, detail="محصول یافت نشد.")
    db.delete_product(product_id)
    return {"status": "ok"}


@app.get("/api/admin/products/{product_id}/configs")
def api_admin_list_configs(product_id: int, auth=Depends(require_admin)):
    _, db, _ = auth
    if not db.get_product(product_id):
        raise HTTPException(status_code=404, detail="محصول یافت نشد.")
    rows = db.get_unused_configs(product_id)
    return [{"id": r["id"], "link": r["link"]} for r in rows]


@app.post("/api/admin/products/{product_id}/configs")
def api_admin_add_configs(product_id: int, body: ConfigsAdd, auth=Depends(require_admin)):
    _, db, _ = auth
    if not db.get_product(product_id):
        raise HTTPException(status_code=404, detail="محصول یافت نشد.")
    links = [l.strip() for l in body.links if l.strip()]
    if not links:
        raise HTTPException(status_code=400, detail="هیچ لینک معتبری وارد نشده است.")
    db.add_configs(product_id, links)
    return {"added": len(links)}


@app.delete("/api/admin/configs/{config_id}")
def api_admin_delete_config(config_id: int, auth=Depends(require_admin)):
    _, db, _ = auth
    db.delete_config(config_id)
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# مدیریت نمایندگی‌ها (فقط بات اصلی)
# ---------------------------------------------------------------------------

class ResellerTokenCheck(BaseModel):
    token: str


class ResellerCreate(BaseModel):
    token: str
    username: str
    owner_telegram_id: int
    owner_name: str = ""


class ResellerUpdate(BaseModel):
    owner_telegram_id: Optional[int] = None
    owner_name: Optional[str] = None


@app.get("/api/admin/resellers")
def api_admin_list_resellers(auth=Depends(require_main_admin)):
    _, db, _ = auth
    rows = db.list_reseller_bots()
    return [
        {
            "id": r["id"], "bot_username": r["bot_username"], "owner_telegram_id": r["owner_telegram_id"],
            "owner_name": r["owner_name"], "is_active": bool(r["is_active"]), "created_at": r["created_at"],
        }
        for r in rows
    ]


@app.post("/api/admin/resellers/validate")
async def api_admin_validate_reseller_token(body: ResellerTokenCheck, auth=Depends(require_main_admin)):
    _, db, _ = auth
    token = body.token.strip()
    if not token:
        raise HTTPException(status_code=400, detail="توکن نمی‌تواند خالی باشد.")
    for r in db.list_reseller_bots():
        if r["bot_token"] == token:
            raise HTTPException(status_code=400, detail="این توکن قبلاً ثبت شده است.")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://api.telegram.org/bot{token}/getMe", timeout=10) as resp:
                data = await resp.json()
                if not data.get("ok"):
                    raise HTTPException(status_code=400, detail="این توکن معتبر نیست.")
                username = data["result"]["username"]
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=400, detail="این توکن معتبر نیست یا تلگرام در دسترس نیست.")
    return {"username": username}


@app.post("/api/admin/resellers")
def api_admin_create_reseller(body: ResellerCreate, auth=Depends(require_main_admin)):
    _, db, _ = auth
    for r in db.list_reseller_bots():
        if r["bot_token"] == body.token:
            raise HTTPException(status_code=400, detail="این توکن قبلاً ثبت شده است.")
    os.makedirs(RESELLER_DBS_DIR, exist_ok=True)
    db_path = os.path.join(RESELLER_DBS_DIR, f"{body.username}.db")
    reseller_id = db.register_reseller_bot(body.token, body.username, body.owner_telegram_id, body.owner_name, db_path)

    # دیتابیس همین نماینده باید بداند شناسه‌ی خودش را تا لینک مینی‌اپ اختصاصی بسازد
    try:
        reseller_db = Database(db_path)
        reseller_db.init_db(owner_id=body.owner_telegram_id)
        reseller_db.set_setting("miniapp_tenant_id", str(reseller_id))
    except Exception:
        logging.getLogger("miniapp.resellers").exception("مقداردهی اولیه دیتابیس نماینده‌ی جدید ناموفق بود.")

    return {
        "id": reseller_id,
        "note": "بات نمایندگی ثبت شد. حداکثر تا ۱۰ ثانیه دیگر توسط بات اصلی خودکار روشن می‌شود.",
    }


@app.patch("/api/admin/resellers/{reseller_id}")
def api_admin_edit_reseller(reseller_id: int, body: ResellerUpdate, auth=Depends(require_main_admin)):
    _, db, _ = auth
    if not db.get_reseller_bot(reseller_id):
        raise HTTPException(status_code=404, detail="نماینده یافت نشد.")
    db.edit_reseller_bot(
        reseller_id,
        owner_telegram_id=body.owner_telegram_id,
        owner_name=body.owner_name.strip() if body.owner_name else None,
    )
    return {"status": "ok"}


@app.post("/api/admin/resellers/{reseller_id}/toggle")
def api_admin_toggle_reseller(reseller_id: int, auth=Depends(require_main_admin)):
    _, db, _ = auth
    if not db.get_reseller_bot(reseller_id):
        raise HTTPException(status_code=404, detail="نماینده یافت نشد.")
    db.toggle_reseller_bot(reseller_id)
    return {"status": "ok", "note": "تغییر وضعیت حداکثر تا ۱۰ ثانیه دیگر روی بات اعمال می‌شود."}


@app.delete("/api/admin/resellers/{reseller_id}")
def api_admin_delete_reseller(reseller_id: int, purge_db: bool = Query(False), auth=Depends(require_main_admin)):
    _, db, _ = auth
    reseller_bot = db.get_reseller_bot(reseller_id)
    if not reseller_bot:
        raise HTTPException(status_code=404, detail="نماینده یافت نشد.")
    db.delete_reseller_bot(reseller_id)

    file_removed = False
    if purge_db:
        resolved_path = resolve_db_path(reseller_bot["db_path"])
        try:
            if os.path.exists(resolved_path):
                os.remove(resolved_path)
                file_removed = True
        except OSError:
            logging.getLogger("miniapp.resellers").exception("حذف فایل دیتابیس نماینده ناموفق بود: %s", resolved_path)

    return {
        "status": "ok",
        "db_purged": file_removed,
        "note": "بات نماینده حداکثر تا ۱۰ ثانیه دیگر متوقف می‌شود.",
    }


app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
