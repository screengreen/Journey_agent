"""Retriever для поиска событий в Weaviate с фильтрацией по тегам."""

from typing import List, Optional
from urllib.parse import urlparse

try:
    import weaviate
    import weaviate.classes as wvc
except ImportError:
    weaviate = None
    wvc = None

from src.vdb.config import WEAVIATE_URL, COLLECTION_NAME, MAX_EVENTS
from src.models.event import Event


class EventRetriever:
    """Retriever для поиска событий в Weaviate."""

    def __init__(self, weaviate_url: str = WEAVIATE_URL, collection_name: str = COLLECTION_NAME):
        """
        Инициализация retriever.

        Args:
            weaviate_url: URL сервера Weaviate
            collection_name: Имя коллекции с событиями
        """
        self.weaviate_url = weaviate_url
        self.collection_name = collection_name
        self._client: Optional[weaviate.WeaviateClient] = None

    def _get_client(self) -> weaviate.WeaviateClient:
        """Получить или создать клиент Weaviate."""
        if self._client is None:
            parsed = urlparse(self.weaviate_url)
            http_port = parsed.port or (443 if parsed.scheme == "https" else 8080)
            http_secure = parsed.scheme == "https"
            hostname = parsed.hostname or "localhost"

            if hostname in ("localhost", "127.0.0.1") and http_port == 8080 and not http_secure:
                self._client = weaviate.connect_to_local()
            else:
                self._client = weaviate.connect_to_custom(
                    http_host=hostname,
                    http_port=http_port,
                    http_secure=http_secure,
                    grpc_host=hostname,
                    grpc_port=50051,
                    grpc_secure=http_secure,
                )
        return self._client

    def retrieve(
        self,
        query: str,
        limit: int = MAX_EVENTS,
        owner: Optional[str] = None,
    ) -> List[Event]:
        """
        Поиск событий по запросу с фильтрацией по тегам.

        Args:
            query: Поисковый запрос
            user_tag: Тег пользователя для фильтрации (события с этим тегом или 'all')
            limit: Максимальное количество результатов

        Returns:
            Список найденных событий
        """
        client = self._get_client()

        try:
            collection = client.collections.get(self.collection_name)
        except Exception:
            # Если коллекция не существует, возвращаем пустой список
            return []

        # Выполняем поиск
        try:
            # В Weaviate v4 near_text не поддерживает where напрямую
            # Используем двухэтапный подход: сначала семантический поиск, затем фильтрация
            result = collection.query.near_text(
                query=query,
                limit=limit * 2,  # Берем больше результатов для последующей фильтрации
                return_metadata=wvc.query.MetadataQuery(distance=True),
            )

            events = []
            for obj in result.objects:
                try:
                    # Фильтруем по владельцу программно
                    if owner:
                        # Проверяем, соответствует ли владелец объекта запрошенному
                        if owner != obj.properties.get("owner"):
                            continue
                    
                    event = Event(**obj.properties)
                    events.append(event)
                    
                    # Ограничиваем количество результатов
                    if len(events) >= limit:
                        break
                        
                except Exception as e:
                    # Пропускаем объекты, которые не соответствуют модели
                    import warnings
                    warnings.warn(f"Ошибка при парсинге события: {e}")
                    continue

            return events
        except Exception as e:
            # В случае ошибки возвращаем пустой список
            import warnings
            warnings.warn(f"Ошибка при поиске в Weaviate: {e}")
            return []

    def format_events_for_context(self, events: List[Event]) -> str:
        """
        Форматирует события для использования в контексте промпта.

        Args:
            events: Список событий

        Returns:
            Отформатированная строка с событиями
        """
        if not events:
            return "События не найдены."

        formatted = []
        for i, event in enumerate(events, 1):
            event_str = f"{i}. {event.title}"
            if event.description:
                event_str += f"\n   Описание: {event.description}"
            if event.location:
                event_str += f"\n   Местоположение: {event.location}"
            if event.date:
                event_str += f"\n   Дата: {event.date}"
            if event.tags:
                event_str += f"\n   Теги: {', '.join(event.tags)}"
            formatted.append(event_str)

        return "\n\n".join(formatted)

    def close(self):
        """Закрыть соединение с Weaviate."""
        if self._client is not None:
            self._client.close()
            self._client = None

