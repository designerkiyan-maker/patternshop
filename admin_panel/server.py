# -*- coding: utf-8 -*-
"""
پنل مدیریت وب کاملاً مستقل ShopVPN - خارج از تلگرام.

لاگین با یوزرنیم/پسورد (نه initData). روی دیتابیس بات اصلی کار می‌کند.
اجرا: uvicorn admin_panel.server:app --host 127.0.0.1 --port 8002
اولین حساب (owner) را با دستور زیر بساز:
    python -m admin_panel.create_admin <username> <password>
"""

import asyncio
import os
from typing import Optional

from fastapi import FastAPI, Request, Response, Depends, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from config import DB_PATH, BOT_TOKEN, OWNER_ID, ADMIN_PANEL_SECRET
from database import Database
from admin_panel.security import hash_password, verify_password, create_session_token, verify_session_token
from admin_panel.telegram_notify import send_message as tg_send
from reseller_auto_provision import provision_auto_config, ProvisionError
from stock_alerts import check_and_notify_low_stock
from panel_providers import get_provider, PanelError, PANEL_TYPE_LABELS

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
COOKIE_NAME = "panel_session"

app = FastAPI(title="ShopVPN Admin Panel")
db = Database(DB_PATH)
db.init_db(owner_id=OWNER_ID)

# ------------------------------------------------------------------ auth --


class LoginBody(BaseModel):
    username: str
    password: str


def get_current_admin(request: Request):
    token = request.cookies.get(COOKIE_NAME)
    payload = verify_session_token(ADMIN_PANEL_SECRET, token) if token else None
    if not payload:
        raise HTTPException(401, "نشست منقضی شده یا نامعتبر است.")
    admin = db.get_web_admin(payload["id"])
    if not admin or not admin["is_active"]:
        raise HTTPException(401, "حساب کاربری غیرفعال یا حذف شده است.")
    return {"id": admin["id"], "username": admin["username"], "role": admin["role"]}


def require_full(admin=Depends(get_current_admin)):
    if not db.is_full_web_admin(admin["role"]):
        raise HTTPException(403, "دسترسی کافی نیست.")
    return admin


def require_senior(admin=Depends(get_current_admin)):
    if not db.is_senior_web_admin(admin["role"]):
        raise HTTPException(403, "این بخش فقط برای مالک/مدیر کامل است.")
    return admin


def require_owner(admin=Depends(get_current_admin)):
    if admin["role"] != "owner":
        raise HTTPException(403, "این بخش فقط برای مالک است.")
    return admin


@app.post("/api/login")
def api_login(body: LoginBody, response: Response):
    admin = db.get_web_admin_by_username(body.username)
    if not admin or not admin["is_active"] or not verify_password(body.password, admin["password_hash"]):
        raise HTTPException(401, "یوزرنیم یا پسورد اشتباه است.")
    token = create_session_token(ADMIN_PANEL_SECRET, admin["id"], admin["username"], admin["role"])
    db.touch_web_admin_login(admin["id"])
    response.set_cookie(
        COOKIE_NAME, token, httponly=True, samesite="lax", max_age=12 * 3600, path="/",
    )
    return {"id": admin["id"], "username": admin["username"], "role": admin["role"]}


@app.post("/api/logout")
def api_logout(response: Response):
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"ok": True}


@app.get("/api/me")
def api_me(admin=Depends(get_current_admin)):
    return admin


# --------------------------------------------------------------- helpers --


def row_to_dict(row):
    return dict(row) if row is not None else None


def rows_to_list(rows):
    return [dict(r) for r in rows]


async def notify_user(chat_id: int, text: str):
    asyncio.create_task(tg_send(BOT_TOKEN, chat_id, text))


# --------------------------------------------------------------- dashboard --


@app.get("/api/dashboard")
def api_dashboard(start: Optional[str] = None, end: Optional[str] = None, admin=Depends(get_current_admin)):
    return db.get_sales_stats(start, end)


# ------------------------------------------------------------------ orders --


