#!/usr/bin/env python3
"""Тест импортов для модуля vdb."""

import sys
from pathlib import Path

# Добавляем корневую директорию проекта в путь
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

def test_imports():
    """Проверяем все импорты модуля vdb."""
    print("🔍 Проверка импортов модуля vdb...")
    print("=" * 60)
    
    try:
        # ============================================================
        # ТЕСТ 1: Проверяем основной модуль vdb (все в одном)
        # ============================================================
        print("\n📦 Тест 1: Импорт всего модуля vdb")
        from src.vdb import (
            # Конфигурация
            WEAVIATE_URL,
            COLLECTION_NAME,
            OPENAI_API_KEY,
            OPENAI_MODEL,
            MAX_EVENTS,
            MAX_ITERATIONS,
            # Клиент
            get_weaviate_client,
            # RAG система
            EventRetriever,
            create_self_rag_graph,
            run_self_rag,
            check_memory,
            # Утилиты
            wait_for_weaviate,
            create_collection_if_not_exists,
            get_client,
            load_events_to_weaviate,
        )
        print("   ✅ Все экспорты из src.vdb доступны")
        print(f"      - WEAVIATE_URL: {WEAVIATE_URL}")
        print(f"      - COLLECTION_NAME: {COLLECTION_NAME}")
        print(f"      - MAX_EVENTS: {MAX_EVENTS}")
        print(f"      - MAX_ITERATIONS: {MAX_ITERATIONS}")
        
        # ============================================================
        # ТЕСТ 2: Проверяем подмодули
        # ============================================================
        print("\n📦 Тест 2: Импорт подмодулей")
        
        # Config
        from src.vdb.config import OPENAI_MODEL
        print("   ✅ src.vdb.config")
        
        # Client
        from src.vdb.client import get_weaviate_client
        print("   ✅ src.vdb.client")
        
        # RAG
        from src.vdb.rag import EventRetriever, create_self_rag_graph, run_self_rag
        print("   ✅ src.vdb.rag")
        
        from src.vdb.rag.memory import check_memory
        print("   ✅ src.vdb.rag.memory")
        
        from src.vdb.rag.prompts import (
            RELEVANCE_EVALUATION_PROMPT,
            QUERY_REFORMULATION_PROMPT,
            RESPONSE_GENERATION_PROMPT,
        )
        print("   ✅ src.vdb.rag.prompts")
        
        from src.vdb.rag.retriever import EventRetriever
        print("   ✅ src.vdb.rag.retriever")
        
        from src.vdb.rag.self_rag_graph import create_self_rag_graph, run_self_rag
        print("   ✅ src.vdb.rag.self_rag_graph")
        
        # Utils
        from src.vdb.utils import (
            wait_for_weaviate,
            create_collection_if_not_exists,
            load_events_to_weaviate,
        )
        print("   ✅ src.vdb.utils")
        
        from src.vdb.utils.test_connection import wait_for_weaviate
        print("   ✅ src.vdb.utils.test_connection")
        
        from src.vdb.utils.add_events import create_collection_if_not_exists, get_client
        print("   ✅ src.vdb.utils.add_events")
        
        from src.vdb.utils.load_kudago_events import load_events_to_weaviate
        print("   ✅ src.vdb.utils.load_kudago_events")
        
        # ============================================================
        # ИТОГ
        # ============================================================
        print("\n" + "=" * 60)
        print("✅ ВСЕ ИМПОРТЫ ПРОШЛИ УСПЕШНО!")
        print("=" * 60)
        print("\n📝 Доступные функции из src.vdb:")
        print("   • Конфигурация: WEAVIATE_URL, COLLECTION_NAME, OPENAI_API_KEY, OPENAI_MODEL, MAX_EVENTS, MAX_ITERATIONS")
        print("   • Клиент: get_weaviate_client()")
        print("   • RAG: EventRetriever, create_self_rag_graph(), run_self_rag(), check_memory()")
        print("   • Утилиты: wait_for_weaviate(), create_collection_if_not_exists(), get_client(), load_events_to_weaviate()")
        
        return True
        
    except ImportError as e:
        print("\n" + "=" * 60)
        print(f"❌ ОШИБКА ИМПОРТА: {e}")
        print("=" * 60)
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_imports()
    sys.exit(0 if success else 1)

