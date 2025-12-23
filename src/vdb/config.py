"""Конфигурация для Self-RAG системы."""

import os
from typing import Optional

try:
    from dotenv import load_dotenv

    # Загружаем переменные окружения из .env файла, если он существует
    load_dotenv()
except ImportError:
    # Если python-dotenv не установлен, просто пропускаем
    pass


# Weaviate настройки
WEAVIATE_URL: str = os.getenv("WEAVIATE_URL", "http://localhost:8080")
COLLECTION_NAME: str = os.getenv("COLLECTION_NAME", "Events")

# LLM настройки
OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# Mistral настройки
MISTRAL_API_KEY: Optional[str] = os.getenv("MISTRAL_API_KEY")
MISTRAL_MODEL: str = os.getenv("MISTRAL_MODEL", "mistral-small-latest")

# Ограничения
MAX_EVENTS: int = 15
MAX_ITERATIONS: int = 3

