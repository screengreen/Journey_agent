"""Парсер для извлечения города и даты/времени из запроса пользователя."""

from typing import Optional
from pydantic import BaseModel, Field

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI
try:
    from langchain_mistralai import ChatMistralAI
except ImportError:
    ChatMistralAI = None

from src.vdb.config import OPENAI_API_KEY, OPENAI_MODEL, MISTRAL_API_KEY, MISTRAL_MODEL


class QueryFilters(BaseModel):
    """Фильтры, извлеченные из запроса пользователя."""

    city: Optional[str] = Field(default=None, description="Город из запроса")
    date: Optional[str] = Field(default=None, description="Дата/время из запроса")


QUERY_FILTERS_EXTRACTION_PROMPT = """
Извлеки из текста запроса пользователя город и дату/время, если они указаны.

Верни ТОЛЬКО валидный JSON объект (без пояснений, без markdown), строго с ключами:
- city: название города (например, "Москва", "Санкт-Петербург", "СПб") или null, если город не указан
- date: дата и/или время (например, "2024-12-25", "25 декабря", "завтра", "сегодня вечером", "14:00") или null, если дата не указана

Важно:
- Распознавай различные варианты написания городов (Москва, москва, МСК, Москве, в Москве и т.д.)
- Распознавай относительные даты (сегодня, завтра, послезавтра, через неделю)
- Распознавай конкретные даты (25 декабря, 25.12, 2024-12-25)
- Распознавай время (14:00, вечером, утром, днем)

Текст запроса пользователя:
{user_query}
""".strip()


def parse_query_filters(
    user_query: str, llm: Optional[BaseChatModel] = None
) -> QueryFilters:
    """
    Извлекает город и дату/время из запроса пользователя.

    Args:
        user_query: Запрос пользователя
        llm: Языковая модель (если None, создается автоматически)

    Returns:
        QueryFilters с извлеченными фильтрами
    """
    if llm is None:
        # Используем Mistral, если доступен ключ, иначе OpenAI
        if MISTRAL_API_KEY and ChatMistralAI is not None:
            llm = ChatMistralAI(
                model=MISTRAL_MODEL,
                api_key=MISTRAL_API_KEY,
                temperature=0,
            )
        elif OPENAI_API_KEY:
            llm = ChatOpenAI(model=OPENAI_MODEL, api_key=OPENAI_API_KEY, temperature=0)
        else:
            raise ValueError(
                "Не установлен ни один API ключ. "
                "Установите MISTRAL_API_KEY или OPENAI_API_KEY"
            )

    prompt = QUERY_FILTERS_EXTRACTION_PROMPT.format(user_query=user_query)

    try:
        response = llm.invoke(prompt)
        raw = (response.content or "").strip()

        # Удаляем markdown код блоки, если есть
        raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()

        # Парсим JSON
        import json

        data = json.loads(raw)

        # Валидируем через Pydantic
        if hasattr(QueryFilters, "model_validate"):
            filters = QueryFilters.model_validate(data)
        else:
            filters = QueryFilters.parse_obj(data)

        return filters

    except Exception as e:
        # В случае ошибки возвращаем пустые фильтры
        import warnings

        warnings.warn(f"Ошибка при парсинге фильтров из запроса: {e}")
        return QueryFilters(city=None, date=None)

