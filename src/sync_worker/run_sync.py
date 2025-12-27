from __future__ import annotations

import warnings
import sys
import os

# Подавляем ворнинги ДО любых импортов
os.environ["PYTHONWARNINGS"] = "ignore"
warnings.filterwarnings("ignore")
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", category=ResourceWarning)
warnings.filterwarnings("ignore", category=UserWarning)

import logging

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger("sync-worker")

from dotenv import load_dotenv

from src.sync_worker.config import AppSettings
from src.sync_worker.db_channels import init_db
from src.sync_worker.tg_parser import TelegramParser
from src.sync_worker.event_miner_agent import EventMinerAgent
from src.sync_worker.weaviate_integration import get_weaviate_client_and_collection
from src.sync_worker.sync_service import ChannelSyncServiceAsync

from src.utils.journey_llm import JourneyLLM

load_dotenv()


async def main_async() -> None:
    logger.info("=" * 60)
    logger.info("🚀 [SYNC-WORKER] Запуск sync-worker...")
    
    settings = AppSettings.from_env()
    logger.info(f"📂 [SYNC-WORKER] DB Path: {settings.db_path}")
    logger.info(f"⏰ [SYNC-WORKER] Интервал: {settings.sync_interval_hours}ч")
    logger.info(f"📊 [SYNC-WORKER] Лимит сообщений: {settings.channel_messages_limit}")

    init_db(settings.db_path, settings.seed_test_channels)
    logger.info("✅ [SYNC-WORKER] БД инициализирована")

    llm = JourneyLLM()
    logger.info("✅ [SYNC-WORKER] LLM инициализирован")

    event_agent = EventMinerAgent(llm=llm)
    parser = TelegramParser()
    logger.info("✅ [SYNC-WORKER] EventMinerAgent и TelegramParser готовы")

    client, collection = get_weaviate_client_and_collection(force_recreate=False)
    logger.info("✅ [SYNC-WORKER] Подключение к Weaviate установлено")

    service = ChannelSyncServiceAsync(
        db_path=settings.db_path,
        limit=settings.channel_messages_limit,
        parser=parser,
        event_agent=event_agent,
        weaviate_collection=collection,
    )

    logger.info("🔄 [SYNC-WORKER] Запуск цикла синхронизации...")
    
    try:
        await service.sync_forever(interval_hours=settings.sync_interval_hours)
    except Exception as e:
        logger.error(f"❌ [SYNC-WORKER] Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
    finally:
        client.close()
        logger.info("👋 [SYNC-WORKER] Соединение с Weaviate закрыто")


if __name__ == "__main__":
    logger.info("🏁 [SYNC-WORKER] Точка входа __main__")
    TelegramParser.run_async(main_async())
