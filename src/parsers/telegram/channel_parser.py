"""Парсер для Telegram каналов."""

import re
from typing import List, Optional

from src.models.event import Event
from src.parsers.base import BaseParser


class TelegramChannelParser(BaseParser):
    """Парсер событий из Telegram каналов."""

    def __init__(self):
        """Инициализация парсера Telegram каналов."""
        super().__init__("telegram")

    def can_parse(self, url: str) -> bool:
        """
        Проверяет, является ли URL Telegram каналом.

        Args:
            url: URL для проверки

        Returns:
            True, если это Telegram канал
        """
        telegram_patterns = [
            r"t\.me/",
            r"telegram\.me/",
            r"@\w+",
        ]
        return any(re.search(pattern, url, re.IGNORECASE) for pattern in telegram_patterns)

    def parse(self, messages: List[dict], user_tag: Optional[str] = None) -> List[Event]:
        """
        Парсит события из сообщений Telegram канала.

        Args:
            messages: Список сообщений из канала
            user_tag: Тег пользователя для добавления к событиям

        Returns:
            Список найденных событий
        """
        events = []

        for message in messages:
            text = message.get("text", "")
            if not text:
                continue

            # Пытаемся извлечь информацию о событии из текста
            event = self._extract_event_from_message(text, message, user_tag)
            if event:
                events.append(self.normalize_event(event))

        return events

    def _extract_event_from_message(
        self, text: str, message: dict, user_tag: Optional[str] = None
    ) -> Optional[Event]:
        """
        Извлекает информацию о событии из сообщения.

        Args:
            text: Текст сообщения
            message: Полное сообщение с метаданными
            user_tag: Тег пользователя

        Returns:
            Event или None, если событие не найдено
        """
        # Простая эвристика: ищем ключевые слова
        event_keywords = [
            "концерт",
            "выставка",
            "фестиваль",
            "спектакль",
            "шоу",
            "мероприятие",
            "событие",
        ]

        text_lower = text.lower()
        if not any(keyword in text_lower for keyword in event_keywords):
            return None

        # Извлекаем заголовок (первая строка или первые 100 символов)
        lines = text.split("\n")
        title = lines[0].strip() if lines else text[:100].strip()
        if len(title) > 200:
            title = title[:200]

        # Описание - весь текст или первые 500 символов
        description = text[:500].strip()

        # Извлекаем URL, если есть
        url = None
        url_pattern = r"https?://[^\s]+"
        urls = re.findall(url_pattern, text)
        if urls:
            url = urls[0]

        # Пытаемся найти локацию (простая эвристика)
        location = self._extract_location(text)

        # Пытаемся найти дату
        date = self._extract_date(text)

        # Формируем теги
        tags = ["all"]
        if user_tag:
            tags.append(user_tag)

        return Event(
            title=title,
            description=description,
            tags=tags,
            location=location,
            date=date,
            url=url,
        )

    def _extract_location(self, text: str) -> Optional[str]:
        """
        Извлекает локацию из текста.

        Args:
            text: Текст сообщения

        Returns:
            Локация или None
        """
        # Простая эвристика: ищем упоминания городов
        cities = ["Москва", "Санкт-Петербург", "Питер", "СПб"]
        for city in cities:
            if city.lower() in text.lower():
                return city

        # Ищем паттерны типа "г. Москва", "Москва, ..."
        location_pattern = r"(?:г\.|город|в\s+)?([А-ЯЁ][а-яё]+(?:\s+[А-ЯЁ][а-яё]+)?)"
        matches = re.findall(location_pattern, text)
        if matches:
            return matches[0]

        return None

    def _extract_date(self, text: str) -> Optional[str]:
        """
        Извлекает дату из текста.

        Args:
            text: Текст сообщения

        Returns:
            Дата в формате YYYY-MM-DD или None
        """
        # Простые паттерны для дат
        date_patterns = [
            r"(\d{1,2})[./](\d{1,2})[./](\d{4})",  # DD.MM.YYYY
            r"(\d{4})[./-](\d{1,2})[./-](\d{1,2})",  # YYYY-MM-DD
        ]

        for pattern in date_patterns:
            matches = re.findall(pattern, text)
            if matches:
                # Возвращаем первую найденную дату
                # TODO: Более сложная обработка дат
                return None  # Пока возвращаем None, нужна более сложная логика

        return None


