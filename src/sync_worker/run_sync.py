from __future__ import annotations

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
    settings = AppSettings.from_env()

    init_db(settings.db_path, settings.seed_test_channels)

    llm = JourneyLLM()

    event_agent = EventMinerAgent(llm=llm)
    parser = TelegramParser()

    client, collection = get_weaviate_client_and_collection(force_recreate=False)

    service = ChannelSyncServiceAsync(
        db_path=settings.db_path,
        limit=settings.channel_messages_limit,
        parser=parser,
        event_agent=event_agent,
        weaviate_collection=collection,
    )

    try:
        await service.sync_forever(interval_hours=settings.sync_interval_hours)
    finally:
        client.close()


if __name__ == "__main__":
    TelegramParser.run_async(main_async())
