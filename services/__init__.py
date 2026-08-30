# -*- coding: utf-8 -*-
"""لایه‌ی سرویس مشترک - «یک» سیستم مدیریتی برای بات تلگرام و پنل وب.

دستورالعمل برای توسعه‌دهنده:
  - همه‌ی منطق تجاریِ مشترک اینجا قرار می‌گیرد؛ رابط‌ها فقط I/O دارند.
  - داخل تراکنش‌های `db.transaction()` هرگز db.* صدا نزنید (حتی تنظیمات را
    قبل از BEGIN بخوانید) - آن‌ها اتصالِ در جریان را commit می‌کنند.
"""

from services import (
    errors,
    permissions,
    settings,
    catalog,
    cart,
    checkout,
    orders,
    payments,
    inventory,
    shipping,
)

__all__ = [
    "errors",
    "permissions",
    "settings",
    "catalog",
    "cart",
    "checkout",
    "orders",
    "payments",
    "inventory",
    "shipping",
]