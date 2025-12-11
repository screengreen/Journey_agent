"""Заглушка для проверки памяти (проверка похожих вопросов)."""

from typing import Optional


def check_memory(user_query: str, user_tag: Optional[str] = None) -> bool:
    """
    Проверяет, был ли задан похожий вопрос ранее.
    
    Args:
        user_query: Запрос пользователя
        user_tag: Тег пользователя (не используется в заглушке)
        
    Returns:
        False - всегда возвращает False (заглушка)
    """
    # Заглушка: всегда возвращаем False
    return False

