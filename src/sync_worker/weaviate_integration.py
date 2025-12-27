from __future__ import annotations

import logging
from typing import List, Optional

import weaviate
from weaviate.collections import Collection

from src.vdb import get_weaviate_client, create_collection_if_not_exists
from src.vdb import COLLECTION_NAME
from src.models.event import Event as VectorEvent
from src.sync_worker.event_miner_agent import Event as ExtractedEvent

# Настройка логирования
logger = logging.getLogger("sync-weaviate")


def get_weaviate_client_and_collection(
    force_recreate: bool = False,
) -> tuple[weaviate.WeaviateClient, Collection]:
    """
    Обёртка: получаем клиент и коллекцию Weaviate
    """
    client = get_weaviate_client()
    create_collection_if_not_exists()
    collection = client.collections.get(COLLECTION_NAME)
    return client, collection


class EventVectorMapper:
    """
    Адаптер между Event из EventExtractionAgent (ExtractedEvent)
    и Event для векторной БД (VectorEvent).

    Здесь НЕТ логики по добавлению username в tags – это делает upload_events_to_collection.
    """

    @staticmethod
    def to_vector_event(
        extracted: ExtractedEvent,
        owner_username: Optional[str] = None,
        channel_username: Optional[str] = None,
        source: str = "telegram_channel",
        country: Optional[str] = None,
    ) -> VectorEvent:
        # 1. title
        title = extracted.title
        if not title:
            candidate = extracted.description or extracted.original_text or ""
            title = (candidate[:77] + "...") if len(candidate) > 80 else (candidate or "Untitled event")

        # 2. description
        description = extracted.description or extracted.original_text or ""

        # 3. базовые теги (без username – он добавится на этапе записи в БД)
        tags: List[str] = []

        if extracted.event_type:
            tags.append(extracted.event_type)

        if extracted.is_online is True:
            tags.append("online")
        elif extracted.is_online is False:
            tags.append("offline")

        tags.append("telegram")

        # 4. source
        vector_source = source

        # 5. location
        location = extracted.location

        # 6. date/time → одна строка
        if extracted.date and extracted.time:
            date_str = f"{extracted.date} {extracted.time}"
        else:
            date_str = extracted.date or None

        # 7. url (если знаем канал и message_id)
        url: Optional[str] = None
        if channel_username and extracted.source_message_id:
            clean = channel_username.strip()
            if clean.startswith("https://t.me/"):
                clean = clean[len("https://t.me/") :]
            if clean.startswith("@"):
                clean = clean[1:]
            url = f"https://t.me/{clean}/{extracted.source_message_id}"

        # 8. country
        vector_country = country

        return VectorEvent(
            title=title,
            description=description,
            tags=tags,
            source=vector_source,
            country=vector_country,
            location=location,
            date=date_str,
            url=url,
        )

    @classmethod
    def map_events(
        cls,
        extracted_events: List[ExtractedEvent],
        owner_username: Optional[str] = None,
        channel_username: Optional[str] = None,
        source: str = "telegram_channel",
        country: Optional[str] = None,
    ) -> List[VectorEvent]:
        """
        Преобразует список ExtractedEvent → список VectorEvent.
        Поддерживает параметр channel_username (нужен для формирования URL).
        """
        return [
            cls.to_vector_event(
                e,
                owner_username=owner_username,
                channel_username=channel_username,
                source=source,
                country=country,
            )
            for e in extracted_events
        ]


def upload_events_to_collection(
    collection: Collection,
    events: List[VectorEvent],
    username: str,
) -> None:
    """
    Загружает события в Weaviate-коллекцию с тегом юзернэйма.
    """
    if not events:
        logger.info(f"📭 [WEAVIATE] Нет событий для загрузки (username={username})")
        return

    logger.info(f"📤 [WEAVIATE] Начинаем загрузку {len(events)} событий в коллекцию (username={username})")
    
    uploaded_count = 0
    with collection.batch.dynamic() as batch:
        for ev in events:
            data = ev.model_dump()
            tags = list(data.get("tags") or [])
            if username not in tags:
                tags.append(username)
            data["tags"] = tags

            batch.add_object(properties=data)
            uploaded_count += 1
            
            # Логируем каждое событие
            title = data.get("title", "Без названия")[:50]
            logger.debug(f"  📝 [WEAVIATE] Добавлено: {title}...")
    
    logger.info(f"✅ [WEAVIATE] Успешно загружено {uploaded_count} событий в базу данных")
    logger.info(f"📊 [WEAVIATE] Теги событий: {username}, source=telegram")