@app.get("/api/orders")
def api_orders(status: str = "pending", admin=Depends(get_current_admin)):
    rows = db.get_pending_orders() if status == "pending" else db.get_orders_by_status(status)
    out = []
    for o in rows:
        o = dict(o)
        product = row_to_dict(db.get_product(o["product_id"])) if o["product_id"] else None
        user = row_to_dict(db.get_user(o["user_id"]))
        o["product_name"] = product["name"] if product else ("ساخت کانفیگ شخصی" if o.get("is_custom_config") else "-")
        o["username"] = user["username"] if user else None
        out.append(o)
    return out


@app.post("/api/orders/{order_id}/approve")
async def api_approve_order(order_id: int, admin=Depends(require_full)):
    order = db.get_order(order_id)
    if not order or order["status"] != "pending":
        raise HTTPException(400, "سفارش یافت نشد یا قبلاً بررسی شده.")

    if order["is_custom_config"]:
        db.approve_custom_config_order(order_id)
        db.log_admin_action(admin["id"], "order_approve", f"سفارش شخصی #{order_id} (پنل وب - {admin['username']})")
        await notify_user(order["user_id"], "✅ خرید شما تایید شد.")
        return {"ok": True}

    product = db.get_product(order["product_id"])
    quantity = order["quantity"] or 1

    if product and product["is_auto_provision"]:
        try:
            results = await provision_auto_config(db, product, quantity)
        except ProvisionError as e:
            raise HTTPException(400, str(e))
        db.approve_order_auto(order_id)
        db.log_admin_action(
            admin["id"], "order_approve",
            f"سفارش #{order_id} (خودکار) | کاربر {order['user_id']} | محصول «{product['name']}» (پنل وب - {admin['username']})",
        )
        links = "\n".join(r["subscription_url"] for r in results)
        await notify_user(order["user_id"], f"✅ خرید شما تایید شد!\n📦 محصول: {product['name']}\n\n{links}")
        return {"ok": True}

    results = db.take_unused_configs(order["product_id"], order["user_id"], quantity)
    if not results:
        raise HTTPException(400, "موجودی این محصول تمام شده است.")
    db.approve_order(order_id, [r["id"] for r in results])
    db.log_admin_action(
        admin["id"], "order_approve",
        f"سفارش #{order_id} | کاربر {order['user_id']} | محصول «{product['name'] if product else '---'}» (پنل وب - {admin['username']})",
    )
    await check_and_notify_low_stock(lambda aid, text: tg_send(BOT_TOKEN, aid, text), db, order["product_id"])
    db.reward_referrer_if_first_purchase(order["user_id"], order["final_price"] or (product["price"] if product else 0))
    links = "\n".join(r["link"] for r in results)
    await notify_user(order["user_id"], f"✅ خرید شما تایید شد!\n📦 محصول: {product['name'] if product else ''}\n\n{links}")
    return {"ok": True}


@app.post("/api/orders/{order_id}/reject")
async def api_reject_order(order_id: int, admin=Depends(require_full)):
    order = db.get_order(order_id)
    if not order or order["status"] != "pending":
        raise HTTPException(400, "سفارش یافت نشد یا قبلاً بررسی شده.")
    db.reject_order(order_id)
    db.log_admin_action(admin["id"], "order_reject", f"سفارش #{order_id} رد شد (پنل وب - {admin['username']})")
    await notify_user(order["user_id"], "⛔️ سفارش شما رد شد. در صورت کسر از کیف پول، مبلغ برگشت داده شد.")
    return {"ok": True}


# ------------------------------------------------------------------ topups --


@app.get("/api/topups")
def api_topups(status: str = "pending", admin=Depends(get_current_admin)):
    rows = db.get_pending_topups() if status == "pending" else db.get_topups_by_status(status)
    out = []
    for t in rows:
        t = dict(t)
        user = row_to_dict(db.get_user(t["user_id"]))
        t["username"] = user["username"] if user else None
        out.append(t)
    return out


@app.post("/api/topups/{topup_id}/approve")
async def api_approve_topup(topup_id: int, admin=Depends(require_full)):
    topup = db.get_topup(topup_id)
    if not topup:
        raise HTTPException(404, "یافت نشد.")
    if not db.approve_topup(topup_id):
        raise HTTPException(400, "قبلاً بررسی شده است.")
    db.log_admin_action(admin["id"], "topup_approve", f"شارژ #{topup_id} تایید شد (پنل وب - {admin['username']})")
    await notify_user(topup["user_id"], f"✅ شارژ کیف پول شما به مبلغ {topup['amount']:,} تومان تایید شد.")
    return {"ok": True}


