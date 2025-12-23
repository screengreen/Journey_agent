"""Retriever для поиска событий в Weaviate с фильтрацией по тегам."""

from typing import List, Optional
from urllib.parse import urlparse
from datetime import datetime, timedelta
import re

try:
    import weaviate
    import weaviate.classes as wvc
except ImportError:
    weaviate = None
    wvc = None

from src.vdb.config import WEAVIATE_URL, COLLECTION_NAME, MAX_EVENTS
from src.models.event import Event


class EventRetriever:
    """Retriever для поиска событий в Weaviate."""

    def __init__(self, weaviate_url: str = WEAVIATE_URL, collection_name: str = COLLECTION_NAME):
        """
        Инициализация retriever.

        Args:
            weaviate_url: URL сервера Weaviate
            collection_name: Имя коллекции с событиями
        """
        self.weaviate_url = weaviate_url
        self.collection_name = collection_name
        self._client: Optional[weaviate.WeaviateClient] = None

    def _get_client(self) -> weaviate.WeaviateClient:
        """Получить или создать клиент Weaviate."""
        if self._client is None:
            parsed = urlparse(self.weaviate_url)
            http_port = parsed.port or (443 if parsed.scheme == "https" else 8080)
            http_secure = parsed.scheme == "https"
            hostname = parsed.hostname or "localhost"

            if hostname in ("localhost", "127.0.0.1") and http_port == 8080 and not http_secure:
                self._client = weaviate.connect_to_local()
            else:
                self._client = weaviate.connect_to_custom(
                    http_host=hostname,
                    http_port=http_port,
                    http_secure=http_secure,
                    grpc_host=hostname,
                    grpc_port=50051,
                    grpc_secure=http_secure,
                )
        return self._client

    def retrieve(
        self,
        query: str,
        limit: int = MAX_EVENTS,
        owner: Optional[str] = None,
        city: Optional[str] = None,
        date: Optional[str] = None,
    ) -> List[Event]:
        """
        Поиск событий по запросу с фильтрацией по тегам, городу и дате.
        Сначала возвращает события пользователя (с тегом owner в tags), затем общие (с тегом 'all').

        Args:
            query: Поисковый запрос
            limit: Максимальное количество результатов (по умолчанию 15)
            owner: Username пользователя для приоритетной фильтрации событий
            city: Город для фильтрации (например, "Москва", "СПб")
            date: Дата/время для фильтрации

        Returns:
            Список найденных событий: сначала события пользователя, затем общие (максимум limit)
        """
        client = self._get_client()

        try:
            collection = client.collections.get(self.collection_name)
        except Exception:
            # Если коллекция не существует, возвращаем пустой список
            return []

        # Вычисляем распределение лимитов
        # Примерно 50% событий пользователя, остальные общие
        user_limit = max(1, limit // 2) if owner else 0
        common_limit = limit - user_limit

        user_events: List[tuple[Event, float]] = []  # (event, distance)
        common_events: List[tuple[Event, float]] = []  # (event, distance)

        # Вспомогательные функции для нормализации и парсинга дат
        def parse_date_string(date_str: str) -> Optional[datetime]:
            """
            Парсит строку с датой в datetime объект.
            Поддерживает различные форматы: "2024-12-25", "25.12.2024", "2024-12-25 10:00" и т.д.
            """
            if not date_str:
                return None
            
            date_str = date_str.strip()
            
            # Пробуем различные форматы
            formats = [
                "%Y-%m-%d %H:%M",
                "%Y-%m-%d",
                "%d.%m.%Y %H:%M",
                "%d.%m.%Y",
                "%d/%m/%Y %H:%M",
                "%d/%m/%Y",
            ]
            
            for fmt in formats:
                try:
                    return datetime.strptime(date_str, fmt)
                except ValueError:
                    continue
            
            # Пробуем ISO формат
            try:
                return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                pass
            
            return None

        def normalize_relative_date(date_filter: str) -> Optional[datetime]:
            """
            Обрабатывает относительные даты: "сегодня", "завтра", "послезавтра", "через неделю".
            Возвращает datetime объект или None.
            """
            date_filter_lower = date_filter.lower().strip()
            now = datetime.now()
            
            relative_dates = {
                "сегодня": now,
                "завтра": now + timedelta(days=1),
                "послезавтра": now + timedelta(days=2),
                "через неделю": now + timedelta(days=7),
                "через 2 недели": now + timedelta(days=14),
                "через месяц": now + timedelta(days=30),
            }
            
            for key, dt in relative_dates.items():
                if key in date_filter_lower:
                    # Проверяем время, если указано
                    time_match = re.search(r'(\d{1,2}):(\d{2})', date_filter_lower)
                    if time_match:
                        hour = int(time_match.group(1))
                        minute = int(time_match.group(2))
                        dt = dt.replace(hour=hour, minute=minute, second=0, microsecond=0)
                    return dt
            
            return None

        def normalize_date_from_filter(date_filter: str) -> Optional[datetime]:
            """
            Нормализует дату из фильтра (извлеченную LLM) в datetime объект.
            Обрабатывает относительные даты, различные форматы и т.д.
            """
            if not date_filter:
                return None
            
            # Сначала пробуем относительные даты
            relative_date = normalize_relative_date(date_filter)
            if relative_date:
                return relative_date
            
            # Пробуем парсить как обычную дату
            parsed = parse_date_string(date_filter)
            if parsed:
                return parsed
            
            # Пробуем извлечь дату из русского текста (например, "25 декабря 2024")
            months_ru = {
                "января": 1, "февраля": 2, "марта": 3, "апреля": 4,
                "мая": 5, "июня": 6, "июля": 7, "августа": 8,
                "сентября": 9, "октября": 10, "ноября": 11, "декабря": 12,
            }
            
            date_filter_lower = date_filter.lower()
            for month_name, month_num in months_ru.items():
                if month_name in date_filter_lower:
                    # Ищем число и год
                    day_match = re.search(r'(\d{1,2})\s+' + month_name, date_filter_lower)
                    year_match = re.search(r'(\d{4})', date_filter)
                    
                    if day_match:
                        day = int(day_match.group(1))
                        year = int(year_match.group(1)) if year_match else datetime.now().year
                        
                        # Пробуем найти время
                        time_match = re.search(r'(\d{1,2}):(\d{2})', date_filter)
                        hour = int(time_match.group(1)) if time_match else 0
                        minute = int(time_match.group(2)) if time_match else 0
                        
                        try:
                            return datetime(year, month_num, day, hour, minute)
                        except ValueError:
                            continue
            
            return None

        # Вспомогательная функция для программной фильтрации по городу и дате
        def matches_city_and_date(event: Event, city_filter: Optional[str], date_filter: Optional[str]) -> bool:
            """Проверяет, соответствует ли событие фильтрам по городу и дате."""
            if city_filter:
                # Ищем город в location (регистронезависимый поиск)
                location = (event.location or "").lower().strip()
                city_lower = city_filter.lower().strip()
                
                # Нормализуем варианты названий городов
                city_variants = {
                    "москва": ["москва", "мск", "moscow"],
                    "санкт-петербург": ["санкт-петербург", "спб", "питер", "петербург", "spb", "saint petersburg", "st. petersburg"],
                    "екатеринбург": ["екатеринбург", "екб", "yekaterinburg"],
                    "новосибирск": ["новосибирск", "нск", "novosibirsk"],
                    "казань": ["казань", "kazan"],
                    "нижний новгород": ["нижний новгород", "нижний", "nn", "nizhny novgorod"],
                }
                
                # Собираем все варианты для поиска
                search_variants = [city_lower]
                for main_city, variants in city_variants.items():
                    if city_lower == main_city or city_lower in variants:
                        search_variants.extend(variants + [main_city])
                        break
                
                # Проверяем, есть ли хотя бы один вариант в location
                found = any(var in location for var in search_variants)
                
                if not found:
                    return False

            if date_filter:
                # Улучшенная фильтрация по дате
                event_date_str = event.date or ""
                if not event_date_str:
                    return False  # Если у события нет даты, пропускаем
                
                # Нормализуем дату из фильтра
                filter_date = normalize_date_from_filter(date_filter)
                if not filter_date:
                    # Если не удалось распарсить, используем простой поиск подстроки как fallback
                    # Это важно для случаев, когда LLM вернул что-то нестандартное
                    if date_filter.lower() not in event_date_str.lower():
                        return False
                    return True
                
                # Парсим дату события
                event_date = parse_date_string(event_date_str)
                if not event_date:
                    # Если не удалось распарсить дату события, используем поиск подстроки
                    # Это fallback для событий с нестандартным форматом даты
                    if date_filter.lower() not in event_date_str.lower():
                        return False
                    return True
                
                # Сравниваем даты (сравниваем только дату, без времени, для большей гибкости)
                filter_date_only = filter_date.date()
                event_date_only = event_date.date()
                
                # Если даты совпадают, событие подходит
                if filter_date_only == event_date_only:
                    return True
                
                # Если фильтр содержит время, можно проверить более точно,
                # но так как мы уже проверили совпадение дат выше, это не нужно
                # Оставляем этот код для будущих улучшений
                
                # Если не совпало, возвращаем False
                return False

            return True

        # 1. Получаем события пользователя (если owner указан)
        user_existing_keys = set()  # Для избежания дубликатов в пользовательских событиях
        if owner and user_limit > 0:
            # Функция для поиска пользовательских событий с заданным фильтром по дате
            def search_user_events(use_date_filter: bool):
                nonlocal user_existing_keys
                current_date_filter = date if use_date_filter else None
                fetch_multiplier = 20 if (city or current_date_filter) else 10
                fetch_limit = max(user_limit * fetch_multiplier, 100)
                
                try:
                    result = collection.query.near_text(
                        query=query,
                        limit=fetch_limit,
                        return_metadata=wvc.query.MetadataQuery(distance=True),
                    )
                    
                    for obj in result.objects:
                        try:
                            event = Event(**obj.properties)
                            tags = event.tags or []
                            if owner not in tags:
                                continue
                            
                            # Проверяем ключ для избежания дубликатов
                            event_key = (event.title or "", event.date or "", event.location or "")
                            if event_key in user_existing_keys:
                                continue
                            user_existing_keys.add(event_key)
                            
                            # Применяем фильтры по городу и дате программно
                            if matches_city_and_date(event, city, current_date_filter):
                                distance = obj.metadata.distance if obj.metadata and hasattr(obj.metadata, 'distance') else 1.0
                                user_events.append((event, distance))
                                if len(user_events) >= user_limit:
                                    break
                        except Exception as e:
                            import warnings
                            warnings.warn(f"Ошибка при парсинге события пользователя: {e}")
                            continue
                except Exception as e:
                    import warnings
                    warnings.warn(f"Ошибка при поиске событий пользователя: {e}")
            
            # Сначала пробуем с фильтром по дате
            search_user_events(use_date_filter=True)
            
            # Если не нашли достаточно событий и есть фильтр по дате, пробуем без него
            if len(user_events) < user_limit and date:
                search_user_events(use_date_filter=False)
            
            # Сортируем события пользователя по релевантности (distance)
            user_events.sort(key=lambda x: x[1])
            # Оставляем только лучшие результаты
            user_events = user_events[:user_limit]

        # 2. Получаем общие события (с тегом 'all' или owner='all')
        if common_limit > 0:
            # Создаем набор ключей для проверки дубликатов (title + date + location)
            existing_keys = {
                (e[0].title or "", e[0].date or "", e[0].location or "")
                for e in user_events
            }
            
            # Функция для поиска общих событий с заданным фильтром по дате
            def search_common_events(use_date_filter: bool):
                current_date_filter = date if use_date_filter else None
                fetch_multiplier = 20 if (city or current_date_filter) else 10
                fetch_limit = max(common_limit * fetch_multiplier, 100)
                
                try:
                    result = collection.query.near_text(
                        query=query,
                        limit=fetch_limit,
                        return_metadata=wvc.query.MetadataQuery(distance=True),
                    )
                    
                    for obj in result.objects:
                        try:
                            event = Event(**obj.properties)
                            tags = event.tags or []
                            
                            # Пропускаем события пользователя, если owner указан
                            if owner and owner in tags:
                                continue
                            
                            # Пропускаем дубликаты
                            event_key = (event.title or "", event.date or "", event.location or "")
                            if event_key in existing_keys:
                                continue
                            existing_keys.add(event_key)
                            
                            # Определяем, является ли событие общим
                            is_common_event = (owner is None) or ("all" in tags) or (event.owner == "all")
                            if not is_common_event:
                                continue
                            
                            # Применяем фильтры по городу и дате программно
                            if matches_city_and_date(event, city, current_date_filter):
                                distance = obj.metadata.distance if obj.metadata and hasattr(obj.metadata, 'distance') else 1.0
                                common_events.append((event, distance))
                                if len(common_events) >= common_limit:
                                    break
                        except Exception as e:
                            import warnings
                            warnings.warn(f"Ошибка при парсинге общего события: {e}")
                            continue
                except Exception as e:
                    import warnings
                    warnings.warn(f"Ошибка при поиске общих событий: {e}")
            
            # Сначала пробуем с фильтром по дате
            search_common_events(use_date_filter=True)
            
            # Если не нашли достаточно событий и есть фильтр по дате, пробуем без него
            if len(common_events) < common_limit and date:
                search_common_events(use_date_filter=False)
            
            # Сортируем общие события по релевантности (distance)
            common_events.sort(key=lambda x: x[1])
            # Оставляем только лучшие результаты
            common_events = common_events[:common_limit]

        # 3. Объединяем результаты: сначала события пользователя, потом общие
        # Извлекаем только события (без distance) и сортируем их по релевантности внутри каждой группы
        all_events = [e[0] for e in user_events] + [e[0] for e in common_events]

        # Ограничиваем общее количество
        return all_events[:limit]

    def format_events_for_context(self, events: List[Event]) -> str:
        """
        Форматирует события для использования в контексте промпта.

        Args:
            events: Список событий

        Returns:
            Отформатированная строка с событиями
        """
        if not events:
            return "События не найдены."

        formatted = []
        for i, event in enumerate(events, 1):
            event_str = f"{i}. {event.title}"
            if event.description:
                event_str += f"\n   Описание: {event.description}"
            if event.location:
                event_str += f"\n   Местоположение: {event.location}"
            if event.date:
                event_str += f"\n   Дата: {event.date}"
            if event.tags:
                event_str += f"\n   Теги: {', '.join(event.tags)}"
            formatted.append(event_str)

        return "\n\n".join(formatted)

    def close(self):
        """Закрыть соединение с Weaviate."""
        if self._client is not None:
            self._client.close()
            self._client = None

