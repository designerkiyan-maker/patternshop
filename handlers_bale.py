# -*- coding: utf-8 -*-
"""
هندلرهای بات بله — python-telegram-bot v22 مستقیم، بدون fake module.

state/fsm:   _fsm_state + _fsm_data  (دیکشنری داخلی)
keyboard:    همان keyboards.py مشترک
database:    همان database.py مشترک
services:    همان services/ مشترک
"""

import asyncio
import logging
import secrets
from typing import Any

from telegram import Update, Bot, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters

import config as cfg
import keyboards as kb
from database import Database
from states import BuyFlow, CartFlow, ContactFlow, DiscountEntry, WalletTopup, LoyaltyRedeem
from file_delivery import deliver_pattern_to_user
from force_join import is_channel_member, CHECK_CALLBACK
import loyalty
from loyalty import LoyaltyError
from jalali import to_jalali_str
from services import cart as cart_svc
from services import checkout as checkout_svc
from services import orders as service_orders
from services.errors import CartError, CatalogError, DiscountError, InventoryError, ShopError, WalletError


def _kb_wrap(fn):
    """Wrap a keyboards.py function so its return value is always a plain dict."""
    def wrapper(*args, **kwargs):
        result = fn(*args, **kwargs)
        if result is None:
            return None
        for method in ("model_dump", "to_dict"):
            if hasattr(result, method):
                return getattr(result, method)(exclude_none=True, by_alias=False)
        return result
    return wrapper


# Patch all keyboard-returning functions to emit plain dicts (ptb needs them).
for _name in dir(kb):
    if _name.startswith("_"):
        continue
    _fn = getattr(kb, _name)
    if callable(_fn) and not getattr(_fn, "__wrapped__", False):
        try:
            setattr(kb, _name, _kb_wrap(_fn))
        except Exception:
            pass

logger = logging.getLogger("handlers_bale")

# ─── Simple dict-based FSM ──────────────────────────────────────
_fsm_state: dict[tuple[int, int], str] = {}
_fsm_data: dict[tuple[int, int], dict] = {}

def _sk(bid: int, uid: int) -> tuple[int, int]:
    return (bid, uid)

def _get_state(uid: int, bid: int = 0) -> str | None:
    return _fsm_state.get(_sk(bid, uid))

def _set_state(uid: int, state: str | None, bid: int = 0):
    k = _sk(bid, uid)
    if state is None: _fsm_state.pop(k, None)
    else: _fsm_state[k] = state

def _get_data(uid: int, bid: int = 0) -> dict:
    return _fsm_data.get(_sk(bid, uid), {})

def _set_data(uid: int, data: dict, bid: int = 0):
    _fsm_data[_sk(bid, uid)] = data

def _clear(uid: int, bid: int = 0):
    _fsm_state.pop(_sk(bid, uid), None)
    _fsm_data.pop(_sk(bid, uid), None)

def _state_msg_filter(state_name: str, bot_id: int = 0):
    """Returns a filter matching messages only when the user's FSM state equals state_name."""
    class _SF(filters.BaseFilter):
        async def check(self, update):
            return _get_state(update.effective_user.id, bot_id) == state_name
    return _SF()

# ─── Combined media filters (ptb v22 compatibility) ─────────────
class _PhotoOrDoc(filters.BaseFilter):
    async def check(self, update):
        msg = update.effective_message
        return bool(msg and (msg.photo or msg.document))
class _NotPhotoOrDoc(filters.BaseFilter):
    async def check(self, update):
        msg = update.effective_message
        return bool(msg and not (msg.photo or msg.document))
_PHOTO_DOC = _PhotoOrDoc()
_NOT_PHOTO_DOC = _NotPhotoOrDoc()

# ─── Helpers ─────────────────────────────────────────────────────
async def _answer(cb: Update, text: str = "", show_alert: bool = False):
    await cb.callback_query.answer(text=text, show_alert=show_alert)

def _msg(u: Update):
    return u.effective_message if u.effective_message else getattr(getattr(u, "callback_query", None), "message", None)

async def _send(u, context, text: str, **kwargs):
    """Send a text message — works for both regular messages and callback-query contexts."""
    chat_id = u.effective_chat.id if u.effective_chat else (u.callback_query.message.chat.id if u.callback_query else None)
    if not chat_id: return
    kwargs["chat_id"] = chat_id
    await context.bot.send_message(**kwargs)

async def _edit_text(u, context, text: str, reply_markup=None, parse_mode=None):
    """Try edit_message_text; fall back to send_message."""
    if u.callback_query and getattr(u.callback_query, "message", None):
        kwargs = {"text": text, "chat_id": u.callback_query.message.chat.id,
                  "message_id": u.callback_query.message.message_id}
        if reply_markup: kwargs["reply_markup"] = reply_markup
        if parse_mode: kwargs["parse_mode"] = parse_mode
        try:
            await context.bot.edit_message_text(**kwargs)
        except Exception as e:
            if "not modified" in str(e).lower(): return
            del kwargs["message_id"]
            await context.bot.send_message(**kwargs)
    elif u.effective_message:
        kwargs = {"chat_id": u.effective_message.chat.id, "text": text}
        if reply_markup: kwargs["reply_markup"] = reply_markup
        if parse_mode: kwargs["parse_mode"] = parse_mode
        await context.bot.send_message(**kwargs)

async def _send_inline_main_menu(u, context, uid: int, db: Database):
    inline_kb = await asyncio.to_thread(kb.inline_menu_for_user, db, uid)
    if inline_kb is not None:
        msg = u.callback_query.message if u.callback_query else u.effective_message
        if msg:
            await context.bot.send_message(chat_id=u.effective_chat.id, text="📋 منو:", reply_markup=inline_kb)


def _receipt_payload(u: Update):
    """Extract (file_id, type) from photo/document message."""
    msg = u.effective_message
    if not msg: return None, None
    if msg.photo:
        return msg.photo[-1].file_id, "photo"
    if msg.document:
        return msg.document.file_id, "document"
    return None, None


# ===================================================================
# Factory — returns list of ptb handlers for one bot instance
# ===================================================================

