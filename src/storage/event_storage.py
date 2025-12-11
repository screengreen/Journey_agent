"""Хранилище событий."""

from typing import List

from src.models.event import Event
from src.services.event_processor import EventProcessor
from src.storage.weaviate_client import WeaviateClient


class EventStorage:
    """Хранилище событий в Weaviate."""

    def __init__(self, weaviate_client: WeaviateClient):
        """
        Инициализация хранилища.

        Args:
            weaviate_client: Клиент Weaviate
        """
        self.weaviate_client = weaviate_client
        self.event_processor = EventProcessor()

    def add_events(self, events: List[Event]) -> int:
        """
        Добавляет события в хранилище.

        Args:
            events: Список событий

        Returns:
            Количество добавленных событий
        """
        # Обрабатываем события перед сохранением
        processed_events = self.event_processor.process_events(events)

        # Добавляем в Weaviate
        return self.weaviate_client.add_events(processed_events)


