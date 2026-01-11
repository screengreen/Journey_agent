"""Парсер города и даты из запроса пользователя."""

from typing import Optional, Tuple
from datetime import datetime, timedelta
import re

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate

# Список основных российских городов с вариантами падежей
RUSSIAN_CITIES = {
    # Москва - все падежи
    "москва": "Москва",
    "москвы": "Москва",
    "москве": "Москва",
    "москву": "Москва",
    "москвой": "Москва",
    "мск": "Москва",
    # Санкт-Петербург
    "санкт-петербург": "Санкт-Петербург",
    "санкт-петербурга": "Санкт-Петербург",
    "санкт-петербурге": "Санкт-Петербург",
    "санкт-петербургу": "Санкт-Петербург",
    "санкт-петербургом": "Санкт-Петербург",
    "спб": "Санкт-Петербург",
    "питер": "Санкт-Петербург",
    "питера": "Санкт-Петербург",
    "питере": "Санкт-Петербург",
    "питеру": "Санкт-Петербург",
    # Другие города
    "казань": "Казань",
    "казани": "Казань",
    "казанью": "Казань",
    "нижний новгород": "Нижний Новгород",
    "нижнего новгорода": "Нижний Новгород",
    "нижнем новгороде": "Нижний Новгород",
    "нн": "Нижний Новгород",
    "екатеринбург": "Екатеринбург",
    "екатеринбурга": "Екатеринбург",
    "екатеринбурге": "Екатеринбург",
    "самара": "Самара",
    "самары": "Самара",
    "самаре": "Самара",
    "самару": "Самара",
    "омск": "Омск",
    "омска": "Омск",
    "омске": "Омск",
    "ростов-на-дону": "Ростов-на-Дону",
    "ростове-на-дону": "Ростов-на-Дону",
    "ростов": "Ростов-на-Дону",
    "ростове": "Ростов-на-Дону",
    "уфа": "Уфа",
    "уфы": "Уфа",
    "уфе": "Уфа",
    "красноярск": "Красноярск",
    "красноярска": "Красноярск",
    "красноярске": "Красноярск",
    "воронеж": "Воронеж",
    "воронежа": "Воронеж",
    "воронеже": "Воронеж",
    "пермь": "Пермь",
    "перми": "Пермь",
    "волгоград": "Волгоград",
    "волгограда": "Волгоград",
    "волгограде": "Волгоград",
    "краснодар": "Краснодар",
    "краснодара": "Краснодар",
    "краснодаре": "Краснодар",
    "саратов": "Саратов",
    "саратова": "Саратов",
    "саратове": "Саратов",
    "тюмень": "Тюмень",
    "тюмени": "Тюмень",
    "тольятти": "Тольятти",
    "ижевск": "Ижевск",
    "ижевска": "Ижевск",
    "ижевске": "Ижевск",
    "барнаул": "Барнаул",
    "барнаула": "Барнаул",
    "барнауле": "Барнаул",
    "ульяновск": "Ульяновск",
    "ульяновска": "Ульяновск",
    "ульяновске": "Ульяновск",
    "иркутск": "Иркутск",
    "иркутска": "Иркутск",
    "иркутске": "Иркутск",
    "хабаровск": "Хабаровск",
    "хабаровска": "Хабаровск",
    "хабаровске": "Хабаровск",
    "ярославль": "Ярославль",
    "ярославля": "Ярославль",
    "ярославле": "Ярославль",
    "владивосток": "Владивосток",
    "владивостока": "Владивосток",
    "владивостоке": "Владивосток",
    "новосибирск": "Новосибирск",
    "новосибирска": "Новосибирск",
    "новосибирске": "Новосибирск",
    "челябинск": "Челябинск",
    "челябинска": "Челябинск",
    "челябинске": "Челябинск",
}