async def make_user_handlers(db: Database, bot_token: str):
    """ساخت لیست handlerهای بات بله — هر بات توکن مستقل handlerهای جداگانه میسازد."""
    BOT_ID = int(bot_token.split(":")[0])
    H = []  # handlers list

    # ── /start ──────────────────────────────────────────────────
    async def cmd_start(update, context):
        uid = update.effective_user.id
        _clear(uid, BOT_ID)
        await asyncio.to_thread(db.add_or_update_user, uid,
                                update.effective_user.username or "",
                                update.effective_user.first_name or "")
        try:
            reg_points = await asyncio.to_thread(loyalty.award_registration, db, uid)
        except Exception:
            logger.exception("award_registration failed for %s", uid); reg_points = 0
        parts = (update.message.text or "").split(maxsplit=1)
        if len(parts) > 1 and parts[1].startswith("ref"):
            ref_part = parts[1][3:]
            if ref_part.isdigit() and int(ref_part) != uid:
                referrer_id = int(ref_part)
                existing = await asyncio.to_thread(db.get_user, uid)
                if not (existing and existing.get("referred_by")):
                    await asyncio.to_thread(db.set_referred_by, uid, referrer_id)
                    try:
                        rp = await asyncio.to_thread(loyalty.award_referral, db, referrer_id, uid)
                    except Exception: logger.exception("award_referral failed"); rp = 0
                    if rp > 0:
                        try: await context.context.bot.send_message(referrer_id, f"🎁 {rp} امتیاز باشگاه مشتریان بابت معرفی دوستتان اضافه شد!")
                        except Exception: pass
                    ri = await asyncio.to_thread(db.apply_referral_invite_rewards, uid, referrer_id)
                    if ri:
                        ib = ri.get("invite_bonus")
                        if ib:
                            try: await context.context.bot.send_message(referrer_id, f"🤝 یک نفر با لینک دعوت شما آمد!\n💰 {ib:,} تومان به کیف پول اضافه شد.")
                            except Exception: pass
                        fp_id = ri.get("free_config_product_id")
                        if fp_id:
                            prod = await asyncio.to_thread(db.get_product, fp_id)
                            if prod and await asyncio.to_thread(db.has_product_files, fp_id):
                                try: await context.context.bot.send_message(referrer_id, "🎁 یک الگوی رایگان به خاطر معرفی دوستتان تعلق گرفت!")
                                except Exception: pass
        welcome = await asyncio.to_thread(db.get_setting, "welcome_text")
        await context.bot.send_message(chat_id=update.effective_message.chat.id, text=welcome, reply_markup=kb.menu_for_user(db, uid))
        await _send_inline_main_menu(update, context, uid, db)
        if reg_points > 0:
            try: await context.bot.send_message(chat_id=update.effective_message.chat.id, text=f"🎁 {reg_points} امتیاز خوشآمدگویی!")
            except Exception: pass

    H.append(CommandHandler("start", cmd_start))

    # ── Inline helper ───────────────────────────────────────────
    async def _inl(target_uid: int, action_fn):
        """Run an action handler but with target_uid as effective_user (for mm: bridge)."""
        class FakeMsg:
            def __init__(self, uid, text="", chat_id=None):
                self._uid = uid
                self.text = text
                self.chat_id = chat_id
            @property
            def effective_user(self):
                class U:
                    id = self._uid
                    username = ""
                    first_name = ""
                return U()
            @property
            def effective_chat(self):
                class C: id = self.chat_id or 0
                return C()
            @property
            def effective_message(self): return self
            async def answer(self, *a, **kw):
                pass  # stub
        class FakeUpdate:
            def __init__(self, uid, text="", chat_id=None):
                self.effective_user = FakeMsg(uid).effective_user
                self.effective_chat = FakeMsg(uid, chat_id=chat_id).effective_chat
                self.effective_message = FakeMsg(uid, text, chat_id)
                self.message = FakeMsg(uid, text, chat_id)
        return await action_fn(FakeUpdate(target_uid))

    # ── Menu buttons (text match) ───────────────────────────────
    async def _text_handler(pattern: str, fn):
        return MessageHandler(filters.TEXT & filters.Regex(f"^{pattern}$"), fn)

    async def _show_buy(update, context):
        cats = await asyncio.to_thread(lambda: db.get_categories(active_only=True))
        if not cats:
            await context.bot.send_message(chat_id=update.effective_message.chat.id, text="هنوز دستهبندیای اضافه نشده است.")
            return
        await context.bot.send_message(chat_id=update.effective_message.chat.id, text="📂 دستهبندیها:", reply_markup=kb.categories_kb(db, cats))

    async def _show_categories_from_cb(update, context):
        cats = await asyncio.to_thread(lambda: db.get_categories(active_only=True))
        await _edit_text(update, context, "📂 دستهبندیها:", reply_markup=kb.categories_kb(db, cats))
        await update.callback_query.answer()

    async def _cb_back_main(update, context):
        uid = update.effective_user.id
        await _edit_text(update, context, await asyncio.to_thread(db.get_setting, "welcome_text"),
                        reply_markup=kb.menu_for_user(db, uid))
        await _send_inline_main_menu(update, context, uid, db)
        await update.callback_query.answer()

    async def _cb_back_categories(update, context):
        cats = await asyncio.to_thread(lambda: db.get_categories(active_only=True))
        await _edit_text(update, context, "📂 دستهبندیها:", reply_markup=kb.categories_kb(db, cats))
        await update.callback_query.answer()

    async def _cb_category(update, context):
        cat_id = int(update.callback_query.data.split(":", 2)[1])
        prods = await asyncio.to_thread(db.get_products, cat_id)
        if not prods:
            await update.callback_query.answer("محصولی در این دستهبندی موجود نیست.", show_alert=True)
            return
        await _edit_text(update, context, "📦 محصولات:", reply_markup=kb.products_kb(db, cat_id, prods))
        await update.callback_query.answer()

    async def _cb_product(update, context):
        try: pid = int(update.callback_query.data.split(":", 2)[1])
        except: await update.callback_query.answer("❌ نامعتبر.", show_alert=True); return
        prod = await asyncio.to_thread(db.get_product, pid)
        if not prod:
            await update.callback_query.answer("محصول یافت نشد.", show_alert=True); return
        hf = await asyncio.to_thread(db.has_product_files, pid)
        wc = await asyncio.to_thread(db.get_wallet_credit, update.effective_user.id)
        txt = [f"🧵 {prod['name']}\n💰 قیمت: {prod['price']:,} تومان"]
        txt.append("✅ فایل الگو موجود است" if hf else "⛔️ فعلاً فاقد فایل الگو است.")
        if wc > 0: txt.append(f"👛 موجودی کیف پول: {wc:,} تومان")
        if not hf:
            await _edit_text(update, context, "\n".join(txt))
            await update.callback_query.answer(); return
        await _edit_text(update, context, "\n".join(txt), reply_markup=kb.product_confirm_kb(pid))
        await update.callback_query.answer()

    async def _cb_noop(update, context):
        await update.callback_query.answer()

    async def _cb_enter_code(update, context):
        try: pid = int(update.callback_query.data.split(":", 2)[1])
        except: await update.callback_query.answer("❌ نامعتبر.", show_alert=True); return
        _set_data(update.effective_user.id, {"discount_product_id": pid}, BOT_ID)
        _set_state(update.effective_user.id, DiscountEntry.waiting_code.state, BOT_ID)
        await _edit_text(update, context, "🎟 کد تخفیف را ارسال کنید:", reply_markup=kb.cancel_kb())
        await update.callback_query.answer()

    async def _process_disc_code(update, context):
        uid = update.effective_user.id
        data = _get_data(uid, BOT_ID)
        pid = data.get("discount_product_id")
        prod = await asyncio.to_thread(db.get_product, pid) if pid else None
        if not prod:
            await context.bot.send_message(chat_id=update.effective_message.chat.id, text="محصول معتبر نیست."); _clear(uid, BOT_ID); return
        cr = await asyncio.to_thread(db.get_discount_code, update.message.text.strip())
        if not await asyncio.to_thread(db.is_discount_code_valid, cr):
            await context.bot.send_message(chat_id=update.effective_message.chat.id, text="❌ کد تخفیف نامعتبر است.", reply_markup=kb.cancel_kb()); return
        total = prod["price"]; disc = await asyncio.to_thread(db.compute_discount_amount, cr, total)
        _set_data(uid, {**data, "discount_code": update.message.text.strip(), "discount_code_id": cr["id"], "discount_amount": disc}, BOT_ID)
        _clear(uid, BOT_ID)
        w = await asyncio.to_thread(db.get_wallet_credit, uid)
        after = total - disc; wu = min(w, after); final = after - wu
        txt = f"✅ کد تخفیف اعمال شد!\n\n🧵 {prod['name']}\n💰 قیمت: {total:,} تومان\n🎟 تخفیف: {disc:,} تومان"
        if wu > 0: txt += f"\n👛 اعمال کیف پول: {wu:,} تومان"
        txt += f"\n💵 مبلغ نهایی: {final:,} تومان"
        await context.bot.send_message(chat_id=update.effective_message.chat.id, text=txt, reply_markup=kb.product_confirm_kb(pid))

    # ── Checkout flow ───────────────────────────────────────────
    async def _cb_buy_start(update, context):
        try: pid = int(update.callback_query.data.split(":", 2)[1])
        except: await update.callback_query.answer("❌ نامعتبر.", show_alert=True); return
        prod = await asyncio.to_thread(db.get_product, pid)
        if not prod: await update.callback_query.answer("الگو موجود نیست.", show_alert=True); return
        try: await asyncio.to_thread(cart_svc.add_to_cart, db, update.effective_user.id, pid, None, 1)
        except (CartError, CatalogError) as e:
            await update.callback_query.answer(e.message, show_alert=True); return
        sm = await asyncio.to_thread(cart_svc.cart_summary, db, update.effective_user.id)
        if sm["count"] == 1 and not sm["has_physical"]:
            await _run_checkout(update, bot); return
        await _show_cart(update, context)

    async def _show_cart(update, context):
        sm = await asyncio.to_thread(cart_svc.cart_summary, db, update.effective_user.id)
        if not sm["items"]:
            await _edit_text(update, context, "🛒 سبد خرید شما خالی است."); await update.callback_query.answer(); return
        lines = ["🛒 سبد خرید:\n"]
        for it in sm["items"]:
            n = it["product_name"]
            if it.get("variant_label"): n = f"{n} ({it['variant_label']})"
            unit = it.get("variant_price") or it["product_price"]
            lines.append(f"• {n} × {it['quantity']} = {int(unit)*int(it['quantity']):,} ت")
        lines.append(f"\n💰 جمع: {sm.get('total',0):,} تومان")
        await _edit_text(update, context, "\n".join(lines), reply_markup=kb.cart_menu_kb(sm))
        await update.callback_query.answer()

    async def _run_checkout(update, context):
        uid = update.effective_user.id
        data = _get_data(uid, BOT_ID)
        try:
            result = await asyncio.to_thread(checkout_svc.checkout_cart, db, uid,
                                              discount_code=data.get("discount_code") or None,
                                              shipping_method_id=data.get("cart_ship_id") or None,
                                              address_id=data.get("cart_address_id") or None)
        except ShopError as e:
            if e.code == "already_purchased":
                oid = e.data.get("previous_order_id")
                if oid:
                    mk = InlineKeyboardMarkup([[InlineKeyboardButton("📥 دریافت محصول", callback_data=f"mo_resend:{oid}")]])
                    await _edit_text(update, context, "⚠️ قبلاً سفارش داده‌اید.\n\nبرای دریافت روی دکمه زیر بزنید:", reply_markup=mk)
                else: await update.callback_query.answer("قبلاً سفارش داده‌اید.", show_alert=True)
                return
            if e.code == "shipping_required":
                ms = await asyncio.to_thread(db.list_shipping_methods, True)
                if ms: await _edit_text(update, context, "📦 روش ارسال را انتخاب کنید:", reply_markup=kb.shipping_methods_kb(ms))
                else: await _edit_text(update, context, "📦 لطفاً با پشتیبانی تماس بگیرید.")
                return
            if e.code == "address_required":
                addrs = await asyncio.to_thread(db.list_addresses, uid)
                txt = "📍 آدرس گیرنده را انتخاب یا ثبت کنید:"
                if not addrs: txt = "📍 لطفاً آدرس گیرنده را ثبت کنید:"
                await _edit_text(update, context, txt, reply_markup=kb.address_choices_kb(addrs)); return
            if e.code == "cart_empty": await update.callback_query.answer("سبد خالی است.", show_alert=True); return
            if isinstance(e, (InventoryError, CatalogError, WalletError)):
                await update.callback_query.answer(e.message, show_alert=True); return
            if isinstance(e, DiscountError) or e.code == "discount_exhausted":
                await update.callback_query.answer("کد تخفیف نامعتبر است.", show_alert=True); return
            await _edit_text(update, context, "❌ خطایی رخ داد."); return
        # Deliver digital files
        for it in result.items:
            if it.product_type != "digital": continue
            fs = await asyncio.to_thread(db.get_product_files, it.product_id)
            if fs:
                try: await deliver_pattern_to_user(bot, uid, it.product_name, [f["file_id"] for f in fs], 0, result.order_id)
                except: logger.exception("Digital delivery failed for #%s", result.order_id)
        sm = await asyncio.to_thread(cart_svc.cart_summary, db, uid)
        await _edit_text(update, context, "✅ سفارش ثبت شد! پس از تایید ادمین، فایل الگو ارسال میشود.",
                        reply_markup=kb.cart_menu_kb(sm))
        await _send_inline_main_menu(update, context, uid, db)

    async def _cb_cart_qty(update, context):
        try: op, iid_s = update.callback_query.data.split(":", 1); iid = int(iid_s)
        except: await update.callback_query.answer("❌ نامعتبر.", show_alert=True); return
        try:
            tgt = None
            for it in (await asyncio.to_thread(cart_svc.cart_summary, db, update.effective_user.id))["items"]:
                if it["id"] == iid: tgt = it
            if not tgt: raise CartError("قلم یافت نشد.", code="item_not_found")
            nq = int(tgt["quantity"]) + (1 if op == "cart_inc" else -1)
            if nq < 1: return await update.callback_query.answer("تعداد باید ≥ ۱ باشد.")
            await asyncio.to_thread(cart_svc.update_quantity, db, update.effective_user.id, iid, nq)
        except CartError as e:
            await update.callback_query.answer(e.message, show_alert=True); return
        await _show_cart(update, context)

    async def _cb_cart_del(update, context):
        try: iid = int(update.callback_query.data.split(":", 2)[1])
        except: await update.callback_query.answer("❌ نامعتبر.", show_alert=True); return
        await asyncio.to_thread(cart_svc.remove_from_cart, db, update.effective_user.id, iid)
        await _show_cart(update, context)

    async def _cb_cart_clear(update, context):
        await asyncio.to_thread(cart_svc.clear_cart, db, update.effective_user.id)
        await _show_cart(update, context)

    async def _cb_cart_show(update, context):
        await _show_cart(update, context)

    async def _cb_cart_checkout(update, context):
        await _run_checkout(update, bot)

    async def _cb_cart_ship(update, context):
        try: sid = int(update.callback_query.data.split(":", 2)[1])
        except: await update.callback_query.answer("❌ نامعتبر.", show_alert=True); return
        d = _get_data(update.effective_user.id, BOT_ID); d["cart_ship_id"] = sid
        _set_data(update.effective_user.id, d, BOT_ID)
        await _run_checkout(update, bot)

    async def _cb_cart_addr(update, context):
        try: aid = int(update.callback_query.data.split(":", 2)[1])
        except: await update.callback_query.answer("❌ نامعتبر.", show_alert=True); return
        d = _get_data(update.effective_user.id, BOT_ID); d["cart_address_id"] = aid
        _set_data(update.effective_user.id, d, BOT_ID)
        await _run_checkout(update, bot)

    async def _cb_cart_addr_new(update, context):
        _set_state(update.effective_user.id, CartFlow.waiting_address.state, BOT_ID)
        await _edit_text(update, context, "📍 آدرس گیرنده (استان، شهر، نشانی کامل، کد پستی) را ارسال کنید:", reply_markup=kb.cancel_kb())
        await update.callback_query.answer()

    async def _process_cart_addr(update, context):
        t = (update.message.text or "").strip()
        if not t: await context.bot.send_message(chat_id=update.effective_message.chat.id, text="لطفاً آدرس را متن ارسال کنید.", reply_markup=kb.cancel_kb()); return
        aid = await asyncio.to_thread(db.add_address, update.effective_user.id,
                                       update.effective_user.first_name or "", update.effective_user.username or "",
                                       "", "", t, "")
        d = _get_data(update.effective_user.id, BOT_ID); d["cart_address_id"] = aid
        _set_data(update.effective_user.id, d, BOT_ID); _clear(update.effective_user.id, BOT_ID)
        sm = await asyncio.to_thread(cart_svc.cart_summary, db, update.effective_user.id)
        await context.bot.send_message(chat_id=update.effective_message.chat.id, text="✅ آدرس ذخیره شد. تسویه را بزنید:", reply_markup=kb.cart_menu_kb(sm))

    async def _cb_cancel_flow(update, context):
        d = _get_data(update.effective_user.id, BOT_ID)
        oid = d.get("order_id")
        if oid:
            try: await db.reject_order(oid)
            except Exception: pass
        _clear(update.effective_user.id, BOT_ID)
        uid = update.effective_user.id
        await _edit_text(update, context, "❌ لغو شد.", reply_markup=kb.menu_for_user(db, uid))
        await _send_inline_main_menu(update, context, uid, db)
        await update.callback_query.answer()

    # ── Receipt handlers ────────────────────────────────────────
    async def _notify_admins_of_order(bot: Bot, oid: int, fid: str = None, rt: str = "photo"):
        order = await asyncio.to_thread(db.get_order, oid)
        if not order: return
        ur = await asyncio.to_thread(db.get_user, order["user_id"])
        un = (ur or {}).get("username", "") or ""; fn = (ur or {}).get("first_name", "") or ""
        for aid in await asyncio.to_thread(db.list_admins):
            try:
                cap = f"سفارش #{oid} | کاربر {fn} (@{un or '---'})"
                mk = kb.order_review_kb(oid)
                if rt == "document": await context.bot.send_document(aid, fid, caption=cap, reply_markup=mk)
                else: await context.bot.send_photo(aid, fid, caption=cap, reply_markup=mk)
            except Exception: logger.exception("Order notification failed for admin %s", aid)

    async def _receive_receipt(update, context):
        uid = update.effective_user.id
        data = _get_data(uid, BOT_ID)
        oid = data.get("order_id")
        if not oid:
            await context.bot.send_message(chat_id=update.effective_message.chat.id, text="درخواست معتبر یافت نشد."); _clear(uid, BOT_ID); return
        fid, rt = _receipt_payload(update)
        if not fid: return
        await asyncio.to_thread(db.set_order_receipt, oid, fid, rt or "photo")
        await _notify_admins_of_order(bot, oid, fid, rt or "photo")
        _clear(uid, BOT_ID)
        await context.bot.send_message(chat_id=update.effective_message.chat.id, text="✅ رسید ارسال شد. پس از تایید ادمین، فایل الگو ارسال میشود.",
                                    reply_markup=kb.menu_for_user(db, uid))
        await _send_inline_main_menu(update, context, uid, db)

    async def _receive_receipt_wrong(update, context):
        await context.bot.send_message(chat_id=update.effective_message.chat.id, text="لطفاً عکس رسید را بهصورت Photo بفرستید.")

    async def _receipt_fallback(update, context):
        if _get_state(update.effective_user.id, BOT_ID): return
        uid = update.effective_user.id
        fid, rt = _receipt_payload(update)
        if not fid: return
        try: order = await asyncio.to_thread(db.get_latest_pending_order_awaiting_receipt, uid)
        except Exception: order = None
        if order:
            try:
                await asyncio.to_thread(db.set_order_receipt, order["id"], fid, rt)
                await _notify_admins_of_order(bot, order["id"], fid, rt)
            except Exception:
                logger.exception("Fallback receipt failed for #%s", order["id"])
                await context.bot.send_message(chat_id=update.effective_message.chat.id, text="⚠️ خطایی رخ داد. دوباره تلاش کنید."); return
            await context.bot.send_message(chat_id=update.effective_message.chat.id, text="✅ رسید ارسال شد.", reply_markup=kb.menu_for_user(db, uid))
            await _send_inline_main_menu(update, context, uid, db); return
        try: topup = await asyncio.to_thread(db.get_latest_pending_topup_awaiting_receipt, uid)
        except Exception: topup = None
        if topup:
            try:
                await asyncio.to_thread(db.set_topup_receipt, topup["id"], fid, rt)
                ur = await asyncio.to_thread(db.get_user, uid)
                cap = f"👛 شارژ #{topup['id']}\n👤 {(ur or {}).get('first_name','')}\n💰 {topup['amount']:,} ت"
                for aid in await asyncio.to_thread(db.list_admins):
                    try:
                        sent = await context.bot.send_photo(aid, fid, caption=cap, reply_markup=kb.topup_review_kb(topup["id"]))
                        if sent: await asyncio.to_thread(db.set_topup_admin_message, topup["id"], aid, sent.message_id)
                    except Exception: pass
            except Exception:
                logger.exception("Fallback topup receipt failed for #%s", topup["id"])
                await context.bot.send_message(chat_id=update.effective_message.chat.id, text="⚠️ خطایی رخ داد."); return
            await context.bot.send_message(chat_id=update.effective_message.chat.id, text="✅ شارژ کیف پول ثبت شد.", reply_markup=kb.menu_for_user(db, uid))
            await _send_inline_main_menu(update, context, uid, db); return
        logger.warning("Photo/doc without state for user %s", uid)
        await context.bot.send_message(chat_id=update.effective_message.chat.id, text="❌ رسید ثبت نشد. لطفاً از منوی اصلی مسیر خرید/شارژ را طی کنید.",
                                    reply_markup=kb.menu_for_user(db, uid))
        await _send_inline_main_menu(update, context, uid, db)

    # ── Test config ─────────────────────────────────────────────
    async def _get_test_config(update, context):
        uid = update.effective_user.id
        if await asyncio.to_thread(db.count_test_files) == 0:
            await context.bot.send_message(chat_id=update.effective_message.chat.id, text="الگوی نمونه موجود نیست."); return
        ok, rem = await asyncio.to_thread(db.can_get_test, uid)
        if not ok:
            await context.bot.send_message(chat_id=update.effective_message.chat.id, text=f"شما {rem} بار گرفته‌اید. سقف: ۱ بار."); return
        samples = await asyncio.to_thread(db.get_sample_files)
        if not samples:
            await context.bot.send_message(chat_id=update.effective_message.chat.id, text="الگوی نمونه موجود نیست."); return
        f = samples[0]
        fid = f["file_id"] if isinstance(f, dict) else getattr(f, "file_id", None)
        if not fid: await context.bot.send_message(chat_id=update.effective_message.chat.id, text="خطا."); return
        await asyncio.to_thread(db.record_test_download, uid)
        await update.message.answer_document(fid, caption="🧪 الگوی نمونه رایگان خیاطی")

    # ── My orders ───────────────────────────────────────────────
    _MO = {"pending": "⏳ در انتظار", "approved": "✅ تایید شده", "rejected": "❌ رد"}
    def _my_orders_items(uid):
        items = []
        for o in db.get_user_orders(uid):
            if o["status"] == "rejected": continue
            pn = o["product_name"] or "محصول حذفشده"
            items.append({"cb_id": str(o["id"]), "label": f"{_MO.get(o['status'],'')} #{o['id']} {pn}"})
        return items
    def _get_owned_order(uid, cb_id):
        try: oid = int(cb_id)
        except: return None
        o = db.get_order(oid)
        return o if o and o["user_id"] == uid else None
    def _my_order_text(o):
        return f"🧵 سفارش #{o['id']} | {(o['product_name'] or 'محصول حذفشده')}\nوضعیت: {_MO.get(o['status'],o['status'])}\n💰 مبلغ: {o['final_price']:,} تومان"

    async def _show_my_orders_list(target, uid, edit=False):
        items = _my_orders_items(uid)
        if not items:
            t = "شما تاکنون سفارشی ثبت نکرده‌اید."
            if edit: await _edit_text(target, t)
            elif target.effective_message: await target.context.bot.send_message(chat_id=update.effective_message.chat.id, text=t)
            return
        t = "🧵 سفارشهای من\n\nیکی را انتخاب کنید:"
        mk = kb.my_orders_menu_kb(items)
        if edit: await _edit_text(target, t, reply_markup=mk)
        elif target.effective_message: await target.context.bot.send_message(chat_id=update.effective_message.chat.id, text=t, reply_markup=mk)

    async def _my_orders(update, context):
        await _show_my_orders_list(update, update.effective_user.id, edit=False)

    async def _cb_mo_back(update, context):
        await _show_my_orders_list(update, update.effective_user.id, edit=True)
        await update.callback_query.answer()

    async def _cb_mo_view(update, context):
        cid = update.callback_query.data.split(":", 2)[1]
        o = _get_owned_order(update.effective_user.id, cid)
        if not o or o.get("user_deleted"):
            await update.callback_query.answer("یافت نشد.", show_alert=True)
            await _show_my_orders_list(update, update.effective_user.id, edit=True); return
        await update.callback_query.answer()
        await _edit_text(update, context, _my_order_text(o), reply_markup=kb.my_order_item_kb(cid, True))

    async def _cb_mo_resend(update, context):
        cid = update.callback_query.data.split(":", 2)[1]
        o = _get_owned_order(update.effective_user.id, cid)
        if not o: await update.callback_query.answer("یافت نشد.", show_alert=True); return
        if o["status"] != "approved" or not o.get("file_ids"):
            await update.callback_query.answer("فایلی ثبت نشده.", show_alert=True); return
        await update.callback_query.answer("در حال ارسال...")
        fs = await asyncio.to_thread(db.get_product_files, o["product_id"])
        fm = {f["id"]: f["file_id"] for f in fs} if isinstance(fs, list) else {}
        rids = []
        for raw in str(o.get("file_ids") or "").split(","):
            r = raw.strip()
            if r:
                try: rids.append(int(r))
                except: pass
        prod = await asyncio.to_thread(db.get_product, o["product_id"])
        pn = prod["name"] if prod else "محصول حذفشده"
        miss = 0
        for rid in rids:
            fid = fm.get(rid)
            if not fid: miss += 1; continue
            try: await context.bot.send_document(update.effective_user.id, fid, caption=f"📥 دانلود مجدد #{o['id']} | {pn}")
            except: miss += 1
        if miss:
            try: await context.context.bot.send_message(update.effective_user.id, "⚠️ یکی از فایلها در دسترس نیست.")
            except: pass

    async def _cb_mo_del_ask(update, context):
        cid = update.callback_query.data.split(":", 2)[1]
        o = _get_owned_order(update.effective_user.id, cid)
        if not o or o.get("user_deleted"):
            await update.callback_query.answer("یافت نشد.", show_alert=True)
            await _show_my_orders_list(update, update.effective_user.id, edit=True); return
        await update.callback_query.answer()
        await _edit_text(update, context, "⚠️ آیا مطمئن هستید؟ این عمل غیرقابل بازگشت است.",
                        reply_markup=kb.my_order_delete_confirm_kb(cid))

    async def _cb_mo_del_ok(update, context):
        cid = update.callback_query.data.split(":", 2)[1]
        uid = update.effective_user.id
        try: oid = int(cid)
        except: await update.callback_query.answer("نامعتبر.", show_alert=True); return
        if not db.delete_owned_order(oid, uid):
            await update.callback_query.answer("یافت نشد.", show_alert=True)
        else:
            await update.callback_query.answer("✅ حذف شد.", show_alert=True)
        await _show_my_orders_list(update, uid, edit=True)

    # ── Referral ────────────────────────────────────────────────
    async def _referral_menu(update, context):
        s = await asyncio.to_thread(db.get_all_settings)
        if s.get("referral_button_enabled", "1") != "1":
            await context.bot.send_message(chat_id=update.effective_message.chat.id, text="سیستم زیرمجموعهگیری غیرفعال است."); return
        en = s.get("referral_enabled", "1") == "1"
        fc = s.get("referral_free_config_enabled", "0") == "1"
        ib = s.get("referral_invite_bonus_enabled", "0") == "1"
        if not (en or fc or ib):
            await context.bot.send_message(chat_id=update.effective_message.chat.id, text="سیستم زیرمجموعهگیری غیرفعال است."); return
        me = await context.bot.get_me()
        link = f"https://t.me/{me.username}?start=ref{update.effective_user.id}"
        st = await asyncio.to_thread(db.get_referral_stats, update.effective_user.id)
        L = ["🤝 زیرمجموعهگیری", "", f"لینک اختصاصی:\n{link}", ""]
        if en:
            pct = s.get("referral_percent", "10")
            mx = int(s.get("referral_commission_max_count", "0") or 0)
            L.append(f"💳 پورسانت {pct}٪ از اولین خرید هر زیرمجموعه{(' (فقط '+str(mx)+' نفر اول)' if mx else '')}.")
        if fc:
            L.append(f"🎁 با دعوت {s.get('referral_free_config_threshold','10')} نفر → الگوی رایگان.")
        if ib:
            am = int(s.get("referral_invite_bonus_amount", "0") or 0)
            imx = int(s.get("referral_invite_bonus_max_count", "0") or 0)
            L.append(f"💰 {am:,} تومان به ازای هر دعوت{(' (فقط '+str(imx)+' نفر اول)' if imx else '')}.")
        L += ["", f"👥 زیرمجموعهها: {st['count']}", f"👛 موجودی: {st['credit']:,} ت"]
        await context.bot.send_message(chat_id=update.effective_message.chat.id, text="\n".join(L))

    # ── Wallet ──────────────────────────────────────────────────
    async def _wallet_menu(update, context):
        bal = await asyncio.to_thread(db.get_wallet_credit, update.effective_user.id)
        await context.bot.send_message(chat_id=update.effective_message.chat.id, text=f"👛 کیف پول شما\n\nموجودی: {bal:,} تومان", reply_markup=kb.wallet_menu_kb())

    # ── Loyalty ─────────────────────────────────────────────────
    _LTX = {"purchase": "🛍", "purchase_refund": "↩️", "registration": "🎁",
            "referral": "🤝", "campaign": "🎯", "tier_bonus": "🏆",
            "adjustment": "🛠", "redeem": "🔄", "expire": "⌛️", "reversal": "🧾"}
    _LTXL = {"purchase": "خرید", "purchase_refund": "بازگشت", "registration": "ثبت‌نام",
             "referral": "معرفی", "campaign": "کمپین", "tier_bonus": "پاداش سطح",
             "adjustment": "تعدیل", "redeem": "تبدیل", "expire": "انقضا", "reversal": "لغو"}

    async def _loyalty_menu(update, context):
        await asyncio.to_thread(db.add_or_update_user, update.effective_user.id,
                                update.effective_user.username or "", update.effective_user.first_name or "")
        if not await asyncio.to_thread(loyalty.is_enabled, db):
            await context.bot.send_message(chat_id=update.effective_message.chat.id, text="باشگاه مشتریان غیرفعال است."); return
        s = await asyncio.to_thread(loyalty.get_summary, db, update.effective_user.id)
        T = ["🎁 <b>باشگاه مشتریان</b>", "",
             f"⭐ امتیاز: {s['current']}",
             f"🏆 سطح: {s['tier']['name'] if s.get('tier') else '—'}"]
        if s.get("next_tier"): T.append(f"📈 تا بعد: {s['points_to_next']} ({s['next_tier']['name']})")
        else: T.append("🎉 بالاترین سطح!")
        T += ["", f"هر {s['redeem_points']} امتیاز = {s['redeem_toman']:,} تومان"]
        await context.bot.send_message(chat_id=update.effective_message.chat.id, text="\n".join(T), parse_mode="HTML", reply_markup=kb.loyalty_menu_kb())

    async def _cb_loy_hist(update, context):
        _clear(update.effective_user.id, BOT_ID)
        try: pg = max(int(update.callback_query.data.split(":", 2)[1]), 0)
        except: pg = 0
        pp = 5
        rows, tot = await asyncio.to_thread(db.get_loyalty_history, update.effective_user.id, pp, pg * pp)
        sr = await asyncio.to_thread(db.ensure_loyalty_state, update.effective_user.id)
        pages = max(1, -(-tot // pp))
        L = [f"📜 تاریخچه (صفحه {pg+1}/{pages})", f"⭐ موجودی: {sr['current_points']}", ""]
        if not rows: L.append("تراکنشی ثبت نشده.")
        for r in rows:
            a = r["amount"]; al = f"⭐ <b>+{a}</b>" if a >= 0 else f"⭐ −{abs(a)}"
            ic = _LTX.get(r["tx_type"], "⭐")
            lb = _LTXL.get(r["tx_type"], r["tx_type"])
            ds = (r.get("description") or "").strip()
            tx = f"{ic} {lb}" + (f" — {ds}" if ds else "")
            try: dt = to_jalali_str(r["created_at"])
            except: dt = "-"
            L.append(f"{al}\n{tx}\n📅 {dt} — موجودی: {r['balance_after']}")
        await _edit_text(update, context, "\n".join(L), kb.loyalty_history_kb(pg, pg > 0, (pg+1)*pp < tot))
        await update.callback_query.answer()

    async def _cb_loy_back(update, context):
        _clear(update.effective_user.id, BOT_ID)
        if not await asyncio.to_thread(loyalty.is_enabled, db):
            await update.callback_query.answer("غیرفعال.", show_alert=True); return
        s = await asyncio.to_thread(loyalty.get_summary, db, update.effective_user.id)
        T = ["🎁 <b>باشگاه مشتریان</b>", "",
             f"⭐ امتیاز: {s['current']}", f"🏆 سطح: {s['tier']['name'] if s.get('tier') else '—'}"]
        await _edit_text(update, context, "\n".join(T), kb.loyalty_menu_kb())
        await update.callback_query.answer()

    async def _cb_loy_rules(update, context):
        _clear(update.effective_user.id, BOT_ID)
        if not await asyncio.to_thread(loyalty.is_enabled, db):
            await update.callback_query.answer("غیرفعال.", show_alert=True); return
        ss = await asyncio.to_thread(db.get_all_settings)
        def _i(k, d):
            try: return int(ss.get(k, d) or 0)
            except: return 0
        ppt = _i("loyalty_points_per_toman", "10000")
        rp = _i("loyalty_redeem_points", "100")
        rt = _i("loyalty_redeem_toman", "0")
        mr = _i("loyalty_min_redeem", "0")
        tiers = await asyncio.to_thread(loyalty.load_tiers, db)
        L = ["❓ قوانین باشگاه", ""]
        L.append(f"⭐ هر {ppt:,} تومان = ۱ امتیاز" if ppt > 0 else "⭐ امتیازدهی فعال نیست.")
        if tiers:
            L += ["", "سطوح:"]
            for t in tiers: L.append(f"• {t['name']} — از {t['min']:,} (ضریب {t['mult']/100:g}×)")
        L += ["", f"🔄 هر {rp} امتیاز = {rt:,} تومان"] if rp > 0 and rt > 0 else ["", "🔄 تبدیل فعال نیست."]
        if mr > 0: L.append(f"حداقل تبدیل: {mr}")
        L.append("امتیازها پس از تایید سفارش اعطا میشوند.")
        await _edit_text(update, context, "\n".join(L), kb.loyalty_rules_kb())
        await update.callback_query.answer()

    async def _cb_loy_redeem(update, context):
        s = await asyncio.to_thread(loyalty.get_summary, db, update.effective_user.id)
        if not s["redeem_enabled"]:
            await update.callback_query.answer("تبدیل فعال نیست.", show_alert=True); return
        _set_state(update.effective_user.id, LoyaltyRedeem.waiting_points.state, BOT_ID)
        try: await update.callback_query.message.edit_text(
            f"🔄 چند امتیاز؟ (مضرب {s['redeem_points']} — حداقل {s['min_redeem']})")
        except: await update.callback_query.context.bot.send_message(chat_id=update.effective_message.chat.id, text=...)
        await update.callback_query.answer()

    async def _process_loy_redeem(update, context):
        raw = (update.message.text or "").strip().replace(",", "")
        if not raw.isdigit() or int(raw) <= 0:
            await context.bot.send_message(chat_id=update.effective_message.chat.id, text="تعداد امتیاز (مثال: 200):"); return
        pts = int(raw); s = await asyncio.to_thread(loyalty.get_summary, db, update.effective_user.id)
        if not s["redeem_enabled"]: _clear(update.effective_user.id, BOT_ID); await context.bot.send_message(chat_id=update.effective_message.chat.id, text="تبدیل فعال نیست."); return
        if s["min_redeem"] > 0 and pts < s["min_redeem"]:
            await context.bot.send_message(chat_id=update.effective_message.chat.id, text=f"حداقل: {s['min_redeem']} امتیاز."); return
        if pts % s["redeem_points"] != 0:
            await context.bot.send_message(chat_id=update.effective_message.chat.id, text=f"مضربی از {s['redeem_points']}."); return
        if pts > s["current"]:
            await context.bot.send_message(chat_id=update.effective_message.chat.id, text="موجودی کافی نیست."); return
        toman = (pts // s["redeem_points"]) * s["redeem_toman"]
        await context.bot.send_message(chat_id=update.effective_message.chat.id, text=f"🔄 {pts} امتیاز → {toman:,} تومان", reply_markup=kb.loyalty_redeem_confirm_kb(pts))

    async def _cb_loy_redeem_ok(update, context):
        try: pts = int(update.callback_query.data.split(":", 2)[1])
        except: _clear(update.effective_user.id, BOT_ID); await update.callback_query.answer("نامعتبر.", show_alert=True); return
        try: result = await asyncio.to_thread(loyalty.redeem, db, update.effective_user.id, pts)
        except LoyaltyError as e: await update.callback_query.answer(str(e), show_alert=True); return
        except Exception:
            logger.exception("Loyalty redeem error"); await update.callback_query.answer("خطا.", show_alert=True); return
        _clear(update.effective_user.id, BOT_ID)
        await _edit_text(update, context, f"✅ {result['points']} امتیاز → {result['toman']:,} تومان.⭐ موجودی: {result['balance_after']}",
                        kb.loyalty_menu_kb())
        await update.callback_query.answer()

    # ── Wheel ───────────────────────────────────────────────────
    async def _wheel_of_fortune(update, context):
        if await asyncio.to_thread(db.get_setting, "wheel_enabled", "1") != "1":
            await context.bot.send_message(chat_id=update.effective_message.chat.id, text="گردونه شانس غیرفعال است."); return
        can, rem = await asyncio.to_thread(db.can_spin_wheel, update.effective_user.id)
        if not can:
            await context.bot.send_message(chat_id=update.effective_message.chat.id, text=f"⏳ حدود {int(rem)+1} ساعت دیگر امتحان کن."); return
        try: await context.bot.send_dice(update.effective_chat.id, emoji="🎰")
        except: await context.bot.send_message(chat_id=update.effective_message.chat.id, text="🎡 در حال چرخش...")
        await asyncio.sleep(2.5)
        await asyncio.to_thread(db.record_wheel_spin, update.effective_user.id)
        ws = await asyncio.to_thread(db.get_wheel_settings)
        won = secrets.randbelow(100) < ws["win_percent"]
        if won and ws["prizes"]:
            pct = secrets.choice(ws["prizes"])
            code, _ = await asyncio.to_thread(db.generate_wheel_prize_code, update.effective_user.id, pct)
            await context.bot.send_message(chat_id=update.effective_message.chat.id, text=f"🎉 تبریک! 🎟 کد {pct}٪: `{code}`\n⏳ اعتبار: {ws['expiry_hours']} ساعت",
                                        parse_mode="Markdown")
        else: await context.bot.send_message(chat_id=update.effective_message.chat.id, text="😔 امروز شانس با تو نبود!")

    # ── Topup ───────────────────────────────────────────────────
    async def _cb_start_topup(update, context):
        _set_state(update.effective_user.id, WalletTopup.waiting_amount.state, BOT_ID)
        await _edit_text(update, context, "💰 مبلغ شارژ (تومان، حداقل 1000):", reply_markup=kb.cancel_kb())
        await update.callback_query.answer()

    async def _process_topup_amount(update, context):
        t = (update.message.text or "").strip().replace(",", "")
        if not t.isdigit() or int(t) < 1000:
            await context.bot.send_message(chat_id=update.effective_message.chat.id, text="عدد معتبر و حداقل 1000 تومان:"); return
        _set_data(update.effective_user.id, {"topup_amount": int(t)}, BOT_ID)
        _set_state(update.effective_user.id, WalletTopup.waiting_receipt.state, BOT_ID)
        card = await asyncio.to_thread(db.get_setting, "card_number")
        holder = await asyncio.to_thread(db.get_setting, "card_holder")
        await context.bot.send_message(chat_id=update.effective_message.chat.id, text=f"مبلغ {int(t):,} ت به `{card}` به نام {holder} واریز کنید و عکس رسید را بفرستید:",
                                    parse_mode="Markdown", reply_markup=kb.payment_choice_kb())

    async def _receive_topup_receipt(update, context):
        uid = update.effective_user.id; data = _get_data(uid, BOT_ID)
        amt = data.get("topup_amount")
        if not amt: await context.bot.send_message(chat_id=update.effective_message.chat.id, text="درخواست معتبر یافت نشد."); _clear(uid, BOT_ID); return
        fid, rt = _receipt_payload(update)
        if not fid: return
        tid = await asyncio.to_thread(db.create_topup, uid, amt, fid, rt or "photo")
        ur = await asyncio.to_thread(db.get_user, uid)
        cap = f"👛 شارژ #{tid}\n👤 {(ur or {}).get('first_name','')}\n💰 {amt:,} ت"
        for aid in await asyncio.to_thread(db.list_admins):
            try:
                sent = await context.bot.send_photo(aid, fid, caption=cap, reply_markup=kb.topup_review_kb(tid))
                if sent: await asyncio.to_thread(db.set_topup_admin_message, tid, aid, sent.message_id)
            except Exception: logger.exception("Topup notif failed for %s", aid)
        _clear(uid, BOT_ID)
        await context.bot.send_message(chat_id=update.effective_message.chat.id, text="✅ ثبت شد. منتظر تایید باشید.", reply_markup=kb.menu_for_user(db, uid))
        await _send_inline_main_menu(update, context, uid, db)

    async def _topup_wrong(update, context):
        await context.bot.send_message(chat_id=update.effective_message.chat.id, text="عکس رسید را بهصورت Photo بفرستید.")

    # ── Contact ─────────────────────────────────────────────────
    async def _contact_start(update, context):
        _set_state(update.effective_user.id, ContactFlow.waiting_message.state, BOT_ID)
        ct = await asyncio.to_thread(db.get_setting, "contact_text")
        await context.bot.send_message(chat_id=update.effective_message.chat.id, text=ct, reply_markup=kb.cancel_kb())

    async def _contact_receive(update, context):
        u = update.effective_user
        if update.message.text:
            await asyncio.to_thread(db.add_support_message, u.id, "user", update.message.text)
        txt = f"📩 پیام جدید\n👤 {u.first_name or ''} (@{u.username or '---'})\n🆔 {u.id}\n\n✉️ {update.message.text}"
        tgt = await asyncio.to_thread(db.resolve_support_admin_for_message, u.id)
        admins = [tgt] if tgt else await asyncio.to_thread(db.list_admins)
        for aid in admins:
            try: await context.bot.send_message(aid, txt, reply_markup=kb.contact_reply_kb(u.id))
            except: logger.exception("Support msg failed for %s", aid)
        await context.bot.send_message(chat_id=update.effective_message.chat.id, text="پیام شما برای پشتیبانی ارسال شد.", reply_markup=kb.menu_for_user(db, u.id))
        await _send_inline_main_menu(update, context, u.id, db)
        _clear(u.id, BOT_ID)

    # ── mm: inline menu bridge ──────────────────────────────────
    async def _cb_mm(update, context):
        await update.callback_query.answer()
        key = update.callback_query.data.split(":", 2)[1]
        uid = update.effective_user.id
        class FakeU:
            effective_user = type('U', (), {"id": uid, "username": "", "first_name": ""})()
            effective_message = type('M', (), {"answer": lambda *a,**k: asyncio.sleep(0)})()
            effective_chat = type('C', (), {"id": uid})()
            bot = context.bot
        fu = FakeU()
        if key == "btn_buy": await _show_buy(fu, context)
        elif key == "btn_test": await _get_test_config(fu, context)
        elif key == "btn_my_orders": await _my_orders(fu, context)
        elif key == "btn_wallet": await _wallet_menu(fu, context)
        elif key == "btn_referral": await _referral_menu(fu, context)
        elif key == "btn_wheel": await _wheel_of_fortune(fu, context)
        elif key == "btn_loyalty": await _loyalty_menu(fu, context)
        elif key == "btn_contact": await _contact_start(fu, context)

    # ── Unknown text → menu ─────────────────────────────────────
    async def _unknown_text(update, context):
        uid = update.effective_user.id
        if _get_state(uid, BOT_ID): return
        await asyncio.to_thread(db.add_or_update_user, uid, update.effective_user.username or "", update.effective_user.first_name or "")
        w = await asyncio.to_thread(db.get_setting, "welcome_text")
        await context.bot.send_message(chat_id=update.effective_message.chat.id, text=w, reply_markup=kb.menu_for_user(db, uid))
        await _send_inline_main_menu(update, context, uid, db)

    # ── Build handler list ──────────────────────────────────────
    btn_buy = await asyncio.to_thread(db.get_setting, "btn_buy")
    btn_test = await asyncio.to_thread(db.get_setting, "btn_test")
    btn_my_orders = await asyncio.to_thread(db.get_setting, "btn_my_orders")
    btn_referral = await asyncio.to_thread(db.get_setting, "btn_referral")
    btn_wallet = await asyncio.to_thread(db.get_setting, "btn_wallet")
    btn_loyalty = await asyncio.to_thread(db.get_setting, "btn_loyalty")
    btn_wheel = await asyncio.to_thread(db.get_setting, "btn_wheel")
    btn_contact = await asyncio.to_thread(db.get_setting, "btn_contact")

    H = [
        CommandHandler("start", cmd_start),
        MessageHandler(filters.TEXT & filters.Regex(f"^{btn_buy}$"), _show_buy),
        CallbackQueryHandler(_cb_back_main, pattern="^back_main$"),
        CallbackQueryHandler(_cb_back_categories, pattern="^back_categories$"),
        CallbackQueryHandler(_cb_category, pattern="^cat:"),
        CallbackQueryHandler(_cb_product, pattern="^prod:"),
        CallbackQueryHandler(_cb_noop, pattern="^noop$"),
        CallbackQueryHandler(_cb_enter_code, pattern="^enter_code:"),
        MessageHandler(_state_msg_filter("waiting_code"), _process_disc_code),
        CallbackQueryHandler(_cb_buy_start, pattern="^buy_start:"),
        CallbackQueryHandler(_cb_cart_show, pattern="^cart_show$"),
        CallbackQueryHandler(_cb_cart_qty, pattern="^(?:cart_dec|cart_inc):"),
        CallbackQueryHandler(_cb_cart_del, pattern="^cart_del:"),
        CallbackQueryHandler(_cb_cart_clear, pattern="^cart_clear$"),
        CallbackQueryHandler(_cb_cart_checkout, pattern="^cart_checkout$"),
        CallbackQueryHandler(_cb_cart_ship, pattern="^cart_ship:"),
        CallbackQueryHandler(_cb_cart_addr, pattern="^cart_addr:"),
        CallbackQueryHandler(_cb_cart_addr_new, pattern="^cart_addr_new$"),
        MessageHandler(_state_msg_filter("waiting_address"), _process_cart_addr),
        CallbackQueryHandler(_cb_cancel_flow, pattern="^cancel_flow$"),
        MessageHandler(_PHOTO_DOC, _receive_receipt),
        MessageHandler(_state_msg_filter("waiting_receipt") & _NOT_PHOTO_DOC, _receive_receipt_wrong),
        MessageHandler(_PHOTO_DOC, _receipt_fallback),
        MessageHandler(filters.TEXT & filters.Regex(f"^{btn_test}$"), _get_test_config),
        MessageHandler(filters.TEXT & filters.Regex(f"^{btn_my_orders}$"), _my_orders),
        CallbackQueryHandler(_cb_mo_back, pattern="^mo_back$"),
        CallbackQueryHandler(_cb_mo_view, pattern="^mo_v:"),
        CallbackQueryHandler(_cb_mo_resend, pattern="^mo_resend:"),
        CallbackQueryHandler(_cb_mo_del_ask, pattern="^mo_del:"),
        CallbackQueryHandler(_cb_mo_del_ok, pattern="^mo_delok:"),
        MessageHandler(filters.TEXT & filters.Regex(f"^{btn_referral}$"), _referral_menu),
        MessageHandler(filters.TEXT & filters.Regex(f"^{btn_wallet}$"), _wallet_menu),
        MessageHandler(filters.TEXT & filters.Regex(f"^{btn_loyalty}$"), _loyalty_menu),
        CallbackQueryHandler(_cb_loy_hist, pattern="^loy_hist:"),
        CallbackQueryHandler(_cb_loy_back, pattern="^loy_back$"),
        CallbackQueryHandler(_cb_loy_rules, pattern="^loy_rules$"),
        CallbackQueryHandler(_cb_loy_redeem, pattern="^loy_redeem$"),
        MessageHandler(_state_msg_filter("waiting_points"), _process_loy_redeem),
        CallbackQueryHandler(_cb_loy_redeem_ok, pattern="^loy_redeem_ok:"),
        MessageHandler(filters.TEXT & filters.Regex(f"^{btn_wheel}$"), _wheel_of_fortune),
        CallbackQueryHandler(_cb_start_topup, pattern="^start_topup$"),
        MessageHandler(_state_msg_filter("waiting_amount"), _process_topup_amount),
        MessageHandler(_state_msg_filter("waiting_receipt") & _PHOTO_DOC, _receive_topup_receipt),
        MessageHandler(_state_msg_filter("waiting_receipt") & _NOT_PHOTO_DOC, _topup_wrong),
        MessageHandler(filters.TEXT & filters.Regex(f"^{btn_contact}$"), _contact_start),
        MessageHandler(_state_msg_filter("waiting_message"), _contact_receive),
        CallbackQueryHandler(_cb_mm, pattern="^mm:"),
        MessageHandler(filters.TEXT & ~filters.COMMAND, _unknown_text),
    ]
    return H


# ===================================================================
# Admin handlers (same patterns, adapted)
# ===================================================================

async def make_admin_handlers(db: Database, bot_token: str):
    BOT_ID = int(bot_token.split(":")[0])
    H = []

    def _admin_only(uid): return db.is_admin(uid)
    def _full_admin_only(uid): return db.is_full_admin(uid)
    def _senior_admin_only(uid): return db.is_senior_admin(uid)
    def _owner_only(uid): return db.is_owner(uid)

    async def _deny(call: Update, txt: str):
        await call.callback_query.answer(txt, show_alert=True)

    async def _safe_edit(call: Update, text: str, reply_markup=None):
        try:
            await call.callback_query.message.edit_text(text, reply_markup=reply_markup)
            return True
        except Exception as exc:
            if "not modified" in str(exc).lower(): return False
            raise

    async def _replace_view(call: Update, text: str, reply_markup=None):
        if call.callback_query and call.callback_query.message:
            try:
                await call.callback_query.message.edit_text(text, reply_markup=reply_markup)
                return True
            except Exception as exc:
                if "not modified" in str(exc).lower(): return False
                raise
        return False

    def _cid(data: str, prefix: str):
        try:
            p = (data or "").split(":", 1)
            if len(p) != 2 or p[0] != prefix or not p[1].isdigit(): return None
            return int(p[1])
        except: return None

    async def _notify_inline(bot, uid):
        try:
            ikb = await asyncio.to_thread(kb.inline_menu_for_user, db, uid)
            if ikb: await context.context.bot.send_message(uid, "📋 منو:", reply_markup=ikb)
        except: pass

    async def _send_receipt(bot, chat_id, fid, rt, cap, reply_markup=None):
        if (rt or "photo") == "document":
            return await context.bot.send_document(chat_id, fid, caption=cap, reply_markup=reply_markup)
        return await context.bot.send_photo(chat_id, fid, caption=cap, reply_markup=reply_markup)

    # --- Panel entry ---
    btn_panel = await asyncio.to_thread(db.get_setting, "btn_admin_panel")

    async def _open_panel(update, context):
        if not _admin_only(update.effective_user.id): return
        _clear(update.effective_user.id, BOT_ID)
        await context.bot.send_message(chat_id=update.effective_message.chat.id, text="🔧 پنل مدیریت:", reply_markup=kb.admin_panel_kb(db))

    async def _cb_back_panel(update, context):
        _clear(update.effective_user.id, BOT_ID)
        await _replace_view(update, "🔧 پنل مدیریت:", reply_markup=kb.admin_panel_kb(db))
        await update.callback_query.answer()

    async def _cb_noop(update, context):
        await update.callback_query.answer()

    async def _cb_admin_cat(update, context):
        if not _admin_only(update.effective_user.id): return
        _clear(update.effective_user.id, BOT_ID)
        ck = update.callback_query.data.split(":", 2)[1]
        title = kb.admin_category_label(ck)
        await _replace_view(update, f"{title}:", reply_markup=kb.admin_category_kb(db, ck))
        await update.callback_query.answer()

    # --- Categories ---
    async def _cb_admin_categories(update, context):
        if not _senior_admin_only(update.effective_user.id): return await _deny(update, "⛔️ دسترسی ندارید.")
        cats = await asyncio.to_thread(lambda: db.get_categories(active_only=True))
        await _replace_view(update, "📂 دستهبندیها:", reply_markup=kb.admin_categories_kb(cats))
        await update.callback_query.answer()

    async def _cb_cat_toggle(update, context):
        if not _senior_admin_only(update.effective_user.id): return await _deny(update, "⛔️.")
        cid = _cid(update.callback_query.data, "adm_cat_toggle")
        if not cid: await _deny(update, "❌."); return
        c = await asyncio.to_thread(db.get_category, cid)
        if not c: await _deny(update, "یافت نشد."); return
        await asyncio.to_thread(db.set_category_active, cid, not c.get("is_active", True))
        (await asyncio.to_thread(db.log_admin_action, update.effective_user.id, "category_toggle", f"#{cid}"))
        cats = await asyncio.to_thread(lambda: db.get_categories(active_only=True))
        await _safe_edit(update, "📂 دستهبندیها:", reply_markup=kb.admin_categories_kb(cats))
        await update.callback_query.answer()

    async def _cb_cat_del(update, context):
        if not _senior_admin_only(update.effective_user.id): return await _deny(update, "⛔️.")
        cid = _cid(update.callback_query.data, "adm_cat_del")
        if not cid: await _deny(update, "❌."); return
        prods = await asyncio.to_thread(db.get_products, cid)
        if prods: await _deny(update, "ابتدا محصولات را حذف کنید."); return
        await asyncio.to_thread(db.delete_category, cid)
        (await asyncio.to_thread(db.log_admin_action, update.effective_user.id, "category_delete", f"#{cid}"))
        cats = await asyncio.to_thread(lambda: db.get_categories(active_only=True))
        await _safe_edit(update, "📂 دستهبندیها:", reply_markup=kb.admin_categories_kb(cats))
        await update.callback_query.answer()

    async def _cb_cat_add(update, context):
        if not _senior_admin_only(update.effective_user.id): return await _deny(update, "⛔️.")
        _set_state(update.effective_user.id, "adm_add_cat", BOT_ID)
        await _safe_edit(update, "نام دستهبندی جدید:", reply_markup=kb.admin_back_kb())
        await update.callback_query.answer()

    async def _process_add_cat(update, context):
        if not _admin_only(update.effective_user.id): return
        name = (update.message.text or "").strip()
        if not name: await context.bot.send_message(chat_id=update.effective_message.chat.id, text="نام نمیتواند خالی باشد."); return
        await asyncio.to_thread(db.add_category, name)
        (await asyncio.to_thread(db.log_admin_action, update.effective_user.id, "category_add", name))
        _clear(update.effective_user.id, BOT_ID)
        await context.bot.send_message(chat_id=update.effective_message.chat.id, text="✅ اضافه شد.", reply_markup=kb.admin_category_kb(db, "products"))

    # --- Products ---
    async def _cb_admin_products(update, context):
        if not _senior_admin_only(update.effective_user.id): return await _deny(update, "⛔️.")
        cats = await asyncio.to_thread(lambda: db.get_categories(active_only=True))
        await _replace_view(update, "📦 مدیریت محصولات:", reply_markup=kb.admin_products_categories_kb(cats))
        await update.callback_query.answer()

    async def _cb_prod_cat(update, context):
        if not _senior_admin_only(update.effective_user.id): return await _deny(update, "⛔️.")
        cid = int(update.callback_query.data.split(":", 2)[1])
        prods = await asyncio.to_thread(db.get_products, cid)
        await _safe_edit(update, "📦 محصولات:", reply_markup=kb.admin_products_list_kb(db, prods))
        await update.callback_query.answer()

    async def _cb_prod_toggle(update, context):
        if not _senior_admin_only(update.effective_user.id): return await _deny(update, "⛔️.")
        pid = _cid(update.callback_query.data, "adm_prod_toggle")
        if not pid: await _deny(update, "❌."); return
        await asyncio.to_thread(db.toggle_product, pid)
        (await asyncio.to_thread(db.log_admin_action, update.effective_user.id, "product_toggle", f"#{pid}"))
        p = await asyncio.to_thread(db.get_product, pid)
        prods = await asyncio.to_thread(db.get_products, p["category_id"] if p else 0)
        await _safe_edit(update, "📦 محصولات:", reply_markup=kb.admin_products_list_kb(db, prods))
        await update.callback_query.answer()

    async def _cb_prod_del(update, context):
        if not _senior_admin_only(update.effective_user.id): return await _deny(update, "⛔️.")
        pid = _cid(update.callback_query.data, "adm_prod_del")
        if not pid: await _deny(update, "❌."); return
        prod = await asyncio.to_thread(db.get_product, pid)
        if not prod: await _deny(update, "یافت نشد."); return
        await asyncio.to_thread(db.delete_product, pid)
        (await asyncio.to_thread(db.log_admin_action, update.effective_user.id, "product_delete", f"#{pid}"))
        prods = await asyncio.to_thread(db.get_products, prod["category_id"])
        await _safe_edit(update, "📦 محصولات:", reply_markup=kb.admin_products_list_kb(db, prods))
        await update.callback_query.answer()

    async def _cb_prod_add(update, context):
        if not _senior_admin_only(update.effective_user.id): return await _deny(update, "⛔️.")
        _set_state(update.effective_user.id, "adm_newprod_cat", BOT_ID)
        cats = await asyncio.to_thread(lambda: db.get_categories(active_only=True))
        await _replace_view(update, "📂 دسته‌بندی محصول جدید:", reply_markup=kb.admin_pick_category_kb(cats, "adm_newprod_cat"))
        await update.callback_query.answer()

    async def _cb_pick_newprod_cat(update, context):
        if not _senior_admin_only(update.effective_user.id): return await _deny(update, "⛔️.")
        cid = int(update.callback_query.data.split(":", 2)[1])
        _set_data(update.effective_user.id, {"newprod_cat": cid}, BOT_ID)
        _set_state(update.effective_user.id, "adm_newprod_name", BOT_ID)
        await _safe_edit(update, "نام محصول:", reply_markup=kb.admin_back_kb("adm_products"))
        await update.callback_query.answer()

    async def _process_newprod_name(update, context):
        if not _admin_only(update.effective_user.id): return
        name = (update.message.text or "").strip()
        if not name: await context.bot.send_message(chat_id=update.effective_message.chat.id, text="نام خالی نیست."); return
        d = _get_data(update.effective_user.id, BOT_ID)
        _set_data(update.effective_user.id, {**d, "newprod_name": name}, BOT_ID)
        _set_state(update.effective_user.id, "adm_newprod_price", BOT_ID)
        await context.bot.send_message(chat_id=update.effective_message.chat.id, text="قیمت (تومان):", reply_markup=kb.admin_back_kb("adm_products"))

    async def _process_newprod_price(update, context):
        if not _admin_only(update.effective_user.id): return
        t = (update.message.text or "").strip()
        if not t.isdigit(): await context.bot.send_message(chat_id=update.effective_message.chat.id, text="عدد صحیح:"); return
        d = _get_data(update.effective_user.id, BOT_ID)
        _set_data(update.effective_user.id, {**d, "newprod_price": int(t)}, BOT_ID)
        _set_state(update.effective_user.id, "adm_newprod_desc", BOT_ID)
        await context.bot.send_message(chat_id=update.effective_message.chat.id, text="توضیحات (یا /skip):", reply_markup=kb.admin_back_kb("adm_products"))

    async def _process_newprod_desc(update, context):
        if not _admin_only(update.effective_user.id): return
        d = _get_data(update.effective_user.id, BOT_ID)
        _set_data(update.effective_user.id, {**d, "newprod_desc": (update.message.text or "").strip()}, BOT_ID)
        _set_state(update.effective_user.id, "adm_newprod_preview", BOT_ID)
        await context.bot.send_message(chat_id=update.effective_message.chat.id, text="عکس پیشنمایش (Photo) یا /skip:", reply_markup=kb.admin_back_kb("adm_products"))

    async def _process_newprod_preview(update, context):
        if not _admin_only(update.effective_user.id): return
        if not update.message.photo:
            await context.bot.send_message(chat_id=update.effective_message.chat.id, text="عکس را بهصورت Photo بفرستید یا /skip:"); return
        d = _get_data(update.effective_user.id, BOT_ID)
        _set_data(update.effective_user.id, {**d, "newprod_preview": update.message.photo[-1].file_id}, BOT_ID)
        _set_state(update.effective_user.id, "adm_newprod_files", BOT_ID)
        await context.bot.send_message(chat_id=update.effective_message.chat.id, text="فایلهای الگو (PDF و مشابه) — بعد از پایان «تمام شد»:", reply_markup=kb.files_upload_done_kb())

    async def _process_newprod_files(update, context):
        if not _admin_only(update.effective_user.id): return
        fname = update.message.document.file_name or ""
        if not cfg.is_allowed_product_filename(fname):
            allowed = "، ".join(e.upper().lstrip(".") for e in cfg.ALLOWED_PRODUCT_FILE_EXTENSIONS)
            await context.bot.send_message(chat_id=update.effective_message.chat.id, text=f"⛔️ پسوند مجاز نیست: {fname.rsplit('.',1)[-1]}\n{allowed}")
            return
        d = _get_data(update.effective_user.id, BOT_ID)
        fs = list(d.get("newprod_files") or [])
        fs.append(update.message.document.file_id)
        _set_data(update.effective_user.id, {**d, "newprod_files": fs}, BOT_ID)
        await context.bot.send_message(chat_id=update.effective_message.chat.id, text=f"📎 فایل {len(fs)} ثبت شد.")

    async def _cb_newprod_files_done(update, context):
        if not _senior_admin_only(update.effective_user.id): return await _deny(update, "⛔️.")
        d = _get_data(update.effective_user.id, BOT_ID)
        cid, name, price, desc, preview = d.get("newprod_cat"), d.get("newprod_name"), d.get("newprod_price"), d.get("newprod_desc",""), d.get("newprod_preview")
        fs = [f for f in (d.get("newprod_files") or []) if f]
        if not all([cid, name, price]):
            await _deny(update, "لطفاً مراحل افزودن محصول را از ابتدا طی کنید.", show_alert=True); return
        pid = await asyncio.to_thread(db.add_product, cid, name, int(price), desc, preview or "")
        for f in fs: await asyncio.to_thread(db.add_product_file, pid, f)
        (await asyncio.to_thread(db.log_admin_action, update.effective_user.id, "product_add", name))
        _clear(update.effective_user.id, BOT_ID)
        prods = await asyncio.to_thread(db.get_products, cid)
        await _replace_view(update, f"✅ «{name}» اضافه شد.", reply_markup=kb.admin_products_list_kb(db, prods))
        await update.callback_query.answer()

    # --- Product files management ---
    async def _cb_prod_files(update, context):
        if not _senior_admin_only(update.effective_user.id): return await _deny(update, "⛔️.")
        prods = await asyncio.to_thread(db.get_all_products)
        await _replace_view(update, "📎 فایلهای الگو:", reply_markup=kb.product_files_pick_kb(prods))
        await update.callback_query.answer()

    async def _cb_file_pick(update, context):
        if not _senior_admin_only(update.effective_user.id): return await _deny(update, "⛔️.")
        pid = _cid(update.callback_query.data, "adm_file_pick")
        if not pid: await _deny(update, "❌."); return
        prod = await asyncio.to_thread(db.get_product, pid)
        if not prod: await _deny(update, "محصول یافت نشد."); return
        await _replace_view(update, f"📎 {prod['name']}:", reply_markup=kb.product_files_kb(db, pid))
        await update.callback_query.answer()

    async def _cb_file_del(update, context):
        if not _senior_admin_only(update.effective_user.id): return await _deny(update, "⛔️.")
        parts = (update.callback_query.data or "").split(":")
        if len(parts) != 3 or not parts[1].isdigit() or not parts[2].isdigit():
            await _deny(update, "❌."); return
        rid, pid = int(parts[1]), int(parts[2])
        prod = await asyncio.to_thread(db.get_product, pid)
        if not prod: await _deny(update, "محصول یافت نشد."); return
        fs = await asyncio.to_thread(db.get_product_files, pid)
        tgt = next((f for f in fs if f["id"] == rid), None)
        if not tgt: await _deny(update, "فایل قبلاً حذف شده."); return
        await asyncio.to_thread(db.delete_product_file, tgt["file_id"])
        (await asyncio.to_thread(db.log_admin_action, update.effective_user.id, "product_file_delete", f"#{rid}"))
        await _safe_edit(update, f"📎 {prod['name']}:", reply_markup=kb.product_files_kb(db, pid))
        await update.callback_query.answer()

    async def _cb_file_add(update, context):
        if not _senior_admin_only(update.effective_user.id): return await _deny(update, "⛔️.")
        pid = _cid(update.callback_query.data, "adm_file_add")
        if not pid: await _deny(update, "❌."); return
        prod = await asyncio.to_thread(db.get_product, pid)
        if not prod: await _deny(update, "محصول یافت نشد."); return
        _set_data(update.effective_user.id, {"files_pid": pid, "files": []}, BOT_ID)
        _set_state(update.effective_user.id, "adm_prod_files_waiting", BOT_ID)
        await _safe_edit(update, f"فایلهای «{prod['name']}» را بفرستید (PDF و مشابه). «تمام شد»:", reply_markup=kb.files_upload_done_kb())
        await update.callback_query.answer()

    async def _process_prod_files(update, context):
        if not _admin_only(update.effective_user.id): return
        fname = update.message.document.file_name or ""
        if not cfg.is_allowed_product_filename(fname):
            allowed = "، ".join(e.upper().lstrip(".") for e in cfg.ALLOWED_PRODUCT_FILE_EXTENSIONS)
            await context.bot.send_message(chat_id=update.effective_message.chat.id, text=f"⛔️ {fname.rsplit('.',1)[-1]} مجاز نیست.\n{allowed}")
            return
        d = _get_data(update.effective_user.id, BOT_ID)
        fs = list(d.get("files") or [])
        fs.append(update.message.document.file_id)
        _set_data(update.effective_user.id, {**d, "files": fs}, BOT_ID)
        await context.bot.send_message(chat_id=update.effective_message.chat.id, text=f"📎 {len(fs)} ثبت شد.")

    async def _cb_prod_files_done(update, context):
        if not _senior_admin_only(update.effective_user.id): return await _deny(update, "⛔️.")
        d = _get_data(update.effective_user.id, BOT_ID)
        pid = d.get("files_pid"); fs = [f for f in (d.get("files") or []) if f]
        if not pid or not fs:
            await _deny(update, "هیچ فایلی ثبت نشده.", show_alert=True); return
        prod = await asyncio.to_thread(db.get_product, pid)
        if not prod: _clear(update.effective_user.id, BOT_ID); await _deny(update, "محصول حذف شده."); return
        added, dup = await asyncio.to_thread(db.add_product_files, pid, fs)
        (await asyncio.to_thread(db.log_admin_action, update.effective_user.id, "product_files_add", f"#{added} فایل"))
        _clear(update.effective_user.id, BOT_ID)
        await _replace_view(update, f"📎 {prod['name']}\n✅ {added} فایل اضافه شد.", reply_markup=kb.product_files_kb(db, pid))
        await update.callback_query.answer()

    # --- Pending orders ---
    async def _cb_pending_orders(update, context):
        if not _admin_only(update.effective_user.id): return
        orders = await asyncio.to_thread(db.get_pending_orders)
        if not orders: await _deny(update, "سفارشی در انتظار نیست.", show_alert=True); return
        await _replace_view(update, "🧾 سفارشهای در انتظار:", reply_markup=kb.pending_orders_kb(orders))
        await update.callback_query.answer()

    async def _cb_view_order(update, context):
        if not _admin_only(update.effective_user.id): return
        oid = _cid(update.callback_query.data, "view_order")
        if not oid: await _deny(update, "❌."); return
        order = await asyncio.to_thread(db.get_order, oid)
        if not order: await _deny(update, "یافت نشد."); return
        prod = await asyncio.to_thread(db.get_product, order["product_id"])
        qty = order.get("quantity") or 1
        cap = f"سفارش #{oid}\nکاربر: {order['user_id']}\nمحصول: {prod['name'] if prod else '---'}"
        if qty > 1: cap += f" ×{qty}"
        if order.get("receipt_file_id"):
            rt = order.get("receipt_type") or "photo"
            await _send_receipt(bot, update.effective_user.id, order["receipt_file_id"], rt, cap, kb.order_review_kb(oid))
        else:
            await update.callback_query.context.bot.send_message(chat_id=update.effective_message.chat.id, text=cap, reply_markup=kb.order_review_kb(oid))
        await update.callback_query.answer()

    async def _cb_order_approve(update, context):
        if not _full_admin_only(update.effective_user.id): return
        oid = _cid(update.callback_query.data, "order_approve")
        if not oid: await _deny(update, "❌."); return
        order = await asyncio.to_thread(db.get_order, oid)
        if not order or order["status"] != "pending":
            await _deny(update, "قبلاً بررسی شده."); return
        files = await asyncio.to_thread(db.get_product_files, order["product_id"])
        if not files: await _deny(update, "فایلی آپلود نشده."); return
        ok, _ = await asyncio.to_thread(service_orders.decide_order, db, oid, True,
                                         [f["id"] for f in files], str(update.effective_user.id))
        if not ok: await _deny(update, "قبلاً بررسی شده."); return
        try:
            ai = await asyncio.to_thread(service_orders.award_after_approve, db, oid)
            awarded = ai.get("loyalty_points") or 0
            ri = ai.get("referral")
        except: logger.exception("award_after_approve error"); awarded, ri = 0, None
        prod = await asyncio.to_thread(db.get_product, order["product_id"])
        pn = prod["name"] if prod else "---"
        (await asyncio.to_thread(db.log_admin_action, update.effective_user.id, "order_approve",
                                 f"#{oid} | {order['user_id']} | {pn} | {(order.get('final_price') or (prod['price'] if prod else 0)):,}"))
        if ri:
            try: await context.context.bot.send_message(ri[1], f"🤝 زیرمجموعه شما خرید کرد!\n💰 {ri[0]:,} تومان پورسانت.")
            except: pass
        try:
            ln = f"\n🎁 {awarded} امتیاز باشگاه مشتریان" if awarded > 0 else ""
            await context.context.bot.send_message(order["user_id"], f"✅ خرید شما تایید شد!\n🧵 {pn}{ln}")
            await deliver_pattern_to_user(bot, order["user_id"], pn, [f["file_id"] for f in files],
                                           final_price=order.get("final_price"), order_id=oid)
            await _notify_inline(bot, order["user_id"])
        except: pass
        nc = (update.callback_query.message.caption or update.callback_query.message.text or "") + "\n\n✅ تایید شد."
        try: await context.bot.edit_message_caption(chat_id=update.effective_user.id, message_id=update.callback_query.message.message_id, caption=nc)
        except:
            try: await _safe_edit(update, (update.callback_query.message.text or "") + "\n\n✅ تایید شد.")
            except: pass
        await update.callback_query.answer()

    async def _cb_order_reject(update, context):
        if not _full_admin_only(update.effective_user.id): return
        oid = _cid(update.callback_query.data, "order_reject")
        if not oid: await _deny(update, "❌."); return
        order = await asyncio.to_thread(db.get_order, oid)
        if not order or order["status"] != "pending":
            await _deny(update, "قبلاً بررسی شده."); return
        ok, _ = await asyncio.to_thread(service_orders.decide_order, db, oid, False, actor=str(update.effective_user.id))
        if not ok: await _deny(update, "قبلاً بررسی شده."); return
        try: await asyncio.to_thread(service_orders.refund_loyalty_for_rejected, db, oid)
        except: logger.exception("refund_loyalty error")
        (await asyncio.to_thread(db.log_admin_action, update.effective_user.id, "order_reject", f"#{oid} | {order['user_id']}"))
        try:
            await context.context.bot.send_message(order["user_id"], "❌ رسید شما تایید نشد. با پشتیبانی تماس بگیرید.")
            await _notify_inline(bot, order["user_id"])
        except: pass
        nc = (update.callback_query.message.caption or update.callback_query.message.text or "") + "\n\n❌ رد شد."
        try: await context.bot.edit_message_caption(chat_id=update.effective_user.id, message_id=update.callback_query.message.message_id, caption=nc)
        except:
            try: await _safe_edit(update, (update.callback_query.message.text or "") + "\n\n❌ رد شد.")
            except: pass
        await update.callback_query.answer()

    # --- Pending topups ---
    async def _cb_pending_topups(update, context):
        if not _full_admin_only(update.effective_user.id): return await _deny(update, "⛔️.")
        topups = await asyncio.to_thread(db.get_pending_topups)
        if not topups: await _deny(update, "درخواستی در انتظار نیست.", show_alert=True); return
        await _replace_view(update, "👛 درخواستهای شارژ:", reply_markup=kb.pending_topups_kb(topups))
        await update.callback_query.answer()

    async def _cb_view_topup(update, context):
        if not _full_admin_only(update.effective_user.id): return await _deny(update, "⛔️.")
        tid = _cid(update.callback_query.data, "view_topup")
        if not tid: await _deny(update, "❌."); return
        tu = await asyncio.to_thread(db.get_topup, tid)
        if not tu: await _deny(update, "یافت نشد."); return
        cap = f"شارژ #{tid}\nکاربر: {tu['user_id']}\nمبلغ: {tu['amount']:,} ت"
        if tu.get("receipt_file_id"):
            rt = tu.get("receipt_type") or "photo"
            await _send_receipt(bot, update.effective_user.id, tu["receipt_file_id"], rt, cap, kb.topup_review_kb(tid))
        else:
            await update.callback_query.context.bot.send_message(chat_id=update.effective_message.chat.id, text=cap, reply_markup=kb.topup_review_kb(tid))
        await update.callback_query.answer()

    async def _cb_topup_approve(update, context):
        if not _full_admin_only(update.effective_user.id): return await _deny(update, "⛔️.")
        tid = _cid(update.callback_query.data, "topup_approve")
        if not tid: await _deny(update, "❌."); return
        tu = await asyncio.to_thread(db.get_topup, tid)
        if not tu or tu["status"] != "pending":
            await _deny(update, "قبلاً بررسی شده."); return
        await asyncio.to_thread(db.approve_topup, tid)
        nb = await asyncio.to_thread(db.get_wallet_credit, tu["user_id"])
        (await asyncio.to_thread(db.log_admin_action, update.effective_user.id, "topup_approve",
                                 f"#{tid} | {tu['user_id']} | {tu['amount']:,} | جدید: {nb:,}"))
        try:
            await context.context.bot.send_message(tu["user_id"], f"✅ شارژ {tu['amount']:,} ت تایید شد!\n👛 موجودی: {nb:,} ت")
            await _notify_inline(bot, tu["user_id"])
        except: pass
        nc = (update.callback_query.message.caption or update.callback_query.message.text or "") + "\n\n✅ تایید شد."
        try: await context.bot.edit_message_caption(chat_id=update.effective_user.id, message_id=update.callback_query.message.message_id, caption=nc)
        except:
            try: await _safe_edit(update, (update.callback_query.message.text or "") + "\n\n✅ تایید شد.")
            except: pass
        await update.callback_query.answer()

    async def _cb_topup_reject(update, context):
        if not _full_admin_only(update.effective_user.id): return await _deny(update, "⛔️.")
        tid = _cid(update.callback_query.data, "topup_reject")
        if not tid: await _deny(update, "❌."); return
        tu = await asyncio.to_thread(db.get_topup, tid)
        if not tu or tu["status"] != "pending":
            await _deny(update, "قبلاً بررسی شده."); return
        await asyncio.to_thread(db.reject_topup, tid)
        (await asyncio.to_thread(db.log_admin_action, update.effective_user.id, "topup_reject", f"#{tid} | {tu['user_id']}"))
        try:
            await context.context.bot.send_message(tu["user_id"], "❌ شارژ کیف پول تایید نشد.")
            await _notify_inline(bot, tu["user_id"])
        except: pass
        nc = (update.callback_query.message.caption or update.callback_query.message.text or "") + "\n\n❌ رد شد."
        try: await context.bot.edit_message_caption(chat_id=update.effective_user.id, message_id=update.callback_query.message.message_id, caption=nc)
        except:
            try: await _safe_edit(update, (update.callback_query.message.text or "") + "\n\n❌ رد شد.")
            except: pass
        await update.callback_query.answer()

    # --- Discounts ---
    async def _cb_discounts_menu(update, context):
        if not _senior_admin_only(update.effective_user.id): return await _deny(update, "⛔️.")
        codes = await asyncio.to_thread(db.list_discount_codes)
        await _replace_view(update, "🎟 کدهای تخفیف:", reply_markup=kb.discount_codes_kb(codes))
        await update.callback_query.answer()

    async def _cb_disc_toggle(update, context):
        if not _senior_admin_only(update.effective_user.id): return await _deny(update, "⛔️.")
        cid = _cid(update.callback_query.data, "adm_disc_toggle")
        if not cid: await _deny(update, "❌."); return
        await asyncio.to_thread(db.toggle_discount_code, cid)
        (await asyncio.to_thread(db.log_admin_action, update.effective_user.id, "discount_toggle", f"#{cid}"))
        codes = await asyncio.to_thread(db.list_discount_codes)
        await _safe_edit(update, "🎟 کدهای تخفیف:", reply_markup=kb.discount_codes_kb(codes))
        await update.callback_query.answer()

    async def _cb_disc_del(update, context):
        if not _senior_admin_only(update.effective_user.id): return await _deny(update, "⛔️.")
        cid = _cid(update.callback_query.data, "adm_disc_del")
        if not cid: await _deny(update, "❌."); return
        await asyncio.to_thread(db.delete_discount_code, cid)
        (await asyncio.to_thread(db.log_admin_action, update.effective_user.id, "discount_delete", f"#{cid}"))
        codes = await asyncio.to_thread(db.list_discount_codes)
        await _safe_edit(update, "🎟 کدهای تخفیف:", reply_markup=kb.discount_codes_kb(codes))
        await update.callback_query.answer()

    async def _cb_disc_add(update, context):
        if not _senior_admin_only(update.effective_user.id): return await _deny(update, "⛔️.")
        _set_state(update.effective_user.id, "adm_disc_code", BOT_ID)
        await _safe_edit(update, "نام کد تخفیف:", reply_markup=kb.admin_back_kb())
        await update.callback_query.answer()

    async def _process_disc_code(update, context):
        if not _senior_admin_only(update.effective_user.id): return
        code = (update.message.text or "").strip()
        if await asyncio.to_thread(db.get_discount_code, code):
            await context.bot.send_message(chat_id=update.effective_message.chat.id, text="این کد وجود دارد. نام دیگر:"); return
        _set_data(update.effective_user.id, {"disc_code": code}, BOT_ID)
        _set_state(update.effective_user.id, "adm_disc_tv", BOT_ID)
        await context.bot.send_message(chat_id=update.effective_message.chat.id, text="فرمت: `percent 20` یا `fixed 50000`", parse_mode="Markdown")

    async def _process_disc_tv(update, context):
        if not _senior_admin_only(update.effective_user.id): return
        parts = (update.message.text or "").strip().split()
        if len(parts) != 2 or parts[0].lower() not in ("percent", "fixed") or not parts[1].isdigit():
            await context.bot.send_message(chat_id=update.effective_message.chat.id, text="فرمت: `percent 20` یا `fixed 50000`"); return
        kind, val = parts[0].lower(), int(parts[1])
        d = _get_data(update.effective_user.id, BOT_ID)
        if kind == "percent": d["disc_pct"] = val; d["disc_fix"] = None
        else: d["disc_pct"] = None; d["disc_fix"] = val
        _set_data(update.effective_user.id, d, BOT_ID)
        _set_state(update.effective_user.id, "adm_disc_mu", BOT_ID)
        await context.bot.send_message(chat_id=update.effective_message.chat.id, text="سقف استفاده (0=نامحدود):")

    async def _process_disc_mu(update, context):
        if not _senior_admin_only(update.effective_user.id): return
        t = (update.message.text or "").strip()
        if not t.isdigit(): await context.bot.send_message(chat_id=update.effective_message.chat.id, text="عدد:"); return
        d = _get_data(update.effective_user.id, BOT_ID)
        await asyncio.to_thread(db.create_discount_code, d["disc_code"], percent=d.get("disc_pct"), fixed_amount=d.get("disc_fix"), max_uses=int(t))
        (await asyncio.to_thread(db.log_admin_action, update.effective_user.id, "discount_add", d["disc_code"]))
        _clear(update.effective_user.id, BOT_ID)
        await context.bot.send_message(chat_id=update.effective_message.chat.id, text=f"✅ کد «{d['disc_code']}» ساخته شد.", reply_markup=kb.discount_codes_kb(await asyncio.to_thread(db.list_discount_codes)))

    # --- Force join ---
    async def _cb_forcejoin_menu(update, context):
        if not _full_admin_only(update.effective_user.id): return await _deny(update, "⛔️.")
        await _replace_view(update, "📢 عضویت اجباری:", reply_markup=kb.admin_forcejoin_menu_kb(db))
        await update.callback_query.answer()

    async def _cb_forcejoin_toggle(update, context):
        if not _full_admin_only(update.effective_user.id): return await _deny(update, "⛔️.")
        s = await asyncio.to_thread(db.get_force_join_settings)
        if not s.get("enabled") and not s.get("channel"):
            await _deny(update, "اول کانال را تنظیم کنید.", show_alert=True); return
        cur = await asyncio.to_thread(db.get_setting, "force_join_enabled", "0")
        await asyncio.to_thread(db.set_setting, "force_join_enabled", "0" if cur == "1" else "1")
        await _safe_edit(update, "📢 عضویت اجباری:", reply_markup=kb.admin_forcejoin_menu_kb(db))
        await update.callback_query.answer()

    async def _cb_forcejoin_set_channel(update, context):
        if not _full_admin_only(update.effective_user.id): return await _deny(update, "⛔️.")
        _set_state(update.effective_user.id, "adm_forcejoin_ch", BOT_ID)
        await _safe_edit(update, "آیدی کانال (@channel یا عددی):", reply_markup=kb.admin_back_kb("adm_forcejoin_menu"))
        await update.callback_query.answer()

    async def _process_forcejoin_ch(update, context):
        if not _full_admin_only(update.effective_user.id): return
        ch = (update.message.text or "").strip()
        if not ch.startswith("@") and not ch.startswith("-"): ch = "@" + ch
        try:
            chat = await context.bot.get_chat(ch)
            mem = await context.bot.get_chat_member(ch, bot.id)
            if mem.status not in ("administrator", "creator"): raise ValueError
        except:
            await context.bot.send_message(chat_id=update.effective_message.chat.id, text="⛔️ دسترسی ندارم. ربات باید ادمین کانال باشد.", parse_mode="Markdown",
                                         reply_markup=kb.admin_back_kb("adm_forcejoin_menu")); return
        await asyncio.to_thread(db.set_setting, "force_join_channel", ch)
        _clear(update.effective_user.id, BOT_ID)
        await context.bot.send_message(chat_id=update.effective_message.chat.id, text=f"✅ کانال «{chat.title}» ثبت شد.", reply_markup=kb.admin_forcejoin_menu_kb(db))

    # --- Referral settings ---
    async def _cb_ref_settings(update, context):
        if not _senior_admin_only(update.effective_user.id): return await _deny(update, "⛔️.")
        await _replace_view(update, "🤝 زیرمجموعهگیری:", reply_markup=kb.referral_settings_kb(db))
        await update.callback_query.answer()

    async def _cb_ref_toggle(update, context):
        if not _senior_admin_only(update.effective_user.id): return await _deny(update, "⛔️.")
        cur = await asyncio.to_thread(db.get_setting, "referral_enabled", "1")
        await asyncio.to_thread(db.set_setting, "referral_enabled", "0" if cur == "1" else "1")
        await _safe_edit(update, "🤝 زیرمجموعهگیری:", reply_markup=kb.referral_settings_kb(db))
        await update.callback_query.answer()

    async def _cb_ref_percent_edit(update, context):
        if not _senior_admin_only(update.effective_user.id): return await _deny(update, "⛔️.")
        _set_state(update.effective_user.id, "adm_ref_pct", BOT_ID)
        await _safe_edit(update, "درصد پورسانت (0-100):", reply_markup=kb.admin_back_kb())
        await update.callback_query.answer()

    async def _process_ref_percent(update, context):
        if not _senior_admin_only(update.effective_user.id): return
        t = (update.message.text or "").strip()
        if not t.isdigit() or not (0 <= int(t) <= 100): await context.bot.send_message(chat_id=update.effective_message.chat.id, text="0-100:"); return
        await asyncio.to_thread(db.set_setting, "referral_percent", t)
        _clear(update.effective_user.id, BOT_ID)
        await context.bot.send_message(chat_id=update.effective_message.chat.id, text=f"✅ {t}٪ تنظیم شد.", reply_markup=kb.referral_settings_kb(db))

    async def _cb_ref_comm_max_edit(update, context):
        if not _senior_admin_only(update.effective_user.id): return await _deny(update, "⛔️.")
        _set_state(update.effective_user.id, "adm_ref_cmx", BOT_ID)
        await _safe_edit(update, "سقف تعداد (0=نامحدود):", reply_markup=kb.admin_back_kb())
        await update.callback_query.answer()

    async def _process_ref_comm_max(update, context):
        if not _senior_admin_only(update.effective_user.id): return
        t = (update.message.text or "").strip()
        if not t.isdigit(): await context.bot.send_message(chat_id=update.effective_message.chat.id, text="عدد:"); return
        await asyncio.to_thread(db.set_setting, "referral_commission_max_count", t)
        _clear(update.effective_user.id, BOT_ID)
        await context.bot.send_message(chat_id=update.effective_message.chat.id, text=f"✅ {t if t=='0' else t+' نفر'}.", reply_markup=kb.referral_settings_kb(db))

    async def _cb_ref_fc_toggle(update, context):
        if not _senior_admin_only(update.effective_user.id): return await _deny(update, "⛔️.")
        cur = await asyncio.to_thread(db.get_setting, "referral_free_config_enabled", "0")
        nv = "0" if cur == "1" else "1"
        if nv == "1" and not await asyncio.to_thread(db.get_setting, "referral_free_config_product_id", ""):
            await _deny(update, "ابتدا محصول جایزه را انتخاب کنید.", show_alert=True); return
        await asyncio.to_thread(db.set_setting, "referral_free_config_enabled", nv)
        await _safe_edit(update, "🤝 زیرمجموعهگیری:", reply_markup=kb.referral_settings_kb(db))
        await update.callback_query.answer()

    async def _cb_ref_fc_thresh_edit(update, context):
        if not _senior_admin_only(update.effective_user.id): return await _deny(update, "⛔️.")
        _set_state(update.effective_user.id, "adm_ref_fct", BOT_ID)
        await _safe_edit(update, "تعداد دعوت لازم (≥1):", reply_markup=kb.admin_back_kb())
        await update.callback_query.answer()

    async def _process_ref_fc_thresh(update, context):
        if not _senior_admin_only(update.effective_user.id): return
        t = (update.message.text or "").strip()
        if not t.isdigit() or int(t) < 1: await context.bot.send_message(chat_id=update.effective_message.chat.id, text="عدد ≥1:"); return
        await asyncio.to_thread(db.set_setting, "referral_free_config_threshold", t)
        _clear(update.effective_user.id, BOT_ID)
        await context.bot.send_message(chat_id=update.effective_message.chat.id, text=f"✅ با دعوت {t} نفر الگوی رایگان.", reply_markup=kb.referral_settings_kb(db))

    async def _cb_ref_fc_product(update, context):
        if not _senior_admin_only(update.effective_user.id): return await _deny(update, "⛔️.")
        await _replace_view(update, "📦 محصول جایزه را انتخاب کنید:", reply_markup=kb.referral_freeconfig_product_kb(db))
        await update.callback_query.answer()

    async def _cb_ref_fc_setprod(update, context):
        if not _senior_admin_only(update.effective_user.id): return await _deny(update, "⛔️.")
        try: pid = int(update.callback_query.data.split(":", 2)[1])
        except: await _deny(update, "❌."); return
        prod = await asyncio.to_thread(db.get_product, pid)
        if not prod: await _deny(update, "یافت نشد."); return
        await asyncio.to_thread(db.set_setting, "referral_free_config_product_id", pid)
        await _safe_edit(update, "🤝 زیرمجموعهگیری:", reply_markup=kb.referral_settings_kb(db))
        await _deny(update, f"✅ «{prod['name']}» انتخاب شد." if await asyncio.to_thread(db.has_product_files, pid) else "⚠️ هنوز فایلی نیست.", show_alert=True)

    async def _cb_ref_ib_toggle(update, context):
        if not _senior_admin_only(update.effective_user.id): return await _deny(update, "⛔️.")
        cur = await asyncio.to_thread(db.get_setting, "referral_invite_bonus_enabled", "0")
        nv = "0" if cur == "1" else "1"
        if nv == "1" and int(await asyncio.to_thread(db.get_setting, "referral_invite_bonus_amount", "0") or 0) <= 0:
            await _deny(update, "ابتدا مبلغ شارژ را تنظیم کنید.", show_alert=True); return
        await asyncio.to_thread(db.set_setting, "referral_invite_bonus_enabled", nv)
        await _safe_edit(update, "🤝 زیرمجموعهگیری:", reply_markup=kb.referral_settings_kb(db))
        await update.callback_query.answer()

    async def _cb_ref_ib_amt_edit(update, context):
        if not _senior_admin_only(update.effective_user.id): return await _deny(update, "⛔️.")
        _set_state(update.effective_user.id, "adm_ref_iba", BOT_ID)
        await _safe_edit(update, "مبلغ شارژ به ازای هر دعوت (تومان):", reply_markup=kb.admin_back_kb())
        await update.callback_query.answer()

    async def _process_ref_ib_amt(update, context):
        if not _senior_admin_only(update.effective_user.id): return
        t = (update.message.text or "").strip()
        if not t.isdigit() or int(t) < 0: await context.bot.send_message(chat_id=update.effective_message.chat.id, text="عدد ≥0:"); return
        await asyncio.to_thread(db.set_setting, "referral_invite_bonus_amount", t)
        _clear(update.effective_user.id, BOT_ID)
        await context.bot.send_message(chat_id=update.effective_message.chat.id, text=f"✅ {int(t):,} تومان.", reply_markup=kb.referral_settings_kb(db))

    async def _cb_ref_ib_max_edit(update, context):
        if not _senior_admin_only(update.effective_user.id): return await _deny(update, "⛔️.")
        _set_state(update.effective_user.id, "adm_ref_ibmx", BOT_ID)
        await _safe_edit(update, "سقف تعداد (0=نامحدود):", reply_markup=kb.admin_back_kb())
        await update.callback_query.answer()

    async def _process_ref_ib_max(update, context):
        if not _senior_admin_only(update.effective_user.id): return
        t = (update.message.text or "").strip()
        if not t.isdigit(): await context.bot.send_message(chat_id=update.effective_message.chat.id, text="عدد:"); return
        await asyncio.to_thread(db.set_setting, "referral_invite_bonus_max_count", t)
        _clear(update.effective_user.id, BOT_ID)
        await context.bot.send_message(chat_id=update.effective_message.chat.id, text=f"✅ {t if t=='0' else t+' نفر'}.", reply_markup=kb.referral_settings_kb(db))

    # --- Wheel settings ---
    async def _cb_wheel_settings(update, context):
        if not _senior_admin_only(update.effective_user.id): return await _deny(update, "⛔️.")
        await _replace_view(update, "🎡 گردونه شانس:", reply_markup=kb.wheel_settings_kb(db))
        await update.callback_query.answer()

    async def _cb_wheel_toggle(update, context):
        if not _senior_admin_only(update.effective_user.id): return await _deny(update, "⛔️.")
        cur = await asyncio.to_thread(db.get_setting, "wheel_enabled", "1")
        await asyncio.to_thread(db.set_setting, "wheel_enabled", "0" if cur == "1" else "1")
        await _safe_edit(update, "🎡 گردونه شانس:", reply_markup=kb.wheel_settings_kb(db))
        await update.callback_query.answer()

    async def _cb_wheel_edit_percent(update, context):
        if not _senior_admin_only(update.effective_user.id): return await _deny(update, "⛔️.")
        _set_state(update.effective_user.id, "adm_wheel_wp", BOT_ID)
        await _safe_edit(update, "درصد احتمال برد (0-100):", reply_markup=kb.admin_back_kb())
        await update.callback_query.answer()

    async def _process_wheel_percent(update, context):
        if not _senior_admin_only(update.effective_user.id): return
        t = (update.message.text or "").strip()
        if not t.isdigit() or not (0 <= int(t) <= 100): await context.bot.send_message(chat_id=update.effective_message.chat.id, text="0-100:"); return
        await asyncio.to_thread(db.set_setting, "wheel_win_percent", t)
        _clear(update.effective_user.id, BOT_ID)
        await context.bot.send_message(chat_id=update.effective_message.chat.id, text=f"✅ {t}٪.", reply_markup=kb.wheel_settings_kb(db))

    async def _cb_wheel_edit_prizes(update, context):
        if not _senior_admin_only(update.effective_user.id): return await _deny(update, "⛔️.")
        _set_state(update.effective_user.id, "adm_wheel_wpz", BOT_ID)
        await _safe_edit(update, "درصدهای جوایز (کاما): مثال 10,20,30,50", reply_markup=kb.admin_back_kb())
        await update.callback_query.answer()

    async def _process_wheel_prizes(update, context):
        if not _senior_admin_only(update.effective_user.id): return
        parts = [p.strip() for p in (update.message.text or "").split(",")]
        if not all(p.isdigit() and 0 < int(p) <= 100 for p in parts) or not parts:
            await context.bot.send_message(chat_id=update.effective_message.chat.id, text="مثال: 10,20,30,50"); return
        await asyncio.to_thread(db.set_wheel_prizes, [int(p) for p in parts])
        _clear(update.effective_user.id, BOT_ID)
        await context.bot.send_message(chat_id=update.effective_message.chat.id, text="✅ لیست جوایز بهروزرسانی شد.", reply_markup=kb.wheel_settings_kb(db))

    async def _cb_wheel_edit_expiry(update, context):
        if not _senior_admin_only(update.effective_user.id): return await _deny(update, "⛔️.")
        _set_state(update.effective_user.id, "adm_wheel_wex", BOT_ID)
        await _safe_edit(update, "اعتبار کد جایزه (ساعت):", reply_markup=kb.admin_back_kb())
        await update.callback_query.answer()

    async def _process_wheel_expiry(update, context):
        if not _senior_admin_only(update.effective_user.id): return
        t = (update.message.text or "").strip()
        if not t.isdigit() or int(t) <= 0: await context.bot.send_message(chat_id=update.effective_message.chat.id, text="عدد ≥1:"); return
        await asyncio.to_thread(db.set_setting, "wheel_code_expiry_hours", t)
        _clear(update.effective_user.id, BOT_ID)
        await context.bot.send_message(chat_id=update.effective_message.chat.id, text=f"✅ {t} ساعت.", reply_markup=kb.wheel_settings_kb(db))

    async def _cb_wheel_edit_cooldown(update, context):
        if not _senior_admin_only(update.effective_user.id): return await _deny(update, "⛔️.")
        _set_state(update.effective_user.id, "adm_wheel_wcd", BOT_ID)
        await _safe_edit(update, "فاصله چرخش (ساعت):", reply_markup=kb.admin_back_kb())
        await update.callback_query.answer()

    async def _process_wheel_cooldown(update, context):
        if not _senior_admin_only(update.effective_user.id): return
        t = (update.message.text or "").strip()
        if not t.isdigit() or int(t) <= 0: await context.bot.send_message(chat_id=update.effective_message.chat.id, text="عدد ≥1:"); return
        await asyncio.to_thread(db.set_setting, "wheel_cooldown_hours", t)
        _clear(update.effective_user.id, BOT_ID)
        await context.bot.send_message(chat_id=update.effective_message.chat.id, text=f"✅ {t} ساعت.", reply_markup=kb.wheel_settings_kb(db))

    # --- Admin panel: /admin and /cancel commands ---
    async def _cmd_admin(update, context):
        uid = update.effective_user.id
        if not _admin_only(uid): return
        _clear(uid, BOT_ID)
        await context.bot.send_message(chat_id=update.effective_message.chat.id, text="🔧 پنل مدیریت:", reply_markup=kb.admin_panel_kb(db))

    async def _cmd_cancel(update, context):
        uid = update.effective_user.id
        if not (_admin_only(uid) or uid == int(cfg.OWNER_ID)): return
        cur = _get_state(uid, BOT_ID)
        _clear(uid, BOT_ID)
        await context.bot.send_message(chat_id=update.effective_message.chat.id, text="❌ عملیات لغو شد." if cur else "❌ عملیاتی در جریان نبود.")
        await context.bot.send_message(chat_id=update.effective_message.chat.id, text="🔧 پنل مدیریت:", reply_markup=kb.admin_panel_kb(db))

    # ── Assemble admin handler list ──
    H = [
        MessageHandler(filters.TEXT & filters.Regex(f"^{btn_panel}$"), _open_panel),
        CallbackQueryHandler(_cb_back_panel, pattern="^adm_back_panel$"),
        CallbackQueryHandler(_cb_noop, pattern="^noop$"),
        CallbackQueryHandler(_cb_admin_cat, pattern="^adm_cat:"),
        CallbackQueryHandler(_cb_admin_categories, pattern="^adm_categories$"),
        CallbackQueryHandler(_cb_cat_toggle, pattern="^adm_cat_toggle:"),
        CallbackQueryHandler(_cb_cat_del, pattern="^adm_cat_del:"),
        CallbackQueryHandler(_cb_cat_add, pattern="^adm_cat_add$"),
        MessageHandler(_state_msg_filter("adm_add_cat", BOT_ID), _process_add_cat),
        CallbackQueryHandler(_cb_admin_products, pattern="^adm_products$"),
        CallbackQueryHandler(_cb_prod_cat, pattern="^adm_prod_cat:"),
        CallbackQueryHandler(_cb_prod_toggle, pattern="^adm_prod_toggle:"),
        CallbackQueryHandler(_cb_prod_del, pattern="^adm_prod_del:"),
        CallbackQueryHandler(_cb_prod_add, pattern="^adm_prod_add$"),
        CallbackQueryHandler(_cb_pick_newprod_cat, pattern="^adm_newprod_cat:"),
        MessageHandler(_state_msg_filter("adm_newprod_name", BOT_ID), _process_newprod_name),
        MessageHandler(_state_msg_filter("adm_newprod_price", BOT_ID), _process_newprod_price),
        MessageHandler(_state_msg_filter("adm_newprod_desc", BOT_ID), _process_newprod_desc),
        MessageHandler(_state_msg_filter("adm_newprod_preview", BOT_ID), _process_newprod_preview),
        MessageHandler(_state_msg_filter("adm_newprod_files", BOT_ID), _process_newprod_files),
        CallbackQueryHandler(_cb_newprod_files_done, pattern="^adm_files_done$"),
        CallbackQueryHandler(_cb_prod_files, pattern="^adm_product_files$"),
        CallbackQueryHandler(_cb_file_pick, pattern="^adm_file_pick:"),
        CallbackQueryHandler(_cb_file_del, pattern="^adm_file_del:"),
        CallbackQueryHandler(_cb_file_add, pattern="^adm_file_add:"),
        MessageHandler(_state_msg_filter("adm_prod_files_waiting", BOT_ID), _process_prod_files),
        CallbackQueryHandler(_cb_prod_files_done, pattern="^adm_files_done$"),
        CallbackQueryHandler(_cb_pending_orders, pattern="^adm_pending_orders$"),
        CallbackQueryHandler(_cb_view_order, pattern="^view_order:"),
        CallbackQueryHandler(_cb_order_approve, pattern="^order_approve:"),
        CallbackQueryHandler(_cb_order_reject, pattern="^order_reject:"),
        CallbackQueryHandler(_cb_pending_topups, pattern="^adm_pending_topups$"),
        CallbackQueryHandler(_cb_view_topup, pattern="^view_topup:"),
        CallbackQueryHandler(_cb_topup_approve, pattern="^topup_approve:"),
        CallbackQueryHandler(_cb_topup_reject, pattern="^topup_reject:"),
        CallbackQueryHandler(_cb_discounts_menu, pattern="^adm_discounts_menu$"),
        CallbackQueryHandler(_cb_disc_toggle, pattern="^adm_disc_toggle:"),
        CallbackQueryHandler(_cb_disc_del, pattern="^adm_disc_del:"),
        CallbackQueryHandler(_cb_disc_add, pattern="^adm_disc_add$"),
        MessageHandler(_state_msg_filter("adm_disc_code", BOT_ID), _process_disc_code),
        MessageHandler(_state_msg_filter("adm_disc_tv", BOT_ID), _process_disc_tv),
        MessageHandler(_state_msg_filter("adm_disc_mu", BOT_ID), _process_disc_mu),
        CallbackQueryHandler(_cb_forcejoin_menu, pattern="^adm_forcejoin_menu$"),
        CallbackQueryHandler(_cb_forcejoin_toggle, pattern="^adm_forcejoin_toggle$"),
        CallbackQueryHandler(_cb_forcejoin_set_channel, pattern="^adm_forcejoin_set_channel$"),
        MessageHandler(_state_msg_filter("adm_forcejoin_ch", BOT_ID), _process_forcejoin_ch),
        CallbackQueryHandler(_cb_ref_settings, pattern="^adm_referral_settings$"),
        CallbackQueryHandler(_cb_ref_toggle, pattern="^adm_referral_toggle$"),
        CallbackQueryHandler(_cb_ref_percent_edit, pattern="^adm_referral_percent_edit$"),
        MessageHandler(_state_msg_filter("adm_ref_pct", BOT_ID), _process_ref_percent),
        CallbackQueryHandler(_cb_ref_comm_max_edit, pattern="^adm_referral_commission_max_edit$"),
        MessageHandler(_state_msg_filter("adm_ref_cmx", BOT_ID), _process_ref_comm_max),
        CallbackQueryHandler(_cb_ref_fc_toggle, pattern="^adm_referral_freeconfig_toggle$"),
        CallbackQueryHandler(_cb_ref_fc_thresh_edit, pattern="^adm_referral_freeconfig_threshold_edit$"),
        MessageHandler(_state_msg_filter("adm_ref_fct", BOT_ID), _process_ref_fc_thresh),
        CallbackQueryHandler(_cb_ref_fc_product, pattern="^adm_referral_freeconfig_product$"),
        CallbackQueryHandler(_cb_ref_fc_setprod, pattern="^adm_referral_freeconfig_setprod:"),
        CallbackQueryHandler(_cb_ref_ib_toggle, pattern="^adm_referral_invitebonus_toggle$"),
        CallbackQueryHandler(_cb_ref_ib_amt_edit, pattern="^adm_referral_invitebonus_amount_edit$"),
        MessageHandler(_state_msg_filter("adm_ref_iba", BOT_ID), _process_ref_ib_amt),
        CallbackQueryHandler(_cb_ref_ib_max_edit, pattern="^adm_referral_invitebonus_max_edit$"),
        MessageHandler(_state_msg_filter("adm_ref_ibmx", BOT_ID), _process_ref_ib_max),
        CallbackQueryHandler(_cb_wheel_settings, pattern="^adm_wheel_settings$"),
        CallbackQueryHandler(_cb_wheel_toggle, pattern="^adm_wheel_toggle$"),
        CallbackQueryHandler(_cb_wheel_edit_percent, pattern="^adm_wheel_edit_percent$"),
        MessageHandler(_state_msg_filter("adm_wheel_wp", BOT_ID), _process_wheel_percent),
        CallbackQueryHandler(_cb_wheel_edit_prizes, pattern="^adm_wheel_edit_prizes$"),
        MessageHandler(_state_msg_filter("adm_wheel_wpz", BOT_ID), _process_wheel_prizes),
        CallbackQueryHandler(_cb_wheel_edit_expiry, pattern="^adm_wheel_edit_expiry$"),
        MessageHandler(_state_msg_filter("adm_wheel_wex", BOT_ID), _process_wheel_expiry),
        CallbackQueryHandler(_cb_wheel_edit_cooldown, pattern="^adm_wheel_edit_cooldown$"),
        MessageHandler(_state_msg_filter("adm_wheel_wcd", BOT_ID), _process_wheel_cooldown),
        CommandHandler("admin", _cmd_admin),
        CommandHandler("cancel", _cmd_cancel),
    ]
    return H



