# -*- coding: utf-8 -*-
"""
هندلرهای پنل مدیریت

این فایل هم مثل handlers_user.py یک تابع کارخانه‌ای دارد: create_admin_router(db, ...).
هر بات (اصلی یا نمایندگی) پنل مدیریت کامل و مستقل خودش را از همین یک کد می‌سازد.
"""

import os
import asyncio

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command

import keyboards as kb
from database import Database
from config import RESELLER_DBS_DIR
from config_delivery import deliver_config_to_user
from states import (
    AdminAddCategory,
    AdminAddProduct,
    AdminAddConfigs,
    AdminAddTestConfigs,
    AdminEditButton,
    AdminSetCard,
    AdminBroadcast,
    AdminAddAdmin,
    AdminRemoveAdmin,
    AdminEditWelcome,
    AdminReplyFlow,
    AdminCreateDiscount,
    AdminReferralPercent,
    AdminAddResellerBot,
    AdminWheelSettings,
    AdminRenewalSettings,
)


def create_admin_router(db, is_main_bot: bool = True, bot_manager=None) -> Router:
    router = Router()

    def admin_only(user_id: int) -> bool:
        return db.is_admin(user_id)

    # -------------------------------------------------------------------
    # ورود به پنل
    # -------------------------------------------------------------------

    @router.message(F.text.func(lambda t: t == db.get_setting("btn_admin_panel")))
    async def open_admin_panel(message: Message, state: FSMContext):
        if not admin_only(message.from_user.id):
            return
        await state.clear()
        await message.answer("🔧 پنل مدیریت:", reply_markup=kb.admin_panel_kb(db, is_main_bot))

    @router.callback_query(F.data == "adm_back_panel")
    async def cb_back_panel(call: CallbackQuery, state: FSMContext):
        if not admin_only(call.from_user.id):
            return await call.answer()
        await state.clear()
        await call.message.edit_text("🔧 پنل مدیریت:", reply_markup=kb.admin_panel_kb(db, is_main_bot))
        await call.answer()

    @router.callback_query(F.data == "noop")
    async def cb_noop(call: CallbackQuery):
        await call.answer()

    # -------------------------------------------------------------------
    # مدیریت دسته‌بندی‌ها
    # -------------------------------------------------------------------

    @router.callback_query(F.data == "adm_categories")
    async def cb_admin_categories(call: CallbackQuery):
        if not admin_only(call.from_user.id):
            return await call.answer()
        categories = db.get_categories(active_only=False)
        await call.message.edit_text("📂 مدیریت دسته‌بندی‌ها:", reply_markup=kb.admin_categories_kb(categories))
        await call.answer()

    @router.callback_query(F.data.startswith("adm_cat_toggle:"))
    async def cb_admin_cat_toggle(call: CallbackQuery):
        if not admin_only(call.from_user.id):
            return await call.answer()
        cat_id = int(call.data.split(":")[1])
        db.toggle_category(cat_id)
        categories = db.get_categories(active_only=False)
        await call.message.edit_text("📂 مدیریت دسته‌بندی‌ها:", reply_markup=kb.admin_categories_kb(categories))
        await call.answer("وضعیت تغییر کرد.")

    @router.callback_query(F.data.startswith("adm_cat_del:"))
    async def cb_admin_cat_del(call: CallbackQuery):
        if not admin_only(call.from_user.id):
            return await call.answer()
        cat_id = int(call.data.split(":")[1])
        db.delete_category(cat_id)
        categories = db.get_categories(active_only=False)
        await call.message.edit_text("📂 مدیریت دسته‌بندی‌ها:", reply_markup=kb.admin_categories_kb(categories))
        await call.answer("دسته‌بندی حذف شد.")

    @router.callback_query(F.data == "adm_cat_add")
    async def cb_admin_cat_add(call: CallbackQuery, state: FSMContext):
        if not admin_only(call.from_user.id):
            return await call.answer()
        await state.set_state(AdminAddCategory.waiting_name)
        await call.message.edit_text("نام دسته‌بندی جدید را ارسال کنید:", reply_markup=kb.admin_back_kb())
        await call.answer()

    @router.message(AdminAddCategory.waiting_name)
    async def process_add_category(message: Message, state: FSMContext):
        if not admin_only(message.from_user.id):
            return
        db.add_category(message.text.strip())
        await state.clear()
        await message.answer("✅ دسته‌بندی اضافه شد.", reply_markup=kb.admin_panel_kb(db, is_main_bot))

    # -------------------------------------------------------------------
    # مدیریت محصولات
    # -------------------------------------------------------------------

    @router.callback_query(F.data == "adm_products")
    async def cb_admin_products(call: CallbackQuery):
        if not admin_only(call.from_user.id):
            return await call.answer()
        categories = db.get_categories(active_only=False)
        await call.message.edit_text(
            "📦 مدیریت محصولات - ابتدا دسته‌بندی را انتخاب کنید:",
            reply_markup=kb.admin_products_categories_kb(categories),
        )
        await call.answer()

    @router.callback_query(F.data.startswith("adm_prod_cat:"))
    async def cb_admin_prod_cat(call: CallbackQuery):
        if not admin_only(call.from_user.id):
            return await call.answer()
        cat_id = int(call.data.split(":")[1])
        products = db.get_products(cat_id, active_only=False)
        if not products:
            await call.answer("محصولی در این دسته وجود ندارد.", show_alert=True)
            return
        await call.message.edit_text("لیست محصولات این دسته‌بندی:", reply_markup=kb.admin_products_list_kb(db, products))
        await call.answer()

    @router.callback_query(F.data.startswith("adm_prod_toggle:"))
    async def cb_admin_prod_toggle(call: CallbackQuery):
        if not admin_only(call.from_user.id):
            return await call.answer()
        product_id = int(call.data.split(":")[1])
        db.toggle_product(product_id)
        product = db.get_product(product_id)
        products = db.get_products(product["category_id"], active_only=False)
        await call.message.edit_text("لیست محصولات این دسته‌بندی:", reply_markup=kb.admin_products_list_kb(db, products))
        await call.answer("وضعیت تغییر کرد.")

    @router.callback_query(F.data.startswith("adm_prod_del:"))
    async def cb_admin_prod_del(call: CallbackQuery):
        if not admin_only(call.from_user.id):
            return await call.answer()
        product_id = int(call.data.split(":")[1])
        product = db.get_product(product_id)
        cat_id = product["category_id"] if product else None
        db.delete_product(product_id)
        if cat_id:
            products = db.get_products(cat_id, active_only=False)
            await call.message.edit_text("لیست محصولات این دسته‌بندی:", reply_markup=kb.admin_products_list_kb(db, products))
        await call.answer("محصول حذف شد.")

    @router.callback_query(F.data == "adm_prod_add")
    async def cb_admin_prod_add(call: CallbackQuery, state: FSMContext):
        if not admin_only(call.from_user.id):
            return await call.answer()
        categories = db.get_categories(active_only=True)
        if not categories:
            await call.answer("ابتدا باید حداقل یک دسته‌بندی فعال بسازید.", show_alert=True)
            return
        await state.set_state(AdminAddProduct.waiting_category)
        await call.message.edit_text(
            "محصول جدید در کدام دسته‌بندی اضافه شود؟",
            reply_markup=kb.admin_pick_category_kb(categories, "adm_newprod_cat"),
        )
        await call.answer()

    @router.callback_query(AdminAddProduct.waiting_category, F.data.startswith("adm_newprod_cat:"))
    async def cb_pick_category_for_new_product(call: CallbackQuery, state: FSMContext):
        cat_id = int(call.data.split(":")[1])
        await state.update_data(category_id=cat_id)
        await state.set_state(AdminAddProduct.waiting_name)
        await call.message.edit_text("نام محصول را ارسال کنید:", reply_markup=kb.admin_back_kb())
        await call.answer()

    @router.message(AdminAddProduct.waiting_name)
    async def process_product_name(message: Message, state: FSMContext):
        await state.update_data(name=message.text.strip())
        await state.set_state(AdminAddProduct.waiting_price)
        await message.answer("قیمت محصول را به تومان و فقط عدد وارد کنید (مثال: 150000):")

    @router.message(AdminAddProduct.waiting_price)
    async def process_product_price(message: Message, state: FSMContext):
        text = message.text.strip().replace(",", "")
        if not text.isdigit():
            await message.answer("لطفاً فقط عدد وارد کنید. مثال: 150000")
            return
        await state.update_data(price=int(text))
        await state.set_state(AdminAddProduct.waiting_desc)
        await message.answer("توضیحات محصول را وارد کنید (یا برای رد شدن بنویسید: -)")

    @router.message(AdminAddProduct.waiting_desc)
    async def process_product_desc(message: Message, state: FSMContext):
        desc = "" if message.text.strip() == "-" else message.text.strip()
        await state.update_data(description=desc)
        await state.set_state(AdminAddProduct.waiting_duration)
        await message.answer(
            "مدت اعتبار این سرویس چند روز است؟ فقط عدد وارد کنید (مثال: 30).\n"
            "این عدد برای محاسبه‌ی تاریخ یادآوری اتمام سرویس به کاربر استفاده می‌شود."
        )

    @router.message(AdminAddProduct.waiting_duration)
    async def process_product_duration(message: Message, state: FSMContext):
        text = message.text.strip()
        if not text.isdigit() or int(text) <= 0:
            await message.answer("لطفاً فقط عدد صحیح و بزرگ‌تر از صفر وارد کنید. مثال: 30")
            return
        data = await state.get_data()
        db.add_product(data["category_id"], data["name"], data["price"], data["description"], int(text))
        await state.clear()
        await message.answer("✅ محصول با موفقیت اضافه شد.", reply_markup=kb.admin_panel_kb(db, is_main_bot))

    # -------------------------------------------------------------------
    # افزودن کانفیگ (بانک لینک) به محصول
    # -------------------------------------------------------------------

    @router.callback_query(F.data == "adm_add_configs")
    async def cb_admin_add_configs(call: CallbackQuery, state: FSMContext):
        if not admin_only(call.from_user.id):
            return await call.answer()
        products = db.get_all_products()
        if not products:
            await call.answer("ابتدا باید یک محصول بسازید.", show_alert=True)
            return
        await state.set_state(AdminAddConfigs.waiting_product)
        await call.message.edit_text(
            "افزودن کانفیگ به کدام محصول؟", reply_markup=kb.admin_pick_product_kb(products, "adm_addcfg_prod")
        )
        await call.answer()

    @router.callback_query(AdminAddConfigs.waiting_product, F.data.startswith("adm_addcfg_prod:"))
    async def cb_pick_product_for_configs(call: CallbackQuery, state: FSMContext):
        product_id = int(call.data.split(":")[1])
        await state.update_data(product_id=product_id)
        await state.set_state(AdminAddConfigs.waiting_links)
        await call.message.edit_text(
            "لینک‌های کانفیگ را ارسال کنید (هر لینک در یک خط جداگانه). می‌توانید چند لینک را با هم در یک پیام بفرستید:",
            reply_markup=kb.admin_back_kb(),
        )
        await call.answer()

    @router.message(AdminAddConfigs.waiting_links)
    async def process_add_configs(message: Message, state: FSMContext):
        data = await state.get_data()
        product_id = data["product_id"]
        links = [line for line in message.text.splitlines() if line.strip()]
        db.add_configs(product_id, links)
        await state.clear()
        stock = db.count_available_configs(product_id)
        await message.answer(
            f"✅ {len(links)} لینک اضافه شد.\n📊 موجودی فعلی این محصول: {stock} عدد",
            reply_markup=kb.admin_panel_kb(db, is_main_bot),
        )

    # -------------------------------------------------------------------
    # مدیریت کانفیگ تست
    # -------------------------------------------------------------------

    @router.callback_query(F.data == "adm_test_menu")
    async def cb_admin_test_menu(call: CallbackQuery):
        if not admin_only(call.from_user.id):
            return await call.answer()
        await call.message.edit_text("🧪 مدیریت کانفیگ تست:", reply_markup=kb.admin_test_menu_kb(db))
        await call.answer()

    @router.callback_query(F.data == "adm_test_toggle")
    async def cb_admin_test_toggle(call: CallbackQuery):
        if not admin_only(call.from_user.id):
            return await call.answer()
        current = db.get_setting("test_enabled", "1")
        db.set_setting("test_enabled", "0" if current == "1" else "1")
        await call.message.edit_text("🧪 مدیریت کانفیگ تست:", reply_markup=kb.admin_test_menu_kb(db))
        await call.answer("وضعیت کانفیگ تست تغییر کرد.")

    @router.callback_query(F.data == "adm_test_add")
    async def cb_admin_test_add(call: CallbackQuery, state: FSMContext):
        if not admin_only(call.from_user.id):
            return await call.answer()
        await state.set_state(AdminAddTestConfigs.waiting_links)
        await call.message.edit_text(
            "لینک‌های کانفیگ تست را ارسال کنید (هر لینک در یک خط):", reply_markup=kb.admin_back_kb()
        )
        await call.answer()

    @router.message(AdminAddTestConfigs.waiting_links)
    async def process_add_test_configs(message: Message, state: FSMContext):
        links = [line for line in message.text.splitlines() if line.strip()]
        db.add_test_configs(links)
        await state.clear()
        await message.answer(f"✅ {len(links)} لینک تست اضافه شد.", reply_markup=kb.admin_panel_kb(db, is_main_bot))

    # -------------------------------------------------------------------
    # سفارش‌های در انتظار
    # -------------------------------------------------------------------

    @router.callback_query(F.data == "adm_pending_orders")
    async def cb_admin_pending_orders(call: CallbackQuery):
        if not admin_only(call.from_user.id):
            return await call.answer()
        orders = db.get_pending_orders()
        if not orders:
            await call.answer("سفارش در انتظاری وجود ندارد.", show_alert=True)
            return
        await call.message.edit_text("🧾 سفارش‌های در انتظار بررسی:", reply_markup=kb.pending_orders_kb(orders))
        await call.answer()

    @router.callback_query(F.data.startswith("view_order:"))
    async def cb_view_order(call: CallbackQuery, bot: Bot):
        if not admin_only(call.from_user.id):
            return await call.answer()
        order_id = int(call.data.split(":")[1])
        order = db.get_order(order_id)
        if not order:
            await call.answer("سفارش یافت نشد.", show_alert=True)
            return
        product = db.get_product(order["product_id"])
        caption = f"سفارش #{order_id}\nکاربر: {order['user_id']}\nمحصول: {product['name'] if product else '---'}"
        if order["receipt_file_id"]:
            await bot.send_photo(call.from_user.id, order["receipt_file_id"], caption=caption, reply_markup=kb.order_review_kb(order_id))
        else:
            await call.message.answer(caption, reply_markup=kb.order_review_kb(order_id))
        await call.answer()

    @router.callback_query(F.data.startswith("order_approve:"))
    async def cb_order_approve(call: CallbackQuery, bot: Bot):
        if not admin_only(call.from_user.id):
            return await call.answer()

        order_id = int(call.data.split(":")[1])
        order = db.get_order(order_id)
        if not order:
            await call.answer("سفارش یافت نشد.", show_alert=True)
            return
        if order["status"] != "pending":
            await call.answer("این سفارش قبلاً بررسی شده است.", show_alert=True)
            return

        product = db.get_product(order["product_id"])
        result = db.take_unused_config(order["product_id"], order["user_id"])
        if not result:
            await call.answer("⛔️ موجودی این محصول تمام شده! ابتدا لینک جدید اضافه کنید.", show_alert=True)
            return

        db.approve_order(order_id, result["id"])

        reward_info = db.reward_referrer_if_first_purchase(order["user_id"], order["final_price"] or product["price"])
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

        try:
            await bot.send_message(order["user_id"], f"✅ خرید شما تایید شد!\n📦 محصول: {product['name']}")
            await deliver_config_to_user(
                bot,
                order["user_id"],
                product["name"],
                result["link"],
                final_price=order["final_price"],
                order_id=order_id,
            )
        except Exception:
            pass

        try:
            await call.message.edit_caption(caption=(call.message.caption or "") + "\n\n✅ تایید شد و کانفیگ ارسال شد.")
        except Exception:
            try:
                await call.message.edit_text((call.message.text or "") + "\n\n✅ تایید شد و کانفیگ ارسال شد.")
            except Exception:
                pass
        await call.answer("سفارش تایید و کانفیگ برای کاربر ارسال شد.")

    @router.callback_query(F.data.startswith("order_reject:"))
    async def cb_order_reject(call: CallbackQuery, bot: Bot):
        if not admin_only(call.from_user.id):
            return await call.answer()

        order_id = int(call.data.split(":")[1])
        order = db.get_order(order_id)
        if not order:
            await call.answer("سفارش یافت نشد.", show_alert=True)
            return
        if order["status"] != "pending":
            await call.answer("این سفارش قبلاً بررسی شده است.", show_alert=True)
            return

        db.reject_order(order_id)
        try:
            await bot.send_message(
                order["user_id"],
                "❌ متاسفانه رسید ارسالی شما تایید نشد. در صورت اشتباه لطفاً با پشتیبانی در ارتباط باشید.",
            )
        except Exception:
            pass

        try:
            await call.message.edit_caption(caption=(call.message.caption or "") + "\n\n❌ رد شد.")
        except Exception:
            try:
                await call.message.edit_text((call.message.text or "") + "\n\n❌ رد شد.")
            except Exception:
                pass
        await call.answer("سفارش رد شد.")

    # -------------------------------------------------------------------
    # درخواست‌های شارژ کیف پول
    # -------------------------------------------------------------------

    @router.callback_query(F.data == "adm_pending_topups")
    async def cb_admin_pending_topups(call: CallbackQuery):
        if not admin_only(call.from_user.id):
            return await call.answer()
        topups = db.get_pending_topups()
        if not topups:
            await call.answer("درخواست شارژ در انتظاری وجود ندارد.", show_alert=True)
            return
        await call.message.edit_text("👛 درخواست‌های شارژ کیف پول در انتظار:", reply_markup=kb.pending_topups_kb(topups))
        await call.answer()

    @router.callback_query(F.data.startswith("view_topup:"))
    async def cb_view_topup(call: CallbackQuery, bot: Bot):
        if not admin_only(call.from_user.id):
            return await call.answer()
        topup_id = int(call.data.split(":")[1])
        topup = db.get_topup(topup_id)
        if not topup:
            await call.answer("درخواست یافت نشد.", show_alert=True)
            return
        caption = f"شارژ کیف پول #{topup_id}\nکاربر: {topup['user_id']}\nمبلغ: {topup['amount']:,} تومان"
        if topup["receipt_file_id"]:
            await bot.send_photo(call.from_user.id, topup["receipt_file_id"], caption=caption, reply_markup=kb.topup_review_kb(topup_id))
        else:
            await call.message.answer(caption, reply_markup=kb.topup_review_kb(topup_id))
        await call.answer()

    @router.callback_query(F.data.startswith("topup_approve:"))
    async def cb_topup_approve(call: CallbackQuery, bot: Bot):
        if not admin_only(call.from_user.id):
            return await call.answer()

        topup_id = int(call.data.split(":")[1])
        topup = db.get_topup(topup_id)
        if not topup:
            await call.answer("درخواست یافت نشد.", show_alert=True)
            return
        if topup["status"] != "pending":
            await call.answer("این درخواست قبلاً بررسی شده است.", show_alert=True)
            return

        db.approve_topup(topup_id)
        new_balance = db.get_wallet_credit(topup["user_id"])

        try:
            await bot.send_message(
                topup["user_id"],
                f"✅ شارژ کیف پول شما تایید شد!\n💰 مبلغ {topup['amount']:,} تومان اضافه شد.\n"
                f"👛 موجودی فعلی کیف پول شما: {new_balance:,} تومان",
            )
        except Exception:
            pass

        try:
            await call.message.edit_caption(caption=(call.message.caption or "") + "\n\n✅ تایید و شارژ شد.")
        except Exception:
            try:
                await call.message.edit_text((call.message.text or "") + "\n\n✅ تایید و شارژ شد.")
            except Exception:
                pass
        await call.answer("شارژ کیف پول تایید شد.")

    @router.callback_query(F.data.startswith("topup_reject:"))
    async def cb_topup_reject(call: CallbackQuery, bot: Bot):
        if not admin_only(call.from_user.id):
            return await call.answer()

        topup_id = int(call.data.split(":")[1])
        topup = db.get_topup(topup_id)
        if not topup:
            await call.answer("درخواست یافت نشد.", show_alert=True)
            return
        if topup["status"] != "pending":
            await call.answer("این درخواست قبلاً بررسی شده است.", show_alert=True)
            return

        db.reject_topup(topup_id)
        try:
            await bot.send_message(
                topup["user_id"],
                "❌ متاسفانه درخواست شارژ کیف پول شما تایید نشد. در صورت اشتباه با پشتیبانی تماس بگیرید.",
            )
        except Exception:
            pass

        try:
            await call.message.edit_caption(caption=(call.message.caption or "") + "\n\n❌ رد شد.")
        except Exception:
            try:
                await call.message.edit_text((call.message.text or "") + "\n\n❌ رد شد.")
            except Exception:
                pass
        await call.answer("درخواست رد شد.")

    # -------------------------------------------------------------------
    # مدیریت کدهای تخفیف
    # -------------------------------------------------------------------

    @router.callback_query(F.data == "adm_discounts_menu")
    async def cb_admin_discounts_menu(call: CallbackQuery):
        if not admin_only(call.from_user.id):
            return await call.answer()
        codes = db.list_discount_codes()
        await call.message.edit_text("🎟 مدیریت کدهای تخفیف:", reply_markup=kb.discount_codes_kb(codes))
        await call.answer()

    @router.callback_query(F.data.startswith("adm_disc_toggle:"))
    async def cb_admin_disc_toggle(call: CallbackQuery):
        if not admin_only(call.from_user.id):
            return await call.answer()
        code_id = int(call.data.split(":")[1])
        db.toggle_discount_code(code_id)
        codes = db.list_discount_codes()
        await call.message.edit_text("🎟 مدیریت کدهای تخفیف:", reply_markup=kb.discount_codes_kb(codes))
        await call.answer("وضعیت تغییر کرد.")

    @router.callback_query(F.data.startswith("adm_disc_del:"))
    async def cb_admin_disc_del(call: CallbackQuery):
        if not admin_only(call.from_user.id):
            return await call.answer()
        code_id = int(call.data.split(":")[1])
        db.delete_discount_code(code_id)
        codes = db.list_discount_codes()
        await call.message.edit_text("🎟 مدیریت کدهای تخفیف:", reply_markup=kb.discount_codes_kb(codes))
        await call.answer("کد حذف شد.")

    @router.callback_query(F.data == "adm_disc_add")
    async def cb_admin_disc_add(call: CallbackQuery, state: FSMContext):
        if not admin_only(call.from_user.id):
            return await call.answer()
        await state.set_state(AdminCreateDiscount.waiting_code)
        await call.message.edit_text(
            "نام کد تخفیف را ارسال کنید (مثلاً WELCOME20، بدون فاصله):", reply_markup=kb.admin_back_kb()
        )
        await call.answer()

    @router.message(AdminCreateDiscount.waiting_code)
    async def process_disc_code(message: Message, state: FSMContext):
        code = message.text.strip()
        if db.get_discount_code(code):
            await message.answer("⛔️ این کد از قبل وجود دارد. یک نام دیگر ارسال کنید:")
            return
        await state.update_data(disc_code=code)
        await state.set_state(AdminCreateDiscount.waiting_type_value)
        await message.answer(
            "نوع و مقدار تخفیف را به یکی از این دو شکل ارسال کنید:\n\n"
            "برای تخفیف درصدی: `percent 20`\n"
            "برای تخفیف مبلغ ثابت: `fixed 50000`",
            parse_mode="Markdown",
        )

    @router.message(AdminCreateDiscount.waiting_type_value)
    async def process_disc_type_value(message: Message, state: FSMContext):
        parts = message.text.strip().split()
        if len(parts) != 2 or parts[0].lower() not in ("percent", "fixed") or not parts[1].isdigit():
            await message.answer("فرمت اشتباه است. مثال درست: `percent 20` یا `fixed 50000`", parse_mode="Markdown")
            return

        kind, value = parts[0].lower(), int(parts[1])
        if kind == "percent":
            await state.update_data(disc_percent=value, disc_fixed=None)
        else:
            await state.update_data(disc_percent=None, disc_fixed=value)

        await state.set_state(AdminCreateDiscount.waiting_maxuses)
        await message.answer("سقف تعداد استفاده از این کد چند بار باشد؟ (برای نامحدود عدد 0 را بفرست)")

    @router.message(AdminCreateDiscount.waiting_maxuses)
    async def process_disc_maxuses(message: Message, state: FSMContext):
        if not message.text.strip().isdigit():
            await message.answer("لطفاً فقط عدد ارسال کنید (0 برای نامحدود).")
            return
        max_uses = int(message.text.strip())
        data = await state.get_data()
        db.create_discount_code(
            data["disc_code"], percent=data.get("disc_percent"), fixed_amount=data.get("disc_fixed"), max_uses=max_uses
        )
        await state.clear()
        await message.answer(f"✅ کد تخفیف «{data['disc_code']}» ساخته شد.", reply_markup=kb.admin_panel_kb(db, is_main_bot))

    # -------------------------------------------------------------------
    # تنظیمات زیرمجموعه‌گیری
    # -------------------------------------------------------------------

    @router.callback_query(F.data == "adm_referral_settings")
    async def cb_admin_referral_settings(call: CallbackQuery):
        if not admin_only(call.from_user.id):
            return await call.answer()
        await call.message.edit_text("🤝 تنظیمات زیرمجموعه‌گیری:", reply_markup=kb.referral_settings_kb(db))
        await call.answer()

    @router.callback_query(F.data == "adm_referral_toggle")
    async def cb_admin_referral_toggle(call: CallbackQuery):
        if not admin_only(call.from_user.id):
            return await call.answer()
        current = db.get_setting("referral_enabled", "1")
        db.set_setting("referral_enabled", "0" if current == "1" else "1")
        await call.message.edit_text("🤝 تنظیمات زیرمجموعه‌گیری:", reply_markup=kb.referral_settings_kb(db))
        await call.answer("وضعیت تغییر کرد.")

    @router.callback_query(F.data == "adm_referral_percent_edit")
    async def cb_admin_referral_percent_edit(call: CallbackQuery, state: FSMContext):
        if not admin_only(call.from_user.id):
            return await call.answer()
        await state.set_state(AdminReferralPercent.waiting_value)
        await call.message.edit_text(
            "درصد پورسانت جدید را وارد کنید (عددی بین 0 تا 100):", reply_markup=kb.admin_back_kb()
        )
        await call.answer()

    @router.message(AdminReferralPercent.waiting_value)
    async def process_referral_percent(message: Message, state: FSMContext):
        text = message.text.strip()
        if not text.isdigit() or not (0 <= int(text) <= 100):
            await message.answer("لطفاً یک عدد بین 0 تا 100 ارسال کنید.")
            return
        db.set_setting("referral_percent", text)
        await state.clear()
        await message.answer(f"✅ درصد پورسانت زیرمجموعه‌گیری روی {text}٪ تنظیم شد.", reply_markup=kb.admin_panel_kb(db, is_main_bot))

    # -------------------------------------------------------------------
    # مدیریت گردونه شانس
    # -------------------------------------------------------------------

    @router.callback_query(F.data == "adm_wheel_settings")
    async def cb_admin_wheel_settings(call: CallbackQuery):
        if not admin_only(call.from_user.id):
            return await call.answer()
        await call.message.edit_text("🎡 مدیریت گردونه شانس:", reply_markup=kb.wheel_settings_kb(db))
        await call.answer()

    @router.callback_query(F.data == "adm_wheel_toggle")
    async def cb_admin_wheel_toggle(call: CallbackQuery):
        if not admin_only(call.from_user.id):
            return await call.answer()
        current = db.get_setting("wheel_enabled", "1")
        db.set_setting("wheel_enabled", "0" if current == "1" else "1")
        await call.message.edit_text("🎡 مدیریت گردونه شانس:", reply_markup=kb.wheel_settings_kb(db))
        await call.answer("وضعیت تغییر کرد.")

    @router.callback_query(F.data == "adm_wheel_edit_percent")
    async def cb_admin_wheel_edit_percent(call: CallbackQuery, state: FSMContext):
        if not admin_only(call.from_user.id):
            return await call.answer()
        await state.set_state(AdminWheelSettings.waiting_win_percent)
        await call.message.edit_text(
            "درصد احتمال برد را وارد کنید (عددی بین 0 تا 100، مثلاً 10):", reply_markup=kb.admin_back_kb()
        )
        await call.answer()

    @router.message(AdminWheelSettings.waiting_win_percent)
    async def process_wheel_percent(message: Message, state: FSMContext):
        text = message.text.strip()
        if not text.isdigit() or not (0 <= int(text) <= 100):
            await message.answer("لطفاً یک عدد بین 0 تا 100 ارسال کنید.")
            return
        db.set_setting("wheel_win_percent", text)
        await state.clear()
        await message.answer(f"✅ احتمال برد گردونه روی {text}٪ تنظیم شد.", reply_markup=kb.admin_panel_kb(db, is_main_bot))

    @router.callback_query(F.data == "adm_wheel_edit_prizes")
    async def cb_admin_wheel_edit_prizes(call: CallbackQuery, state: FSMContext):
        if not admin_only(call.from_user.id):
            return await call.answer()
        await state.set_state(AdminWheelSettings.waiting_prizes)
        await call.message.edit_text(
            "درصدهای تخفیف ممکن را با کاما جدا کرده و ارسال کنید (مثلاً: 10,20,30,50):",
            reply_markup=kb.admin_back_kb(),
        )
        await call.answer()

    @router.message(AdminWheelSettings.waiting_prizes)
    async def process_wheel_prizes(message: Message, state: FSMContext):
        parts = [p.strip() for p in message.text.split(",")]
        if not all(p.isdigit() and 0 < int(p) <= 100 for p in parts) or not parts:
            await message.answer("فرمت اشتباه است. مثال درست: 10,20,30,50")
            return
        db.set_wheel_prizes([int(p) for p in parts])
        await state.clear()
        await message.answer("✅ لیست جوایز گردونه به‌روزرسانی شد.", reply_markup=kb.admin_panel_kb(db, is_main_bot))

    @router.callback_query(F.data == "adm_wheel_edit_expiry")
    async def cb_admin_wheel_edit_expiry(call: CallbackQuery, state: FSMContext):
        if not admin_only(call.from_user.id):
            return await call.answer()
        await state.set_state(AdminWheelSettings.waiting_expiry)
        await call.message.edit_text(
            "کد جایزه چند ساعت اعتبار داشته باشد؟ (فقط عدد، مثلاً 24):", reply_markup=kb.admin_back_kb()
        )
        await call.answer()

    @router.message(AdminWheelSettings.waiting_expiry)
    async def process_wheel_expiry(message: Message, state: FSMContext):
        text = message.text.strip()
        if not text.isdigit() or int(text) <= 0:
            await message.answer("لطفاً یک عدد صحیح مثبت ارسال کنید.")
            return
        db.set_setting("wheel_code_expiry_hours", text)
        await state.clear()
        await message.answer(f"✅ اعتبار کد جایزه روی {text} ساعت تنظیم شد.", reply_markup=kb.admin_panel_kb(db, is_main_bot))

    @router.callback_query(F.data == "adm_wheel_edit_cooldown")
    async def cb_admin_wheel_edit_cooldown(call: CallbackQuery, state: FSMContext):
        if not admin_only(call.from_user.id):
            return await call.answer()
        await state.set_state(AdminWheelSettings.waiting_cooldown)
        await call.message.edit_text(
            "فاصله مجاز بین دو چرخش هر کاربر چند ساعت باشد؟ (فقط عدد، مثلاً 24):", reply_markup=kb.admin_back_kb()
        )
        await call.answer()

    @router.message(AdminWheelSettings.waiting_cooldown)
    async def process_wheel_cooldown(message: Message, state: FSMContext):
        text = message.text.strip()
        if not text.isdigit() or int(text) <= 0:
            await message.answer("لطفاً یک عدد صحیح مثبت ارسال کنید.")
            return
        db.set_setting("wheel_cooldown_hours", text)
        await state.clear()
        await message.answer(f"✅ فاصله بین دو چرخش روی {text} ساعت تنظیم شد.", reply_markup=kb.admin_panel_kb(db, is_main_bot))

    # -------------------------------------------------------------------
    # یادآوری اتمام سرویس + کد تخفیف تشویقی تمدید
    # -------------------------------------------------------------------

    @router.callback_query(F.data == "adm_renewal_settings")
    async def cb_admin_renewal_settings(call: CallbackQuery):
        if not admin_only(call.from_user.id):
            return await call.answer()
        await call.message.edit_text("🔔 یادآوری تمدید سرویس:", reply_markup=kb.renewal_settings_kb(db))
        await call.answer()

    @router.callback_query(F.data == "adm_renewal_toggle")
    async def cb_admin_renewal_toggle(call: CallbackQuery):
        if not admin_only(call.from_user.id):
            return await call.answer()
        current = db.get_setting("renewal_reminder_enabled", "1")
        db.set_setting("renewal_reminder_enabled", "0" if current == "1" else "1")
        await call.message.edit_text("🔔 یادآوری تمدید سرویس:", reply_markup=kb.renewal_settings_kb(db))
        await call.answer("وضعیت تغییر کرد.")

    @router.callback_query(F.data == "adm_renewal_edit_days")
    async def cb_admin_renewal_edit_days(call: CallbackQuery, state: FSMContext):
        if not admin_only(call.from_user.id):
            return await call.answer()
        await state.set_state(AdminRenewalSettings.waiting_days_before)
        await call.message.edit_text(
            "چند روز قبل از اتمام سرویس، یادآوری ارسال شود؟ (فقط عدد، مثلاً 5):",
            reply_markup=kb.admin_back_kb(),
        )
        await call.answer()

    @router.message(AdminRenewalSettings.waiting_days_before)
    async def process_renewal_days(message: Message, state: FSMContext):
        text = message.text.strip()
        if not text.isdigit() or int(text) <= 0:
            await message.answer("لطفاً یک عدد صحیح مثبت ارسال کنید.")
            return
        db.set_setting("renewal_reminder_days_before", text)
        await state.clear()
        await message.answer(
            f"✅ یادآوری روی {text} روز قبل از اتمام سرویس تنظیم شد.", reply_markup=kb.admin_panel_kb(db, is_main_bot)
        )

    @router.callback_query(F.data == "adm_renewal_edit_percent")
    async def cb_admin_renewal_edit_percent(call: CallbackQuery, state: FSMContext):
        if not admin_only(call.from_user.id):
            return await call.answer()
        await state.set_state(AdminRenewalSettings.waiting_percent)
        await call.message.edit_text(
            "درصد تخفیف کد تشویقی تمدید چقدر باشد؟ (عددی بین 1 تا 100، مثلاً 20):",
            reply_markup=kb.admin_back_kb(),
        )
        await call.answer()

    @router.message(AdminRenewalSettings.waiting_percent)
    async def process_renewal_percent(message: Message, state: FSMContext):
        text = message.text.strip()
        if not text.isdigit() or not (0 < int(text) <= 100):
            await message.answer("لطفاً یک عدد بین 1 تا 100 ارسال کنید.")
            return
        db.set_setting("renewal_discount_percent", text)
        await state.clear()
        await message.answer(f"✅ درصد تخفیف کد تشویقی روی {text}٪ تنظیم شد.", reply_markup=kb.admin_panel_kb(db, is_main_bot))

    @router.callback_query(F.data == "adm_renewal_edit_hours")
    async def cb_admin_renewal_edit_hours(call: CallbackQuery, state: FSMContext):
        if not admin_only(call.from_user.id):
            return await call.answer()
        await state.set_state(AdminRenewalSettings.waiting_expiry_hours)
        await call.message.edit_text(
            "کد تخفیف تشویقی چند ساعت اعتبار داشته باشد؟ (فقط عدد، مثلاً 24):",
            reply_markup=kb.admin_back_kb(),
        )
        await call.answer()

    @router.message(AdminRenewalSettings.waiting_expiry_hours)
    async def process_renewal_hours(message: Message, state: FSMContext):
        text = message.text.strip()
        if not text.isdigit() or int(text) <= 0:
            await message.answer("لطفاً یک عدد صحیح مثبت ارسال کنید.")
            return
        db.set_setting("renewal_discount_expiry_hours", text)
        await state.clear()
        await message.answer(
            f"✅ اعتبار کد تخفیف تشویقی روی {text} ساعت تنظیم شد.", reply_markup=kb.admin_panel_kb(db, is_main_bot)
        )

    # -------------------------------------------------------------------
    # مدیریت بات‌های نمایندگی (فقط در بات اصلی)
    # هر نماینده توکن بات خودش را می‌دهد؛ سیستم یک بات کاملاً مستقل با
    # دیتابیس جدا (شامل تمام امکانات: تست، تخفیف، زیرمجموعه‌گیری، کیف پول)
    # برایش راه‌اندازی می‌کند.
    # -------------------------------------------------------------------

    if is_main_bot:

        @router.callback_query(F.data == "adm_resellers_menu")
        async def cb_admin_resellers_menu(call: CallbackQuery):
            if not admin_only(call.from_user.id):
                return await call.answer()
            bots = db.list_reseller_bots()
            await call.message.edit_text("🏪 مدیریت بات‌های نمایندگی:", reply_markup=kb.resellers_kb(bots))
            await call.answer()

        @router.callback_query(F.data.startswith("adm_resbot_toggle:"))
        async def cb_admin_resbot_toggle(call: CallbackQuery):
            if not admin_only(call.from_user.id):
                return await call.answer()
            bot_id = int(call.data.split(":")[1])
            reseller_bot = db.get_reseller_bot(bot_id)
            if not reseller_bot:
                return await call.answer("یافت نشد.", show_alert=True)

            db.toggle_reseller_bot(bot_id)
            updated = db.get_reseller_bot(bot_id)

            if bot_manager:
                if updated["is_active"]:
                    await bot_manager.start_bot(
                        updated["bot_token"], updated["db_path"], updated["owner_telegram_id"], is_main_bot=False
                    )
                else:
                    await bot_manager.stop_bot(updated["bot_token"])

            bots = db.list_reseller_bots()
            await call.message.edit_text("🏪 مدیریت بات‌های نمایندگی:", reply_markup=kb.resellers_kb(bots))
            await call.answer("وضعیت تغییر کرد و اعمال شد.")

        @router.callback_query(F.data.startswith("adm_resbot_del:"))
        async def cb_admin_resbot_del(call: CallbackQuery):
            if not admin_only(call.from_user.id):
                return await call.answer()
            bot_id = int(call.data.split(":")[1])
            reseller_bot = db.get_reseller_bot(bot_id)
            if reseller_bot and bot_manager:
                await bot_manager.stop_bot(reseller_bot["bot_token"])
            db.delete_reseller_bot(bot_id)
            bots = db.list_reseller_bots()
            await call.message.edit_text(
                "🏪 مدیریت بات‌های نمایندگی:\n\n⚠️ بات متوقف شد. فایل دیتابیسش برای احتیاط پاک نشد.",
                reply_markup=kb.resellers_kb(bots),
            )
            await call.answer("بات نمایندگی حذف شد.")

        @router.callback_query(F.data == "adm_resbot_add")
        async def cb_admin_resbot_add(call: CallbackQuery, state: FSMContext):
            if not admin_only(call.from_user.id):
                return await call.answer()
            await state.set_state(AdminAddResellerBot.waiting_token)
            await call.message.edit_text(
                "توکن بات نماینده را ارسال کنید (همانی که از @BotFather گرفته):",
                reply_markup=kb.admin_back_kb(),
            )
            await call.answer()

        @router.message(AdminAddResellerBot.waiting_token)
        async def process_resbot_token(message: Message, state: FSMContext):
            token = message.text.strip()

            existing = None
            with_conn_check = None
            for b in db.list_reseller_bots():
                if b["bot_token"] == token:
                    existing = b
                    break
            if existing:
                await message.answer("⛔️ این توکن قبلاً ثبت شده است.")
                return

            await message.answer("⏳ در حال بررسی اعتبار توکن...")
            temp_bot = Bot(token=token)
            try:
                me = await temp_bot.get_me()
            except Exception:
                await message.answer("❌ این توکن معتبر نیست. دوباره بررسی و ارسال کنید:")
                await temp_bot.session.close()
                return
            await temp_bot.session.close()

            await state.update_data(resbot_token=token, resbot_username=me.username)
            await state.set_state(AdminAddResellerBot.waiting_owner_id)
            await message.answer(
                f"✅ توکن معتبر است: @{me.username}\n\n"
                f"حالا آیدی عددی نماینده (مالک این بات) را ارسال کنید:"
            )

        @router.message(AdminAddResellerBot.waiting_owner_id)
        async def process_resbot_owner_id(message: Message, state: FSMContext):
            if not message.text.strip().isdigit():
                await message.answer("لطفاً فقط آیدی عددی ارسال کنید.")
                return
            await state.update_data(resbot_owner_id=int(message.text.strip()))
            await state.set_state(AdminAddResellerBot.waiting_owner_name)
            await message.answer("یک نام برای این نماینده وارد کنید (فقط برای نمایش در پنل مدیریت):")

        @router.message(AdminAddResellerBot.waiting_owner_name)
        async def process_resbot_owner_name(message: Message, state: FSMContext):
            data = await state.get_data()
            token = data["resbot_token"]
            username = data["resbot_username"]
            owner_id = data["resbot_owner_id"]
            owner_name = message.text.strip()

            os.makedirs(RESELLER_DBS_DIR, exist_ok=True)
            db_path = os.path.join(RESELLER_DBS_DIR, f"{username}.db")

            db.register_reseller_bot(token, username, owner_id, owner_name, db_path)

            started = False
            if bot_manager:
                started = await bot_manager.start_bot(token, db_path, owner_id, is_main_bot=False)

            await state.clear()
            status_text = "✅ بات نمایندگی راه‌اندازی و همین الان روشن شد." if started else \
                "⚠️ بات ثبت شد ولی راه‌اندازی زنده انجام نشد؛ با ری‌استارت سرویس اصلی خودکار روشن می‌شود."
            await message.answer(
                f"{status_text}\n\n"
                f"🤖 بات: @{username}\n"
                f"👤 نماینده: {owner_name} ({owner_id})\n\n"
                f"این بات کاملاً مستقل است و تمام امکانات (کد تخفیف، زیرمجموعه‌گیری، کیف پول، کانفیگ تست) را "
                f"از صفر و جدا از بات اصلی دارد. نماینده باید با /start به بات خودش (@{username}) وارد شود.",
                reply_markup=kb.admin_panel_kb(db, is_main_bot),
            )

    # -------------------------------------------------------------------
    # ویرایش متن دکمه‌ها
    # -------------------------------------------------------------------

    @router.callback_query(F.data == "adm_edit_buttons")
    async def cb_admin_edit_buttons(call: CallbackQuery):
        if not admin_only(call.from_user.id):
            return await call.answer()
        await call.message.edit_text("کدام دکمه ویرایش شود؟", reply_markup=kb.admin_edit_buttons_kb(db))
        await call.answer()

    @router.callback_query(F.data.startswith("adm_btn_edit:"))
    async def cb_admin_btn_edit(call: CallbackQuery, state: FSMContext):
        key = call.data.split(":")[1]
        await state.update_data(setting_key=key)
        await state.set_state(AdminEditButton.waiting_text)
        current = db.get_setting(key)
        await call.message.edit_text(
            f"متن فعلی: {current}\n\nمتن جدید را ارسال کنید (می‌توانید ایموجی هم اضافه کنید):",
            reply_markup=kb.admin_back_kb(),
        )
        await call.answer()

    @router.message(AdminEditButton.waiting_text)
    async def process_edit_button(message: Message, state: FSMContext):
        data = await state.get_data()
        key = data["setting_key"]
        db.set_setting(key, message.text.strip())
        await state.clear()
        await message.answer("✅ متن دکمه به‌روزرسانی شد.", reply_markup=kb.admin_panel_kb(db, is_main_bot))

    def _lookup_button_label(key: str) -> str:
        if key in kb.BUTTON_LABELS:
            return kb.BUTTON_LABELS[key]
        for item_key, label, _ in kb.ADMIN_PANEL_ITEMS:
            if item_key == key:
                return label
        return key

    def _is_panel_item_key(key: str) -> bool:
        return any(item_key == key for item_key, _, _ in kb.ADMIN_PANEL_ITEMS)

    @router.callback_query(F.data.startswith("adm_btn_color_menu:"))
    async def cb_admin_btn_color_menu(call: CallbackQuery):
        key = call.data.split(":")[1]
        label = _lookup_button_label(key)
        back_callback = "adm_panel_colors_menu" if _is_panel_item_key(key) else "adm_edit_buttons"
        await call.message.edit_text(
            f"رنگ «{label}» را انتخاب کنید:", reply_markup=kb.admin_color_picker_kb(key, back_callback)
        )
        await call.answer()

    @router.callback_query(F.data.startswith("adm_btn_color_set:"))
    async def cb_admin_btn_color_set(call: CallbackQuery):
        _, key, style = call.data.split(":")
        db.set_setting(f"{key}_style", "" if style == "none" else style)
        if _is_panel_item_key(key):
            await call.message.edit_text("🎨 رنگ‌آمیزی دکمه‌های پنل مدیریت:", reply_markup=kb.admin_panel_colors_kb(db, is_main_bot))
        else:
            await call.message.edit_text("کدام دکمه ویرایش شود؟", reply_markup=kb.admin_edit_buttons_kb(db))
        await call.answer("✅ رنگ دکمه به‌روزرسانی شد.")

    @router.callback_query(F.data == "adm_panel_colors_menu")
    async def cb_admin_panel_colors_menu(call: CallbackQuery):
        await call.message.edit_text("🎨 رنگ‌آمیزی دکمه‌های پنل مدیریت:", reply_markup=kb.admin_panel_colors_kb(db, is_main_bot))
        await call.answer()

    # -------------------------------------------------------------------
    # تنظیم شماره کارت
    # -------------------------------------------------------------------

    @router.callback_query(F.data == "adm_set_card")
    async def cb_admin_set_card(call: CallbackQuery, state: FSMContext):
        if not admin_only(call.from_user.id):
            return await call.answer()
        await state.set_state(AdminSetCard.waiting_number)
        await call.message.edit_text("شماره کارت جدید را ارسال کنید:", reply_markup=kb.admin_back_kb())
        await call.answer()

    @router.message(AdminSetCard.waiting_number)
    async def process_set_card_number(message: Message, state: FSMContext):
        await state.update_data(card_number=message.text.strip())
        await state.set_state(AdminSetCard.waiting_holder)
        await message.answer("نام صاحب حساب را ارسال کنید:")

    @router.message(AdminSetCard.waiting_holder)
    async def process_set_card_holder(message: Message, state: FSMContext):
        data = await state.get_data()
        db.set_setting("card_number", data["card_number"])
        db.set_setting("card_holder", message.text.strip())
        await state.clear()
        await message.answer("✅ اطلاعات کارت به‌روزرسانی شد.", reply_markup=kb.admin_panel_kb(db, is_main_bot))

    # -------------------------------------------------------------------
    # ویرایش پیام خوش‌آمد
    # -------------------------------------------------------------------

    @router.callback_query(F.data == "adm_edit_welcome")
    async def cb_admin_edit_welcome(call: CallbackQuery, state: FSMContext):
        if not admin_only(call.from_user.id):
            return await call.answer()
        await state.set_state(AdminEditWelcome.waiting_text)
        current = db.get_setting("welcome_text")
        await call.message.edit_text(f"متن فعلی:\n{current}\n\nمتن جدید را ارسال کنید:", reply_markup=kb.admin_back_kb())
        await call.answer()

    @router.message(AdminEditWelcome.waiting_text)
    async def process_edit_welcome(message: Message, state: FSMContext):
        db.set_setting("welcome_text", message.text)
        await state.clear()
        await message.answer("✅ پیام خوش‌آمد به‌روزرسانی شد.", reply_markup=kb.admin_panel_kb(db, is_main_bot))

    # -------------------------------------------------------------------
    # مدیریت ادمین‌ها
    # -------------------------------------------------------------------

    @router.callback_query(F.data == "adm_admins_menu")
    async def cb_admin_admins_menu(call: CallbackQuery):
        if not admin_only(call.from_user.id):
            return await call.answer()
        await call.message.edit_text("👤 مدیریت ادمین‌ها:", reply_markup=kb.admin_admins_menu_kb())
        await call.answer()

    @router.callback_query(F.data == "adm_admins_list")
    async def cb_admin_admins_list(call: CallbackQuery):
        admins = db.list_admins()
        text = "لیست ادمین‌ها:\n" + "\n".join([f"- `{a}`" for a in admins])
        await call.message.edit_text(text, parse_mode="Markdown", reply_markup=kb.admin_back_kb("adm_admins_menu"))
        await call.answer()

    @router.callback_query(F.data == "adm_admin_add")
    async def cb_admin_admin_add(call: CallbackQuery, state: FSMContext):
        if not admin_only(call.from_user.id):
            return await call.answer()
        await state.set_state(AdminAddAdmin.waiting_id)
        await call.message.edit_text(
            "آیدی عددی کاربر جدید برای افزودن به ادمین‌ها را ارسال کنید:", reply_markup=kb.admin_back_kb("adm_admins_menu")
        )
        await call.answer()

    @router.message(AdminAddAdmin.waiting_id)
    async def process_add_admin(message: Message, state: FSMContext):
        if not message.text.strip().isdigit():
            await message.answer("لطفاً فقط آیدی عددی ارسال کنید.")
            return
        db.add_admin(int(message.text.strip()))
        await state.clear()
        await message.answer("✅ ادمین جدید اضافه شد.", reply_markup=kb.admin_panel_kb(db, is_main_bot))

    @router.callback_query(F.data == "adm_admin_remove")
    async def cb_admin_admin_remove(call: CallbackQuery, state: FSMContext):
        if not admin_only(call.from_user.id):
            return await call.answer()
        await state.set_state(AdminRemoveAdmin.waiting_id)
        await call.message.edit_text(
            "آیدی عددی ادمینی که باید حذف شود را ارسال کنید:", reply_markup=kb.admin_back_kb("adm_admins_menu")
        )
        await call.answer()

    @router.message(AdminRemoveAdmin.waiting_id)
    async def process_remove_admin(message: Message, state: FSMContext):
        if not message.text.strip().isdigit():
            await message.answer("لطفاً فقط آیدی عددی ارسال کنید.")
            return
        ok = db.remove_admin(int(message.text.strip()))
        await state.clear()
        if ok:
            await message.answer("✅ ادمین حذف شد.", reply_markup=kb.admin_panel_kb(db, is_main_bot))
        else:
            await message.answer("⛔️ این ادمین قابل حذف نیست.", reply_markup=kb.admin_panel_kb(db, is_main_bot))

    # -------------------------------------------------------------------
    # پیام همگانی
    # -------------------------------------------------------------------

    @router.callback_query(F.data == "adm_broadcast")
    async def cb_admin_broadcast(call: CallbackQuery, state: FSMContext):
        if not admin_only(call.from_user.id):
            return await call.answer()
        await state.set_state(AdminBroadcast.waiting_message)
        await call.message.edit_text("متن پیام همگانی را ارسال کنید (برای همه کاربران ارسال می‌شود):", reply_markup=kb.admin_back_kb())
        await call.answer()

    @router.message(AdminBroadcast.waiting_message)
    async def process_broadcast(message: Message, state: FSMContext, bot: Bot):
        user_ids = db.get_all_user_ids()
        success, failed = 0, 0
        for uid in user_ids:
            try:
                await message.copy_to(uid)
                success += 1
            except Exception:
                failed += 1
        await state.clear()
        await message.answer(
            f"📢 پیام همگانی ارسال شد.\n✅ موفق: {success}\n❌ ناموفق: {failed}", reply_markup=kb.admin_panel_kb(db, is_main_bot)
        )

    # -------------------------------------------------------------------
    # پاسخ به پیام پشتیبانی کاربر
    # -------------------------------------------------------------------

    @router.callback_query(F.data.startswith("reply_user:"))
    async def cb_reply_user(call: CallbackQuery, state: FSMContext):
        user_id = int(call.data.split(":")[1])
        await state.update_data(reply_to_user=user_id)
        await state.set_state(AdminReplyFlow.waiting_reply)
        await call.message.answer(f"متن پاسخ برای کاربر {user_id} را ارسال کنید:")
        await call.answer()

    @router.message(AdminReplyFlow.waiting_reply)
    async def process_reply_to_user(message: Message, state: FSMContext, bot: Bot):
        data = await state.get_data()
        user_id = data.get("reply_to_user")
        if not user_id:
            await state.clear()
            return
        try:
            await bot.send_message(user_id, f"📩 پاسخ پشتیبانی:\n\n{message.text}")
            await message.answer("✅ پاسخ ارسال شد.", reply_markup=kb.admin_panel_kb(db, is_main_bot))
        except Exception:
            await message.answer("⛔️ ارسال پیام به کاربر با خطا مواجه شد.", reply_markup=kb.admin_panel_kb(db, is_main_bot))
        await state.clear()

    # -------------------------------------------------------------------
    # آمار فروش
    # -------------------------------------------------------------------

    @router.callback_query(F.data == "adm_stats")
    async def cb_admin_stats(call: CallbackQuery):
        if not admin_only(call.from_user.id):
            return await call.answer()
        stats = db.get_stats()
        text = (
            "📊 آمار فروشگاه:\n\n"
            f"👥 تعداد کاربران: {stats['users']}\n"
            f"⏳ سفارش‌های در انتظار: {stats['pending']}\n"
            f"✅ سفارش‌های تایید شده: {stats['approved']}\n"
            f"❌ سفارش‌های رد شده: {stats['rejected']}\n"
            f"💰 مجموع فروش: {stats['revenue']:,} تومان"
        )
        await call.message.edit_text(text, reply_markup=kb.admin_back_kb())
        await call.answer()

    # -------------------------------------------------------------------
    # دستور متنی برای دسترسی سریع
    # -------------------------------------------------------------------

    @router.message(Command("admin"))
    async def cmd_admin(message: Message, state: FSMContext):
        if not admin_only(message.from_user.id):
            return
        await state.clear()
        await message.answer("🔧 پنل مدیریت:", reply_markup=kb.admin_panel_kb(db, is_main_bot))

    return router