# Промпт для извлечения города и даты
CITY_DATE_EXTRACTION_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """Ты эксперт по извлечению информации из текста.

Твоя задача - извлечь город и дату из запроса пользователя.

Правила для города:
- Извлекай только российские города
- Если город не указан, верни "null"
- Приводи название к стандартной форме (например: "спб" -> "Санкт-Петербург", "мск" -> "Москва", "питер" -> "Санкт-Петербург")
- Распознавай города в любых падежах (например: "в Москве" -> "Москва", "в Санкт-Петербурге" -> "Санкт-Петербург", "в Казани" -> "Казань")
- Верни ТОЛЬКО название города в именительном падеже или "null" (без кавычек, без пояснений)

Правила для даты:
- Извлекай дату в любом формате: "DD.MM.YYYY", "DD-MM-YYYY", "завтра", "послезавтра", "выходные", "15 января", "15 января 2025", "январь 2025", "сегодня"
- Если дата не указана, верни "null"
- Для относительных дат ("завтра", "послезавтра", "выходные", "выходной") верни их как есть
- Для конкретных дат типа "15 января" верни в формате "DD.MM.YYYY" (если год не указан, используй текущий год)
- Верни ТОЛЬКО дату или "null" (без кавычек, без пояснений)

ВАЖНО: Верни ответ ТОЛЬКО в формате JSON, без дополнительного текста:
{
  "city": "название города или null",
  "date": "дата или null"
}

Примеры:
- "Что интересного в Москве на выходных?" -> {"city": "Москва", "date": "выходные"}
- "Покажи концерты в спб 15 января" -> {"city": "Санкт-Петербург", "date": "15.01.2025"}
- "Хочу посетить музей" -> {"city": "null", "date": "null"}
- "Куда сходить в Казани завтра?" -> {"city": "Казань", "date": "завтра"}
- "Хочу провести выходные в центре города Москва, выходные" -> {"city": "Москва", "date": "выходные"}
- "Хочу провести в центре города Москва 15 января" -> {"city": "Москва", "date": "15.01.2025"}"""),
    ("human", """Запрос пользователя: {user_query}

Извлеки город и дату в формате JSON (только JSON, без дополнительного текста):"""),
])


def _normalize_city(city: str) -> Optional[str]:
    """Нормализует название города."""
    if not city or city.lower() in ("null", "none", "не указан", ""):
        return None
    
    city_lower = city.lower().strip()
    return RUSSIAN_CITIES.get(city_lower, city.strip())


def _parse_date_relative(date_str: str) -> Optional[str]:
    """Парсит относительные даты (завтра, послезавтра, выходные)."""
    date_lower = date_str.lower().strip()
    
    if date_lower in ("завтра", "tomorrow"):
        tomorrow = datetime.now() + timedelta(days=1)
        return tomorrow.strftime("%d.%m.%Y")
    elif date_lower in ("послезавтра", "day after tomorrow"):
        day_after = datetime.now() + timedelta(days=2)
        return day_after.strftime("%d.%m.%Y")
    elif date_lower in ("сегодня", "today"):
        today = datetime.now()
        return today.strftime("%d.%m.%Y")
    elif "выходн" in date_lower:
        # Для выходных возвращаем как есть, фильтрация будет по диапазону
        return "выходные"
    
    return None


def _parse_russian_date(date_str: str) -> Optional[str]:
    """Парсит дату в формате '15 января' или '15 января 2025'."""
    date_lower = date_str.lower().strip()
    
    # Паттерн для дат типа "15 января" или "15 января 2025"
    # Улучшенный паттерн: ищем дату в любом месте строки
    pattern = r'(\d{1,2})\s+(январ[ья]|феврал[ья]|март[а]?|апрел[ья]|ма[йя]|июн[ья]|июл[ья]|август[а]?|сентябр[ья]|октябр[ья]|ноябр[ья]|декабр[ья])(?:\s+(\d{4}))?'
    match = re.search(pattern, date_lower)
    
    if match:
        day = int(match.group(1))
        month_name = match.group(2)
        year = int(match.group(3)) if match.group(3) else None
        
        # Преобразуем название месяца в номер
        months = {
            "январ": 1, "феврал": 2, "март": 3, "апрел": 4,
            "май": 5, "ма": 5, "июн": 6, "июл": 7,
            "август": 8, "сентябр": 9, "октябр": 10,
            "ноябр": 11, "декабр": 12
        }
        
        month_num = None
        for month_key, month_val in months.items():
            if month_name.startswith(month_key):
                month_num = month_val
                break
        
        if month_num:
            # Если год не указан, определяем его умно
            if year is None:
                now = datetime.now()
                current_year = now.year
                current_month = now.month
                
                # Если указанный месяц уже прошел в текущем году, используем текущий год
                # Иначе используем текущий год (для будущих дат)
                if month_num < current_month or (month_num == current_month and day < now.day):
                    # Месяц уже прошел, но если это декабрь и сейчас январь, то это прошлый год
                    if month_num == 12 and current_month == 1:
                        year = current_year - 1
                    else:
                        year = current_year
                else:
                    year = current_year
            
            try:
                parsed = datetime(year, month_num, day)
                return parsed.strftime("%d.%m.%Y")
            except ValueError:
                return None
    
    return None


