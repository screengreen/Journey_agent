#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для добавления событий в Weaviate.

Запуск:
    python scripts/add_events.py
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


def create_collection_if_not_exists(client: weaviate.WeaviateClient, force_recreate: bool = False) -> None:
    """
    Создает коллекцию Events, если она не существует.
    
    Args:
        client: Клиент Weaviate
        force_recreate: Если True, пересоздает коллекцию даже если она существует
    """
    if COLLECTION_NAME in client.collections.list_all():
        if force_recreate:
            print(f"ℹ️  Удаляю существующую коллекцию '{COLLECTION_NAME}' для пересоздания")
            client.collections.delete(COLLECTION_NAME)
        else:
            print(f"ℹ️  Коллекция '{COLLECTION_NAME}' уже существует")
            print(f"   Для пересоздания с новой конфигурацией используйте: python {__file__} --recreate")
            return

    print(f"ℹ️  Создаю коллекцию '{COLLECTION_NAME}'")
    client.collections.create(
        name=COLLECTION_NAME,
        description="События для посещения",
        properties=[
            wvc.config.Property(
                name="title",
                description="Название события",
                data_type=wvc.config.DataType.TEXT,
                vectorize_property_name=True,  # Используется для векторизации
            ),
            wvc.config.Property(
                name="description",
                description="Описание события",
                data_type=wvc.config.DataType.TEXT,
                vectorize_property_name=True,  # Используется для векторизации
            ),
            wvc.config.Property(
                name="tags",
                description="Теги события (массив строк)",
                data_type=wvc.config.DataType.TEXT_ARRAY,
                vectorize_property_name=False,  # Не используется для векторизации (только для фильтрации)
            ),
            wvc.config.Property(
                name="source",
                description="Источник события",
                data_type=wvc.config.DataType.TEXT,
                vectorize_property_name=False,  # Исключено из векторизации
            ),
            wvc.config.Property(
                name="country",
                description="Страна события",
                data_type=wvc.config.DataType.TEXT,
                vectorize_property_name=True,  # Используется для векторизации
            ),
            wvc.config.Property(
                name="location",
                description="Местоположение события",
                data_type=wvc.config.DataType.TEXT,
                vectorize_property_name=True,  # Используется для векторизации
            ),
            wvc.config.Property(
                name="date",
                description="Дата события",
                data_type=wvc.config.DataType.TEXT,
                vectorize_property_name=False,  # Исключено из векторизации
            ),
            wvc.config.Property(
                name="url",
                description="URL события",
                data_type=wvc.config.DataType.TEXT,
                vectorize_property_name=False,  # Исключено из векторизации
            ),
        ],
        vectorizer_config=wvc.config.Configure.Vectorizer.text2vec_contextionary(
            # Можно указать, какие поля использовать для векторизации
            # По умолчанию используются все TEXT поля
        ),
    )
    print(f"✅ Коллекция '{COLLECTION_NAME}' создана")


def add_sample_events(collection: weaviate.collections.Collection) -> None:
    """Добавляет примеры событий в коллекцию."""
    events = [
        {
            "title": "Джазовый концерт в Blue Note",
            "description": "Вечер джазовой музыки с участием известных музыкантов. Уютная атмосфера, живая музыка.",
            "tags": ["user123", "all"],
            "source": "eventbrite",
            "country": "Russia",
            "location": "Москва, ул. Арбат, 1",
            "date": "2024-02-15",
            "url": "https://example.com/jazz-concert",
        },
        {
            "title": "Рок-фестиваль 'Лето в городе'",
            "description": "Масштабный рок-фестиваль под открытым небом с участием топовых российских групп.",
            "tags": ["user123", "all"],
            "source": "afisha",
            "country": "Russia",
            "location": "Москва, Парк Горького",
            "date": "2024-02-20",
            "url": "https://example.com/rock-festival",
        },
        {
            "title": "Выставка 'Импрессионисты в Эрмитаже'",
            "description": "Уникальная выставка картин импрессионистов из коллекции Эрмитажа. Работы Моне, Ренуара, Дега.",
            "tags": ["user456", "all"],
            "source": "hermitage",
            "country": "Russia",
            "location": "Санкт-Петербург, Эрмитаж",
            "date": "2024-02-10",
            "url": "https://example.com/impressionists",
        },
        {
            "title": "Современное искусство в Третьяковке",
            "description": "Выставка современного российского искусства. Инсталляции, перформансы, мультимедиа.",
            "tags": ["user456", "all"],
            "source": "tretyakov",
            "country": "Russia",
            "location": "Москва, Третьяковская галерея",
            "date": "2024-02-18",
            "url": "https://example.com/modern-art",
        },
        {
            "title": "Классический концерт в Консерватории",
            "description": "Симфонический оркестр исполняет произведения Чайковского и Рахманинова.",
            "tags": ["user123", "all"],
            "source": "conservatory",
            "country": "Russia",
            "location": "Москва, Консерватория",
            "date": "2024-02-12",
            "url": "https://example.com/classical",
        },
        {
            "title": "Фотовыставка 'Москва глазами фотографов'",
            "description": "Выставка фотографий Москвы разных эпох. От дореволюционных снимков до современности.",
            "tags": ["user456", "all"],
            "source": "photocenter",
            "country": "Russia",
            "location": "Москва, Центр фотографии",
            "date": "2024-02-14",
            "url": "https://example.com/photos",
        },
    ]

    print(f"ℹ️  Добавляю {len(events)} событий в коллекцию")
    with collection.batch.dynamic() as batch:
        for event in events:
            batch.add_object(properties=event)
    print(f"✅ Добавлено {len(events)} событий")


def main() -> int:
    """Основная функция."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Добавление событий в Weaviate")
    parser.add_argument(
        "--recreate",
        action="store_true",
        help="Пересоздать коллекцию даже если она существует (для применения новой конфигурации векторизации)",
    )
    args = parser.parse_args()
    
    try:
        client = get_client()
        
        try:
            create_collection_if_not_exists(client, force_recreate=args.recreate)
            collection = client.collections.get(COLLECTION_NAME)
            
            # Если коллекция была пересоздана, нужно добавить события заново
            if args.recreate or COLLECTION_NAME not in client.collections.list_all():
                add_sample_events(collection)
                print("\n✅ События успешно добавлены в базу данных")
            else:
                print("\n💡 Коллекция уже существует. Используйте --recreate для пересоздания с новой конфигурацией")
        finally:
            client.close()
        
        return 0
    except Exception as e:
        print(f"❌ Ошибка: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())

