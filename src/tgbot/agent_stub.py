"""
Интеграция агентской системы Journey Agent с Telegram ботом.
"""
from typing import Dict, Any, Optional

from src.main_pipeline import main_pipeline
from src.vdb.rag.query_parser import extract_city_and_date
from src.utils.journey_llm import JourneyLLM


def process_route_request(prompt: str, username: str, conversation_history: list = None) -> Dict[str, Any]:
    """
    Обработка запроса на создание маршрута через Journey Agent систему.
    
    Args:
        prompt: Промпт от пользователя
        username: Имя пользователя (используется как user_id для фильтрации событий)
        conversation_history: История диалога (опционально, пока не используется)
    
    Returns:
        Словарь с результатом обработки
    """
    try:
        # Извлекаем город и дату из запроса
        llm = JourneyLLM()
        city, date = extract_city_and_date(prompt, llm=llm.llm)
        
        # Логирование для отладки
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Извлечено из запроса '{prompt}': city={city}, date={date}")
        
        # Валидация: проверяем, что город и дата указаны
        if city is None or date is None:
            missing = []
            if city is None:
                missing.append("город")
            if date is None:
                missing.append("дату")
            
            missing_str = " и ".join(missing)
            return {
                "response": (
                    f"Пожалуйста, укажи {missing_str} для поиска мероприятий. "
                    f"Например: 'Москва, 15 января' или 'Санкт-Петербург, выходные'"
                ),
                "status": "validation_error"
            }
        
        # Передаем city и date в main_pipeline
        response = main_pipeline(prompt, city=city, date=date)

        return {
            "response": response,
            "status": "success"
        }
    
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"❌ Ошибка при обработке запроса: {e}")
        print(error_trace)
        
        # Формируем понятное сообщение об ошибке для пользователя
        error_msg = str(e)
        
        # Если это ошибка валидации Pydantic, делаем более понятное сообщение
        if "validation error" in error_msg.lower() or "ValidationError" in error_msg:
            error_msg = (
                "Не удалось создать план из-за неполных данных. "
                "Попробуй переформулировать запрос или указать больше деталей."
            )
        elif len(error_msg) > 200:
            # Обрезаем слишком длинные сообщения
            error_msg = error_msg[:200] + "..."
        
        return {
            "response": f"Произошла ошибка при обработке вашего запроса: {error_msg}",
            "status": "error"
        }