def _normalize_date(date: str) -> Optional[str]:
    """Нормализует дату к единому формату."""
    if not date or date.lower() in ("null", "none", "не указана", ""):
        return None
    
    date = date.strip()
    
    # Проверяем относительные даты
    relative = _parse_date_relative(date)
    if relative:
        return relative
    
    # Пытаемся распарсить русские даты (15 января)
    russian_date = _parse_russian_date(date)
    if russian_date:
        return russian_date
    
    # Пытаемся распарсить различные форматы
    formats = [
        "%d.%m.%Y",
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%Y-%m-%d",
        "%d.%m.%y",
        "%d-%m-%y",
    ]
    
    for fmt in formats:
        try:
            parsed = datetime.strptime(date, fmt)
            return parsed.strftime("%d.%m.%Y")
        except ValueError:
            continue
    
    # Если не удалось распарсить, возвращаем как есть (может быть "15 января" и т.д.)
    return date


def extract_city_and_date(
    query: str, 
    llm: Optional[BaseChatModel] = None
) -> Tuple[Optional[str], Optional[str]]:
    """
    Извлекает город и дату из запроса пользователя.
    
    Args:
        query: Запрос пользователя
        llm: LLM модель для извлечения (опционально, если None - используется regex)
    
    Returns:
        Кортеж (city, date) или (None, None) если не найдено
    """
    if not query or not query.strip():
        return None, None
    
    # Сначала пробуем regex для быстрого извлечения
    city, date = _extract_with_regex(query)
    
    # Если LLM доступен и что-то не найдено, используем LLM
    if llm and (city is None or date is None):
        llm_city, llm_date = _extract_with_llm(query, llm)
        city = city or llm_city
        date = date or llm_date
    
    # Дополнительная проверка: если дата все еще не найдена, но в тексте явно есть указания
    if date is None:
        query_lower = query.lower()
        # Проверяем явные упоминания дат
        if re.search(r'\bвыходн[ыеой]\b', query_lower):
            date = "выходные"
        elif re.search(r'\bзавтра\b', query_lower):
            date = "завтра"
        elif re.search(r'\bпослезавтра\b', query_lower):
            date = "послезавтра"
        elif re.search(r'\bсегодня\b', query_lower):
            date = "сегодня"
        elif re.search(r'\b\d{1,2}\s+(январ[ья]|феврал[ья]|март[а]?|апрел[ья]|ма[йя]|июн[ья]|июл[ья]|август[а]?|сентябр[ья]|октябр[ья]|ноябр[ья]|декабр[ья])\b', query_lower):
            # Если есть дата типа "15 января", но не распарсилась, пробуем еще раз
            date = _parse_russian_date(query)
    
    # Нормализуем результаты
    city = _normalize_city(city) if city else None
    date = _normalize_date(date) if date else None
    
    # Для отладки
    import logging
    logger = logging.getLogger(__name__)
    if city is None or date is None:
        logger.warning(f"Не удалось извлечь полную информацию из запроса '{query}': city={city}, date={date}")
    else:
        logger.info(f"Извлечено из запроса '{query}': city={city}, date={date}")
    
    return city, date


