Возможности
Парсинг реальных данных: Получение актуальных событий из Kudago API

12+ категорий: Концерты, театр, выставки, фестивали, образование, вечеринки, шоу, детские, кино, мода, гастрономия, стендап

100+ событий на категорию: Целевой показатель для каждой категории

Автоматическое обогащение: Преобразование place_id в полную информацию о местах

Pydantic модели: Строгая типизация и валидация данных

Векторная база данных: Семантический поиск по событиям

Поддержка нескольких городов: Москва и Санкт-Петербург

Обработка ошибок: Детальное логирование и восстановление

Экспорт данных: JSON, CSV, базы данных SQLite

# 1. Инициализация парсера
from src.parser import RealKudaGoParser

# 2. Парсинг Москвы
parser_msk = RealKudaGoParser(city="msk")
events_msk = await parser_msk.parse_all_categories()

# 3. Парсинг Санкт-Петербурга
parser_spb = RealKudaGoParser(city="spb")
events_spb = await parser_spb.parse_all_categories()
Запуск через Python скрипт
Создайте файл run_parser.py:

python
import asyncio
from src.pipeline import RealDataPipeline

async def main():
    # Запуск полного пайплайна для Москвы
    pipeline = RealDataPipeline(city="msk")
    results = await pipeline.run_pipeline()
    
    print(f"Спаршено событий: {results['total_events']}")
    print(f"Сохранено в БД: {results['save_result']['success']}")
    print(f"JSON файл: {results['json_file']}")

if __name__ == "__main__":
    asyncio.run(main())
📊 Использование
1. Базовый парсинг одной категории
python
import asyncio
from src.parser import RealKudaGoParser

async def parse_single_category():
    parser = RealKudaGoParser(
        city="msk",
        categories=["concert"],  # Только концерты
        max_events_per_category=50
    )
    
    results = await parser.parse_all_categories()
    print(f"Концертов в Москве: {len(results.get('Концерты', []))}")

asyncio.run(parse_single_category())
2. Использование удобного клиента
python
from src.client import KudagoClient
import asyncio

async def use_client():
    # Создание клиента
    client = KudagoClient(
        default_city="msk",
        default_categories=["concert", "theater", "exhibition"]
    )
    
    # Получение данных
    events = await client.get_events(
        limit_per_category=100,
        days_ahead=180  # События на полгода вперед
    )
    
    # Сохранение в файлы
    files = client.save_to_disk(events, output_dir="my_events")
    
    print(f"Сохраненные файлы: {list(files.keys())}")

asyncio.run(use_client())
3. Полный пайплайн для обоих городов
python
from src.pipeline import parse_both_cities_real
import asyncio

async def full_pipeline():
    results = await parse_both_cities_real()
    
    # Анализ результатов
    print("="*60)
    print("ИТОГИ ПАРСИНГА")
    print("="*60)
    
    for city, data in results.items():
        if data:
            city_name = "Москва" if city == "msk" else "Санкт-Петербург"
            print(f"\n{city_name}:")
            print(f"  • Событий: {data['total_events']}")
            print(f"  • Pydantic моделей: {data['pydantic_models']}")
            print(f"  • Файл: {data['json_file'].split('/')[-1]}")

asyncio.run(full_pipeline())
4. Поиск по векторной БД
python
from src.vector_db import RealEventVectorDatabase

# Подключение к БД
db = RealEventVectorDatabase("real_events_msk_vector.db")

# Поиск похожих событий
query = "рок концерт вечер"
results = db.search_similar(query, limit=5, category="concert")

print(f"Результаты поиска для '{query}':")
for i, event in enumerate(results, 1):
    print(f"{i}. {event['title'][:60]}...")
    print(f"   Сходство: {event['similarity']:.3f}")
    print(f"   Категория: {event['category']}")
    print()

# Статистика БД
stats = db.get_stats()
print(f"Всего событий в БД: {stats['total_events']}")
print(f"Категорий: {len(stats['by_category'])}")

db.close()
⚙️ Конфигурация
Настройки парсера
Параметр	Тип	По умолчанию	Описание
city	str	"msk"	Город (msk или spb)
categories	List[str]	12 категорий	Список категорий для парсинга
max_events_per_category	int	100	Максимум событий на категорию
page_size	int	100	Размер страницы API (max 100)
timeout	int	30	Таймаут запросов в секундах
retries	int	3	Количество повторных попыток
enable_enrichment	bool	True	Обогащение данных о местах
days_ahead	int	365	Парсинг событий на N дней вперед
Доступные категории
python
categories = [
    "concert",      # Концерты
    "theater",      # Театр
    "exhibition",   # Выставки
    "festival",     # Фестивали
    "education",    # Образование
    "party",        # Вечеринки
    "sport",        # Спорт
    "quest",        # Квесты
    "excursion",    # Экскурсии
    "show",         # Шоу
    "standup",      # Стендап
    "kids",         # Детские
    "fashion",      # Мода
    "gastronomy",   # Гастрономия
    "cinema",       # Кино
    "lecture",      # Лекции
    "masterclass",  # Мастер-классы
    "tour",         # Туры
]
🏗️ Модели данных
Основные модели Pydantic:
python
# EventModel - основная модель события
{
    "id": int,                    # ID события
    "title": str,                 # Название
    "description": str,           # Описание
    "category": EventCategory,    # Категория (enum)
    "dates": List[DateModel],     # Даты проведения
    "age_restriction": str,       # Возрастное ограничение (0+, 6+, 12+, и т.д.)
    "place": PlaceModel,          # Место проведения
    "price": PriceModel,          # Цена
    "tags": List[TagModel],       # Теги
    "images": List[ImageModel],   # Изображения
    "participants": List[ParticipantModel],  # Участники
    "url": str,                   # URL события
    "is_free": bool,              # Бесплатное ли
}
Особенности валидации:
Автоматическое преобразование age_restriction: 0 → "0+", 6 → "6+"

