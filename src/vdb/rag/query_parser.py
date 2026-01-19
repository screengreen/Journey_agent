"""Парсер города и даты из запроса пользователя."""

from typing import Optional, Tuple
from datetime import datetime, timedelta
import logging
import json
import re

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)


class ParsedQuery(BaseModel):
    """Результат парсинга запроса пользователя."""
    
    city: Optional[str] = Field(
        None,
        description="Название города в именительном падеже (например: Москва, Санкт-Петербург)"
    )
    date: Optional[str] = Field(
        None,
        description="Дата в формате DD.MM.YYYY или относительная дата (завтра, выходные, сегодня)"
    )
    
    @field_validator('city', mode='before')
    @classmethod
    def normalize_city(cls, v):
        """Нормализует город: null/пустое -> None."""
        if not v or str(v).lower() in ("null", "none", "не указан"):
            return None
        return str(v).strip()
    
    @field_validator('date', mode='before')
    @classmethod
    def normalize_date(cls, v):
        """Нормализует дату: null/пустое -> None."""
        if not v or str(v).lower() in ("null", "none", "не указана"):
            return None
        return str(v).strip()


# Промпт для LLM
EXTRACTION_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """Ты эксперт по извлечению информации из запросов пользователей о событиях и мероприятиях.

Извлеки из запроса:
1. **Город** - название российского города в именительном падеже
   - Примеры: "Москва", "Санкт-Петербург", "Казань"
   - Распознавай сокращения: "спб" → "Санкт-Петербург", "мск" → "Москва", "питер" → "Санкт-Петербург"
   - Распознавай любые падежи: "в Москве" → "Москва", "в Санкт-Петербурге" → "Санкт-Петербург"
   - Если город не указан → null

2. **Дата** - в формате DD.MM.YYYY или относительная
   - Для точных дат: "15 января 2025" → "15.01.2025"
   - Если год не указан, используй 2026 (текущий год)
   - Для относительных дат сохрани как есть: "завтра", "послезавтра", "выходные", "сегодня"
   - Если дата не указана → null

Примеры:
- "Что интересного в Москве на выходных?" → city: "Москва", date: "выходные"
- "Покажи концерты в спб 15 января" → city: "Санкт-Петербург", date: "15.01.2026"
- "Хочу послушать рок в Москве 27 декабря 2024" → city: "Москва", date: "27.12.2024"
- "Куда сходить завтра?" → city: null, date: "завтра"
- "Хочу посетить музей" → city: null, date: null"""),
    ("human", "{user_query}"),
])


def _resolve_relative_date(date_str: str) -> str:
    """Преобразует относительные даты в абсолютные."""
    date_lower = date_str.lower()
    
    if date_lower == "сегодня":
        return datetime.now().strftime("%d.%m.%Y")
    elif date_lower == "завтра":
        return (datetime.now() + timedelta(days=1)).strftime("%d.%m.%Y")
    elif date_lower == "послезавтра":
        return (datetime.now() + timedelta(days=2)).strftime("%d.%m.%Y")
    elif "выходн" in date_lower:
        # Для выходных оставляем как есть - retriever обработает
        return "выходные"
    
    return date_str


def _parse_json_fallback(content: str) -> Optional[ParsedQuery]:
    """Fallback парсинг JSON из ответа LLM."""
    try:
        # Убираем markdown блоки
        content = content.strip()
        content = content.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        
        # Ищем JSON объект
        json_match = re.search(r'\{[^{}]*"city"[^{}]*"date"[^{}]*\}', content, re.DOTALL)
        if json_match:
            content = json_match.group(0)
        
        data = json.loads(content)
        return ParsedQuery(**data)
    except Exception as e:
        logger.warning(f"Не удалось распарсить JSON fallback: {e}")
        return None


def extract_city_and_date(
    query: str, 
    llm: BaseChatModel
) -> Tuple[Optional[str], Optional[str]]:
    """
    Извлекает город и дату из запроса пользователя.
    
    Args:
        query: Запрос пользователя
        llm: LLM модель для извлечения
    
    Returns:
        Кортеж (city, date) или (None, None) если не найдено
    """
    if not query or not query.strip():
        logger.warning("Пустой запрос для парсинга")
        return None, None
    
    result: Optional[ParsedQuery] = None
    
    try:
        # Сначала пробуем structured output
        structured_llm = llm.with_structured_output(ParsedQuery)
        prompt = EXTRACTION_PROMPT.invoke({"user_query": query})
        result = structured_llm.invoke(prompt)
        
    except Exception as e:
        logger.warning(f"⚠️ with_structured_output не сработал: {e}")
        
        # Fallback: получаем сырой ответ и парсим JSON вручную
        try:
            prompt = EXTRACTION_PROMPT.invoke({"user_query": query})
            response = llm.invoke(prompt)
            content = response.content if hasattr(response, 'content') else str(response)
            result = _parse_json_fallback(content)
        except Exception as e2:
            logger.error(f"❌ Fallback парсинг также не удался: {e2}")
            return None, None
    
    # Проверка на None
    if result is None:
        logger.error(f"❌ LLM вернул None при парсинге запроса: '{query}'")
        return None, None
    
    city = result.city
    date = result.date
    
    # Преобразуем относительные даты в абсолютные
    if date:
        date = _resolve_relative_date(date)
    
    # Логируем результат
    if city or date:
        logger.info(f"✅ Извлечено: city='{city}', date='{date}' из запроса: '{query}'")
    else:
        logger.warning(f"⚠️ Не удалось извлечь город и дату из запроса: '{query}'")
    
    return city, date
