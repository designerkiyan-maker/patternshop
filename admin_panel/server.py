# -*- coding: utf-8 -*-
"""
پنل مدیریت وب کاملاً مستقل فروشگاه الگوی خیاطی - خارج از تلگرام.

لاگین با یوزرنیم/پسورد (نه initData). روی دیتابیس بات اصلی کار می‌کند.
اجرا: python -m admin_panel.server (پورت 8002) یا:
    uvicorn admin_panel.server:app --host 127.0.0.1 --port 8002
اولین حساب (owner) را با دستور زیر بساز:
    python -m admin_panel.create_admin <username> <password>
"""

import asyncio
import json
import logging
import os
import time
import tempfile
from datetime import datetime
from typing import Optional

import aiohttp

from fastapi import FastAPI, Request, Response, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from config import DB_PATH, BOT_TOKEN, OWNER_ID, ADMIN_PANEL_SECRET, VAPID_PUBLIC_KEY
from database import Database, WEB_ADMIN_PERMISSIONS, MENU_BUTTON_META
from admin_panel.security import hash_password, verify_password, create_session_token, verify_session_token
from admin_panel.telegram_notify import send_message as tg_send, send_document as tg_send_document, fetch_telegram_file
from admin_panel.config_delivery_web import deliver_pattern_to_user_web
from admin_panel.webpush import PUSH_ENABLED, send_push
from backup import create_backup, restore_backup, is_valid_sqlite_db
import loyalty

logger = logging.getLogger("admin_panel.server")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
COOKIE_NAME = "panel_session"
NOTIFY_POLL_SECONDS = 15

app = FastAPI(title="پنل مدیریت فروشگاه الگوی خیاطی")
db = Database(DB_PATH)
db.init_db(owner_id=OWNER_ID)


def _bot_token() -> str:
    return BOT_TOKEN


def _backup_dir() -> str:
    return os.path.join(os.path.dirname(os.path.abspath(DB_PATH)), "backups")

# ---------------------------------------------------- live push notifier --
# یک تسک پس‌زمینه‌ی سبک که هر چند ثانیه دیتابیس را برای سفارش/شارژ/تیکت جدید
# چک می‌کند و برای ادمین‌های مربوطه Push می‌فرستد؛ چون پنل وب مستقل است و
# instance ای از بات در اختیار ندارد، این ساده‌ترین راه برای تشخیص «جدید بودن»
# یک رکورد بدون دست‌کاری کد بات اصلی است. اگر کلیدهای VAPID تنظیم نشده باشند
# (PUSH_ENABLED=False) این تسک اصلاً استارت نمی‌شود.


async def _notify_admins(permission: str, payload: dict):
    subs = (await asyncio.to_thread(db.list_push_subscriptions_for_permission, permission))
    if not subs:
        return
    gone = []
    for s in subs:
        result = await send_push(s, payload)
        if result == "gone":
            gone.append(s["endpoint"])
    if gone:
        (await asyncio.to_thread(db.delete_push_subscriptions_by_endpoints, gone))


async def _notifier_loop():
    init_orders = (await asyncio.to_thread(db.get_pending_orders))
    init_topups = (await asyncio.to_thread(db.get_pending_topups))
    init_tickets = (await asyncio.to_thread(db.get_all_tickets, "open"))
    last_order_id = max((o["id"] for o in init_orders), default=0)
    last_topup_id = max((t["id"] for t in init_topups), default=0)
    last_ticket_id = max((t["id"] for t in init_tickets), default=0)
    last_support_id = (await asyncio.to_thread(db.get_latest_user_support_message_id))
    while True:
        try:
            all_pending_orders = (await asyncio.to_thread(db.get_pending_orders))
            orders = [o for o in all_pending_orders if o["id"] > last_order_id]
            for o in orders:
                user = (await asyncio.to_thread(db.get_user, o["user_id"]))
                uname = (user["username"] if user else None) or o["user_id"]
                await _notify_admins("orders", {
                    "title": "🛒 سفارش جدید",
                    "body": f"سفارش #{o['id']} از {uname} در انتظار بررسی است.",
                    "tag": "orders",
                })
            if orders:
                last_order_id = max(o["id"] for o in orders)

            all_pending_topups = (await asyncio.to_thread(db.get_pending_topups))
            topups = [t for t in all_pending_topups if t["id"] > last_topup_id]
            for t in topups:
                user = (await asyncio.to_thread(db.get_user, t["user_id"]))
                uname = (user["username"] if user else None) or t["user_id"]
                await _notify_admins("orders", {
                    "title": "💳 درخواست شارژ جدید",
                    "body": f"شارژ #{t['id']} از {uname} به مبلغ {t['amount']:,} تومان.",
                    "tag": "topups",
                })
            if topups:
                last_topup_id = max(t["id"] for t in topups)

            all_open_tickets = (await asyncio.to_thread(db.get_all_tickets, "open"))
            tickets = [tk for tk in all_open_tickets if tk["id"] > last_ticket_id]
            for tk in tickets:
                await _notify_admins("tickets", {
                    "title": "🎫 تیکت جدید",
                    "body": f"تیکت #{tk['id']}: {tk['subject']}",
                    "tag": "tickets",
                })
            if tickets:
                last_ticket_id = max(tk["id"] for tk in tickets)

            latest_support_id = (await asyncio.to_thread(db.get_latest_user_support_message_id))
            if latest_support_id > last_support_id:
                new_msgs = (await asyncio.to_thread(db.get_new_support_messages_since, last_support_id))
                for m in new_msgs:
                    user = (await asyncio.to_thread(db.get_user, m["user_id"]))
                    uname = (user["username"] if user else None) or (user["first_name"] if user else None) or m["user_id"]
                    preview = (m["message"] or "")[:120]
                    await _notify_admins("tickets", {
                        "title": "💬 پیام جدید در چت زنده",
                        "body": f"{uname}: {preview}",
                        "tag": "support",
                    })
                last_support_id = latest_support_id
        except Exception:
            logger.exception("خطا در حلقه‌ی اعلان زنده‌ی پنل وب")
        await asyncio.sleep(NOTIFY_POLL_SECONDS)


# ------------------------------------------------------ server status watch --
# (این بخش در نسخه‌ی فروشگاه الگو حذف شده است؛ اسکن وضعیت سرورها به مدل فروش
# الگوی دیجیتال ارتباطی ندارد.)


@app.on_event("startup")
async def _start_notifier():
    if PUSH_ENABLED:
        asyncio.create_task(_notifier_loop())


# ------------------------------------------------------------------ auth --


class LoginBody(BaseModel):
    username: str
    password: str


