from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from dataclasses import dataclass
from typing import List

from db_scripts.db_channels import get_active_channels, update_last_synced, UserChannel
from tg_parsing.tg_parser import TelegramParser 
from tg_parsing.event_miner_agent import Event as ExtractedEvent, EventMinerAgent
from db_scripts.weaviate_integration import (
    EventVectorMapper,
    upload_events_to_collection,
)
from weaviate.collections import Collection

try:
    from telethon.tl.types import Message as TelegramMessage
except ImportError:
    TelegramMessage = None


@dataclass
class ChannelSyncServiceAsync:
    """
    - берёт личные каналы пользователей из SQLite
    - парсит сообщения из Telegram
    - прогоняет через EventMinerAgent
    - конвертирует ExtractedEvent → VectorEvent
    - кладёт их в Weaviate-коллекцию с тегом username
    """

    db_path: str
    limit: int
    parser: TelegramParser
    event_agent: EventMinerAgent
    weaviate_collection: Collection

    async def sync_once(self) -> None:
        channels: List[UserChannel] = get_active_channels(self.db_path)
        if not channels:
            print("ℹ️  Активных каналов в БД нет, синхронизировать нечего")
            return

        async with self.parser as parser:
            for ch in channels:
                print(f"🔄 Синхронизация канала {ch.username} — {ch.channel_url}")

                raw_messages = await parser.get_channel_messages(
                    ch.channel_url,
                    limit=self.limit,
                    reverse=True,
                )

                if not raw_messages:
                    print("  ↳ Сообщений не получено, пропускаю канал")
                    continue

                # ФИЛЬТРАЦИЯ: оставляем только поддерживаемые типы
                filtered_messages = []
                for m in raw_messages:
                    if isinstance(m, dict):
                        filtered_messages.append(m)
                    elif TelegramMessage and isinstance(m, TelegramMessage):
                        filtered_messages.append(m)
                    else:
                        print(f"  ⚠️ Пропускаю сообщение неподдерживаемого типа: {type(m)}")

                if not filtered_messages:
                    print("  ↳ После фильтрации не осталось пригодных сообщений")
                    continue

                print(f"  ↳ Сообщений после фильтрации по типу: {len(filtered_messages)}")

                # фильтруем по last_synced_at (если он есть)
                cutoff_ts = None
                if ch.last_synced_at:
                    try:
                        cutoff_dt = datetime.fromisoformat(ch.last_synced_at)
                        # делаем aware, если надо
                        if cutoff_dt.tzinfo is None:
                            cutoff_dt = cutoff_dt.replace(tzinfo=timezone.utc)
                        cutoff_ts = cutoff_dt.timestamp()
                    except Exception as e:
                        print(f"  ⚠️ Не удалось распарсить last_synced_at='{ch.last_synced_at}': {e}")

                if cutoff_ts is not None:
                    after_cutoff = []
                    for m in filtered_messages:
                        msg_date = getattr(m, "date", None)
                        if msg_date is None:
                            continue
                        # Telethon обычно даёт timezone-aware datetime
                        if msg_date.tzinfo is None:
                            msg_date = msg_date.replace(tzinfo=timezone.utc)
                        if msg_date.timestamp() > cutoff_ts:
                            after_cutoff.append(m)
                    filtered_messages = after_cutoff

                    print(f"  ↳ Сообщений новее last_synced_at={ch.last_synced_at}: {len(filtered_messages)}")

                if not filtered_messages:
                    print("  ↳ Нет новых сообщений, пропускаю канал")
                    update_last_synced(self.db_path, ch.id)
                    continue

                # 1) извлекаем события из Telegram
                extracted_events: List[ExtractedEvent] = self.event_agent.process_messages_batch(
                    filtered_messages,
                    batch_size=10,
                )
                print(f"  ↳ Извлечено событий: {len(extracted_events)}")

                if not extracted_events:
                    print("  ↳ Событий не найдено, пропускаю загрузку в Weaviate")
                    update_last_synced(self.db_path, ch.id)
                    continue

                # 2) конвертируем в VectorEvent для векторной БД
                vector_events = EventVectorMapper.map_events(
                    extracted_events,
                    owner_username=ch.username,
                    channel_username=ch.channel_url,
                    source="telegram_channel",
                    country=None,
                )
                print(f"  ↳ Подготовлено к загрузке в Weaviate: {len(vector_events)}")

                # 3) загружаем в Weaviate с тегом username
                upload_events_to_collection(
                    collection=self.weaviate_collection,
                    events=vector_events,
                    username=ch.username,
                )

                # 4) отмечаем, что канал синхронизирован
                update_last_synced(self.db_path, ch.id)
                print("  ✅ Синхронизация канала завершена\n")

    async def sync_forever(self, interval_hours: int) -> None:
        interval_sec = interval_hours * 3600
        while True:
            await self.sync_once()
            await asyncio.sleep(interval_sec)
