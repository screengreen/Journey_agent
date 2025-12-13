# Парсеры данных для llm_journer

Модуль для парсинга событий из различных источников в формат модели `Event`.

## KudaGo Parser

Парсер для событий из API KudaGo (kudago.com) - крупнейшего агрегатора событий в России.

### Поддерживаемые форматы

Парсер поддерживает JSON файлы с событиями KudaGo в следующих форматах:
- `events_msk_*.json` - события Москвы
- `events_spb_*.json` - события Санкт-Петербурга
- `events_pydantic_*.json` - события с дополнительными полями

### Структура данных

Парсер извлекает следующие поля из JSON:

| JSON поле | Event поле | Описание |
|-----------|------------|----------|
| `title` / `short_title` | `title` | Название события |
| `description` | `description` | Описание события |
| `tags[].name` | `tags` | Теги и категории |
| `category` | `tags` | Категория события (concert, exhibition, etc.) |
| `place.title`, `place.address` | `location` | Адрес места проведения |
| `dates[].start` | `date` | Дата начала события (timestamp -> строка) |
| `site_url` / `url` | `url` | Ссылка на событие |
| `location` | `tags` | Код города (msk, spb) |

### Использование

#### В Python коде

```python
from src.data_parsers.kudago_parser import parse_kudago_json, parse_all_kudago_files

# Парсинг одного файла
events = parse_kudago_json("data/events.json", owner="user123")

# Парсинг всех файлов из директории
all_events = parse_all_kudago_files("data/raw_data/real_events_data", owner="user123")

print(f"Загружено {len(all_events)} событий")
```

#### Через скрипт командной строки

```bash
# Загрузить события в Weaviate
python src/vdb/scripts/load_kudago_events.py \
    --data-dir data/raw_data/real_events_data \
    --owner user123

# С ограничением количества (для тестирования)
python src/vdb/scripts/load_kudago_events.py \
    --data-dir data/raw_data/real_events_data \
    --owner user123 \
    --limit 100

# Тихий режим
python src/vdb/scripts/load_kudago_events.py \
    --data-dir data/raw_data/real_events_data \
    --owner user123 \
    --quiet
```

#### В Jupyter Notebook

См. примеры в `test.ipynb`:
- Ячейка 8: Парсинг одного файла
- Ячейка 9: Парсинг всех файлов из директории
- Ячейка 10: Загрузка в Weaviate

### Функции

#### `parse_kudago_json(json_path, owner=None)`

Парсит один JSON файл с событиями.

**Параметры:**
- `json_path` (str): Путь к JSON файлу
- `owner` (str, optional): ID владельца события для фильтрации

**Возвращает:**
- `List[Event]`: Список спарсенных событий

**Пример:**
```python
events = parse_kudago_json("events.json", owner="user123")
for event in events[:3]:
    print(f"{event.title} - {event.location}")
```

#### `parse_all_kudago_files(directory, owner=None)`

Парсит все JSON файлы с событиями из директории.

**Параметры:**
- `directory` (str): Путь к директории с JSON файлами
- `owner` (str, optional): ID владельца события

**Возвращает:**
- `List[Event]`: Список всех событий из всех файлов

**Пример:**
```python
all_events = parse_all_kudago_files("data/raw_data/real_events_data")
print(f"Всего событий: {len(all_events)}")
```

### Обработка ошибок

Парсер устойчив к ошибкам:
- Пропускает события с некорректными данными
- Логирует ошибки в консоль
- Продолжает обработку остальных событий

### Особенности

1. **Даты**: Unix timestamps конвертируются в читаемый формат `YYYY-MM-DD HH:MM`
2. **Теги**: Автоматически добавляется тег `all` для общедоступных событий
3. **Местоположение**: Собирается из названия места, адреса и ближайшего метро
4. **Защита от некорректных данных**: Фильтруются нереалистичные даты и пустые значения

### Примеры данных

**Входные данные (JSON):**
```json
{
  "id": 205773,
  "title": "музыкальный проект #В_СВЕЧАХ",
  "description": "Цикл завораживающих концертов...",
  "category": "concert",
  "place": {
    "title": "гостиница «Националь»",
    "address": "ул. Моховая, д. 15/1",
    "subway": "Охотный Ряд"
  },
  "dates": [{"start": 1688922000}],
  "url": "https://kudago.com/msk/event/..."
}
```

**Выходные данные (Event):**
```python
Event(
    title="музыкальный проект #В_СВЕЧАХ",
    owner="user123",
    description="Цикл завораживающих концертов...",
    tags=["all", "concert", "msk"],
    source="kudago",
    country="Россия",
    location="гостиница «Националь», ул. Моховая, д. 15/1, м. Охотный Ряд",
    date="2023-07-09 19:00",
    url="https://kudago.com/msk/event/..."
)
```

## Добавление новых парсеров

Чтобы добавить парсер для нового источника:

1. Создайте новый файл `{source}_parser.py`
2. Реализуйте функцию `parse_{source}_json(json_path, owner=None) -> List[Event]`
3. Убедитесь, что возвращаемые объекты соответствуют модели `Event`
4. Добавьте документацию и примеры использования

## Тестирование

```python
# Тестирование парсера
from src.data_parsers.kudago_parser import parse_kudago_json

events = parse_kudago_json("test_data.json")
assert len(events) > 0
assert all(isinstance(e.title, str) for e in events)
assert all(e.source == "kudago" for e in events)
```



