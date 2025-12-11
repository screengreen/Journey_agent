"""Клиент для работы с Weaviate."""

from typing import List, Optional
from urllib.parse import urlparse

import weaviate
import weaviate.classes as wvc

from src.config import WEAVIATE_URL, COLLECTION_NAME
from src.models.event import Event


class WeaviateClient:
    """Клиент для работы с векторной БД Weaviate."""

    def __init__(self, weaviate_url: str = WEAVIATE_URL, collection_name: str = COLLECTION_NAME):
        """
        Инициализация клиента.

        Args:
            weaviate_url: URL сервера Weaviate
            collection_name: Имя коллекции
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

    def add_events(self, events: List[Event]) -> int:
        """
        Добавляет события в Weaviate.

        Args:
            events: Список событий для добавления

        Returns:
            Количество добавленных событий
        """
        if not events:
            return 0

        client = self._get_client()
        collection = client.collections.get(self.collection_name)

        added_count = 0
        with collection.batch.dynamic() as batch:
            for event in events:
                try:
                    # Преобразуем Event в словарь для Weaviate
                    properties = event.model_dump(exclude_none=True)
                    batch.add_object(properties=properties)
                    added_count += 1
                except Exception as e:
                    print(f"Ошибка при добавлении события '{event.title}': {e}")

        return added_count

    def close(self):
        """Закрывает соединение с Weaviate."""
        if self._client is not None:
            self._client.close()
            self._client = None