@app.post("/api/topups/{topup_id}/reject")
async def api_reject_topup(topup_id: int, admin=Depends(require_full)):
    topup = db.get_topup(topup_id)
    if not topup or topup["status"] != "pending":
        raise HTTPException(400, "یافت نشد یا قبلاً بررسی شده.")
    db.reject_topup(topup_id)
    db.log_admin_action(admin["id"], "topup_reject", f"شارژ #{topup_id} رد شد (پنل وب - {admin['username']})")
    await notify_user(topup["user_id"], "⛔️ درخواست شارژ کیف پول شما رد شد.")
    return {"ok": True}


# ------------------------------------------------------------------- users --


@app.get("/api/users")
def api_users(q: str = "", status: str = "all", page: int = 1, admin=Depends(get_current_admin)):
    limit = 25
    rows, total = db.search_users(q, status, limit=limit, offset=(page - 1) * limit)
    return {"items": rows_to_list(rows), "total": total, "page": page, "limit": limit}


@app.get("/api/users/{tg_id}")
def api_user_detail(tg_id: int, admin=Depends(get_current_admin)):
    user = db.get_user(tg_id)
    if not user:
        raise HTTPException(404, "کاربر یافت نشد.")
    history = db.get_user_full_history(tg_id)
    return {
        "user": dict(user),
        "orders": rows_to_list(history["orders"]),
        "topups": rows_to_list(history["topups"]),
        "referral": db.get_referral_stats(tg_id),
        "is_reseller": db.is_reseller(tg_id),
        "reseller_credit": db.get_reseller_credit(tg_id),
    }


@app.post("/api/users/{tg_id}/block")
def api_block_user(tg_id: int, admin=Depends(require_full)):
    db.set_user_blocked(tg_id, True)
    db.log_admin_action(admin["id"], "user_block", f"کاربر {tg_id} مسدود شد (پنل وب - {admin['username']})")
    return {"ok": True}


@app.post("/api/users/{tg_id}/unblock")
def api_unblock_user(tg_id: int, admin=Depends(require_full)):
    db.set_user_blocked(tg_id, False)
    db.log_admin_action(admin["id"], "user_unblock", f"کاربر {tg_id} رفع مسدودیت شد (پنل وب - {admin['username']})")
    return {"ok": True}


class WalletAdjustBody(BaseModel):
    delta: int


@app.post("/api/users/{tg_id}/wallet")
async def api_adjust_wallet(tg_id: int, body: WalletAdjustBody, admin=Depends(require_senior)):
    db.add_wallet_credit(tg_id, body.delta)
    db.log_admin_action(
        admin["id"], "wallet_adjust", f"کیف پول کاربر {tg_id} به میزان {body.delta:,} تغییر کرد (پنل وب - {admin['username']})"
    )
    if body.delta:
        sign = "افزایش" if body.delta > 0 else "کاهش"
        await notify_user(tg_id, f"💰 موجودی کیف پول شما {sign} یافت: {abs(body.delta):,} تومان")
    return {"ok": True}


# ------------------------------------------------------- categories/products --


class CategoryBody(BaseModel):
    name: str


@app.get("/api/categories")
def api_categories(admin=Depends(get_current_admin)):
    return rows_to_list(db.get_categories(active_only=False))


@app.post("/api/categories")
def api_add_category(body: CategoryBody, admin=Depends(require_senior)):
    cat_id = db.add_category(body.name)
    db.log_admin_action(admin["id"], "category_add", body.name)
    return {"id": cat_id}


@app.put("/api/categories/{cat_id}")
def api_edit_category(cat_id: int, body: CategoryBody, admin=Depends(require_senior)):
    db.edit_category(cat_id, body.name)
    return {"ok": True}


@app.post("/api/categories/{cat_id}/toggle")
def api_toggle_category(cat_id: int, admin=Depends(require_senior)):
    db.toggle_category(cat_id)
    return {"ok": True}


