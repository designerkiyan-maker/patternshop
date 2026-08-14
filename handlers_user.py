# -*- coding: utf-8 -*-
"""
هندلرهای مربوط به کاربر عادی

این فایل یک تابع کارخانه‌ای (factory) دارد: create_user_router(db).
چون هر بات (اصلی یا نمایندگی) دیتابیس مستقل خودش را دارد، این تابع یک
Router تازه می‌سازد که به همان یک db گره خورده؛ یعنی دقیقاً همان کد،
برای بات اصلی و هر بات نمایندگی، مستقل و کامل اجرا می‌شود.
"""

import random
import asyncio
import logging

from aiogram import Router, F, Bot
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramRetryAfter, TelegramForbiddenError, TelegramBadRequest, TelegramNetworkError

import keyboards as kb
from states import BuyFlow, ContactFlow, DiscountEntry, WalletTopup
from config import MAX_TEST_PER_USER
from config_delivery import deliver_config_to_user
from force_join import is_channel_member, CHECK_CALLBACK
from sub_info import fetch_sub_info, format_sub_info_fa
from stock_alerts import check_and_notify_low_stock
import crypto_payment


async def _send_admin_notification(bot, admin_id, send_coro_factory, context_label: str, ref_id: int):
    """ارسال اعلان به یک ادمین با تلاش مجدد در برابر flood-limit و خطای شبکه.
    دلیل عدم دریافت نوتیف توسط ادمین (بلاک بودن ربات، فایل نامعتبر و ...) به‌صورت
    شفاف در logs/bot.log ثبت می‌شود تا قابل بررسی باشد."""
    log = logging.getLogger("handlers_user")
    for attempt in range(2):
        try:
            return await send_coro_factory()
        except TelegramRetryAfter as e:
            log.warning(
                "محدودیت ارسال تلگرام (flood) هنگام اطلاع %s #%s به ادمین %s؛ %s ثانیه صبر و تلاش مجدد.",
                context_label, ref_id, admin_id, e.retry_after,
            )
            await asyncio.sleep(e.retry_after + 1)
            continue
        except TelegramForbiddenError:
            log.warning(
                "ادمین %s ربات را بلاک/استارت نکرده - اطلاع %s #%s ارسال نشد.",
                admin_id, context_label, ref_id,
            )
            return None
        except TelegramBadRequest:
            log.exception(
                "درخواست نامعتبر هنگام ارسال اطلاع %s #%s به ادمین %s (احتمالاً عکس رسید/file_id نامعتبر است).",
                context_label, ref_id, admin_id,
            )
            return None
        except TelegramNetworkError:
            log.warning(
                "خطای شبکه هنگام ارسال اطلاع %s #%s به ادمین %s؛ تلاش مجدد.",
                context_label, ref_id, admin_id,
            )
            await asyncio.sleep(2)
            continue
        except Exception:
            log.exception(
                "ارسال اطلاع %s #%s به ادمین %s ناموفق بود.",
                context_label, ref_id, admin_id,
            )
            return None
    log.error(
        "ارسال اطلاع %s #%s به ادمین %s پس از تلاش مجدد هم ناموفق بود.",
        context_label, ref_id, admin_id,
    )
    return None


