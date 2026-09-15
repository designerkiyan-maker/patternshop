# -*- coding: utf-8 -*-
"""Fake aiogram package — replaces real aiogram when running Bale bot."""
from providers.__fake_aiogram import (
    Router, Dispatcher,
    User, Chat, Message, CallbackQuery, Update,
    MenuButtonWebApp, MenuButtonDefault, WebAppInfo,
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, ForceReply,
    F, CommandStart, Command, StateFilter, TextFilter, PhotoFilter,
    DocumentFilter, RegexFilter, CallbackDataFilter, OrFilter,
    State, StatesGroup, FSMContext,
    TelegramException, TelegramRetryAfter, TelegramForbiddenError,
    TelegramBadRequest, TelegramNetworkError,
    BaseStorage, StorageKey,
    BaseMiddleware,
    BotWrapper,
    set_global_dispatcher, get_global_dispatcher,
)

# نام اختصاری برای backward-compatibility با handlerها
Bot = BotWrapper

__version__ = "3.10.0-bale"
