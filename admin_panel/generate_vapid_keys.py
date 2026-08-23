# -*- coding: utf-8 -*-
"""
یک‌بار اجرا کن تا کلیدهای VAPID لازم برای اعلان‌های Push پنل وب ساخته شوند:

    python -m admin_panel.generate_vapid_keys

خروجی را داخل فایل .env (کنار BOT_TOKEN) کپی کن:

    VAPID_PUBLIC_KEY=...
    VAPID_PRIVATE_KEY=...

بعد از اضافه‌کردن، پروسه‌ی پنل وب (uvicorn admin_panel.server:app) را ری‌استارت کن.
این کلیدها باید ثابت بمانند؛ اگر دوباره تولیدشان کنی، تمام دستگاه‌هایی که قبلاً
اعلان را روی‌شان فعال کرده‌اند از کار می‌افتند و باید دوباره فعال‌سازی کنند.
"""

import base64

from cryptography.hazmat.primitives.asymmetric import ec


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def main():
    private_key = ec.generate_private_key(ec.SECP256R1())
    public_key = private_key.public_key()

    private_raw = private_key.private_numbers().private_value.to_bytes(32, "big")

    pub_numbers = public_key.public_numbers()
    public_raw = b"\x04" + pub_numbers.x.to_bytes(32, "big") + pub_numbers.y.to_bytes(32, "big")

    print("این دو خط را داخل فایل .env قرار بده:\n")
    print(f"VAPID_PUBLIC_KEY={_b64url(public_raw)}")
    print(f"VAPID_PRIVATE_KEY={_b64url(private_raw)}")
    print("\n(اختیاری) یک ایمیل تماس هم می‌توانی اضافه کنی:")
    print("VAPID_CLAIM_EMAIL=you@example.com")


if __name__ == "__main__":
    main()
