from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

from src.utils.paths import project_root

@dataclass
class AppSettings:
    """Глобальные настройки сервиса синхронизации каналов."""

    db_path: str
    sync_interval_hours: int
    weaviate_url: str
    channel_messages_limit: int
    seed_test_channels: bool

    @classmethod
    def from_env(cls) -> "AppSettings":
        return cls(
            db_path=os.getenv("JOURNEY_AGENT_DB_PATH", str(project_root() / "data" / "channels_db" / "users_channels.db")),
            sync_interval_hours=int(os.getenv("CHANNEL_SYNC_INTERVAL_HOURS", "6")),
            weaviate_url=os.getenv("WEAVIATE_URL", "http://localhost:8080"),
            channel_messages_limit=int(os.getenv("CHANNEL_MESSAGES_LIMIT", "10")),
            seed_test_channels=os.getenv("JOURNEY_AGENT_SEED_TEST_CHANNELS", True),
        )
