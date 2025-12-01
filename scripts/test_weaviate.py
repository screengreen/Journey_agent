#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Небольшой smoke-тест для локального кластера Weaviate.

Запуск:
    pip install "weaviate-client>=4.6,<5" requests
    python scripts/test_weaviate.py

Переменные окружения:
    WEAVIATE_URL                — адрес сервера (по умолчанию http://localhost:8080)
    WEAVIATE_TEST_COLLECTION    — имя коллекции для проверки (по умолчанию SmokeTestJourneys)
    DROP_COLLECTION_AFTER_TEST  — если "0", коллекция останется после теста
"""

from __future__ import annotations

import os
import sys
import time
from typing import Sequence
from urllib.parse import urlparse

import requests
import weaviate
import weaviate.classes as wvc


WEAVIATE_URL = os.getenv("WEAVIATE_URL", "http://localhost:8080").rstrip("/")
COLLECTION_NAME = os.getenv("WEAVIATE_TEST_COLLECTION", "SmokeTestJourneys")
DROP_COLLECTION = os.getenv("DROP_COLLECTION_AFTER_TEST", "1") != "0"
READY_ENDPOINT = f"{WEAVIATE_URL}/v1/.well-known/ready"

JOURNEYS: Sequence[dict[str, str]] = (
    {
        "title": "Сёрф на Бали",
        "description": "Чангу, утренние волны и стабильный коворкинг рядом с океаном.",
        "country": "Indonesia",
    },
    {
        "title": "Доломиты осенью",
        "description": "Легкий хайкинг к массиву Тре-Чиме и ночёвки в rifugio.",
        "country": "Italy",
    },
    {
        "title": "Саппоро зимой",
        "description": "Фестиваль снежных скульптур и поездки на онсены Хоккайдо.",
        "country": "Japan",
    },
)


def wait_for_ready(timeout: int = 60) -> None:
    """Ожидаем, пока кластер ответит READY, иначе бросаем исключение."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            response = requests.get(READY_ENDPOINT, timeout=3)
            if response.ok:
                # Weaviate 1.25.x может возвращать пустой 200 (готов) или JSON {"status":"READY"}
                if not response.text or response.json().get("status") == "READY":
                    print("✅  Weaviate готов к работе")
                    return
        except (requests.RequestException, ValueError):
            # ValueError для случая, когда response.json() падает на пустом ответе
            pass
        time.sleep(1)
    raise TimeoutError(f"Weaviate не ответил READY за {timeout} секунд")


def recreate_collection(client: weaviate.WeaviateClient) -> weaviate.collections.Collection:
    if COLLECTION_NAME in client.collections.list_all():
        print(f"ℹ️  Удаляю существующую коллекцию '{COLLECTION_NAME}'")
        client.collections.delete(COLLECTION_NAME)

    print(f"ℹ️  Создаю коллекцию '{COLLECTION_NAME}'")
    client.collections.create(
        name=COLLECTION_NAME,
        description="Smoke-тест Journey_agent",
        properties=[
            wvc.config.Property(
                name="title",
                description="Название заметки",
                data_type=wvc.config.DataType.TEXT,
            ),
            wvc.config.Property(
                name="description",
                description="Описание маршрута",
                data_type=wvc.config.DataType.TEXT,
            ),
            wvc.config.Property(
                name="country",
                description="Страна",
                data_type=wvc.config.DataType.TEXT,
            ),
        ],
        vectorizer_config=wvc.config.Configure.Vectorizer.text2vec_contextionary(),
    )

    return client.collections.get(COLLECTION_NAME)


def load_sample_data(collection: weaviate.collections.Collection) -> None:
    print("ℹ️  Загружаю тестовые объекты")
    with collection.batch.dynamic() as batch:
        for journey in JOURNEYS:
            batch.add_object(properties=journey)


def run_query(collection: weaviate.collections.Collection) -> None:
    print("ℹ️  Выполняю поиск near_text")
    result = collection.query.near_text(
        query="теплый океан и серфинг рядом с коворкингом",
        limit=2,
        return_metadata=wvc.query.MetadataQuery(distance=True),
    )

    if not result.objects:
        raise RuntimeError("Поиск не вернул результатов")

    print("🔎  Релевантные результаты:")
    for obj in result.objects:
        distance = getattr(obj.metadata, "distance", None)
        props = obj.properties
        print(f" • {props['title']} ({props['country']}) — distance={distance:.3f}")


def main() -> int:
    try:
        wait_for_ready()
    except TimeoutError as err:
        print(f"❌  {err}", file=sys.stderr)
        return 1

    # Подключение к Weaviate используя v4 API
    parsed = urlparse(WEAVIATE_URL)
    http_port = parsed.port or (443 if parsed.scheme == "https" else 8080)
    http_secure = parsed.scheme == "https"
    hostname = parsed.hostname or "localhost"
    
    # Для локального подключения используем connect_to_local, для кастомного - connect_to_custom с gRPC
    if hostname in ("localhost", "127.0.0.1") and http_port == 8080 and not http_secure:
        client = weaviate.connect_to_local()
    else:
        # Для кастомного URL нужны и HTTP и gRPC параметры (gRPC обычно на 50051)
        client = weaviate.connect_to_custom(
            http_host=hostname,
            http_port=http_port,
            http_secure=http_secure,
            grpc_host=hostname,
            grpc_port=50051,
            grpc_secure=http_secure,
        )

    try:
        collection = recreate_collection(client)
        load_sample_data(collection)
        run_query(collection)
        print("✅  Smoke-тест пройден")
    except Exception as exc:  # pylint: disable=broad-except
        print(f"❌  Тест завершился ошибкой: {exc}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1
    finally:
        if DROP_COLLECTION:
            try:
                client.collections.delete(COLLECTION_NAME)
                print(f"ℹ️  Коллекция '{COLLECTION_NAME}' удалена")
            except Exception:  # pylint: disable=broad-except
                pass
        client.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())

