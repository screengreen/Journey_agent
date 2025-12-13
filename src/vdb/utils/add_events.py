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

try:
    import weaviate
    import weaviate.classes as wvc
except ImportError:
    weaviate = None
    wvc = None

# Добавляем корневую директорию проекта в путь
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from src.vdb.config import WEAVIATE_URL, COLLECTION_NAME


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


def create_collection_if_not_exists(force_recreate: bool = False) -> None:
    """
    Создает коллекцию Events, если она не существует.
    
    Args:
        client: Клиент Weaviate
        force_recreate: Если True, пересоздает коллекцию даже если она существует
    """
    client = get_client()
    if COLLECTION_NAME in client.collections.list_all():
        if force_recreate:
            print(f"ℹ️  Удаляю существующую коллекцию '{COLLECTION_NAME}' для пересоздания")
            client.collections.delete(COLLECTION_NAME)
        else:
            collection = client.collections.get(COLLECTION_NAME)
            total_count = collection.aggregate.over_all(total_count=True).total_count
            print(f"ℹ️  Коллекция '{COLLECTION_NAME}' уже существует")
            print(f"   Количество записей в коллекции: {total_count}")
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
                name="owner",
                description="Владелец события",
                data_type=wvc.config.DataType.TEXT,
                vectorize_property_name=False,  # Исключено из векторизации
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
            wvc.config.Property(
                name="uuid",
                description="UUID события",
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


