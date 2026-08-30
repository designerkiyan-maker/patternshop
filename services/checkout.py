# -*- coding: utf-8 -*-
"""تسویه‌ی سبد خرید - هسته‌ی اتمیکِ خرید یکپارچه (دیجیتال + فیزیکی).

همه‌ی مسیرهای خرید (بات تلگرام، Mini App، و هر رابط آینده) از همین یک تابع
می‌گذرند تا قواعد قیمت/تخفیف/کیف پول/موجودی/ارسال یکسان باشد.

قواعد مالی (مستند):
  - subtotal        = جمع قیمت فروش اقلام (قیمت واریانت یا قیمت محصول × تعداد)
  - discount_amount = فقط روی «کلِ» اقلام سبد اعمال می‌شود (قاعده‌ی جدید برای
                      سبد چندقلمه؛ برای خرید تک‌دیجیتالی عیناً مثل قانون قدیم است)
  - wallet_used     = min(موجودی کیف پول، subtotal - discount_amount) و فقط
                      می‌تواند بخش کالا را بپوشاند نه ارسال را
  - shipping_cost   = هزینه‌ی روش ارسال انتخابی (فقط برای سبد دارای آیتم فیزیکی)
  - payable/final_price = max(subtotal - discount - wallet_used, 0) + shipping

خاصیت‌های aتمیک:
  - کل فرآیند در «یک» تراکنش `BEGIN IMMEDIATE` انجام می‌شود (سری‌سازی‌ی خودکار
    concurrent)؛ هیچ تماس db.xxx داخل تراکنش نیست، فقط conn راوی.
  - ادعای سبد: قبل از محاسبات، ردیف‌های سبد خوانده و حذف می‌شوند -> دو تسویه‌ی
    هم‌زمان از یک سبد فقط یکی موفق می‌شود.
  - idempotency: کلید `idem_key`؛ اگر قبلاً وجود داشته باشد، همان نتیجه‌ی ذخیره
    شده بازگردانده می‌شود (بدون هیچ اثر تکراری). پیش‌فرض مبتنی بر max(item_id)
    سبد است -> بعد از هر سبد تازه، کلید جدید می‌شود.
  - بدهی کیف پول / مصرف کد تخفیف / رزرو موجودی all به‌صورت UPDATE با شرط
    (rowcount) انجام می‌شوند؛ غیرممکن است دو رویداد همان واحد را ببرند.
"""

import datetime as _dt
from dataclasses import dataclass, field, asdict

from services import settings as store_settings
from services.errors import (
    CheckoutError, EmptyCartError, DiscountError, InventoryError,
    WalletError, CatalogError,
)

_CART_JOIN = (
    "SELECT ci.*, "
    "p.name AS product_name, p.price AS product_price, p.type AS product_type, "
    "COALESCE(p.is_active, 0) AS product_active, v.price AS variant_price, "
    "v.is_active AS variant_active, "
    "COALESCE(i.on_hand, 0) AS on_hand, COALESCE(i.reserved, 0) AS reserved "
    "FROM cart_items ci "
    "JOIN products p ON p.id = ci.product_id "
    "LEFT JOIN product_variants v ON v.id = ci.variant_id "
    "LEFT JOIN inventory i ON i.variant_id = ci.variant_id "
    "WHERE ci.user_id = ? ORDER BY ci.id"
)


def _row_has(r, key):
    if not r:
        return False
    return key in r.keys() and r[key] is not None


@dataclass
class CheckoutItem:
    product_id: int
    product_name: str
    product_type: str
    quantity: int
    unit_price: int
    total_price: int
    variant_id: int = None
    variant_label: str = None
    file_ids: str = ""


@dataclass
class CheckoutResult:
    order_id: int
    status: str
    payment_status: str
    order_type: str              # digital | physical | mixed
    idem_key: str
    tg_id: int
    base_total: int              # جمع قیمت فروش اقلام
    discount_amount: int
    wallet_used: int
    shipping_cost: int
    final_price: int             # payable = مبلغی که کاربر باید بپردازد
    discount_code_id: int = None
    shipping_method_id: int = None
    shipping_method_name: str = ""
    items: list = field(default_factory=list)

    def to_dict(self):
        return asdict(self)


