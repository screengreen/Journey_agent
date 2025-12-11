"""Сервис для обработки и нормализации событий."""

from typing import List

from src.models.event import Event
from src.services.geolocation import GeolocationService


class EventProcessor:
    """Сервис для обработки событий перед сохранением."""

    def __init__(self):
        """Инициализация сервиса."""
        self.geolocation_service = GeolocationService()

    def process_events(self, events: List[Event]) -> List[Event]:
        """
        Обрабатывает список событий: нормализует и добавляет координаты.

        Args:
            events: Список событий для обработки

        Returns:
            Обработанный список событий
        """
        processed_events = []

        for event in events:
            processed_event = self.process_event(event)
            if processed_event:
                processed_events.append(processed_event)

        return processed_events

    def process_event(self, event: Event) -> Event:
        """
        Обрабатывает одно событие: нормализует данные и добавляет координаты.

        Args:
            event: Событие для обработки

        Returns:
            Обработанное событие
        """
        # Если координат нет, но есть адрес, пытаемся геокодировать
        if not event.latitude or not event.longitude:
            if event.location:
                location = self.geolocation_service.geocode(event.location)
                if location:
                    event.latitude = location.latitude
                    event.longitude = location.longitude
                    if not event.country and location.country:
                        event.country = location.country

        # Нормализуем теги
        if not event.tags:
            event.tags = ["all"]

        # Убеждаемся, что есть хотя бы базовые поля
        if not event.title:
            event.title = "Без названия"

        if not event.description:
            event.description = ""

        return event


