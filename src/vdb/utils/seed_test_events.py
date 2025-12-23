#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для заполнения коллекции Events тестовыми событиями в соответствии с моделью Event.
"""

import sys
from pathlib import Path

# Добавляем корневую директорию проекта в путь
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from src.models.event import Event
from src.vdb.client import get_weaviate_client
from src.vdb.config import COLLECTION_NAME
from src.vdb.utils.test_connection import wait_for_weaviate
from src.vdb.utils.add_events import create_collection_if_not_exists
from uuid import uuid5, NAMESPACE_URL


def make_event_uuid(event: Event) -> Event:
    """Генерирует UUID для события на основе его уникальных полей."""
    unique_key = (
        f"{event.title}:{event.description}:{event.location or ''}:"
        f"{event.date or ''}:{event.url or ''}:{event.source or ''}:"
        f"{event.country or ''}:{':'.join(event.tags)}:{event.owner or ''}"
    )
    event.uuid = str(uuid5(NAMESPACE_URL, f"event:{unique_key}"))
    return event


def create_test_events() -> list[Event]:
    """Создает список тестовых событий для заполнения коллекции."""
    
    events = [
        # Москва - события с owner="all"
        Event(
            title="Фотовыставка 'Москва глазами фотографов'",
            owner="all",
            description="Выставка фотографий Москвы разных эпох. От дореволюционных снимков до современности.",
            tags=["all", "exhibition", "msk", "фото", "культура"],
            source="photocenter",
            country="Россия",
            location="Москва, Центр фотографии имени братьев Люмьер",
            date="2024-12-25 10:00",
            url="https://example.com/photos",
        ),
        Event(
            title="Джазовый концерт в Blue Note",
            owner="all",
            description="Вечер джазовой музыки с участием известных музыкантов. Уютная атмосфера, живая музыка.",
            tags=["all", "concert", "msk", "джаз", "музыка"],
            source="eventbrite",
            country="Россия",
            location="Москва, ул. Арбат, д. 1, клуб Blue Note",
            date="2024-12-26 20:00",
            url="https://example.com/jazz-concert",
        ),
        Event(
            title="Рок-фестиваль 'Лето в городе'",
            owner="all",
            description="Масштабный рок-фестиваль под открытым небом с участием топовых российских групп.",
            tags=["all", "festival", "msk", "рок", "музыка", "outdoor"],
            source="afisha",
            country="Россия",
            location="Москва, Парк Горького, главная сцена",
            date="2024-12-27 15:00",
            url="https://example.com/rock-festival",
        ),
        Event(
            title="Современное искусство в Третьяковке",
            owner="all",
            description="Выставка современного российского искусства. Инсталляции, перформансы, мультимедиа.",
            tags=["all", "exhibition", "msk", "современное искусство"],
            source="tretyakov",
            country="Россия",
            location="Москва, Третьяковская галерея, Крымский Вал, 10",
            date="2024-12-28 11:00",
            url="https://example.com/modern-art",
        ),
        Event(
            title="Классический концерт в Консерватории",
            owner="all",
            description="Симфонический оркестр исполняет произведения Чайковского и Рахманинова.",
            tags=["all", "concert", "msk", "классика", "симфоническая музыка"],
            source="conservatory",
            country="Россия",
            location="Москва, Московская консерватория, Большой зал",
            date="2024-12-29 19:00",
            url="https://example.com/classical",
        ),
        Event(
            title="Новогодний концерт в Большом театре",
            owner="all",
            description="Праздничный новогодний концерт классической музыки в Большом театре.",
            tags=["all", "concert", "msk", "новый год", "классика"],
            source="bolshoi",
            country="Россия",
            location="Москва, Большой театр, Театральная площадь, 1",
            date="2024-12-31 19:00",
            url="https://example.com/ny-concert",
        ),
        
        # Санкт-Петербург - события с owner="all"
        Event(
            title="Выставка 'Импрессионисты в Эрмитаже'",
            owner="all",
            description="Уникальная выставка картин импрессионистов из коллекции Эрмитажа. Работы Моне, Ренуара, Дега.",
            tags=["all", "exhibition", "spb", "импрессионизм", "живопись"],
            source="hermitage",
            country="Россия",
            location="Санкт-Петербург, Эрмитаж, Дворцовая площадь, 2",
            date="2024-12-30 10:00",
            url="https://example.com/impressionists",
        ),
        Event(
            title="Балет 'Лебединое озеро'",
            owner="all",
            description="Шедевр Петра Ильича Чайковского, символ русского балетного искусства.",
            tags=["all", "theater", "spb", "балет", "классика"],
            source="mariinsky",
            country="Россия",
            location="Санкт-Петербург, Мариинский театр, Театральная площадь, 1",
            date="2024-12-31 19:30",
            url="https://example.com/swan-lake",
        ),
        Event(
            title="Концерт под звёздами Interstellar",
            owner="all",
            description="Санкт-Петербургский планетарий приглашает в путешествие по межзвёздному пространству в компании с известным пианистом.",
            tags=["all", "concert", "spb", "космос", "планетарий"],
            source="planetarium",
            country="Россия",
            location="Санкт-Петербург, Планетарий, Александровский парк, 4",
            date="2025-01-01 21:00",
            url="https://example.com/interstellar",
        ),
        
        # События пользователя user123
        Event(
            title="Личная встреча с друзьями",
            owner="user123",
            description="Встреча с друзьями в центре Москвы. Обсуждение планов на новый год.",
            tags=["all", "user123", "meeting", "msk", "личное"],
            source="personal",
            country="Россия",
            location="Москва, кафе на Тверской",
            date="2024-12-25 18:00",
            url=None,
        ),
        Event(
            title="Личный мастер-класс по фотографии",
            owner="user123",
            description="Мастер-класс по портретной фотографии для личного развития.",
            tags=["all", "user123", "education", "msk", "фотография"],
            source="personal",
            country="Россия",
            location="Москва, фотостудия",
            date="2024-12-27 14:00",
            url=None,
        ),
        
        # События пользователя user456
        Event(
            title="Персональная экскурсия по Эрмитажу",
            owner="user456",
            description="Приватная экскурсия по залам Эрмитажа с персональным гидом.",
            tags=["all", "user456", "exhibition", "spb", "экскурсия"],
            source="personal",
            country="Россия",
            location="Санкт-Петербург, Эрмитаж",
            date="2024-12-28 11:00",
            url=None,
        ),
        Event(
            title="Концерт в личном клубе",
            owner="user456",
            description="Выступление джазового коллектива в закрытом клубе для членов.",
            tags=["all", "user456", "concert", "spb", "джаз"],
            source="personal",
            country="Россия",
            location="Санкт-Петербург, джаз-клуб",
            date="2024-12-29 20:00",
            url=None,
        ),
    ]
    
    return events


def seed_collection(force_recreate: bool = False):
    """
    Заполняет коллекцию Events тестовыми событиями.
    
    Args:
        force_recreate: Если True, пересоздает коллекцию даже если она существует
    """
    print("🔄 Ожидание подключения к Weaviate...")
    wait_for_weaviate()
    
    print("📋 Создание/проверка коллекции...")
    create_collection_if_not_exists(force_recreate=force_recreate)
    
    client = get_weaviate_client()
    try:
        collection = client.collections.get(COLLECTION_NAME)
        
        # Создаем тестовые события
        test_events = create_test_events()
        print(f"\n📤 Загрузка {len(test_events)} тестовых событий...")
        
        success_count = 0
        error_count = 0
        skipped_count = 0
        
        with collection.batch.dynamic() as batch:
            for i, event in enumerate(test_events, 1):
                try:
                    # Генерируем UUID
                    event = make_event_uuid(event)
                    uuid = event.uuid
                    
                    # Проверяем существование
                    if collection.data.exists(uuid):
                        skipped_count += 1
                        continue
                    
                    # Преобразуем в словарь и загружаем
                    # Исключаем uuid из свойств, так как он передается отдельно
                    event_dict = event.model_dump(exclude={"uuid"}, exclude_none=True)
                    
                    batch.add_object(properties=event_dict, uuid=uuid)
                    success_count += 1
                    
                    if i % 5 == 0:
                        print(f"  Загружено: {i}/{len(test_events)}")
                        
                except Exception as e:
                    error_count += 1
                    print(f"  ❌ Ошибка при загрузке события '{event.title}': {e}")
        
        print(f"\n✅ Загрузка завершена!")
        print(f"   Успешно: {success_count}")
        print(f"   Ошибок: {error_count}")
        print(f"   Пропущено: {skipped_count}")
        
        # Проверяем итоговое количество
        total_count = collection.aggregate.over_all(total_count=True).total_count
        print(f"\n📊 Всего событий в коллекции: {total_count}")
        
    finally:
        client.close()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Заполнение коллекции Events тестовыми событиями")
    parser.add_argument(
        "--recreate",
        action="store_true",
        help="Пересоздать коллекцию даже если она существует",
    )
    
    args = parser.parse_args()
    seed_collection(force_recreate=args.recreate)

