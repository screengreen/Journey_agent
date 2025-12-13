"""Модуль для работы с векторной базой данных Weaviate.

Этот модуль предоставляет полный набор инструментов для работы с Weaviate:
- Подключение к базе данных (client)
- Конфигурация (config)
- RAG система (rag)
- Утилиты для управления данными (utils)
"""

# ============================================================================
# КОНФИГУРАЦИЯ
# ============================================================================
from src.vdb.config import (
    WEAVIATE_URL,
    COLLECTION_NAME,
    OPENAI_API_KEY,
    OPENAI_MODEL,
    MAX_EVENTS,
    MAX_ITERATIONS,
)

# ============================================================================
# КЛИЕНТ WEAVIATE
# ============================================================================
from src.vdb.client import get_weaviate_client

# ============================================================================
# RAG СИСТЕМА
# ============================================================================
from src.vdb.rag import (
    EventRetriever,
    create_self_rag_graph,
    run_self_rag,
    check_memory,
)

# ============================================================================
# УТИЛИТЫ
# ============================================================================
from src.vdb.utils import (
    wait_for_weaviate,
    create_collection_if_not_exists,
    get_client,
    load_events_to_weaviate,
)

# ============================================================================
# ПУБЛИЧНЫЙ API
# ============================================================================
__all__ = [
    # Конфигурация
    "WEAVIATE_URL",
    "COLLECTION_NAME",
    "OPENAI_API_KEY",
    "OPENAI_MODEL",
    "MAX_EVENTS",
    "MAX_ITERATIONS",
    # Клиент
    "get_weaviate_client",
    # RAG система
    "EventRetriever",
    "create_self_rag_graph",
    "run_self_rag",
    "check_memory",
    # Утилиты
    "wait_for_weaviate",
    "create_collection_if_not_exists",
    "get_client",
    "load_events_to_weaviate",
]

