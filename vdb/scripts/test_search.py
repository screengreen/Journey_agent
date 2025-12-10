#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тестовый скрипт для проверки поиска событий в Weaviate.
"""

import sys
from pathlib import Path
from urllib.parse import urlparse

import weaviate
import weaviate.classes as wvc

# Добавляем корневую директорию проекта в путь
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.config import WEAVIATE_URL, COLLECTION_NAME


def get_client() -> weaviate.WeaviateClient:
    """Создает клиент Weaviate."""
    parsed = urlparse(WEAVIATE_URL)
    http_port = parsed.port or (443 if parsed.scheme == "https" else 8080)
    http_secure = parsed.scheme == "https"
    hostname = parsed.hostname or "localhost"

    if hostname in ("localhost", "127.0.0.1") and http_port == 8080 and not http_secure:
        return weaviate.connect_to_local()
    else:
        return weaviate.connect_to_custom(
            http_host=hostname,
            http_port=http_port,
            http_secure=http_secure,
            grpc_host=hostname,
            grpc_port=50051,
            grpc_secure=http_secure,
        )


def test_search():
    """Тестирует поиск событий."""
    client = get_client()
    
    try:
        if COLLECTION_NAME not in client.collections.list_all():
            print(f"❌ Коллекция '{COLLECTION_NAME}' не найдена")
            return 1
        
        collection = client.collections.get(COLLECTION_NAME)
        
        # Тест 1: Поиск без фильтра
        print("🔍 Тест 1: Поиск без фильтра")
        result = collection.query.near_text(
            query="музыка",
            limit=10,
            return_metadata=wvc.query.MetadataQuery(distance=True),
        )
        print(f"   Найдено: {len(result.objects)} событий")
        for obj in result.objects[:3]:
            print(f"   - {obj.properties.get('title', 'N/A')} (теги: {obj.properties.get('tags', [])})")
        print()
        
        # Тест 2: Поиск с фильтром по тегу user123
        print("🔍 Тест 2: Поиск с фильтром по тегу 'user123'")
        filter_user123 = wvc.query.Filter.by_property("tags").contains_any(["user123"])
        # В Weaviate v4 нужно использовать fetch_objects с фильтром для точного поиска
        # или комбинировать near_text с фильтром через другой метод
        result = collection.query.fetch_objects(
            where=filter_user123,
            limit=10,
        )
        print(f"   Найдено: {len(result.objects)} событий")
        for obj in result.objects:
            print(f"   - {obj.properties.get('title', 'N/A')} (теги: {obj.properties.get('tags', [])})")
        print()
        
        # Тест 3: Поиск с фильтром по тегу 'all'
        print("🔍 Тест 3: Поиск с фильтром по тегу 'all'")
        filter_all = wvc.query.Filter.by_property("tags").contains_any(["all"])
        result = collection.query.fetch_objects(
            where=filter_all,
            limit=10,
        )
        print(f"   Найдено: {len(result.objects)} событий")
        for obj in result.objects:
            print(f"   - {obj.properties.get('title', 'N/A')} (теги: {obj.properties.get('tags', [])})")
        print()
        
        # Тест 4: Поиск с фильтром user123 ИЛИ all
        print("🔍 Тест 4: Поиск с фильтром 'user123' ИЛИ 'all'")
        filter_combined = wvc.query.Filter.any_of([
            wvc.query.Filter.by_property("tags").contains_any(["user123"]),
            wvc.query.Filter.by_property("tags").contains_any(["all"]),
        ])
        result = collection.query.fetch_objects(
            where=filter_combined,
            limit=10,
        )
        print(f"   Найдено: {len(result.objects)} событий")
        for obj in result.objects:
            print(f"   - {obj.properties.get('title', 'N/A')} (теги: {obj.properties.get('tags', [])})")
        print()
        
        # Тест 5: Простой запрос всех объектов
        print("🔍 Тест 5: Получение всех объектов (без поиска)")
        result = collection.query.fetch_objects(limit=10)
        print(f"   Всего объектов в коллекции: {len(result.objects)}")
        for obj in result.objects:
            print(f"   - {obj.properties.get('title', 'N/A')} (теги: {obj.properties.get('tags', [])})")
        
        return 0
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        client.close()


if __name__ == "__main__":
    sys.exit(test_search())