def _default_idem_key(db, tg_id: int) -> str:
    """کلید idempotency پیش‌فرض بر اساس آخرین نسخه‌ی سبد (max id قلم).

    خرید از یک سبد یکسان -> همان کلید -> تکرارِ ارسال = همان سفارش.
    تغییر سبد (افزودن قلم/تسویه‌شده) -> کلید جدید -> یک سفارش جدید."""
    max_id = 0
    for item in db.get_cart_items(tg_id):
        max_id = max(max_id, int(item["id"]))
    return f"checkout:{tg_id}:{max_id}"


def _find_discount_subtotal(base_total: int, discount_row, product: str) -> int:
    val = discount_row["percent"] or 0
    if val:
        return min((base_total * val) // 100, base_total)
    fixed = discount_row["fixed_amount"] or 0
    return min(int(fixed), base_total)


def _validate_discount(db, discount_code, base_total: int):
    """بررسی کد تخفیف: باید فعال/منقضی‌نشده و دارای ظرفیت باشد.
    برگشت: (code_id, discount_amount). اگر کد ندهند: (None, 0)."""
    if not discount_code:
        return None, 0
    row = db.get_discount_code(str(discount_code))
    if not db.is_discount_code_valid(row):
        raise DiscountError("کد تخفیف نامعتبر یا منقضی شده است.")
    return int(row["id"]), _find_discount_subtotal(base_total, row, discount_code)


def _snapshot_address(db, conn, tg_id: int, address_id, required: bool) -> dict:
    if not address_id:
        if required:
            raise CheckoutError("برای خرید کالای فیزیکی، ثبت آدرس گیرنده الزامی است.",
                                code="address_required")
        return {}
    row = conn.execute(
        "SELECT * FROM customer_addresses WHERE id=? AND user_id=?", (int(address_id), tg_id)
    ).fetchone()
    if not row:
        raise CheckoutError("آدرس انتخابی نامعتبر است.", code="address_invalid")
    return {
        "address_id": row["id"],
        "recipient_name": row["recipient_name"],
        "recipient_mobile": row["mobile"],
        "recipient_address": "، ".join(filter(None, [
            row["province"], row["city"], row["address"],
            (f"کد پستی: {row['postal_code']}" if row["postal_code"] else ""),
        ])),
    }


def _load_cart(conn, tg_id: int):
    return conn.execute(_CART_JOIN, (tg_id,)).fetchall()


def _claim_cart(conn, tg_id: int):
    conn.execute("DELETE FROM cart_items WHERE user_id=?", (tg_id,))


def _has_files(conn, product_id: int) -> bool:
    row = conn.execute(
        "SELECT 1 FROM product_files WHERE product_id=? LIMIT 1", (product_id,)
    ).fetchone()
    return bool(row)


def _reserve_item(conn, variant_id: int, qty: int, product_id: int, order_id: int, actor: str):
    """رزرو اتمیک داخل تراکنش‌ی تسویه. فقط اگر موجودی کافی باشد تأثیر می‌گذارد
    (UPDATE با شرط)؛ برگشت True/False."""
    conn.execute("INSERT OR IGNORE INTO inventory (variant_id) VALUES (?)", (variant_id,))
    cur = conn.execute(
        "UPDATE inventory SET reserved = reserved + ?, updated_at=CURRENT_TIMESTAMP "
        "WHERE variant_id=? AND (on_hand - reserved) >= ?",
        (qty, variant_id, qty),
    )
    if cur.rowcount == 0:
        return False
    conn.execute(
        "INSERT INTO inventory_transactions "
        "(variant_id, product_id, delta, on_hand_after, reason, order_id, actor) "
        "SELECT ?, ?, 0, on_hand, 'sale', ?, ? FROM inventory WHERE variant_id=?",
        (variant_id, product_id, order_id, actor, variant_id),
    )
    return True


def _shipping_name_from(order, conn=None, db=None) -> str:
    if not order["shipping_method_id"]:
        return ""
    if conn is not None:
        row = conn.execute(
            "SELECT name FROM shipping_methods WHERE id=?", (order["shipping_method_id"],)
        ).fetchone()
        return row["name"] if row else ""
    if db is not None:
        row = db.get_shipping_method(order["shipping_method_id"])
        return row["name"] if row else ""
    return ""


def _row_to_item(it, variant_label=None) -> CheckoutItem:
    return CheckoutItem(
        product_id=it["product_id"],
        product_name=it["product_name"],
        product_type=it["product_type"],
        quantity=it["quantity"],
        unit_price=it["unit_price"],
        total_price=it["total_price"],
        variant_id=it["variant_id"],
        variant_label=variant_label,
        file_ids=it["file_ids"] or "",
    )


def _build_from_orders(db, order, items_rows, conn=None) -> CheckoutResult:
    """بازسازی نتیجه از ردیف‌های orders و order_items. وقتی `conn` داده شود (یعنی
    داخل تراکنش هستیم) هیچ تقاضایی به دیتابیس از مسیر db.* انجام نمی‌شود تا
    commit زودهنگام تراکنشِ در جریان رخ ندهد."""
    items_out = []
    for it in items_rows:
        variant_label = None
        if it["variant_id"]:
            if conn is not None:
                r = conn.execute(
                    "SELECT label FROM product_variants WHERE id=?", (it["variant_id"],)
                ).fetchone()
                variant_label = r["label"] if r else None
            else:
                r = db.get_variant(it["variant_id"])
                variant_label = r["label"] if r else None
        items_out.append(_row_to_item(it, variant_label))

    return CheckoutResult(
        order_id=order["id"],
        status=order["status"],
        payment_status=order["payment_status"] or "pending",
        order_type=order["order_type"] or "digital",
        idem_key=order["idem_key"] or "",
        tg_id=order["user_id"],
        base_total=order["base_price"],
        discount_amount=order["discount_amount"],
        wallet_used=order["wallet_used"],
        shipping_cost=order["shipping_cost"] or 0,
        final_price=order["final_price"],
        discount_code_id=order["discount_code_id"],
        shipping_method_id=order["shipping_method_id"],
        shipping_method_name=_shipping_name_from(order, conn=conn, db=None if conn else db),
        items=items_out,
    )


def find_existing_commit(db, idem_key: str):
    """اگر کلید idempotency قبلاً تسویه شده، نتیجه‌ی همان سفارش را برمی‌گرداند
    (برای پاسخ‌های idempotent در رابط‌ها قبل از هر کار دیگری)."""
    if not idem_key:
        return None
    order_id = db.get_checkout_order_id(idem_key)
    if not order_id:
        return None
    order = db.get_order(order_id)
    if not order:
        return None
    items = db.get_order_items(order_id)
    return _build_from_orders(db, order, items)


def checkout_cart(
    db,
    tg_id: int,
    *,
    discount_code=None,
    shipping_method_id=None,
    address_id=None,
    idem_key: str = None,
    actor: str = "user",
):
    """تسویه‌ی اتمیک یک سبد. در موفقیت CheckoutResult برمی‌گرداند؛ در شکست
    استثنای دامنه (سبد خالی / کد نامعتبر / موجودی ناکافی / ...).

    نکته: برای خرید «فیزیکی» باید shipping_method_id و address_id داده شوند؛
    برای خرید تمام‌دیجیتال اختیاری‌اند."""
    idem_key = idem_key or _default_idem_key(db, tg_id)

    # --- fast-path بازپخش idempotent (غیر از تراکنش، کم‌هزینه) ----------------
    existing = find_existing_commit(db, idem_key)
    if existing:
        return existing

    if not store_settings.get_bool(db, "cart_enabled", True):
        raise CheckoutError("خرید در حال حاضر غیرفعال است.", code="checkout_disabled")

    # بررسی کد تخفیف (خواندنِ ساده، بیرون از تراکنش هم امن است؛ مصرف در داخل)
    code_id, discount_amount = _validate_discount(db, discount_code, 0)

    # خواندنِ تنظیمات پیش از تراکنش: داخل بلوک transaction نباید هیچ db.* صدا زده
    # شود (آن‌ها اتصال را commit می‌کنند)؛ این مقادیر فقط به متغیرهای محلی می‌آیند.
    auto_approve_wallet = store_settings.get_bool(db, "checkout_auto_approve_wallet", True)

    with db.transaction() as conn:
        # --- بازپخش هم‌زمان: تراکنش قفل را گرفته؛ اگر همین حالا کلید ثبت شد ---------
        earlier = conn.execute(
            "SELECT order_id FROM checkout_idem WHERE idem_key=?", (idem_key,)
        ).fetchone()
        if earlier:
            od = conn.execute("SELECT * FROM orders WHERE id=?", (earlier["order_id"],)).fetchone()
            its = conn.execute(
                "SELECT * FROM order_items WHERE order_id=?", (earlier["order_id"],)
            ).fetchall()
            return _build_from_orders(db, od, its, conn=conn)

        # --- ادعای سبد: خواندن و حذف هم‌زمان --------------------------------------
        cart = _load_cart(conn, tg_id)
        if not cart:
            raise EmptyCartError("سبد خرید خالی است.")
        _claim_cart(conn, tg_id)

        # --- اعتبارسنجی اقلام و محاسبه‌ی کل ---------------------------------------
        items_for_order = []
        base_total = 0
        total_qty = 0
        has_physical = False
        has_digital = False
        for r in cart:
            if not _row_has(r, "product_active") or not r["product_active"]:
                raise CatalogError(f"محصول «{r['product_name']}» دیگر فعال نیست.",
                                   code="product_unavailable")
            if r["product_type"] == "physical":
                if not _row_has(r, "variant_active") or not r["variant_active"]:
                    raise CatalogError(f"واریانت «{r['product_name']}» فعال نیست.",
                                       code="variant_unavailable")
                has_physical = True
                unit = r["variant_price"] if _row_has(r, "variant_price") else r["product_price"]
            else:
                if not _has_files(conn, r["product_id"]):
                    raise CatalogError(f"برای «{r['product_name']}» فایل الگویی ثبت نشده.",
                                       code="no_files")
                has_digital = True
                unit = r["product_price"]
            qty = int(r["quantity"] or 1)
            if r["product_type"] == "digital":
                qty = 1
            total_qty += qty
            base_total += int(unit) * qty
            items_for_order.append({
                "product_id": r["product_id"],
                "product_type": r["product_type"],
                "product_name": r["product_name"],
                "quantity": qty,
                "unit_price": int(unit),
                "total_price": int(unit) * qty,
                "variant_id": r["variant_id"],
            })

        # --- تخفیف (روی کل اقلام) ---------------------------------------------------
        if discount_code:
            code_id, discount_amount = _validate_discount(db, discount_code, base_total)
        discount_amount = min(discount_amount, base_total)

        # --- ارسال ---------------------------------------------------------------
        shipping_cost = 0
        shipping_method_row = None
        if has_physical:
            if not shipping_method_id:
                raise CheckoutError("انتخاب روش ارسال الزامی است.", code="shipping_required")
            shipping_method_row = conn.execute(
                "SELECT * FROM shipping_methods WHERE id=? AND is_active=1",
                (int(shipping_method_id),),
            ).fetchone()
            if not shipping_method_row:
                raise CheckoutError("روش ارسال انتخابی معتبر نیست.", code="shipping_invalid")
            shipping_cost = int(shipping_method_row["cost"] or 0)

        addr = _snapshot_address(db, conn, tg_id, address_id, required=has_physical)

        # --- کیف پول --------------------------------------------------------------
        credit_row = conn.execute(
            "SELECT referral_credit FROM users WHERE telegram_id=?", (tg_id,)
        ).fetchone()
        credit = int(credit_row["referral_credit"]) if credit_row else 0
        product_payable = max(base_total - discount_amount, 0)
        wallet_used = min(credit, product_payable)
        final_price = max(base_total - discount_amount - wallet_used, 0) + shipping_cost

        order_type = "physical" if (has_physical and not has_digital) else (
            "digital" if (has_digital and not has_physical) else "mixed")

        # --- پرداختِ واقعی (UPDATEهای شرطی) -----------------------------------------
        if wallet_used:
            cur = conn.execute(
                "UPDATE users SET referral_credit = referral_credit - ? "
                "WHERE telegram_id=? AND referral_credit >= ?",
                (wallet_used, tg_id, wallet_used),
            )
            if cur.rowcount == 0:
                raise WalletError("موجودی کیف پول کافی نیست.", code="wallet_insufficient")

        if code_id:
            cur = conn.execute(
                "UPDATE discount_codes SET used_count = used_count + 1 "
                "WHERE id=? AND is_active=1 AND (max_uses=0 OR used_count < max_uses)",
                (code_id,),
            )
            if cur.rowcount == 0:
                raise DiscountError("کد تخفیف دیگر ظرفیت ندارد.", code="discount_exhausted")

        # --- ثبت سفارش --------------------------------------------------------------
        auto_ok = final_price <= 0 and auto_approve_wallet
        status = "approved" if auto_ok else "pending"
        payment_status = "paid" if auto_ok else "pending"
        now_iso = _dt.datetime.utcnow().isoformat()

        cur = conn.execute(
            "INSERT INTO orders (user_id, product_id, status, base_price, wallet_used, "
            "discount_code_id, discount_amount, final_price, quantity, payment_status, "
            "order_type, shipping_cost, shipping_method_id, address_id, recipient_name, "
            "recipient_mobile, recipient_address, idem_key, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                tg_id, items_for_order[0]["product_id"], status, base_total, wallet_used,
                code_id, discount_amount, final_price, total_qty, payment_status,
                order_type, shipping_cost,
                shipping_method_row["id"] if shipping_method_row else None,
                (addr.get("address_id") or None),
                (addr.get("recipient_name") or ""),
                (addr.get("recipient_mobile") or ""),
                (addr.get("recipient_address") or ""),
                idem_key, now_iso,
            ),
        )
        order_id = cur.lastrowid

        for it in items_for_order:
            db.insert_order_item(
                conn, order_id, it["product_id"], it["product_type"], it["product_name"],
                it["quantity"], it["unit_price"], it["total_price"],
                variant_id=it["variant_id"],
            )

        if has_physical:
            for it in items_for_order:
                if it["product_type"] != "physical":
                    continue
                ok = _reserve_item(conn, it["variant_id"], it["quantity"],
                                   it["product_id"], order_id, str(actor))
                if not ok:
                    raise InventoryError(
                        f"موجودی «{it['product_name']}» برای این سفارش کافی نیست.",
                        code="stock_unavailable")

        conn.execute("INSERT OR IGNORE INTO checkout_idem (idem_key, order_id) VALUES (?, ?)",
                     (idem_key, order_id))

    # --- ساخت نتیجه با خواندن دوباره‌ی متعهدشده --------------------------------
    committed = db.get_order(order_id)
    committed_items = list(db.get_order_items(order_id))
    return _build_from_orders(db, committed, committed_items)


