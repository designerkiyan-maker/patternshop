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
import tempfile
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, Request, Response, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from config import DB_PATH, BOT_TOKEN, OWNER_ID, ADMIN_PANEL_SECRET
from database import Database, WEB_ADMIN_PERMISSIONS
from admin_panel.security import hash_password, verify_password, create_session_token, verify_session_token
from admin_panel.telegram_notify import send_message as tg_send, send_document as tg_send_document
from reseller_auto_provision import provision_auto_config, ProvisionError
from stock_alerts import check_and_notify_low_stock
from panel_providers import get_provider, PanelError, PANEL_TYPE_LABELS
from renewal_reminders import STATUS_KEY_LAST_RUN, STATUS_KEY_LAST_DATE_SENT, STATUS_KEY_LAST_VOLUME_SENT
from backup import create_backup, restore_backup, is_valid_sqlite_db
import exchange_rate

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
    return {
        "id": admin["id"],
        "username": admin["username"],
        "role": admin["role"],
        "permissions": db.get_web_admin_permissions(admin),
    }


def require_permission(permission: str):
    def _dep(admin=Depends(get_current_admin)):
        if admin["role"] != "owner" and permission not in admin["permissions"]:
            raise HTTPException(403, "دسترسی کافی نیست.")
        return admin
    return _dep


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


# ------------------------------------------------------------------ system --


@app.get("/api/system/stats")
def api_system_stats(admin=Depends(get_current_admin)):
    """وضعیت لحظه‌ای منابع سرور (CPU / RAM / دیسک) برای نمایش در صفحه‌ی خانه."""
    try:
        import psutil
    except ImportError:
        raise HTTPException(500, "psutil نصب نیست. دستور: pip install psutil")

    cpu_percent = psutil.cpu_percent(interval=0.3)
    cpu_count = psutil.cpu_count(logical=True) or 1

    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("/")

    try:
        load1, load5, load15 = os.getloadavg()
    except (OSError, AttributeError):
        load1 = load5 = load15 = None

    return {
        "cpu": {
            "percent": round(cpu_percent, 1),
            "cores": cpu_count,
            "load1": load1, "load5": load5, "load15": load15,
        },
        "ram": {
            "percent": round(mem.percent, 1),
            "used_gb": round(mem.used / (1024 ** 3), 1),
            "total_gb": round(mem.total / (1024 ** 3), 1),
        },
        "disk": {
            "percent": round(disk.percent, 1),
            "used_gb": round(disk.used / (1024 ** 3), 1),
            "total_gb": round(disk.total / (1024 ** 3), 1),
        },
    }


@app.get("/api/system/jobs")
def api_system_jobs(admin=Depends(require_permission("system"))):
    """وضعیت فقط‌خواندنیِ آخرین اجرای یادآوری‌های تمدید/حجم + وضعیت لحظه‌ای موجودی محصولات.
    زمان‌بندی این‌ها هاردکد است (renewal_reminder_loop در پردازش بات) و از اینجا قابل تغییر نیست."""
    return {
        "renewal": {
            "last_run": db.get_setting(STATUS_KEY_LAST_RUN, "") or None,
            "last_date_sent": int(db.get_setting(STATUS_KEY_LAST_DATE_SENT, "0") or 0),
            "last_volume_sent": int(db.get_setting(STATUS_KEY_LAST_VOLUME_SENT, "0") or 0),
        },
        "stock": db.get_low_stock_overview(),
    }


# ------------------------------------------------------------------ backup --

BACKUP_DIR = os.path.join(os.path.dirname(os.path.abspath(DB_PATH)), "backups")


@app.get("/api/system/backup/status")
def api_backup_status(admin=Depends(require_permission("system"))):
    """آخرین وضعیت بکاپ‌ها؛ فقط‌خواندنی، برای نمایش در پنل."""
    if not os.path.isdir(BACKUP_DIR):
        return {"last_backup_at": None, "last_backup_size_mb": None, "count": 0}
    files = sorted(
        (f for f in os.listdir(BACKUP_DIR) if f.endswith(".db") and not f.startswith("pre_restore_")),
    )
    if not files:
        return {"last_backup_at": None, "last_backup_size_mb": None, "count": 0}
    last_path = os.path.join(BACKUP_DIR, files[-1])
    return {
        "last_backup_at": db.get_setting("_job_backup_last_at", "") or None,
        "last_backup_size_mb": round(os.path.getsize(last_path) / (1024 * 1024), 1),
        "count": len(files),
    }


