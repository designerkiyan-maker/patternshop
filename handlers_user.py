# -*- coding: utf-8 -*-
"""
هندلرهای مربوط به کاربر عادی

این فایل یک تابع کارخانه‌ای (factory) دارد: create_user_router(db).
چون هر بات (اصلی یا نمایندگی) دیتابیس مستقل خودش را دارد، این تابع یک
Router تازه می‌سازد که به همان یک db گره خورده؛ یعنی دقیقاً همان کد،
برای بات اصلی و هر بات نمایندگی، مستقل و کامل اجرا می‌شود.
"""

import random
import re
import asyncio
import logging
import os

from aiogram import Router, F, Bot
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramRetryAfter, TelegramForbiddenError, TelegramBadRequest, TelegramNetworkError

import keyboards as kb
from states import BuyFlow, ContactFlow, DiscountEntry, WalletTopup, CustomConfigFlow, ResellerFlow, ResellerRequestFlow, ResellerProductFlow, SubResellerCardFlow, ResellerStoreFlow
from config import MAX_TEST_PER_USER
from config_delivery import deliver_config_to_user
from force_join import is_channel_member, CHECK_CALLBACK
from sub_info import fetch_sub_info, format_sub_info_fa
from stock_alerts import check_and_notify_low_stock
import crypto_payment
from panel_providers import get_provider, PanelError, PanelUsernameTakenError
from config import RESELLER_DBS_DIR
from database import Database


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


