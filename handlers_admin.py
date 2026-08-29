# -*- coding: utf-8 -*-
"""
هندلرهای پنل مدیریت بات فروش الگوی خیاطی

مثل handlers_user.py یک تابع کارخانه‌ای دارد: create_admin_router(db) که همه‌ی
هندلرهای مدیریتی (محصولات و فایل‌های الگو، سفارش‌ها، مالی، ظاهر و ...) را روی
یک روتر جمع می‌کند.
"""

import os
import asyncio
from datetime import date, timedelta
import tempfile
import logging

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command
from aiogram.exceptions import TelegramBadRequest

import config
import keyboards as kb
from database import MENU_BUTTON_META
from file_delivery import deliver_pattern_to_user
from jalali import to_jalali_str
from backup import create_backup, restore_backup, is_valid_sqlite_db
from states import (
    AdminAddCategory,
    AdminAddProduct,
    AdminProductFiles,
    AdminProductPreview,
    AdminSampleFiles,
    AdminResetSample,
    AdminForceJoin,
    AdminEditButton,
    AdminSetCard,
    AdminBroadcast,
    AdminAddAdmin,
    AdminRemoveAdmin,
    AdminChangeRole,
    AdminEditWelcome,
    AdminReplyFlow,
    AdminCreateDiscount,
    AdminReferralPercent,
    AdminReferralCommissionMax,
    AdminReferralFreeConfigThreshold,
    AdminReferralInviteBonusAmount,
    AdminReferralInviteBonusMax,
    AdminWheelSettings,
    AdminRestoreBackup,
)

logger = logging.getLogger(__name__)


