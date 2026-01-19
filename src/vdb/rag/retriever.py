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


def _parse_event_date(date_str: Optional[str]) -> Optional[datetime]:
    """Парсит дату события из строки."""
    if not date_str:
        return None
    
    date_str = str(date_str).strip()
    
    # Пробуем различные форматы (важно: порядок имеет значение - сначала более специфичные)
    formats = [
        "%Y-%m-%d %H:%M:%S",  # ISO формат с секундами
        "%Y-%m-%d %H:%M",     # ISO формат без секунд (2024-12-27 15:00)
        "%Y-%m-%d",           # ISO формат только дата
        "%d.%m.%Y %H:%M:%S",  # DD.MM.YYYY с секундами
        "%d.%m.%Y %H:%M",     # DD.MM.YYYY с временем
        "%d.%m.%Y",           # DD.MM.YYYY только дата
        "%d-%m-%Y %H:%M:%S",  # DD-MM-YYYY с секундами
        "%d-%m-%Y %H:%M",     # DD-MM-YYYY с временем
        "%d-%m-%Y",           # DD-MM-YYYY только дата
        "%d/%m/%Y",           # DD/MM/YYYY
        "%d.%m.%y",           # DD.MM.YY
        "%d-%m-%y",           # DD-MM-YY
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    
    return None


def _matches_date_filter(event_date_str: Optional[str], filter_date: str) -> bool:
    """
    Проверяет, соответствует ли дата события фильтру.
    
    Args:
        event_date_str: Дата события в виде строки
        filter_date: Дата фильтра (может быть "DD.MM.YYYY", "завтра", "выходные" и т.д.)
    
    Returns:
        True если дата соответствует фильтру, False иначе
    """
    if not event_date_str or not filter_date:
        return True  # Если дата не указана, пропускаем фильтрацию
    
    filter_date_lower = filter_date.lower().strip()
    
    # Обработка относительных дат
    if filter_date_lower == "выходные":
        # Для выходных проверяем, попадает ли событие на субботу или воскресенье
        event_dt = _parse_event_date(event_date_str)
        if event_dt:
            weekday = event_dt.weekday()
            return weekday in [5, 6]  # Суббота или воскресенье
        return True  # Если не удалось распарсить, пропускаем
    
    # Парсим дату фильтра
    filter_dt = None
    if filter_date_lower in ("завтра", "tomorrow"):
        filter_dt = datetime.now() + timedelta(days=1)
    elif filter_date_lower in ("послезавтра", "day after tomorrow"):
        filter_dt = datetime.now() + timedelta(days=2)
    elif filter_date_lower in ("сегодня", "today"):
        filter_dt = datetime.now()
    else:
        # Пытаемся распарсить как конкретную дату
        # Сначала пробуем стандартный парсер
        filter_dt = _parse_event_date(filter_date)
        
        # Если не получилось, пробуем парсить через _parse_russian_date из query_parser
        if filter_dt is None:
            try:
                from src.vdb.rag.query_parser import _parse_russian_date, _normalize_date
                # Пробуем нормализовать дату через query_parser
                normalized = _normalize_date(filter_date)
                if normalized and normalized != filter_date:
                    # Если нормализация изменила дату, пробуем распарсить нормализованную
                    filter_dt = _parse_event_date(normalized)
                elif normalized:
                    # Если нормализация вернула ту же дату, пробуем распарсить русскую дату
                    russian_parsed = _parse_russian_date(filter_date)
                    if russian_parsed:
                        filter_dt = _parse_event_date(russian_parsed)
            except Exception:
                pass
    
    if filter_dt is None:
        # Если не удалось распарсить фильтр, логируем и ОТФИЛЬТРОВЫВАЕМ событие
        # (строгая фильтрация - если дата фильтра не парсится, событие не подходит)
        import warnings
        warnings.warn(f"Не удалось распарсить дату фильтра: '{filter_date}', отфильтровываем событие")
        return False
    
    # Парсим дату события
    event_dt = _parse_event_date(event_date_str)
    if event_dt is None:
        # Если не удалось распарсить дату события, ОТФИЛЬТРОВЫВАЕМ событие
        # (строгая фильтрация - если дата события не парсится, событие не подходит)
        import warnings
        warnings.warn(f"Не удалось распарсить дату события: '{event_date_str}', отфильтровываем событие")
        return False
    
    # Сравниваем только даты (без времени)
    filter_date_only = filter_dt.date()
    event_date_only = event_dt.date()
    
    matches = filter_date_only == event_date_only
    
    # Логируем для отладки
    if not matches:
        import warnings
        warnings.warn(f"❌ Дата события '{event_date_str}' ({event_date_only}) не соответствует фильтру '{filter_date}' ({filter_date_only})")
    else:
        import warnings
        warnings.warn(f"✅ Дата события '{event_date_str}' ({event_date_only}) соответствует фильтру '{filter_date}' ({filter_date_only})")
    
    return matches


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
        similarity_threshold: Optional[float] = 0.4,
    ) -> List[Event]:
        """
        Поиск событий по запросу с фильтрацией по владельцу, городу и дате.

        Args:
            query: Поисковый запрос
            limit: Максимальное количество результатов
            owner: Владелец события для фильтрации
            city: Город для фильтрации (применяется только для публичных событий owner="all")
            date: Дата для фильтрации (формат: "DD.MM.YYYY", "завтра", "выходные" и т.д.)

        Returns:
            Список найденных событий
        """
        client = self._get_client()

        try:
            collection = client.collections.get(self.collection_name)
        except Exception:
            # Если коллекция не существует, возвращаем пустой список
            return []

        # Выполняем поиск
        try:
            # В Weaviate v4 near_text не поддерживает where напрямую
            # Используем двухэтапный подход: сначала семантический поиск, затем фильтрация
            result = collection.query.near_text(
                query=query,
                limit=limit * 3,  # Берем больше результатов для фильтрации по городу
                return_metadata=wvc.query.MetadataQuery(distance=True),
            )

            events = []
            for obj in result.objects:
                try:
                    # Фильтрация по эмбеддинговой близости (если есть distance)
                    obj_distance = getattr(obj.metadata, "distance", None)
                    if similarity_threshold is not None and obj_distance is not None:
                        if obj_distance > similarity_threshold:
                            continue

                    obj_owner = obj.properties.get("owner")
                    
                    # Фильтруем по владельцу программно
                    if owner:
                        # Проверяем, соответствует ли владелец объекта запрошенному
                        if owner != obj_owner:
                            continue
                    
                    # Фильтрация по городу применяется для ВСЕХ событий, если город указан
                    if city:
                        obj_location = obj.properties.get("location") or ""
                        obj_country = obj.properties.get("country") or ""
                        
                        # Проверяем наличие города в location или country (без учёта регистра)
                        city_lower = city.lower().strip()
                        location_lower = (obj_location or "").lower()
                        country_lower = (obj_country or "").lower()
                        
                        # Список вариантов города для проверки (включая падежи)
                        city_variants = [city_lower]
                        
                        # Добавляем варианты для Москвы
                        if city_lower == "москва":
                            city_variants.extend(["москве", "москвы", "москву", "москвой", "мск"])
                        # Добавляем варианты для Санкт-Петербурга
                        elif city_lower == "санкт-петербург":
                            city_variants.extend(["санкт-петербурге", "санкт-петербурга", "спб", "питер", "питере", "питера"])
                        # Для других городов добавляем основные падежи
                        else:
                            # Простое добавление окончаний для проверки
                            city_variants.extend([f"{city_lower}е", f"{city_lower}а", f"{city_lower}у"])
                        
                        # Проверяем, содержит ли location или country указанный город или его варианты
                        city_found = False
                        import re
                        
                        for variant in city_variants:
                            # Ищем город как отдельное слово (не часть другого слова)
                            # Паттерн: начало строки, пробел или запятая, затем город, затем пробел, запятая или конец строки
                            pattern = r'(^|[\s,])' + re.escape(variant) + r'([\s,]|$)'
                            if re.search(pattern, location_lower) or re.search(pattern, country_lower):
                                city_found = True
                                break
                        
                        # Если город не найден, пропускаем событие
                        if not city_found:
                            # Логируем для отладки
                            import warnings
                            warnings.warn(f"❌ Событие отфильтровано по городу: location='{obj_location}', country='{obj_country}', искомый город='{city}'")
                            continue
                        else:
                            # Логируем успешное совпадение для отладки
                            import warnings
                            warnings.warn(f"✅ Событие прошло фильтр по городу: location='{obj_location}', искомый город='{city}'")
                    
                    # Фильтрация по дате
                    if date:
                        obj_date = obj.properties.get("date")
                        if not _matches_date_filter(obj_date, date):
                            # Логируем для отладки (только если событие отфильтровано)
                            import warnings
                            warnings.warn(f"Событие отфильтровано по дате: event_date='{obj_date}', filter_date='{date}'")
                            continue
                        # Логируем успешное совпадение для отладки
                        import warnings
                        warnings.warn(f"✓ Событие прошло фильтр по дате: event_date='{obj_date}', filter_date='{date}'")
                    
                    event = Event(**obj.properties)
                    events.append(event)
                    
                    # Ограничиваем количество результатов
                    if len(events) >= limit:
                        break
                        
                except Exception as e:
                    # Пропускаем объекты, которые не соответствуют модели
                    import warnings
                    warnings.warn(f"Ошибка при парсинге события: {e}")
                    continue

            return events
        except Exception as e:
            # В случае ошибки возвращаем пустой список
            import warnings
            warnings.warn(f"Ошибка при поиске в Weaviate: {e}")
            return []

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

