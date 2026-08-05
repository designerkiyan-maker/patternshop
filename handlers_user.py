# -*- coding: utf-8 -*-
"""
هندلرهای مربوط به کاربر عادی
"""

from aiogram import Router, F, Bot
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

import database as db
import keyboards as kb
from states import BuyFlow, ContactFlow
from config import MAX_TEST_PER_USER

router = Router()


# ---------------------------------------------------------------------------
# شروع
# ---------------------------------------------------------------------------

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    db.add_or_update_user(
        message.from_user.id, message.from_user.username or "", message.from_user.first_name or ""
    )
    welcome = db.get_setting("welcome_text")
    await message.answer(welcome, reply_markup=kb.main_menu_kb(db.is_admin(message.from_user.id)))


def _is_button(message: Message, key: str) -> bool:
    return message.text == db.get_setting(key)


# ---------------------------------------------------------------------------
# خرید کانفیگ
# ---------------------------------------------------------------------------

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
    await call.message.edit_text("یک محصول را انتخاب کنید:", reply_markup=kb.products_kb(products, cat_id))
    await call.answer()


@router.callback_query(F.data.startswith("prod:"))
async def cb_product(call: CallbackQuery):
    product_id = int(call.data.split(":")[1])
    product = db.get_product(product_id)
    if not product:
        await call.answer("محصول یافت نشد.", show_alert=True)
        return
    stock = db.count_available_configs(product_id)
    text = (
        f"📦 {product['name']}\n"
        f"💰 قیمت: {product['price']:,} تومان\n"
        f"📝 توضیحات: {product['description'] or '---'}\n"
        f"📊 موجودی: {stock} عدد\n"
    )
    if stock <= 0:
        text += "\n⛔️ در حال حاضر موجودی این محصول تمام شده است."
        await call.message.edit_text(text)
        await call.answer()
        return
    await call.message.edit_text(text, reply_markup=kb.product_confirm_kb(product_id))
    await call.answer()


@router.callback_query(F.data.startswith("buy_confirm:"))
async def cb_buy_confirm(call: CallbackQuery, state: FSMContext):
    product_id = int(call.data.split(":")[1])
    product = db.get_product(product_id)
    if not product or db.count_available_configs(product_id) <= 0:
        await call.answer("این محصول در حال حاضر موجود نیست.", show_alert=True)
        return

    order_id = db.create_order(call.from_user.id, product_id)
    await state.update_data(order_id=order_id)
    await state.set_state(BuyFlow.waiting_receipt)

    card_number = db.get_setting("card_number")
    card_holder = db.get_setting("card_holder")
    after_buy_text = db.get_setting("after_buy_text")

    text = (
        f"{after_buy_text}\n\n"
        f"💳 شماره کارت: `{card_number}`\n"
        f"👤 به نام: {card_holder}\n"
        f"💰 مبلغ: {product['price']:,} تومان\n\n"
        f"لطفاً عکس رسید پرداخت را همینجا ارسال کنید."
    )
    await call.message.edit_text(text, parse_mode="Markdown", reply_markup=kb.cancel_kb())
    await call.answer()


@router.callback_query(F.data == "cancel_flow")
async def cb_cancel_flow(call: CallbackQuery, state: FSMContext):
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

    product = db.get_product(order["product_id"])
    user = message.from_user
    caption = (
        f"🧾 رسید جدید - سفارش #{order_id}\n"
        f"👤 کاربر: {user.first_name or ''} (@{user.username or '---'})\n"
        f"🆔 آیدی عددی: `{user.id}`\n"
        f"📦 محصول: {product['name']}\n"
        f"💰 مبلغ: {product['price']:,} تومان"
    )

    for admin_id in db.list_admins():
        try:
            sent = await bot.send_photo(
                admin_id,
                file_id,
                caption=caption,
                parse_mode="Markdown",
                reply_markup=kb.order_review_kb(order_id),
            )
            db.set_order_admin_message(order_id, admin_id, sent.message_id)
        except Exception:
            pass

    await message.answer(
        "✅ رسید شما برای بررسی ارسال شد. پس از تایید ادمین، کانفیگ برای شما ارسال خواهد شد.",
        reply_markup=kb.main_menu_kb(db.is_admin(user.id)),
    )
    await state.clear()


@router.message(BuyFlow.waiting_receipt)
async def receipt_wrong_type(message: Message):
    await message.answer("لطفاً فقط عکس رسید پرداخت را ارسال کنید.")


# ---------------------------------------------------------------------------
# کانفیگ تست
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# سفارش‌های من
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# ارتباط با پشتیبانی
# ---------------------------------------------------------------------------

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
    await message.answer("پیام شما برای پشتیبانی ارسال شد. به زودی پاسخ داده می‌شود.", reply_markup=kb.main_menu_kb(db.is_admin(user.id)))
    await state.clear()
