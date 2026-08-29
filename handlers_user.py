# -*- coding: utf-8 -*-
"""
هندلرهای مربوط به کاربر عادی

این فایل یک تابع کارخانه‌ای (factory) دارد: create_user_router(db).
این تابع یک Router تازه می‌سازد که به db گره خورده؛ محصولات فروشگاه،
الگوهای خیاطی (PDF) هستند که پس از تایید پرداخت به‌صورت فایل تلگرامی
تحویل داده می‌شوند (ماژول file_delivery).
"""

import random
import asyncio
import logging
import html

from aiogram import Router, F, Bot
from aiogram.filters import CommandStart, StateFilter
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramRetryAfter, TelegramForbiddenError, TelegramBadRequest, TelegramNetworkError

import keyboards as kb
from states import BuyFlow, ContactFlow, DiscountEntry, WalletTopup, LoyaltyRedeem
from config import MAX_TEST_PER_USER
from file_delivery import deliver_pattern_to_user
from force_join import is_channel_member, CHECK_CALLBACK
import loyalty
from loyalty import LoyaltyError
from jalali import to_jalali_str


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
    async def _send_receipt_to_admin(bot: Bot, admin_id: int, file_id: str, receipt_type: str, caption: str, reply_markup=None):
        if receipt_type == "document":
            return await bot.send_document(admin_id, file_id, caption=caption, reply_markup=reply_markup)
        return await bot.send_photo(admin_id, file_id, caption=caption, reply_markup=reply_markup)

    def _receipt_payload(message: Message):
        if message.photo:
            return message.photo[-1].file_id, "photo"
        if message.document:
            return message.document.file_id, "document"
        return None, None
    router = Router()

    async def _send_inline_main_menu(target, user_tg_id: int):
        """اگر منوی شیشه‌ای بالا از تنظیمات فعال باشد، آن را به‌عنوان یک پیام
        جدا (کنار/بعد از منوی پایین) ارسال می‌کند. target هر شیء‌ای است که
        متد answer async دارد (Message یا call.message)."""
        inline_kb = (await asyncio.to_thread(kb.inline_menu_for_user, db, user_tg_id))
        if inline_kb is not None:
            await target.answer("📋 منو:", reply_markup=inline_kb)

    # -----------------------------------------------------------------------
    # عضویت اجباری در کانال
    # -----------------------------------------------------------------------

    @router.callback_query(F.data == CHECK_CALLBACK)
    async def cb_check_force_join(call: CallbackQuery, bot: Bot):
        settings = (await asyncio.to_thread(db.get_force_join_settings))
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
            welcome = (await asyncio.to_thread(db.get_setting, "welcome_text"))
            await call.message.answer(welcome, reply_markup=kb.menu_for_user(db, call.from_user.id))
            await _send_inline_main_menu(call.message, call.from_user.id)
        else:
            await call.answer("❌ هنوز عضو کانال نشده‌اید.", show_alert=True)

    # -----------------------------------------------------------------------
    # شروع
    # -----------------------------------------------------------------------

    @router.message(CommandStart())
    async def cmd_start(message: Message, state: FSMContext, bot: Bot):
        await state.clear()
        (await asyncio.to_thread(db.add_or_update_user,
            message.from_user.id, message.from_user.username or "", message.from_user.first_name or ""
        ))

        # امتیاز خوش‌آمدگویی باشگاه مشتریان (خودکار، یک‌بار برای هر کاربر؛
        # هر خطا نباید در مسیر /start اختلال ایجاد کند)
        try:
            reg_points = (await asyncio.to_thread(loyalty.award_registration, db, message.from_user.id))
        except Exception:
            logging.getLogger("handlers_user").exception(
                "اعطای امتیاز خوش‌آمدگویی به کاربر %s ناموفق بود.", message.from_user.id
            )
            reg_points = 0

        # پردازش لینک دعوت زیرمجموعه‌گیری: /start ref123456789
        # (نیازی به «کاربر جدید بودن» نیست؛ خود set_referred_by فقط وقتی کاربر
        # هنوز referred_by ندارد آن را ثبت می‌کند - همین‌جا هم برای جلوگیری از
        # اعمال چندباره‌ی پاداش‌های حالت ۲/۳، دقیقاً همان شرط را چک می‌کنیم)
        parts = (message.text or "").split(maxsplit=1)
        if len(parts) > 1 and parts[1].startswith("ref"):
            ref_part = parts[1][3:]
            if ref_part.isdigit() and int(ref_part) != message.from_user.id:
                referrer_id = int(ref_part)
                already_referred = (await asyncio.to_thread(db.get_user, message.from_user.id))
                already_referred = bool(already_referred and already_referred["referred_by"])
                if not already_referred:
                    (await asyncio.to_thread(db.set_referred_by, message.from_user.id, referrer_id))
                    # امتیاز معرفی باشگاه مشتریان برای دعوت‌کننده (idempotent)
                    try:
                        ref_points = (await asyncio.to_thread(
                            loyalty.award_referral, db, referrer_id, message.from_user.id
                        ))
                    except Exception:
                        logging.getLogger("handlers_user").exception(
                            "اعطای امتیاز معرفی به دعوت‌کننده %s ناموفق بود.", referrer_id
                        )
                        ref_points = 0
                    if ref_points > 0:
                        try:
                            await bot.send_message(
                                referrer_id,
                                f"🎁 {ref_points} امتیاز باشگاه مشتریان بابت معرفی دوستتان اضافه شد!",
                            )
                        except Exception:
                            pass
                    reward_info = (await asyncio.to_thread(
                        db.apply_referral_invite_rewards, message.from_user.id, referrer_id
                    ))
                    await _handle_referral_invite_rewards(bot, referrer_id, reward_info)

        welcome = (await asyncio.to_thread(db.get_setting, "welcome_text"))
        await message.answer(welcome, reply_markup=kb.menu_for_user(db, message.from_user.id))
        await _send_inline_main_menu(message, message.from_user.id)
        if reg_points > 0:
            try:
                await message.answer(f"🎁 {reg_points} امتیاز خوش‌آمدگویی به شما اضافه شد!")
            except Exception:
                pass

    async def _handle_referral_invite_rewards(bot: Bot, referrer_id: int, reward_info: dict):
        """پیام و تحویل جوایز حالت‌های ۲ و ۳ زیرمجموعه‌گیری (که با صرفِ دعوت، بدون
        نیاز به خرید زیرمجموعه، فعال می‌شوند) را برای دعوت‌کننده انجام می‌دهد."""
        if not reward_info:
            return

        invite_bonus = reward_info.get("invite_bonus")
        if invite_bonus:
            try:
                await bot.send_message(
                    referrer_id,
                    f"🤝 یک نفر با لینک دعوت شما به بات آمد!\n"
                    f"💰 {invite_bonus:,} تومان به کیف پول شما اضافه شد.",
                )
            except Exception:
                pass

        free_product_id = reward_info.get("free_config_product_id")
        if free_product_id:
            product = (await asyncio.to_thread(db.get_product, free_product_id))
            files = (await asyncio.to_thread(db.get_product_files, free_product_id)) if product else []
            if not product or not files:
                # محصول جایزه حذف شده یا ادمین هنوز فایلی برایش آپلود نکرده است
                try:
                    await bot.send_message(
                        referrer_id,
                        "🎁 شما با تعداد دعوت‌های خود، یک الگوی رایگان برنده شدید! "
                        "اما هم‌اکنون فایل این الگو در دسترس نیست. لطفاً با پشتیبانی تماس بگیرید.",
                    )
                except Exception:
                    pass
                return
            try:
                await bot.send_message(
                    referrer_id,
                    f"🎉 تبریک! با دعوت موفق دوستانتان، الگوی «{product['name']}» به‌صورت رایگان برای شما ارسال می‌شود:",
                )
            except Exception:
                pass
            try:
                # پاداشِ الگوی رایگان: سفارشی در کار نیست؛ order_id نمادین ۰
                await deliver_pattern_to_user(
                    bot,
                    referrer_id,
                    product["name"],
                    [f["file_id"] for f in files],
                    0,
                    0,
                )
            except Exception:
                pass

    # -----------------------------------------------------------------------
    # خرید الگو
    # -----------------------------------------------------------------------

    @router.message(F.text.func(lambda t: t == db.get_setting("btn_buy")))
    async def show_categories(message: Message, state: FSMContext):
        await state.clear()
        categories = (await asyncio.to_thread(db.get_categories, active_only=True))
        if not categories:
            await message.answer("در حال حاضر دسته‌بندی فعالی وجود ندارد.")
            return
        await message.answer("یک گزینه را انتخاب کنید:", reply_markup=kb.categories_kb(db, categories))

    @router.callback_query(F.data == "back_main")
    async def cb_back_main(call: CallbackQuery, state: FSMContext):
        await state.clear()
        try:
            await call.message.delete()
        except Exception:
            # پیام قدیمی‌تر از ۴۸ ساعت یا از قبل حذف‌شده باشد، تلگرام حذف را رد
            # می‌کند؛ در این حالت به‌جای کرش، فقط دکمه‌ها را از زیر پیام برمی‌داریم.
            try:
                await call.message.edit_reply_markup(reply_markup=None)
            except Exception:
                pass
        await call.answer()

    @router.callback_query(F.data == "back_categories")
    async def cb_back_categories(call: CallbackQuery):
        categories = (await asyncio.to_thread(db.get_categories, active_only=True))
        await call.message.edit_text("یک دسته‌بندی را انتخاب کنید:", reply_markup=kb.categories_kb(db, categories))
        await call.answer()

    @router.callback_query(F.data.startswith("cat:"))
    async def cb_category(call: CallbackQuery):
        cat_id = int(call.data.split(":")[1])
        products = (await asyncio.to_thread(db.get_products, cat_id, active_only=True))
        if not products:
            await call.answer("محصولی در این دسته‌بندی موجود نیست.", show_alert=True)
            return
        await call.message.edit_text("یک محصول را انتخاب کنید:", reply_markup=kb.products_kb(db, cat_id, products))
        await call.answer()

    def _product_confirm_text(product, has_files: bool, wallet_credit: int) -> str:
        availability_line = (
            "✅ این الگو آماده‌ی دانلود است.\n"
            if has_files else
            "⛔️ این الگو فعلاً موجود نیست.\n"
        )
        text = (
            f"🧵 {product['name']}\n"
            f"💰 قیمت: {product['price']:,} تومان\n"
            f"📝 توضیحات: {product['description'] or '---'}\n"
            f"{availability_line}"
        )
        if wallet_credit > 0:
            text += f"\n👛 موجودی کیف پول شما: {wallet_credit:,} تومان (به‌صورت خودکار در پرداخت اعمال می‌شود)\n"
        return text

    @router.callback_query(F.data.startswith("prod:"))
    async def cb_product(call: CallbackQuery):
        product_id = int(call.data.split(":")[1])
        product = (await asyncio.to_thread(db.get_product, product_id))
        if not product:
            await call.answer("محصول یافت نشد.", show_alert=True)
            return
        has_files = (await asyncio.to_thread(db.has_product_files, product_id))
        wallet_credit = (await asyncio.to_thread(db.get_wallet_credit, call.from_user.id))
        text = _product_confirm_text(product, has_files, wallet_credit)
        if not has_files:
            await call.message.edit_text(text)
            await call.answer()
            return
        await call.message.edit_text(text, reply_markup=kb.product_confirm_kb(product_id))
        await call.answer()

    @router.callback_query(F.data == "noop")
    async def cb_noop(call: CallbackQuery):
        await call.answer()

    @router.callback_query(F.data.startswith("enter_code:"))
    async def cb_enter_code(call: CallbackQuery, state: FSMContext):
        _, product_id, _qty = call.data.split(":")
        await state.update_data(discount_product_id=int(product_id))
        await state.set_state(DiscountEntry.waiting_code)
        await call.message.edit_text("🎟 کد تخفیف را ارسال کنید:", reply_markup=kb.cancel_kb())
        await call.answer()

    @router.message(DiscountEntry.waiting_code)
    async def process_discount_code(message: Message, state: FSMContext):
        data = await state.get_data()
        product_id = data.get("discount_product_id")
        product = (await asyncio.to_thread(db.get_product, product_id)) if product_id else None
        if not product:
            await message.answer("محصول معتبر نیست. لطفاً دوباره از منو شروع کنید.")
            await state.clear()
            return

        code_row = (await asyncio.to_thread(db.get_discount_code, message.text.strip()))
        if not (await asyncio.to_thread(db.is_discount_code_valid, code_row)):
            await message.answer(
                "❌ این کد تخفیف نامعتبر، غیرفعال یا به سقف استفاده رسیده است. دوباره تلاش کنید یا بدون کد ادامه دهید.",
                reply_markup=kb.cancel_kb(),
            )
            return

        total_price = product["price"]
        discount_amount = (await asyncio.to_thread(db.compute_discount_amount, code_row, total_price))
        await state.update_data(discount_code_id=code_row["id"], discount_amount=discount_amount)
        await state.set_state(None)

        wallet_credit = (await asyncio.to_thread(db.get_wallet_credit, message.from_user.id))
        price_after_code = total_price - discount_amount
        wallet_used_preview = min(wallet_credit, price_after_code)
        final_preview = price_after_code - wallet_used_preview

        text = (
            f"✅ کد تخفیف اعمال شد!\n\n"
            f"🧵 {product['name']}\n"
            f"💰 قیمت: {total_price:,} تومان\n"
            f"🎟 تخفیف کد: {discount_amount:,} تومان\n"
        )
        if wallet_used_preview > 0:
            text += f"👛 اعمال کیف پول: {wallet_used_preview:,} تومان\n"
        text += f"💵 مبلغ نهایی قابل پرداخت: {final_preview:,} تومان"

        await message.answer(text, reply_markup=kb.product_confirm_kb(product_id))

    async def _notify_admins_of_order(bot: Bot, order_id: int, receipt_file_id: str = None, receipt_type: str = "photo"):
        order = (await asyncio.to_thread(db.get_order, order_id))

        product = (await asyncio.to_thread(db.get_product, order["product_id"]))
        user_row = (await asyncio.to_thread(db.get_user, order["user_id"]))
        username = user_row["username"] if user_row else ""
        first_name = user_row["first_name"] if user_row else ""

        caption = (
            f"🧾 سفارش #{order_id}\n"
            f"👤 کاربر: {first_name or ''} (@{username or '---'})\n"
            f"🆔 آیدی عددی: {order['user_id']}\n"
            f"🧵 محصول: {product['name']}\n"
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
            caption += "\n\n✅ این سفارش به‌طور خودکار تایید و فایل‌های الگو برای کاربر ارسال شد (پرداخت کامل از کیف پول/کد تخفیف)."

        if not receipt_file_id and not already_approved:
            caption += "\n\n(بدون نیاز به رسید - مبلغ کاملاً از کیف پول/تخفیف پوشش داده شده)"

        for admin_id in (await asyncio.to_thread(db.list_admins)):
            if receipt_file_id:
                factory = lambda aid=admin_id: _send_receipt_to_admin(
                    bot, aid, receipt_file_id, receipt_type, caption, reply_markup
                )
            else:
                factory = lambda aid=admin_id: bot.send_message(
                    aid, caption, reply_markup=reply_markup,
                )
            sent = await _send_admin_notification(bot, admin_id, factory, "سفارش", order_id)
            if sent:
                (await asyncio.to_thread(db.set_order_admin_message, order_id, admin_id, sent.message_id))

    @router.callback_query(F.data.startswith("buy_start:"))
    async def cb_buy_start(call: CallbackQuery, state: FSMContext, bot: Bot):
        # فروش تک‌عددی است؛ عدد بعدی در callback_data (qty) عمداً نادیده گرفته می‌شود
        _, product_id, _qty = call.data.split(":")
        product_id = int(product_id)
        product = (await asyncio.to_thread(db.get_product, product_id))
        has_files = (await asyncio.to_thread(db.has_product_files, product_id))
        if not product or not has_files:
            await call.answer("این الگو در حال حاضر موجود نیست.", show_alert=True)
            return

        data = await state.get_data()
        discount_code_id = data.get("discount_code_id")
        discount_amount = data.get("discount_amount", 0) or 0

        total_price = product["price"]
        wallet_credit = (await asyncio.to_thread(db.get_wallet_credit, call.from_user.id))
        price_after_code = max(total_price - discount_amount, 0)
        wallet_used = min(wallet_credit, price_after_code)

        if wallet_used > 0:
            (await asyncio.to_thread(db.add_wallet_credit, call.from_user.id, -wallet_used))
        if discount_code_id:
            (await asyncio.to_thread(db.increment_discount_usage, discount_code_id))

        order_id = (await asyncio.to_thread(db.create_order, 
            call.from_user.id,
            product_id,
            base_price=total_price,
            wallet_used=wallet_used,
            discount_code_id=discount_code_id,
            discount_amount=discount_amount,
        ))
        order = (await asyncio.to_thread(db.get_order, order_id))
        await state.update_data(order_id=order_id)
        await state.update_data(discount_code_id=None, discount_amount=0, discount_product_id=None)

        if order["final_price"] <= 0:
            await state.clear()

            files = (await asyncio.to_thread(db.get_product_files, product_id))
            if not files:
                # الگو بدون فایل شده: سفارش را رد کن، مبلغ کسرشده از کیف پول/کد تخفیف را برگردان و به ادمین اطلاع بده
                (await asyncio.to_thread(db.reject_order, order_id))
                # برگشت امتیاز باشگاه مشتریان این سفارش (اگر قبلاً اعطا شده باشد؛ idempotent)
                try:
                    (await asyncio.to_thread(loyalty.reverse_purchase, db, order_id))
                except Exception:
                    logging.getLogger("handlers_user").exception(
                        "برگشت امتیاز سفارش #%s هنگام عدم موجودی ناموفق بود.", order_id
                    )
                await _notify_admins_of_order(bot, order_id)
                await call.message.edit_text(
                    "⛔️ این الگو در حال حاضر موجود نیست.\n"
                    "مبلغ کسرشده از کیف پول شما به‌طور کامل بازگردانده شد. لطفاً بعداً دوباره تلاش کنید "
                    "یا با پشتیبانی در تماس باشید."
                )
                await call.answer()
                return
            (await asyncio.to_thread(db.approve_order, order_id, [f["id"] for f in files]))
            # امتیاز باشگاه مشتریان بابت این خرید (idempotent؛ هر خطا نباید
            # روند تحویل سفارش را متوقف کند)
            try:
                awarded = (await asyncio.to_thread(loyalty.award_purchase, db, order_id))
            except Exception:
                logging.getLogger("handlers_user").exception(
                    "اعطای امتیاز باشگاه مشتریان برای سفارش #%s ناموفق بود.", order_id
                )
                awarded = 0
            reward_info = (await asyncio.to_thread(db.reward_referrer_if_first_purchase, call.from_user.id, order["base_price"]))
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

            success_text = (
                "✅ مبلغ سفارش شما به‌طور کامل از کیف پول/تخفیف پوشش داده شد.\n"
                "فایل الگوی شما در پیام بعدی ارسال می‌شود 👇"
            )
            if awarded > 0:
                success_text += f"\n🎁 {awarded} امتیاز باشگاه مشتریان به شما اضافه شد."
            await call.message.edit_text(success_text)
            await deliver_pattern_to_user(
                bot,
                call.from_user.id,
                product["name"],
                [f["file_id"] for f in files],
                0,
                order_id,
            )
            await call.answer()
            return

        await state.set_state(BuyFlow.waiting_receipt)

        card_number = (await asyncio.to_thread(db.get_setting, "card_number"))
        card_holder = (await asyncio.to_thread(db.get_setting, "card_holder"))
        after_buy_text = (await asyncio.to_thread(db.get_setting, "after_buy_text"))

        text = f"{after_buy_text}\n\n"
        text += f"💳 شماره کارت: `{card_number}`\n"
        text += f"👤 به نام: {card_holder}\n"
        if discount_amount:
            text += f"🎟 تخفیف کد: {discount_amount:,} تومان\n"
        if wallet_used:
            text += f"👛 استفاده از کیف پول: {wallet_used:,} تومان\n"
        text += f"💰 مبلغ نهایی قابل پرداخت: {order['final_price']:,} تومان\n\n"
        text += "لطفاً عکس رسید پرداخت را همینجا ارسال کنید."

        await call.message.edit_text(
            text, parse_mode="Markdown",
            reply_markup=kb.payment_choice_kb(),
        )
        await call.answer()

    @router.callback_query(F.data == "cancel_flow")
    async def cb_cancel_flow(call: CallbackQuery, state: FSMContext):
        data = await state.get_data()
        order_id = data.get("order_id")
        if order_id:
            order = (await asyncio.to_thread(db.get_order, order_id))
            if order and order["status"] == "pending":
                (await asyncio.to_thread(db.reject_order, order_id))
                # برگشت امتیاز باشگاه مشتریان سفارش لغوشده (اگر اعطا شده باشد؛ idempotent)
                try:
                    (await asyncio.to_thread(loyalty.reverse_purchase, db, order_id))
                except Exception:
                    logging.getLogger("handlers_user").exception(
                        "برگشت امتیاز سفارش لغوشده #%s ناموفق بود.", order_id
                    )
        await state.clear()
        await call.message.edit_text("عملیات لغو شد.")
        await call.answer()

    @router.message(BuyFlow.waiting_receipt, F.photo | F.document)
    async def receive_receipt(message: Message, state: FSMContext, bot: Bot):
        data = await state.get_data()
        order_id = data.get("order_id")
        order = (await asyncio.to_thread(db.get_order, order_id))
        if not order or order["status"] != "pending":
            await message.answer("سفارش معتبر یافت نشد. لطفاً دوباره از منو شروع کنید.")
            await state.clear()
            return

        file_id, receipt_type = _receipt_payload(message)
        if not file_id:
            await message.answer("لطفاً عکس یا فایل رسید پرداخت را ارسال کنید.")
            return
        (await asyncio.to_thread(db.set_order_receipt, order_id, file_id, receipt_type))

        await _notify_admins_of_order(
            bot, order_id, receipt_file_id=file_id, receipt_type=receipt_type
        )

        await message.answer(
            "✅ رسید شما برای بررسی ارسال شد. پس از تایید ادمین، فایل الگو برای شما ارسال خواهد شد.",
            reply_markup=kb.menu_for_user(db, message.from_user.id),
        )
        await _send_inline_main_menu(message, message.from_user.id)
        await state.clear()

    @router.message(BuyFlow.waiting_receipt)
    async def receipt_wrong_type(message: Message):
        await message.answer("لطفاً عکس یا فایل رسید پرداخت را ارسال کنید.")

    # -----------------------------------------------------------------------
    # الگوی نمونه‌ی رایگان
    # -----------------------------------------------------------------------

    @router.message(F.text.func(lambda t: t == db.get_setting("btn_test")))
    async def get_test_config(message: Message):
        if (await asyncio.to_thread(db.get_setting, "test_enabled", "1")) != "1":
            await message.answer("در حال حاضر امکان دریافت الگوی نمونه غیرفعال است.")
            return

        user = (await asyncio.to_thread(db.get_user, message.from_user.id))
        if user and user["test_used"] >= MAX_TEST_PER_USER:
            await message.answer("شما قبلاً الگوی نمونه‌ی رایگان خود را دریافت کرده‌اید. هر کاربر فقط یک بار مجاز به دریافت آن است.")
            return

        # الگوی نمونه مصرف نمی‌شود (ارسال نامحدود)؛ فقط دفعه‌ی استفاده‌ی هر کاربر ثبت می‌شود
        file = (await asyncio.to_thread(db.take_unused_sample_file))
        if not file:
            await message.answer("⛔️ فعلاً الگوی نمونه‌ای موجود نیست.")
            return

        (await asyncio.to_thread(db.mark_test_used, message.from_user.id))
        try:
            await message.answer_document(
                file["file_id"],
                caption="🧪 الگوی نمونه‌ی رایگان شما!\n\nاین الگو برای آشنایی با کیفیت کار ماست. برای دیدن همه‌ی الگوها، «🛒 خرید الگو» را بزنید.",
            )
        except Exception:
            await message.answer(
                "⚠️ در ارسال فایل الگوی نمونه خطایی رخ داد. لطفاً بعداً دوباره تلاش کنید یا با پشتیبانی تماس بگیرید."
            )

    # -----------------------------------------------------------------------
    # سفارش‌های من (دانلود مجدد فایل الگو + حذف سفارش از لیست)
    # -----------------------------------------------------------------------

    _MO_STATUS_MAP = {"pending": "⏳ در انتظار بررسی", "approved": "✅ تایید شده", "rejected": "❌ رد شده"}
    _MO_STATUS_ICON = {"pending": "⏳", "approved": "✅", "rejected": "❌"}

    def _my_orders_items(user_tg_id: int):
        """هر سفارش تاییدشده یا در انتظار بررسی، یک آیتم (یک دکمه) در منوست.
        سفارش‌های رد‌شده نمایش داده نمی‌شوند (فایلی برایشان تحویل نشده است)."""
        items = []
        for o in db.get_user_orders(user_tg_id):
            if o["status"] == "rejected":
                continue
            pname = o["product_name"] or "محصول حذف‌شده"
            label = f"{_MO_STATUS_ICON.get(o['status'], '')} #{o['id']} {pname}"
            items.append({"cb_id": str(o["id"]), "label": label, "order": o})
        return items

    async def _get_owned_order(user_tg_id: int, cb_id: str):
        """سفارش متعلق به کاربر را از روی cb_id برمی‌گرداند؛ در غیر این صورت None."""
        try:
            order_id = int(cb_id)
        except (TypeError, ValueError):
            return None
        order = (await asyncio.to_thread(db.get_order, order_id))
        if not order or order["user_id"] != user_tg_id:
            return None
        return order

    def _my_order_text(order) -> str:
        pname = order["product_name"] or "محصول حذف‌شده"
        return (
            f"🧵 سفارش #{order['id']} | {pname}\n"
            f"وضعیت: {_MO_STATUS_MAP.get(order['status'], order['status'])}\n"
            f"💰 مبلغ: {order['final_price']:,} تومان\n"
            f"📅 تاریخ: {order['created_at'] or '---'}"
        )

    async def _show_my_orders_list(target, user_tg_id: int, edit: bool):
        items = _my_orders_items(user_tg_id)
        if not items:
            text = "شما تاکنون سفارشی ثبت نکرده‌اید."
            if edit:
                await target.edit_text(text)
            else:
                await target.answer(text)
            return
        text = "🧵 الگوها و سفارش‌های من\n\nیکی از موارد زیر را برای مشاهده‌ی جزئیات انتخاب کنید:"
        markup = kb.my_orders_menu_kb(items)
        if edit:
            await target.edit_text(text, reply_markup=markup)
        else:
            await target.answer(text, reply_markup=markup)

    @router.message(F.text.func(lambda t: t == db.get_setting("btn_my_orders")))
    async def my_orders(message: Message):
        await _show_my_orders_list(message, message.from_user.id, edit=False)

    @router.callback_query(F.data == "mo_back")
    async def cb_my_orders_back(call: CallbackQuery):
        await _show_my_orders_list(call.message, call.from_user.id, edit=True)
        await call.answer()

    @router.callback_query(F.data.startswith("mo_v:"))
    async def cb_my_orders_view(call: CallbackQuery):
        cb_id = call.data.split(":", 1)[1]
        order = (await _get_owned_order(call.from_user.id, cb_id))
        if not order or order["status"] == "rejected" or order["user_deleted"]:
            await call.answer("این مورد یافت نشد (شاید قبلاً حذف شده).", show_alert=True)
            await _show_my_orders_list(call.message, call.from_user.id, edit=True)
            return
        await call.answer()
        await call.message.edit_text(_my_order_text(order), reply_markup=kb.my_order_item_kb(cb_id, True))

    @router.callback_query(F.data.startswith("mo_resend:"))
    async def cb_my_orders_resend(call: CallbackQuery, bot: Bot):
        cb_id = call.data.split(":", 1)[1]
        order = (await _get_owned_order(call.from_user.id, cb_id))
        if not order:
            await call.answer("این سفارش یافت نشد (شاید قبلاً حذف شده).", show_alert=True)
            return
        if order["status"] != "approved" or not order["file_ids"]:
            await call.answer("برای این سفارش فایلی ثبت نشده است.", show_alert=True)
            return
        await call.answer("در حال ارسال فایل‌ها...")

        # سفارش، شناسه‌ی رکوردهای فایل (product_files.id) را به‌صورت CSV نگه می‌دارد؛
        # اینجا هر رکورد به file_id تلگرامی فعلی‌اش نگاشت می‌شود. اگر ادمین بعداً
        # یکی از فایل‌های محصول را حذف کرده باشد، همان فایل با پیام هشدار جا می‌ماند.
        files = (await asyncio.to_thread(db.get_product_files, order["product_id"]))
        file_map = {f["id"]: f["file_id"] for f in files}
        record_ids = []
        for raw in str(order["file_ids"]).split(","):
            raw = raw.strip()
            if not raw:
                continue
            try:
                record_ids.append(int(raw))
            except ValueError:
                continue

        product = (await asyncio.to_thread(db.get_product, order["product_id"]))
        pname = product["name"] if product else "محصول حذف‌شده"

        missing = 0
        for rec_id in record_ids:
            file_id = file_map.get(rec_id)
            if not file_id:
                missing += 1
                continue
            try:
                await bot.send_document(
                    call.from_user.id,
                    file_id,
                    caption=(
                        f"📥 دانلود مجدد فایل سفارش #{order['id']}\n"
                        f"🧵 محصول: {pname}"
                    ),
                )
            except Exception:
                logging.getLogger("handlers_user").exception(
                    "ارسال مجدد فایل سفارش #%s به کاربر %s ناموفق بود.", order["id"], call.from_user.id
                )
                missing += 1
        if missing:
            try:
                await bot.send_message(
                    call.from_user.id,
                    "⚠️ یکی از فایل‌ها دیگر در دسترس نیست — با پشتیبانی تماس بگیرید.",
                )
            except Exception:
                pass

    @router.callback_query(F.data.startswith("mo_del:"))
    async def cb_my_orders_delete_ask(call: CallbackQuery):
        cb_id = call.data.split(":", 1)[1]
        order = (await _get_owned_order(call.from_user.id, cb_id))
        if not order or order["user_deleted"]:
            await call.answer("این مورد یافت نشد (شاید قبلاً حذف شده).", show_alert=True)
            await _show_my_orders_list(call.message, call.from_user.id, edit=True)
            return
        await call.answer()
        await call.message.edit_text(
            "⚠️ آیا مطمئن هستید؟\n\n"
            "این سفارش فقط از لیست «سفارش‌های من» شما حذف می‌شود و دیگر از این بخش "
            "نمی‌توانید فایل آن را دریافت کنید.\n"
            "این عملیات **غیرقابل بازگشت** است.",
            parse_mode="Markdown",
            reply_markup=kb.my_order_delete_confirm_kb(cb_id),
        )

    @router.callback_query(F.data.startswith("mo_delok:"))
    async def cb_my_orders_delete_confirm(call: CallbackQuery):
        cb_id = call.data.split(":", 1)[1]
        user_tg_id = call.from_user.id
        try:
            order_id = int(cb_id)
        except ValueError:
            await call.answer("درخواست نامعتبر.", show_alert=True)
            await _show_my_orders_list(call.message, user_tg_id, edit=True)
            return

        removed = (await asyncio.to_thread(db.delete_owned_order, order_id, user_tg_id))
        if not removed:
            await call.answer("این سفارش یافت نشد (شاید قبلاً حذف شده).", show_alert=True)
        else:
            await call.answer("✅ سفارش از لیست شما حذف شد.", show_alert=True)

        await _show_my_orders_list(call.message, user_tg_id, edit=True)

    # -----------------------------------------------------------------------
    # زیرمجموعه‌گیری (رفرال)
    # -----------------------------------------------------------------------

    @router.message(F.text.func(lambda t: t == db.get_setting("btn_referral")))
    async def referral_menu(message: Message, bot: Bot):
        settings = (await asyncio.to_thread(db.get_all_settings))
        if settings.get("referral_button_enabled", "1") != "1":
            await message.answer("در حال حاضر سیستم زیرمجموعه‌گیری غیرفعال است.")
            return
        commission_on = settings.get("referral_enabled", "1") == "1"
        freeconfig_on = settings.get("referral_free_config_enabled", "0") == "1"
        invitebonus_on = settings.get("referral_invite_bonus_enabled", "0") == "1"

        if not (commission_on or freeconfig_on or invitebonus_on):
            await message.answer("در حال حاضر سیستم زیرمجموعه‌گیری غیرفعال است.")
            return

        me = await bot.get_me()
        link = f"https://t.me/{me.username}?start=ref{message.from_user.id}"
        stats = (await asyncio.to_thread(db.get_referral_stats, message.from_user.id))

        lines = ["🤝 سیستم زیرمجموعه‌گیری", "", f"لینک اختصاصی دعوت شما:\n{link}", ""]
        if commission_on:
            percent = settings.get("referral_percent", "10")
            max_count = int(settings.get("referral_commission_max_count", "0") or 0)
            cap_text = f" (فقط برای {max_count} نفر اول از زیرمجموعه‌هایی که خرید می‌کنند)" if max_count > 0 else ""
            lines.append(
                f"💳 هر کاربری که با این لینک وارد بات شود و اولین خریدش تایید شود، {percent}٪ از مبلغ "
                f"پرداختی او به‌صورت اعتبار کیف پول به شما تعلق می‌گیرد{cap_text}."
            )
        if freeconfig_on:
            threshold = settings.get("referral_free_config_threshold", "10")
            lines.append(f"🎁 با دعوت {threshold} نفر (حتی بدون خرید آن‌ها)، یک الگوی رایگان دریافت می‌کنید.")
        if invitebonus_on:
            amount = settings.get("referral_invite_bonus_amount", "0")
            ib_max = int(settings.get("referral_invite_bonus_max_count", "0") or 0)
            cap_text = f" (فقط برای {ib_max} دعوت اول)" if ib_max > 0 else ""
            lines.append(f"💰 با دعوت هر نفر (حتی بدون خرید)، {int(amount):,} تومان به کیف پول شما اضافه می‌شود{cap_text}.")

        lines.append("")
        lines.append(f"👥 تعداد زیرمجموعه‌های شما: {stats['count']}")
        lines.append(f"👛 موجودی کیف پول شما: {stats['credit']:,} تومان")

        await message.answer("\n".join(lines))

    # -----------------------------------------------------------------------
    # کیف پول (جدا از زیرمجموعه‌گیری)
    # -----------------------------------------------------------------------

    @router.message(F.text.func(lambda t: t == db.get_setting("btn_wallet")))
    async def wallet_menu(message: Message):
        balance = (await asyncio.to_thread(db.get_wallet_credit, message.from_user.id))
        text = (
            "👛 کیف پول شما\n\n"
            f"موجودی فعلی: {balance:,} تومان\n\n"
            "این موجودی (چه از شارژ دستی، چه از پورسانت زیرمجموعه‌گیری) به‌صورت خودکار در خرید بعدی شما کسر می‌شود."
        )
        await message.answer(text, reply_markup=kb.wallet_menu_kb())

    # -----------------------------------------------------------------------
    # باشگاه مشتریان (Loyalty)
    # -----------------------------------------------------------------------

    _LOYALTY_TX_ICONS = {
        loyalty.TX_PURCHASE: "🛍",
        loyalty.TX_PURCHASE_REFUND: "↩️",
        loyalty.TX_REGISTRATION: "🎁",
        loyalty.TX_REFERRAL: "🤝",
        loyalty.TX_CAMPAIGN: "🎯",
        loyalty.TX_TIER_BONUS: "🏆",
        loyalty.TX_ADMIN_ADJUSTMENT: "🛠",
        loyalty.TX_POINTS_REDEEM: "🔄",
        loyalty.TX_POINTS_EXPIRE: "⌛️",
        loyalty.TX_REVERSAL: "🧾",
    }

    def _loyalty_menu_text(s: dict) -> str:
        lines = [
            "🎁 <b>باشگاه مشتریان</b>",
            "",
            f"⭐ امتیاز فعلی: {s['current']}",
            f"🏆 سطح: {s['tier']['name'] if s['tier'] else '—'}",
        ]
        if s["next_tier"]:
            lines.append(f"📈 امتیاز تا سطح بعد: {s['points_to_next']} ({s['next_tier']['name']})")
        else:
            lines.append("🎉 در بالاترین سطح هستید!")
        lines.append("")
        lines.append(f"هر {s['redeem_points']} امتیاز = {s['redeem_toman']:,} تومان اعتبار کیف پول")
        return "\n".join(lines)

    async def _edit_or_resend(target, text: str, reply_markup=None):
        """ویرایش امن پیام موجود (safe_edit)؛ اگر ویرایش ممکن نباشد (پیام قدیمی
        یا حذف‌شده)، همان متن به‌صورت پیام جدید ارسال می‌شود. خطای بی‌خطر
        «message is not modified» (کلیک دوباره روی همان صفحه) نادیده گرفته می‌شود."""
        try:
            await target.edit_text(text, reply_markup=reply_markup)
        except TelegramBadRequest as e:
            if "not modified" in str(e).lower():
                return
            await target.answer(text, reply_markup=reply_markup)

    @router.message(F.text.func(lambda t: t == db.get_setting("btn_loyalty")))
    async def loyalty_menu(message: Message):
        (await asyncio.to_thread(db.add_or_update_user,
            message.from_user.id, message.from_user.username or "", message.from_user.first_name or ""
        ))
        if not (await asyncio.to_thread(loyalty.is_enabled, db)):
            await message.answer("باشگاه مشتریان در حال حاضر غیرفعال است.")
            return
        s = (await asyncio.to_thread(loyalty.get_summary, db, message.from_user.id))
        await message.answer(_loyalty_menu_text(s), reply_markup=kb.loyalty_menu_kb())

    @router.callback_query(F.data.startswith("loy_hist:"))
    async def cb_loyalty_history(call: CallbackQuery, state: FSMContext):
        await state.clear()
        try:
            page = max(int(call.data.split(":", 1)[1]), 0)
        except (TypeError, ValueError):
            page = 0

        per_page = 5
        rows, total = (await asyncio.to_thread(
            db.get_loyalty_history, call.from_user.id, per_page, page * per_page
        ))
        state_row = (await asyncio.to_thread(db.ensure_loyalty_state, call.from_user.id))
        pages = max(1, -(-total // per_page))

        lines = [
            f"📜 تاریخچه امتیاز (صفحه {page + 1} از {pages})",
            f"⭐ موجودی: {state_row['current_points']}",
            "",
        ]
        if not rows:
            lines.append("هنوز تراکنشی برای شما ثبت نشده است.")
        for row in rows:
            amount = row["amount"]
            if amount >= 0:
                amount_line = f"⭐ <b>+{amount}</b>"
            else:
                amount_line = f"⭐ −{abs(amount)}"
            icon = _LOYALTY_TX_ICONS.get(row["tx_type"], "⭐")
            label = loyalty.TX_LABELS_FA.get(row["tx_type"], row["tx_type"])
            desc = html.escape((row["description"] or "").strip())
            tx_line = f"{icon} {label}" + (f" — {desc}" if desc else "")
            try:
                date_str = to_jalali_str(row["created_at"])
            except Exception:
                date_str = "-"
            lines.append(f"{amount_line}\n{tx_line}\n📅 {date_str} — موجودی: {row['balance_after']}")

        has_prev = page > 0
        has_next = (page + 1) * per_page < total
        await _edit_or_resend(
            call.message, "\n".join(lines), kb.loyalty_history_kb(page, has_prev, has_next)
        )
        await call.answer()

    @router.callback_query(F.data == "loy_back")
    async def cb_loyalty_back(call: CallbackQuery, state: FSMContext):
        await state.clear()
        if not (await asyncio.to_thread(loyalty.is_enabled, db)):
            await call.answer("باشگاه مشتریان در حال حاضر غیرفعال است.", show_alert=True)
            return
        s = (await asyncio.to_thread(loyalty.get_summary, db, call.from_user.id))
        await _edit_or_resend(call.message, _loyalty_menu_text(s), kb.loyalty_menu_kb())
        await call.answer()

    @router.callback_query(F.data == "loy_rules")
    async def cb_loyalty_rules(call: CallbackQuery, state: FSMContext):
        await state.clear()
        if not (await asyncio.to_thread(loyalty.is_enabled, db)):
            await call.answer("باشگاه مشتریان در حال حاضر غیرفعال است.", show_alert=True)
            return

        settings = (await asyncio.to_thread(db.get_all_settings))

        def _int_setting(key: str, default: str) -> int:
            try:
                return int(settings.get(key, default) or 0)
            except (TypeError, ValueError):
                return 0

        points_per_toman = _int_setting("loyalty_points_per_toman", "10000")
        redeem_points = _int_setting("loyalty_redeem_points", "100")
        redeem_toman = _int_setting("loyalty_redeem_toman", "0")
        min_redeem = _int_setting("loyalty_min_redeem", "0")
        tiers = (await asyncio.to_thread(loyalty.load_tiers, db))

        lines = ["❓ قوانین باشگاه مشتریان", ""]
        if points_per_toman > 0:
            lines.append(f"⭐ هر {points_per_toman:,} تومان خرید = ۱ امتیاز")
        else:
            lines.append("⭐ امتیازدهی خرید در حال حاضر فعال نیست.")
        if tiers:
            lines.append("")
            lines.append("سطوح باشگاه (بر اساس کل امتیازهای کسب‌شده):")
            for t in tiers:
                lines.append(f"• {t['name']} — از {t['min']:,} امتیاز (ضریب {t['mult'] / 100:g}×)")
        lines.append("")
        if redeem_points > 0 and redeem_toman > 0:
            lines.append(f"🔄 هر {redeem_points} امتیاز = {redeem_toman:,} تومان اعتبار کیف پول")
        else:
            lines.append("🔄 تبدیل امتیاز به کیف پول در حال حاضر فعال نیست.")
        if min_redeem > 0:
            lines.append(f"حداقل امتیاز قابل تبدیل در هر درخواست: {min_redeem}")
        lines.append("")
        lines.append("امتیازها پس از تایید سفارش اعطا می‌شوند.")

        await _edit_or_resend(call.message, "\n".join(lines), kb.loyalty_rules_kb())
        await call.answer()

    @router.callback_query(F.data == "loy_redeem")
    async def cb_loyalty_redeem(call: CallbackQuery, state: FSMContext):
        s = (await asyncio.to_thread(loyalty.get_summary, db, call.from_user.id))
        if not s["redeem_enabled"]:
            await call.answer("تبدیل امتیاز در حال حاضر فعال نیست.", show_alert=True)
            return
        await state.set_state(LoyaltyRedeem.waiting_points)
        prompt = f"🔄 چند امتیاز می‌خواهید تبدیل کنید؟ (مضرب {s['redeem_points']} — حداقل {s['min_redeem']})"
        try:
            await call.message.edit_text(prompt)
        except TelegramBadRequest as e:
            if "not modified" not in str(e).lower():
                await call.message.answer(prompt)
        await call.answer()

    @router.message(LoyaltyRedeem.waiting_points)
    async def process_loyalty_redeem_points(message: Message, state: FSMContext):
        raw = (message.text or "").strip().replace(",", "")
        if not raw.isdigit() or int(raw) <= 0:
            await message.answer("لطفاً تعداد امتیاز را به‌صورت عدد ارسال کنید (مثال: 200).")
            return
        points = int(raw)

        s = (await asyncio.to_thread(loyalty.get_summary, db, message.from_user.id))
        if not s["redeem_enabled"]:
            await state.clear()
            await message.answer("تبدیل امتیاز در حال حاضر فعال نیست.")
            return
        redeem_points = s["redeem_points"]
        # پیش‌نمایش: همان اعتبارسنجی‌هایی که loyalty.redeem در لحظه‌ی تایید انجام می‌دهد
        if s["min_redeem"] > 0 and points < s["min_redeem"]:
            await message.answer(f"❌ حداقل امتیاز قابل تبدیل {s['min_redeem']} امتیاز است.")
            return
        if points % redeem_points != 0:
            await message.answer(f"❌ تعداد امتیاز باید مضربی از {redeem_points} باشد.")
            return
        if points > s["current"]:
            await message.answer("موجودی امتیاز شما کافی نیست.")
            return
        toman = (points // redeem_points) * s["redeem_toman"]

        await message.answer(
            f"🔄 تبدیل {points} امتیاز → {toman:,} تومان اعتبار کیف پول",
            reply_markup=kb.loyalty_redeem_confirm_kb(points),
        )

    @router.callback_query(F.data.startswith("loy_redeem_ok:"))
    async def cb_loyalty_redeem_ok(call: CallbackQuery, state: FSMContext):
        try:
            points = int(call.data.split(":", 1)[1])
        except (TypeError, ValueError):
            await state.clear()
            await call.answer("درخواست نامعتبر است.", show_alert=True)
            return
        try:
            result = (await asyncio.to_thread(loyalty.redeem, db, call.from_user.id, points))
        except LoyaltyError as e:
            await call.answer(str(e), show_alert=True)
            return
        except Exception:
            logging.getLogger("handlers_user").exception(
                "تبدیل امتیاز به کیف پول برای کاربر %s ناموفق بود.", call.from_user.id
            )
            await call.answer("⚠️ خطایی رخ داد. لطفاً دوباره تلاش کنید.", show_alert=True)
            return
        await state.clear()
        text = (
            f"✅ {result['points']} امتیاز تبدیل و {result['toman']:,} تومان به کیف پول شما اضافه شد.\n"
            f"⭐ موجودی امتیاز: {result['balance_after']}"
        )
        await _edit_or_resend(call.message, text, kb.loyalty_menu_kb())
        await call.answer()

    # -----------------------------------------------------------------------
    # گردونه شانس
    # -----------------------------------------------------------------------

    @router.message(F.text.func(lambda t: t == db.get_setting("btn_wheel")))
    async def wheel_of_fortune(message: Message, bot: Bot):
        if (await asyncio.to_thread(db.get_setting, "wheel_enabled", "1")) != "1":
            await message.answer("در حال حاضر گردونه شانس غیرفعال است.")
            return

        can_spin, remaining_hours = (await asyncio.to_thread(db.can_spin_wheel, message.from_user.id))
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

        (await asyncio.to_thread(db.record_wheel_spin, message.from_user.id))

        settings = (await asyncio.to_thread(db.get_wheel_settings))
        won = random.randint(1, 100) <= settings["win_percent"]

        if won and settings["prizes"]:
            percent = random.choice(settings["prizes"])
            code, expires_at = (await asyncio.to_thread(db.generate_wheel_prize_code, message.from_user.id, percent))
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

        card_number = (await asyncio.to_thread(db.get_setting, "card_number"))
        card_holder = (await asyncio.to_thread(db.get_setting, "card_holder"))

        text = (
            f"مبلغ {amount:,} تومان را به شماره کارت زیر واریز کرده و سپس عکس رسید را ارسال کنید:\n\n"
            f"💳 شماره کارت: `{card_number}`\n"
            f"👤 به نام: {card_holder}\n"
        )
        await message.answer(
            text, parse_mode="Markdown",
            reply_markup=kb.payment_choice_kb(),
        )

    @router.message(WalletTopup.waiting_receipt, F.photo | F.document)
    async def receive_topup_receipt(message: Message, state: FSMContext, bot: Bot):
        data = await state.get_data()
        amount = data.get("topup_amount")
        if not amount:
            await message.answer("درخواست معتبر یافت نشد. لطفاً دوباره از منو شروع کنید.")
            await state.clear()
            return

        file_id, receipt_type = _receipt_payload(message)
        if not file_id:
            await message.answer("لطفاً عکس یا فایل رسید پرداخت را ارسال کنید.")
            return
        topup_id = (await asyncio.to_thread(db.create_topup, message.from_user.id, amount))
        (await asyncio.to_thread(db.set_topup_receipt, topup_id, file_id, receipt_type))

        user_row = (await asyncio.to_thread(db.get_user, message.from_user.id))
        caption = (
            f"👛 درخواست شارژ کیف پول #{topup_id}\n"
            f"👤 کاربر: {user_row['first_name'] or ''} (@{user_row['username'] or '---'})\n"
            f"🆔 آیدی عددی: {message.from_user.id}\n"
            f"💰 مبلغ: {amount:,} تومان"
        )
        for admin_id in (await asyncio.to_thread(db.list_admins)):
            factory = lambda aid=admin_id: _send_receipt_to_admin(
                bot, aid, file_id, receipt_type, caption, kb.topup_review_kb(topup_id)
            )
            sent = await _send_admin_notification(bot, admin_id, factory, "شارژ کیف پول", topup_id)
            if sent:
                (await asyncio.to_thread(db.set_topup_admin_message, topup_id, admin_id, sent.message_id))

        await message.answer(
            "✅ درخواست شارژ کیف پول شما برای بررسی ارسال شد. پس از تایید ادمین، مبلغ به کیف پول شما اضافه می‌شود.",
            reply_markup=kb.menu_for_user(db, message.from_user.id),
        )
        await _send_inline_main_menu(message, message.from_user.id)
        await state.clear()

    @router.message(WalletTopup.waiting_receipt)
    async def topup_receipt_wrong_type(message: Message):
        await message.answer("لطفاً عکس یا فایل رسید پرداخت را ارسال کنید.")

    @router.message(F.photo | F.document)
    async def receipt_fallback_catch(message: Message, state: FSMContext, bot: Bot):
        # کاربر عکس/فایل رسید می‌فرستد اما state ندارد. این حالت معمولاً وقتی
        # پیش می‌آید که بین ارسال رسید و رسیدن پیام، پروسه‌ی بات ری‌استارت شده
        # و FSM state از دست رفته است. بدون این بخش، رسید کاملاً بی‌سروصدا
        # نادیده گرفته می‌شد: نه در دیتابیس ذخیره می‌شد، نه به ادمین می‌رسید،
        # نه کاربر می‌فهمید. اینجا با پیدا کردن آخرین سفارش pending این کاربر
        # که هنوز رسید ندارد، رسید را به همان سفارش می‌چسبانیم - دقیقاً همان
        # مسیر عادی receive_receipt.
        current_state = await state.get_state()
        if current_state:
            return  # یک state دیگر (سفارش/شارژ/...) در حال پردازش این عکس است

        log = logging.getLogger("handlers_user")

        file_id, receipt_type = _receipt_payload(message)
        if not file_id:
            return

        try:
            order = (await asyncio.to_thread(db.get_latest_pending_order_awaiting_receipt, message.from_user.id))
        except Exception:
            log.exception("خطا در جست‌وجوی سفارش pending برای fallback رسید کاربر %s", message.from_user.id)
            order = None

        if order:
            try:
                (await asyncio.to_thread(db.set_order_receipt, order["id"], file_id, receipt_type))
                await _notify_admins_of_order(
                    bot, order["id"], receipt_file_id=file_id, receipt_type=receipt_type
                )
            except Exception:
                log.exception(
                    "پردازش fallback رسید سفارش #%s کاربر %s ناموفق بود.",
                    order["id"], message.from_user.id,
                )
                await message.answer(
                    "⚠️ در ثبت رسید شما خطایی رخ داد. لطفاً دوباره تلاش کنید یا با پشتیبانی تماس بگیرید."
                )
                return
            log.warning(
                "رسید سفارش #%s کاربر %s با fallback (بدون FSM state) پردازش شد.",
                order["id"], message.from_user.id,
            )
            await message.answer(
                "✅ رسید شما برای بررسی ارسال شد. پس از تایید ادمین، فایل الگو برای شما ارسال خواهد شد.",
                reply_markup=kb.menu_for_user(db, message.from_user.id),
            )
            await _send_inline_main_menu(message, message.from_user.id)
            return

        # هیچ سفارش/درخواست pending‌ای برای این کاربر پیدا نشد. برای شارژ کیف‌پول
        # نمی‌توان بازیابی کرد چون مبلغ فقط داخل state نگه داشته می‌شود، نه دیتابیس؛
        # پس حداقل کاربر را از سکوت کامل نجات می‌دهیم و راهنمایی می‌کنیم.
        try:
            topup = (await asyncio.to_thread(db.get_latest_pending_topup_awaiting_receipt, message.from_user.id))
        except Exception:
            log.exception("خطا در جست‌وجوی شارژ کیف‌پول pending برای fallback رسید کاربر %s", message.from_user.id)
            topup = None

        if topup:
            try:
                (await asyncio.to_thread(db.set_topup_receipt, topup["id"], file_id, receipt_type))
                user_row = (await asyncio.to_thread(db.get_user, message.from_user.id))
                caption = (
                    f"👛 درخواست شارژ کیف پول #{topup['id']}\n"
                    f"👤 کاربر: {user_row['first_name'] or ''} (@{user_row['username'] or '---'})\n"
                    f"🆔 آیدی عددی: {message.from_user.id}\n"
                    f"💰 مبلغ: {topup['amount']:,} تومان"
                )
                for admin_id in (await asyncio.to_thread(db.list_admins)):
                    factory = lambda aid=admin_id: _send_receipt_to_admin(
                        bot, aid, file_id, receipt_type, caption, kb.topup_review_kb(topup["id"])
                    )
                    sent = await _send_admin_notification(bot, admin_id, factory, "شارژ کیف پول", topup["id"])
                    if sent:
                        (await asyncio.to_thread(db.set_topup_admin_message, topup["id"], admin_id, sent.message_id))
            except Exception:
                log.exception(
                    "پردازش fallback رسید شارژ کیف‌پول #%s کاربر %s ناموفق بود.",
                    topup["id"], message.from_user.id,
                )
                await message.answer(
                    "⚠️ در ثبت رسید شما خطایی رخ داد. لطفاً دوباره تلاش کنید یا با پشتیبانی تماس بگیرید."
                )
                return
            log.warning(
                "رسید شارژ کیف‌پول #%s کاربر %s با fallback (بدون FSM state) پردازش شد.",
                topup["id"], message.from_user.id,
            )
            await message.answer(
                "✅ درخواست شارژ کیف پول شما برای بررسی ارسال شد. پس از تایید ادمین، مبلغ به کیف پول شما اضافه می‌شود.",
                reply_markup=kb.menu_for_user(db, message.from_user.id),
            )
            await _send_inline_main_menu(message, message.from_user.id)
            return

        log.warning(
            "عکس/فایل بدون state و بدون هیچ سفارش/درخواست pending‌ای از کاربر %s دریافت شد.",
            message.from_user.id,
        )
        await message.answer(
            "❌ رسید شما ثبت نشد.\n"
            "دلیل: هیچ سفارش یا درخواست شارژ در انتظار رسیدی برای شما پیدا نشد "
            "(احتمالاً ارتباط قطع شده بود یا قبلاً بررسی شده است).\n\n"
            "لطفاً دوباره از منوی اصلی همان مسیر خرید یا شارژ کیف پول را طی کنید و رسید را مجدداً ارسال کنید.",
            reply_markup=kb.menu_for_user(db, message.from_user.id),
        )
        await _send_inline_main_menu(message, message.from_user.id)

    # -----------------------------------------------------------------------
    # ارتباط با پشتیبانی
    # -----------------------------------------------------------------------

    @router.message(F.text.func(lambda t: t == db.get_setting("btn_contact")))
    async def contact_start(message: Message, state: FSMContext):
        await state.set_state(ContactFlow.waiting_message)
        await message.answer((await asyncio.to_thread(db.get_setting, "contact_text")), reply_markup=kb.cancel_kb())

    @router.message(ContactFlow.waiting_message)
    async def contact_receive(message: Message, state: FSMContext, bot: Bot):
        user = message.from_user
        if message.text:
            (await asyncio.to_thread(db.add_support_message, user.id, "user", message.text))
        text = (
            f"📩 پیام جدید از کاربر\n"
            f"👤 {user.first_name or ''} (@{user.username or '---'})\n"
            f"🆔 {user.id}\n\n"
            f"✉️ {message.text or '(بدون متن / رسانه)'}"
        )
        # فقط به اولین ادمین/مالک آنلاین اطلاع بده تا مکالمه به او اختصاص یابد؛
        # اگر هیچ‌کس آنلاین نبود، طبق روال قدیم به همه‌ی ادمین‌ها اطلاع بده.
        target_admin = (await asyncio.to_thread(db.resolve_support_admin_for_message, user.id))
        admin_ids = [target_admin] if target_admin else (await asyncio.to_thread(db.list_admins))
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
        await _send_inline_main_menu(message, user.id)
        await state.clear()

    # -----------------------------------------------------------------------
    # پل بین منوی شیشه‌ای بالا (Inline) و همان هندلرهای منوی پایین (Reply)
    # چون هر دکمه‌ی پایین از قبل یک هندلر مستقل دارد، به‌جای تکرار منطق هرکدام،
    # کلیک روی دکمه‌ی شیشه‌ای معادل، مستقیماً همان تابع را با کاربرِ واقعیِ
    # کلیک‌کننده (call.from_user) صدا می‌زند تا رفتار دقیقاً یکسان بماند.
    # فقط کلیدهایی که در kb._menu_items ساخته می‌شوند اینجا dispatch می‌شوند.
    # -----------------------------------------------------------------------

    @router.callback_query(F.data.startswith("mm:"))
    async def cb_main_menu_inline(call: CallbackQuery, state: FSMContext, bot: Bot):
        await call.answer()
        key = call.data.split(":", 1)[1]
        # پیام جعلی: همان پیام بات ولی از_user واقعیِ کلیک‌کننده، تا هندلرهای
        # زیر که message.from_user.id می‌خوانند درست کار کنند
        fake_message = call.message.model_copy(update={"from_user": call.from_user})

        if key == "btn_buy":
            await show_categories(fake_message, state)
        elif key == "btn_test":
            await get_test_config(fake_message)
        elif key == "btn_my_orders":
            await my_orders(fake_message)
        elif key == "btn_wallet":
            await wallet_menu(fake_message)
        elif key == "btn_referral":
            await referral_menu(fake_message, bot)
        elif key == "btn_wheel":
            await wheel_of_fortune(fake_message, bot)
        elif key == "btn_loyalty":
            await loyalty_menu(fake_message)
        elif key == "btn_contact":
            await contact_start(fake_message, state)
        # کلید دکمه‌ی مدیریت (پنل ادمین) اینجا هندل نمی‌شود؛ هندلر اصلی‌اش در
        # handlers_admin.py تعریف شده است.

    # هر متن ناشناخته‌ای منوی اصلی را دوباره نمایش می‌دهد. کاربرد اصلی: بعد از
    # «Clear History» تلگرام، هم کیبورد پاسخ‌گو حذف می‌شود هم دکمه‌ی Start
    # دیگر ظاهر نمی‌شود (رفتار خود تلگرام) — با فرستادن هر متنی (یا همان
    # دکمه‌های قبلی) منو دوباره برمی‌گردد و کاربر گم نمی‌شود.
    @router.message(StateFilter(None), F.text, ~F.text.startswith("/"))
    async def unknown_text_shows_menu(message: Message, state: FSMContext, bot: Bot):
        (await asyncio.to_thread(db.add_or_update_user,
            message.from_user.id, message.from_user.username or "", message.from_user.first_name or ""
        ))
        welcome = (await asyncio.to_thread(db.get_setting, "welcome_text"))
        await message.answer(welcome, reply_markup=kb.menu_for_user(db, message.from_user.id))
        await _send_inline_main_menu(message, message.from_user.id)

    return router
