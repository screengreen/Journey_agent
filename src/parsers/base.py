"""Базовый класс для парсеров событий."""

from abc import ABC, abstractmethod
from typing import List

from src.models.event import Event


class BaseParser(ABC):
    """Базовый класс для всех парсеров событий."""

    def __init__(self, source_name: str):
        """
        Инициализация парсера.

        Args:
            source_name: Название источника (например, "afisha", "telegram")
        """
        self.source_name = source_name

    @abstractmethod
    def parse(self, *args, **kwargs) -> List[Event]:
        """
        Парсит события из источника.

        Returns:
            Список найденных событий
        """
        pass

    @abstractmethod
    def can_parse(self, url: str) -> bool:
        """
        Проверяет, может ли парсер обработать данный URL.

        Args:
            url: URL для проверки

        Returns:
            True, если парсер может обработать URL
        """
        pass

    def normalize_event(self, event: Event) -> Event:
        """
        Нормализует событие перед сохранением.

        Args:
            event: Событие для нормализации

        Returns:
            Нормализованное событие
        """
        # Устанавливаем источник, если не указан
        if not event.source:
            event.source = self.source_name

        # Добавляем тег источника
        if self.source_name not in event.tags:
            event.tags.append(self.source_name)

        return event