@app.delete("/api/categories/{cat_id}")
def api_delete_category(cat_id: int, admin=Depends(require_senior)):
    db.delete_category(cat_id)
    db.log_admin_action(admin["id"], "category_delete", str(cat_id))
    return {"ok": True}


class ProductBody(BaseModel):
    category_id: int
    name: str
    price: int
    description: str = ""
    duration_days: int = 30
    is_auto_provision: bool = False
    auto_provision_volume_gb: Optional[int] = None


@app.get("/api/products")
def api_products(admin=Depends(get_current_admin)):
    products = rows_to_list(db.get_all_products())
    for p in products:
        p["stock"] = db.count_available_configs(p["id"])
    return products


@app.post("/api/products")
def api_add_product(body: ProductBody, admin=Depends(require_senior)):
    pid = db.add_product(
        body.category_id, body.name, body.price, body.description, body.duration_days,
        body.is_auto_provision, body.auto_provision_volume_gb,
    )
    db.log_admin_action(admin["id"], "product_add", f"{body.name} (پنل وب - {admin['username']})")
    return {"id": pid}


class ProductEditBody(BaseModel):
    name: Optional[str] = None
    price: Optional[int] = None
    description: Optional[str] = None
    duration_days: Optional[int] = None


@app.put("/api/products/{product_id}")
def api_edit_product(product_id: int, body: ProductEditBody, admin=Depends(require_senior)):
    db.edit_product(product_id, body.name, body.price, body.description, body.duration_days)
    db.log_admin_action(admin["id"], "product_edit", f"#{product_id} (پنل وب - {admin['username']})")
    return {"ok": True}


@app.post("/api/products/{product_id}/toggle")
def api_toggle_product(product_id: int, admin=Depends(require_senior)):
    db.toggle_product(product_id)
    return {"ok": True}


@app.delete("/api/products/{product_id}")
def api_delete_product(product_id: int, admin=Depends(require_senior)):
    db.delete_product(product_id)
    db.log_admin_action(admin["id"], "product_delete", str(product_id))
    return {"ok": True}


# ------------------------------------------------------------- config bank --


class ConfigsAddBody(BaseModel):
    links: str  # هر خط یک لینک


@app.get("/api/products/{product_id}/configs")
def api_product_configs(product_id: int, admin=Depends(require_senior)):
    return rows_to_list(db.get_unused_configs(product_id))


@app.post("/api/products/{product_id}/configs")
def api_add_configs(product_id: int, body: ConfigsAddBody, admin=Depends(require_senior)):
    links = [l.strip() for l in body.links.splitlines() if l.strip()]
    added, duplicates = db.add_configs(product_id, links)
    db.log_admin_action(admin["id"], "configs_add", f"{added} لینک به محصول #{product_id} (پنل وب - {admin['username']})")
    return {"added": added, "duplicates": duplicates}


@app.delete("/api/configs/{config_id}")
def api_delete_config(config_id: int, admin=Depends(require_senior)):
    db.delete_config(config_id)
    return {"ok": True}


# --------------------------------------------------------------- discounts --


class DiscountBody(BaseModel):
    code: str
    percent: Optional[int] = None
    fixed_amount: Optional[int] = None
    max_uses: int = 0
    expires_at: Optional[str] = None


@app.get("/api/discounts")
def api_discounts(admin=Depends(require_senior)):
    return rows_to_list(db.list_discount_codes())


@app.post("/api/discounts")
def api_add_discount(body: DiscountBody, admin=Depends(require_senior)):
    code_id = db.create_discount_code(body.code, body.percent, body.fixed_amount, body.max_uses, body.expires_at)
    db.log_admin_action(admin["id"], "discount_add", body.code)
    return {"id": code_id}


@app.post("/api/discounts/{code_id}/toggle")
def api_toggle_discount(code_id: int, admin=Depends(require_senior)):
    db.toggle_discount_code(code_id)
    return {"ok": True}


@app.delete("/api/discounts/{code_id}")
def api_delete_discount(code_id: int, admin=Depends(require_senior)):
    db.delete_discount_code(code_id)
    return {"ok": True}


# ------------------------------------------------------------------ tickets --


@app.get("/api/tickets")
def api_tickets(status: Optional[str] = None, admin=Depends(get_current_admin)):
    tickets = rows_to_list(db.get_all_tickets(status))
    for t in tickets:
        user = row_to_dict(db.get_user(t["user_id"]))
        t["username"] = user["username"] if user else None
    return tickets


