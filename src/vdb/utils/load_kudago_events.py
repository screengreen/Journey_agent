#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для загрузки событий из JSON файлов KudaGo в Weaviate.

Запуск:
    python src/vdb/scripts/load_kudago_events.py --data-dir data/raw_data/real_events_data --owner user123
"""

import sys
from pathlib import Path

# Добавляем корневую директорию проекта в путь
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from src.vdb.client import get_weaviate_client
from src.vdb.config import COLLECTION_NAME

from uuid import uuid5, NAMESPACE_URL

def make_event_uuid(event) -> str:

    unique_key = event.description + event.title + str(event.location) + str(event.date) + str(event.url) +str(event.source) + str(event.country) + str(event.tags) + str(event.owner)
    event.uuid = str(uuid5(NAMESPACE_URL, f"description:{unique_key}"))
    return event

def load_events_to_weaviate(events: list, batch_size: int = 100, verbose: bool = True):
    """
    Загружает события в Weaviate.
    
    Args:
        events: Список событий (Event objects)
        batch_size: Размер батча для загрузки
        verbose: Выводить подробную информацию
    """
    client = get_weaviate_client()
    
    try:
        # Проверяем существование коллекции
        if COLLECTION_NAME not in client.collections.list_all():
            print(f"Коллекция '{COLLECTION_NAME}' не существует!")
            print("Создайте её командой: python src/vdb/scripts/add_events.py")
            return False
        
        collection = client.collections.get(COLLECTION_NAME)
        
        if verbose:
            print(f"📤 Загрузка {len(events)} событий в Weaviate...")
        
        # Загружаем батчами
        success_count = 0
        error_count = 0
        skipped_count = 0
        with collection.batch.dynamic() as batch:
            for i, event in enumerate(events, 1):
                try:
                    event = make_event_uuid(event)
                    uuid = event.uuid
                    if collection.data.exists(uuid):
                        # print(f"   Событие '{event.title}' уже существует")
                        skipped_count += 1
                        continue

                    event_dict = event.model_dump(exclude_none=True)
                    batch.add_object(properties=event_dict, uuid=uuid)
                    success_count += 1
                    
                    if verbose and i % batch_size == 0:
                        print(f"  Загружено: {i}/{len(events)}")
                        
                except Exception as e:
                    error_count += 1
                    if verbose:
                        print(f"  Ошибка при загрузке события '{event.title}': {e}")
        
        if verbose:
            print("\nЗагрузка завершена!")
            print(f"   Успешно: {success_count}")
            print(f"   Ошибок: {error_count}")
            print(f"   Пропущено: {skipped_count}")
        
        return True
        
    finally:
        client.close()



