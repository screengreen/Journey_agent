"""Сервис для планирования задач парсинга."""

import logging
from typing import List

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from src.parsers.base import BaseParser
from src.storage.event_storage import EventStorage

logger = logging.getLogger(__name__)


class SchedulerService:
    """Сервис для планирования периодических задач парсинга."""

    def __init__(self, event_storage: EventStorage):
        """
        Инициализация планировщика.

        Args:
            event_storage: Хранилище событий
        """
        self.scheduler = AsyncIOScheduler()
        self.event_storage = event_storage
        self.parsers: List[BaseParser] = []

    def add_parser(self, parser: BaseParser, interval_minutes: int = 60):
        """
        Добавляет парсер в планировщик.

        Args:
            parser: Парсер для добавления
            interval_minutes: Интервал запуска в минутах
        """
        self.parsers.append(parser)

        async def parse_job():
            """Задача парсинга."""
            try:
                logger.info(f"Запуск парсинга для {parser.source_name}")
                # TODO: Реализовать логику парсинга в зависимости от типа парсера
                # events = await parser.parse()
                # processed_events = await self.event_storage.add_events(events)
                logger.info(f"Парсинг {parser.source_name} завершен")
            except Exception as e:
                logger.error(f"Ошибка при парсинге {parser.source_name}: {e}")

        self.scheduler.add_job(
            parse_job,
            trigger=IntervalTrigger(minutes=interval_minutes),
            id=f"parse_{parser.source_name}",
            replace_existing=True,
        )

    def start(self):
        """Запускает планировщик."""
        self.scheduler.start()
        logger.info("Планировщик запущен")

    def stop(self):
        """Останавливает планировщик."""
        self.scheduler.shutdown()
        logger.info("Планировщик остановлен")