Обогащение мест: place_id → полная информация о месте

Нормализация цен: Корректная обработка бесплатных событий

Обработка дат: Конвертация timestamp → читаемый формат

🗃️ Векторная база данных
Структура БД:
sql
-- Основные таблицы:
events                  # Основная информация
event_embeddings        # Векторные эмбеддинги
event_details           # Детальные данные (JSON)
processing_errors       # Ошибки обработки
Возможности поиска:
python
# Поиск по семантическому сходству
db.search_similar("джаз концерт вечер", limit=10)

# Фильтрация по категории
db.search_similar("выставка", category="exhibition", limit=5)

# Фильтрация по городу
db.search_similar("детский праздник", city="msk", limit=3)
Создание эмбеддингов:
Используется модель all-MiniLM-L6-v2:

Размерность: 384

Быстрая обработка

Хорошее качество для русского языка

📈 Примеры работы
Пример 1: Сбор статистики
python
import json
from datetime import datetime

def analyze_data(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        events = json.load(f)
    
    print(f"Всего событий: {len(events)}")
    
    # Статистика по категориям
    categories = {}
    for event in events:
        cat = event.get('category', 'unknown')
        categories[cat] = categories.get(cat, 0) + 1
    
    print("\nРаспределение по категориям:")
    for cat, count in sorted(categories.items(), key=lambda x: x[1], reverse=True):
        print(f"  {cat}: {count}")
    
    # Статистика по ценам
    free = sum(1 for e in events if e.get('is_free'))
    print(f"\nБесплатных событий: {free} ({free/len(events)*100:.1f}%)")
    
    # Статистика по датам
    if events and 'dates' in events[0]:
        dates_count = sum(1 for e in events if e.get('dates'))
        print(f"Событий с датами: {dates_count}")

# Использование
analyze_data("real_events_data/events_msk_20241212_120000.json")
Пример 2: Экспорт в CSV
python
import pandas as pd
import json

def export_to_csv(json_file, csv_file):
    with open(json_file, 'r', encoding='utf-8') as f:
        events = json.load(f)
    
    # Преобразование данных
    df_data = []
    for event in events:
        row = {
            'id': event['id'],
            'title': event['title'],
            'category': event.get('category'),
            'age_restriction': event.get('age_restriction', '0+'),
            'is_free': event.get('is_free', False),
            'dates_count': len(event.get('dates', [])),
            'place': event.get('place', {}).get('title'),
            'price_text': event.get('price_text', 'Цена не указана'),
            'url': event.get('url')
        }
        df_data.append(row)
    
    df = pd.DataFrame(df_data)
    df.to_csv(csv_file, index=False, encoding='utf-8-sig')
    print(f"Экспортировано {len(df)} событий в {csv_file}")

export_to_csv(
    "real_events_data/events_msk_20241212_120000.json",
    "events_export.csv"
)
🚀 Развертывание
Вариант 1: Локальный запуск (рекомендуется для разработки)
bash
# Активация окружения
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# Запуск парсера
python -c "
import asyncio
from src.pipeline import parse_moscow_real
asyncio.run(parse_moscow_real())
"
Вариант 2: Docker контейнер
dockerfile
# Dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY data/ ./data/

CMD ["python", "-c", "
import asyncio
from src.pipeline import parse_both_cities_real
asyncio.run(parse_both_cities_real())
"]
bash
# Сборка и запуск
docker build -t kudago-parser .
docker run -v $(pwd)/data:/app/data kudago-parser
Вариант 3: Планировщик задач (CRON)
bash
# crontab -e
# Ежедневный запуск в 3:00
0 3 * * * cd /path/to/real-events-parser && venv/bin/python run_daily.py
🔧 Решение проблем
Частые проблемы и решения:
Ошибка 429 (Too Many Requests):

python
# Увеличьте паузы между запросами
parser = RealKudaGoParser(
    retries=5,
    timeout=60
)
Нет данных в некоторых категориях:

Некоторые категории могут не содержать событий

Попробуйте альтернативные категории из списка

Проблемы с эмбеддингами:

python
# Используйте более простую модель
db = RealEventVectorDatabase(
    embedding_model="paraphrase-multilingual-MiniLM-L12-v2"
)
Ошибки валидации Pydantic:

Все ошибки сохраняются в real_events_data/conversion_errors_*.json

Проверьте логи для деталей

Мониторинг и логирование:
python
import logging

# Настройка подробного логирования
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('parser.log'),
        logging.StreamHandler()
    ]
)