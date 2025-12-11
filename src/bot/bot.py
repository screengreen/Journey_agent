"""Основной класс Telegram бота."""

import logging
import os

from telegram.ext import Application

from src.bot.handlers import register_commands, register_channel_handlers, register_search_handlers
from src.config import WEAVIATE_URL
from src.services.geolocation import GeolocationService
from src.services.vector_search import VectorSearchService
from src.storage.user_storage import UserStorage

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


class JourneyBot:
    """Telegram бот для поиска событий."""

    def __init__(self, token: str):
        """
        Инициализация бота.

        Args:
            token: Токен Telegram бота
        """
        self.token = token
        self.application = Application.builder().token(token).build()

        # Инициализируем сервисы
        self.user_storage = UserStorage()
        self.vector_search = VectorSearchService(weaviate_url=WEAVIATE_URL)
        self.geolocation = GeolocationService()

        # Сохраняем сервисы в bot_data для доступа из обработчиков
        self.application.bot_data["user_storage"] = self.user_storage
        self.application.bot_data["vector_search"] = self.vector_search
        self.application.bot_data["geolocation"] = self.geolocation

        # Регистрируем обработчики
        self._register_handlers()

    def _register_handlers(self):
        """Регистрирует все обработчики."""
        register_commands(self.application)
        register_channel_handlers(self.application)
        register_search_handlers(self.application)

    async def start(self):
        """Запускает бота."""
        logger.info("Запуск бота...")
        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling()
        logger.info("Бот запущен и готов к работе")

    async def stop(self):
        """Останавливает бота."""
        logger.info("Остановка бота...")
        await self.application.updater.stop()
        await self.application.stop()
        await self.application.shutdown()
        self.vector_search.close()
        logger.info("Бот остановлен")

    def run(self):
        """Запускает бота в синхронном режиме."""
        self.application.run_polling()


def create_bot() -> JourneyBot:
    """
    Создает и возвращает экземпляр бота.

    Returns:
        JourneyBot
    """
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN не установлен в переменных окружения")

    return JourneyBot(token)