@app.post("/api/system/backup/create")
async def api_backup_create(admin=Depends(require_permission("backup"))):
    """یک بکاپ فوری می‌سازد و به همه‌ی ادمین‌های تلگرامی همین بات ارسال می‌کند."""
    backup_path = await asyncio.to_thread(create_backup, DB_PATH, BACKUP_DIR, 14)
    if not backup_path:
        raise HTTPException(404, "فایل دیتابیس پیدا نشد.")

    size_mb = round(os.path.getsize(backup_path) / (1024 * 1024), 1)
    caption = f"🗄 بکاپ فوری دیتابیس (پنل وب - {admin['username']})"

    sent, failed = 0, 0
    for admin_tg_id in db.list_admins():
        ok = await tg_send_document(BOT_TOKEN, admin_tg_id, backup_path, caption)
        sent += 1 if ok else 0
        failed += 0 if ok else 1

    db.set_setting("_job_backup_last_at", datetime.now().isoformat())
    db.log_admin_action(
        admin["id"], "backup_create",
        f"بکاپ فوری ساخته شد ({os.path.basename(backup_path)}, {size_mb} مگابایت) — ارسال به {sent} ادمین "
        f"(پنل وب - {admin['username']})",
    )
    return {"ok": True, "filename": os.path.basename(backup_path), "size_mb": size_mb, "sent": sent, "failed": failed}


@app.post("/api/system/backup/restore")
async def api_backup_restore(
    file: UploadFile = File(...), confirm_phrase: str = Form(""), admin=Depends(require_owner)
):
    """جایگزینی کامل دیتابیس با فایل بکاپ آپلودشده. چون این کار overwrite کامل و
    غیرقابل‌برگشت (به‌جز با بکاپ دیگر) است، علاوه بر تاییدیه‌ی دوگانه‌ی فرانت‌اند،
    سمت سرور هم عبارت تاییدی «RESTORE» را الزامی می‌کند."""
    if confirm_phrase.strip().upper() != "RESTORE":
        raise HTTPException(400, "برای تایید بازیابی، عبارت RESTORE را دقیقاً وارد کن.")
    if not file.filename or not file.filename.lower().endswith((".db", ".sqlite", ".sqlite3")):
        raise HTTPException(400, "فایل باید پسوند .db یا .sqlite داشته باشد.")

    tmp_dir = tempfile.mkdtemp(prefix="restore_")
    tmp_path = os.path.join(tmp_dir, "uploaded.db")
    content = await file.read()
    with open(tmp_path, "wb") as f:
        f.write(content)

    if not is_valid_sqlite_db(tmp_path):
        os.remove(tmp_path)
        os.rmdir(tmp_dir)
        raise HTTPException(400, "این فایل یک دیتابیس sqlite معتبر نیست.")

    try:
        pre_restore_path = await asyncio.to_thread(restore_backup, db, DB_PATH, tmp_path)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, f"بازیابی ناموفق بود: {e}")
    finally:
        try:
            os.remove(tmp_path)
            os.rmdir(tmp_dir)
        except OSError:
            pass

    db.log_admin_action(
        admin["id"], "backup_restore",
        f"دیتابیس از فایل آپلودی بازیابی شد؛ نسخه‌ی قبلی: {os.path.basename(pre_restore_path)} "
        f"(پنل وب - {admin['username']})",
    )
    return {"ok": True, "pre_restore_backup": os.path.basename(pre_restore_path)}


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
async def api_approve_order(order_id: int, admin=Depends(require_permission("orders"))):
    order = db.get_order(order_id)
    if not order or order["status"] != "pending":
        raise HTTPException(400, "سفارش یافت نشد یا قبلاً بررسی شده.")

    if order["is_custom_config"]:
        db.approve_custom_config_order(order_id)
        db.log_admin_action(admin["id"], "order_approve", f"سفارش شخصی #{order_id} (پنل وب - {admin['username']})", "order", order_id)
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
            "order", order_id,
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
        "order", order_id,
    )
    await check_and_notify_low_stock(lambda aid, text: tg_send(BOT_TOKEN, aid, text), db, order["product_id"])
    db.reward_referrer_if_first_purchase(order["user_id"], order["final_price"] or (product["price"] if product else 0))
    links = "\n".join(r["link"] for r in results)
    await notify_user(order["user_id"], f"✅ خرید شما تایید شد!\n📦 محصول: {product['name'] if product else ''}\n\n{links}")
    return {"ok": True}


