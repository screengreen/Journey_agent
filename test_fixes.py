#!/usr/bin/env python3
"""
Тест исправлений для проблем с количеством мероприятий и временем.
"""
import sys
from pathlib import Path

# Добавляем корень проекта в sys.path
sys.path.insert(0, str(Path(__file__).parent))

from src.vdb.rag.self_rag_graph import run_self_rag
from src.planner_agent.graph import PlanningGraph
from src.utils.journey_llm import JourneyLLM


def test_max_events_constraint():
    """Тест 1: Проверка соблюдения ограничения на количество событий."""
    print("\n" + "="*80)
    print("ТЕСТ 1: Проверка ограничения max_events")
    print("="*80)
    
    # Запрос с явным ограничением на 2 события
    query = "Хочу посетить 2 места в Москве, время с 10 до 14 часов"
    
    print(f"\n📝 Запрос: {query}")
    print("\nОжидаемый результат:")
    print("  - max_events должно быть извлечено = 2")
    print("  - В плане должно быть не более 2 событий")
    print("  - start_time = 10:00, end_time = 14:00")
    
    llm = JourneyLLM()
    
    # Этап 1: Self-RAG (извлечение constraints)
    print("\n🔍 Этап 1: Self-RAG - извлечение constraints...")
    input_data, logs = run_self_rag(query, llm=llm, return_logs=True)
    
    print("\n📋 Логи Self-RAG:")
    for log in logs:
        print(f"  {log}")
    
    print(f"\n✅ Извлеченные constraints:")
    print(f"  - max_events: {input_data.constraints.max_events}")
    print(f"  - start_time: {input_data.constraints.start_time}")
    print(f"  - end_time: {input_data.constraints.end_time}")
    print(f"  - Найдено событий: {len(input_data.events)}")
    
    # Этап 2: Planning Graph (создание плана)
    print("\n🗺️ Этап 2: Planning Graph - создание плана...")
    graph = PlanningGraph(llm)
    output = graph.run(input_data)
    
    print(f"\n✅ Результат:")
    print(f"  - Событий в плане: {len(output.final_plan.items)}")
    print(f"  - Время первого события: {output.final_plan.items[0].start_time if output.final_plan.items else 'N/A'}")
    print(f"  - Время последнего события: {output.final_plan.items[-1].end_time if output.final_plan.items else 'N/A'}")
    
    # Проверка
    success = True
    if input_data.constraints.max_events != 2:
        print(f"\n❌ ОШИБКА: max_events не извлечен правильно (получено: {input_data.constraints.max_events}, ожидалось: 2)")
        success = False
    
    if len(output.final_plan.items) > 2:
        print(f"\n❌ ОШИБКА: план содержит больше 2 событий (получено: {len(output.final_plan.items)})")
        success = False
    
    if success:
        print("\n✅ ТЕСТ ПРОЙДЕН!")
    else:
        print("\n❌ ТЕСТ НЕ ПРОЙДЕН!")
    
    return success


def test_time_constraint():
    """Тест 2: Проверка соблюдения временных ограничений."""
    print("\n" + "="*80)
    print("ТЕСТ 2: Проверка временных ограничений")
    print("="*80)
    
    # Запрос с явными временными рамками
    query = "Хочу посетить немного мест в Санкт-Петербурге, время с 12:00 до 15:00"
    
    print(f"\n📝 Запрос: {query}")
    print("\nОжидаемый результат:")
    print("  - start_time = 12:00")
    print("  - end_time = 15:00")
    print("  - max_events примерно 3-4")
    print("  - Все события в плане должны быть в диапазоне 12:00-15:00")
    
    llm = JourneyLLM()
    
    # Этап 1: Self-RAG
    print("\n🔍 Этап 1: Self-RAG - извлечение constraints...")
    input_data, logs = run_self_rag(query, llm=llm, return_logs=True)
    
    print("\n📋 Логи Self-RAG:")
    for log in logs:
        print(f"  {log}")
    
    print(f"\n✅ Извлеченные constraints:")
    print(f"  - max_events: {input_data.constraints.max_events}")
    print(f"  - start_time: {input_data.constraints.start_time}")
    print(f"  - end_time: {input_data.constraints.end_time}")
    
    # Проверка
    success = True
    
    from datetime import time
    expected_start = time(12, 0)
    expected_end = time(15, 0)
    
    if input_data.constraints.start_time != expected_start:
        print(f"\n⚠️ ПРЕДУПРЕЖДЕНИЕ: start_time не соответствует (получено: {input_data.constraints.start_time}, ожидалось: {expected_start})")
        success = False
    
    if input_data.constraints.end_time != expected_end:
        print(f"\n⚠️ ПРЕДУПРЕЖДЕНИЕ: end_time не соответствует (получено: {input_data.constraints.end_time}, ожидалось: {expected_end})")
        success = False
    
    if success:
        print("\n✅ ТЕСТ ПРОЙДЕН!")
    else:
        print("\n❌ ТЕСТ НЕ ПРОЙДЕН!")
    
    return success


def main():
    """Запуск всех тестов."""
    print("\n" + "🚀"*40)
    print("ЗАПУСК ТЕСТОВ ИСПРАВЛЕНИЙ")
    print("🚀"*40)
    
    try:
        test1_result = test_max_events_constraint()
    except Exception as e:
        print(f"\n❌ ТЕСТ 1 ЗАВЕРШИЛСЯ С ОШИБКОЙ: {e}")
        import traceback
        traceback.print_exc()
        test1_result = False
    
    try:
        test2_result = test_time_constraint()
    except Exception as e:
        print(f"\n❌ ТЕСТ 2 ЗАВЕРШИЛСЯ С ОШИБКОЙ: {e}")
        import traceback
        traceback.print_exc()
        test2_result = False
    
    print("\n" + "="*80)
    print("ИТОГИ ТЕСТОВ")
    print("="*80)
    print(f"Тест 1 (max_events): {'✅ ПРОЙДЕН' if test1_result else '❌ НЕ ПРОЙДЕН'}")
    print(f"Тест 2 (time): {'✅ ПРОЙДЕН' if test2_result else '❌ НЕ ПРОЙДЕН'}")
    
    if test1_result and test2_result:
        print("\n🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ!")
    else:
        print("\n⚠️ НЕКОТОРЫЕ ТЕСТЫ НЕ ПРОШЛИ. ТРЕБУЕТСЯ ДОРАБОТКА.")


if __name__ == "__main__":
    main()
