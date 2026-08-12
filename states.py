# -*- coding: utf-8 -*-
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
    waiting_duration = State()


class AdminAddConfigs(StatesGroup):
    waiting_product = State()
    waiting_links = State()


class AdminAddTestConfigs(StatesGroup):
    waiting_links = State()


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


class AdminAddResellerBot(StatesGroup):
    waiting_token = State()
    waiting_owner_id = State()
    waiting_owner_name = State()


class AdminWheelSettings(StatesGroup):
    waiting_win_percent = State()
    waiting_prizes = State()
    waiting_expiry = State()
    waiting_cooldown = State()


class AdminRenewalSettings(StatesGroup):
    waiting_days_before = State()
    waiting_percent = State()
    waiting_expiry_hours = State()


class AdminStockAlertSettings(StatesGroup):
    waiting_threshold = State()
