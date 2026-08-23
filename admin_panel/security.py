# -*- coding: utf-8 -*-
"""
هش کردن پسورد و ساخت/بررسی توکن نشست (session) پنل وب مستقل.
عمداً بدون هیچ وابستگی خارجی (فقط hashlib/hmac استاندارد پایتون) تا نیازی
به نصب پکیج اضافه روی سرور کاربر نباشد.
"""

import base64
import hashlib
import hmac
import json
import os
import time

PBKDF2_ITERATIONS = 260_000


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return f"{salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt_hex, hash_hex = stored.split("$", 1)
    except ValueError:
        return False
    salt = bytes.fromhex(salt_hex)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return hmac.compare_digest(dk.hex(), hash_hex)


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def create_session_token(secret_key: str, admin_id: int, username: str, role: str, hours: int = 12,
                          tenant: str = "") -> str:
    payload = {
        "id": admin_id,
        "u": username,
        "r": role,
        "b": tenant,  # شناسه/اسلاگ تننت (نماینده)؛ خالی یعنی بات اصلی. منبع اعتبار تننت همین payload است نه پارامتر URL.
        "exp": int(time.time()) + hours * 3600,
    }
    body = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    sig = hmac.new(secret_key.encode("utf-8"), body.encode("ascii"), hashlib.sha256).hexdigest()
    return f"{body}.{sig}"


def verify_session_token(secret_key: str, token: str):
    """توکن معتبر را به‌صورت dict برمی‌گرداند؛ در غیر این صورت None."""
    if not token or "." not in token:
        return None
    body, _, sig = token.partition(".")
    expected_sig = hmac.new(secret_key.encode("utf-8"), body.encode("ascii"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected_sig, sig):
        return None
    try:
        payload = json.loads(_b64url_decode(body))
    except Exception:
        return None
    if payload.get("exp", 0) < time.time():
        return None
    return payload
