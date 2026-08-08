# -*- coding: utf-8 -*-
"""
بک‌اند مینی‌اپ (فقط بخش کاربر، فقط برای بات اصلی در این فاز).

اجرا (جدا از پروسه‌ی اصلی بات): uvicorn miniapp.server:app --host 127.0.0.1 --port 8001
سپس nginx مسیر /miniapp/ را به این پورت و فایل‌های استاتیک را proxy می‌کند.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, Header, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

from config import BOT_TOKEN, DB_PATH
from database import Database
from miniapp.auth import validate_init_data

app = FastAPI(title="V2Ray Shop Mini App API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

db = Database(DB_PATH)


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
            "expires_at": o["expires_at"],
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
        return {"status": "approved", "order_id": order_id, "link": cfg["link"], "expires_at": order["expires_at"]}

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
        "note": "رسید پرداخت را در خود بات (نه اینجا) برای ادمین ارسال کنید تا تایید شود.",
    }


app.mount("/", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static"), html=True), name="static")