@app.post("/api/orders/{order_id}/reject")
async def api_reject_order(order_id: int, admin=Depends(require_permission("orders"))):
    order = db.get_order(order_id)
    if not order or order["status"] != "pending":
        raise HTTPException(400, "سفارش یافت نشد یا قبلاً بررسی شده.")
    db.reject_order(order_id)
    db.log_admin_action(admin["id"], "order_reject", f"سفارش #{order_id} رد شد (پنل وب - {admin['username']})", "order", order_id)
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
async def api_approve_topup(topup_id: int, admin=Depends(require_permission("orders"))):
    topup = db.get_topup(topup_id)
    if not topup:
        raise HTTPException(404, "یافت نشد.")
    if not db.approve_topup(topup_id):
        raise HTTPException(400, "قبلاً بررسی شده است.")
    db.log_admin_action(admin["id"], "topup_approve", f"شارژ #{topup_id} تایید شد (پنل وب - {admin['username']})", "topup", topup_id)
    await notify_user(topup["user_id"], f"✅ شارژ کیف پول شما به مبلغ {topup['amount']:,} تومان تایید شد.")
    return {"ok": True}


@app.post("/api/topups/{topup_id}/reject")
async def api_reject_topup(topup_id: int, admin=Depends(require_permission("orders"))):
    topup = db.get_topup(topup_id)
    if not topup or topup["status"] != "pending":
        raise HTTPException(400, "یافت نشد یا قبلاً بررسی شده.")
    db.reject_topup(topup_id)
    db.log_admin_action(admin["id"], "topup_reject", f"شارژ #{topup_id} رد شد (پنل وب - {admin['username']})", "topup", topup_id)
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
def api_block_user(tg_id: int, admin=Depends(require_permission("users"))):
    db.set_user_blocked(tg_id, True)
    db.log_admin_action(admin["id"], "user_block", f"کاربر {tg_id} مسدود شد (پنل وب - {admin['username']})", "user", tg_id)
    return {"ok": True}


@app.post("/api/users/{tg_id}/unblock")
def api_unblock_user(tg_id: int, admin=Depends(require_permission("users"))):
    db.set_user_blocked(tg_id, False)
    db.log_admin_action(admin["id"], "user_unblock", f"کاربر {tg_id} رفع مسدودیت شد (پنل وب - {admin['username']})", "user", tg_id)
    return {"ok": True}


class WalletAdjustBody(BaseModel):
    delta: int


