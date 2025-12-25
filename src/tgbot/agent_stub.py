"""
Интеграция агентской системы Journey Agent с Telegram ботом через VDB API.
"""
import os
from typing import Dict, Any, Optional, List
import requests
from dotenv import load_dotenv

load_dotenv()

# URL VDB API сервиса
# В Docker Compose используйте: VDB_API_URL=http://vdb:8001
# Для локальной разработки: VDB_API_URL=http://localhost:8001 (по умолчанию)
VDB_API_URL = os.getenv("VDB_API_URL", "http://localhost:8001")


def format_event_card(event: Dict[str, Any], index: int) -> str:
    """
    Форматирует одно событие в красивую карточку для Telegram.
    
    Args:
        event: Словарь с данными события
        index: Номер события в списке
    
    Returns:
        Отформатированная строка для отправки в Telegram
    """
    lines = [f"🎯 <b>{index + 1}. {event.get('title', 'Без названия')}</b>"]
    
    if event.get('description'):
        # Обрезаем описание если слишком длинное
        description = event['description']
        if len(description) > 200:
            description = description[:197] + "..."
        lines.append(f"\n📝 {description}")
    
    if event.get('location'):
        lines.append(f"\n📍 {event['location']}")
    
    if event.get('date'):
        lines.append(f"\n📅 {event['date']}")
    
    if event.get('tags'):
        tags_str = ", ".join(event['tags'][:5])  # Берем первые 5 тегов
        lines.append(f"\n🏷️ {tags_str}")
    
    if event.get('url'):
        lines.append(f"\n🔗 <a href=\"{event['url']}\">Подробнее</a>")
    
    return "\n".join(lines)


def format_events_response(events: List[Dict[str, Any]], constraints: Optional[Dict[str, Any]] = None, max_length: int = 4000) -> str:
    """
    Форматирует список событий в красивое сообщение для Telegram.
    
    Args:
        events: Список событий
        constraints: Ограничения для планирования (опционально)
        max_length: Максимальная длина сообщения (по умолчанию 4000 для Telegram)
    
    Returns:
        Отформатированная строка для отправки в Telegram
    """
    if not events:
        return "❌ К сожалению, по вашему запросу ничего не найдено.\n\nПопробуйте изменить условия поиска."
    
    lines = [f"✅ <b>Найдено событий: {len(events)}</b>\n"]
    
    # Форматируем каждое событие
    for i, event in enumerate(events):
        event_card = format_event_card(event, i)
        lines.append(event_card)
        if i < len(events) - 1:  # Добавляем разделитель между событиями
            lines.append("\n" + "─" * 40 + "\n")
    
    # Добавляем информацию об ограничениях, если они есть
    if constraints:
        constraint_lines = []
        if constraints.get('start_time'):
            constraint_lines.append(f"⏰ Начало: {constraints['start_time']}")
        if constraints.get('end_time'):
            constraint_lines.append(f"⏰ Окончание: {constraints['end_time']}")
        if constraints.get('max_total_time_minutes'):
            constraint_lines.append(f"⏱️ Макс. время: {constraints['max_total_time_minutes']} мин")
        if constraints.get('preferred_transport'):
            constraint_lines.append(f"🚌 Транспорт: {constraints['preferred_transport']}")
        if constraints.get('budget'):
            constraint_lines.append(f"💰 Бюджет: {constraints['budget']} руб")
        
        if constraint_lines:
            lines.append("\n\n<b>📋 Условия:</b>")
            lines.extend(constraint_lines)
    
    result = "\n".join(lines)
    
    # Если сообщение слишком длинное, обрезаем и добавляем информацию об обрезке
    if len(result) > max_length:
        # Пытаемся обрезать по событиям
        truncated_events_count = 0
        for i in range(len(events), 0, -1):
            temp_lines = [f"✅ <b>Найдено событий: {len(events)}</b>\n"]
            for j in range(i):
                event_card = format_event_card(events[j], j)
                temp_lines.append(event_card)
                if j < i - 1:
                    temp_lines.append("\n" + "─" * 40 + "\n")
            
            temp_result = "\n".join(temp_lines)
            if len(temp_result) <= max_length - 100:  # Оставляем место для сообщения об обрезке
                truncated_events_count = i
                result = temp_result
                result += f"\n\n⚠️ <i>Показано только {i} из {len(events)} событий. Попробуйте уточнить запрос.</i>"
                break
        else:
            # Если даже одно событие не помещается, показываем только заголовок
            result = f"✅ <b>Найдено событий: {len(events)}</b>\n\n"
            result += "⚠️ <i>События слишком длинные для отображения. Попробуйте уточнить запрос.</i>"
    
    return result


def process_route_request(prompt: str, username: str, conversation_history: list = None) -> Dict[str, Any]:
    """
    Обработка запроса на создание маршрута через VDB API сервис.
    
    Args:
        prompt: Промпт от пользователя
        username: Имя пользователя (используется как owner для фильтрации событий)
        conversation_history: История диалога (опционально, пока не используется)
    
    Returns:
        Словарь с результатом обработки
    """
    try:
        # Формируем запрос к VDB API
        api_url = f"{VDB_API_URL}/search"
        payload = {
            "query": prompt,
            "owner": username,
            "return_logs": False
        }
        
        # Отправляем запрос
        response = requests.post(api_url, json=payload, timeout=60)
        
        if response.status_code != 200:
            error_msg = f"Ошибка API (код {response.status_code})"
            try:
                error_data = response.json()
                error_msg = error_data.get("detail", error_msg)
            except:
                error_msg = response.text or error_msg
            
            return {
                "response": f"❌ Произошла ошибка при поиске событий: {error_msg}",
                "status": "error"
            }
        
        # Парсим ответ
        data = response.json()
        events = data.get("events", [])
        constraints = data.get("constraints", {})
        
        # Форматируем результат для Telegram
        formatted_response = format_events_response(events, constraints)
        
        return {
            "response": formatted_response,
            "status": "success",
            "events_count": len(events)
        }
    
    except requests.exceptions.ConnectionError:
        return {
            "response": "❌ Не удалось подключиться к сервису поиска событий. Попробуйте позже.",
            "status": "error"
        }
    
    except requests.exceptions.Timeout:
        return {
            "response": "⏱️ Превышено время ожидания ответа от сервиса. Попробуйте упростить запрос.",
            "status": "error"
        }
    
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"❌ Ошибка при обработке запроса: {e}")
        print(error_trace)
        
        return {
            "response": f"❌ Произошла ошибка при обработке вашего запроса: {str(e)}",
            "status": "error"
        }

