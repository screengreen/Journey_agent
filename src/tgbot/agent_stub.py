"""
Интеграция агентской системы Journey Agent с Telegram ботом.
"""
from typing import Dict, Any

from src.main_pipeline import main_pipeline


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
        response = main_pipeline(prompt)

        return {
            "response": response,
            "status": "success"
        }
    
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"❌ Ошибка при обработке запроса: {e}")
        print(error_trace)
        
        return {
            "response": f"Произошла ошибка при обработке вашего запроса: {str(e)}",
            "status": "error"
        }
