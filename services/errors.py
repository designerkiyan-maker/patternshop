# -*- coding: utf-8 -*-
"""خطاهای دامنه‌ی لایه‌ی سرویس (یک مدیریت واحد برای وب و تلگرام)."""


class ShopError(Exception):
    """پایه‌ی همه‌ی خطاهای دامنه. هر خطا یک `code` ماشین‌خوان دارد تا رابط‌ها
    بتوانند به آن واکنش متفاوت بدهند (پیام فارسی / status code HTTP / دکمه)."""
    code = "shop_error"

    def __init__(self, message: str = "", *, code: str = None, **data):
        super().__init__(message or self.code)
        self.message = message or self.code
        if code:
            self.code = code
        self.data = data


class PermissionDenied(ShopError):
    code = "permission_denied"


class CartError(ShopError):
    code = "cart_error"


class EmptyCartError(CartError):
    code = "cart_empty"


class CheckoutError(ShopError):
    code = "checkout_error"


class DiscountError(CheckoutError):
    code = "discount_invalid"


class InventoryError(CheckoutError):
    code = "inventory_unavailable"


class WalletError(CheckoutError):
    code = "wallet_insufficient"


class OrderError(ShopError):
    code = "order_error"


class AlreadyDecidedError(OrderError):
    """سفارش قبلاً بررسی شده (approve/reject هم‌زمان)."""
    code = "order_already_decided"


class PaymentError(ShopError):
    code = "payment_error"


class SettingsError(ShopError):
    code = "settings_error"


class CatalogError(ShopError):
    code = "catalog_error"