async def get_current_admin(request: Request):
    token = request.cookies.get(COOKIE_NAME)
    payload = verify_session_token(ADMIN_PANEL_SECRET, token) if token else None
    if not payload:
        raise HTTPException(401, "نشست منقضی شده یا نامعتبر است.")

    admin = (await asyncio.to_thread(db.get_web_admin, payload["id"]))
    if not admin or not admin["is_active"]:
        raise HTTPException(401, "حساب کاربری غیرفعال یا حذف شده است.")
    return {
        "id": admin["id"],
        "username": admin["username"],
        "role": admin["role"],
        "permissions": (await asyncio.to_thread(db.get_web_admin_permissions, admin)),
        "tenant": "",  # برای سازگاری با فرانت‌اند؛ تننت (نماینده) دیگر وجود ندارد
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
    return {"id": admin["id"], "username": admin["username"], "role": admin["role"], "tenant": ""}


@app.post("/api/logout")
def api_logout(response: Response):
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"ok": True}


@app.get("/api/me")
def api_me(admin=Depends(get_current_admin)):
    return admin


@app.get("/api/notifications/summary")
def api_notifications_summary(admin=Depends(get_current_admin)):
    """شمارش موارد در انتظار برای بج‌های زنده‌ی منو (سفارش/شارژ/تیکت/چت زنده).
    چت زنده مثل تب خودش (role: 'any' در NAV) برای هر ادمین لاگین‌کرده‌ای نمایش
    داده می‌شود، چون خودِ endpointهای /api/support هم به مجوز خاصی گیر نخورده‌اند."""
    out = {}
    if admin["role"] == "owner" or "orders" in admin["permissions"]:
        out["orders"] = len(db.get_pending_orders())
        out["topups"] = len(db.get_pending_topups())
    if admin["role"] == "owner" or "tickets" in admin["permissions"]:
        out["tickets"] = len(db.get_all_tickets("open"))
    out["support"] = db.count_unread_support_conversations()
    return out


# -------------------------------------------------------------- web push --


class PushSubscribeBody(BaseModel):
    endpoint: str
    keys: dict
    user_agent: Optional[str] = None


class PushUnsubscribeBody(BaseModel):
    endpoint: str


@app.get("/api/push/vapid-public-key")
def api_push_vapid_key(admin=Depends(get_current_admin)):
    return {"publicKey": VAPID_PUBLIC_KEY, "enabled": PUSH_ENABLED}


@app.get("/api/push/status")
def api_push_status(endpoint: str, admin=Depends(get_current_admin)):
    """بررسی می‌کند آیا این endpoint واقعاً برای همین ادمین در دیتابیس ذخیره شده یا نه
    (برای تشخیص حالتی که subscription محلی مرورگر با دیتابیس سرور ناهماهنگ شده)."""
    subs = db.list_push_subscriptions_for_admin(admin["id"])
    registered = any(s["endpoint"] == endpoint for s in subs)
    return {"registered": registered}


@app.post("/api/push/subscribe")
def api_push_subscribe(body: PushSubscribeBody, admin=Depends(get_current_admin)):
    if not PUSH_ENABLED:
        raise HTTPException(400, "اعلان Push روی سرور تنظیم نشده است.")
    p256dh = (body.keys or {}).get("p256dh")
    auth = (body.keys or {}).get("auth")
    if not p256dh or not auth:
        raise HTTPException(400, "اطلاعات subscription ناقص است.")
    db.save_push_subscription(admin["id"], body.endpoint, p256dh, auth, body.user_agent)
    return {"ok": True}


@app.post("/api/push/unsubscribe")
def api_push_unsubscribe(body: PushUnsubscribeBody, admin=Depends(get_current_admin)):
    db.delete_push_subscription_by_endpoint(body.endpoint)
    return {"ok": True}


@app.post("/api/push/test")
async def api_push_test(admin=Depends(get_current_admin)):
    if not PUSH_ENABLED:
        raise HTTPException(400, "اعلان Push روی سرور تنظیم نشده است.")
    subs = (await asyncio.to_thread(db.list_push_subscriptions_for_admin, admin["id"]))
    if not subs:
        raise HTTPException(400, "هنوز روی این دستگاه اعلان را فعال نکرده‌ای.")
    sent, gone = 0, []
    for s in subs:
        result = await send_push(s, {
            "title": "🔔 اعلان تست",
            "body": "این یک پیام آزمایشی از پنل مدیریت فروشگاه است.",
            "tag": "test",
        })
        if result == "ok":
            sent += 1
        elif result == "gone":
            gone.append(s["endpoint"])
    if gone:
        (await asyncio.to_thread(db.delete_push_subscriptions_by_endpoints, gone))
    if not sent:
        raise HTTPException(502, "ارسال اعلان تست ناموفق بود.")
    return {"ok": True, "sent": sent}


# --------------------------------------------------------------- helpers --


def row_to_dict(row):
    return dict(row) if row is not None else None


def rows_to_list(rows):
    return [dict(r) for r in rows]


async def notify_user(chat_id: int, text: str):
    asyncio.create_task(tg_send(_bot_token(), chat_id, text))


async def _store_media_via_bot(method: str, field: str, content: bytes, filename: str,
                               caption: str = "", content_type: str = "application/octet-stream") -> Optional[str]:
    """فایل آپلودی ادمین (عکس پیش‌نمایش یا PDF الگو) را برای چت مالک می‌فرستد تا
    تلگرام یک file_id پایدار به آن بدهد (همان مکانیزمی که بات با دریافت مستقیم
    پیام ادمین انجام می‌دهد) و file_id را از پاسخ Bot API استخراج می‌کند؛
    در صورت هر خطایی None برمی‌گرداند."""
    if not _bot_token():
        return None
    url = f"https://api.telegram.org/bot{_bot_token()}/{method}"
    try:
        form = aiohttp.FormData()
        form.add_field("chat_id", str(OWNER_ID))
        if caption:
            form.add_field("caption", caption)
        form.add_field(field, content, filename=filename, content_type=content_type)
        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=form, timeout=aiohttp.ClientTimeout(total=90)) as resp:
                data = await resp.json()
        if not data.get("ok"):
            logger.warning("آپلود %s برای گرفتن file_id ناموفق بود: %s", method, data)
            return None
        result = data.get("result") or {}
        if field == "photo":
            sizes = result.get("photo") or []
            # تلگرام چند سایز از هر عکس می‌دهد؛ آخرین مورد بزرگ‌ترین/باکیفیت‌ترین است
            return sizes[-1]["file_id"] if sizes else None
        return (result.get("document") or {}).get("file_id")
    except Exception:
        logger.exception("آپلود فایل به تلگرام برای گرفتن file_id ناموفق بود.")
        return None


# --------------------------------------------------------------- dashboard --


@app.get("/api/dashboard")
def api_dashboard(start: Optional[str] = None, end: Optional[str] = None, admin=Depends(get_current_admin)):
    return db.get_full_stats(start, end)


# ------------------------------------------------------------------ system --


@app.get("/api/system/stats")
def api_system_stats(admin=Depends(get_current_admin)):
    """وضعیت لحظه‌ای منابع سرور (CPU / RAM / دیسک) برای کارت‌های داشبورد."""
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
    """وضعیت فقط‌خواندنیِ جاب‌های پس‌زمینه. در نسخه‌ی فروشگاه الگو فقط جاب
    «بکاپ خودکار» باقی است (زمان‌بندی‌اش در پردازش بات هاردکد است و از اینجا
    قابل تغییر نیست)."""
    return {
        "backup": {
            "last_run": db.get_setting("_job_backup_last_at", "") or None,
        },
    }


