from __future__ import annotations

from dotenv import load_dotenv

from db_scripts.config import AppSettings
from db_scripts.db_channels import init_db
from tg_parsing.tg_parser import TelegramParser
from tg_parsing.event_miner_agent import EventMinerAgent
from db_scripts.journey_llm import JourneyLLM
from db_scripts.weaviate_integration import get_weaviate_client_and_collection
from db_scripts.sync_service import ChannelSyncServiceAsync


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
