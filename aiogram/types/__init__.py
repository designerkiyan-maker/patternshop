# -*- coding: utf-8 -*-
"""Fake aiogram.types subpackage."""
from providers.__fake_aiogram import (
    User, Chat, Message, CallbackQuery, Update,
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, ForceReply,
    MenuButtonWebApp, MenuButtonDefault, WebAppInfo,
)


class TelegramObject:
    """پایه کلاس همه‌ی نوع‌های update بله/تلگرام."""
    pass


class FSInputFile:
    """شیء فایل محلی برای send_document/send_photo — Bale فایل‌ها را با file_id میگیرد."""
    def __init__(self, path_or_id):
        self._path = str(path_or_id)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    @property
    def name(self):
        return self._path


class ErrorEvent:
    """نماینده خطای پردازش update برای dp.errors.register."""
    def __init__(self, exception, update=None):
        self.exception = exception
        self.update = update