# ------------------------------------------------------------------ backup --

@app.get("/api/system/backup/status")
def api_backup_status(admin=Depends(require_permission("system"))):
    """آخرین وضعیت بکاپ‌ها؛ فقط‌خواندنی، برای نمایش در پنل."""
    backup_dir = _backup_dir()
    if not os.path.isdir(backup_dir):
        return {"last_backup_at": None, "last_backup_size_mb": None, "count": 0}
    files = sorted(
        (f for f in os.listdir(backup_dir) if f.endswith(".db") and not f.startswith("pre_restore_")),
    )
    if not files:
        return {"last_backup_at": None, "last_backup_size_mb": None, "count": 0}
    last_path = os.path.join(backup_dir, files[-1])
    return {
        "last_backup_at": db.get_setting("_job_backup_last_at", "") or None,
        "last_backup_size_mb": round(os.path.getsize(last_path) / (1024 * 1024), 1),
        "count": len(files),
    }


@app.post("/api/system/backup/create")
async def api_backup_create(admin=Depends(require_permission("backup"))):
    """یک بکاپ فوری می‌سازد و به همه‌ی ادمین‌های تلگرامی همین بات ارسال می‌کند."""
    backup_path = await asyncio.to_thread(create_backup, DB_PATH, _backup_dir(), 14)
    if not backup_path:
        raise HTTPException(404, "فایل دیتابیس پیدا نشد.")

    size_mb = round(os.path.getsize(backup_path) / (1024 * 1024), 1)
    caption = f"🗄 بکاپ فوری دیتابیس (پنل وب - {admin['username']})"

    sent, failed = 0, 0
    for admin_tg_id in (await asyncio.to_thread(db.list_admins)):
        ok = await tg_send_document(_bot_token(), admin_tg_id, backup_path, caption)
        sent += 1 if ok else 0
        failed += 0 if ok else 1

    (await asyncio.to_thread(db.set_setting, "_job_backup_last_at", datetime.now().isoformat()))
    (await asyncio.to_thread(db.log_admin_action, 
        admin["id"], "backup_create",
        f"بکاپ فوری ساخته شد ({os.path.basename(backup_path)}, {size_mb} مگابایت) — ارسال به {sent} ادمین "
        f"(پنل وب - {admin['username']})",
    ))
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

    # فایل آپلودی در یک فایل موقتی با نام تصادفیِ سمت سیستم‌عامل ذخیره می‌شود
    # (بدون ساختن مسیر از ورودی کاربر — ضد path traversal)
    tmp_fd, tmp_path = tempfile.mkstemp(prefix="restore_", suffix=".db")
    content = await file.read()
    with os.fdopen(tmp_fd, "wb") as f:
        f.write(content)

    if not is_valid_sqlite_db(tmp_path):
        os.remove(tmp_path)
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
        except OSError:
            pass

    (await asyncio.to_thread(db.log_admin_action, 
        admin["id"], "backup_restore",
        f"دیتابیس از فایل آپلودی بازیابی شد؛ نسخه‌ی قبلی: {os.path.basename(pre_restore_path)} "
        f"(پنل وب - {admin['username']})",
    ))
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
        o["product_name"] = product["name"] if product else "-"
        o["has_files"] = db.has_product_files(o["product_id"]) if o["product_id"] else False
        o["username"] = user["username"] if user else None
        out.append(o)
    return out


@app.get("/api/orders/{order_id}/receipt")
async def api_order_receipt(order_id: int, admin=Depends(get_current_admin)):
    order = (await asyncio.to_thread(db.get_order, order_id))
    if not order or not order["receipt_file_id"]:
        raise HTTPException(404, "رسیدی برای این سفارش ثبت نشده است.")
    result = await fetch_telegram_file(_bot_token(), order["receipt_file_id"])
    if not result:
        raise HTTPException(502, "دریافت رسید از تلگرام ناموفق بود.")
    content, content_type = result
    return Response(content=content, media_type=content_type)


@app.post("/api/orders/{order_id}/approve")
async def api_approve_order(order_id: int, admin=Depends(require_permission("orders"))):
    """تایید سفارش کارت‌به‌کارت: همه‌ی فایل‌های الگوی محصول از بانک فایل خوانده و
    هم در رکورد سفارش ثبت و هم مستقیم برای خریدار ارسال می‌شوند (فروش نامحدود است؛
    هر خریدار همان فایل‌ها را دریافت می‌کند)."""
    order = (await asyncio.to_thread(db.get_order, order_id))
    if not order or order["status"] != "pending":
        raise HTTPException(400, "سفارش یافت نشد یا قبلاً بررسی شده.")

    product = (await asyncio.to_thread(db.get_product, order["product_id"]))
    files = (await asyncio.to_thread(db.get_product_files, order["product_id"]))
    if not files:
        raise HTTPException(409, "هنوز فایلی برای این محصول آپلود نشده است")

    (await asyncio.to_thread(db.approve_order, order_id, [f["id"] for f in files]))
    awarded = 0
    try:
        awarded = await asyncio.to_thread(loyalty.award_purchase, db, order_id)
    except Exception:
        logger.exception("اعطای امتیاز وفاداری سفارش %s ناموفق بود.", order_id)
    (await asyncio.to_thread(db.log_admin_action, 
        admin["id"], "order_approve",
        f"سفارش #{order_id} | کاربر {order['user_id']} | محصول «{product['name'] if product else '---'}» "
        f"| تحویل {len(files)} فایل الگو (پنل وب - {admin['username']})",
        "order", order_id,
    ))
    (await asyncio.to_thread(db.reward_referrer_if_first_purchase,
                             order["user_id"], order["final_price"] or (product["price"] if product else 0)))
    await notify_user(order["user_id"], "✅ خرید شما تایید شد!")
    asyncio.create_task(deliver_pattern_to_user_web(
        _bot_token(), order["user_id"], product["name"] if product else "",
        [f["file_id"] for f in files],
        final_price=order["final_price"], order_id=order_id,
    ))
    response = {"ok": True}
    if awarded > 0:
        response["loyalty_awarded"] = awarded
    return response


@app.post("/api/orders/{order_id}/reject")
async def api_reject_order(order_id: int, admin=Depends(require_permission("orders"))):
    order = (await asyncio.to_thread(db.get_order, order_id))
    if not order or order["status"] != "pending":
        raise HTTPException(400, "سفارش یافت نشد یا قبلاً بررسی شده.")
    (await asyncio.to_thread(db.reject_order, order_id))
    try:
        await asyncio.to_thread(loyalty.reverse_purchase, db, order_id)
    except Exception:
        logger.exception("برگشت امتیاز وفاداری سفارش %s ناموفق بود.", order_id)
    (await asyncio.to_thread(db.log_admin_action, admin["id"], "order_reject", f"سفارش #{order_id} رد شد (پنل وب - {admin['username']})", "order", order_id))
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