def create_admin_router(db) -> Router:
    router = Router()

    def admin_only(user_id: int) -> bool:
        return db.is_admin(user_id)

    def full_admin_only(user_id: int) -> bool:
        """دسترسی کامل: مالک، مدیر یا ادمین میانی. ادمین با نقش «پشتیبان» اجازه‌ی این اقدامات
        (تنظیمات، مالی، مدیریت محصولات/موجودی) را ندارد."""
        return db.is_full_admin(user_id)

    def senior_admin_only(user_id: int) -> bool:
        """فقط مالک یا مدیر کامل؛ ادمین میانی و پشتیبان اجازه‌ی این بخش‌های حساس
        (آمار فروش، تنظیمات کمپین‌ها/تخفیف، برندینگ، مدیریت محصولات/دسته‌بندی‌ها/
        فایل‌های الگو) را ندارند."""
        return db.is_senior_admin(user_id)

    async def _notify_user_inline_menu(bot: Bot, user_tg_id: int):
        """بعد از این‌که مدیر یک اقدام را روی سفارش/شارژ/درخواست کاربر انجام می‌دهد
        (تایید، رد و ...) و پیامی برای کاربر ارسال می‌شود، اگر منوی شیشه‌ای بالا از
        تنظیمات فعال باشد، دوباره برایش ارسال می‌شود؛ وگرنه بعد از این پیام‌های جدید
        از دسترس کاربر خارج می‌ماند (چون به پیام قبلی‌اش چسبیده بود، نه به چت)."""
        try:
            inline_kb = (await asyncio.to_thread(kb.inline_menu_for_user, db, user_tg_id))
            if inline_kb is not None:
                await bot.send_message(user_tg_id, "📋 منو:", reply_markup=inline_kb)
        except Exception:
            pass

    async def _send_receipt(bot: Bot, chat_id: int, file_id: str, receipt_type: str, caption: str, reply_markup=None):
        """ارسال رسید ذخیره‌شده؛ رسیدهای قدیمی photo فرض می‌شوند."""
        if (receipt_type or "photo") == "document":
            return await bot.send_document(chat_id, file_id, caption=caption, reply_markup=reply_markup)
        return await bot.send_photo(chat_id, file_id, caption=caption, reply_markup=reply_markup)

    def owner_only(user_id: int) -> bool:
        """فقط مالک اصلی بات (تعیین‌شده در env)؛ برای مدیریت خود ادمین‌ها."""
        return db.is_owner(user_id)

    async def deny_support(call: CallbackQuery):
        await call.answer("⛔️ این بخش فقط برای مدیران کامل در دسترس است.", show_alert=True)

    async def deny_mid(call: CallbackQuery):
        await call.answer("⛔️ این بخش فقط برای مالک و مدیر کامل در دسترس است.", show_alert=True)

    async def safe_edit(call: CallbackQuery, text: str, reply_markup=None, parse_mode=None) -> bool:
        """ویرایش امن پیام؛ خطای message is not modified نباید کل callback را خراب کند."""
        try:
            kwargs = {"reply_markup": reply_markup}
            if parse_mode is not None:
                kwargs["parse_mode"] = parse_mode
            await call.message.edit_text(text, **kwargs)
            return True
        except TelegramBadRequest as exc:
            error = str(exc).lower()
            if any(phrase in error for phrase in (
                "message is not modified",
                "message can't be edited",
                "message to edit not found",
            )):
                return False
            raise

    async def replace_admin_view(call: CallbackQuery, text: str, reply_markup=None, parse_mode=None) -> bool:
        """تغییر منوی ادمین روی همان پیام؛ بدون حذف/ارسال مجدد پیام."""
        if call.message is None:
            return False

        kwargs = {"reply_markup": reply_markup}
        if parse_mode is not None:
            kwargs["parse_mode"] = parse_mode

        try:
            await call.message.edit_text(text, **kwargs)
            return True
        except TelegramBadRequest as exc:
            error = str(exc).lower()
            if any(phrase in error for phrase in (
                "message is not modified",
                "message can't be edited",
                "message to edit not found",
            )):
                return False
            raise

    def callback_id(data: str, prefix: str):
        """استخراج امن ID از callback_data و بررسی پیشوند."""
        try:
            parts = (data or "").split(":", 1)
            if len(parts) != 2 or parts[0] != prefix:
                return None
            value = parts[1]
            if not value.isdigit():
                return None
            return int(value)
        except (IndexError, AttributeError, ValueError):
            return None

    # -------------------------------------------------------------------
    # ورود به پنل
    # -------------------------------------------------------------------

    @router.message(F.text.func(lambda t: t == db.get_setting("btn_admin_panel")))
    async def open_admin_panel(message: Message, state: FSMContext):
        if not admin_only(message.from_user.id):
            return
        await state.clear()
        await message.answer("🔧 پنل مدیریت:", reply_markup=kb.admin_panel_kb(db))

    @router.callback_query(F.data == "adm_back_panel")
    async def cb_back_panel(call: CallbackQuery, state: FSMContext):
        if not admin_only(call.from_user.id):
            return await call.answer()
        await state.clear()
        await replace_admin_view(call, "🔧 پنل مدیریت:", reply_markup=kb.admin_panel_kb(db))
        await call.answer()

    @router.callback_query(F.data == "noop")
    async def cb_noop(call: CallbackQuery):
        await call.answer()

    @router.callback_query(F.data.startswith("adm_cat:"))
    async def cb_admin_category(call: CallbackQuery, state: FSMContext):
        if not admin_only(call.from_user.id):
            return await call.answer()
        await state.clear()
        cat_key = call.data.split(":", 1)[1]
        title = kb.admin_category_label(cat_key)
        await replace_admin_view(call, f"{title}:", reply_markup=kb.admin_category_kb(db, cat_key))
        await call.answer()

    # -------------------------------------------------------------------
    # مدیریت دسته‌بندی‌ها
    # -------------------------------------------------------------------

    @router.callback_query(F.data == "adm_categories")
    async def cb_admin_categories(call: CallbackQuery):
        if not senior_admin_only(call.from_user.id):
            return await deny_mid(call)
        try:
            categories = (await asyncio.to_thread(db.get_categories, active_only=False))
            await replace_admin_view(call, "📂 مدیریت دسته‌بندی‌ها:", kb.admin_categories_kb(categories))
            await call.answer()
        except Exception:
            await call.answer("⚠️ بارگذاری دسته‌بندی‌ها ناموفق بود. دوباره تلاش کنید.", show_alert=True)

    @router.callback_query(F.data.startswith("adm_cat_toggle:"))
    async def cb_admin_cat_toggle(call: CallbackQuery):
        if not senior_admin_only(call.from_user.id):
            return await deny_mid(call)
        cat_id = callback_id(call.data, "adm_cat_toggle")
        if cat_id is None:
            return await call.answer("⚠️ درخواست نامعتبر است.", show_alert=True)
        try:
            if (await asyncio.to_thread(db.get_category, cat_id)) is None:
                return await call.answer("⚠️ این دسته‌بندی دیگر وجود ندارد.", show_alert=True)
            (await asyncio.to_thread(db.toggle_category, cat_id))
            (await asyncio.to_thread(db.log_admin_action, call.from_user.id, "category_toggle", f"دسته‌بندی #{cat_id}"))
            categories = (await asyncio.to_thread(db.get_categories, active_only=False))
            await safe_edit(call, "📂 مدیریت دسته‌بندی‌ها:", kb.admin_categories_kb(categories))
            await call.answer("وضعیت تغییر کرد.")
        except Exception:
            await call.answer("⚠️ تغییر وضعیت دسته‌بندی ناموفق بود. دوباره تلاش کنید.", show_alert=True)

    @router.callback_query(F.data.startswith("adm_cat_del:"))
    async def cb_admin_cat_del(call: CallbackQuery):
        if not senior_admin_only(call.from_user.id):
            return await deny_mid(call)
        cat_id = callback_id(call.data, "adm_cat_del")
        if cat_id is None:
            return await call.answer("⚠️ درخواست نامعتبر است.", show_alert=True)
        try:
            if (await asyncio.to_thread(db.get_category, cat_id)) is None:
                return await call.answer("⚠️ این دسته‌بندی قبلاً حذف شده است.", show_alert=True)
            (await asyncio.to_thread(db.delete_category, cat_id))
            (await asyncio.to_thread(db.log_admin_action, call.from_user.id, "category_delete", f"دسته‌بندی #{cat_id}"))
            categories = (await asyncio.to_thread(db.get_categories, active_only=False))
            await safe_edit(call, "📂 مدیریت دسته‌بندی‌ها:", kb.admin_categories_kb(categories))
            await call.answer("دسته‌بندی حذف شد.")
        except Exception:
            await call.answer("⚠️ حذف دسته‌بندی ناموفق بود. دوباره تلاش کنید.", show_alert=True)

    @router.callback_query(F.data == "adm_cat_add")
    async def cb_admin_cat_add(call: CallbackQuery, state: FSMContext):
        if not senior_admin_only(call.from_user.id):
            return await deny_mid(call)
        await state.set_state(AdminAddCategory.waiting_name)
        await safe_edit(call, "نام دسته‌بندی جدید را ارسال کنید:", reply_markup=kb.admin_back_kb())
        await call.answer()

    @router.message(AdminAddCategory.waiting_name)
    async def process_add_category(message: Message, state: FSMContext):
        if not admin_only(message.from_user.id):
            return
        name = (message.text or "").strip()
        if not name:
            await message.answer("لطفاً نام دسته‌بندی را وارد کنید.")
            return
        if len(name) > 100:
            await message.answer("نام دسته‌بندی نباید بیشتر از ۱۰۰ کاراکتر باشد.")
            return
        try:
            (await asyncio.to_thread(db.add_category, name))
            (await asyncio.to_thread(db.log_admin_action, message.from_user.id, "category_add", f"دسته‌بندی «{name}»"))
            await state.clear()
            await message.answer("✅ دسته‌بندی اضافه شد.", reply_markup=kb.admin_category_kb(db, "products"))
        except Exception:
            await message.answer("⚠️ افزودن دسته‌بندی ناموفق بود. دوباره تلاش کنید.")

    # -------------------------------------------------------------------
    # مدیریت محصولات
    # -------------------------------------------------------------------

    @router.callback_query(F.data == "adm_products")
    async def cb_admin_products(call: CallbackQuery):
        if not senior_admin_only(call.from_user.id):
            return await deny_mid(call)
        categories = (await asyncio.to_thread(db.get_categories, active_only=False))
        await replace_admin_view(call, 
            "📦 مدیریت محصولات - ابتدا دسته‌بندی را انتخاب کنید:",
            reply_markup=kb.admin_products_categories_kb(categories),
        )
        await call.answer()

    @router.callback_query(F.data.startswith("adm_prod_cat:"))
    async def cb_admin_prod_cat(call: CallbackQuery):
        if not senior_admin_only(call.from_user.id):
            return await deny_mid(call)
        cat_id = callback_id(call.data, "adm_prod_cat")
        if cat_id is None:
            await call.answer("❌ درخواست نامعتبر است.", show_alert=True)
            return
        products = (await asyncio.to_thread(db.get_products, cat_id, active_only=False))
        if not products:
            await call.answer("محصولی در این دسته وجود ندارد.", show_alert=True)
            return
        await safe_edit(call, "لیست محصولات این دسته‌بندی:", reply_markup=kb.admin_products_list_kb(db, products))
        await call.answer()

    @router.callback_query(F.data.startswith("adm_prod_toggle:"))
    async def cb_admin_prod_toggle(call: CallbackQuery):
        if not senior_admin_only(call.from_user.id):
            return await deny_mid(call)
        product_id = callback_id(call.data, "adm_prod_toggle")
        if product_id is None:
            await call.answer("❌ درخواست نامعتبر است.", show_alert=True)
            return
        (await asyncio.to_thread(db.toggle_product, product_id))
        product = (await asyncio.to_thread(db.get_product, product_id))
        (await asyncio.to_thread(db.log_admin_action, call.from_user.id, "product_toggle", f"محصول «{product['name'] if product else product_id}»"))
        products = (await asyncio.to_thread(db.get_products, product["category_id"], active_only=False))
        await safe_edit(call, "لیست محصولات این دسته‌بندی:", reply_markup=kb.admin_products_list_kb(db, products))
        await call.answer("وضعیت تغییر کرد.")

    @router.callback_query(F.data.startswith("adm_prod_del:"))
    async def cb_admin_prod_del(call: CallbackQuery):
        if not senior_admin_only(call.from_user.id):
            return await deny_mid(call)
        product_id = callback_id(call.data, "adm_prod_del")
        if product_id is None:
            await call.answer("❌ درخواست نامعتبر است.", show_alert=True)
            return
        product = (await asyncio.to_thread(db.get_product, product_id))
        cat_id = product["category_id"] if product else None
        (await asyncio.to_thread(db.delete_product, product_id))
        (await asyncio.to_thread(db.log_admin_action, call.from_user.id, "product_delete", f"محصول «{product['name'] if product else product_id}»"))
        if cat_id:
            products = (await asyncio.to_thread(db.get_products, cat_id, active_only=False))
            await safe_edit(call, "لیست محصولات این دسته‌بندی:", reply_markup=kb.admin_products_list_kb(db, products))
        await call.answer("محصول حذف شد.")

    @router.callback_query(F.data == "adm_prod_add")
    async def cb_admin_prod_add(call: CallbackQuery, state: FSMContext):
        if not senior_admin_only(call.from_user.id):
            return await deny_mid(call)
        categories = (await asyncio.to_thread(db.get_categories, active_only=True))
        if not categories:
            await call.answer("ابتدا باید حداقل یک دسته‌بندی فعال بسازید.", show_alert=True)
            return
        await state.set_state(AdminAddProduct.waiting_category)
        await safe_edit(call, 
            "محصول جدید در کدام دسته‌بندی اضافه شود؟",
            reply_markup=kb.admin_pick_category_kb(categories, "adm_newprod_cat"),
        )
        await call.answer()

    @router.callback_query(AdminAddProduct.waiting_category, F.data.startswith("adm_newprod_cat:"))
    async def cb_pick_category_for_new_product(call: CallbackQuery, state: FSMContext):
        cat_id = callback_id(call.data, "adm_newprod_cat")
        if cat_id is None:
            await call.answer("❌ درخواست نامعتبر است.", show_alert=True)
            return
        await state.update_data(category_id=cat_id)
        await state.set_state(AdminAddProduct.waiting_name)
        await safe_edit(call, "نام محصول را ارسال کنید:", reply_markup=kb.admin_back_kb())
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
        await state.set_state(AdminAddProduct.waiting_preview)
        await message.answer("🖼 یک عکس برای پیش‌نمایش بفرست، یا /skip")

    @router.message(AdminAddProduct.waiting_preview, F.photo)
    async def process_product_preview_photo(message: Message, state: FSMContext):
        if not admin_only(message.from_user.id):
            return
        await state.update_data(preview_file_id=message.photo[-1].file_id)
        await state.set_state(AdminAddProduct.waiting_files)
        await state.update_data(files=[])
        await message.answer(
            "✅ عکس پیش‌نمایش ثبت شد.\n\n"
            "حالا فایل‌های الگو (PDF و مشابه) را بفرست. می‌توانی چند فایل پشت‌سرهم بفرستی؛ "
            "بعد از پایان، دکمه‌ی «✅ تمام شد» را بزن:",
            reply_markup=kb.files_upload_done_kb(),
        )

    @router.message(AdminAddProduct.waiting_preview, Command("skip"))
    async def process_product_preview_skip(message: Message, state: FSMContext):
        if not admin_only(message.from_user.id):
            return
        await state.update_data(preview_file_id="")
        await state.set_state(AdminAddProduct.waiting_files)
        await state.update_data(files=[])
        await message.answer(
            "عکس پیش‌نمایش رد شد.\n\n"
            "حالا فایل‌های الگو (PDF و مشابه) را بفرست. می‌توانی چند فایل پشت‌سرهم بفرستی؛ "
            "بعد از پایان، دکمه‌ی «✅ تمام شد» را بزن:",
            reply_markup=kb.files_upload_done_kb(),
        )

    @router.message(AdminAddProduct.waiting_preview)
    async def process_product_preview_wrong_type(message: Message):
        if not admin_only(message.from_user.id):
            return
        await message.answer("لطفاً یک عکس بفرست، یا برای رد شدن /skip را بزن.")

    @router.message(AdminAddProduct.waiting_files, F.document)
    async def process_new_product_files_upload(message: Message, state: FSMContext):
        if not admin_only(message.from_user.id):
            return
        data = await state.get_data()
        files = list(data.get("files") or [])
        files.append(message.document.file_id)
        await state.update_data(files=files)
        await message.answer(f"📎 فایل {len(files)} ثبت شد. بعد از پایان، «✅ تمام شد» را بزن.")

    @router.message(AdminAddProduct.waiting_files)
    async def process_new_product_files_wrong_type(message: Message):
        if not admin_only(message.from_user.id):
            return
        await message.answer("لطفاً فایل الگو را به‌صورت Document بفرست (نه متن یا عکس).")

    @router.callback_query(AdminAddProduct.waiting_files, F.data == "adm_files_done")
    async def cb_admin_add_product_done(call: CallbackQuery, state: FSMContext):
        if not senior_admin_only(call.from_user.id):
            return await deny_mid(call)
        data = await state.get_data()
        files = [f for f in (data.get("files") or []) if f]
        if not files:
            await call.answer("⛔️ حداقل یک فایل الگو لازم است؛ اول فایل بفرست.", show_alert=True)
            return
        product_id = (await asyncio.to_thread(db.add_product, 
            data["category_id"], data["name"], data["price"], data.get("description", ""), data.get("preview_file_id", ""),
        ))
        added, duplicates = (await asyncio.to_thread(db.add_product_files, product_id, files))
        (await asyncio.to_thread(db.log_admin_action, 
            call.from_user.id, "product_add",
            f"محصول «{data['name']}» | قیمت: {data['price']:,} | {added} فایل الگو",
        ))
        await state.clear()
        text = f"✅ محصول «{data['name']}» با {added} فایل الگو ساخته شد."
        if duplicates:
            text += f"\n⚠️ {duplicates} فایل تکراری نادیده گرفته شد."
        await safe_edit(call, text, reply_markup=kb.admin_category_kb(db, "products"))
        await call.answer("محصول اضافه شد.")

    # -------------------------------------------------------------------
    # مدیریت فایل‌های الگو (پیش‌تر: بانک لینک)
    # -------------------------------------------------------------------

    def _product_files_title(product) -> str:
        return f"📎 فایل‌های الگوی محصول «{product['name']}»"

    @router.callback_query(F.data == "adm_product_files")
    async def cb_admin_product_files(call: CallbackQuery):
        if not senior_admin_only(call.from_user.id):
            return await deny_mid(call)
        products = (await asyncio.to_thread(db.get_all_products))
        if not products:
            await call.answer("ابتدا باید یک محصول بسازید.", show_alert=True)
            return
        await replace_admin_view(call, 
            "📎 مدیریت فایل‌های الگو - محصول را انتخاب کنید:",
            reply_markup=kb.product_files_pick_kb(products),
        )
        await call.answer()

    @router.callback_query(F.data.startswith("adm_file_pick:"))
    async def cb_admin_file_pick(call: CallbackQuery, state: FSMContext):
        if not senior_admin_only(call.from_user.id):
            return await deny_mid(call)
        product_id = callback_id(call.data, "adm_file_pick")
        if product_id is None:
            await call.answer("❌ درخواست نامعتبر است.", show_alert=True)
            return
        product = (await asyncio.to_thread(db.get_product, product_id))
        if not product:
            await call.answer("این محصول حذف شده است.", show_alert=True)
            return
        await state.clear()
        await replace_admin_view(call, _product_files_title(product), reply_markup=kb.product_files_kb(db, product_id))
        await call.answer()

    @router.callback_query(F.data.startswith("adm_file_del:"))
    async def cb_admin_file_del(call: CallbackQuery, state: FSMContext):
        if not senior_admin_only(call.from_user.id):
            return await deny_mid(call)
        parts = (call.data or "").split(":")
        if len(parts) != 3 or not parts[1].isdigit() or not parts[2].isdigit():
            await call.answer("❌ درخواست نامعتبر است.", show_alert=True)
            return
        record_id, product_id = int(parts[1]), int(parts[2])
        product = (await asyncio.to_thread(db.get_product, product_id))
        if not product:
            await call.answer("این محصول حذف شده است.", show_alert=True)
            return
        # callback_data فقط شناسه‌ی رکورد را جا می‌دهد؛ حذف در دیتابیس با file_id
        # انجام می‌شود، پس اول رکورد را پیدا و file_id واقعی‌اش را استخراج می‌کنیم.
        files = (await asyncio.to_thread(db.get_product_files, product_id))
        target = next((f for f in files if f["id"] == record_id), None)
        if not target:
            await call.answer("این فایل قبلاً حذف شده است.", show_alert=True)
            return
        (await asyncio.to_thread(db.delete_product_file, target["file_id"]))
        (await asyncio.to_thread(db.log_admin_action, 
            call.from_user.id, "product_file_delete",
            f"محصول «{product['name']}» | فایل #{record_id}",
        ))
        await safe_edit(call, _product_files_title(product), reply_markup=kb.product_files_kb(db, product_id))
        await call.answer("فایل حذف شد.")

    @router.callback_query(F.data.startswith("adm_file_add:"))
    async def cb_admin_file_add(call: CallbackQuery, state: FSMContext):
        if not senior_admin_only(call.from_user.id):
            return await deny_mid(call)
        product_id = callback_id(call.data, "adm_file_add")
        if product_id is None:
            await call.answer("❌ درخواست نامعتبر است.", show_alert=True)
            return
        product = (await asyncio.to_thread(db.get_product, product_id))
        if not product:
            await call.answer("این محصول حذف شده است.", show_alert=True)
            return
        await state.update_data(files_product_id=product_id, files=[])
        await state.set_state(AdminProductFiles.waiting_files)
        await safe_edit(call, 
            f"فایل‌های الگوی محصول «{product['name']}» را بفرست (PDF و مشابه).\n"
            "می‌توانی چند فایل پشت‌سرهم بفرستی؛ بعد از پایان، دکمه‌ی «✅ تمام شد» را بزن:",
            reply_markup=kb.files_upload_done_kb(),
        )
        await call.answer()

    @router.message(AdminProductFiles.waiting_files, F.document)
    async def process_product_files_upload(message: Message, state: FSMContext):
        if not admin_only(message.from_user.id):
            return
        data = await state.get_data()
        files = list(data.get("files") or [])
        files.append(message.document.file_id)
        await state.update_data(files=files)
        await message.answer(f"📎 فایل {len(files)} ثبت شد. بعد از پایان، «✅ تمام شد» را بزن.")

    @router.message(AdminProductFiles.waiting_files)
    async def process_product_files_wrong_type(message: Message):
        if not admin_only(message.from_user.id):
            return
        await message.answer("لطفاً فایل الگو را به‌صورت Document بفرست (نه متن یا عکس).")

    @router.callback_query(AdminProductFiles.waiting_files, F.data == "adm_files_done")
    async def cb_admin_product_files_done(call: CallbackQuery, state: FSMContext):
        if not senior_admin_only(call.from_user.id):
            return await deny_mid(call)
        data = await state.get_data()
        product_id = data.get("files_product_id")
        files = [f for f in (data.get("files") or []) if f]
        if not product_id or not files:
            await call.answer("هیچ فایلی ثبت نشده است؛ ابتدا حداقل یک فایل بفرست.", show_alert=True)
            return
        product = (await asyncio.to_thread(db.get_product, product_id))
        if not product:
            await state.clear()
            await call.answer("این محصول حذف شده است.", show_alert=True)
            return
        added, duplicates = (await asyncio.to_thread(db.add_product_files, product_id, files))
        (await asyncio.to_thread(db.log_admin_action, 
            call.from_user.id, "product_files_add",
            f"محصول «{product['name']}» | {added} فایل جدید اضافه شد",
        ))
        await state.clear()
        text = _product_files_title(product) + f"\n\n✅ {added} فایل اضافه شد."
        if duplicates:
            text += f"\n⚠️ {duplicates} فایل تکراری نادیده گرفته شد."
        await replace_admin_view(call, text, reply_markup=kb.product_files_kb(db, product_id))
        await call.answer("فایل‌ها ذخیره شدند.")

    @router.callback_query(F.data.startswith("adm_preview_set:"))
    async def cb_admin_preview_set(call: CallbackQuery, state: FSMContext):
        if not senior_admin_only(call.from_user.id):
            return await deny_mid(call)
        product_id = callback_id(call.data, "adm_preview_set")
        if product_id is None:
            await call.answer("❌ درخواست نامعتبر است.", show_alert=True)
            return
        product = (await asyncio.to_thread(db.get_product, product_id))
        if not product:
            await call.answer("این محصول حذف شده است.", show_alert=True)
            return
        await state.update_data(preview_product_id=product_id)
        await state.set_state(AdminProductPreview.waiting_photo)
        await safe_edit(call, 
            f"🖼 عکس پیش‌نمایش محصول «{product['name']}» را به‌صورت عکس (Photo) بفرست:",
            reply_markup=kb.admin_back_kb(f"adm_file_pick:{product_id}"),
        )
        await call.answer()

    @router.message(AdminProductPreview.waiting_photo, F.photo)
    async def process_preview_photo(message: Message, state: FSMContext):
        if not admin_only(message.from_user.id):
            return
        data = await state.get_data()
        product_id = data.get("preview_product_id")
        if not product_id:
            await state.clear()
            return
        product = (await asyncio.to_thread(db.get_product, product_id))
        if not product:
            await state.clear()
            await message.answer("این محصول حذف شده است.")
            return
        (await asyncio.to_thread(db.edit_product, product_id, preview_file_id=message.photo[-1].file_id))
        (await asyncio.to_thread(db.log_admin_action, 
            message.from_user.id, "product_preview_set", f"محصول «{product['name']}»",
        ))
        await state.clear()
        await message.answer("✅ عکس پیش‌نمایش ذخیره شد.", reply_markup=kb.product_files_kb(db, product_id))

    @router.message(AdminProductPreview.waiting_photo)
    async def process_preview_wrong_type(message: Message):
        if not admin_only(message.from_user.id):
            return
        await message.answer("لطفاً عکس پیش‌نمایش را به‌صورت Photo بفرست (نه فایل یا متن).")

    # -------------------------------------------------------------------
    # الگوی نمونه رایگان (مخزن فایل‌های نمونه)
    # -------------------------------------------------------------------

    @router.callback_query(F.data == "adm_sample_menu")
    async def cb_admin_sample_menu(call: CallbackQuery):
        if not senior_admin_only(call.from_user.id):
            return await deny_mid(call)
        count = (await asyncio.to_thread(db.count_sample_files))
        await replace_admin_view(call, 
            f"🧪 الگوی نمونه رایگان:\n\nتعداد فایل‌های نمونه‌ی فعلی: {count}",
            reply_markup=kb.sample_menu_kb(db),
        )
        await call.answer()

    @router.callback_query(F.data == "adm_sample_add")
    async def cb_admin_sample_add(call: CallbackQuery, state: FSMContext):
        if not senior_admin_only(call.from_user.id):
            return await deny_mid(call)
        await state.update_data(sample_files=[])
        await state.set_state(AdminSampleFiles.waiting_files)
        await safe_edit(call, 
            "فایل الگوهای نمونه را بفرست (PDF و مشابه).\n"
            "می‌توانی چند فایل پشت‌سرهم بفرستی؛ بعد از پایان، دکمه‌ی «✅ تمام شد» را بزن:",
            reply_markup=kb.files_upload_done_kb(),
        )
        await call.answer()

    @router.message(AdminSampleFiles.waiting_files, F.document)
    async def process_sample_files_upload(message: Message, state: FSMContext):
        if not admin_only(message.from_user.id):
            return
        data = await state.get_data()
        files = list(data.get("sample_files") or [])
        files.append(message.document.file_id)
        await state.update_data(sample_files=files)
        await message.answer(f"📎 فایل {len(files)} ثبت شد. بعد از پایان، «✅ تمام شد» را بزن.")

    @router.message(AdminSampleFiles.waiting_files)
    async def process_sample_files_wrong_type(message: Message):
        if not admin_only(message.from_user.id):
            return
        await message.answer("لطفاً فایل نمونه را به‌صورت Document بفرست (نه متن یا عکس).")

    @router.callback_query(AdminSampleFiles.waiting_files, F.data == "adm_files_done")
    async def cb_admin_sample_files_done(call: CallbackQuery, state: FSMContext):
        if not senior_admin_only(call.from_user.id):
            return await deny_mid(call)
        data = await state.get_data()
        files = [f for f in (data.get("sample_files") or []) if f]
        if not files:
            await call.answer("هیچ فایلی ثبت نشده است؛ ابتدا حداقل یک فایل بفرست.", show_alert=True)
            return
        added, duplicates = (await asyncio.to_thread(db.add_sample_files, files))
        (await asyncio.to_thread(db.log_admin_action, 
            call.from_user.id, "sample_files_add", f"{added} فایل نمونه اضافه شد",
        ))
        await state.clear()
        count = (await asyncio.to_thread(db.count_sample_files))
        text = f"🧪 الگوی نمونه رایگان:\n\n✅ {added} فایل اضافه شد"
        text += f" ({duplicates} تکراری نادیده گرفته شد)." if duplicates else "."
        text += f"\nتعداد کل فایل‌های نمونه: {count}"
        await replace_admin_view(call, text, reply_markup=kb.sample_menu_kb(db))
        await call.answer("ذخیره شد.")

    @router.callback_query(F.data.startswith("adm_sample_del:"))
    async def cb_admin_sample_del(call: CallbackQuery, state: FSMContext):
        if not senior_admin_only(call.from_user.id):
            return await deny_mid(call)
        raw = call.data.split(":", 1)[1] if ":" in (call.data or "") else ""
        if not raw.isdigit():
            await call.answer("❌ درخواست نامعتبر است.", show_alert=True)
            return
        record_id = int(raw)
        # مثل فایل‌های محصول: callback شناسه‌ی رکورد را دارد؛ حذف با file_id انجام می‌شود.
        samples = (await asyncio.to_thread(db.get_sample_files))
        target = next((f for f in samples if f["id"] == record_id), None)
        if not target:
            await call.answer("این فایل قبلاً حذف شده است.", show_alert=True)
            return
        (await asyncio.to_thread(db.delete_sample_file, target["file_id"]))
        (await asyncio.to_thread(db.log_admin_action, 
            call.from_user.id, "sample_file_delete", f"فایل نمونه #{record_id}",
        ))
        await replace_admin_view(call, "🧪 الگوی نمونه رایگان:", reply_markup=kb.sample_menu_kb(db))
        await call.answer("فایل نمونه حذف شد.")

    @router.callback_query(F.data == "adm_sample_reset")
    async def cb_admin_sample_reset(call: CallbackQuery, state: FSMContext):
        if not senior_admin_only(call.from_user.id):
            return await deny_mid(call)
        await state.set_state(AdminResetSample.waiting_message)
        await safe_edit(call, 
            "🆔 آیدی عددی کاربری که می‌خواهی دوباره بتواند الگوی نمونه‌ی رایگان دریافت کند را بفرست:\n\n"
            "بعد از ثبت، او می‌تواند از منوی اصلی دوباره الگوی نمونه بگیرد.",
            reply_markup=kb.admin_back_kb(),
        )
        await call.answer()

    @router.message(AdminResetSample.waiting_message)
    async def process_reset_sample(message: Message, state: FSMContext, bot: Bot):
        if not senior_admin_only(message.from_user.id):
            return
        raw = (message.text or "").strip()
        if not raw.isdigit():
            await message.answer("لطفاً فقط آیدی عددی کاربر را ارسال کنید.")
            return
        target_id = int(raw)
        user = (await asyncio.to_thread(db.get_user, target_id))
        if not user:
            await message.answer("کاربری با این آیدی پیدا نشد (کاربر باید یک‌بار بات را استارت کرده باشد).")
            return
        (await asyncio.to_thread(db.reset_user_sample_usage, target_id))
        (await asyncio.to_thread(db.log_admin_action, 
            message.from_user.id, "reset_sample", f"بازنشانی دریافت الگوی نمونه برای کاربر {target_id}",
        ))
        await state.clear()
        try:
            await bot.send_message(
                target_id,
                "✅ دسترسی شما به الگوی نمونه‌ی رایگان دوباره فعال شد!\nاز منوی اصلی می‌توانی دریافتش کنی.",
            )
        except Exception:
            pass
        await message.answer(
            f"✅ دریافت الگوی نمونه برای کاربر {target_id} بازنشانی شد.",
            reply_markup=kb.sample_menu_kb(db),
        )

    @router.callback_query(F.data == "adm_files_done")
    async def cb_admin_files_done_fallback(call: CallbackQuery):
        """اگر به‌خاطر ری‌استارت بات هیچ‌کدام از جریان‌های آپلود فعال نبود، کلیک
        دکمه‌ی «✅ تمام شد» بی‌جواب نماند."""
        if not admin_only(call.from_user.id):
            return await call.answer()
        await call.answer("نشست آپلود فعالی پیدا نشد؛ دوباره از منوی مدیریت شروع کن.", show_alert=True)

    # -------------------------------------------------------------------
    # عضویت اجباری در کانال
    # -------------------------------------------------------------------

    @router.callback_query(F.data == "adm_forcejoin_menu")
    async def cb_admin_forcejoin_menu(call: CallbackQuery):
        if not full_admin_only(call.from_user.id):
            return await deny_support(call)
        await replace_admin_view(call, 
            "📢 عضویت اجباری در کانال:\n\n"
            "کاربران قبل از استفاده از بات باید عضو کانال شما باشند. "
            "دقت کن که ربات باید از قبل ادمین کانال شده باشد تا بتواند عضویت را بررسی کند.",
            reply_markup=kb.admin_forcejoin_menu_kb(db),
        )
        await call.answer()

    @router.callback_query(F.data == "adm_forcejoin_toggle")
    async def cb_admin_forcejoin_toggle(call: CallbackQuery):
        if not full_admin_only(call.from_user.id):
            return await deny_support(call)
        settings = (await asyncio.to_thread(db.get_force_join_settings))
        if not settings["enabled"] and not settings["channel"]:
            await call.answer("اول باید آیدی کانال را تنظیم کنی.", show_alert=True)
            return
        current = (await asyncio.to_thread(db.get_setting, "force_join_enabled", "0"))
        (await asyncio.to_thread(db.set_setting, "force_join_enabled", "0" if current == "1" else "1"))
        await safe_edit(call, "📢 عضویت اجباری در کانال:", reply_markup=kb.admin_forcejoin_menu_kb(db))
        await call.answer("وضعیت عضویت اجباری تغییر کرد.")

    @router.callback_query(F.data == "adm_forcejoin_set_channel")
    async def cb_admin_forcejoin_set_channel(call: CallbackQuery, state: FSMContext):
        if not full_admin_only(call.from_user.id):
            return await deny_support(call)
        await state.set_state(AdminForceJoin.waiting_channel)
        await safe_edit(call, 
            "آیدی عددی یا یوزرنیم کانال را ارسال کن.\n\n"
            "مثال: `@mychannel`\n\n"
            "⚠️ حتماً ربات باید از قبل به‌عنوان ادمین به کانال اضافه شده باشد؛ در غیر این صورت نمی‌تواند عضویت را بررسی کند.",
            reply_markup=kb.admin_back_kb("adm_forcejoin_menu"),
        )
        await call.answer()

    @router.message(AdminForceJoin.waiting_channel)
    async def process_forcejoin_channel(message: Message, state: FSMContext, bot: Bot):
        channel = (message.text or "").strip()
        if not channel:
            await message.answer("ورودی نامعتبر است. دوباره تلاش کن.")
            return
        if not channel.startswith("@") and not channel.startswith("-"):
            channel = "@" + channel

        try:
            chat = await bot.get_chat(channel)
            member = await bot.get_chat_member(channel, bot.id)
            if member.status not in ("administrator", "creator"):
                raise ValueError("bot is not admin")
        except Exception:
            await message.answer(
                "⛔️ نتوانستم به این کانال دسترسی پیدا کنم.\n"
                "مطمئن شو آیدی درست است و ربات از قبل به‌عنوان *ادمین* به کانال اضافه شده باشد.",
                reply_markup=kb.admin_back_kb("adm_forcejoin_menu"),
            )
            return

        (await asyncio.to_thread(db.set_setting, "force_join_channel", channel))
        await state.clear()
        await message.answer(
            f"✅ کانال «{chat.title}» ثبت شد. حالا می‌تونی از منوی قبلی عضویت اجباری رو فعال کنی.",
            reply_markup=kb.admin_forcejoin_menu_kb(db),
        )

    # -------------------------------------------------------------------
    # سفارش‌های در انتظار
    # -------------------------------------------------------------------

    @router.callback_query(F.data == "adm_pending_orders")
    async def cb_admin_pending_orders(call: CallbackQuery):
        if not admin_only(call.from_user.id):
            return await call.answer()
        orders = (await asyncio.to_thread(db.get_pending_orders))
        if not orders:
            await call.answer("سفارش در انتظاری وجود ندارد.", show_alert=True)
            return
        await replace_admin_view(call, "🧾 سفارش‌های در انتظار بررسی:", reply_markup=kb.pending_orders_kb(orders))
        await call.answer()

    @router.callback_query(F.data.startswith("view_order:"))
    async def cb_view_order(call: CallbackQuery, bot: Bot):
        if not admin_only(call.from_user.id):
            return await call.answer()
        order_id = callback_id(call.data, "view_order")
        if order_id is None:
            await call.answer("❌ درخواست نامعتبر است.", show_alert=True)
            return
        order = (await asyncio.to_thread(db.get_order, order_id))
        if not order:
            await call.answer("سفارش یافت نشد.", show_alert=True)
            return
        product = (await asyncio.to_thread(db.get_product, order["product_id"]))
        qty = order["quantity"] or 1
        caption = f"سفارش #{order_id}\nکاربر: {order['user_id']}\nمحصول: {product['name'] if product else '---'}"
        if qty > 1:
            caption += f" × {qty}"
        if order["receipt_file_id"]:
            await _send_receipt(
                bot, call.from_user.id, order["receipt_file_id"], (order["receipt_type"] if "receipt_type" in order.keys() else "photo"),
                caption, kb.order_review_kb(order_id)
            )
        else:
            await call.message.answer(caption, reply_markup=kb.order_review_kb(order_id))
        await call.answer()

    @router.callback_query(F.data.startswith("order_approve:"))
    async def cb_order_approve(call: CallbackQuery, bot: Bot):
        if not admin_only(call.from_user.id):
            return await call.answer()

        order_id = callback_id(call.data, "order_approve")
        if order_id is None:
            await call.answer("❌ درخواست نامعتبر است.", show_alert=True)
            return
        order = (await asyncio.to_thread(db.get_order, order_id))
        if not order:
            await call.answer("سفارش یافت نشد.", show_alert=True)
            return
        if order["status"] != "pending":
            await call.answer("این سفارش قبلاً بررسی شده است.", show_alert=True)
            return

        product = (await asyncio.to_thread(db.get_product, order["product_id"]))

        # فروش نامحدود است: برای تایید سفارش فقط باید حداقل یک فایل الگو برای
        # محصول آپلود شده باشد؛ همین فایل‌ها به خریدار تحویل داده می‌شوند.
        files = (await asyncio.to_thread(db.get_product_files, order["product_id"]))
        if not files:
            await call.answer("⛔️ هنوز فایلی برای این محصول آپلود نشده است.", show_alert=True)
            return

        (await asyncio.to_thread(db.approve_order, order_id, [f["id"] for f in files]))
        product_name = product["name"] if product else "---"
        (await asyncio.to_thread(db.log_admin_action, 
            call.from_user.id, "order_approve",
            f"سفارش #{order_id} | کاربر {order['user_id']} | محصول «{product_name}» | "
            f"مبلغ: {(order['final_price'] or (product['price'] if product else 0)):,}",
        ))

        reward_info = (await asyncio.to_thread(db.reward_referrer_if_first_purchase, 
            order["user_id"], order["final_price"] or (product["price"] if product else 0),
        ))
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
            await bot.send_message(order["user_id"], f"✅ خرید شما تایید شد!\n🧵 محصول: {product_name}")
            await deliver_pattern_to_user(
                bot,
                order["user_id"],
                product_name,
                [f["file_id"] for f in files],
                final_price=order["final_price"],
                order_id=order_id,
            )
            await _notify_user_inline_menu(bot, order["user_id"])
        except Exception:
            pass

        try:
            await call.message.edit_caption(caption=(call.message.caption or "") + "\n\n✅ تایید شد و فایل‌ها ارسال شد.")
        except Exception:
            try:
                await safe_edit(call, (call.message.text or "") + "\n\n✅ تایید شد و فایل‌ها ارسال شد.")
            except Exception:
                pass
        await call.answer("سفارش تایید و فایل‌ها برای کاربر ارسال شد.")

    @router.callback_query(F.data.startswith("order_reject:"))
    async def cb_order_reject(call: CallbackQuery, bot: Bot):
        if not admin_only(call.from_user.id):
            return await call.answer()

        order_id = callback_id(call.data, "order_reject")
        if order_id is None:
            await call.answer("❌ درخواست نامعتبر است.", show_alert=True)
            return
        order = (await asyncio.to_thread(db.get_order, order_id))
        if not order:
            await call.answer("سفارش یافت نشد.", show_alert=True)
            return
        if order["status"] != "pending":
            await call.answer("این سفارش قبلاً بررسی شده است.", show_alert=True)
            return

        (await asyncio.to_thread(db.reject_order, order_id))
        (await asyncio.to_thread(db.log_admin_action, 
            call.from_user.id, "order_reject",
            f"سفارش #{order_id} | کاربر {order['user_id']}",
        ))
        try:
            await bot.send_message(
                order["user_id"],
                "❌ متاسفانه رسید ارسالی شما تایید نشد. در صورت اشتباه لطفاً با پشتیبانی در ارتباط باشید.",
            )
            await _notify_user_inline_menu(bot, order["user_id"])
        except Exception:
            pass

        try:
            await call.message.edit_caption(caption=(call.message.caption or "") + "\n\n❌ رد شد.")
        except Exception:
            try:
                await safe_edit(call, (call.message.text or "") + "\n\n❌ رد شد.")
            except Exception:
                pass
        await call.answer("سفارش رد شد.")

    # -------------------------------------------------------------------
    # درخواست‌های شارژ کیف پول
    # -------------------------------------------------------------------

    @router.callback_query(F.data == "adm_pending_topups")
    async def cb_admin_pending_topups(call: CallbackQuery):
        if not full_admin_only(call.from_user.id):
            return await deny_support(call)
        topups = (await asyncio.to_thread(db.get_pending_topups))
        if not topups:
            await call.answer("درخواست شارژ در انتظاری وجود ندارد.", show_alert=True)
            return
        await replace_admin_view(call, "👛 درخواست‌های شارژ کیف پول در انتظار:", reply_markup=kb.pending_topups_kb(topups))
        await call.answer()

    @router.callback_query(F.data.startswith("view_topup:"))
    async def cb_view_topup(call: CallbackQuery, bot: Bot):
        if not full_admin_only(call.from_user.id):
            return await deny_support(call)
        topup_id = callback_id(call.data, "view_topup")
        if topup_id is None:
            await call.answer("❌ درخواست نامعتبر است.", show_alert=True)
            return
        topup = (await asyncio.to_thread(db.get_topup, topup_id))
        if not topup:
            await call.answer("درخواست یافت نشد.", show_alert=True)
            return
        caption = f"شارژ کیف پول #{topup_id}\nکاربر: {topup['user_id']}\nمبلغ: {topup['amount']:,} تومان"
        if topup["receipt_file_id"]:
            await _send_receipt(
                bot, call.from_user.id, topup["receipt_file_id"], (topup["receipt_type"] if "receipt_type" in topup.keys() else "photo"),
                caption, kb.topup_review_kb(topup_id)
            )
        else:
            await call.message.answer(caption, reply_markup=kb.topup_review_kb(topup_id))
        await call.answer()

    @router.callback_query(F.data.startswith("topup_approve:"))
    async def cb_topup_approve(call: CallbackQuery, bot: Bot):
        if not full_admin_only(call.from_user.id):
            return await deny_support(call)

        topup_id = callback_id(call.data, "topup_approve")
        if topup_id is None:
            await call.answer("❌ درخواست نامعتبر است.", show_alert=True)
            return
        topup = (await asyncio.to_thread(db.get_topup, topup_id))
        if not topup:
            await call.answer("درخواست یافت نشد.", show_alert=True)
            return
        if topup["status"] != "pending":
            await call.answer("این درخواست قبلاً بررسی شده است.", show_alert=True)
            return

        (await asyncio.to_thread(db.approve_topup, topup_id))
        new_balance = (await asyncio.to_thread(db.get_wallet_credit, topup["user_id"]))
        (await asyncio.to_thread(db.log_admin_action, 
            call.from_user.id, "topup_approve",
            f"شارژ #{topup_id} | کاربر {topup['user_id']} | مبلغ: {topup['amount']:,} | موجودی جدید: {new_balance:,}",
        ))

        try:
            await bot.send_message(
                topup["user_id"],
                f"✅ شارژ کیف پول شما تایید شد!\n💰 مبلغ {topup['amount']:,} تومان اضافه شد.\n"
                f"👛 موجودی فعلی کیف پول شما: {new_balance:,} تومان",
            )
            await _notify_user_inline_menu(bot, topup["user_id"])
        except Exception:
            pass

        try:
            await call.message.edit_caption(caption=(call.message.caption or "") + "\n\n✅ تایید و شارژ شد.")
        except Exception:
            try:
                await safe_edit(call, (call.message.text or "") + "\n\n✅ تایید و شارژ شد.")
            except Exception:
                pass
        await call.answer("شارژ کیف پول تایید شد.")

    @router.callback_query(F.data.startswith("topup_reject:"))
    async def cb_topup_reject(call: CallbackQuery, bot: Bot):
        if not full_admin_only(call.from_user.id):
            return await deny_support(call)

        topup_id = callback_id(call.data, "topup_reject")
        if topup_id is None:
            await call.answer("❌ درخواست نامعتبر است.", show_alert=True)
            return
        topup = (await asyncio.to_thread(db.get_topup, topup_id))
        if not topup:
            await call.answer("درخواست یافت نشد.", show_alert=True)
            return
        if topup["status"] != "pending":
            await call.answer("این درخواست قبلاً بررسی شده است.", show_alert=True)
            return

        (await asyncio.to_thread(db.reject_topup, topup_id))
        (await asyncio.to_thread(db.log_admin_action, 
            call.from_user.id, "topup_reject",
            f"شارژ #{topup_id} | کاربر {topup['user_id']} | مبلغ: {topup['amount']:,}",
        ))
        try:
            await bot.send_message(
                topup["user_id"],
                "❌ متاسفانه درخواست شارژ کیف پول شما تایید نشد. در صورت اشتباه با پشتیبانی تماس بگیرید.",
            )
            await _notify_user_inline_menu(bot, topup["user_id"])
        except Exception:
            pass

        try:
            await call.message.edit_caption(caption=(call.message.caption or "") + "\n\n❌ رد شد.")
        except Exception:
            try:
                await safe_edit(call, (call.message.text or "") + "\n\n❌ رد شد.")
            except Exception:
                pass
        await call.answer("درخواست رد شد.")

    # -------------------------------------------------------------------
    # مدیریت کدهای تخفیف
    # -------------------------------------------------------------------

    @router.callback_query(F.data == "adm_discounts_menu")
    async def cb_admin_discounts_menu(call: CallbackQuery):
        if not senior_admin_only(call.from_user.id):
            return await deny_mid(call)
        codes = (await asyncio.to_thread(db.list_discount_codes))
        await replace_admin_view(call, "🎟 مدیریت کدهای تخفیف:", reply_markup=kb.discount_codes_kb(codes))
        await call.answer()

    @router.callback_query(F.data.startswith("adm_disc_toggle:"))
    async def cb_admin_disc_toggle(call: CallbackQuery):
        if not senior_admin_only(call.from_user.id):
            return await deny_mid(call)
        code_id = callback_id(call.data, "adm_disc_toggle")
        if code_id is None:
            await call.answer("❌ درخواست نامعتبر است.", show_alert=True)
            return
        (await asyncio.to_thread(db.toggle_discount_code, code_id))
        (await asyncio.to_thread(db.log_admin_action, call.from_user.id, "discount_toggle", f"کد تخفیف #{code_id}"))
        codes = (await asyncio.to_thread(db.list_discount_codes))
        await safe_edit(call, "🎟 مدیریت کدهای تخفیف:", reply_markup=kb.discount_codes_kb(codes))
        await call.answer("وضعیت تغییر کرد.")

    @router.callback_query(F.data.startswith("adm_disc_del:"))
    async def cb_admin_disc_del(call: CallbackQuery):
        if not senior_admin_only(call.from_user.id):
            return await deny_mid(call)
        code_id = callback_id(call.data, "adm_disc_del")
        if code_id is None:
            await call.answer("❌ درخواست نامعتبر است.", show_alert=True)
            return
        (await asyncio.to_thread(db.delete_discount_code, code_id))
        (await asyncio.to_thread(db.log_admin_action, call.from_user.id, "discount_delete", f"کد تخفیف #{code_id}"))
        codes = (await asyncio.to_thread(db.list_discount_codes))
        await safe_edit(call, "🎟 مدیریت کدهای تخفیف:", reply_markup=kb.discount_codes_kb(codes))
        await call.answer("کد حذف شد.")

    @router.callback_query(F.data == "adm_disc_add")
    async def cb_admin_disc_add(call: CallbackQuery, state: FSMContext):
        if not senior_admin_only(call.from_user.id):
            return await deny_mid(call)
        await state.set_state(AdminCreateDiscount.waiting_code)
        await safe_edit(call, 
            "نام کد تخفیف را ارسال کنید (مثلاً WELCOME20، بدون فاصله):", reply_markup=kb.admin_back_kb()
        )
        await call.answer()

    @router.message(AdminCreateDiscount.waiting_code)
    async def process_disc_code(message: Message, state: FSMContext):
        code = message.text.strip()
        if (await asyncio.to_thread(db.get_discount_code, code)):
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
        (await asyncio.to_thread(db.create_discount_code, 
            data["disc_code"], percent=data.get("disc_percent"), fixed_amount=data.get("disc_fixed"), max_uses=max_uses
        ))
        (await asyncio.to_thread(db.log_admin_action, message.from_user.id, "discount_add", f"کد «{data['disc_code']}»"))
        await state.clear()
        codes = (await asyncio.to_thread(db.list_discount_codes))
        await message.answer(f"✅ کد تخفیف «{data['disc_code']}» ساخته شد.", reply_markup=kb.discount_codes_kb(codes))

    # -------------------------------------------------------------------
    # تنظیمات زیرمجموعه‌گیری
    # -------------------------------------------------------------------

    @router.callback_query(F.data == "adm_referral_settings")
    async def cb_admin_referral_settings(call: CallbackQuery):
        if not senior_admin_only(call.from_user.id):
            return await deny_mid(call)
        await replace_admin_view(call, "🤝 تنظیمات زیرمجموعه‌گیری:", reply_markup=kb.referral_settings_kb(db))
        await call.answer()

    @router.callback_query(F.data == "adm_referral_toggle")
    async def cb_admin_referral_toggle(call: CallbackQuery):
        if not senior_admin_only(call.from_user.id):
            return await deny_mid(call)
        current = (await asyncio.to_thread(db.get_setting, "referral_enabled", "1"))
        (await asyncio.to_thread(db.set_setting, "referral_enabled", "0" if current == "1" else "1"))
        await safe_edit(call, "🤝 تنظیمات زیرمجموعه‌گیری:", reply_markup=kb.referral_settings_kb(db))
        await call.answer("وضعیت تغییر کرد.")

    @router.callback_query(F.data == "adm_referral_percent_edit")
    async def cb_admin_referral_percent_edit(call: CallbackQuery, state: FSMContext):
        if not senior_admin_only(call.from_user.id):
            return await deny_mid(call)
        await state.set_state(AdminReferralPercent.waiting_value)
        await safe_edit(call, 
            "درصد پورسانت جدید را وارد کنید (عددی بین 0 تا 100):", reply_markup=kb.admin_back_kb()
        )
        await call.answer()

    @router.message(AdminReferralPercent.waiting_value)
    async def process_referral_percent(message: Message, state: FSMContext):
        text = message.text.strip()
        if not text.isdigit() or not (0 <= int(text) <= 100):
            await message.answer("لطفاً یک عدد بین 0 تا 100 ارسال کنید.")
            return
        (await asyncio.to_thread(db.set_setting, "referral_percent", text))
        await state.clear()
        await message.answer(f"✅ درصد پورسانت زیرمجموعه‌گیری روی {text}٪ تنظیم شد.", reply_markup=kb.referral_settings_kb(db))

    @router.callback_query(F.data == "adm_referral_commission_max_edit")
    async def cb_admin_referral_commission_max_edit(call: CallbackQuery, state: FSMContext):
        if not senior_admin_only(call.from_user.id):
            return await deny_mid(call)
        await state.set_state(AdminReferralCommissionMax.waiting_value)
        await safe_edit(call,
            "حداکثر تعداد زیرمجموعه‌هایی که پورسانت خریدشان تعلق می‌گیرد را وارد کنید "
            "(برای نامحدود، عدد 0 را ارسال کنید):",
            reply_markup=kb.admin_back_kb(),
        )
        await call.answer()

    @router.message(AdminReferralCommissionMax.waiting_value)
    async def process_referral_commission_max(message: Message, state: FSMContext):
        text = message.text.strip()
        if not text.isdigit():
            await message.answer("لطفاً یک عدد صحیح (0 یا بیشتر) ارسال کنید.")
            return
        (await asyncio.to_thread(db.set_setting, "referral_commission_max_count", text))
        await state.clear()
        label = "نامحدود" if text == "0" else f"{text} نفر"
        await message.answer(f"✅ سقف تعداد نفرات پورسانت‌دار روی «{label}» تنظیم شد.", reply_markup=kb.referral_settings_kb(db))

    # --- حالت ۲: الگوی رایگان با تعداد دعوت مشخص ---

    @router.callback_query(F.data == "adm_referral_freeconfig_toggle")
    async def cb_admin_referral_freeconfig_toggle(call: CallbackQuery):
        if not senior_admin_only(call.from_user.id):
            return await deny_mid(call)
        current = (await asyncio.to_thread(db.get_setting, "referral_free_config_enabled", "0"))
        new_value = "0" if current == "1" else "1"
        if new_value == "1" and not (await asyncio.to_thread(db.get_setting, "referral_free_config_product_id", "")):
            await call.answer("ابتدا از «انتخاب محصول جایزه» یک محصول انتخاب کنید.", show_alert=True)
            return
        (await asyncio.to_thread(db.set_setting, "referral_free_config_enabled", new_value))
        await safe_edit(call, "🤝 تنظیمات زیرمجموعه‌گیری:", reply_markup=kb.referral_settings_kb(db))
        await call.answer("وضعیت تغییر کرد.")

    @router.callback_query(F.data == "adm_referral_freeconfig_threshold_edit")
    async def cb_admin_referral_freeconfig_threshold_edit(call: CallbackQuery, state: FSMContext):
        if not senior_admin_only(call.from_user.id):
            return await deny_mid(call)
        await state.set_state(AdminReferralFreeConfigThreshold.waiting_value)
        await safe_edit(call,
            "با دعوت چند نفر، یک الگوی رایگان تعلق بگیرد؟ عدد را وارد کنید:",
            reply_markup=kb.admin_back_kb(),
        )
        await call.answer()

    @router.message(AdminReferralFreeConfigThreshold.waiting_value)
    async def process_referral_freeconfig_threshold(message: Message, state: FSMContext):
        text = message.text.strip()
        if not text.isdigit() or int(text) < 1:
            await message.answer("لطفاً یک عدد صحیح بزرگ‌تر از صفر ارسال کنید.")
            return
        (await asyncio.to_thread(db.set_setting, "referral_free_config_threshold", text))
        await state.clear()
        await message.answer(f"✅ با دعوت {text} نفر، الگوی رایگان تعلق می‌گیرد.", reply_markup=kb.referral_settings_kb(db))

    @router.callback_query(F.data == "adm_referral_freeconfig_product")
    async def cb_admin_referral_freeconfig_product(call: CallbackQuery):
        if not senior_admin_only(call.from_user.id):
            return await deny_mid(call)
        await replace_admin_view(call, "📦 محصولی که به‌عنوان جایزه رایگان تحویل داده شود را انتخاب کنید:", reply_markup=kb.referral_freeconfig_product_kb(db))
        await call.answer()

    @router.callback_query(F.data.startswith("adm_referral_freeconfig_setprod:"))
    async def cb_admin_referral_freeconfig_setprod(call: CallbackQuery):
        if not senior_admin_only(call.from_user.id):
            return await deny_mid(call)
        product_id = call.data.split(":")[1]
        product = (await asyncio.to_thread(db.get_product, int(product_id)))
        if not product:
            await call.answer("این محصول یافت نشد.", show_alert=True)
            return
        (await asyncio.to_thread(db.set_setting, "referral_free_config_product_id", product_id))
        await safe_edit(call, "🤝 تنظیمات زیرمجموعه‌گیری:", reply_markup=kb.referral_settings_kb(db))
        if (await asyncio.to_thread(db.has_product_files, int(product_id))):
            await call.answer(f"✅ محصول «{product['name']}» به‌عنوان جایزه انتخاب شد.")
        else:
            await call.answer(
                f"✅ محصول «{product['name']}» به‌عنوان جایزه انتخاب شد.\n"
                "⚠️ برای این محصول هنوز فایلی آپلود نشده؛ تا آپلود فایل، تحویل جایزه ممکن نیست.",
                show_alert=True,
            )

    # --- حالت ۳: شارژ ثابت کیف پول به‌ازای هر دعوت ---

    @router.callback_query(F.data == "adm_referral_invitebonus_toggle")
    async def cb_admin_referral_invitebonus_toggle(call: CallbackQuery):
        if not senior_admin_only(call.from_user.id):
            return await deny_mid(call)
        current = (await asyncio.to_thread(db.get_setting, "referral_invite_bonus_enabled", "0"))
        new_value = "0" if current == "1" else "1"
        if new_value == "1" and int((await asyncio.to_thread(db.get_setting, "referral_invite_bonus_amount", "0")) or 0) <= 0:
            await call.answer("ابتدا مبلغ شارژ را از «تغییر مبلغ شارژ» تنظیم کنید.", show_alert=True)
            return
        (await asyncio.to_thread(db.set_setting, "referral_invite_bonus_enabled", new_value))
        await safe_edit(call, "🤝 تنظیمات زیرمجموعه‌گیری:", reply_markup=kb.referral_settings_kb(db))
        await call.answer("وضعیت تغییر کرد.")

    @router.callback_query(F.data == "adm_referral_invitebonus_amount_edit")
    async def cb_admin_referral_invitebonus_amount_edit(call: CallbackQuery, state: FSMContext):
        if not senior_admin_only(call.from_user.id):
            return await deny_mid(call)
        await state.set_state(AdminReferralInviteBonusAmount.waiting_value)
        await safe_edit(call,
            "مبلغ ثابتی که برای هر دعوت به کیف پول دعوت‌کننده اضافه شود را به تومان وارد کنید:",
            reply_markup=kb.admin_back_kb(),
        )
        await call.answer()

    @router.message(AdminReferralInviteBonusAmount.waiting_value)
    async def process_referral_invitebonus_amount(message: Message, state: FSMContext):
        text = message.text.strip()
        if not text.isdigit() or int(text) < 0:
            await message.answer("لطفاً یک عدد صحیح ارسال کنید.")
            return
        (await asyncio.to_thread(db.set_setting, "referral_invite_bonus_amount", text))
        await state.clear()
        await message.answer(f"✅ مبلغ شارژ به‌ازای هر دعوت روی {int(text):,} تومان تنظیم شد.", reply_markup=kb.referral_settings_kb(db))

    @router.callback_query(F.data == "adm_referral_invitebonus_max_edit")
    async def cb_admin_referral_invitebonus_max_edit(call: CallbackQuery, state: FSMContext):
        if not senior_admin_only(call.from_user.id):
            return await deny_mid(call)
        await state.set_state(AdminReferralInviteBonusMax.waiting_value)
        await safe_edit(call,
            "این شارژ فقط برای چند نفر اول دعوت‌شده اعمال شود؟ عدد را وارد کنید "
            "(برای نامحدود، عدد 0 را ارسال کنید):",
            reply_markup=kb.admin_back_kb(),
        )
        await call.answer()

    @router.message(AdminReferralInviteBonusMax.waiting_value)
    async def process_referral_invitebonus_max(message: Message, state: FSMContext):
        text = message.text.strip()
        if not text.isdigit():
            await message.answer("لطفاً یک عدد صحیح (0 یا بیشتر) ارسال کنید.")
            return
        (await asyncio.to_thread(db.set_setting, "referral_invite_bonus_max_count", text))
        await state.clear()
        label = "نامحدود" if text == "0" else f"{text} نفر"
        await message.answer(f"✅ سقف تعداد نفرات شارژ به‌ازای دعوت روی «{label}» تنظیم شد.", reply_markup=kb.referral_settings_kb(db))

    # -------------------------------------------------------------------
    # مدیریت گردونه شانس
    # -------------------------------------------------------------------

    @router.callback_query(F.data == "adm_wheel_settings")
    async def cb_admin_wheel_settings(call: CallbackQuery):
        if not senior_admin_only(call.from_user.id):
            return await deny_mid(call)
        await replace_admin_view(call, "🎡 مدیریت گردونه شانس:", reply_markup=kb.wheel_settings_kb(db))
        await call.answer()

    @router.callback_query(F.data == "adm_wheel_toggle")
    async def cb_admin_wheel_toggle(call: CallbackQuery):
        if not senior_admin_only(call.from_user.id):
            return await deny_mid(call)
        current = (await asyncio.to_thread(db.get_setting, "wheel_enabled", "1"))
        (await asyncio.to_thread(db.set_setting, "wheel_enabled", "0" if current == "1" else "1"))
        await safe_edit(call, "🎡 مدیریت گردونه شانس:", reply_markup=kb.wheel_settings_kb(db))
        await call.answer("وضعیت تغییر کرد.")

    @router.callback_query(F.data == "adm_wheel_edit_percent")
    async def cb_admin_wheel_edit_percent(call: CallbackQuery, state: FSMContext):
        if not senior_admin_only(call.from_user.id):
            return await deny_mid(call)
        await state.set_state(AdminWheelSettings.waiting_win_percent)
        await safe_edit(call, 
            "درصد احتمال برد را وارد کنید (عددی بین 0 تا 100، مثلاً 10):", reply_markup=kb.admin_back_kb()
        )
        await call.answer()

    @router.message(AdminWheelSettings.waiting_win_percent)
    async def process_wheel_percent(message: Message, state: FSMContext):
        text = message.text.strip()
        if not text.isdigit() or not (0 <= int(text) <= 100):
            await message.answer("لطفاً یک عدد بین 0 تا 100 ارسال کنید.")
            return
        (await asyncio.to_thread(db.set_setting, "wheel_win_percent", text))
        await state.clear()
        await message.answer(f"✅ احتمال برد گردونه روی {text}٪ تنظیم شد.", reply_markup=kb.wheel_settings_kb(db))

    @router.callback_query(F.data == "adm_wheel_edit_prizes")
    async def cb_admin_wheel_edit_prizes(call: CallbackQuery, state: FSMContext):
        if not senior_admin_only(call.from_user.id):
            return await deny_mid(call)
        await state.set_state(AdminWheelSettings.waiting_prizes)
        await safe_edit(call, 
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
        (await asyncio.to_thread(db.set_wheel_prizes, [int(p) for p in parts]))
        await state.clear()
        await message.answer("✅ لیست جوایز گردونه به‌روزرسانی شد.", reply_markup=kb.wheel_settings_kb(db))

    @router.callback_query(F.data == "adm_wheel_edit_expiry")
    async def cb_admin_wheel_edit_expiry(call: CallbackQuery, state: FSMContext):
        if not senior_admin_only(call.from_user.id):
            return await deny_mid(call)
        await state.set_state(AdminWheelSettings.waiting_expiry)
        await safe_edit(call, 
            "کد جایزه چند ساعت اعتبار داشته باشد؟ (فقط عدد، مثلاً 24):", reply_markup=kb.admin_back_kb()
        )
        await call.answer()

    @router.message(AdminWheelSettings.waiting_expiry)
    async def process_wheel_expiry(message: Message, state: FSMContext):
        text = message.text.strip()
        if not text.isdigit() or int(text) <= 0:
            await message.answer("لطفاً یک عدد صحیح مثبت ارسال کنید.")
            return
        (await asyncio.to_thread(db.set_setting, "wheel_code_expiry_hours", text))
        await state.clear()
        await message.answer(f"✅ اعتبار کد جایزه روی {text} ساعت تنظیم شد.", reply_markup=kb.wheel_settings_kb(db))

    @router.callback_query(F.data == "adm_wheel_edit_cooldown")
    async def cb_admin_wheel_edit_cooldown(call: CallbackQuery, state: FSMContext):
        if not senior_admin_only(call.from_user.id):
            return await deny_mid(call)
        await state.set_state(AdminWheelSettings.waiting_cooldown)
        await safe_edit(call, 
            "فاصله مجاز بین دو چرخش هر کاربر چند ساعت باشد؟ (فقط عدد، مثلاً 24):", reply_markup=kb.admin_back_kb()
        )
        await call.answer()

    @router.message(AdminWheelSettings.waiting_cooldown)
    async def process_wheel_cooldown(message: Message, state: FSMContext):
        text = message.text.strip()
        if not text.isdigit() or int(text) <= 0:
            await message.answer("لطفاً یک عدد صحیح مثبت ارسال کنید.")
            return
        (await asyncio.to_thread(db.set_setting, "wheel_cooldown_hours", text))
        await state.clear()
        await message.answer(f"✅ فاصله بین دو چرخش روی {text} ساعت تنظیم شد.", reply_markup=kb.wheel_settings_kb(db))

    # -------------------------------------------------------------------
    # ویرایش متن دکمه‌ها
    # -------------------------------------------------------------------

    @router.callback_query(F.data == "adm_edit_buttons")
    async def cb_admin_edit_buttons(call: CallbackQuery):
        if not full_admin_only(call.from_user.id):
            return await deny_support(call)
        await replace_admin_view(call, "کدام دکمه ویرایش شود؟", reply_markup=kb.admin_edit_buttons_kb(db))
        await call.answer()

    @router.callback_query(F.data.startswith("adm_btn_edit:"))
    async def cb_admin_btn_edit(call: CallbackQuery, state: FSMContext):
        key = call.data.split(":")[1]
        await state.update_data(setting_key=key)
        await state.set_state(AdminEditButton.waiting_text)
        current = (await asyncio.to_thread(db.get_setting, key))
        await safe_edit(call, 
            f"متن فعلی: {current}\n\nمتن جدید را ارسال کنید (می‌توانید ایموجی هم اضافه کنید):",
            reply_markup=kb.admin_back_kb(),
        )
        await call.answer()

    @router.message(AdminEditButton.waiting_text)
    async def process_edit_button(message: Message, state: FSMContext):
        data = await state.get_data()
        key = data["setting_key"]
        (await asyncio.to_thread(db.set_setting, key, message.text.strip()))
        await state.clear()
        await message.answer("✅ متن دکمه به‌روزرسانی شد.", reply_markup=kb.admin_edit_buttons_kb(db))

    @router.callback_query(F.data.startswith("adm_btn_toggle:"))
    async def cb_admin_btn_toggle(call: CallbackQuery):
        if not full_admin_only(call.from_user.id):
            return await deny_support(call)
        key = call.data.split(":")[1]
        meta = MENU_BUTTON_META.get(key)
        if not meta or not meta["toggle_key"]:
            await call.answer("❌ این دکمه قابل فعال/غیرفعال کردن نیست.", show_alert=True)
            return
        toggle_key = meta["toggle_key"]
        current = (await asyncio.to_thread(db.get_setting, toggle_key, "1"))
        (await asyncio.to_thread(db.set_setting, toggle_key, "0" if current == "1" else "1"))
        await safe_edit(call, "کدام دکمه ویرایش شود؟", reply_markup=kb.admin_edit_buttons_kb(db))
        await call.answer("✅ وضعیت دکمه به‌روزرسانی شد.")

    # -------------------------------------------------------------------
    # چیدمان/نمایش منوی اصلی: منوی پایین (Reply) و منوی شیشه‌ای بالا (Inline)
    # -------------------------------------------------------------------

    @router.callback_query(F.data == "adm_main_menu_settings")
    async def cb_admin_main_menu_settings(call: CallbackQuery):
        if not full_admin_only(call.from_user.id):
            return await deny_support(call)
        await replace_admin_view(call, "🧩 تنظیمات منوی اصلی:", reply_markup=kb.main_menu_settings_kb(db))
        await call.answer()

    @router.callback_query(F.data == "adm_mm_toggle_reply")
    async def cb_admin_mm_toggle_reply(call: CallbackQuery):
        if not full_admin_only(call.from_user.id):
            return await deny_support(call)
        current = (await asyncio.to_thread(db.get_setting, "main_menu_reply_enabled", "1")) == "1"
        if current and (await asyncio.to_thread(db.get_setting, "main_menu_inline_enabled", "0")) != "1":
            await call.answer("⚠️ چون منوی شیشه‌ای بالا غیرفعال است، منوی پایین را نمی‌توان خاموش کرد.", show_alert=True)
            return
        (await asyncio.to_thread(db.set_setting, "main_menu_reply_enabled", "0" if current else "1"))
        await safe_edit(call, "🧩 تنظیمات منوی اصلی:", reply_markup=kb.main_menu_settings_kb(db))
        await call.answer("✅ اعمال شد.")

    @router.callback_query(F.data == "adm_mm_toggle_inline")
    async def cb_admin_mm_toggle_inline(call: CallbackQuery):
        if not full_admin_only(call.from_user.id):
            return await deny_support(call)
        current = (await asyncio.to_thread(db.get_setting, "main_menu_inline_enabled", "0")) == "1"
        if current and (await asyncio.to_thread(db.get_setting, "main_menu_reply_enabled", "1")) != "1":
            await call.answer("⚠️ چون منوی پایین غیرفعال است، منوی شیشه‌ای بالا را نمی‌توان خاموش کرد.", show_alert=True)
            return
        (await asyncio.to_thread(db.set_setting, "main_menu_inline_enabled", "0" if current else "1"))
        await safe_edit(call, "🧩 تنظیمات منوی اصلی:", reply_markup=kb.main_menu_settings_kb(db))
        await call.answer("✅ اعمال شد.")

    @router.callback_query(F.data == "adm_mm_toggle_columns")
    async def cb_admin_mm_toggle_columns(call: CallbackQuery):
        if not full_admin_only(call.from_user.id):
            return await deny_support(call)
        current = (await asyncio.to_thread(db.get_setting, "main_menu_columns", "1"))
        new_val = "2" if current != "2" else "1"
        (await asyncio.to_thread(db.set_setting, "main_menu_columns", new_val))
        await safe_edit(call, "🧩 تنظیمات منوی اصلی:", reply_markup=kb.main_menu_settings_kb(db))
        await call.answer("✅ اعمال شد.")

    # کلیک روی دکمه‌ی «پنل مدیریت» وقتی از منوی شیشه‌ای بالا (نه منوی پایین) زده شود
    @router.callback_query(F.data == "mm:btn_admin_panel")
    async def cb_mm_admin_panel(call: CallbackQuery, state: FSMContext):
        await call.answer()
        if not admin_only(call.from_user.id):
            return
        await state.clear()
        await call.message.answer("🔧 پنل مدیریت:", reply_markup=kb.admin_panel_kb(db))

    def _lookup_button_label(key: str) -> str:
        if key in kb.BUTTON_LABELS:
            return kb.BUTTON_LABELS[key]
        for item_key, label, _ in kb.ADMIN_PANEL_ITEMS:
            if item_key == key:
                return label
        for item_key, label in kb.BUY_FLOW_COLOR_ITEMS:
            if item_key == key:
                return label
        if key in kb._EXTRA_PANEL_ITEM_LABELS:
            return kb._EXTRA_PANEL_ITEM_LABELS[key]
        return key

    def _is_panel_item_key(key: str) -> bool:
        return any(item_key == key for item_key, _, _ in kb.ADMIN_PANEL_ITEMS)

    def _is_buyflow_key(key: str) -> bool:
        return any(item_key == key for item_key, _ in kb.BUY_FLOW_COLOR_ITEMS)

    @router.callback_query(F.data.startswith("adm_btn_color_menu:"))
    async def cb_admin_btn_color_menu(call: CallbackQuery):
        key = call.data.split(":")[1]
        label = _lookup_button_label(key)
        if _is_panel_item_key(key):
            back_callback = "adm_panel_colors_menu"
        elif _is_buyflow_key(key):
            back_callback = "adm_buyflow_colors_menu"
        else:
            back_callback = "adm_edit_buttons"
        await safe_edit(call, 
            f"رنگ «{label}» را انتخاب کنید:", reply_markup=kb.admin_color_picker_kb(key, back_callback)
        )
        await call.answer()

    @router.callback_query(F.data.startswith("adm_btn_color_set:"))
    async def cb_admin_btn_color_set(call: CallbackQuery):
        parts = (call.data or "").split(":")
        if len(parts) != 3 or parts[0] != "adm_btn_color_set":
            await call.answer("❌ درخواست نامعتبر است.", show_alert=True)
            return
        _, key, style = parts
        if not key or style not in {"primary", "success", "danger", "none"}:
            await call.answer("❌ رنگ انتخاب‌شده نامعتبر است.", show_alert=True)
            return
        (await asyncio.to_thread(db.set_setting, f"{key}_style", "" if style == "none" else style))
        if _is_panel_item_key(key):
            await safe_edit(call, "🎨 رنگ‌آمیزی دکمه‌های پنل مدیریت:", reply_markup=kb.admin_panel_colors_kb(db))
        elif _is_buyflow_key(key):
            await safe_edit(call, "🎨 رنگ‌آمیزی دکمه‌های خرید:", reply_markup=kb.buy_flow_colors_kb(db))
        else:
            await safe_edit(call, "کدام دکمه ویرایش شود؟", reply_markup=kb.admin_edit_buttons_kb(db))
        await call.answer("✅ رنگ دکمه به‌روزرسانی شد.")

    @router.callback_query(F.data == "adm_panel_colors_menu")
    async def cb_admin_panel_colors_menu(call: CallbackQuery):
        await replace_admin_view(call, "🎨 رنگ‌آمیزی دکمه‌های پنل مدیریت:", reply_markup=kb.admin_panel_colors_kb(db))
        await call.answer()

    @router.callback_query(F.data == "adm_buyflow_colors_menu")
    async def cb_admin_buyflow_colors_menu(call: CallbackQuery):
        await replace_admin_view(call, "🎨 رنگ‌آمیزی دکمه‌های خرید:", reply_markup=kb.buy_flow_colors_kb(db))
        await call.answer()

    # -------------------------------------------------------------------
    # تنظیم شماره کارت
    # -------------------------------------------------------------------

    @router.callback_query(F.data == "adm_set_card")
    async def cb_admin_set_card(call: CallbackQuery, state: FSMContext):
        if not full_admin_only(call.from_user.id):
            return await deny_support(call)
        await state.set_state(AdminSetCard.waiting_number)
        await safe_edit(call, "شماره کارت جدید را ارسال کنید:", reply_markup=kb.admin_back_kb())
        await call.answer()

    @router.message(AdminSetCard.waiting_number)
    async def process_set_card_number(message: Message, state: FSMContext):
        await state.update_data(card_number=message.text.strip())
        await state.set_state(AdminSetCard.waiting_holder)
        await message.answer("نام صاحب حساب را ارسال کنید:")

    @router.message(AdminSetCard.waiting_holder)
    async def process_set_card_holder(message: Message, state: FSMContext):
        data = await state.get_data()
        (await asyncio.to_thread(db.set_setting, "card_number", data["card_number"]))
        (await asyncio.to_thread(db.set_setting, "card_holder", message.text.strip()))
        await state.clear()
        (await asyncio.to_thread(db.log_admin_action, 
            message.from_user.id, "card_change",
            f"شماره کارت جدید: {data['card_number']} | به نام: {message.text.strip()}",
        ))
        await message.answer("✅ اطلاعات کارت به‌روزرسانی شد.", reply_markup=kb.admin_category_kb(db, "finance"))

    # -------------------------------------------------------------------
    # ویرایش پیام خوش‌آمد
    # -------------------------------------------------------------------

    @router.callback_query(F.data == "adm_edit_welcome")
    async def cb_admin_edit_welcome(call: CallbackQuery, state: FSMContext):
        if not full_admin_only(call.from_user.id):
            return await deny_support(call)
        await state.set_state(AdminEditWelcome.waiting_text)
        current = (await asyncio.to_thread(db.get_setting, "welcome_text"))
        await safe_edit(call, f"متن فعلی:\n{current}\n\nمتن جدید را ارسال کنید:", reply_markup=kb.admin_back_kb())
        await call.answer()

    @router.message(AdminEditWelcome.waiting_text)
    async def process_edit_welcome(message: Message, state: FSMContext):
        (await asyncio.to_thread(db.set_setting, "welcome_text", message.text))
        await state.clear()
        await message.answer("✅ پیام خوش‌آمد به‌روزرسانی شد.", reply_markup=kb.admin_category_kb(db, "appearance"))

    # -------------------------------------------------------------------
    # مدیریت ادمین‌ها
    # -------------------------------------------------------------------

    @router.callback_query(F.data == "adm_admins_menu")
    async def cb_admin_admins_menu(call: CallbackQuery):
        if not owner_only(call.from_user.id):
            return await call.answer("⛔️ مدیریت ادمین‌ها فقط برای مالک اصلی در دسترس است.", show_alert=True)
        try:
            await replace_admin_view(call, "👤 مدیریت ادمین‌ها:", kb.admin_admins_menu_kb())
            await call.answer()
        except Exception:
            await call.answer("⚠️ باز کردن مدیریت ادمین‌ها ناموفق بود.", show_alert=True)

    @router.callback_query(F.data == "adm_admins_list")
    async def cb_admin_admins_list(call: CallbackQuery):
        if not owner_only(call.from_user.id):
            return await call.answer("⛔️ فقط مالک اصلی می‌تواند لیست ادمین‌ها را ببیند.", show_alert=True)
        try:
            admins = (await asyncio.to_thread(db.list_admins_with_roles))
            if not admins:
                text = "📃 هیچ ادمینی ثبت نشده است."
            else:
                # برای جلوگیری از خطاهای Markdown، لیست را بدون parse_mode ارسال می‌کنیم.
                lines = [f"• {a['telegram_id']} — {kb.ADMIN_ROLE_LABELS.get(a['role'], a['role'])}" for a in admins]
                text = "📃 لیست ادمین‌ها و نقش‌ها:\n\n" + "\n".join(lines)
            await replace_admin_view(call, text, kb.admin_back_kb("adm_admins_menu"))
            await call.answer()
        except Exception:
            await call.answer("⚠️ دریافت لیست ادمین‌ها ناموفق بود. دوباره تلاش کنید.", show_alert=True)

    @router.callback_query(F.data == "adm_admin_add")
    async def cb_admin_admin_add(call: CallbackQuery, state: FSMContext):
        if not owner_only(call.from_user.id):
            return await call.answer("⛔️ فقط مالک اصلی می‌تواند ادمین اضافه کند.", show_alert=True)
        await state.set_state(AdminAddAdmin.waiting_id)
        await replace_admin_view(call, 
            "آیدی عددی کاربر جدید برای افزودن به ادمین‌ها را ارسال کنید:", reply_markup=kb.admin_back_kb("adm_admins_menu")
        )
        await call.answer()

    @router.message(AdminAddAdmin.waiting_id)
    async def process_add_admin(message: Message, state: FSMContext):
        raw = (message.text or "").strip()
        if not raw.isdigit():
            await message.answer("لطفاً فقط آیدی عددی ارسال کنید.")
            return
        target_id = int(raw)
        if (await asyncio.to_thread(db.is_admin, target_id)):
            await state.clear()
            await message.answer(
                "این کاربر از قبل ادمین است. برای تغییر نقشش از «🔄 تغییر نقش ادمین» استفاده کن.",
                reply_markup=kb.admin_admins_menu_kb(),
            )
            return
        await state.clear()
        await message.answer(
            f"نقش کاربر {target_id} چه باشد?",
            reply_markup=kb.admin_role_pick_kb(target_id, "add"),
        )

    @router.callback_query(F.data.startswith("adm_add_admin_role:"))
    async def cb_admin_add_admin_role(call: CallbackQuery):
        if not owner_only(call.from_user.id):
            return await call.answer("⛔️ فقط مالک اصلی می‌تواند ادمین اضافه کند.", show_alert=True)
        try:
            parts = (call.data or "").split(":")
            if len(parts) != 3 or not parts[1].isdigit() or parts[2] not in ("admin", "mid", "support"):
                return await call.answer("⚠️ درخواست نامعتبر است.", show_alert=True)
            target_id, role = int(parts[1]), parts[2]
            (await asyncio.to_thread(db.add_admin, target_id, role=role))
            (await asyncio.to_thread(db.log_admin_action, 
                call.from_user.id, "admin_add",
                f"کاربر {target_id} | نقش: {kb.ADMIN_ROLE_LABELS.get(role, role)}",
            ))
            await safe_edit(
                call,
                f"✅ کاربر {target_id} با نقش «{kb.ADMIN_ROLE_LABELS.get(role, role)}» اضافه شد.",
                kb.admin_back_kb("adm_admins_menu"),
            )
            await call.answer("ادمین اضافه شد.")
        except Exception:
            await call.answer("⚠️ افزودن ادمین ناموفق بود. دوباره تلاش کنید.", show_alert=True)

    @router.callback_query(F.data == "adm_admin_role_change")
    async def cb_admin_role_change_start(call: CallbackQuery, state: FSMContext):
        if not owner_only(call.from_user.id):
            return await call.answer("⛔️ فقط مالک اصلی می‌تواند نقش ادمین‌ها را تغییر دهد.", show_alert=True)
        await state.set_state(AdminChangeRole.waiting_id)
        await replace_admin_view(call, 
            "آیدی عددی ادمینی که می‌خواهی نقشش را تغییر دهی را ارسال کن:",
            reply_markup=kb.admin_back_kb("adm_admins_menu"),
        )
        await call.answer()

    @router.message(AdminChangeRole.waiting_id)
    async def process_change_role_id(message: Message, state: FSMContext):
        raw = (message.text or "").strip()
        if not raw.isdigit():
            await message.answer("لطفاً فقط آیدی عددی ارسال کنید.")
            return
        target_id = int(raw)
        await state.clear()
        role = (await asyncio.to_thread(db.get_admin_role, target_id))
        if role is None:
            await message.answer("این کاربر ادمین نیست.", reply_markup=kb.admin_admins_menu_kb())
            return
        if role == "owner":
            await message.answer("نقش مالک اصلی قابل تغییر نیست.", reply_markup=kb.admin_admins_menu_kb())
            return
        await message.answer(
            f"نقش جدید کاربر {target_id} (نقش فعلی: {kb.ADMIN_ROLE_LABELS.get(role, role)}) چه باشد؟",
            reply_markup=kb.admin_role_pick_kb(target_id, "setrole"),
        )

    @router.callback_query(F.data.startswith("adm_change_role_set:"))
    async def cb_admin_change_role_set(call: CallbackQuery):
        if not owner_only(call.from_user.id):
            return await call.answer("⛔️ فقط مالک اصلی می‌تواند نقش ادمین‌ها را تغییر دهد.", show_alert=True)
        try:
            parts = (call.data or "").split(":")
            if len(parts) != 3 or not parts[1].isdigit() or parts[2] not in ("admin", "mid", "support"):
                return await call.answer("⚠️ درخواست نامعتبر است.", show_alert=True)
            target_id, role = int(parts[1]), parts[2]
            ok = (await asyncio.to_thread(db.set_admin_role, target_id, role))
            if not ok:
                return await call.answer("⛔️ تغییر نقش ناموفق بود.", show_alert=True)
            (await asyncio.to_thread(db.log_admin_action, 
                call.from_user.id, "admin_role_change",
                f"کاربر {target_id} | نقش جدید: {kb.ADMIN_ROLE_LABELS.get(role, role)}",
            ))
            await safe_edit(
                call,
                f"✅ نقش کاربر {target_id} به «{kb.ADMIN_ROLE_LABELS.get(role, role)}» تغییر کرد.",
                kb.admin_back_kb("adm_admins_menu"),
            )
            await call.answer("نقش تغییر کرد.")
        except Exception:
            await call.answer("⚠️ تغییر نقش ناموفق بود. دوباره تلاش کنید.", show_alert=True)

    @router.callback_query(F.data == "adm_admin_remove")
    async def cb_admin_admin_remove(call: CallbackQuery, state: FSMContext):
        if not owner_only(call.from_user.id):
            return await call.answer("⛔️ فقط مالک اصلی می‌تواند ادمین حذف کند.", show_alert=True)
        await state.set_state(AdminRemoveAdmin.waiting_id)
        await replace_admin_view(call, 
            "آیدی عددی ادمینی که باید حذف شود را ارسال کنید:", reply_markup=kb.admin_back_kb("adm_admins_menu")
        )
        await call.answer()

    @router.message(AdminRemoveAdmin.waiting_id)
    async def process_remove_admin(message: Message, state: FSMContext):
        raw = (message.text or "").strip()
        if not raw.isdigit():
            await message.answer("لطفاً فقط آیدی عددی ارسال کنید.")
            return
        target_id = int(raw)
        try:
            if not (await asyncio.to_thread(db.is_admin, target_id)):
                await state.clear()
                await message.answer("⛔️ این کاربر ادمین نیست.", reply_markup=kb.admin_admins_menu_kb())
                return
            if (await asyncio.to_thread(db.get_admin_role, target_id)) == "owner":
                await state.clear()
                await message.answer("⛔️ مالک اصلی قابل حذف نیست.", reply_markup=kb.admin_admins_menu_kb())
                return
            ok = (await asyncio.to_thread(db.remove_admin, target_id))
            await state.clear()
            if ok:
                (await asyncio.to_thread(db.log_admin_action, message.from_user.id, "admin_remove", f"کاربر {target_id}"))
                await message.answer("✅ ادمین حذف شد.", reply_markup=kb.admin_admins_menu_kb())
            else:
                await message.answer("⛔️ حذف ادمین ناموفق بود.", reply_markup=kb.admin_admins_menu_kb())
        except Exception:
            await state.clear()
            await message.answer("⚠️ حذف ادمین ناموفق بود. دوباره تلاش کنید.")

    # -------------------------------------------------------------------
    # پیام همگانی
    # -------------------------------------------------------------------

    @router.callback_query(F.data == "adm_broadcast")
    async def cb_admin_broadcast(call: CallbackQuery, state: FSMContext):
        if not full_admin_only(call.from_user.id):
            return await deny_support(call)
        await state.set_state(AdminBroadcast.waiting_message)
        await replace_admin_view(call, "متن پیام همگانی را ارسال کنید (برای همه کاربران ارسال می‌شود):", reply_markup=kb.admin_back_kb())
        await call.answer()

    @router.message(AdminBroadcast.waiting_message)
    async def process_broadcast(message: Message, state: FSMContext, bot: Bot):
        user_ids = (await asyncio.to_thread(db.get_all_user_ids))
        success, failed = 0, 0
        for uid in user_ids:
            try:
                await message.copy_to(uid)
                success += 1
            except Exception:
                failed += 1
        await state.clear()
        (await asyncio.to_thread(db.log_admin_action, message.from_user.id, "broadcast", f"ارسال به {len(user_ids)} کاربر | موفق: {success} | ناموفق: {failed}"))
        await message.answer(
            f"📢 پیام همگانی ارسال شد.\n✅ موفق: {success}\n❌ ناموفق: {failed}", reply_markup=kb.admin_category_kb(db, "marketing")
        )

    # -------------------------------------------------------------------
    # پاسخ به پیام پشتیبانی کاربر
    # -------------------------------------------------------------------

    @router.callback_query(F.data.startswith("reply_user:"))
    async def cb_reply_user(call: CallbackQuery, state: FSMContext):
        user_id = callback_id(call.data, "reply_user")
        if user_id is None:
            await call.answer("❌ درخواست نامعتبر است.", show_alert=True)
            return
        conv = (await asyncio.to_thread(db.get_support_conversation, user_id))
        assigned_admin_id = conv["assigned_admin_id"] if conv else None
        if assigned_admin_id and assigned_admin_id != call.from_user.id and not owner_only(call.from_user.id):
            await call.answer(
                "⛔️ این گفتگو در حال حاضر توسط ادمین دیگری پاسخ داده می‌شود.", show_alert=True
            )
            return
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
        conv = (await asyncio.to_thread(db.get_support_conversation, user_id))
        assigned_admin_id = conv["assigned_admin_id"] if conv else None
        if assigned_admin_id and assigned_admin_id != message.from_user.id and not owner_only(message.from_user.id):
            await message.answer(
                "⛔️ این گفتگو در حال حاضر توسط ادمین دیگری پاسخ داده می‌شود.",
                reply_markup=kb.admin_panel_kb(db),
            )
            await state.clear()
            return
        try:
            await bot.send_message(user_id, f"📩 پاسخ پشتیبانی:\n\n{message.text}")
            if message.text:
                if not owner_only(message.from_user.id):
                    (await asyncio.to_thread(db.set_support_conversation_admin, user_id, message.from_user.id))
                (await asyncio.to_thread(db.add_support_message, user_id, "admin", message.text))
            await _notify_user_inline_menu(bot, user_id)
            await message.answer("✅ پاسخ ارسال شد.", reply_markup=kb.admin_panel_kb(db))
        except Exception:
            await message.answer("⛔️ ارسال پیام به کاربر با خطا مواجه شد.", reply_markup=kb.admin_panel_kb(db))
        await state.clear()

    # -------------------------------------------------------------------
    # آمار فروش
    # -------------------------------------------------------------------

    def _fmt_stats_report(stats: dict) -> str:
        def _pct(v):
            if v is None:
                return "—"
            sign = "+" if v > 0 else ""
            return f"{sign}{v}٪"

        lines = [
            f"📊 آمار فروشگاه ({to_jalali_str(stats['start_date'])} تا {to_jalali_str(stats['end_date'])})\n",
            f"👥 کاربران کل: {stats['total_users']:,} | 🆕 جدید در بازه: {stats['new_users']:,}",
            f"✅ سفارش تایید شده: {stats['approved']:,} ({_pct(stats['orders_change_pct'])} نسبت به بازه‌ی قبل)",
            f"⏳ در انتظار: {stats['pending']:,} | ❌ رد شده: {stats['rejected']:,}",
            f"💰 درآمد: {stats['revenue']:,} تومان ({_pct(stats['revenue_change_pct'])})",
            f"📈 نرخ تبدیل: {stats['conversion_rate']}٪ | 🧾 میانگین سبد خرید: {stats['aov']:,} تومان",
            f"🔁 مشتری تکراری: {stats['repeat_customers']:,} از {stats['total_customers']:,} ({stats['repeat_customer_rate']}٪)",
            f"🤝 درآمد رفرال: {stats['referral_revenue']:,} | مستقیم: {stats['direct_revenue']:,} تومان",
            f"🎫 تیکت: {stats['tickets_created']:,} ثبت‌شده، {stats['tickets_open']:,} باز",
        ]
        if stats["avg_ticket_response_minutes"] is not None:
            lines.append(f"⏱ میانگین زمان پاسخ اول: {stats['avg_ticket_response_minutes']} دقیقه")
        if stats["top_products"]:
            lines.append("\n🏆 پرفروش‌ترین محصولات:")
            for i, p in enumerate(stats["top_products"][:5], 1):
                lines.append(f"{i}. {p['name']} — {p['orders']:,} فروش، {p['revenue']:,} تومان")
        return "\n".join(lines)

    @router.callback_query(F.data == "adm_stats")
    async def cb_admin_stats(call: CallbackQuery):
        if not senior_admin_only(call.from_user.id):
            return await deny_mid(call)
        stats = await asyncio.to_thread(db.get_full_stats, None, None)
        await replace_admin_view(call, _fmt_stats_report(stats), reply_markup=kb.admin_stats_period_kb(7))
        await call.answer()

    @router.callback_query(F.data.startswith("adm_stats_p:"))
    async def cb_admin_stats_period(call: CallbackQuery):
        if not senior_admin_only(call.from_user.id):
            return await deny_mid(call)
        days = int(call.data.split(":", 1)[1])
        end_date = date.today().isoformat()
        start_date = (date.today() - timedelta(days=days - 1)).isoformat()
        stats = await asyncio.to_thread(db.get_full_stats, start_date, end_date)
        await replace_admin_view(call, _fmt_stats_report(stats), reply_markup=kb.admin_stats_period_kb(days))
        await call.answer()

    # -------------------------------------------------------------------
    # بکاپ و بازیابی
    # -------------------------------------------------------------------
    # فقط مالک اصلی بات (owner_only) به این بخش دسترسی دارد، چون بازیابی
    # یعنی جایگزینی کامل دیتابیس فعلی و برگشت‌ناپذیر است.

    @router.callback_query(F.data == "adm_backup_menu")
    async def cb_backup_menu(call: CallbackQuery, state: FSMContext):
        if not owner_only(call.from_user.id):
            return await deny_support(call)
        await state.clear()
        await replace_admin_view(call, 
            "🗄 بکاپ و بازیابی دیتابیس\n\n"
            "• «دریافت بکاپ فوری» یک نسخه از دیتابیس فعلی را همین الان برایت می‌فرستد.\n"
            "• «بازیابی از فایل بکاپ» دیتابیس فعلی را با فایلی که آپلود می‌کنی جایگزین می‌کند "
            "(این کار قابل بازگشت نیست مگر با بکاپ دیگری).",
            reply_markup=kb.admin_backup_menu_kb(),
        )
        await call.answer()

    @router.callback_query(F.data == "adm_backup_now")
    async def cb_backup_now(call: CallbackQuery):
        if not owner_only(call.from_user.id):
            return await deny_support(call)
        await call.answer("⏳ در حال گرفتن بکاپ...")
        backup_dir = os.path.join(os.path.dirname(os.path.abspath(db.db_path)), "backups")
        try:
            backup_path = await asyncio.to_thread(create_backup, db.db_path, backup_dir, 14)
        except Exception:
            return await call.message.answer("❌ گرفتن بکاپ ناموفق بود.")
        if not backup_path:
            return await call.message.answer("❌ فایل دیتابیس پیدا نشد.")
        (await asyncio.to_thread(db.log_admin_action, call.from_user.id, "backup_create", "دریافت بکاپ فوری از طریق بات"))
        await call.message.answer_document(
            FSInputFile(backup_path), caption="🗄 بکاپ فوری دیتابیس"
        )

    @router.callback_query(F.data == "adm_restore_start")
    async def cb_restore_start(call: CallbackQuery, state: FSMContext):
        if not owner_only(call.from_user.id):
            return await deny_support(call)
        await state.set_state(AdminRestoreBackup.waiting_file)
        await safe_edit(call, 
            "♻️ فایل بکاپ (.db) را همین‌جا به‌صورت Document ارسال کن.\n\n"
            "⚠️ توجه: بعد از تایید، کل دیتابیس فعلی با این فایل جایگزین می‌شود.",
            reply_markup=kb.admin_restore_waiting_kb(),
        )
        await call.answer()

    @router.callback_query(AdminRestoreBackup.waiting_file, F.data == "adm_restore_cancel_wait")
    async def cb_restore_cancel_wait(call: CallbackQuery, state: FSMContext):
        if not owner_only(call.from_user.id):
            return await deny_support(call)
        await state.clear()
        await safe_edit(call, "❌ بازیابی لغو شد.", reply_markup=kb.admin_back_kb())
        await call.answer()

    @router.message(AdminRestoreBackup.waiting_file, F.document)
    async def on_restore_file(message: Message, state: FSMContext):
        if not owner_only(message.from_user.id):
            return
        doc = message.document
        if not doc.file_name.lower().endswith((".db", ".sqlite", ".sqlite3")):
            return await message.answer("❌ فایل باید پسوند .db یا .sqlite داشته باشد. دوباره ارسال کن.")

        tmp_dir = tempfile.mkdtemp(prefix="restore_")
        tmp_path = os.path.join(tmp_dir, "uploaded.db")
        file = await message.bot.get_file(doc.file_id)
        await message.bot.download_file(file.file_path, destination=tmp_path)

        if not is_valid_sqlite_db(tmp_path):
            return await message.answer("❌ این فایل یک دیتابیس sqlite معتبر نیست. عملیات لغو شد.")

        await state.update_data(restore_tmp_path=tmp_path)
        await state.set_state(AdminRestoreBackup.waiting_confirm)
        size_mb = os.path.getsize(tmp_path) / (1024 * 1024)
        await message.answer(
            f"📦 فایل دریافت شد ({size_mb:.1f} مگابایت).\n\n"
            "⚠️ با تایید، دیتابیس فعلی جایگزین می‌شود (یک نسخه از وضعیت فعلی هم قبلش ذخیره می‌شود). "
            "مطمئنی؟",
            reply_markup=kb.admin_restore_confirm_kb(),
        )

    @router.message(AdminRestoreBackup.waiting_file)
    async def on_restore_file_wrong_type(message: Message):
        if not owner_only(message.from_user.id):
            return
        await message.answer("❌ باید فایل بکاپ را به‌صورت Document ارسال کنی، نه متن یا عکس.")

    @router.callback_query(AdminRestoreBackup.waiting_confirm, F.data == "adm_restore_confirm")
    async def cb_restore_confirm(call: CallbackQuery, state: FSMContext):
        if not owner_only(call.from_user.id):
            return await deny_support(call)
        data = await state.get_data()
        tmp_path = data.get("restore_tmp_path")
        await state.clear()
        if not tmp_path or not os.path.exists(tmp_path):
            return await safe_edit(call, "❌ فایل موقت پیدا نشد، دوباره تلاش کن.")

        await safe_edit(call, "⏳ در حال بازیابی...")
        try:
            await asyncio.to_thread(restore_backup, db, db.db_path, tmp_path)
        except Exception as e:
            return await safe_edit(call, f"❌ بازیابی ناموفق بود: {e}")
        else:
            (await asyncio.to_thread(db.log_admin_action, call.from_user.id, "backup_restore", "بازیابی دیتابیس از فایل بکاپ آپلودی"))
        finally:
            try:
                os.remove(tmp_path)
                os.rmdir(os.path.dirname(tmp_path))
            except OSError:
                pass

        await safe_edit(call, 
            "✅ دیتابیس با موفقیت بازیابی شد.\n"
            "از نسخه‌ی قبلی هم یک بکاپ ایمن (pre_restore) کنار دیتابیس ذخیره شد."
        )
        await call.answer()

    @router.callback_query(AdminRestoreBackup.waiting_confirm, F.data == "adm_restore_cancel")
    async def cb_restore_cancel(call: CallbackQuery, state: FSMContext):
        if not owner_only(call.from_user.id):
            return await deny_support(call)
        data = await state.get_data()
        tmp_path = data.get("restore_tmp_path")
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
                os.rmdir(os.path.dirname(tmp_path))
            except OSError:
                pass
        await state.clear()
        await safe_edit(call, "❌ بازیابی لغو شد.", reply_markup=kb.admin_back_kb())
        await call.answer()

    # -------------------------------------------------------------------
    # دستور متنی برای دسترسی سریع
    # -------------------------------------------------------------------

    @router.message(Command("admin"))
    async def cmd_admin(message: Message, state: FSMContext):
        if not admin_only(message.from_user.id):
            return
        await state.clear()
        await message.answer("🔧 پنل مدیریت:", reply_markup=kb.admin_panel_kb(db))

    return router
