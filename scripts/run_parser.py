#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для запуска парсеров событий.

Запуск:
    python scripts/run_parser.py
"""

import asyncio
import sys
from pathlib import Path

# Добавляем корневую директорию проекта в путь
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.config import WEAVIATE_URL
from src.parsers.telegram import TelegramChannelParser
from src.services.scheduler import SchedulerService
from src.storage.event_storage import EventStorage
from src.storage.weaviate_client import WeaviateClient
from src.utils.logging import setup_logging

setup_logging()


async def main():
    """Основная функция."""
    try:
        # Инициализируем хранилище
        weaviate_client = WeaviateClient(weaviate_url=WEAVIATE_URL)
        event_storage = EventStorage(weaviate_client)

        # Создаем планировщик
        scheduler = SchedulerService(event_storage)

        # Добавляем парсеры
        telegram_parser = TelegramChannelParser()
        scheduler.add_parser(telegram_parser, interval_minutes=60)

        # Запускаем планировщик
        scheduler.start()

        print("✅ Парсеры запущены. Нажмите Ctrl+C для остановки.")

        # Ожидаем завершения
        try:
            await asyncio.Event().wait()
        except KeyboardInterrupt:
            print("\nПолучен сигнал остановки...")
        finally:
            scheduler.stop()
            weaviate_client.close()

    except Exception as e:
        print(f"❌ Ошибка: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())