def create_user_router(db) -> Router:
    router = Router()

    # -----------------------------------------------------------------------
    # عضویت اجباری در کانال
    # -----------------------------------------------------------------------

    @router.callback_query(F.data == CHECK_CALLBACK)
    async def cb_check_force_join(call: CallbackQuery, bot: Bot):
        settings = db.get_force_join_settings()
        if not settings["enabled"] or not settings["channel"]:
            await call.answer("✅")
            try:
                await call.message.delete()
            except Exception:
                pass
            return
        member = await is_channel_member(bot, settings["channel"], call.from_user.id)
        if member:
            await call.answer("✅ عضویت شما تایید شد.", show_alert=True)
            try:
                await call.message.delete()
            except Exception:
                pass
            welcome = db.get_setting("welcome_text")
            await call.message.answer(welcome, reply_markup=kb.menu_for_user(db, call.from_user.id))
        else:
            await call.answer("❌ هنوز عضو کانال نشده‌اید.", show_alert=True)

    # -----------------------------------------------------------------------
    # شروع
    # -----------------------------------------------------------------------

    @router.message(CommandStart())
    async def cmd_start(message: Message, state: FSMContext):
        await state.clear()
        db.add_or_update_user(
            message.from_user.id, message.from_user.username or "", message.from_user.first_name or ""
        )

        # پردازش لینک دعوت زیرمجموعه‌گیری: /start ref123456789
        parts = (message.text or "").split(maxsplit=1)
        if len(parts) > 1 and parts[1].startswith("ref"):
            ref_part = parts[1][3:]
            if ref_part.isdigit():
                db.set_referred_by(message.from_user.id, int(ref_part))

        welcome = db.get_setting("welcome_text")
        await message.answer(welcome, reply_markup=kb.menu_for_user(db, message.from_user.id))

    # -----------------------------------------------------------------------
    # مینی‌اپ (دکمه‌ی متنی -> پیام با دکمه‌ی inline واقعی وب‌اپ)
    # -----------------------------------------------------------------------

    @router.message(F.text == kb.MINIAPP_BTN_TEXT)
    async def open_miniapp(message: Message):
        miniapp_url = kb._miniapp_url(db)
        if not miniapp_url:
            return
        await message.answer(
            "برای ورود به مینی‌اپ فروشگاه، روی دکمه‌ی زیر بزن:",
            reply_markup=kb.miniapp_inline_kb(miniapp_url),
        )

    # -----------------------------------------------------------------------
    # خرید کانفیگ
    # -----------------------------------------------------------------------

    @router.message(F.text.func(lambda t: t == db.get_setting("btn_buy")))
    async def show_categories(message: Message, state: FSMContext):
        await state.clear()
        categories = db.get_categories(active_only=True)
        if not categories:
            await message.answer("در حال حاضر دسته‌بندی فعالی وجود ندارد.")
            return
        await message.answer("یک دسته‌بندی را انتخاب کنید:", reply_markup=kb.categories_kb(db, categories))

    @router.callback_query(F.data == "back_main")
    async def cb_back_main(call: CallbackQuery, state: FSMContext):
        await state.clear()
        await call.message.delete()
        await call.answer()

    @router.callback_query(F.data == "back_categories")
    async def cb_back_categories(call: CallbackQuery):
        categories = db.get_categories(active_only=True)
        await call.message.edit_text("یک دسته‌بندی را انتخاب کنید:", reply_markup=kb.categories_kb(db, categories))
        await call.answer()

    @router.callback_query(F.data.startswith("cat:"))
    async def cb_category(call: CallbackQuery):
        cat_id = int(call.data.split(":")[1])
        products = db.get_products(cat_id, active_only=True)
        if not products:
            await call.answer("محصولی در این دسته‌بندی موجود نیست.", show_alert=True)
            return
        await call.message.edit_text("یک محصول را انتخاب کنید:", reply_markup=kb.products_kb(db, products, cat_id))
        await call.answer()

    def _product_confirm_text(product, quantity: int, stock: int, wallet_credit: int) -> str:
        text = (
            f"📦 {product['name']}\n"
            f"💰 قیمت واحد: {product['price']:,} تومان\n"
            f"📝 توضیحات: {product['description'] or '---'}\n"
            f"📊 موجودی: {stock} عدد\n"
        )
        if quantity > 1:
            text += f"\n🔢 تعداد انتخابی: {quantity} عدد\n💵 جمع کل: {product['price'] * quantity:,} تومان\n"
        if wallet_credit > 0:
            text += f"\n👛 موجودی کیف پول شما: {wallet_credit:,} تومان (به‌صورت خودکار در پرداخت اعمال می‌شود)\n"
        return text

    @router.callback_query(F.data.startswith("prod:"))
    async def cb_product(call: CallbackQuery):
        product_id = int(call.data.split(":")[1])
        product = db.get_product(product_id)
        if not product:
            await call.answer("محصول یافت نشد.", show_alert=True)
            return
        stock = db.count_available_configs(product_id)
        wallet_credit = db.get_wallet_credit(call.from_user.id)
        if stock <= 0:
            text = _product_confirm_text(product, 1, stock, wallet_credit)
            text += "\n⛔️ در حال حاضر موجودی این محصول تمام شده است."
            await call.message.edit_text(text)
            await call.answer()
            return
        text = _product_confirm_text(product, 1, stock, wallet_credit)
        await call.message.edit_text(text, reply_markup=kb.product_confirm_kb(db, product_id, 1, stock))
        await call.answer()

    async def _cb_qty_change(call: CallbackQuery, delta: int):
        _, product_id, quantity = call.data.split(":")
        product_id, quantity = int(product_id), int(quantity)
        product = db.get_product(product_id)
        if not product:
            await call.answer("محصول یافت نشد.", show_alert=True)
            return
        stock = db.count_available_configs(product_id)
        if stock <= 0:
            await call.answer("این محصول در حال حاضر موجود نیست.", show_alert=True)
            return
        quantity = max(1, min(quantity + delta, stock))
        wallet_credit = db.get_wallet_credit(call.from_user.id)
        text = _product_confirm_text(product, quantity, stock, wallet_credit)
        await call.message.edit_text(text, reply_markup=kb.product_confirm_kb(db, product_id, quantity, stock))
        await call.answer()

    @router.callback_query(F.data.startswith("qty_inc:"))
    async def cb_qty_inc(call: CallbackQuery):
        await _cb_qty_change(call, 1)

    @router.callback_query(F.data.startswith("qty_dec:"))
    async def cb_qty_dec(call: CallbackQuery):
        await _cb_qty_change(call, -1)

    @router.callback_query(F.data == "noop")
    async def cb_noop(call: CallbackQuery):
        await call.answer()

    @router.callback_query(F.data.startswith("enter_code:"))
    async def cb_enter_code(call: CallbackQuery, state: FSMContext):
        _, product_id, quantity = call.data.split(":")
        await state.update_data(discount_product_id=int(product_id), discount_quantity=int(quantity))
        await state.set_state(DiscountEntry.waiting_code)
        await call.message.edit_text("🎟 کد تخفیف را ارسال کنید:", reply_markup=kb.cancel_kb())
        await call.answer()

    @router.message(DiscountEntry.waiting_code)
    async def process_discount_code(message: Message, state: FSMContext):
        data = await state.get_data()
        product_id = data.get("discount_product_id")
        quantity = data.get("discount_quantity", 1)
        product = db.get_product(product_id) if product_id else None
        if not product:
            await message.answer("محصول معتبر نیست. لطفاً دوباره از منو شروع کنید.")
            await state.clear()
            return

        stock = db.count_available_configs(product_id)
        quantity = max(1, min(quantity, stock)) if stock > 0 else quantity

        code_row = db.get_discount_code(message.text.strip())
        if not db.is_discount_code_valid(code_row):
            await message.answer(
                "❌ این کد تخفیف نامعتبر، غیرفعال یا به سقف استفاده رسیده است. دوباره تلاش کنید یا بدون کد ادامه دهید.",
                reply_markup=kb.cancel_kb(),
            )
            return

        total_price = product["price"] * quantity
        discount_amount = db.compute_discount_amount(code_row, total_price)
        await state.update_data(discount_code_id=code_row["id"], discount_amount=discount_amount)
        await state.set_state(None)

        wallet_credit = db.get_wallet_credit(message.from_user.id)
        price_after_code = total_price - discount_amount
        wallet_used_preview = min(wallet_credit, price_after_code)
        final_preview = price_after_code - wallet_used_preview

        text = (
            f"✅ کد تخفیف اعمال شد!\n\n"
            f"📦 {product['name']}\n"
            f"🔢 تعداد: {quantity} عدد\n"
            f"💰 قیمت کل: {total_price:,} تومان\n"
            f"🎟 تخفیف کد: {discount_amount:,} تومان\n"
        )
        if wallet_used_preview > 0:
            text += f"👛 اعمال کیف پول: {wallet_used_preview:,} تومان\n"
        text += f"💵 مبلغ نهایی قابل پرداخت: {final_preview:,} تومان\n"
        text += f"📊 موجودی: {stock} عدد"

        await message.answer(text, reply_markup=kb.product_confirm_kb(db, product_id, quantity, max(stock, quantity)))

    async def _notify_admins_of_order(bot: Bot, order_id: int, receipt_file_id: str = None):
        order = db.get_order(order_id)
        product = db.get_product(order["product_id"])
        user_row = db.get_user(order["user_id"])
        username = user_row["username"] if user_row else ""
        first_name = user_row["first_name"] if user_row else ""

        quantity = order["quantity"] or 1
        caption = (
            f"🧾 سفارش #{order_id}\n"
            f"👤 کاربر: {first_name or ''} (@{username or '---'})\n"
            f"🆔 آیدی عددی: {order['user_id']}\n"
            f"📦 محصول: {product['name']}"
            + (f" × {quantity}\n" if quantity > 1 else "\n")
            + f"💰 قیمت پایه: {order['base_price']:,} تومان\n"
        )
        if order["discount_amount"]:
            caption += f"🎟 تخفیف کد: {order['discount_amount']:,} تومان\n"
        if order["wallet_used"]:
            caption += f"👛 استفاده از کیف پول: {order['wallet_used']:,} تومان\n"
        caption += f"💵 مبلغ قابل پرداخت: {order['final_price']:,} تومان"

        # اگر سفارش از قبل به‌صورت خودکار تایید شده (کاملاً از کیف پول/کد تخفیف پوشش داده شده بود)،
        # این پیام فقط جهت اطلاع ادمین است و نیازی به دکمه تایید/رد ندارد.
        already_approved = order["status"] != "pending"
        reply_markup = None if already_approved else kb.order_review_kb(order_id)
        if already_approved:
            caption += "\n\n✅ این سفارش به‌طور خودکار تایید و کانفیگ برای کاربر ارسال شد (پرداخت کامل از کیف پول/کد تخفیف)."

        if not receipt_file_id and not already_approved:
            caption += "\n\n(بدون نیاز به رسید - مبلغ کاملاً از کیف پول/تخفیف پوشش داده شده)"

        for admin_id in db.list_admins():
            if receipt_file_id:
                factory = lambda aid=admin_id: bot.send_photo(
                    aid, receipt_file_id, caption=caption, reply_markup=reply_markup,
                )
            else:
                factory = lambda aid=admin_id: bot.send_message(
                    aid, caption, reply_markup=reply_markup,
                )
            sent = await _send_admin_notification(bot, admin_id, factory, "سفارش", order_id)
            if sent:
                db.set_order_admin_message(order_id, admin_id, sent.message_id)

    @router.callback_query(F.data.startswith("buy_start:"))
    async def cb_buy_start(call: CallbackQuery, state: FSMContext, bot: Bot):
        _, product_id, quantity = call.data.split(":")
        product_id, quantity = int(product_id), int(quantity)
        product = db.get_product(product_id)
        stock = db.count_available_configs(product_id)
        if not product or stock <= 0:
            await call.answer("این محصول در حال حاضر موجود نیست.", show_alert=True)
            return
        if quantity < 1:
            quantity = 1
        if quantity > stock:
            await call.answer(f"موجودی کافی نیست. فقط {stock} عدد موجود است.", show_alert=True)
            return

        data = await state.get_data()
        discount_code_id = data.get("discount_code_id")
        discount_amount = data.get("discount_amount", 0) or 0

        total_price = product["price"] * quantity
        wallet_credit = db.get_wallet_credit(call.from_user.id)
        price_after_code = max(total_price - discount_amount, 0)
        wallet_used = min(wallet_credit, price_after_code)

        if wallet_used > 0:
            db.add_wallet_credit(call.from_user.id, -wallet_used)
        if discount_code_id:
            db.increment_discount_usage(discount_code_id)

        order_id = db.create_order(
            call.from_user.id,
            product_id,
            base_price=total_price,
            wallet_used=wallet_used,
            discount_code_id=discount_code_id,
            discount_amount=discount_amount,
            quantity=quantity,
        )
        order = db.get_order(order_id)
        await state.update_data(order_id=order_id)
        await state.update_data(discount_code_id=None, discount_amount=0, discount_product_id=None)

        if order["final_price"] <= 0:
            await state.clear()

            results = db.take_unused_configs(product_id, call.from_user.id, quantity)
            if not results:
                # موجودی تمام شده: مبلغ کسرشده از کیف پول/کد تخفیف را برگردان و به ادمین اطلاع بده
                db.reject_order(order_id)
                await _notify_admins_of_order(bot, order_id)
                await call.message.edit_text(
                    "⛔️ موجودی این محصول در حال حاضر تمام شده است.\n"
                    "مبلغ کسرشده از کیف پول شما به‌طور کامل بازگردانده شد. لطفاً بعداً دوباره تلاش کنید "
                    "یا با پشتیبانی در تماس باشید."
                )
                await call.answer()
                return

            db.approve_order(order_id, [r["id"] for r in results])
            await check_and_notify_low_stock(bot.send_message, db, product_id)
            reward_info = db.reward_referrer_if_first_purchase(call.from_user.id, order["base_price"])
            if reward_info:
                reward_amount, referrer_id = reward_info
                try:
                    await bot.send_message(
                        referrer_id,
                        f"🤝 تبریک! یکی از زیرمجموعه‌های شما اولین خرید خود را انجام داد.\n"
                        f"💰 {reward_amount:,} تومان به کیف پول شما اضافه شد.",
                    )
                except Exception:
                    pass

            # اطلاع‌رسانی به ادمین‌ها فقط جهت آگاهی (نیازی به تایید دستی نیست)
            try:
                await _notify_admins_of_order(bot, order_id)
            except Exception:
                pass

            await call.message.edit_text(
                "✅ مبلغ سفارش شما به‌طور کامل از کیف پول/تخفیف پوشش داده شد.\n"
                "کانفیگ شما در پیام بعدی ارسال می‌شود 👇"
            )
            await deliver_config_to_user(
                bot,
                call.from_user.id,
                product["name"],
                [r["link"] for r in results],
                final_price=0,
                order_id=order_id,
            )
            await call.answer()
            return

        await state.set_state(BuyFlow.waiting_receipt)

        card_number = db.get_setting("card_number")
        card_holder = db.get_setting("card_holder")
        after_buy_text = db.get_setting("after_buy_text")

        text = f"{after_buy_text}\n\n"
        if quantity > 1:
            text += f"🔢 تعداد: {quantity} عدد\n"
        text += f"💳 شماره کارت: `{card_number}`\n"
        text += f"👤 به نام: {card_holder}\n"
        if discount_amount:
            text += f"🎟 تخفیف کد: {discount_amount:,} تومان\n"
        if wallet_used:
            text += f"👛 استفاده از کیف پول: {wallet_used:,} تومان\n"
        text += f"💰 مبلغ نهایی قابل پرداخت: {order['final_price']:,} تومان\n\n"
        text += "لطفاً عکس رسید پرداخت را همینجا ارسال کنید، یا از دکمه‌ی زیر با ارز دیجیتال پرداخت کنید."

        await call.message.edit_text(
            text, parse_mode="Markdown",
            reply_markup=kb.payment_choice_kb(crypto_payment.crypto_payment_available(db)),
        )
        await call.answer()

    @router.callback_query(F.data == "cancel_flow")
    async def cb_cancel_flow(call: CallbackQuery, state: FSMContext):
        data = await state.get_data()
        order_id = data.get("order_id")
        if order_id:
            order = db.get_order(order_id)
            if order and order["status"] == "pending":
                db.reject_order(order_id)
        await state.clear()
        await call.message.edit_text("عملیات لغو شد.")
        await call.answer()

    @router.callback_query(F.data == "pay_crypto", BuyFlow.waiting_receipt)
    async def cb_pay_crypto_order(call: CallbackQuery, state: FSMContext):
        data = await state.get_data()
        order_id = data.get("order_id")
        order = db.get_order(order_id) if order_id else None
        if not order or order["status"] != "pending":
            await call.answer("سفارش معتبر یافت نشد.", show_alert=True)
            return
        await call.answer("در حال ساخت فاکتور...")
        product = db.get_product(order["product_id"])
        tenant_id = db.get_setting("miniapp_tenant_id", "")
        try:
            result = await crypto_payment.create_invoice_for(
                db, tenant_id, call.from_user.id, "order", order_id, order["final_price"],
                order_name=f"سفارش #{order_id} - {product['name'] if product else ''}",
            )
        except crypto_payment.CryptoPaymentError as e:
            await call.message.answer(f"⚠️ {e}")
            return
        await call.message.answer(
            "🪙 فاکتور پرداخت ساخته شد. روی دکمه‌ی زیر بزن، ارز و مبلغ رو انتخاب کن و پرداخت رو تکمیل کن.\n"
            "⏳ اعتبار این فاکتور فقط ۸۰ دقیقه است.\n"
            "به‌محض تایید تراکنش روی بلاک‌چین، سفارش شما به‌صورت خودکار تحویل داده می‌شود.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="🔗 رفتن به صفحه‌ی پرداخت", url=result["invoice_url"]),
            ]]),
        )

    @router.message(BuyFlow.waiting_receipt, F.photo)
    async def receive_receipt(message: Message, state: FSMContext, bot: Bot):
        data = await state.get_data()
        order_id = data.get("order_id")
        order = db.get_order(order_id)
        if not order or order["status"] != "pending":
            await message.answer("سفارش معتبر یافت نشد. لطفاً دوباره از منو شروع کنید.")
            await state.clear()
            return

        file_id = message.photo[-1].file_id
        db.set_order_receipt(order_id, file_id)

        await _notify_admins_of_order(bot, order_id, receipt_file_id=file_id)

        await message.answer(
            "✅ رسید شما برای بررسی ارسال شد. پس از تایید ادمین، کانفیگ برای شما ارسال خواهد شد.",
            reply_markup=kb.menu_for_user(db, message.from_user.id),
        )
        await state.clear()

    @router.message(BuyFlow.waiting_receipt)
    async def receipt_wrong_type(message: Message):
        await message.answer("لطفاً فقط عکس رسید پرداخت را ارسال کنید.")

    # -----------------------------------------------------------------------
    # کانفیگ تست
    # -----------------------------------------------------------------------

    @router.message(F.text.func(lambda t: t == db.get_setting("btn_test")))
    async def get_test_config(message: Message):
        if db.get_setting("test_enabled", "1") != "1":
            await message.answer("در حال حاضر امکان دریافت کانفیگ تست غیرفعال است.")
            return

        user = db.get_user(message.from_user.id)
        if user and user["test_used"] >= MAX_TEST_PER_USER:
            await message.answer("شما قبلاً کانفیگ تست خود را دریافت کرده‌اید. هر کاربر فقط یک بار مجاز به دریافت کانفیگ تست است.")
            return

        result = db.take_unused_test_config(message.from_user.id)
        if not result:
            await message.answer("متاسفانه موجودی کانفیگ تست تمام شده است. لطفاً بعداً مراجعه کنید.")
            return

        db.mark_test_used(message.from_user.id)
        await message.answer(f"🧪 کانفیگ تست شما:\n\n`{result['link']}`", parse_mode="Markdown")

    # -----------------------------------------------------------------------
    # سفارش‌های من
    # -----------------------------------------------------------------------

    @router.message(F.text.func(lambda t: t == db.get_setting("btn_my_orders")))
    async def my_orders(message: Message):
        orders = db.get_user_orders(message.from_user.id)
        if not orders:
            await message.answer("شما تاکنون سفارشی ثبت نکرده‌اید.")
            return

        status_map = {"pending": "⏳ در انتظار بررسی", "approved": "✅ تایید شده", "rejected": "❌ رد شده"}
        lines = []
        approved = []  # (product_name, link)
        for o in orders:
            product = db.get_product(o["product_id"])
            pname = product["name"] if product else "نامشخص"
            qty = o["quantity"] or 1
            line = f"#{o['id']} | {pname}" + (f" × {qty}" if qty > 1 else "") + f" | {status_map.get(o['status'], o['status'])}"
            if o["status"] == "approved":
                configs = db.get_order_configs(o["id"])
                links = [c["link"] for c in configs] if configs else None
                if not links and o["config_id"]:
                    cfg = db.get_config_by_id(o["config_id"])
                    links = [cfg["link"]] if cfg else []
                for i, link in enumerate(links or [], start=1):
                    prefix = f"\n🔗 کانفیگ {i}: " if len(links) > 1 else "\n🔗 "
                    line += f"{prefix}`{link}`"
                    approved.append((pname, link))
            lines.append(line)
        await message.answer("\n\n".join(lines), parse_mode="Markdown")

        if approved:
            wait_msg = await message.answer("⏳ در حال دریافت اطلاعات لحظه‌ای مصرف سرویس‌ها...")
            infos = await asyncio.gather(*[fetch_sub_info(link) for _, link in approved])
            try:
                await wait_msg.delete()
            except Exception:
                pass
            for (pname, _link), info in zip(approved, infos):
                text = f"📦 {pname}\n\n{format_sub_info_fa(info)}"
                await message.answer(text)

    # -----------------------------------------------------------------------
    # زیرمجموعه‌گیری (رفرال)
    # -----------------------------------------------------------------------

    @router.message(F.text.func(lambda t: t == db.get_setting("btn_referral")))
    async def referral_menu(message: Message, bot: Bot):
        if db.get_setting("referral_enabled", "1") != "1":
            await message.answer("در حال حاضر سیستم زیرمجموعه‌گیری غیرفعال است.")
            return

        me = await bot.get_me()
        link = f"https://t.me/{me.username}?start=ref{message.from_user.id}"
        stats = db.get_referral_stats(message.from_user.id)
        percent = db.get_setting("referral_percent", "10")

        text = (
            "🤝 سیستم زیرمجموعه‌گیری\n\n"
            f"لینک اختصاصی دعوت شما:\n{link}\n\n"
            f"هر کاربری که با این لینک وارد بات شود و اولین خریدش تایید شود، {percent}٪ از مبلغ پرداختی او "
            f"به‌صورت اعتبار کیف پول به شما تعلق می‌گیرد و به‌طور خودکار در خرید بعدی‌تان کسر می‌شود.\n\n"
            f"👥 تعداد زیرمجموعه‌های شما: {stats['count']}\n"
            f"👛 موجودی کیف پول شما: {stats['credit']:,} تومان"
        )
        await message.answer(text)

    # -----------------------------------------------------------------------
    # کیف پول (جدا از زیرمجموعه‌گیری)
    # -----------------------------------------------------------------------

    @router.message(F.text.func(lambda t: t == db.get_setting("btn_wallet")))
    async def wallet_menu(message: Message):
        balance = db.get_wallet_credit(message.from_user.id)
        text = (
            "👛 کیف پول شما\n\n"
            f"موجودی فعلی: {balance:,} تومان\n\n"
            "این موجودی (چه از شارژ دستی، چه از پورسانت زیرمجموعه‌گیری) به‌صورت خودکار در خرید بعدی شما کسر می‌شود."
        )
        await message.answer(text, reply_markup=kb.wallet_menu_kb())

    # -----------------------------------------------------------------------
    # گردونه شانس
    # -----------------------------------------------------------------------

    @router.message(F.text.func(lambda t: t == db.get_setting("btn_wheel")))
    async def wheel_of_fortune(message: Message, bot: Bot):
        if db.get_setting("wheel_enabled", "1") != "1":
            await message.answer("در حال حاضر گردونه شانس غیرفعال است.")
            return

        can_spin, remaining_hours = db.can_spin_wheel(message.from_user.id)
        if not can_spin:
            hours = int(remaining_hours) + 1
            await message.answer(f"⏳ فردا دوباره امتحان کن! حدود {hours} ساعت دیگر می‌توانی دوباره گردونه را بچرخانی.")
            return

        # افکت چرخش: انیمیشن اسلات‌ماشین بومی تلگرام
        try:
            await bot.send_dice(message.chat.id, emoji="🎰")
        except Exception:
            await message.answer("🎡 در حال چرخش گردونه...")
        await asyncio.sleep(2.5)

        db.record_wheel_spin(message.from_user.id)

        settings = db.get_wheel_settings()
        won = random.randint(1, 100) <= settings["win_percent"]

        if won and settings["prizes"]:
            percent = random.choice(settings["prizes"])
            code, expires_at = db.generate_wheel_prize_code(message.from_user.id, percent)
            await message.answer(
                f"🎉 تبریک! برنده شدی!\n\n"
                f"🎟 کد تخفیف {percent}٪ شما:\n`{code}`\n\n"
                f"⏳ اعتبار: تا {settings['expiry_hours']} ساعت آینده\n"
                f"این کد یکبارمصرف است و در خرید بعدی‌ات قابل استفاده است.",
                parse_mode="Markdown",
            )
        else:
            await message.answer("😔 امروز شانس با تو نبود! فردا دوباره امتحان کن.")

    @router.callback_query(F.data == "start_topup")
    async def cb_start_topup(call: CallbackQuery, state: FSMContext):
        await state.set_state(WalletTopup.waiting_amount)
        await call.message.edit_text(
            "💰 چه مبلغی (به تومان) می‌خواهید به کیف پول خود شارژ کنید؟ فقط عدد ارسال کنید (مثال: 100000):",
            reply_markup=kb.cancel_kb(),
        )
        await call.answer()

    @router.message(WalletTopup.waiting_amount)
    async def process_topup_amount(message: Message, state: FSMContext):
        text = message.text.strip().replace(",", "")
        if not text.isdigit() or int(text) < 1000:
            await message.answer("لطفاً یک عدد معتبر و حداقل 1000 تومان ارسال کنید.")
            return

        amount = int(text)
        await state.update_data(topup_amount=amount)
        await state.set_state(WalletTopup.waiting_receipt)

        card_number = db.get_setting("card_number")
        card_holder = db.get_setting("card_holder")

        text = (
            f"مبلغ {amount:,} تومان را به شماره کارت زیر واریز کرده و سپس عکس رسید را ارسال کنید:\n\n"
            f"💳 شماره کارت: `{card_number}`\n"
            f"👤 به نام: {card_holder}\n"
        )
        await message.answer(
            text, parse_mode="Markdown",
            reply_markup=kb.payment_choice_kb(crypto_payment.crypto_payment_available(db)),
        )

    @router.callback_query(F.data == "pay_crypto", WalletTopup.waiting_receipt)
    async def cb_pay_crypto_topup(call: CallbackQuery, state: FSMContext):
        data = await state.get_data()
        amount = data.get("topup_amount")
        if not amount:
            await call.answer("درخواست معتبر یافت نشد.", show_alert=True)
            return
        await call.answer("در حال ساخت فاکتور...")
        topup_id = db.create_topup(call.from_user.id, amount)
        tenant_id = db.get_setting("miniapp_tenant_id", "")
        try:
            result = await crypto_payment.create_invoice_for(
                db, tenant_id, call.from_user.id, "wallet_topup", topup_id, amount,
                order_name=f"شارژ کیف پول #{topup_id}",
            )
        except crypto_payment.CryptoPaymentError as e:
            await call.message.answer(f"⚠️ {e}")
            return
        await call.message.answer(
            "🪙 فاکتور پرداخت ساخته شد. روی دکمه‌ی زیر بزن، ارز و مبلغ رو انتخاب کن و پرداخت رو تکمیل کن.\n"
            "⏳ اعتبار این فاکتور فقط ۸۰ دقیقه است.\n"
            "به‌محض تایید تراکنش روی بلاک‌چین، کیف پول شما به‌صورت خودکار شارژ می‌شود.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="🔗 رفتن به صفحه‌ی پرداخت", url=result["invoice_url"]),
            ]]),
        )

    @router.message(WalletTopup.waiting_receipt, F.photo)
    async def receive_topup_receipt(message: Message, state: FSMContext, bot: Bot):
        data = await state.get_data()
        amount = data.get("topup_amount")
        if not amount:
            await message.answer("درخواست معتبر یافت نشد. لطفاً دوباره از منو شروع کنید.")
            await state.clear()
            return

        file_id = message.photo[-1].file_id
        topup_id = db.create_topup(message.from_user.id, amount)
        db.set_topup_receipt(topup_id, file_id)

        user_row = db.get_user(message.from_user.id)
        caption = (
            f"👛 درخواست شارژ کیف پول #{topup_id}\n"
            f"👤 کاربر: {user_row['first_name'] or ''} (@{user_row['username'] or '---'})\n"
            f"🆔 آیدی عددی: {message.from_user.id}\n"
            f"💰 مبلغ: {amount:,} تومان"
        )
        for admin_id in db.list_admins():
            factory = lambda aid=admin_id: bot.send_photo(
                aid, file_id, caption=caption, reply_markup=kb.topup_review_kb(topup_id),
            )
            sent = await _send_admin_notification(bot, admin_id, factory, "شارژ کیف پول", topup_id)
            if sent:
                db.set_topup_admin_message(topup_id, admin_id, sent.message_id)

        await message.answer(
            "✅ درخواست شارژ کیف پول شما برای بررسی ارسال شد. پس از تایید ادمین، مبلغ به کیف پول شما اضافه می‌شود.",
            reply_markup=kb.menu_for_user(db, message.from_user.id),
        )
        await state.clear()

    @router.message(WalletTopup.waiting_receipt)
    async def topup_receipt_wrong_type(message: Message):
        await message.answer("لطفاً فقط عکس رسید پرداخت را ارسال کنید.")

    # -----------------------------------------------------------------------
    # ارتباط با پشتیبانی
    # -----------------------------------------------------------------------

    @router.message(F.text.func(lambda t: t == db.get_setting("btn_contact")))
    async def contact_start(message: Message, state: FSMContext):
        await state.set_state(ContactFlow.waiting_message)
        await message.answer(db.get_setting("contact_text"), reply_markup=kb.cancel_kb())

    @router.message(ContactFlow.waiting_message)
    async def contact_receive(message: Message, state: FSMContext, bot: Bot):
        user = message.from_user
        if message.text:
            db.add_support_message(user.id, "user", message.text)
        text = (
            f"📩 پیام جدید از کاربر\n"
            f"👤 {user.first_name or ''} (@{user.username or '---'})\n"
            f"🆔 {user.id}\n\n"
            f"✉️ {message.text or '(بدون متن / رسانه)'}"
        )
        # فقط به اولین ادمین/مالک آنلاین اطلاع بده تا مکالمه به او اختصاص یابد؛
        # اگر هیچ‌کس آنلاین نبود، طبق روال قدیم به همه‌ی ادمین‌ها اطلاع بده.
        target_admin = db.resolve_support_admin_for_message(user.id)
        admin_ids = [target_admin] if target_admin else db.list_admins()
        for admin_id in admin_ids:
            try:
                await bot.send_message(admin_id, text, reply_markup=kb.contact_reply_kb(user.id))
            except Exception:
                logging.getLogger("handlers_user").exception(
                    "ارسال پیام پشتیبانی کاربر %s به ادمین %s ناموفق بود.", user.id, admin_id
                )
        await message.answer(
            "پیام شما برای پشتیبانی ارسال شد. به زودی پاسخ داده می‌شود.",
            reply_markup=kb.menu_for_user(db, user.id),
        )
        await state.clear()

    return router
