"""Клавиатуры для Telegram бота."""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton


def get_main_keyboard():
    """Возвращает главную клавиатуру."""
    keyboard = [
        [KeyboardButton("🔍 Найти события")],
        [KeyboardButton("📋 Мои каналы"), KeyboardButton("➕ Добавить канал")],
        [KeyboardButton("📍 Установить локацию"), KeyboardButton("ℹ️ Помощь")],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def get_event_keyboard(event_url: str):
    """
    Возвращает клавиатуру для события.

    Args:
        event_url: URL события

    Returns:
        InlineKeyboardMarkup
    """
    keyboard = [[InlineKeyboardButton("🔗 Открыть событие", url=event_url)]]
    return InlineKeyboardMarkup(keyboard)


def get_location_keyboard():
    """Возвращает клавиатуру с кнопкой для отправки локации."""
    keyboard = [[KeyboardButton("📍 Отправить мою локацию", request_location=True)]]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)


