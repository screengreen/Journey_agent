"""Конфигурация для Self-RAG системы."""

import os
from typing import Optional


# Weaviate настройки
WEAVIATE_URL: str = os.getenv("WEAVIATE_URL", "http://localhost:8080")
COLLECTION_NAME: str = os.getenv("COLLECTION_NAME", "Events")

# OpenAI настройки
OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o")

# Ограничения
MAX_EVENTS: int = 15
MAX_ITERATIONS: int = 3

