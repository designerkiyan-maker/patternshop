# -*- coding: utf-8 -*-
"""تعریف State های FSM برای مکالمات چندمرحله‌ای (فروش الگوی خیاطی)."""

from aiogram.fsm.state import State, StatesGroup


class BuyFlow(StatesGroup):
    waiting_receipt = State()


class DiscountEntry(StatesGroup):
    waiting_code = State()


class WalletTopup(StatesGroup):
    waiting_amount = State()
    waiting_receipt = State()


class ContactFlow(StatesGroup):
    waiting_message = State()


class AdminReplyFlow(StatesGroup):
    waiting_reply = State()


class AdminAddCategory(StatesGroup):
    waiting_name = State()


class AdminAddProduct(StatesGroup):
    waiting_category = State()
    waiting_name = State()
    waiting_price = State()
    waiting_desc = State()
    waiting_preview = State()
    waiting_files = State()


class AdminProductFiles(StatesGroup):
    waiting_product = State()
    waiting_files = State()


class AdminProductPreview(StatesGroup):
    waiting_product = State()
    waiting_photo = State()


class AdminSampleFiles(StatesGroup):
    waiting_files = State()


class AdminResetSample(StatesGroup):
    waiting_message = State()


class AdminForceJoin(StatesGroup):
    waiting_channel = State()


class AdminEditButton(StatesGroup):
    waiting_text = State()


class AdminSetCard(StatesGroup):
    waiting_number = State()
    waiting_holder = State()


class AdminBroadcast(StatesGroup):
    waiting_message = State()


class AdminAddAdmin(StatesGroup):
    waiting_id = State()


class AdminRemoveAdmin(StatesGroup):
    waiting_id = State()


class AdminChangeRole(StatesGroup):
    waiting_id = State()


class AdminEditWelcome(StatesGroup):
    waiting_text = State()


class AdminCreateDiscount(StatesGroup):
    waiting_code = State()
    waiting_type_value = State()
    waiting_maxuses = State()


class AdminReferralPercent(StatesGroup):
    waiting_value = State()


class AdminReferralCommissionMax(StatesGroup):
    waiting_value = State()


class AdminReferralFreeConfigThreshold(StatesGroup):
    waiting_value = State()


class AdminReferralInviteBonusAmount(StatesGroup):
    waiting_value = State()


class AdminReferralInviteBonusMax(StatesGroup):
    waiting_value = State()


class AdminWheelSettings(StatesGroup):
    waiting_win_percent = State()
    waiting_prizes = State()
    waiting_expiry = State()
    waiting_cooldown = State()


class AdminRestoreBackup(StatesGroup):
    waiting_file = State()
    waiting_confirm = State()
