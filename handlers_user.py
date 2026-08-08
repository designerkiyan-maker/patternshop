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

from aiogram import Router, F, Bot
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

import keyboards as kb
from states import BuyFlow, ContactFlow, DiscountEntry, WalletTopup
from config import MAX_TEST_PER_USER


def create_user_router(db) -> Router:
    router = Router()

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
    # خرید کانفیگ
    # -----------------------------------------------------------------------

    @router.message(F.text.func(lambda t: t == db.get_setting("btn_buy")))
    async def show_categories(message: Message, state: FSMContext):
        await state.clear()
        categories = db.get_categories(active_only=True)
        if not categories:
            await message.answer("در حال حاضر دسته‌بندی فعالی وجود ندارد.")
            return
        await message.answer("یک دسته‌بندی را انتخاب کنید:", reply_markup=kb.categories_kb(categories))

    @router.callback_query(F.data == "back_main")
    async def cb_back_main(call: CallbackQuery, state: FSMContext):
        await state.clear()
        await call.message.delete()
        await call.answer()

    @router.callback_query(F.data == "back_categories")
    async def cb_back_categories(call: CallbackQuery):
        categories = db.get_categories(active_only=True)
        await call.message.edit_text("یک دسته‌بندی را انتخاب کنید:", reply_markup=kb.categories_kb(categories))
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

    @router.callback_query(F.data.startswith("prod:"))
    async def cb_product(call: CallbackQuery):
        product_id = int(call.data.split(":")[1])
        product = db.get_product(product_id)
        if not product:
            await call.answer("محصول یافت نشد.", show_alert=True)
            return
        stock = db.count_available_configs(product_id)
        wallet_credit = db.get_wallet_credit(call.from_user.id)
        text = (
            f"📦 {product['name']}\n"
            f"💰 قیمت: {product['price']:,} تومان\n"
            f"📝 توضیحات: {product['description'] or '---'}\n"
            f"📊 موجودی: {stock} عدد\n"
        )
        if wallet_credit > 0:
            text += f"\n👛 موجودی کیف پول شما: {wallet_credit:,} تومان (به‌صورت خودکار در پرداخت اعمال می‌شود)\n"
        if stock <= 0:
            text += "\n⛔️ در حال حاضر موجودی این محصول تمام شده است."
            await call.message.edit_text(text)
            await call.answer()
            return
        await call.message.edit_text(text, reply_markup=kb.product_confirm_kb(product_id))
        await call.answer()

    @router.callback_query(F.data.startswith("enter_code:"))
    async def cb_enter_code(call: CallbackQuery, state: FSMContext):
        product_id = int(call.data.split(":")[1])
        await state.update_data(discount_product_id=product_id)
        await state.set_state(DiscountEntry.waiting_code)
        await call.message.edit_text("🎟 کد تخفیف را ارسال کنید:", reply_markup=kb.cancel_kb())
        await call.answer()

    @router.message(DiscountEntry.waiting_code)
    async def process_discount_code(message: Message, state: FSMContext):
        data = await state.get_data()
        product_id = data.get("discount_product_id")
        product = db.get_product(product_id) if product_id else None
        if not product:
            await message.answer("محصول معتبر نیست. لطفاً دوباره از منو شروع کنید.")
            await state.clear()
            return

        code_row = db.get_discount_code(message.text.strip())
        if not db.is_discount_code_valid(code_row):
            await message.answer(
                "❌ این کد تخفیف نامعتبر، غیرفعال یا به سقف استفاده رسیده است. دوباره تلاش کنید یا بدون کد ادامه دهید.",
                reply_markup=kb.cancel_kb(),
            )
            return

        discount_amount = db.compute_discount_amount(code_row, product["price"])
        await state.update_data(discount_code_id=code_row["id"], discount_amount=discount_amount)
        await state.set_state(None)

        stock = db.count_available_configs(product_id)
        wallet_credit = db.get_wallet_credit(message.from_user.id)
        price_after_code = product["price"] - discount_amount
        wallet_used_preview = min(wallet_credit, price_after_code)
        final_preview = price_after_code - wallet_used_preview

        text = (
            f"✅ کد تخفیف اعمال شد!\n\n"
            f"📦 {product['name']}\n"
            f"💰 قیمت اصلی: {product['price']:,} تومان\n"
            f"🎟 تخفیف کد: {discount_amount:,} تومان\n"
        )
        if wallet_used_preview > 0:
            text += f"👛 اعمال کیف پول: {wallet_used_preview:,} تومان\n"
        text += f"💵 مبلغ نهایی قابل پرداخت: {final_preview:,} تومان\n"
        text += f"📊 موجودی: {stock} عدد"

        await message.answer(text, reply_markup=kb.product_confirm_kb(product_id))

    async def _notify_admins_of_order(bot: Bot, order_id: int, receipt_file_id: str = None):
        order = db.get_order(order_id)
        product = db.get_product(order["product_id"])
        user_row = db.get_user(order["user_id"])
        username = user_row["username"] if user_row else ""
        first_name = user_row["first_name"] if user_row else ""

        caption = (
            f"🧾 سفارش #{order_id}\n"
            f"👤 کاربر: {first_name or ''} (@{username or '---'})\n"
            f"🆔 آیدی عددی: `{order['user_id']}`\n"
            f"📦 محصول: {product['name']}\n"
            f"💰 قیمت پایه: {order['base_price']:,} تومان\n"
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

        for admin_id in db.list_admins():
            try:
                if receipt_file_id:
                    sent = await bot.send_photo(
                        admin_id, receipt_file_id, caption=caption, parse_mode="Markdown",
                        reply_markup=reply_markup,
                    )
                else:
                    if not already_approved:
                        caption += "\n\n(بدون نیاز به رسید - مبلغ کاملاً از کیف پول/تخفیف پوشش داده شده)"
                    sent = await bot.send_message(
                        admin_id, caption, parse_mode="Markdown", reply_markup=reply_markup,
                    )
                db.set_order_admin_message(order_id, admin_id, sent.message_id)
            except Exception:
                pass

    @router.callback_query(F.data.startswith("buy_start:"))
    async def cb_buy_start(call: CallbackQuery, state: FSMContext, bot: Bot):
        product_id = int(call.data.split(":")[1])
        product = db.get_product(product_id)
        if not product or db.count_available_configs(product_id) <= 0:
            await call.answer("این محصول در حال حاضر موجود نیست.", show_alert=True)
            return

        data = await state.get_data()
        discount_code_id = data.get("discount_code_id")
        discount_amount = data.get("discount_amount", 0) or 0

        wallet_credit = db.get_wallet_credit(call.from_user.id)
        price_after_code = max(product["price"] - discount_amount, 0)
        wallet_used = min(wallet_credit, price_after_code)

        if wallet_used > 0:
            db.add_wallet_credit(call.from_user.id, -wallet_used)
        if discount_code_id:
            db.increment_discount_usage(discount_code_id)

        order_id = db.create_order(
            call.from_user.id,
            product_id,
            base_price=product["price"],
            wallet_used=wallet_used,
            discount_code_id=discount_code_id,
            discount_amount=discount_amount,
        )
        order = db.get_order(order_id)
        await state.update_data(order_id=order_id)
        await state.update_data(discount_code_id=None, discount_amount=0, discount_product_id=None)

        if order["final_price"] <= 0:
            await state.clear()

            result = db.take_unused_config(product_id, call.from_user.id)
            if not result:
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

            db.approve_order(order_id, result["id"])

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
                f"🔗 کانفیگ شما:\n`{result['link']}`",
                parse_mode="Markdown",
            )
            await call.answer()
            return

        await state.set_state(BuyFlow.waiting_receipt)

        card_number = db.get_setting("card_number")
        card_holder = db.get_setting("card_holder")
        after_buy_text = db.get_setting("after_buy_text")

        text = f"{after_buy_text}\n\n"
        text += f"💳 شماره کارت: `{card_number}`\n"
        text += f"👤 به نام: {card_holder}\n"
        if discount_amount:
            text += f"🎟 تخفیف کد: {discount_amount:,} تومان\n"
        if wallet_used:
            text += f"👛 استفاده از کیف پول: {wallet_used:,} تومان\n"
        text += f"💰 مبلغ نهایی قابل پرداخت: {order['final_price']:,} تومان\n\n"
        text += "لطفاً عکس رسید پرداخت را همینجا ارسال کنید."

        await call.message.edit_text(text, parse_mode="Markdown", reply_markup=kb.cancel_kb())
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
        for o in orders:
            product = db.get_product(o["product_id"])
            pname = product["name"] if product else "نامشخص"
            line = f"#{o['id']} | {pname} | {status_map.get(o['status'], o['status'])}"
            if o["status"] == "approved" and o["config_id"]:
                cfg = db.get_config_by_id(o["config_id"])
                if cfg:
                    line += f"\n🔗 `{cfg['link']}`"
            lines.append(line)
        await message.answer("\n\n".join(lines), parse_mode="Markdown")

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
        await message.answer(text, parse_mode="Markdown", reply_markup=kb.cancel_kb())

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
            f"🆔 آیدی عددی: `{message.from_user.id}`\n"
            f"💰 مبلغ: {amount:,} تومان"
        )
        for admin_id in db.list_admins():
            try:
                sent = await bot.send_photo(
                    admin_id, file_id, caption=caption, parse_mode="Markdown",
                    reply_markup=kb.topup_review_kb(topup_id),
                )
                db.set_topup_admin_message(topup_id, admin_id, sent.message_id)
            except Exception:
                pass

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
        text = (
            f"📩 پیام جدید از کاربر\n"
            f"👤 {user.first_name or ''} (@{user.username or '---'})\n"
            f"🆔 `{user.id}`\n\n"
            f"✉️ {message.text or '(بدون متن / رسانه)'}"
        )
        for admin_id in db.list_admins():
            try:
                await bot.send_message(admin_id, text, parse_mode="Markdown", reply_markup=kb.contact_reply_kb(user.id))
            except Exception:
                pass
        await message.answer(
            "پیام شما برای پشتیبانی ارسال شد. به زودی پاسخ داده می‌شود.",
            reply_markup=kb.menu_for_user(db, user.id),
        )
        await state.clear()

    return router