def requote_shipping_cost(db, tg_id: int, shipping_method_id: int) -> int:
    """برآورد هزینه‌ی ارسال برای سبد فعلی کاربر (نمایشی، پیش از تسویه)."""
    method = db.get_shipping_method(shipping_method_id)
    if not method or not method["is_active"]:
        raise CheckoutError("روش ارسال انتخابی معتبر نیست.", code="shipping_invalid")
    return int(method["cost"] or 0)


def estimate_summary(db, tg_id: int, *, discount_code=None, shipping_method_id=None) -> dict:
    """برآورد غیرمتعهد (پیش‌نمایش) برای سبد فعلی؛ برای «نمایشِ» پیش از پرداخت."""
    items = db.get_cart_items(tg_id)
    if not items:
        raise EmptyCartError("سبد خرید خالی است.")
    base_total = 0
    has_physical = False
    for it in items:
        unit = it["variant_price"] if (it["variant_price"] is not None and it["product_type"] == "physical") else it["product_price"]
        qty = it["quantity"] if it["product_type"] == "physical" else 1
        base_total += int(unit) * qty
        if it["product_type"] == "physical":
            has_physical = True

    code_id, discount_amount = _validate_discount(db, discount_code, base_total)
    discount_amount = min(discount_amount, base_total)
    credit = db.get_wallet_credit(tg_id)
    wallet_used = min(credit, max(base_total - discount_amount, 0))
    shipping_cost = 0
    method_name = ""
    if has_physical and shipping_method_id:
        method = db.get_shipping_method(shipping_method_id)
        if method and method["is_active"]:
            shipping_cost = int(method["cost"] or 0)
            method_name = method["name"]
    final_price = max(base_total - discount_amount - wallet_used, 0) + shipping_cost
    return {
        "count": len(items),
        "base_total": int(base_total),
        "discount_amount": int(discount_amount),
        "wallet_used": int(wallet_used),
        "wallet_credit": credit,
        "shipping_cost": int(shipping_cost),
        "shipping_method_name": method_name,
        "final_price": int(final_price),
        "has_physical": has_physical,
    }