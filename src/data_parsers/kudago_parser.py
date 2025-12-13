"""Парсер для событий из KudaGo API."""

import json
from typing import List, Optional, Dict, Any
from pathlib import Path
from datetime import datetime
from src.models.event import Event


def _format_date(timestamp: Optional[int]) -> Optional[str]:
    """
    Форматирует Unix timestamp в читаемую дату.
    
    Args:
        timestamp: Unix timestamp в секундах
        
    Returns:
        Отформатированная дата или None
    """
    if not timestamp or timestamp < 0:
        return None
    
    try:
        # Защита от нереалистичных дат
        if timestamp > 253370754000:  # Дата далеко в будущем
            return None
        
        dt = datetime.fromtimestamp(timestamp)
        return dt.strftime("%Y-%m-%d %H:%M")
    except (ValueError, OSError):
        return None


def _extract_tags(event_data: Dict[str, Any]) -> List[str]:
    """
    Извлекает теги из данных события.
    
    Args:
        event_data: Данные события
        
    Returns:
        Список тегов
    """
    tags = ['all']  # Общедоступное событие
    
    # Добавляем категорию
    if event_data.get('category'):
        tags.append(event_data['category'])
    
    # Добавляем локацию
    if event_data.get('location'):
        tags.append(event_data['location'])
    
    # Добавляем теги из массива
    if event_data.get('tags'):
        for tag in event_data['tags']:
            if isinstance(tag, dict):
                tag_name = tag.get('name')
                if tag_name:
                    tags.append(tag_name)
            elif isinstance(tag, str):
                tags.append(tag)
    
    # Добавляем возрастное ограничение
    if event_data.get('age_restriction'):
        tags.append(event_data['age_restriction'])
    
    return tags


def _extract_location(event_data: Dict[str, Any]) -> Optional[str]:
    """
    Извлекает информацию о местоположении события.
    
    Args:
        event_data: Данные события
        
    Returns:
        Строка с местоположением
    """
    place = event_data.get('place')
    
    if place and isinstance(place, dict):
        parts = []
        
        if place.get('title'):
            parts.append(place['title'])
        
        if place.get('address'):
            parts.append(place['address'])
        
        if place.get('subway'):
            parts.append(f"м. {place['subway']}")
        
        return ', '.join(parts) if parts else None
    
    return None


def _extract_dates(event_data: Dict[str, Any]) -> Optional[str]:
    """
    Извлекает даты проведения события.
    
    Args:
        event_data: Данные события
        
    Returns:
        Строка с датами
    """
    dates = event_data.get('dates', [])
    
    if not dates:
        return None
    
    # Берем первую валидную дату
    for date_info in dates:
        start = date_info.get('start')
        end = date_info.get('end')
        
        start_str = _format_date(start)
        end_str = _format_date(end)
        
        if start_str:
            if end_str and start_str != end_str:
                return f"{start_str} - {end_str}"
            return start_str
    
    return None


def parse_kudago_json(json_path: str, owner: Optional[str] = None) -> List[Event]:
    """
    Парсит JSON файл с событиями из KudaGo API.
    
    Args:
        json_path: Путь к JSON файлу
        owner: ID владельца события (для фильтрации по пользователю)
    
    Returns:
        List[Event]: Список событий
    """
    path = Path(json_path)
    
    if not path.exists():
        raise FileNotFoundError(f"Файл не найден: {json_path}")
    
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Данные могут быть списком событий напрямую или вложенными
    events_data = data
    if isinstance(data, dict) and 'events' in data:
        events_data = data['events']
    
    events = []
    
    for event_data in events_data:
        try:
            # Извлекаем основные поля
            title = event_data.get('title') or event_data.get('short_title', 'Без названия')
            description = event_data.get('description', '')
            
            # Формируем теги
            tags = _extract_tags(event_data)
            
            # Извлекаем местоположение
            location = _extract_location(event_data)
            
            # Извлекаем даты
            date = _extract_dates(event_data)
            
            # Извлекаем URL
            url = event_data.get('site_url') or event_data.get('url')
            
            # Определяем страну
            country = 'Россия'
            
            # Создаем Event
            event = Event(
                title=title,
                owner=owner,
                description=description,
                tags=tags,
                source='kudago',
                country=country,
                location=location,
                date=date,
                url=url,
            )
            events.append(event)
            
        except (KeyError, ValueError, TypeError) as e:
            # Пропускаем события с ошибками, но логируем
            print(f"Ошибка при парсинге события {event_data.get('id', 'unknown')}: {e}")
            continue
    
    return events


def parse_all_kudago_files(directory: str, owner: Optional[str] = None) -> List[Event]:
    """
    Парсит все JSON файлы с событиями KudaGo из директории.
    
    Args:
        directory: Путь к директории с JSON файлами
        owner: ID владельца события (для фильтрации по пользователю)
    
    Returns:
        List[Event]: Список всех событий из всех файлов
    """
    dir_path = Path(directory)
    
    if not dir_path.exists():
        raise FileNotFoundError(f"Директория не найдена: {directory}")
    
    all_events = []
    
    # Ищем JSON файлы с событиями
    json_files = list(dir_path.glob("events*.json"))
    
    print(f"Найдено {len(json_files)} файлов с событиями")
    
    for json_file in json_files:
        print(f"Парсим файл: {json_file.name}")
        try:
            events = parse_kudago_json(str(json_file), owner=owner)
            all_events.extend(events)
            print(f"  Добавлено событий: {len(events)}")
        except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
            print(f"  Ошибка при парсинге файла {json_file.name}: {e}")
            continue
    
    print(f"\nВсего событий загружено: {len(all_events)}")
    return all_events