def create_user_router(db, bot_manager=None) -> Router:
    router = Router()

    # -----------------------------------------------------------------------
    # فلوی خودکار خودسرویس ساخت بات نمایندگی (بعد از تایید درخواست ادمین)
    # این دو هندلر عمداً اول از همه ثبت می‌شوند تا اولویت داشته باشند و با
    # هیچ دکمه‌ی متنی دیگری تداخل نکنند (فقط وقتی فعال می‌شوند که کاربر
    # واقعاً وسط این مرحله باشد).
    # -----------------------------------------------------------------------

    @router.message(F.func(lambda m: db.get_reseller_bot_setup_step(m.from_user.id) == "waiting_token"))
    async def reseller_bot_setup_receive_token(message: Message):
        if not bot_manager:
            db.clear_reseller_bot_setup(message.from_user.id)
            return
        token = message.text.strip()
        for b in db.list_reseller_bots():
            if b["bot_token"] == token:
                await message.answer("⛔️ این توکن قبلاً برای یک بات دیگر ثبت شده. یک بات دیگر بساز و توکن جدیدش را بفرست.")
                return
        await message.answer("⏳ در حال بررسی اعتبار توکن...")
        temp_bot = Bot(token=token)
        try:
            me = await temp_bot.get_me()
        except Exception:
            await message.answer("❌ این توکن معتبر نیست. لطفاً دوباره بررسی و ارسال کن:")
            await temp_bot.session.close()
            return
        await temp_bot.session.close()

        db.set_reseller_bot_setup_token(message.from_user.id, token, me.username)
        await message.answer(
            f"✅ توکن معتبر است: @{me.username}\n\n"
            f"حالا آیدی عددی تلگرام خودت را ارسال کن (همانی که مالک این بات خواهد بود):"
        )

    @router.message(F.func(lambda m: db.get_reseller_bot_setup_step(m.from_user.id) == "waiting_owner_id"))
    async def reseller_bot_setup_receive_owner_id(message: Message, bot: Bot):
        if not bot_manager:
            db.clear_reseller_bot_setup(message.from_user.id)
            return
        text = message.text.strip()
        if not text.isdigit():
            await message.answer("لطفاً فقط آیدی عددی ارسال کن.")
            return
        owner_id = int(text)
        setup = db.get_reseller_bot_setup_data(message.from_user.id)
        if not setup:
            await message.answer("چیزی اشتباه پیش رفت؛ دوباره از اول امتحان کن.")
            return

        token = setup["token"]
        bot_username = setup["bot_username"]
        mode = setup["mode"] if "mode" in setup.keys() else "independent"
        user = db.get_user(message.from_user.id)
        owner_name = (user["first_name"] if user else None) or (user["username"] if user else None) or str(owner_id)

        os.makedirs(RESELLER_DBS_DIR, exist_ok=True)
        db_path = os.path.join(RESELLER_DBS_DIR, f"{bot_username}.db")
        reseller_id = db.register_reseller_bot(token, bot_username, owner_id, owner_name, db_path, mode=mode)

        started = await bot_manager.start_bot(token, db_path, owner_id, is_main_bot=False)

        reseller_db = Database(db_path)
        reseller_db.init_db(owner_id=owner_id)
        reseller_db.set_setting("miniapp_tenant_id", str(reseller_id))
        # ادمین‌های اصلی (بات مادر) را هم به‌عنوان ادمین این بات نماینده اضافه می‌کنیم
        # تا بتوانند مستقیم وارد بات نماینده شوند و اعتبار حجمی/پنل برایش تنظیم کنند
        # (چون هر بات نماینده دیتابیس و استخر حجم کاملاً مستقل خودش را دارد).
        for admin_id in db.list_admins():
            if admin_id != owner_id:
                reseller_db.add_admin(admin_id, role="admin")

        if mode == "volume":
            # بات با حجم: صاحب بات همان لحظه به‌عنوان نماینده‌ی حجمی (استخر گیگابایت) داخل
            # دیتابیس مستقل خودش فعال می‌شود؛ ادمین بعداً فقط باید شارژش کند.
            reseller_db.set_reseller_status(owner_id, True)

        db.clear_reseller_bot_setup(message.from_user.id)
        db.log_admin_action(message.from_user.id, "reseller_self_bot_created", f"بات @{bot_username} (#{reseller_id}) | mode={mode}")

        status_text = "✅ بات نمایندگی شما ساخته و روشن شد!" if started else \
            "⚠️ بات ثبت شد ولی راه‌اندازی زنده انجام نشد؛ به‌زودی خودکار روشن می‌شود."
        mode_note = (
            "این بات از نوع «بات با حجم» است: کاملاً مستقل (توکن/دیتابیس خودش) است و علاوه بر آن "
            "یک استخر حجم هم دارد که با آن می‌توانی برای مشتری‌هایت کانفیگ بسازی."
            if mode == "volume" else
            "این بات کاملاً مستقل است و همه‌ی امکانات (کد تخفیف، زیرمجموعه‌گیری، کیف پول، کانفیگ تست) را "
            "از صفر و جدا دارد."
        )
        await message.answer(
            f"{status_text}\n\n"
            f"🤖 بات شما: @{bot_username}\n\n"
            f"{mode_note} برای شروع، با /start وارد @{bot_username} شو.\n\n"
            f"برای دریافت اعتبار حجمی و اتصال به پنل VPN، به ادمین ما پیام بده.",
        )
        try:
            for admin_id in db.list_admins():
                await bot.send_message(
                    admin_id,
                    f"🤖 نماینده {owner_name} ({owner_id}) بات @{bot_username} را خودکار ساخت (نوع: "
                    f"{'📦 با حجم' if mode == 'volume' else '🤖 مستقل'}).\n"
                    f"برای دادن اعتبار حجمی، وارد @{bot_username} شو و از «📦 مدیریت نمایندگان» بهش شارژ بده "
                    f"(چون هر بات نماینده استخر مستقل خودش را دارد).",
                )
        except Exception:
            pass

    @router.message(F.func(lambda m: db.get_pending_reseller_bot_fee_order(m.from_user.id) is not None), F.photo)
    async def reseller_bot_fee_receive_receipt(message: Message, bot: Bot):
        order = db.get_pending_reseller_bot_fee_order(message.from_user.id)
        file_id = message.photo[-1].file_id
        db.set_order_receipt(order["id"], file_id)
        await _notify_admins_of_order(bot, order["id"], receipt_file_id=file_id)
        await message.answer("✅ رسید شما برای بررسی ارسال شد. پس از تایید ادمین، مراحل ساخت بات ادامه پیدا می‌کند.")

    @router.callback_query(F.data == "pay_crypto", F.func(lambda c: db.get_pending_reseller_bot_fee_order(c.from_user.id) is not None))
    async def cb_pay_crypto_reseller_bot_fee(call: CallbackQuery):
        order = db.get_pending_reseller_bot_fee_order(call.from_user.id)
        await call.answer("در حال ساخت فاکتور...")
        tenant_id = db.get_setting("miniapp_tenant_id", "")
        try:
            result = await crypto_payment.create_invoice_for(
                db, tenant_id, call.from_user.id, "order", order["id"], order["final_price"],
                order_name=f"هزینه‌ی بات نمایندگی #{order['id']}",
            )
        except crypto_payment.CryptoPaymentError as e:
            await call.message.answer(f"⚠️ {e}")
            return
        await call.message.answer(
            "🪙 فاکتور پرداخت ساخته شد. روی دکمه‌ی زیر بزن، ارز و مبلغ رو انتخاب کن و پرداخت رو تکمیل کن.\n"
            "⏳ اعتبار این فاکتور فقط ۸۰ دقیقه است.\n"
            "به‌محض تایید تراکنش روی بلاک‌چین، خودکار به مرحله‌ی بعد می‌ری.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="🔗 رفتن به صفحه‌ی پرداخت", url=result["invoice_url"]),
            ]]),
        )

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

        # لینک اختصاصی فروشگاه یک نماینده/زیرنماینده: /start rshop_<slug>
        if len(parts) > 1 and parts[1].startswith("rshop_"):
            slug = parts[1][len("rshop_"):]
            await _open_reseller_storefront_by_slug(message, slug)
            return

        welcome = db.get_setting("welcome_text")
        await message.answer(welcome, reply_markup=kb.menu_for_user(db, message.from_user.id))

    async def _open_reseller_storefront_by_slug(message: Message, slug: str):
        seller_type, seller_id, seller_label = None, None, None
        sub = db.get_sub_reseller_by_slug(slug)
        if sub and sub["is_active"]:
            seller_type, seller_id = "sub_reseller", sub["telegram_id"]
            seller_label = sub["display_name"] or "نماینده"
        else:
            owner_row = db.get_owner_by_store_slug(slug)
            if owner_row:
                seller_type, seller_id = "owner", owner_row["telegram_id"]
                seller_label = owner_row["first_name"] or owner_row["username"] or "نماینده"

        if not seller_type:
            welcome = db.get_setting("welcome_text")
            await message.answer(welcome, reply_markup=kb.menu_for_user(db, message.from_user.id))
            return

        products = db.list_reseller_products(seller_type=seller_type, seller_id=seller_id, active_only=True)
        if not products:
            await message.answer(
                f"🛍 فروشگاه {seller_label} فعلاً محصولی فعال ندارد.",
                reply_markup=kb.menu_for_user(db, message.from_user.id),
            )
            return
        await message.answer(
            f"🛍 فروشگاه {seller_label}\n\nیکی از محصولات زیر را انتخاب کن:",
            reply_markup=kb.reseller_storefront_kb(products),
        )

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
        custom_enabled = db.get_setting("custom_config_enabled", "0") == "1"
        has_owner_store = bool(db.list_reseller_products(seller_type="owner", active_only=True))
        if not categories and not custom_enabled and not has_owner_store:
            await message.answer("در حال حاضر دسته‌بندی فعالی وجود ندارد.")
            return
        await message.answer("یک گزینه را انتخاب کنید:", reply_markup=kb.categories_kb(db, categories))

    @router.callback_query(F.data == "custom_config_start")
    async def cb_custom_config_start(call: CallbackQuery, state: FSMContext):
        await call.answer()
        try:
            await call.message.delete()
        except Exception:
            pass
        await custom_config_start(call.message, state)

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

        if order["is_reseller_bot_fee"]:
            user_row = db.get_user(order["user_id"])
            username = user_row["username"] if user_row else ""
            first_name = user_row["first_name"] if user_row else ""
            caption = (
                f"🧾 پرداخت هزینه‌ی بات نمایندگی #{order_id}\n"
                f"👤 کاربر: {first_name or ''} (@{username or '---'})\n"
                f"🆔 آیدی عددی: {order['user_id']}\n"
                f"💵 مبلغ: {order['final_price']:,} تومان"
            )
            reply_markup = kb.order_review_kb(order_id)
            for admin_id in db.list_admins():
                if receipt_file_id:
                    factory = lambda aid=admin_id: bot.send_photo(
                        aid, receipt_file_id, caption=caption, reply_markup=reply_markup,
                    )
                else:
                    factory = lambda aid=admin_id: bot.send_message(
                        aid, caption, reply_markup=reply_markup,
                    )
                sent = await _send_admin_notification(bot, admin_id, factory, "هزینه‌ی بات نمایندگی", order_id)
                if sent:
                    db.set_order_admin_message(order_id, admin_id, sent.message_id)
            return

        if order["is_custom_config"]:
            user_row = db.get_user(order["user_id"])
            username = user_row["username"] if user_row else ""
            first_name = user_row["first_name"] if user_row else ""
            caption = (
                f"🧾 سفارش کانفیگ شخصی #{order_id}\n"
                f"👤 کاربر: {first_name or ''} (@{username or '---'})\n"
                f"🆔 آیدی عددی: {order['user_id']}\n"
                f"🛠 نام کاربری: {order['custom_username']}\n"
                f"📶 حجم: {order['custom_volume_gb']} گیگابایت\n"
                f"💰 قیمت پایه: {order['base_price']:,} تومان\n"
            )
            if order["wallet_used"]:
                caption += f"👛 استفاده از کیف پول: {order['wallet_used']:,} تومان\n"
            caption += f"💵 مبلغ قابل پرداخت: {order['final_price']:,} تومان"
            already_approved = order["status"] != "pending"
            reply_markup = None if already_approved else kb.order_review_kb(order_id)
            if already_approved:
                caption += "\n\n✅ این سفارش به‌طور خودکار تایید و کانفیگ ساخته شد (پرداخت کامل از کیف پول)."
            if not receipt_file_id and not already_approved:
                caption += "\n\n(بدون نیاز به رسید - مبلغ کاملاً از کیف پول پوشش داده شده)"
            for admin_id in db.list_admins():
                if receipt_file_id:
                    factory = lambda aid=admin_id: bot.send_photo(
                        aid, receipt_file_id, caption=caption, reply_markup=reply_markup,
                    )
                else:
                    factory = lambda aid=admin_id: bot.send_message(
                        aid, caption, reply_markup=reply_markup,
                    )
                sent = await _send_admin_notification(bot, admin_id, factory, "سفارش کانفیگ شخصی", order_id)
                if sent:
                    db.set_order_admin_message(order_id, admin_id, sent.message_id)
            return

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
    # ساخت کانفیگ شخصی (اتصال مستقیم به پنل VPN)
    # -----------------------------------------------------------------------

    def _format_pricing_table(tiers) -> str:
        lines = ["💰 جدول قیمت‌گذاری (بر اساس بازه‌ی حجم):", ""]
        for t in tiers:
            to_label = f"{t['to_gb']} گیگ" if t["to_gb"] is not None else "به بالا"
            from_label = f"{t['from_gb']}" if t["to_gb"] is not None else f"{t['from_gb']} گیگ"
            lines.append(f"▫️ {from_label} تا {to_label} ← {t['price_per_gb']:,} تومان/گیگ")
        lines.append("")
        lines.append("قیمت نهایی = کل حجم انتخابی × نرخ همان بازه‌ای که حجم داخلش قرار می‌گیرد.")
        return "\n".join(lines)

    async def custom_config_start(message: Message, state: FSMContext):
        settings = db.get_custom_config_settings()
        if not settings["enabled"]:
            await message.answer("این بخش در حال حاضر غیرفعال است.")
            return
        server = db.get_panel_server_for_usage("custom_config")
        if not server:
            await message.answer("در حال حاضر سروری برای ساخت کانفیگ شخصی فعال نیست. لطفاً بعداً تلاش کنید.")
            return
        tiers = db.get_pricing_tiers()
        if not tiers:
            await message.answer("قیمت‌گذاری این بخش هنوز توسط ادمین تنظیم نشده است.")
            return
        await state.set_state(CustomConfigFlow.waiting_username)
        await state.update_data(panel_server_id=server["id"])
        await message.answer(
            "🛠 ساخت کانفیگ شخصی\n\n"
            "لطفاً یک نام کاربری دلخواه برای کانفیگ خود ارسال کنید، یا از دکمه‌ی زیر یک نام تصادفی بگیر.\n"
            "فقط حروف انگلیسی، عدد و آندرلاین مجاز است (بین ۳ تا ۲۰ کاراکتر).",
            reply_markup=kb.custom_config_username_kb(),
        )

    @router.callback_query(F.data == "custom_config_random_username", CustomConfigFlow.waiting_username)
    async def cb_custom_config_random_username(call: CallbackQuery, state: FSMContext):
        for _ in range(10):
            candidate = "u" + "".join(random.choices("abcdefghijklmnopqrstuvwxyz0123456789", k=8))
            if not db.is_custom_username_taken(candidate):
                break
        await call.answer()
        await _custom_config_apply_username(call.message, state, candidate)

    @router.message(CustomConfigFlow.waiting_username)
    async def custom_config_receive_username(message: Message, state: FSMContext):
        username = (message.text or "").strip()
        if not re.fullmatch(r"[A-Za-z0-9_]{3,20}", username):
            await message.answer("❌ نام کاربری نامعتبر است. فقط حروف انگلیسی، عدد و آندرلاین، بین ۳ تا ۲۰ کاراکتر.")
            return
        if db.is_custom_username_taken(username):
            await message.answer("❌ این نام کاربری قبلاً استفاده شده. لطفاً نام دیگری انتخاب کنید.")
            return
        await _custom_config_apply_username(message, state, username)

    async def _custom_config_apply_username(message: Message, state: FSMContext, username: str):
        settings = db.get_custom_config_settings()
        tiers = db.get_pricing_tiers()
        await state.update_data(custom_username=username)
        await state.set_state(CustomConfigFlow.waiting_volume)
        await message.answer(
            f"✅ نام کاربری: {username}\n\n"
            f"{_format_pricing_table(tiers)}\n\n"
            f"📶 حالا حجم مورد نظر خود را به گیگابایت وارد کنید.\n"
            f"حداقل: {settings['min_gb']} گیگ — حداکثر: {settings['max_gb']} گیگ\n"
            f"⏳ مدت اعتبار: {settings['duration_days']} روز (ثابت)",
            reply_markup=kb.cancel_kb(),
        )

    @router.message(CustomConfigFlow.waiting_volume)
    async def custom_config_receive_volume(message: Message, state: FSMContext):
        settings = db.get_custom_config_settings()
        text = (message.text or "").strip()
        if not text.isdigit():
            await message.answer("❌ لطفاً فقط عدد صحیح وارد کنید (به گیگابایت).")
            return
        volume_gb = int(text)
        if volume_gb < settings["min_gb"] or volume_gb > settings["max_gb"]:
            await message.answer(
                f"❌ حجم باید بین {settings['min_gb']} تا {settings['max_gb']} گیگابایت باشد."
            )
            return

        price = db.calc_custom_config_price(volume_gb)
        if price <= 0:
            await message.answer("⚠️ قیمت‌گذاری برای این بخش هنوز تنظیم نشده. لطفاً با پشتیبانی تماس بگیرید.")
            await state.clear()
            return

        data = await state.get_data()
        username = data.get("custom_username")
        server = db.get_panel_server(data.get("panel_server_id"))
        if not server or not server["is_active"]:
            await message.answer("⛔️ سرور این بخش دیگر در دسترس نیست. لطفاً دوباره از منو شروع کنید.")
            await state.clear()
            return

        wallet_credit = db.get_wallet_credit(message.from_user.id)
        wallet_used = min(wallet_credit, price)

        if wallet_used > 0:
            db.add_wallet_credit(message.from_user.id, -wallet_used)

        order_id = db.create_custom_config_order(
            message.from_user.id, volume_gb, username, server["id"],
            base_price=price, wallet_used=wallet_used,
        )
        order = db.get_order(order_id)
        await state.update_data(order_id=order_id, custom_volume_gb=volume_gb)

        if order["final_price"] <= 0:
            await state.clear()
            db.approve_custom_config_order(order_id)
            server_row = db.get_panel_server(server["id"])
            try:
                provider = get_provider(server_row)
                result = await provider.create_user(username, volume_gb, settings["duration_days"])
            except Exception as e:
                db.reject_order(order_id)
                await message.answer(f"⛔️ خطا در ساخت کانفیگ روی پنل: {e}\nمبلغ به کیف پول بازگردانده شد.")
                return
            db.add_custom_config(
                message.from_user.id, server["id"], result.username, volume_gb,
                settings["duration_days"], result.subscription_url, order_id=order_id,
            )
            await message.answer(
                "✅ مبلغ سفارش شما به‌طور کامل از کیف پول پوشش داده شد.\n"
                "کانفیگ شما در پیام بعدی ارسال می‌شود 👇",
                reply_markup=kb.menu_for_user(db, message.from_user.id),
            )
            await deliver_config_to_user(
                message.bot, message.from_user.id, "کانفیگ شخصی",
                [result.subscription_url], final_price=0, order_id=order_id,
            )
            try:
                await _notify_admins_of_order(message.bot, order_id)
            except Exception:
                pass
            return

        await state.set_state(CustomConfigFlow.waiting_receipt)
        card_number = db.get_setting("card_number")
        card_holder = db.get_setting("card_holder")
        text = (
            f"🛠 نام کاربری: {username}\n"
            f"📶 حجم: {volume_gb} گیگابایت\n"
            f"⏳ مدت: {settings['duration_days']} روز\n\n"
            f"💳 شماره کارت: `{card_number}`\n"
            f"👤 به نام: {card_holder}\n"
        )
        if wallet_used:
            text += f"👛 استفاده از کیف پول: {wallet_used:,} تومان\n"
        text += f"💰 مبلغ نهایی قابل پرداخت: {order['final_price']:,} تومان\n\n"
        text += "لطفاً عکس رسید پرداخت را همینجا ارسال کنید، یا از دکمه‌ی زیر با ارز دیجیتال پرداخت کنید."
        await message.answer(
            text, parse_mode="Markdown",
            reply_markup=kb.payment_choice_kb(crypto_payment.crypto_payment_available(db)),
        )

    @router.callback_query(F.data == "pay_crypto", CustomConfigFlow.waiting_receipt)
    async def cb_pay_crypto_custom_config(call: CallbackQuery, state: FSMContext):
        data = await state.get_data()
        order_id = data.get("order_id")
        order = db.get_order(order_id) if order_id else None
        if not order or order["status"] != "pending":
            await call.answer("سفارش معتبر یافت نشد.", show_alert=True)
            return
        await call.answer("در حال ساخت فاکتور...")
        tenant_id = db.get_setting("miniapp_tenant_id", "")
        try:
            result = await crypto_payment.create_invoice_for(
                db, tenant_id, call.from_user.id, "order", order_id, order["final_price"],
                order_name=f"کانفیگ شخصی #{order_id} - {order['custom_username']}",
            )
        except crypto_payment.CryptoPaymentError as e:
            await call.message.answer(f"⚠️ {e}")
            return
        await call.message.answer(
            "🪙 فاکتور پرداخت ساخته شد. روی دکمه‌ی زیر بزن، ارز و مبلغ رو انتخاب کن و پرداخت رو تکمیل کن.\n"
            "⏳ اعتبار این فاکتور فقط ۸۰ دقیقه است.\n"
            "به‌محض تایید تراکنش روی بلاک‌چین، کانفیگ شما به‌صورت خودکار ساخته می‌شود.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="🔗 رفتن به صفحه‌ی پرداخت", url=result["invoice_url"]),
            ]]),
        )

    @router.message(CustomConfigFlow.waiting_receipt, F.photo)
    async def receive_custom_config_receipt(message: Message, state: FSMContext, bot: Bot):
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
            "✅ رسید شما برای بررسی ارسال شد. پس از تایید ادمین، کانفیگ شخصی شما ساخته و ارسال خواهد شد.",
            reply_markup=kb.menu_for_user(db, message.from_user.id),
        )
        await state.clear()

    @router.message(CustomConfigFlow.waiting_receipt)
    async def custom_config_receipt_wrong_type(message: Message):
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

        panel_server = db.get_panel_server_for_usage("test_config")
        if panel_server:
            volume_gb = int(db.get_setting("test_config_panel_volume_gb", "1") or 1)
            duration_days = int(db.get_setting("test_config_panel_duration_days", "1") or 1)
            for _ in range(10):
                username = "test" + "".join(random.choices("abcdefghijklmnopqrstuvwxyz0123456789", k=8))
                if not db.is_custom_username_taken(username):
                    break
            try:
                provider = get_provider(panel_server)
                result = await provider.create_user(username, volume_gb, duration_days)
            except PanelError as e:
                await message.answer(f"⛔️ خطا در ساخت کانفیگ تست: {e}\nلطفاً بعداً تلاش کنید.")
                return
            db.add_custom_config(
                message.from_user.id, panel_server["id"], result.username,
                volume_gb, duration_days, result.subscription_url, source="test",
            )
            db.mark_test_used(message.from_user.id)
            await message.answer(
                f"🧪 کانفیگ تست شما ({volume_gb} گیگ، {duration_days} روز):\n\n`{result.subscription_url}`",
                parse_mode="Markdown",
            )
            return

        result = db.take_unused_test_config(message.from_user.id)
        if not result:
            await message.answer("متاسفانه موجودی کانفیگ تست تمام شده است. لطفاً بعداً مراجعه کنید.")
            return

        db.mark_test_used(message.from_user.id)
        await message.answer(f"🧪 کانفیگ تست شما:\n\n`{result['link']}`", parse_mode="Markdown")

    # -----------------------------------------------------------------------
    # پنل نمایندگی (ساخت کانفیگ از استخر حجم بدون پرداخت جداگانه)
    # -----------------------------------------------------------------------

    @router.message(F.text == "🧑‍💼 پنل نمایندگی")
    async def reseller_panel_open(message: Message, state: FSMContext):
        seller_type, seller_id = _reseller_seller_type_id(message.from_user.id)
        if not seller_type:
            return
        await state.clear()
        if seller_type == "owner":
            credit = db.get_reseller_credit(message.from_user.id)
        else:
            credit = db.get_sub_reseller_by_telegram_id(message.from_user.id)["credit_gb"]
        await message.answer(
            f"🧑‍💼 پنل نمایندگی\n\n"
            f"📦 اعتبار باقی‌مانده: {credit:,} گیگابایت\n\n"
            f"می‌تونی از این اعتبار مستقیم کانفیگ بسازی، بدون پرداخت جداگانه. "
            f"با هر قیمتی که خودت بخوای می‌تونی به مشتری‌هات بفروشیش.",
            reply_markup=kb.reseller_panel_kb(show_card_button=(seller_type == "sub_reseller"), show_store_link=(seller_type == "sub_reseller")),
        )

    def _reseller_resolve_panel(seller_type: str, seller_id: int):
        if seller_type == "owner":
            reseller_cfg = db.get_reseller_config(seller_id)
            if reseller_cfg["panel_server_id"]:
                s = db.get_panel_server(reseller_cfg["panel_server_id"])
                if s and s["is_active"]:
                    return s
        else:
            sub = db.get_sub_reseller_by_telegram_id(seller_id)
            if sub and sub["panel_server_id"]:
                s = db.get_panel_server(sub["panel_server_id"])
                if s and s["is_active"]:
                    return s
        return db.get_panel_server_for_usage("reseller")

    @router.callback_query(F.data == "reseller_new_config")
    async def cb_reseller_new_config(call: CallbackQuery, state: FSMContext):
        seller_type, seller_id = _reseller_seller_type_id(call.from_user.id)
        if not seller_type:
            await call.answer("دسترسی نداری.", show_alert=True)
            return
        credit = db.get_reseller_credit(seller_id) if seller_type == "owner" else \
            db.get_sub_reseller_by_telegram_id(seller_id)["credit_gb"]
        if credit <= 0:
            await call.answer("اعتبار شما کافی نیست. با نماینده/ادمین بالادستی تماس بگیر.", show_alert=True)
            return
        server = _reseller_resolve_panel(seller_type, seller_id)
        if not server:
            await call.answer("هنوز سروری برای نمایندگی توسط ادمین تنظیم نشده.", show_alert=True)
            return
        await state.set_state(ResellerFlow.waiting_username)
        await state.update_data(panel_server_id=server["id"])
        await call.answer()
        await call.message.answer(
            "یک نام کاربری برای این کانفیگ وارد کن، یا از دکمه‌ی زیر یک نام تصادفی بگیر.\n"
            "فقط حروف انگلیسی، عدد و آندرلاین (بین ۳ تا ۲۰ کاراکتر).",
            reply_markup=kb.custom_config_username_kb(),
        )

    @router.callback_query(F.data == "custom_config_random_username", ResellerFlow.waiting_username)
    async def cb_reseller_random_username(call: CallbackQuery, state: FSMContext):
        for _ in range(10):
            candidate = "r" + "".join(random.choices("abcdefghijklmnopqrstuvwxyz0123456789", k=8))
            if not db.is_custom_username_taken(candidate):
                break
        await call.answer()
        await _reseller_apply_username(call.message, state, candidate)

    @router.message(ResellerFlow.waiting_username)
    async def reseller_receive_username(message: Message, state: FSMContext):
        username = (message.text or "").strip()
        if not re.fullmatch(r"[A-Za-z0-9_]{3,20}", username):
            await message.answer("❌ نام کاربری نامعتبر است. فقط حروف انگلیسی، عدد و آندرلاین، بین ۳ تا ۲۰ کاراکتر.")
            return
        if db.is_custom_username_taken(username):
            await message.answer("❌ این نام کاربری قبلاً استفاده شده. لطفاً نام دیگری انتخاب کنید.")
            return
        await _reseller_apply_username(message, state, username)

    async def _reseller_apply_username(message: Message, state: FSMContext, username: str):
        credit = db.get_reseller_credit(message.from_user.id)
        await state.update_data(reseller_username=username)
        await state.set_state(ResellerFlow.waiting_volume)
        await message.answer(
            f"✅ نام کاربری: {username}\n\n"
            f"📦 اعتبار باقی‌مانده: {credit:,} گیگابایت\n"
            f"حالا حجم مورد نظر برای این کانفیگ را به گیگابایت وارد کن:",
            reply_markup=kb.cancel_kb(),
        )

    @router.message(ResellerFlow.waiting_volume)
    async def reseller_receive_volume(message: Message, state: FSMContext):
        text = (message.text or "").strip()
        if not text.isdigit() or int(text) <= 0:
            await message.answer("❌ لطفاً فقط عدد صحیح مثبت وارد کنید.")
            return
        volume_gb = int(text)
        seller_type, seller_id = _reseller_seller_type_id(message.from_user.id)
        if not seller_type:
            return
        credit = db.get_reseller_credit(seller_id) if seller_type == "owner" else \
            db.get_sub_reseller_by_telegram_id(seller_id)["credit_gb"]
        if volume_gb > credit:
            await message.answer(f"❌ اعتبار شما کافی نیست. اعتبار باقی‌مانده: {credit:,} گیگ.")
            return

        await state.update_data(reseller_volume_gb=volume_gb)
        await state.set_state(ResellerFlow.waiting_duration)
        if seller_type == "owner":
            reseller_cfg = db.get_reseller_config(seller_id)
            await state.update_data(reseller_min_dur=reseller_cfg["min_duration_days"], reseller_max_dur=reseller_cfg["max_duration_days"])
            await message.answer(
                f"⏳ حالا مدت اعتبار این کانفیگ را به روز وارد کن.\n"
                f"حداقل: {reseller_cfg['min_duration_days']} روز — حداکثر: {reseller_cfg['max_duration_days']} روز",
                reply_markup=kb.cancel_kb(),
            )
        else:
            await state.update_data(reseller_min_dur=1, reseller_max_dur=3650)
            await message.answer("⏳ حالا مدت اعتبار این کانفیگ را به روز وارد کن:", reply_markup=kb.cancel_kb())

    @router.message(ResellerFlow.waiting_duration)
    async def reseller_receive_duration(message: Message, state: FSMContext):
        text = (message.text or "").strip()
        if not text.isdigit() or int(text) <= 0:
            await message.answer("❌ لطفاً فقط عدد صحیح مثبت وارد کنید.")
            return
        duration_days = int(text)
        data = await state.get_data()
        min_dur, max_dur = data.get("reseller_min_dur", 1), data.get("reseller_max_dur", 3650)
        if duration_days < min_dur or duration_days > max_dur:
            await message.answer(f"❌ مدت باید بین {min_dur} تا {max_dur} روز باشد.")
            return

        volume_gb = data["reseller_volume_gb"]
        server = db.get_panel_server(data.get("panel_server_id"))
        if not server or not server["is_active"]:
            await message.answer("⛔️ سرور نمایندگی دیگر در دسترس نیست.")
            await state.clear()
            return

        seller_type, seller_id = _reseller_seller_type_id(message.from_user.id)
        if not seller_type:
            await state.clear()
            return

        try:
            provider = get_provider(server)
            result = await provider.create_user(data["reseller_username"], volume_gb, duration_days)
        except PanelUsernameTakenError:
            await message.answer("❌ این نام کاربری روی پنل تکراری است. دوباره از ابتدا با نام دیگری امتحان کن.")
            return
        except PanelError as e:
            await message.answer(f"⛔️ خطا در ساخت کانفیگ: {e}")
            return

        if seller_type == "owner":
            db.adjust_reseller_credit(seller_id, -volume_gb, reason=f"ساخت کانفیگ «{result.username}»")
            new_credit = db.get_reseller_credit(seller_id)
        else:
            sub = db.get_sub_reseller_by_telegram_id(seller_id)
            db.adjust_sub_reseller_credit(sub["id"], -volume_gb, reason=f"ساخت کانفیگ «{result.username}»")
            new_credit = db.get_sub_reseller_by_telegram_id(seller_id)["credit_gb"]
        db.add_custom_config(
            message.from_user.id, server["id"], result.username, volume_gb, duration_days, result.subscription_url,
            source="reseller",
        )
        await state.clear()
        await message.answer(
            f"✅ کانفیگ ساخته شد!\n\n"
            f"🛠 نام کاربری: {result.username}\n"
            f"📶 حجم: {volume_gb} گیگ | ⏳ مدت: {duration_days} روز\n\n"
            f"`{result.subscription_url}`\n\n"
            f"📦 اعتبار باقی‌مانده: {new_credit:,} گیگابایت",
            parse_mode="Markdown",
            reply_markup=kb.menu_for_user(db, message.from_user.id),
        )


    # -----------------------------------------------------------------------
    # بانک کانفیگ نماینده (محصول ثابت که در «خرید کانفیگ» به مشتری دیده می‌شود)
    # -----------------------------------------------------------------------

    def _reseller_seller_type_id(user_id: int):
        """اگر یوزر نماینده‌ی حجمی خود این باتِ (owner) باشد seller_type='owner' و seller_id=telegram_id او؛
        اگر زیرنماینده‌ی فعال باشد seller_type='sub_reseller'. در غیر این صورت None."""
        if db.is_reseller(user_id):
            return "owner", user_id
        if db.is_sub_reseller(user_id):
            return "sub_reseller", user_id
        return None, None

    @router.callback_query(F.data == "reseller_panel_back")
    async def cb_reseller_panel_back(call: CallbackQuery):
        seller_type, _ = _reseller_seller_type_id(call.from_user.id)
        if not seller_type:
            await call.answer("دسترسی نداری.", show_alert=True)
            return
        credit = db.get_reseller_credit(call.from_user.id) if seller_type == "owner" else \
            db.get_sub_reseller_by_telegram_id(call.from_user.id)["credit_gb"]
        await call.message.edit_text(
            f"🧑‍💼 پنل نمایندگی\n\n"
            f"📦 اعتبار باقی‌مانده: {credit:,} گیگابایت",
            reply_markup=kb.reseller_panel_kb(show_card_button=(seller_type == "sub_reseller"), show_store_link=(seller_type == "sub_reseller")),
        )
        await call.answer()

    @router.callback_query(F.data == "reseller_products_menu")
    async def cb_reseller_products_menu(call: CallbackQuery):
        seller_type, seller_id = _reseller_seller_type_id(call.from_user.id)
        if not seller_type:
            await call.answer("دسترسی نداری.", show_alert=True)
            return
        products = db.list_reseller_products(seller_type=seller_type, seller_id=seller_id)
        await call.message.edit_text(
            "🛍 محصولات من\n\n"
            "این‌ها محصولاتی هستند که فقط با «لینک فروشگاه من» به مشتری‌های خودت نمایش داده می‌شوند "
            "(نه تو فروشگاه عمومی بات) و از اعتبار حجمی خودت ساخته و کسر می‌شوند.",
            reply_markup=kb.reseller_products_list_kb(products),
        )
        await call.answer()

    @router.callback_query(F.data == "reseller_store_link")
    async def cb_reseller_store_link(call: CallbackQuery, bot: Bot):
        seller_type, seller_id = _reseller_seller_type_id(call.from_user.id)
        if not seller_type:
            await call.answer("دسترسی نداری.", show_alert=True)
            return
        if seller_type == "sub_reseller":
            sub = db.get_sub_reseller_by_telegram_id(seller_id)
            slug = sub["invite_slug"]
            if not slug:
                import secrets
                slug = secrets.token_urlsafe(6).replace("-", "").replace("_", "")[:8]
                db.set_sub_reseller_invite_slug(sub["id"], slug)
        else:
            slug = db.get_or_create_owner_store_slug(seller_id)
        me = await bot.get_me()
        link = f"https://t.me/{me.username}?start=rshop_{slug}"
        await call.answer()
        await call.message.answer(
            f"🔗 لینک اختصاصی فروشگاه تو:\n\n{link}\n\n"
            f"هر کسی با این لینک وارد بات بشه، فقط محصولات خودِ تو رو می‌بینه (نه فروشگاه عمومی و نه محصول نماینده‌های دیگه).",
        )

    @router.callback_query(F.data == "rprod_add")
    async def cb_rprod_add(call: CallbackQuery, state: FSMContext):
        seller_type, seller_id = _reseller_seller_type_id(call.from_user.id)
        if not seller_type:
            await call.answer("دسترسی نداری.", show_alert=True)
            return
        await state.set_state(ResellerProductFlow.waiting_title)
        await call.answer()
        await call.message.answer("عنوان محصول را وارد کن (مثلاً «۳۰ گیگ ماهانه»):", reply_markup=kb.cancel_kb())

    @router.message(ResellerProductFlow.waiting_title)
    async def rprod_receive_title(message: Message, state: FSMContext):
        title = (message.text or "").strip()
        if not title:
            await message.answer("❌ عنوان نامعتبر است.")
            return
        await state.update_data(rprod_title=title)
        await state.set_state(ResellerProductFlow.waiting_volume)
        await message.answer("حجم این محصول را به گیگابایت وارد کن:", reply_markup=kb.cancel_kb())

    @router.message(ResellerProductFlow.waiting_volume)
    async def rprod_receive_volume(message: Message, state: FSMContext):
        text = (message.text or "").strip()
        if not text.isdigit() or int(text) <= 0:
            await message.answer("❌ لطفاً فقط عدد صحیح مثبت وارد کنید.")
            return
        await state.update_data(rprod_volume=int(text))
        await state.set_state(ResellerProductFlow.waiting_duration)
        await message.answer("مدت اعتبار این محصول را به روز وارد کن:", reply_markup=kb.cancel_kb())

    @router.message(ResellerProductFlow.waiting_duration)
    async def rprod_receive_duration(message: Message, state: FSMContext):
        text = (message.text or "").strip()
        if not text.isdigit() or int(text) <= 0:
            await message.answer("❌ لطفاً فقط عدد صحیح مثبت وارد کنید.")
            return
        await state.update_data(rprod_duration=int(text))
        await state.set_state(ResellerProductFlow.waiting_price)
        await message.answer("قیمت فروش این محصول را به تومان وارد کن:", reply_markup=kb.cancel_kb())

    @router.message(ResellerProductFlow.waiting_price)
    async def rprod_receive_price(message: Message, state: FSMContext):
        text = (message.text or "").strip()
        if not text.isdigit() or int(text) <= 0:
            await message.answer("❌ لطفاً فقط عدد صحیح مثبت وارد کنید.")
            return
        seller_type, seller_id = _reseller_seller_type_id(message.from_user.id)
        if not seller_type:
            await state.clear()
            return
        await state.update_data(rprod_price=int(text))
        await state.set_state(ResellerProductFlow.waiting_source)
        await message.answer(
            "این محصول رو از کجا تامین می‌کنی؟",
            reply_markup=kb.reseller_product_source_kb(),
        )

    @router.callback_query(F.data == "rprod_src:credit_pool", ResellerProductFlow.waiting_source)
    async def cb_rprod_src_credit(call: CallbackQuery, state: FSMContext):
        await _rprod_finalize(call.message, state, call.from_user.id, "credit_pool")
        await call.answer()

    @router.callback_query(F.data == "rprod_src:own_panel", ResellerProductFlow.waiting_source)
    async def cb_rprod_src_panel(call: CallbackQuery, state: FSMContext):
        servers = db.get_panel_servers(active_only=True)
        if not servers:
            await call.answer("هنوز هیچ پنلی وصل نکردی. اول از بخش پنل‌ها یکی اضافه کن.", show_alert=True)
            return
        await state.set_state(ResellerProductFlow.waiting_panel)
        await call.answer()
        await call.message.answer("کدام پنل شخصی خودت؟", reply_markup=kb.reseller_product_panel_select_kb(servers))

    @router.callback_query(F.data.startswith("rprod_panel:"), ResellerProductFlow.waiting_panel)
    async def cb_rprod_pick_panel(call: CallbackQuery, state: FSMContext):
        server_id = int(call.data.split(":")[1])
        await call.answer()
        await _rprod_finalize(call.message, state, call.from_user.id, "own_panel", panel_server_id=server_id)

    @router.callback_query(F.data == "rprod_src:stock", ResellerProductFlow.waiting_source)
    async def cb_rprod_src_stock(call: CallbackQuery, state: FSMContext):
        await state.set_state(ResellerProductFlow.waiting_stock)
        await call.answer()
        await call.message.answer(
            "لینک‌های اشتراک آماده رو بفرست، هر کدوم تو یک خط جدا (می‌تونی چندتا با هم بفرستی):",
            reply_markup=kb.cancel_kb(),
        )

    @router.message(ResellerProductFlow.waiting_stock)
    async def rprod_receive_stock(message: Message, state: FSMContext):
        links = [line.strip() for line in (message.text or "").splitlines() if line.strip()]
        if not links:
            await message.answer("❌ حداقل یک لینک بفرست.")
            return
        await state.update_data(rprod_stock_links=links)
        await _rprod_finalize(message, state, message.from_user.id, "stock")

    async def _rprod_finalize(message: Message, state: FSMContext, user_id: int, source_type: str, panel_server_id: int = None):
        seller_type, seller_id = _reseller_seller_type_id(user_id)
        if not seller_type:
            await state.clear()
            return
        data = await state.get_data()
        pid = db.create_reseller_product(
            seller_type, seller_id, data["rprod_title"], data["rprod_volume"], data["rprod_duration"], data["rprod_price"],
            source_type=source_type, panel_server_id=panel_server_id,
        )
        note = ""
        if source_type == "stock":
            links = data.get("rprod_stock_links", [])
            db.add_reseller_product_stock(pid, links)
            note = f"\n📥 {len(links)} لینک به انبار این محصول اضافه شد."
        await state.clear()
        products = db.list_reseller_products(seller_type=seller_type, seller_id=seller_id)
        await message.answer(
            f"✅ محصول ساخته شد و از همین الان به مشتری‌هات نمایش داده می‌شود.{note}",
            reply_markup=kb.reseller_products_list_kb(products),
        )

    @router.callback_query(F.data.startswith("rprod_view:"))
    async def cb_rprod_view(call: CallbackQuery):
        product_id = int(call.data.split(":")[1])
        product = db.get_reseller_product(product_id)
        seller_type, seller_id = _reseller_seller_type_id(call.from_user.id)
        if not product or not seller_type or product["seller_type"] != seller_type or product["seller_id"] != seller_id:
            await call.answer("محصول یافت نشد.", show_alert=True)
            return
        await call.message.edit_text(
            f"🛍 {product['title']}\n\n"
            f"📶 حجم: {product['volume_gb']} گیگ\n"
            f"⏳ مدت: {product['duration_days']} روز\n"
            f"💰 قیمت: {product['price']:,} تومان\n"
            f"وضعیت: {'🟢 فعال' if product['is_active'] else '🔴 غیرفعال'}",
            reply_markup=kb.reseller_product_view_kb(product_id),
        )
        await call.answer()

    @router.callback_query(F.data.startswith("rprod_toggle:"))
    async def cb_rprod_toggle(call: CallbackQuery):
        product_id = int(call.data.split(":")[1])
        product = db.get_reseller_product(product_id)
        seller_type, seller_id = _reseller_seller_type_id(call.from_user.id)
        if not product or not seller_type or product["seller_type"] != seller_type or product["seller_id"] != seller_id:
            await call.answer("محصول یافت نشد.", show_alert=True)
            return
        db.toggle_reseller_product(product_id)
        await cb_rprod_view(call)

    @router.callback_query(F.data.startswith("rprod_del:"))
    async def cb_rprod_del(call: CallbackQuery):
        product_id = int(call.data.split(":")[1])
        product = db.get_reseller_product(product_id)
        seller_type, seller_id = _reseller_seller_type_id(call.from_user.id)
        if not product or not seller_type or product["seller_type"] != seller_type or product["seller_id"] != seller_id:
            await call.answer("محصول یافت نشد.", show_alert=True)
            return
        db.delete_reseller_product(product_id)
        await call.answer("حذف شد.")
        await cb_reseller_products_menu(call)

    # -----------------------------------------------------------------------
    # شماره کارت اختصاصی زیرنماینده (پرداخت مشتری مستقیم به خودش)
    # -----------------------------------------------------------------------

    @router.callback_query(F.data == "subres_set_card")
    async def cb_subres_set_card(call: CallbackQuery, state: FSMContext):
        if not db.is_sub_reseller(call.from_user.id):
            await call.answer("دسترسی نداری.", show_alert=True)
            return
        await state.set_state(SubResellerCardFlow.waiting_number)
        await call.answer()
        await call.message.answer("شماره کارت ۱۶ رقمی خودت رو بفرست:", reply_markup=kb.cancel_kb())

    @router.message(SubResellerCardFlow.waiting_number)
    async def subres_receive_card_number(message: Message, state: FSMContext):
        number = re.sub(r"\D", "", message.text or "")
        if len(number) != 16:
            await message.answer("❌ شماره کارت باید دقیقاً ۱۶ رقم باشد.")
            return
        await state.update_data(card_number=number)
        await state.set_state(SubResellerCardFlow.waiting_holder)
        await message.answer("نام و نام‌خانوادگی صاحب کارت را بفرست:", reply_markup=kb.cancel_kb())

    @router.message(SubResellerCardFlow.waiting_holder)
    async def subres_receive_card_holder(message: Message, state: FSMContext):
        holder = (message.text or "").strip()
        if not holder:
            await message.answer("❌ نام نامعتبر است.")
            return
        data = await state.get_data()
        sub = db.get_sub_reseller_by_telegram_id(message.from_user.id)
        if not sub:
            await state.clear()
            return
        db.set_sub_reseller_card(sub["id"], data["card_number"], holder)
        await state.clear()
        await message.answer(
            "✅ شماره کارتت ثبت شد. از این به بعد مشتری‌هایی که از محصولات تو خرید می‌کنن، مستقیم به این کارت پرداخت می‌کنن.",
            reply_markup=kb.menu_for_user(db, message.from_user.id),
        )

    # -----------------------------------------------------------------------
    # فروشگاه بانک کانفیگ نمایندگان (نمایش به مشتری + خرید و تحویل خودکار)
    # -----------------------------------------------------------------------

    async def _notify_seller_of_order(bot: Bot, order_id: int, receipt_file_id: str = None):
        order = db.get_order(order_id)
        product = db.get_reseller_product(order["reseller_product_id"])
        if not product:
            return
        buyer = db.get_user(order["user_id"])
        buyer_label = f"@{buyer['username']}" if buyer and buyer["username"] else str(order["user_id"])
        caption = (
            f"🛍 سفارش جدید از بانک کانفیگ\n\n"
            f"📦 محصول: {product['title']} ({product['volume_gb']} گیگ / {product['duration_days']} روز)\n"
            f"🧑 مشتری: {buyer_label}\n"
            f"🛠 یوزرنیم درخواستی: {order['custom_username']}\n"
            f"💰 مبلغ: {order['final_price']:,} تومان\n"
        )
        recipients = db.list_admins() if product["seller_type"] == "owner" else [product["seller_id"]]
        for chat_id in recipients:
            try:
                if receipt_file_id:
                    msg = await bot.send_photo(chat_id, receipt_file_id, caption=caption, reply_markup=kb.reseller_order_review_kb(order_id))
                else:
                    msg = await bot.send_message(chat_id, caption, reply_markup=kb.reseller_order_review_kb(order_id))
                db.set_order_admin_message(order_id, chat_id, msg.message_id)
            except Exception:
                pass

    @router.callback_query(F.data == "rstore_open")
    async def cb_rstore_open(call: CallbackQuery):
        products = db.list_reseller_products(seller_type="owner", active_only=True)
        if not products:
            await call.answer("در حال حاضر محصولی موجود نیست.", show_alert=True)
            return
        await call.message.edit_text(
            "🛍 بانک کانفیگ\n\nیکی از محصولات زیر را انتخاب کن:",
            reply_markup=kb.reseller_storefront_kb(products),
        )
        await call.answer()

    @router.callback_query(F.data.startswith("rstore_view:"))
    async def cb_rstore_view(call: CallbackQuery):
        product_id = int(call.data.split(":")[1])
        product = db.get_reseller_product(product_id)
        if not product or not product["is_active"]:
            await call.answer("این محصول دیگر موجود نیست.", show_alert=True)
            return
        back_cb = "rstore_open" if product["seller_type"] == "owner" else "back_main"
        await call.message.edit_text(
            f"🛍 {product['title']}\n\n"
            f"📶 حجم: {product['volume_gb']} گیگ\n"
            f"⏳ مدت: {product['duration_days']} روز\n"
            f"💰 قیمت: {product['price']:,} تومان",
            reply_markup=kb.reseller_storefront_confirm_kb(product_id, back_callback=back_cb),
        )
        await call.answer()

    @router.callback_query(F.data.startswith("rstore_buy:"))
    async def cb_rstore_buy(call: CallbackQuery, state: FSMContext):
        product_id = int(call.data.split(":")[1])
        product = db.get_reseller_product(product_id)
        if not product or not product["is_active"]:
            await call.answer("این محصول دیگر موجود نیست.", show_alert=True)
            return
        await state.set_state(ResellerStoreFlow.waiting_username)
        await state.update_data(rstore_product_id=product_id)
        await call.answer()
        await call.message.answer(
            "یک نام کاربری برای این کانفیگ وارد کن، یا از دکمه‌ی زیر یک نام تصادفی بگیر.\n"
            "فقط حروف انگلیسی، عدد و آندرلاین (بین ۳ تا ۲۰ کاراکتر).",
            reply_markup=kb.custom_config_username_kb(),
        )

    @router.callback_query(F.data == "custom_config_random_username", ResellerStoreFlow.waiting_username)
    async def cb_rstore_random_username(call: CallbackQuery, state: FSMContext):
        for _ in range(10):
            candidate = "s" + "".join(random.choices("abcdefghijklmnopqrstuvwxyz0123456789", k=8))
            if not db.is_custom_username_taken(candidate):
                break
        await call.answer()
        await _rstore_apply_username(call.message, state, candidate)

    @router.message(ResellerStoreFlow.waiting_username)
    async def rstore_receive_username(message: Message, state: FSMContext):
        username = (message.text or "").strip()
        if not re.fullmatch(r"[A-Za-z0-9_]{3,20}", username):
            await message.answer("❌ نام کاربری نامعتبر است. فقط حروف انگلیسی، عدد و آندرلاین، بین ۳ تا ۲۰ کاراکتر.")
            return
        if db.is_custom_username_taken(username):
            await message.answer("❌ این نام کاربری قبلاً استفاده شده. لطفاً نام دیگری انتخاب کنید.")
            return
        await _rstore_apply_username(message, state, username)

    async def _rstore_apply_username(message: Message, state: FSMContext, username: str):
        data = await state.get_data()
        product = db.get_reseller_product(data["rstore_product_id"])
        if not product or not product["is_active"]:
            await state.clear()
            await message.answer("⛔️ این محصول دیگر موجود نیست.")
            return

        wallet_credit = db.get_wallet_credit(message.from_user.id)
        wallet_used = min(wallet_credit, product["price"])
        if wallet_used > 0:
            db.add_wallet_credit(message.from_user.id, -wallet_used)

        sub_reseller_id = None
        if product["seller_type"] == "sub_reseller":
            sub = db.get_sub_reseller_by_telegram_id(product["seller_id"])
            sub_reseller_id = sub["id"] if sub else None

        order_id = db.create_reseller_product_order(
            message.from_user.id, product["id"], username, product["price"],
            wallet_used=wallet_used, sub_reseller_id=sub_reseller_id,
        )
        order = db.get_order(order_id)
        await state.update_data(order_id=order_id)

        if order["final_price"] <= 0:
            await state.clear()
            ok, info = await _rstore_provision(message.bot, order_id)
            if ok:
                await message.answer(
                    "✅ مبلغ سفارش شما به‌طور کامل از کیف پول پوشش داده شد.\n"
                    "کانفیگ شما در پیام بعدی ارسال می‌شود 👇",
                    reply_markup=kb.menu_for_user(db, message.from_user.id),
                )
            else:
                await message.answer(f"⛔️ خطا در ساخت کانفیگ: {info}\nمبلغ به کیف پول بازگردانده شد.")
            return

        await state.set_state(ResellerStoreFlow.waiting_receipt)
        if product["seller_type"] == "sub_reseller" and sub_reseller_id:
            sub = db.get_sub_reseller(sub_reseller_id)
            card_number = sub["card_number"] or db.get_setting("card_number")
            card_holder = sub["card_holder_name"] or db.get_setting("card_holder")
        else:
            card_number = db.get_setting("card_number")
            card_holder = db.get_setting("card_holder")
        text = (
            f"🛍 {product['title']}\n"
            f"🛠 نام کاربری: {username}\n\n"
            f"💳 شماره کارت: `{card_number}`\n"
            f"👤 به نام: {card_holder}\n"
        )
        if wallet_used:
            text += f"👛 استفاده از کیف پول: {wallet_used:,} تومان\n"
        text += f"💰 مبلغ نهایی قابل پرداخت: {order['final_price']:,} تومان\n\n"
        text += "لطفاً عکس رسید پرداخت را همینجا ارسال کنید."
        await message.answer(text, parse_mode="Markdown", reply_markup=kb.cancel_kb())

    @router.message(ResellerStoreFlow.waiting_receipt, F.photo)
    async def rstore_receive_receipt(message: Message, state: FSMContext, bot: Bot):
        data = await state.get_data()
        order_id = data.get("order_id")
        order = db.get_order(order_id)
        if not order or order["status"] != "pending":
            await message.answer("سفارش معتبر یافت نشد. لطفاً دوباره از منو شروع کنید.")
            await state.clear()
            return
        file_id = message.photo[-1].file_id
        db.set_order_receipt(order_id, file_id)
        await _notify_seller_of_order(bot, order_id, receipt_file_id=file_id)
        await message.answer(
            "✅ رسید شما برای بررسی ارسال شد. پس از تایید، کانفیگ برای شما ساخته و ارسال خواهد شد.",
            reply_markup=kb.menu_for_user(db, message.from_user.id),
        )
        await state.clear()

    @router.message(ResellerStoreFlow.waiting_receipt)
    async def rstore_receipt_wrong_type(message: Message):
        await message.answer("لطفاً فقط عکس رسید پرداخت را ارسال کنید.")

    async def _rstore_provision(bot: Bot, order_id: int):
        """ساخت/تحویل خودکار کانفیگ + کسر اعتبار (در صورت نیاز) + تحویل به خریدار. خروجی: (ok, error_or_None)"""
        order = db.get_order(order_id)
        product = db.get_reseller_product(order["reseller_product_id"])
        if not product:
            db.reject_order(order_id)
            return False, "محصول یافت نشد."

        source_type = product["source_type"] if "source_type" in product.keys() else "credit_pool"

        if source_type == "stock":
            item = db.take_reseller_product_stock(product["id"], order_id=order_id)
            if not item:
                return False, "انبار این محصول خالی شده. با فروشنده هماهنگ کن."
            placeholder_panel_id = db.get_or_create_stock_placeholder_panel()
            db.approve_custom_config_order(order_id)
            db.add_custom_config(
                order["user_id"], placeholder_panel_id, order["custom_username"], product["volume_gb"], product["duration_days"],
                item["subscription_url"], order_id=order_id, source="reseller_product",
            )
            try:
                await deliver_config_to_user(
                    bot, order["user_id"], product["title"], [item["subscription_url"]],
                    final_price=order["final_price"], order_id=order_id,
                )
            except Exception:
                pass
            return True, None

        if source_type == "own_panel":
            server = db.get_panel_server(product["panel_server_id"])
        else:
            server = _reseller_resolve_panel(product["seller_type"], product["seller_id"])
        if not server:
            return False, "سروری برای این محصول تنظیم نشده."

        try:
            provider = get_provider(server)
            result = await provider.create_user(order["custom_username"], product["volume_gb"], product["duration_days"])
        except PanelUsernameTakenError:
            return False, "این نام کاربری روی پنل تکراری است."
        except PanelError as e:
            return False, str(e)

        db.approve_custom_config_order(order_id)
        db.add_custom_config(
            order["user_id"], server["id"], result.username, product["volume_gb"], product["duration_days"],
            result.subscription_url, order_id=order_id, source="reseller_product",
        )
        if source_type == "credit_pool":
            if product["seller_type"] == "owner":
                db.adjust_reseller_credit(product["seller_id"], -product["volume_gb"], reason=f"فروش «{product['title']}» به مشتری")
            elif order["sub_reseller_id"]:
                db.adjust_sub_reseller_credit(order["sub_reseller_id"], -product["volume_gb"], reason=f"فروش «{product['title']}» به مشتری")
        # source_type == 'own_panel': پنل شخصی خودشونه، از استخر گیگ چیزی کم نمی‌شود.

        try:
            await deliver_config_to_user(
                bot, order["user_id"], product["title"], [result.subscription_url],
                final_price=order["final_price"], order_id=order_id,
            )
        except Exception:
            pass
        return True, None

    @router.callback_query(F.data.startswith("rporder_approve:"))
    async def cb_rporder_approve(call: CallbackQuery):
        order_id = int(call.data.split(":")[1])
        order = db.get_order(order_id)
        if not order or not order["is_reseller_product"]:
            await call.answer("سفارش نامعتبر است.", show_alert=True)
            return
        if order["status"] != "pending":
            await call.answer("این سفارش قبلاً بررسی شده است.", show_alert=True)
            return
        product = db.get_reseller_product(order["reseller_product_id"])
        allowed = product and (
            (product["seller_type"] == "owner" and db.is_admin(call.from_user.id)) or
            (product["seller_type"] == "sub_reseller" and call.from_user.id == product["seller_id"])
        )
        if not allowed:
            await call.answer("اجازه‌ی این کار را نداری.", show_alert=True)
            return

        ok, err = await _rstore_provision(call.bot, order_id)
        if not ok:
            await call.answer(f"⛔️ {err}", show_alert=True)
            return
        try:
            if call.message.photo:
                await call.message.edit_caption(caption=(call.message.caption or "") + "\n\n✅ تایید شد و کانفیگ ساخته شد.")
            else:
                await call.message.edit_text((call.message.text or "") + "\n\n✅ تایید شد و کانفیگ ساخته شد.")
        except Exception:
            pass
        await call.answer("تایید شد.")

    @router.callback_query(F.data.startswith("rporder_reject:"))
    async def cb_rporder_reject(call: CallbackQuery):
        order_id = int(call.data.split(":")[1])
        order = db.get_order(order_id)
        if not order or not order["is_reseller_product"]:
            await call.answer("سفارش نامعتبر است.", show_alert=True)
            return
        if order["status"] != "pending":
            await call.answer("این سفارش قبلاً بررسی شده است.", show_alert=True)
            return
        product = db.get_reseller_product(order["reseller_product_id"])
        allowed = product and (
            (product["seller_type"] == "owner" and db.is_admin(call.from_user.id)) or
            (product["seller_type"] == "sub_reseller" and call.from_user.id == product["seller_id"])
        )
        if not allowed:
            await call.answer("اجازه‌ی این کار را نداری.", show_alert=True)
            return
        if order["wallet_used"]:
            db.add_wallet_credit(order["user_id"], order["wallet_used"])
        db.reject_order(order_id)
        try:
            await call.bot.send_message(order["user_id"], "❌ متاسفانه سفارش شما رد شد. در صورت کسر از کیف پول، مبلغ بازگردانده شد.")
        except Exception:
            pass
        try:
            if call.message.photo:
                await call.message.edit_caption(caption=(call.message.caption or "") + "\n\n❌ رد شد.")
            else:
                await call.message.edit_text((call.message.text or "") + "\n\n❌ رد شد.")
        except Exception:
            pass
        await call.answer("رد شد.")

    # -----------------------------------------------------------------------
    # درخواست نمایندگی
    # -----------------------------------------------------------------------

    @router.message(F.text.func(lambda t: t == db.get_setting("btn_reseller_request", "🤝 درخواست نمایندگی")))
    async def reseller_request_start(message: Message, state: FSMContext):
        if db.is_reseller(message.from_user.id):
            await message.answer("شما همین الان هم نماینده هستید.")
            return
        if db.has_pending_reseller_request(message.from_user.id):
            await message.answer("درخواست قبلی شما هنوز در حال بررسی است؛ لطفاً منتظر بمانید.")
            return
        is_main = db.get_setting("is_main_bot", "1") == "1"
        text = (
            "🤝 درخواست نمایندگی\n\n"
            "کدام حالت را می‌خواهی؟\n\n"
        )
        if is_main:
            text += "🤖 <b>بات خام مستقل</b>: یک بات جدا با آیدی خودت که کاملاً مستقل مدیریتش می‌کنی.\n"
            text += "📦 <b>بات با حجم</b>: یک بات جدا با آیدی خودت (مثل بات مستقل) به‌علاوه‌ی یک استخر گیگابایت که خودت هرجور بخواهی ازش کانفیگ می‌سازی."
        else:
            text += "📦 <b>زیرنمایندگی</b>: داخل همین بات، با یک استخر گیگابایت (از سهم همین نماینده) که خودت هرجور بخواهی ازش کانفیگ می‌سازی و حتی می‌تونی شماره کارت خودت رو هم بذاری."
        await message.answer(
            text, parse_mode="HTML",
            reply_markup=kb.reseller_request_type_kb(show_bot_option=is_main),
        )

    @router.callback_query(F.data.startswith("reseller_req_type:"))
    async def cb_reseller_request_type(call: CallbackQuery, state: FSMContext):
        req_type = call.data.split(":")[1]
        await state.update_data(reseller_request_type=req_type)
        await state.set_state(ResellerRequestFlow.waiting_note)
        await call.answer()
        await call.message.answer(
            "اگه توضیح یا درخواست خاصی داری بنویس (مثلاً حجم تقریبی مدنظرت)، وگرنه فقط بنویس «ندارم».",
            reply_markup=kb.cancel_kb(),
        )

    @router.message(ResellerRequestFlow.waiting_note)
    async def reseller_request_receive_note(message: Message, state: FSMContext, bot: Bot):
        data = await state.get_data()
        note = message.text.strip()
        request_id = db.create_reseller_request(message.from_user.id, data["reseller_request_type"], note)
        await state.clear()
        await message.answer(
            "✅ درخواست شما ثبت شد و برای ادمین ارسال شد. نتیجه رو بهت اطلاع می‌دیم.",
            reply_markup=kb.menu_for_user(db, message.from_user.id),
        )

        user = db.get_user(message.from_user.id)
        is_main_req = db.get_setting("is_main_bot", "1") == "1"
        if data["reseller_request_type"] == "bot":
            type_label = "🤖 بات خام مستقل"
        elif is_main_req:
            type_label = "📦 بات با حجم"
        else:
            type_label = "📦 زیرنمایندگی"
        text = (
            f"🤝 درخواست نمایندگی جدید #{request_id}\n"
            f"👤 {user['first_name'] if user else ''} (@{user['username'] if user and user['username'] else '---'})\n"
            f"🆔 آیدی: {message.from_user.id}\n"
            f"نوع: {type_label}\n"
            f"توضیح: {note}"
        )
        for admin_id in db.list_admins():
            try:
                needs_price = data["reseller_request_type"] == "bot" or (data["reseller_request_type"] == "credit" and is_main_req)
                await bot.send_message(
                    admin_id, text,
                    reply_markup=kb.reseller_request_admin_kb(request_id, data["reseller_request_type"], needs_price=needs_price),
                )
            except Exception:
                pass

    @router.message(F.text.func(lambda t: t == db.get_setting("btn_my_orders")))
    async def my_orders(message: Message):
        orders = db.get_user_orders(message.from_user.id)
        custom_configs = db.get_custom_configs_for_user(message.from_user.id)
        if not orders and not custom_configs:
            await message.answer("شما تاکنون سفارشی ثبت نکرده‌اید.")
            return

        status_map = {"pending": "⏳ در انتظار بررسی", "approved": "✅ تایید شده", "rejected": "❌ رد شده"}
        lines = []
        approved = []  # (product_name, link)
        for o in orders:
            if o["is_custom_config"]:
                pname = f"کانفیگ شخصی «{o['custom_username']}» ({o['custom_volume_gb']} گیگ)"
            else:
                product = db.get_product(o["product_id"])
                pname = product["name"] if product else "نامشخص"
            qty = o["quantity"] or 1
            line = f"#{o['id']} | {pname}" + (f" × {qty}" if qty > 1 else "") + f" | {status_map.get(o['status'], o['status'])}"
            if o["status"] == "approved" and not o["is_custom_config"]:
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

        for cc in custom_configs:
            pname = f"کانفیگ شخصی «{cc['username']}»"
            line = f"🛠 {pname} | {cc['volume_gb']} گیگ | {cc['duration_days']} روز"
            if cc["subscription_url"]:
                line += f"\n🔗 `{cc['subscription_url']}`"
                approved.append((pname, cc["subscription_url"]))
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
