# -*- coding: utf-8 -*-
"""Fake aiogram.fsm.storage.memory subpackage — just a pass-through since we use SQLiteStorage."""
from providers.__fake_aiogram import FSMContext

class MemoryStorage:
    """Simple in-memory FSM storage (fallback only)."""
    def __init__(self):
        self._states = {}
        self._data = {}
    async def set_state(self, key, state=None):
        self._states[key] = state
    async def get_state(self, key):
        return self._states.get(key)
    async def set_data(self, key, data=None):
        if data is not None:
            self._data[key] = data
    async def get_data(self, key):
        return self._data.get(key, {})
    async def close(self):
        pass
