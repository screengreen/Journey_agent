#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Пример использования Self-RAG системы.

Запуск:
    # С реальным LLM:
    export OPENAI_API_KEY=your_api_key
    python examples/run_self_rag.py

    # С Dummy LLM (для тестирования):
    python examples/run_self_rag.py --dummy
"""

import argparse
import os
import sys
import traceback
from pathlib import Path

from langchain_openai import ChatOpenAI

# Добавляем корневую директорию проекта в путь
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.rag.dummy_llm import DummyLLM
from src.rag.self_rag_graph import run_self_rag


def main():
    """Основная функция для запуска примера."""
    parser = argparse.ArgumentParser(description="Пример использования Self-RAG системы")
    parser.add_argument(
        "--dummy",
        action="store_true",
        help="Использовать Dummy LLM вместо реального (для тестирования)",
    )
    parser.add_argument(
        "--relevance",
        type=str,
        default="YES",
        choices=["YES", "NO"],
        help="Ответ Dummy LLM для оценки релевантности (по умолчанию: YES)",
    )
    args = parser.parse_args()

    # Выбираем LLM
    if args.dummy:
        print("🤖 Используется Dummy LLM для тестирования\n")
        llm = DummyLLM(relevance_response=args.relevance)
    else:
        # Проверяем наличие API ключа
        if not os.getenv("OPENAI_API_KEY"):
            print("❌ Ошибка: OPENAI_API_KEY не установлен")
            print("   Установите переменную окружения: export OPENAI_API_KEY=your_api_key")
            print("   Или используйте --dummy для тестирования без API ключа")
            return 1
        llm = ChatOpenAI(base_url="https://students.openai.azure.com/")

    # Примеры запросов
    examples = [
        {
            "query": "Найди интересные музыкальные события на этой неделе",
            "user_tag": "user123",
        },
        {
            "query": "Какие выставки проходят в Москве?",
            "user_tag": "user456",
        },
    ]

    print("🚀 Запуск Self-RAG системы")
    print("💡 Совет: Убедитесь, что события добавлены в БД: python scripts/add_events.py\n")

    for i, example in enumerate(examples, 1):
        print(f"Пример {i}:")
        print(f"  Запрос: {example['query']}")
        print(f"  Тег пользователя: {example['user_tag']}")
        print("\n  Обработка...\n")

        try:
            response, logs = run_self_rag(
                user_query=example["query"],
                user_tag=example["user_tag"],
                llm=llm,
                return_logs=True,
            )

            print("  📋 Логи работы Self-RAG:")
            for log in logs:
                print(f"  {log}")
            print()

            print("  Ответ:")
            print(f"  {response}\n")
            print("-" * 80 + "\n")

        except Exception as e:
            print(f"  ❌ Ошибка: {e}\n")
            traceback.print_exc()
            print("-" * 80 + "\n")

    print("✅ Примеры завершены")
    return 0


if __name__ == "__main__":
    sys.exit(main())