@app.get("/api/topups/{topup_id}/receipt")
async def api_topup_receipt(topup_id: int, admin=Depends(get_current_admin)):
    topup = (await asyncio.to_thread(db.get_topup, topup_id))
    if not topup or not topup["receipt_file_id"]:
        raise HTTPException(404, "رسیدی برای این شارژ ثبت نشده است.")
    result = await fetch_telegram_file(_bot_token(), topup["receipt_file_id"])
    if not result:
        raise HTTPException(502, "دریافت رسید از تلگرام ناموفق بود.")
    content, content_type = result
    return Response(content=content, media_type=content_type)


@app.post("/api/topups/{topup_id}/approve")
async def api_approve_topup(topup_id: int, admin=Depends(require_permission("orders"))):
    topup = (await asyncio.to_thread(db.get_topup, topup_id))
    if not topup:
        raise HTTPException(404, "یافت نشد.")
    if not (await asyncio.to_thread(db.approve_topup, topup_id)):
        raise HTTPException(400, "قبلاً بررسی شده است.")
    (await asyncio.to_thread(db.log_admin_action, admin["id"], "topup_approve", f"شارژ #{topup_id} تایید شد (پنل وب - {admin['username']})", "topup", topup_id))
    await notify_user(topup["user_id"], f"✅ شارژ کیف پول شما به مبلغ {topup['amount']:,} تومان تایید شد.")
    return {"ok": True}