@app.get("/api/tickets/{ticket_id}/messages")
def api_ticket_messages(ticket_id: int, admin=Depends(get_current_admin)):
    ticket = db.get_ticket(ticket_id)
    if not ticket:
        raise HTTPException(404, "یافت نشد.")
    return {"ticket": dict(ticket), "messages": rows_to_list(db.get_ticket_messages(ticket_id))}


class TicketReplyBody(BaseModel):
    message: str


@app.post("/api/tickets/{ticket_id}/reply")
async def api_ticket_reply(ticket_id: int, body: TicketReplyBody, admin=Depends(require_full)):
    ticket = db.get_ticket(ticket_id)
    if not ticket:
        raise HTTPException(404, "یافت نشد.")
    db.claim_ticket_if_open(ticket_id, admin["id"])
    db.add_ticket_message(ticket_id, "admin", body.message)
    await notify_user(ticket["user_id"], f"📩 پاسخ پشتیبانی برای تیکت «{ticket['subject']}»:\n\n{body.message}")
    return {"ok": True}


@app.post("/api/tickets/{ticket_id}/close")
def api_ticket_close(ticket_id: int, admin=Depends(require_full)):
    db.close_ticket(ticket_id)
    return {"ok": True}


# -------------------------------------------------------------- resellers --


@app.get("/api/resellers")
def api_resellers(admin=Depends(require_senior)):
    return rows_to_list(db.get_resellers())


class ResellerCreditBody(BaseModel):
    delta_gb: int
    reason: Optional[str] = None


@app.post("/api/resellers/{tg_id}/credit")
async def api_adjust_reseller_credit(tg_id: int, body: ResellerCreditBody, admin=Depends(require_senior)):
    db.adjust_reseller_credit(tg_id, body.delta_gb, admin_id=admin["id"], reason=body.reason or "تنظیم از پنل وب")
    db.log_admin_action(
        admin["id"], "reseller_credit_adjust",
        f"نماینده {tg_id} به میزان {body.delta_gb:,} گیگ (پنل وب - {admin['username']})",
    )
    await notify_user(tg_id, f"📦 اعتبار حجمی نمایندگی شما تغییر کرد: {body.delta_gb:+,} گیگابایت")
    return {"ok": True}


@app.get("/api/resellers/{tg_id}/log")
def api_reseller_log(tg_id: int, admin=Depends(require_senior)):
    return rows_to_list(db.get_reseller_credit_log(tg_id, limit=50))


class ResellerToggleBody(BaseModel):
    enabled: bool


@app.post("/api/resellers/{tg_id}/status")
def api_reseller_status(tg_id: int, body: ResellerToggleBody, admin=Depends(require_senior)):
    db.set_reseller_status(tg_id, body.enabled)
    return {"ok": True}


@app.get("/api/reseller-requests")
def api_reseller_requests(status: Optional[str] = None, admin=Depends(require_senior)):
    return rows_to_list(db.list_reseller_requests(status))


# ---------------------------------------------------------------- panels --


class PanelServerBody(BaseModel):
    name: str
    panel_type: str
    api_url: str
    api_username: str
    api_password: str
    default_group: Optional[str] = None


@app.get("/api/panel-servers")
def api_panel_servers(admin=Depends(require_senior)):
    servers = rows_to_list(db.get_panel_servers())
    for s in servers:
        s["type_label"] = PANEL_TYPE_LABELS.get(s["panel_type"], s["panel_type"])
    return servers


@app.post("/api/panel-servers")
def api_add_panel_server(body: PanelServerBody, admin=Depends(require_senior)):
    sid = db.add_panel_server(body.name, body.panel_type, body.api_url, body.api_username, body.api_password, body.default_group)
    db.log_admin_action(admin["id"], "panel_add", body.name)
    return {"id": sid}


@app.delete("/api/panel-servers/{server_id}")
def api_delete_panel_server(server_id: int, admin=Depends(require_senior)):
    db.delete_panel_server(server_id)
    return {"ok": True}


