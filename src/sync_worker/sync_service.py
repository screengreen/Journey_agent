from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from dataclasses import dataclass
from typing import List

from src.sync_worker.db_channels import get_active_channels, update_last_synced, UserChannel
from src.sync_worker.tg_parser import TelegramParser 
from src.sync_worker.event_miner_agent import Event as ExtractedEvent, EventMinerAgent
from src.sync_worker.weaviate_integration import (EventVectorMapper, upload_events_to_collection)
from weaviate.collections import Collection
from telethon.tl.types import Message as TelegramMessage, MessageService

# Настройка логирования
logger = logging.getLogger("sync-service")

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
        logger.info(f"🔄 [SYNC-SERVICE] Найдено каналов для синхронизации: {len(channels)}")
        
        if not channels:
            logger.info("ℹ️  [SYNC-SERVICE] Активных каналов в БД нет, синхронизировать нечего")
            return

        for ch in channels:
            logger.info(f"📋 [SYNC-SERVICE] Канал: user_id={ch.user_id}, name={ch.channel_name}, url={ch.channel_url}")

        async with self.parser as parser:
            for ch in channels:
                display_name = ch.channel_name or ch.username or f"user_{ch.user_id}"
                logger.info(f"🔄 [SYNC-SERVICE] ▶ Начинаю синхронизацию канала: {display_name}")
                logger.info(f"   URL: {ch.channel_url}")
                logger.info(f"   User ID: {ch.user_id}")

                raw_messages = await parser.get_channel_messages(
                    ch.channel_url,
                    limit=self.limit,
                    reverse=False,
                )

                if not raw_messages:
                    logger.warning(f"   ⚠️ [SYNC-SERVICE] Сообщений не получено, пропускаю канал")
                    continue

                logger.info(f"   📨 [SYNC-SERVICE] Получено сырых сообщений: {len(raw_messages)}")

                # ФИЛЬТРАЦИЯ: оставляем только поддерживаемые типы
                filtered_messages = []
                skipped_service = 0
                for m in raw_messages:
                    if isinstance(m, dict):
                        filtered_messages.append(m)
                    elif isinstance(m, MessageService):
                        # Служебные сообщения (пин, вступление и т.д.) — пропускаем молча
                        skipped_service += 1
                    elif isinstance(m, TelegramMessage):
                        # Обычные сообщения с текстом
                        if m.message:  # Только если есть текст
                            filtered_messages.append(m)
                    else:
                        logger.warning(f"   ⚠️ [SYNC-SERVICE] Пропускаю сообщение неподдерживаемого типа: {type(m)}")
                
                if skipped_service > 0:
                    logger.debug(f"   ℹ️ [SYNC-SERVICE] Пропущено служебных сообщений: {skipped_service}")

                if not filtered_messages:
                    logger.warning("   ⚠️ [SYNC-SERVICE] После фильтрации не осталось пригодных сообщений")
                    continue

                logger.info(f"   📝 [SYNC-SERVICE] Сообщений после фильтрации по типу: {len(filtered_messages)}")

                # фильтруем по last_synced_at (если он есть)
                cutoff_ts = None
                if ch.last_synced_at:
                    try:
                        cutoff_dt = datetime.fromisoformat(ch.last_synced_at)
                        cutoff_ts = cutoff_dt.timestamp()
                        logger.info(f"   ⏰ [SYNC-SERVICE] Фильтрация по дате last_synced_at: {ch.last_synced_at}")
                    except Exception as e:
                        logger.warning(f"   ⚠️ [SYNC-SERVICE] Не удалось распарсить last_synced_at='{ch.last_synced_at}': {e}")

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

                    logger.info(f"   📅 [SYNC-SERVICE] Сообщений новее last_synced_at: {len(filtered_messages)}")

                if not filtered_messages:
                    logger.info("   ⏭️ [SYNC-SERVICE] Нет новых сообщений, пропускаю канал")
                    continue

                # 1) извлекаем события из Telegram
                logger.info(f"   🤖 [SYNC-SERVICE] Запускаю EventMinerAgent для извлечения событий...")
                extracted_events: List[ExtractedEvent] = self.event_agent.process_messages_batch(
                    filtered_messages,
                    batch_size=10,
                )
                logger.info(f"   🎯 [SYNC-SERVICE] Извлечено событий: {len(extracted_events)}")

                if not extracted_events:
                    logger.info("   ⏭️ [SYNC-SERVICE] Событий не найдено, пропускаю загрузку в Weaviate")
                    continue

                # Логируем извлечённые события
                for i, ev in enumerate(extracted_events[:3]):  # Логируем первые 3
                    logger.info(f"      📌 Событие {i+1}: {ev.title or 'Без названия'}")

                # 2) конвертируем в VectorEvent для векторной БД
                owner_tag = ch.username or f"user_{ch.user_id}"
                vector_events = EventVectorMapper.map_events(
                    extracted_events,
                    owner_username=owner_tag,
                    channel_username=ch.channel_url,
                    source="telegram_channel",
                    country=None,
                )
                logger.info(f"   📦 [SYNC-SERVICE] Подготовлено к загрузке в Weaviate: {len(vector_events)}")

                # 3) загружаем в Weaviate с тегом username/user_id
                logger.info(f"   💾 [SYNC-SERVICE] Загружаю события в Weaviate (tag={owner_tag})...")
                upload_events_to_collection(
                    collection=self.weaviate_collection,
                    events=vector_events,
                    username=owner_tag,
                )

                # 4) отмечаем, что канал синхронизирован
                update_last_synced(self.db_path, ch.id)
                logger.info(f"   ✅ [SYNC-SERVICE] Синхронизация канала {display_name} завершена!")
                logger.info(f"   📊 [SYNC-SERVICE] Итого загружено: {len(vector_events)} событий\n")

    async def sync_forever(self, interval_hours: int) -> None:
        interval_sec = interval_hours * 3600
        logger.info(f"🔄 [SYNC-SERVICE] Запуск бесконечного цикла синхронизации (интервал: {interval_hours}ч)")
        
        while True:
            try:
                logger.info("=" * 60)
                logger.info("🔄 [SYNC-SERVICE] Начало цикла синхронизации")
                await self.sync_once()
                logger.info("✅ [SYNC-SERVICE] Цикл синхронизации завершён")
            except Exception as e:
                logger.error(f"❌ [SYNC-SERVICE] Ошибка в цикле синхронизации: {e}")
                import traceback
                traceback.print_exc()
            
            logger.info(f"😴 [SYNC-SERVICE] Следующая синхронизация через {interval_hours}ч ({interval_sec}с)")
            await asyncio.sleep(interval_sec)