def _extract_with_regex(query: str) -> Tuple[Optional[str], Optional[str]]:
    """Извлечение города и даты с помощью регулярных выражений."""
    city = None
    date = None
    
    query_lower = query.lower()
    
    # Поиск города по списку
    for city_key, city_value in RUSSIAN_CITIES.items():
        # Ищем город в тексте (как отдельное слово)
        pattern = r'\b' + re.escape(city_key) + r'\b'
        if re.search(pattern, query_lower):
            city = city_value
            break
    
    # Поиск даты в различных форматах
    # Сначала ищем относительные даты (выходные, завтра и т.д.)
    # Улучшенный паттерн для "выходные" - ищем как отдельное слово
    if re.search(r'\bвыходн[ыеой]\b', query_lower):
        date = "выходные"
    elif re.search(r'\bзавтра\b', query_lower):
        date = "завтра"
    elif re.search(r'\bпослезавтра\b', query_lower):
        date = "послезавтра"
    elif re.search(r'\bсегодня\b', query_lower):
        date = "сегодня"
    else:
        # Ищем даты типа "15 января" или "15 января 2025"
        month_pattern = r'\b(\d{1,2})\s+(январ[ья]|феврал[ья]|март[а]?|апрел[ья]|ма[йя]|июн[ья]|июл[ья]|август[а]?|сентябр[ья]|октябр[ья]|ноябр[ья]|декабр[ья])(?:\s+(\d{4}))?\b'
        match = re.search(month_pattern, query_lower)
        if match:
            day = int(match.group(1))
            month_name = match.group(2)
            year_str = match.group(3)
            
            # Преобразуем название месяца в номер
            months = {
                "январ": 1, "феврал": 2, "март": 3, "апрел": 4,
                "май": 5, "ма": 5, "июн": 6, "июл": 7,
                "август": 8, "сентябр": 9, "октябр": 10,
                "ноябр": 11, "декабр": 12
            }
            
            month_num = None
            for month_key, month_val in months.items():
                if month_name.startswith(month_key):
                    month_num = month_val
                    break
            
            if month_num:
                # Определяем год умно, если не указан
                if year_str:
                    year = int(year_str)
                else:
                    now = datetime.now()
                    current_year = now.year
                    current_month = now.month
                    
                    # Если указанный месяц уже прошел в текущем году, используем текущий год
                    # Если это декабрь и сейчас январь, то это прошлый год
                    if month_num == 12 and current_month == 1:
                        year = current_year - 1
                    elif month_num < current_month or (month_num == current_month and day < now.day):
                        year = current_year
                    else:
                        year = current_year
                
                date = f"{day:02d}.{month_num:02d}.{year}"
        else:
            # Ищем даты в формате DD.MM.YYYY, DD-MM-YYYY
            numeric_pattern = r'\b(\d{1,2})[./-](\d{1,2})[./-](\d{2,4})\b'
            match = re.search(numeric_pattern, query_lower)
            if match:
                date = match.group(0)
    
    return city, date


def _extract_with_llm(query: str, llm: BaseChatModel) -> Tuple[Optional[str], Optional[str]]:
    """Извлечение города и даты с помощью LLM."""
    try:
        prompt = CITY_DATE_EXTRACTION_PROMPT.format_messages(user_query=query)
        response = llm.invoke(prompt)
        content = response.content.strip()
        
        # Пытаемся извлечь JSON из ответа
        import json
        
        # Убираем markdown код блоки если есть
        content = content.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        
        # Пытаемся найти JSON объект в тексте (более гибкий поиск)
        # Ищем { ... } с ключами city и date
        json_match = re.search(r'\{[^{}]*"city"[^{}]*"date"[^{}]*\}', content, re.DOTALL)
        if not json_match:
            # Пробуем более широкий поиск
            json_match = re.search(r'\{.*?"city".*?"date".*?\}', content, re.DOTALL)
        
        if json_match:
            content = json_match.group(0)
        
        # Пытаемся распарсить JSON
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            # Если не удалось распарсить, пробуем найти значения напрямую
            city_match = re.search(r'"city"\s*:\s*"([^"]*)"', content)
            date_match = re.search(r'"date"\s*:\s*"([^"]*)"', content)
            
            city = city_match.group(1) if city_match else None
            date = date_match.group(1) if date_match else None
            
            # Обрабатываем значения "null" как None
            if city and city.lower() in ("null", "none", "не указан", ""):
                city = None
            if date and date.lower() in ("null", "none", "не указана", ""):
                date = None
            
            return city, date
        
        # Если JSON распарсился успешно
        city = data.get("city")
        date = data.get("date")
        
        # Обрабатываем значения "null" как None
        if city and city.lower() in ("null", "none", "не указан", ""):
            city = None
        if date and date.lower() in ("null", "none", "не указана", ""):
            date = None
        
        return city, date
    except Exception as e:
        # В случае ошибки возвращаем None
        import warnings
        response_content = response.content[:200] if 'response' in locals() else 'N/A'
        warnings.warn(f"Ошибка при извлечении города и даты через LLM: {e}. Ответ: {response_content}")
        return None, None