@app.post("/api/panel-servers/{server_id}/test")
async def api_test_panel_server(server_id: int, admin=Depends(require_senior)):
    server = db.get_panel_server(server_id)
    if not server:
        raise HTTPException(404, "یافت نشد.")
    try:
        provider = get_provider(server)
        ok = await provider.test_connection()
    except PanelError as e:
        return {"ok": False, "error": str(e)}
    return {"ok": ok}


# --------------------------------------------------------------- settings --


@app.get("/api/settings")
def api_settings(admin=Depends(require_senior)):
    return db.get_all_settings()


class SettingBody(BaseModel):
    key: str
    value: str


@app.post("/api/settings")
def api_set_setting(body: SettingBody, admin=Depends(require_senior)):
    db.set_setting(body.key, body.value)
    db.log_admin_action(admin["id"], "setting_change", f"{body.key}={body.value} (پنل وب - {admin['username']})")
    return {"ok": True}


# ----------------------------------------------------------------- logs ---


@app.get("/api/admin-logs")
def api_admin_logs(page: int = 1, admin=Depends(require_senior)):
    limit = 40
    rows, total = db.get_admin_logs(limit=limit, offset=(page - 1) * limit)
    return {"items": rows_to_list(rows), "total": total, "page": page, "limit": limit}


# ----------------------------------------------------------- web admins ---


class WebAdminCreateBody(BaseModel):
    username: str
    password: str
    role: str = "admin"


@app.get("/api/web-admins")
def api_web_admins(admin=Depends(require_owner)):
    return rows_to_list(db.list_web_admins())


@app.post("/api/web-admins")
def api_create_web_admin(body: WebAdminCreateBody, admin=Depends(require_owner)):
    if db.get_web_admin_by_username(body.username):
        raise HTTPException(400, "این یوزرنیم قبلاً استفاده شده.")
    if len(body.password) < 8:
        raise HTTPException(400, "پسورد باید حداقل ۸ کاراکتر باشد.")
    new_id = db.create_web_admin(body.username, hash_password(body.password), body.role)
    db.log_admin_action(admin["id"], "web_admin_add", f"{body.username} ({body.role})")
    return {"id": new_id}


class WebAdminRoleBody(BaseModel):
    role: str


@app.post("/api/web-admins/{admin_id}/role")
def api_set_web_admin_role(admin_id: int, body: WebAdminRoleBody, admin=Depends(require_owner)):
    if not db.set_web_admin_role(admin_id, body.role):
        raise HTTPException(400, "امکان تغییر نقش این حساب نیست.")
    return {"ok": True}


class WebAdminActiveBody(BaseModel):
    active: bool


@app.post("/api/web-admins/{admin_id}/active")
def api_set_web_admin_active(admin_id: int, body: WebAdminActiveBody, admin=Depends(require_owner)):
    if not db.set_web_admin_active(admin_id, body.active):
        raise HTTPException(400, "امکان تغییر وضعیت این حساب نیست.")
    return {"ok": True}


@app.delete("/api/web-admins/{admin_id}")
def api_delete_web_admin(admin_id: int, admin=Depends(require_owner)):
    if not db.delete_web_admin(admin_id):
        raise HTTPException(400, "امکان حذف این حساب نیست.")
    return {"ok": True}


class MyPasswordBody(BaseModel):
    current_password: str
    new_password: str


@app.post("/api/me/password")
def api_change_my_password(body: MyPasswordBody, admin=Depends(get_current_admin)):
    row = db.get_web_admin(admin["id"])
    if not verify_password(body.current_password, row["password_hash"]):
        raise HTTPException(400, "پسورد فعلی اشتباه است.")
    if len(body.new_password) < 8:
        raise HTTPException(400, "پسورد جدید باید حداقل ۸ کاراکتر باشد.")
    db.set_web_admin_password(admin["id"], hash_password(body.new_password))
    return {"ok": True}


# ------------------------------------------------------------------ static --

STATIC_DIR = os.path.join(BASE_DIR, "static")
app.mount("/assets", StaticFiles(directory=STATIC_DIR), name="assets")


@app.get("/", response_class=HTMLResponse)
def serve_index():
    with open(os.path.join(STATIC_DIR, "index.html"), "r", encoding="utf-8") as f:
        return f.read()
