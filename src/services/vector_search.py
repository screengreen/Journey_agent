"""Сервис для поиска событий в векторной БД."""

from typing import List, Optional

from src.config import WEAVIATE_URL, COLLECTION_NAME, MAX_EVENTS
from src.models.event import Event
from src.rag.retriever import EventRetriever


class VectorSearchService:
    """Сервис для семантического поиска событий в Weaviate."""

    def __init__(self, weaviate_url: str = WEAVIATE_URL, collection_name: str = COLLECTION_NAME):
        """
        Инициализация сервиса.

        Args:
            weaviate_url: URL сервера Weaviate
            collection_name: Имя коллекции с событиями
        """
        self.retriever = EventRetriever(weaviate_url=weaviate_url, collection_name=collection_name)

    def search(
        self,
        query: str,
        user_tag: Optional[str] = None,
        limit: int = MAX_EVENTS,
    ) -> List[Event]:
        """
        Выполняет семантический поиск событий.

        Args:
            query: Поисковый запрос пользователя
            user_tag: Тег пользователя для фильтрации
            limit: Максимальное количество результатов

        Returns:
            Список найденных событий
        """
        return self.retriever.retrieve(query=query, user_tag=user_tag, limit=limit)

    def close(self):
        """Закрывает соединение с Weaviate."""
        self.retriever.close()


