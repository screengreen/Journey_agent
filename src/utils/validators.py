"""Валидаторы для данных."""

import re
from typing import Optional


def validate_telegram_channel(channel_id: str) -> bool:
    """
    Валидирует ID Telegram канала.

    Args:
        channel_id: ID канала

    Returns:
        True, если валидный
    """
    patterns = [
        r"^@[a-zA-Z0-9_]{5,32}$",  # @channel
        r"^[a-zA-Z0-9_]{5,32}$",  # channel (без @)
    ]
    return any(re.match(pattern, channel_id) for pattern in patterns)


def validate_url(url: str) -> bool:
    """
    Валидирует URL.

    Args:
        url: URL для проверки

    Returns:
        True, если валидный
    """
    pattern = r"^https?://.+"
    return bool(re.match(pattern, url))


def extract_city_from_text(text: str) -> Optional[str]:
    """
    Извлекает название города из текста.

    Args:
        text: Текст для анализа

    Returns:
        Название города или None
    """
    cities = ["Москва", "Санкт-Петербург", "Питер", "СПб", "Казань", "Екатеринбург"]
    text_lower = text.lower()

    for city in cities:
        if city.lower() in text_lower:
            return city

    return None