@app.post("/api/users/{tg_id}/wallet")
async def api_adjust_wallet(tg_id: int, body: WalletAdjustBody, admin=Depends(require_permission("users"))):
    db.add_wallet_credit(tg_id, body.delta)
    db.log_admin_action(
        admin["id"], "wallet_adjust", f"کیف پول کاربر {tg_id} به میزان {body.delta:,} تغییر کرد (پنل وب - {admin['username']})",
        "user", tg_id,
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
def api_add_category(body: CategoryBody, admin=Depends(require_permission("catalog"))):
    cat_id = db.add_category(body.name)
    db.log_admin_action(admin["id"], "category_add", body.name, "category", cat_id)
    return {"id": cat_id}


@app.put("/api/categories/{cat_id}")
def api_edit_category(cat_id: int, body: CategoryBody, admin=Depends(require_permission("catalog"))):
    db.edit_category(cat_id, body.name)
    db.log_admin_action(admin["id"], "category_edit", body.name, "category", cat_id)
    return {"ok": True}


@app.post("/api/categories/{cat_id}/toggle")
def api_toggle_category(cat_id: int, admin=Depends(require_permission("catalog"))):
    db.toggle_category(cat_id)
    db.log_admin_action(admin["id"], "category_toggle", str(cat_id), "category", cat_id)
    return {"ok": True}


@app.delete("/api/categories/{cat_id}")
def api_delete_category(cat_id: int, admin=Depends(require_permission("catalog"))):
    db.delete_category(cat_id)
    db.log_admin_action(admin["id"], "category_delete", str(cat_id), "category", cat_id)
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
def api_add_product(body: ProductBody, admin=Depends(require_permission("catalog"))):
    pid = db.add_product(
        body.category_id, body.name, body.price, body.description, body.duration_days,
        body.is_auto_provision, body.auto_provision_volume_gb,
    )
    db.log_admin_action(admin["id"], "product_add", f"{body.name} (پنل وب - {admin['username']})", "product", pid)
    return {"id": pid}


class ProductEditBody(BaseModel):
    name: Optional[str] = None
    price: Optional[int] = None
    description: Optional[str] = None
    duration_days: Optional[int] = None


@app.put("/api/products/{product_id}")
def api_edit_product(product_id: int, body: ProductEditBody, admin=Depends(require_permission("catalog"))):
    db.edit_product(product_id, body.name, body.price, body.description, body.duration_days)
    db.log_admin_action(admin["id"], "product_edit", f"#{product_id} (پنل وب - {admin['username']})", "product", product_id)
    return {"ok": True}


@app.post("/api/products/{product_id}/toggle")
def api_toggle_product(product_id: int, admin=Depends(require_permission("catalog"))):
    db.toggle_product(product_id)
    db.log_admin_action(admin["id"], "product_toggle", str(product_id), "product", product_id)
    return {"ok": True}


@app.delete("/api/products/{product_id}")
def api_delete_product(product_id: int, admin=Depends(require_permission("catalog"))):
    db.delete_product(product_id)
    db.log_admin_action(admin["id"], "product_delete", str(product_id), "product", product_id)
    return {"ok": True}


# ------------------------------------------------------------- config bank --


class ConfigsAddBody(BaseModel):
    links: str  # هر خط یک لینک


@app.get("/api/products/{product_id}/configs")
def api_product_configs(product_id: int, admin=Depends(require_permission("catalog"))):
    return rows_to_list(db.get_unused_configs(product_id))


@app.post("/api/products/{product_id}/configs")
def api_add_configs(product_id: int, body: ConfigsAddBody, admin=Depends(require_permission("catalog"))):
    links = [l.strip() for l in body.links.splitlines() if l.strip()]
    added, duplicates = db.add_configs(product_id, links)
    db.log_admin_action(admin["id"], "configs_add", f"{added} لینک به محصول #{product_id} (پنل وب - {admin['username']})", "product", product_id)
    return {"added": added, "duplicates": duplicates}


@app.delete("/api/configs/{config_id}")
def api_delete_config(config_id: int, admin=Depends(require_permission("catalog"))):
    db.delete_config(config_id)
    db.log_admin_action(admin["id"], "config_delete", str(config_id), "config", config_id)
    return {"ok": True}


# --------------------------------------------------------------- discounts --


class DiscountBody(BaseModel):
    code: str
    percent: Optional[int] = None
    fixed_amount: Optional[int] = None
    max_uses: int = 0
    expires_at: Optional[str] = None


@app.get("/api/discounts")
def api_discounts(admin=Depends(require_permission("discounts"))):
    return rows_to_list(db.list_discount_codes())


@app.post("/api/discounts")
def api_add_discount(body: DiscountBody, admin=Depends(require_permission("discounts"))):
    code_id = db.create_discount_code(body.code, body.percent, body.fixed_amount, body.max_uses, body.expires_at)
    db.log_admin_action(admin["id"], "discount_add", body.code, "discount", code_id)
    return {"id": code_id}


@app.post("/api/discounts/{code_id}/toggle")
def api_toggle_discount(code_id: int, admin=Depends(require_permission("discounts"))):
    db.toggle_discount_code(code_id)
    db.log_admin_action(admin["id"], "discount_toggle", str(code_id), "discount", code_id)
    return {"ok": True}


@app.delete("/api/discounts/{code_id}")
def api_delete_discount(code_id: int, admin=Depends(require_permission("discounts"))):
    db.delete_discount_code(code_id)
    db.log_admin_action(admin["id"], "discount_delete", str(code_id), "discount", code_id)
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
async def api_ticket_reply(ticket_id: int, body: TicketReplyBody, admin=Depends(require_permission("tickets"))):
    ticket = db.get_ticket(ticket_id)
    if not ticket:
        raise HTTPException(404, "یافت نشد.")
    db.claim_ticket_if_open(ticket_id, admin["id"])
    db.add_ticket_message(ticket_id, "admin", body.message)
    await notify_user(ticket["user_id"], f"📩 پاسخ پشتیبانی برای تیکت «{ticket['subject']}»:\n\n{body.message}")
    db.log_admin_action(admin["id"], "ticket_reply", f"تیکت #{ticket_id} (پنل وب - {admin['username']})", "ticket", ticket_id)
    return {"ok": True}


@app.post("/api/tickets/{ticket_id}/close")
def api_ticket_close(ticket_id: int, admin=Depends(require_permission("tickets"))):
    db.close_ticket(ticket_id)
    db.log_admin_action(admin["id"], "ticket_close", f"تیکت #{ticket_id} (پنل وب - {admin['username']})", "ticket", ticket_id)
    return {"ok": True}


# -------------------------------------------------------------- broadcast --


class BroadcastBody(BaseModel):
    message: str


@app.post("/api/broadcast")
async def api_broadcast(body: BroadcastBody, admin=Depends(require_permission("broadcast"))):
    text = (body.message or "").strip()
    if not text:
        raise HTTPException(400, "متن پیام نمی‌تواند خالی باشد.")
    if len(text) > 4000:
        raise HTTPException(400, "متن پیام بیش از حد طولانی است.")

    user_ids = db.get_all_user_ids()
    sem = asyncio.Semaphore(20)
    counters = {"success": 0, "failed": 0}

    async def _send(uid):
        async with sem:
            ok = await tg_send(BOT_TOKEN, uid, text)
            counters["success" if ok else "failed"] += 1

    await asyncio.gather(*[_send(uid) for uid in user_ids])
    db.log_admin_action(
        admin["id"], "broadcast",
        f"ارسال به {len(user_ids)} کاربر | موفق: {counters['success']} | ناموفق: {counters['failed']} "
        f"(پنل وب - {admin['username']})",
    )
    return {"total": len(user_ids), "success": counters["success"], "failed": counters["failed"]}


# --------------------------------------------------------- live support chat --


def _support_lock_label(assigned_admin_id):
    """assigned_admin_id مثبت یعنی قفل روی ادمین تلگرام (بات/میان‌اپ)، منفی یعنی
    قفل روی ادمین وب (چون ادمین‌های وب آیدی تلگرام ندارند، با -admin_id ذخیره می‌شوند)."""
    if not assigned_admin_id:
        return None
    if assigned_admin_id < 0:
        wa = db.get_web_admin(-assigned_admin_id)
        return f"{wa['username']} (پنل وب)" if wa else "ادمین وب"
    return f"ادمین تلگرام #{assigned_admin_id}"


@app.get("/api/support/conversations")
def api_support_conversations(admin=Depends(get_current_admin)):
    my_lock_id = -admin["id"]
    is_owner = admin["role"] == "owner"
    convs = rows_to_list(db.list_support_conversations())
    for c in convs:
        user = row_to_dict(db.get_user(c["user_id"]))
        c["user_name"] = (user["first_name"] if user else "") or ""
        c["user_username"] = (user["username"] if user else "") or ""
        assigned = c.get("assigned_admin_id")
        c["locked_by"] = _support_lock_label(assigned)
        c["locked_for_me"] = bool(assigned) and assigned != my_lock_id and not is_owner
    return convs


@app.get("/api/support/{user_id}/messages")
def api_support_messages(user_id: int, since_id: int = 0, admin=Depends(get_current_admin)):
    user = db.get_user(user_id)
    if not user:
        raise HTTPException(404, "کاربر یافت نشد.")
    db.mark_support_read_by_admin(user_id)
    rows = rows_to_list(db.get_support_messages(user_id, since_id=since_id))
    conv = db.get_support_conversation(user_id)
    assigned = conv["assigned_admin_id"] if conv else None
    my_lock_id = -admin["id"]
    is_owner = admin["role"] == "owner"
    return {
        "user": {
            "user_id": user_id,
            "user_name": (user["first_name"] if user else "") or "",
            "user_username": (user["username"] if user else "") or "",
            "locked_by": _support_lock_label(assigned),
            "locked_for_me": bool(assigned) and assigned != my_lock_id and not is_owner,
        },
        "messages": [
            {"id": m["id"], "sender": m["sender"], "message": m["message"], "created_at": m["created_at"]}
            for m in rows
        ],
    }


class SupportReplyBody(BaseModel):
    message: str


@app.post("/api/support/{user_id}/messages")
async def api_support_send(user_id: int, body: SupportReplyBody, admin=Depends(get_current_admin)):
    user = db.get_user(user_id)
    if not user:
        raise HTTPException(404, "کاربر یافت نشد.")
    text = (body.message or "").strip()
    if not text:
        raise HTTPException(400, "پیام نمی‌تواند خالی باشد.")
    if len(text) > 2000:
        raise HTTPException(400, "پیام بیش از حد طولانی است.")

    # قفل مکالمه: چون ادمین‌های وب آیدی تلگرام ندارند، با -admin_id در همان
    # ستون assigned_admin_id ذخیره می‌شود (که با آیدی‌های واقعی تلگرام تداخل ندارد).
    my_lock_id = -admin["id"]
    is_owner = admin["role"] == "owner"
    conv = db.get_support_conversation(user_id)
    assigned = conv["assigned_admin_id"] if conv else None
    if assigned and assigned != my_lock_id and not is_owner:
        raise HTTPException(
            403,
            f"این گفتگو در حال حاضر توسط {_support_lock_label(assigned)} در حال پاسخ‌دهی است.",
        )
    if not is_owner:
        db.set_support_conversation_admin(user_id, my_lock_id)

    msg_id = db.add_support_message(user_id, "admin", text)
    await notify_user(user_id, f"💬 پشتیبانی:\n\n{text}")
    db.log_admin_action(admin["id"], "support_reply", f"پاسخ چت زنده به کاربر {user_id} (پنل وب - {admin['username']})", "user", user_id)
    return {"ok": True, "id": msg_id}


# -------------------------------------------------------------- resellers --


@app.get("/api/resellers")
def api_resellers(admin=Depends(require_permission("resellers"))):
    return rows_to_list(db.get_resellers())


class ResellerCreditBody(BaseModel):
    delta_gb: int
    reason: Optional[str] = None


@app.post("/api/resellers/{tg_id}/credit")
async def api_adjust_reseller_credit(tg_id: int, body: ResellerCreditBody, admin=Depends(require_permission("resellers"))):
    db.adjust_reseller_credit(tg_id, body.delta_gb, admin_id=admin["id"], reason=body.reason or "تنظیم از پنل وب")
    db.log_admin_action(
        admin["id"], "reseller_credit_adjust",
        f"نماینده {tg_id} به میزان {body.delta_gb:,} گیگ (پنل وب - {admin['username']})",
        "reseller", tg_id,
    )
    await notify_user(tg_id, f"📦 اعتبار حجمی نمایندگی شما تغییر کرد: {body.delta_gb:+,} گیگابایت")
    return {"ok": True}


@app.get("/api/resellers/{tg_id}/log")
def api_reseller_log(tg_id: int, admin=Depends(require_permission("resellers"))):
    return rows_to_list(db.get_reseller_credit_log(tg_id, limit=50))


class ResellerToggleBody(BaseModel):
    enabled: bool


@app.post("/api/resellers/{tg_id}/status")
def api_reseller_status(tg_id: int, body: ResellerToggleBody, admin=Depends(require_permission("resellers"))):
    db.set_reseller_status(tg_id, body.enabled)
    db.log_admin_action(admin["id"], "reseller_status_toggle", f"نماینده {tg_id} -> {body.enabled}", "reseller", tg_id)
    return {"ok": True}


@app.get("/api/resellers/analytics/cohort")
def api_reseller_cohort(days: int = 30, months: int = 6, admin=Depends(require_permission("resellers"))):
    """تحلیل کوهورت (نگهداشت ماهانه) و ریزش (churn) نمایندگی‌ها."""
    days = max(1, min(days, 365))
    months = max(1, min(months, 12))
    return db.get_reseller_cohort_churn(inactivity_days=days, months=months)


@app.get("/api/reseller-requests")
def api_reseller_requests(status: Optional[str] = None, admin=Depends(require_permission("resellers"))):
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
def api_panel_servers(admin=Depends(require_permission("panels"))):
    servers = rows_to_list(db.get_panel_servers())
    for s in servers:
        s["type_label"] = PANEL_TYPE_LABELS.get(s["panel_type"], s["panel_type"])
    return servers


@app.post("/api/panel-servers")
def api_add_panel_server(body: PanelServerBody, admin=Depends(require_permission("panels"))):
    sid = db.add_panel_server(body.name, body.panel_type, body.api_url, body.api_username, body.api_password, body.default_group)
    db.log_admin_action(admin["id"], "panel_add", body.name, "panel", sid)
    return {"id": sid}


@app.delete("/api/panel-servers/{server_id}")
def api_delete_panel_server(server_id: int, admin=Depends(require_permission("panels"))):
    db.delete_panel_server(server_id)
    db.log_admin_action(admin["id"], "panel_delete", str(server_id), "panel", server_id)
    return {"ok": True}


@app.post("/api/panel-servers/{server_id}/test")
async def api_test_panel_server(server_id: int, admin=Depends(require_permission("panels"))):
    server = db.get_panel_server(server_id)
    if not server:
        raise HTTPException(404, "یافت نشد.")
    try:
        provider = get_provider(server)
        ok = await provider.test_connection()
    except PanelError as e:
        return {"ok": False, "error": str(e)}
    return {"ok": ok}


# ----------------------------------------------------------- exchange rate --


def _rate_response(ok: bool, status: dict, error: Optional[str] = None) -> dict:
    ts = status.get("ts") or 0
    return {
        "ok": ok,
        "rate": status.get("rate"),
        "source": status.get("source"),
        "updated_at": datetime.fromtimestamp(ts).isoformat(sep=" ") if ts else None,
        "cache_ttl_seconds": exchange_rate.CACHE_TTL_SECONDS,
        "error": error,
    }


def _manual_fallback_rate() -> Optional[float]:
    try:
        value = float(db.get_setting("manual_usd_rate_toman", "0") or 0)
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


@app.get("/api/exchange-rate")
async def api_exchange_rate(admin=Depends(require_permission("panels"))):
    """نرخ فعلی دلار به تومان (از کش یا در صورت انقضا، از منابع خارجی) + نام منبع."""
    try:
        await exchange_rate.get_usd_to_toman_rate(manual_fallback=_manual_fallback_rate())
        return _rate_response(True, exchange_rate.get_cache_status())
    except Exception as e:
        # حتی اگر دریافت زنده شکست بخورد، هر مقدار کش‌شده‌ی قدیمی را نشان بده
        return _rate_response(False, exchange_rate.get_cache_status(), str(e))


@app.post("/api/exchange-rate/refresh")
async def api_exchange_rate_refresh(admin=Depends(require_permission("panels"))):
    """کش نرخ را باطل و دوباره از منابع خارجی (tgju/نوبیتکس/والکس/coingecko) دریافت می‌کند."""
    try:
        status = await exchange_rate.refresh_rate(manual_fallback=_manual_fallback_rate())
    except Exception as e:
        raise HTTPException(502, str(e))
    db.log_admin_action(
        admin["id"], "exchange_rate_refresh",
        f"نرخ دلار به {status['rate']:,} تومان (منبع: {status['source']}) رفرش شد (پنل وب - {admin['username']})",
    )
    return _rate_response(True, status)


# --------------------------------------------------------------- settings --


@app.get("/api/settings")
def api_settings(admin=Depends(require_permission("settings"))):
    return db.get_all_settings()


class SettingBody(BaseModel):
    key: str
    value: str


@app.post("/api/settings")
def api_set_setting(body: SettingBody, admin=Depends(require_permission("settings"))):
    db.set_setting(body.key, body.value)
    db.log_admin_action(admin["id"], "setting_change", f"{body.key}={body.value} (پنل وب - {admin['username']})", "setting", body.key)
    return {"ok": True}


# ----------------------------------------------------------------- logs ---


@app.get("/api/admin-logs")
def api_admin_logs(
    page: int = 1, action: Optional[str] = None, record_type: Optional[str] = None,
    record_id: Optional[str] = None, admin=Depends(require_permission("system")),
):
    limit = 40
    rows, total = db.get_admin_logs(
        limit=limit, offset=(page - 1) * limit,
        action=action or None, record_type=record_type or None, record_id=record_id or None,
    )
    return {"items": rows_to_list(rows), "total": total, "page": page, "limit": limit}


@app.get("/api/admin-logs/actions")
def api_admin_log_actions(admin=Depends(require_permission("system"))):
    return {"actions": db.list_admin_log_actions()}


# ----------------------------------------------------------- web admins ---


class WebAdminCreateBody(BaseModel):
    username: str
    password: str
    role: str = "admin"
    permissions: Optional[list] = None


@app.get("/api/web-admins")
def api_web_admins(admin=Depends(require_owner)):
    rows = rows_to_list(db.list_web_admins())
    for r in rows:
        r["permissions"] = db.get_web_admin_permissions(r)
    return rows


@app.get("/api/web-admins/permissions")
def api_web_admin_permission_keys(admin=Depends(require_owner)):
    return {"permissions": list(WEB_ADMIN_PERMISSIONS)}


@app.post("/api/web-admins")
def api_create_web_admin(body: WebAdminCreateBody, admin=Depends(require_owner)):
    if db.get_web_admin_by_username(body.username):
        raise HTTPException(400, "این یوزرنیم قبلاً استفاده شده.")
    if len(body.password) < 8:
        raise HTTPException(400, "پسورد باید حداقل ۸ کاراکتر باشد.")
    new_id = db.create_web_admin(body.username, hash_password(body.password), body.role, body.permissions)
    db.log_admin_action(admin["id"], "web_admin_add", f"{body.username} ({body.role})", "webadmin", new_id)
    return {"id": new_id}


class WebAdminRoleBody(BaseModel):
    role: str


@app.post("/api/web-admins/{admin_id}/role")
def api_set_web_admin_role(admin_id: int, body: WebAdminRoleBody, admin=Depends(require_owner)):
    if not db.set_web_admin_role(admin_id, body.role):
        raise HTTPException(400, "امکان تغییر نقش این حساب نیست.")
    return {"ok": True}


class WebAdminPermissionsBody(BaseModel):
    permissions: list


@app.post("/api/web-admins/{admin_id}/permissions")
def api_set_web_admin_permissions(admin_id: int, body: WebAdminPermissionsBody, admin=Depends(require_owner)):
    if not db.set_web_admin_permissions(admin_id, body.permissions):
        raise HTTPException(400, "امکان تغییر مجوزهای این حساب نیست.")
    db.log_admin_action(admin["id"], "web_admin_permissions", f"admin#{admin_id} -> {body.permissions}", "webadmin", admin_id)
    return {"ok": True}


class WebAdminActiveBody(BaseModel):
    active: bool


@app.post("/api/web-admins/{admin_id}/active")
def api_set_web_admin_active(admin_id: int, body: WebAdminActiveBody, admin=Depends(require_owner)):
    if not db.set_web_admin_active(admin_id, body.active):
        raise HTTPException(400, "امکان تغییر وضعیت این حساب نیست.")
    db.log_admin_action(admin["id"], "web_admin_active", f"admin#{admin_id} -> {body.active}", "webadmin", admin_id)
    return {"ok": True}


@app.delete("/api/web-admins/{admin_id}")
def api_delete_web_admin(admin_id: int, admin=Depends(require_owner)):
    if not db.delete_web_admin(admin_id):
        raise HTTPException(400, "امکان حذف این حساب نیست.")
    db.log_admin_action(admin["id"], "web_admin_delete", f"admin#{admin_id}", "webadmin", admin_id)
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
