"""Конфигурация приложения."""

import os
from typing import Optional


# Weaviate настройки
WEAVIATE_URL: str = os.getenv("WEAVIATE_URL", "http://localhost:8080")
COLLECTION_NAME: str = os.getenv("COLLECTION_NAME", "Events")

# OpenAI настройки
OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# Telegram настройки
TELEGRAM_BOT_TOKEN: Optional[str] = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_API_ID: Optional[str] = os.getenv("TELEGRAM_API_ID")
TELEGRAM_API_HASH: Optional[str] = os.getenv("TELEGRAM_API_HASH")

# Геокодирование
YANDEX_GEOCODING_API_KEY: Optional[str] = os.getenv("YANDEX_GEOCODING_API_KEY")

# Ограничения
MAX_EVENTS: int = int(os.getenv("MAX_EVENTS", "15"))
MAX_ITERATIONS: int = int(os.getenv("MAX_ITERATIONS", "3"))

