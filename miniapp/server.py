# -*- coding: utf-8 -*-
"""
بک‌اند مینی‌اپ (فقط بخش کاربر، فقط برای بات اصلی در این فاز).

اجرا (جدا از پروسه‌ی اصلی بات): uvicorn miniapp.server:app --host 127.0.0.1 --port 8001
سپس nginx مسیر /miniapp/ را به این پورت و فایل‌های استاتیک را proxy می‌کند.
"""

import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import aiohttp
from fastapi import FastAPI, Header, HTTPException, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

from config import BOT_TOKEN, DB_PATH, MAX_TEST_PER_USER
from database import Database
from miniapp.auth import validate_init_data

app = FastAPI(title="V2Ray Shop Mini App API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

db = Database(DB_PATH)

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")

_bot_username_cache: Optional[str] = None


async def get_bot_username() -> str:
    """یوزرنیم بات را (برای ساخت لینک دعوت زیرمجموعه‌گیری) از تلگرام می‌گیرد و کش می‌کند."""
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


def get_verified_user(x_init_data: str = Header(...)) -> int:
    result = validate_init_data(x_init_data, BOT_TOKEN)
    if not result or "user" not in result:
        raise HTTPException(status_code=401, detail="initData نامعتبر است.")
    return result["user"]["id"]


@app.get("/api/me")
def api_me(user_id: int = Header(None), x_init_data: str = Header(...)):
    tg_id = get_verified_user(x_init_data)
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
    }


@app.get("/api/orders")
def api_orders(x_init_data: str = Header(...)):
    tg_id = get_verified_user(x_init_data)
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
def api_catalog(x_init_data: str = Header(...)):
    get_verified_user(x_init_data)  # فقط برای احراز هویت؛ کاتالوگ برای همه یکسان است
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


@app.get("/api/test-config")
def api_test_config_status(x_init_data: str = Header(...)):
    tg_id = get_verified_user(x_init_data)
    user = db.get_user(tg_id)
    return {
        "enabled": db.get_setting("test_enabled", "1") == "1",
        "used": bool(user and user["test_used"] >= MAX_TEST_PER_USER),
        "available": db.count_available_test_configs(),
    }


@app.post("/api/test-config/claim")
def api_test_config_claim(x_init_data: str = Header(...)):
    tg_id = get_verified_user(x_init_data)
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


@app.get("/api/referral")
async def api_referral(x_init_data: str = Header(...)):
    tg_id = get_verified_user(x_init_data)
    if db.get_setting("referral_enabled", "1") != "1":
        return {"enabled": False}
    username = await get_bot_username()
    link = f"https://t.me/{username}?start=ref{tg_id}" if username else None
    stats = db.get_referral_stats(tg_id)
    return {
        "enabled": True,
        "link": link,
        "count": stats["count"],
        "credit": stats["credit"],
        "percent": db.get_setting("referral_percent", "10"),
    }


@app.get("/api/expiring")
def api_expiring(x_init_data: str = Header(...)):
    tg_id = get_verified_user(x_init_data)
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


@app.get("/api/support/messages")
def api_support_messages(since_id: int = 0, x_init_data: str = Header(...)):
    tg_id = get_verified_user(x_init_data)
    db.mark_support_read_by_user(tg_id)
    rows = db.get_support_messages(tg_id, since_id=since_id)
    return [
        {"id": m["id"], "sender": m["sender"], "message": m["message"], "created_at": m["created_at"]}
        for m in rows
    ]


class SupportMessageCreate(BaseModel):
    message: str


@app.post("/api/support/messages")
async def api_support_send(body: SupportMessageCreate, x_init_data: str = Header(...)):
    tg_id = get_verified_user(x_init_data)
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
    reply_markup = json.dumps({
        "inline_keyboard": [[{"text": "↩️ پاسخ", "callback_data": f"reply_user:{tg_id}"}]]
    })
    async with aiohttp.ClientSession() as session:
        for admin_id in admin_ids:
            try:
                await session.post(
                    f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                    json={
                        "chat_id": admin_id, "text": caption,
                        "parse_mode": "Markdown", "reply_markup": json.loads(reply_markup),
                    },
                )
            except Exception:
                pass

    return {"id": msg_id, "sender": "user", "message": text}


async def send_photo_to_admins(caption: str, reply_markup: str, photo_bytes: bytes, filename: str, content_type: str):
    """رسید را برای همه‌ی ادمین‌ها ارسال می‌کند. (file_id, تعداد تحویل موفق) را برمی‌گرداند."""
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
                    f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto", data=form
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


class OrderCreate(BaseModel):
    product_id: int
    discount_code: Optional[str] = None


@app.post("/api/orders")
def api_create_order(body: OrderCreate, x_init_data: str = Header(...)):
    tg_id = get_verified_user(x_init_data)
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


@app.get("/api/wheel")
def api_wheel_status(x_init_data: str = Header(...)):
    tg_id = get_verified_user(x_init_data)
    settings = db.get_wheel_settings()
    can_spin, remaining_hours = db.can_spin_wheel(tg_id)
    return {
        "enabled": settings["enabled"], "can_spin": can_spin,
        "remaining_hours": round(remaining_hours, 1) if remaining_hours else 0,
        "prizes": settings["prizes"],
    }


@app.post("/api/wheel/spin")
def api_wheel_spin(x_init_data: str = Header(...)):
    import random
    tg_id = get_verified_user(x_init_data)
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


class TopupCreate(BaseModel):
    amount: int


@app.post("/api/wallet/topup-request")
def api_topup_request(body: TopupCreate, x_init_data: str = Header(...)):
    tg_id = get_verified_user(x_init_data)
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
):
    tg_id = get_verified_user(x_init_data)
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
        caption, reply_markup, photo_bytes, photo.filename or "receipt.jpg", photo.content_type
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
):
    tg_id = get_verified_user(x_init_data)
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
        caption, reply_markup, photo_bytes, photo.filename or "receipt.jpg", photo.content_type
    )
    if delivered == 0:
        raise HTTPException(status_code=502, detail="ارسال رسید به ادمین ناموفق بود. دوباره تلاش کنید.")

    for admin_id, message_id in results:
        db.set_order_admin_message(order_id, admin_id, message_id)
    if sent_file_id:
        db.set_order_receipt(order_id, sent_file_id)

    return {"status": "sent"}


app.mount("/", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static"), html=True), name="static")