@app.post("/api/topups/{topup_id}/reject")
async def api_reject_topup(topup_id: int, admin=Depends(require_permission("orders"))):
    topup = (await asyncio.to_thread(db.get_topup, topup_id))
    if not topup or topup["status"] != "pending":
        raise HTTPException(400, "یافت نشد یا قبلاً بررسی شده.")
    (await asyncio.to_thread(db.reject_topup, topup_id))
    (await asyncio.to_thread(db.log_admin_action, admin["id"], "topup_reject", f"شارژ #{topup_id} رد شد (پنل وب - {admin['username']})", "topup", topup_id))
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
    loyalty_summary = None
    try:
        s = loyalty.get_summary(db, tg_id)
        loyalty_summary = {
            "points": s["current"],
            "tier": s["tier"]["name"] if s["tier"] else None,
            "lifetime_earned": s["lifetime_earned"],
            "lifetime_spent": s["lifetime_spent"],
        }
    except Exception:
        logger.exception("خلاصه‌ی باشگاه وفاداری کاربر %s دریافت نشد.", tg_id)
    return {
        "user": dict(user),
        "orders": rows_to_list(history["orders"]),
        "topups": rows_to_list(history["topups"]),
        "referral": db.get_referral_stats(tg_id),
        "loyalty": loyalty_summary,
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
    (await asyncio.to_thread(db.add_wallet_credit, tg_id, body.delta))
    (await asyncio.to_thread(db.log_admin_action, 
        admin["id"], "wallet_adjust", f"کیف پول کاربر {tg_id} به میزان {body.delta:,} تغییر کرد (پنل وب - {admin['username']})",
        "user", tg_id,
    ))
    if body.delta:
        sign = "افزایش" if body.delta > 0 else "کاهش"
        await notify_user(tg_id, f"💰 موجودی کیف پول شما {sign} یافت: {abs(body.delta):,} تومان")
    return {"ok": True}


class LoyaltyAdjustBody(BaseModel):
    amount: int
    reason: str


@app.post("/api/users/{tg_id}/loyalty")
async def api_adjust_loyalty(tg_id: int, body: LoyaltyAdjustBody, admin=Depends(require_permission("users"))):
    if body.amount == 0:
        raise HTTPException(400, "مقدار تعدیل نمی‌تواند صفر باشد.")
    reason = (body.reason or "").strip()
    if not reason:
        raise HTTPException(400, "دلیل تعدیل الزامی است.")
    if (await asyncio.to_thread(db.get_user, tg_id)) is None:
        raise HTTPException(404, "کاربری با این آیدی پیدا نشد.")
    try:
        new_balance = (await asyncio.to_thread(
            loyalty.admin_adjust, db, admin["id"], tg_id, body.amount, reason,
        ))
    except loyalty.LoyaltyError as e:
        raise HTTPException(400, str(e))
    (await asyncio.to_thread(
        db.log_admin_action,
        admin["id"], "loyalty_adjust",
        f"کاربر {tg_id} | {body.amount:+d} | دلیل: {reason} (پنل وب - {admin['username']})",
        "user", tg_id,
    ))
    return {"ok": True, "new_balance": int(new_balance)}


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


@app.get("/api/products")
def api_products(admin=Depends(get_current_admin)):
    products = rows_to_list(db.get_all_products())
    for p in products:
        # فروش نامحدود است؛ فقط کافی است حداقل یک فایل الگو برای محصول ثبت شده باشد
        p["has_files"] = db.has_product_files(p["id"])
    return products


@app.post("/api/products")
def api_add_product(body: ProductBody, admin=Depends(require_permission("catalog"))):
    pid = db.add_product(body.category_id, body.name, body.price, body.description)
    db.log_admin_action(admin["id"], "product_add", f"{body.name} (پنل وب - {admin['username']})", "product", pid)
    return {"id": pid}


class ProductEditBody(BaseModel):
    name: Optional[str] = None
    price: Optional[int] = None
    description: Optional[str] = None


@app.put("/api/products/{product_id}")
def api_edit_product(product_id: int, body: ProductEditBody, admin=Depends(require_permission("catalog"))):
    db.edit_product(product_id, body.name, body.price, body.description)
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


# ----------------------------------------------------- بانک فایل‌های الگو --


@app.get("/api/products/{product_id}/files")
def api_product_files(product_id: int, admin=Depends(require_permission("catalog"))):
    """لیست فایل‌های الگوی یک محصول (id رکورد، file_id تلگرام، تاریخ)."""
    product = db.get_product(product_id)
    if not product:
        raise HTTPException(404, "محصول یافت نشد.")
    return {"items": db.get_product_files(product_id), "count": db.count_product_files(product_id)}


@app.post("/api/products/{product_id}/files")
async def api_add_product_file(product_id: int, file: UploadFile = File(...), admin=Depends(require_permission("catalog"))):
    """آپلود فایل الگو (PDF و ...) از مرورگر: فایل برای چت مالک فرستاده می‌شود تا
    تلگرام file_id پایدار بدهد و همان file_id در بانک فایل محصول ذخیره شود."""
    product = db.get_product(product_id)
    if not product:
        raise HTTPException(404, "محصول یافت نشد.")
    content = await file.read()
    if not content:
        raise HTTPException(400, "فایل خالی است.")
    if len(content) > 50 * 1024 * 1024:
        raise HTTPException(400, "حجم فایل نباید بیشتر از ۵۰ مگابایت باشد (محدودیت تلگرام).")

    caption = f"📁 فایل الگوی «{product['name']}» (ذخیره خودکار پنل وب)"
    file_id = await _store_media_via_bot(
        "sendDocument", "document", content,
        filename=file.filename or "pattern.pdf", caption=caption,
    )
    if not file_id:
        raise HTTPException(502, "ارسال فایل به تلگرام ناموفق بود؛ دوباره تلاش کنید.")

    added, duplicates = db.add_product_files(product_id, [file_id])
    db.log_admin_action(
        admin["id"], "product_file_add",
        f"فایل الگو به محصول «{product['name']}» (پنل وب - {admin['username']})", "product", product_id,
    )
    return {"ok": True, "file_id": file_id, "added": added, "duplicates": duplicates}


@app.delete("/api/files/{file_id}")
def api_delete_product_file(file_id: str, admin=Depends(require_permission("catalog"))):
    """حذف یک فایل الگو از بانک (بر اساس file_id تلگرام)."""
    if not db.delete_product_file(file_id):
        raise HTTPException(404, "فایل یافت نشد.")
    db.log_admin_action(admin["id"], "product_file_delete", "حذف فایل الگو (پنل وب)", "product_file", file_id)
    return {"ok": True}


# ------------------------------------------------------ بانک الگوی نمونه --


@app.get("/api/sample-files")
def api_sample_files(admin=Depends(require_permission("catalog"))):
    return db.get_sample_files()


@app.post("/api/sample-files")
async def api_add_sample_file(file: UploadFile = File(...), admin=Depends(require_permission("catalog"))):
    """آپلود الگوی نمونه‌ی رایگان (که دکمه‌ی «الگوی نمونه رایگان» بات می‌فرستد)."""
    content = await file.read()
    if not content:
        raise HTTPException(400, "فایل خالی است.")
    if len(content) > 50 * 1024 * 1024:
        raise HTTPException(400, "حجم فایل نباید بیشتر از ۵۰ مگابایت باشد (محدودیت تلگرام).")

    file_id = await _store_media_via_bot(
        "sendDocument", "document", content,
        filename=file.filename or "sample.pdf", caption="🧪 فایل الگوی نمونه (ذخیره خودکار پنل وب)",
    )
    if not file_id:
        raise HTTPException(502, "ارسال فایل به تلگرام ناموفق بود؛ دوباره تلاش کنید.")

    added, duplicates = db.add_sample_files([file_id])
    db.log_admin_action(admin["id"], "sample_file_add", f"الگوی نمونه (پنل وب - {admin['username']})")
    return {"ok": True, "file_id": file_id, "added": added, "duplicates": duplicates}


@app.delete("/api/sample-files/{file_id}")
def api_delete_sample_file(file_id: str, admin=Depends(require_permission("catalog"))):
    if not db.delete_sample_file(file_id):
        raise HTTPException(404, "فایل یافت نشد.")
    db.log_admin_action(admin["id"], "sample_file_delete", "حذف الگوی نمونه (پنل وب)")
    return {"ok": True}


# ---------------------------------------------------------- پیش‌نمایش محصول --


@app.post("/api/products/{product_id}/preview")
async def api_upload_product_preview(product_id: int, photo: UploadFile = File(...), admin=Depends(require_permission("catalog"))):
    """آپلود عکس پیش‌نمایش الگو: عکس برای چت مالک فرستاده می‌شود و file_id حاصل
    در ستون preview_file_id محصول ذخیره می‌شود (همان عکسی که در کاتالوگ دیده می‌شود)."""
    product = db.get_product(product_id)
    if not product:
        raise HTTPException(404, "محصول یافت نشد.")
    if not photo.content_type or not photo.content_type.startswith("image/"):
        raise HTTPException(400, "فقط فایل تصویری مجاز است.")
    content = await photo.read()
    if not content:
        raise HTTPException(400, "تصویر خالی است.")
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(400, "حجم تصویر نباید بیشتر از ۱۰ مگابایت باشد.")

    file_id = await _store_media_via_bot(
        "sendPhoto", "photo", content,
        filename=photo.filename or "preview.jpg", content_type=photo.content_type,
        caption=f"🖼 پیش‌نمایش الگوی «{product['name']}» (ذخیره خودکار پنل وب)",
    )
    if not file_id:
        raise HTTPException(502, "ارسال تصویر به تلگرام ناموفق بود؛ دوباره تلاش کنید.")

    db.edit_product(product_id, preview_file_id=file_id)
    db.log_admin_action(
        admin["id"], "product_preview_set",
        f"پیش‌نمایش محصول «{product['name']}» (پنل وب - {admin['username']})", "product", product_id,
    )
    return {"ok": True, "file_id": file_id}


@app.get("/api/products/{product_id}/preview")
async def api_product_preview(product_id: int, admin=Depends(get_current_admin)):
    """نمایش عکس پیش‌نمایش محصول در مرورگر ادمین (پروکسی getFile تلگرام)."""
    product = db.get_product(product_id)
    if not product or not product["preview_file_id"]:
        raise HTTPException(404, "پیش‌نمایشی برای این محصول ثبت نشده است.")
    result = await fetch_telegram_file(_bot_token(), product["preview_file_id"])
    if not result:
        raise HTTPException(502, "دریافت پیش‌نمایش از تلگرام ناموفق بود.")
    content, content_type = result
    return Response(content=content, media_type=content_type, headers={"Cache-Control": "private, max-age=300"})


@app.get("/api/files/{file_id}")
async def api_stream_product_file(file_id: str, admin=Depends(require_permission("catalog"))):
    """نمایش/دانلود محتوای یک فایل الگو در مرورگر ادمین (پروکسی getFile تلگرام).
    فقط برای ادمین‌های با مجوز «catalog» - چون فایل الگو خودِ محصولِ قابل‌فروش است."""
    result = await fetch_telegram_file(_bot_token(), file_id)
    if not result:
        raise HTTPException(502, "دریافت فایل از تلگرام ناموفق بود.")
    content, content_type = result
    return Response(content=content, media_type=content_type)


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
    ticket = (await asyncio.to_thread(db.get_ticket, ticket_id))
    if not ticket:
        raise HTTPException(404, "یافت نشد.")
    (await asyncio.to_thread(db.claim_ticket_if_open, ticket_id, admin["id"]))
    (await asyncio.to_thread(db.add_ticket_message, ticket_id, "admin", body.message))
    await notify_user(ticket["user_id"], f"📩 پاسخ پشتیبانی برای تیکت «{ticket['subject']}»:\n\n{body.message}")
    (await asyncio.to_thread(db.log_admin_action, admin["id"], "ticket_reply", f"تیکت #{ticket_id} (پنل وب - {admin['username']})", "ticket", ticket_id))
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

    user_ids = (await asyncio.to_thread(db.get_all_user_ids))
    sem = asyncio.Semaphore(20)
    counters = {"success": 0, "failed": 0}

    async def _send(uid):
        async with sem:
            ok = await tg_send(_bot_token(), uid, text)
            counters["success" if ok else "failed"] += 1

    await asyncio.gather(*[_send(uid) for uid in user_ids])
    (await asyncio.to_thread(db.log_admin_action, 
        admin["id"], "broadcast",
        f"ارسال به {len(user_ids)} کاربر | موفق: {counters['success']} | ناموفق: {counters['failed']} "
        f"(پنل وب - {admin['username']})",
    ))
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
    user = (await asyncio.to_thread(db.get_user, user_id))
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
    conv = (await asyncio.to_thread(db.get_support_conversation, user_id))
    assigned = conv["assigned_admin_id"] if conv else None
    if assigned and assigned != my_lock_id and not is_owner:
        raise HTTPException(
            403,
            f"این گفتگو در حال حاضر توسط {_support_lock_label(assigned)} در حال پاسخ‌دهی است.",
        )
    if not is_owner:
        (await asyncio.to_thread(db.set_support_conversation_admin, user_id, my_lock_id))

    msg_id = (await asyncio.to_thread(db.add_support_message, user_id, "admin", text))
    await notify_user(user_id, f"💬 پشتیبانی:\n\n{text}")
    (await asyncio.to_thread(db.log_admin_action, admin["id"], "support_reply", f"پاسخ چت زنده به کاربر {user_id} (پنل وب - {admin['username']})", "user", user_id))
    return {"ok": True, "id": msg_id}


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


# --------------------------------------------------- تنظیمات کامل فروش -----
# این بخش‌ها قبلاً فقط از داخل ربات یا مینی‌اپ قابل تنظیم بودند و در پنل وب
# مستقل اصلاً وجود نداشتند (رفرال، گردونه‌شانس، عضویت اجباری کانال). این‌جا
# برای هماهنگی کامل با ربات و مینی‌اپ اضافه شده‌اند.


class ReferralSettingsBody(BaseModel):
    enabled: bool
    percent: int
    commission_max_count: int = 0
    free_config_enabled: bool = False
    free_config_threshold: int = 10
    free_config_product_id: Optional[int] = None
    invite_bonus_enabled: bool = False
    invite_bonus_amount: int = 0
    invite_bonus_max_count: int = 0


@app.get("/api/settings/referral")
def api_get_referral_settings(admin=Depends(require_permission("settings"))):
    fc_product_id = db.get_setting("referral_free_config_product_id", "") or ""
    return {
        "enabled": db.get_setting("referral_enabled", "1") == "1",
        "percent": int(db.get_setting("referral_percent", "10") or 0),
        "commission_max_count": int(db.get_setting("referral_commission_max_count", "0") or 0),
        "free_config_enabled": db.get_setting("referral_free_config_enabled", "0") == "1",
        "free_config_threshold": int(db.get_setting("referral_free_config_threshold", "10") or 0),
        "free_config_product_id": int(fc_product_id) if fc_product_id else None,
        "invite_bonus_enabled": db.get_setting("referral_invite_bonus_enabled", "0") == "1",
        "invite_bonus_amount": int(db.get_setting("referral_invite_bonus_amount", "0") or 0),
        "invite_bonus_max_count": int(db.get_setting("referral_invite_bonus_max_count", "0") or 0),
    }


@app.post("/api/settings/referral")
def api_set_referral_settings(body: ReferralSettingsBody, admin=Depends(require_permission("settings"))):
    if body.percent < 0 or body.percent > 100:
        raise HTTPException(400, "درصد باید بین ۰ تا ۱۰۰ باشد.")
    if body.commission_max_count < 0:
        raise HTTPException(400, "سقف تعداد نفرات نمی‌تواند منفی باشد.")
    if body.free_config_threshold < 0 or body.invite_bonus_amount < 0 or body.invite_bonus_max_count < 0:
        raise HTTPException(400, "مقادیر عددی نمی‌توانند منفی باشند.")

    product = None
    if body.free_config_product_id:
        product = db.get_product(body.free_config_product_id)
        if not product:
            raise HTTPException(400, "محصول جایزه یافت نشد.")
    if body.free_config_enabled and (not body.free_config_product_id or body.free_config_threshold < 1):
        raise HTTPException(400, "برای فعال‌سازی الگوی جایزه، محصول جایزه و آستانه‌ی معتبر (حداقل ۱) لازم است.")
    if body.invite_bonus_enabled and body.invite_bonus_amount <= 0:
        raise HTTPException(400, "برای فعال‌سازی شارژ به‌ازای دعوت، مبلغ باید بزرگ‌تر از صفر باشد.")

    db.set_setting("referral_enabled", "1" if body.enabled else "0")
    db.set_setting("referral_percent", str(body.percent))
    db.set_setting("referral_commission_max_count", str(body.commission_max_count))
    db.set_setting("referral_free_config_enabled", "1" if body.free_config_enabled else "0")
    db.set_setting("referral_free_config_threshold", str(body.free_config_threshold))
    db.set_setting("referral_free_config_product_id", str(body.free_config_product_id) if body.free_config_product_id else "")
    db.set_setting("referral_invite_bonus_enabled", "1" if body.invite_bonus_enabled else "0")
    db.set_setting("referral_invite_bonus_amount", str(body.invite_bonus_amount))
    db.set_setting("referral_invite_bonus_max_count", str(body.invite_bonus_max_count))
    db.log_admin_action(admin["id"], "setting_change", f"referral settings (پنل وب - {admin['username']})", "setting", "referral")
    return {"ok": True}


class WheelSettingsBody(BaseModel):
    enabled: bool
    win_percent: int
    prizes: list[int]
    expiry_hours: int
    cooldown_hours: int


@app.get("/api/settings/wheel")
def api_get_wheel_settings(admin=Depends(require_permission("settings"))):
    return db.get_wheel_settings()


@app.post("/api/settings/wheel")
def api_set_wheel_settings(body: WheelSettingsBody, admin=Depends(require_permission("settings"))):
    if body.win_percent < 0 or body.win_percent > 100:
        raise HTTPException(400, "درصد برد باید بین ۰ تا ۱۰۰ باشد.")
    if not body.prizes or any(p <= 0 for p in body.prizes):
        raise HTTPException(400, "حداقل یک جایزه‌ی معتبر (بزرگ‌تر از صفر) لازم است.")
    if body.expiry_hours <= 0 or body.cooldown_hours <= 0:
        raise HTTPException(400, "مقادیر ساعت باید بزرگ‌تر از صفر باشند.")
    db.set_setting("wheel_enabled", "1" if body.enabled else "0")
    db.set_setting("wheel_win_percent", str(body.win_percent))
    db.set_wheel_prizes(body.prizes)
    db.set_setting("wheel_code_expiry_hours", str(body.expiry_hours))
    db.set_setting("wheel_cooldown_hours", str(body.cooldown_hours))
    db.log_admin_action(admin["id"], "setting_change", f"wheel updated (پنل وب - {admin['username']})", "setting", "wheel")
    return {"ok": True}


# ---------------------------------------------------- باشگاه مشتریان -------
# تنظیمات امتیاز وفاداری؛ همان کلیدهایی که سرویس loyalty.py می‌خواند تا ربات،
# مینی‌اپ و پنل وب همیشه یک منبع حقیقت مشترک داشته باشند.


class LoyaltyTierBody(BaseModel):
    name: str
    min: int
    mult: int


class LoyaltySettingsBody(BaseModel):
    enabled: bool
    points_per_toman: int
    reg_bonus: int
    referral_bonus: int
    redeem_points: int
    redeem_toman: int
    min_redeem: int
    max_per_order: int
    tiers: list[LoyaltyTierBody]


@app.get("/api/settings/loyalty")
def api_get_loyalty_settings(admin=Depends(require_permission("settings"))):
    return {
        "enabled": db.get_setting("loyalty_enabled", "1") == "1",
        "points_per_toman": int(db.get_setting("loyalty_points_per_toman", "10000") or 0),
        "reg_bonus": int(db.get_setting("loyalty_reg_bonus", "0") or 0),
        "referral_bonus": int(db.get_setting("loyalty_referral_bonus", "0") or 0),
        "redeem_points": int(db.get_setting("loyalty_redeem_points", "100") or 0),
        "redeem_toman": int(db.get_setting("loyalty_redeem_toman", "0") or 0),
        "min_redeem": int(db.get_setting("loyalty_min_redeem", "0") or 0),
        "max_per_order": int(db.get_setting("loyalty_max_per_order", "0") or 0),
        "tiers": loyalty.load_tiers(db),
    }


@app.post("/api/settings/loyalty")
def api_set_loyalty_settings(body: LoyaltySettingsBody, admin=Depends(require_permission("settings"))):
    if body.points_per_toman < 1:
        raise HTTPException(400, "نرخ امتیاز باید حداقل ۱ باشد.")
    if body.reg_bonus < 0 or body.referral_bonus < 0 or body.min_redeem < 0 or body.max_per_order < 0:
        raise HTTPException(400, "مقادیر عددی نمی‌توانند منفی باشند.")
    if body.redeem_points < 1 or body.redeem_toman < 1:
        raise HTTPException(400, "نرخ تبدیل امتیاز باید حداقل ۱ امتیاز و ۱ تومان باشد.")

    if not body.tiers:
        raise HTTPException(400, "حداقل یک سطح لازم است.")
    for t in body.tiers:
        if not t.name.strip():
            raise HTTPException(400, "نام سطح نمی‌تواند خالی باشد.")
        if t.min < 0 or t.mult < 1:
            raise HTTPException(400, "آستانه و ضریب سطح‌ها باید معتبر باشند (آستانه ≥ ۰ و ضریب ≥ ۱).")
    sorted_tiers = sorted(body.tiers, key=lambda t: t.min)
    if sorted_tiers[0].min != 0:
        raise HTTPException(400, "کم‌ترین سطح باید آستانه‌ی صفر داشته باشد.")
    mins = [t.min for t in sorted_tiers]
    if len(set(mins)) != len(mins):
        raise HTTPException(400, "آستانه‌ی سطح‌ها نباید تکراری باشد.")

    tiers_out = [
        {"id": f"t{i}", "name": t.name.strip(), "min": t.min, "mult": t.mult}
        for i, t in enumerate(sorted_tiers)
    ]
    db.set_setting("loyalty_enabled", "1" if body.enabled else "0")
    db.set_setting("loyalty_points_per_toman", str(body.points_per_toman))
    db.set_setting("loyalty_reg_bonus", str(body.reg_bonus))
    db.set_setting("loyalty_referral_bonus", str(body.referral_bonus))
    db.set_setting("loyalty_redeem_points", str(body.redeem_points))
    db.set_setting("loyalty_redeem_toman", str(body.redeem_toman))
    db.set_setting("loyalty_min_redeem", str(body.min_redeem))
    db.set_setting("loyalty_max_per_order", str(body.max_per_order))
    db.set_setting("loyalty_tiers", json.dumps(tiers_out, ensure_ascii=False))
    db.log_admin_action(admin["id"], "loyalty_settings", f"باشگاه مشتریان به‌روزرسانی شد (پنل وب - {admin['username']})", "setting", "loyalty")
    return {"ok": True}


class ForceJoinSettingsBody(BaseModel):
    enabled: bool
    channel: str = ""


@app.get("/api/settings/force-join")
def api_get_force_join_settings(admin=Depends(require_permission("settings"))):
    return db.get_force_join_settings()


@app.post("/api/settings/force-join")
def api_set_force_join_settings(body: ForceJoinSettingsBody, admin=Depends(require_permission("settings"))):
    channel = (body.channel or "").strip()
    if body.enabled and not channel:
        raise HTTPException(400, "برای فعال‌سازی، آیدی کانال الزامی است.")
    db.set_setting("force_join_enabled", "1" if body.enabled else "0")
    db.set_setting("force_join_channel", channel)
    db.log_admin_action(admin["id"], "setting_change", f"force_join_channel={channel} (پنل وب - {admin['username']})", "setting", "force_join")
    return {"ok": True}


# ------------------------------------------------------------- menu order --


@app.get("/api/settings/menu-order")
def api_menu_order_get(admin=Depends(require_permission("settings"))):
    settings = db.get_all_settings()
    order = db.get_menu_order()
    row_breaks = db.get_menu_row_breaks()
    break_set = set(row_breaks) if row_breaks is not None else None
    result = []
    for key in order:
        meta = MENU_BUTTON_META.get(key)
        if not meta:
            continue
        item = {
            "key": key, "label": meta["label"], "admin_only": meta["admin_only"],
            "togglable": meta["toggle_key"] is not None,
        }
        if meta["toggle_key"]:
            item["enabled"] = settings.get(meta["toggle_key"], "1") == "1"
        # break_before یعنی این دکمه یک ردیف تازه در منو شروع می‌کند (کنار دکمه‌ی
        # قبلی‌اش قرار نمی‌گیرد). اگر کاربر هنوز چیدمان سفارشی نساخته باشد
        # (break_set is None)، null برمی‌گردد تا فرانت‌اند بداند هنوز از حالت
        # قدیمی «تعداد ستون ثابت» استفاده می‌شود.
        item["break_before"] = (key in break_set) if break_set is not None else None
        result.append(item)
    return result


class MenuButtonToggle(BaseModel):
    key: str
    enabled: bool


def _apply_menu_button_toggles(buttons: Optional[list[MenuButtonToggle]]):
    for btn in buttons or []:
        meta = MENU_BUTTON_META.get(btn.key)
        if meta and meta["toggle_key"]:
            db.set_setting(meta["toggle_key"], "1" if btn.enabled else "0")


class MenuOrderBody(BaseModel):
    order: list[str]
    buttons: Optional[list[MenuButtonToggle]] = None


@app.post("/api/settings/menu-order")
def api_menu_order_set(body: MenuOrderBody, admin=Depends(require_permission("settings"))):
    db.set_menu_order(body.order)
    _apply_menu_button_toggles(body.buttons)
    db.log_admin_action(admin["id"], "menu_order_change", f"ترتیب منوی ربات تغییر کرد (پنل وب - {admin['username']})", "setting", "menu_order")
    return {"ok": True}


class MenuLayoutBody(BaseModel):
    order: list[str]
    breaks: list[str]
    buttons: Optional[list[MenuButtonToggle]] = None


@app.post("/api/settings/menu-layout")
def api_menu_layout_set(body: MenuLayoutBody, admin=Depends(require_permission("settings"))):
    """مثل /settings/menu-order ولی علاوه بر ترتیب، چیدمان ردیف‌ها (کدام دکمه‌ها
    کنار هم و کدام‌ها در ردیف جدا قرار بگیرند) را هم ذخیره می‌کند - یعنی چیدمان
    آزاد (نه فقط بالا/پایین با تعداد ستون ثابت)."""
    db.set_menu_order(body.order)
    db.set_menu_row_breaks(body.breaks)
    _apply_menu_button_toggles(body.buttons)
    db.log_admin_action(admin["id"], "menu_order_change", f"چیدمان منوی ربات تغییر کرد (پنل وب - {admin['username']})", "setting", "menu_order")
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
        r.pop("password_hash", None)
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


# ------------------------------------------------------- telegram admins ---
# مدیریت ادمین‌های تلگرامی (جدول admins) — فقط مالک؛ دقیقاً مثل خود ربات.


class TelegramAdminBody(BaseModel):
    telegram_id: int
    role: str = "admin"


@app.get("/api/telegram-admins")
def api_telegram_admins(admin=Depends(require_owner)):
    return db.list_admins_with_roles()


@app.post("/api/telegram-admins")
def api_add_telegram_admin(body: TelegramAdminBody, admin=Depends(require_owner)):
    if body.role not in ("admin", "mid", "support"):
        raise HTTPException(400, "نقش باید یکی از مقادیر admin، mid یا support باشد.")
    existing = {a["telegram_id"] for a in db.list_admins_with_roles()}
    if body.telegram_id in existing:
        raise HTTPException(400, "این آیدی از قبل ادمین است.")
    db.add_admin(body.telegram_id, body.role)
    db.log_admin_action(admin["id"], "tg_admin_add", f"ادمین تلگرام {body.telegram_id} با نقش {body.role} اضافه شد (پنل وب - {admin['username']})", "tg_admin", body.telegram_id)
    return {"ok": True}


class TelegramAdminRoleBody(BaseModel):
    role: str


@app.post("/api/telegram-admins/{tg_id}/role")
def api_set_telegram_admin_role(tg_id: int, body: TelegramAdminRoleBody, admin=Depends(require_owner)):
    if not db.set_admin_role(tg_id, body.role):
        raise HTTPException(400, "این ادمین قابل تغییر نیست یا وجود ندارد.")
    db.log_admin_action(admin["id"], "tg_admin_role", f"نقش ادمین تلگرام {tg_id} به {body.role} تغییر کرد (پنل وب - {admin['username']})", "tg_admin", tg_id)
    return {"ok": True}


@app.delete("/api/telegram-admins/{tg_id}")
def api_remove_telegram_admin(tg_id: int, admin=Depends(require_owner)):
    if not db.remove_admin(tg_id, protected_owner_id=OWNER_ID):
        raise HTTPException(400, "مالک قابل حذف نیست.")
    db.log_admin_action(admin["id"], "tg_admin_remove", f"ادمین تلگرام {tg_id} حذف شد (پنل وب - {admin['username']})", "tg_admin", tg_id)
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


@app.get("/sw.js")
def serve_service_worker():
    # عمداً روی ریشه‌ی دامنه سرو می‌شود (نه زیر /assets) تا scope پیش‌فرض
    # Service Worker کل پنل را بگیرد و بتواند برای هر صفحه‌ای اعلان Push نشان دهد.
    return FileResponse(os.path.join(STATIC_DIR, "sw.js"), media_type="application/javascript")


@app.get("/manifest.json")
def serve_manifest(request: Request):
    """Web App Manifest برای قابلیت نصب (Add to Home Screen / PWA) روی اندروید
    و آیفون. index.html این مسیر را با همان query string صفحه‌ی جاری صدا می‌زند."""
    start_url = "/?source=pwa"
    manifest = {
        "name": "پنل مدیریت فروشگاه الگو",
        "short_name": "پنل الگو",
        "description": "پنل مدیریت وب فروشگاه الگوی خیاطی",
        "start_url": start_url,
        "scope": "/",
        "display": "standalone",
        "orientation": "portrait-primary",
        "background_color": "#0B0C14",
        "theme_color": "#0B0C14",
        "dir": "rtl",
        "lang": "fa",
        "icons": [
            {"src": "/assets/icons/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any"},
            {"src": "/assets/icons/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any"},
            {"src": "/assets/icons/icon-maskable-192.png", "sizes": "192x192", "type": "image/png", "purpose": "maskable"},
            {"src": "/assets/icons/icon-maskable-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
        ],
    }
    return JSONResponse(manifest, media_type="application/manifest+json")


def _asset_version(filename: str) -> int:
    try:
        return int(os.path.getmtime(os.path.join(STATIC_DIR, filename)))
    except OSError:
        return int(time.time())


def _bust_asset_cache(html: str) -> str:
    # کش‌شکن خودکار: هر بار app.js یا style.css عوض شود mtime‌شان هم عوض
    # می‌شود، پس مرورگر دیگر نسخه‌ی قدیمیِ کش‌شده را اجرا نمی‌کند — بدون
    # نیاز به دستی زیاد کردن شماره‌ی ورژن در هر دیپلوی.
    html = html.replace('src="/assets/app.js"', f'src="/assets/app.js?v={_asset_version("app.js")}"')
    html = html.replace('href="/assets/style.css"', f'href="/assets/style.css?v={_asset_version("style.css")}"')
    return html


@app.get("/", response_class=HTMLResponse)
def serve_index():
    with open(os.path.join(STATIC_DIR, "index.html"), "r", encoding="utf-8") as f:
        html = f.read()
    # کش‌شکن خودکار: هر بار app.js عوض شود mtime آن هم عوض می‌شود، پس
    # مرورگر دیگر نسخه‌ی قدیمیِ کش‌شده را اجرا نمی‌کند و مجبور به دانلود
    # مجدد است — بدون نیاز به دستی زیاد کردن شماره‌ی ورژن در هر دیپلوی.
    return _bust_asset_cache(html)


@app.get("/setup", response_class=HTMLResponse)
def serve_setup_page():
    """مسیر قدیمی؛ همان SPA سرو می‌شود تا رفرش صفحه‌ی لینک‌های قدیمی ۴۰۴ ندهد."""
    with open(os.path.join(STATIC_DIR, "index.html"), "r", encoding="utf-8") as f:
        html = f.read()
    return _bust_asset_cache(html)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8002)

