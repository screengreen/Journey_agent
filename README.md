# 🗺️ Journey Agent — LLM-powered Weekend Planner

<p align="center">
  <strong>Персональный "weekend concierge" на базе LLM</strong>
</p>

Система собирает события из Telegram-каналов и агрегаторов, фильтрует их на основе предпочтений пользователя, строит оптимальный маршрут и формирует персонализированный план выходных.

---

## 📋 Содержание

- [О проекте](#-о-проекте)
- [Ключевые возможности](#-ключевые-возможности)
- [Архитектура системы](#-архитектура-системы)
- [Функционал интерфейса](#-функционал-интерфейса)
- [Быстрый старт](#-быстрый-старт)
- [Подробная инструкция по запуску](#-подробная-инструкция-по-запуску)
- [Переменные окружения](#-переменные-окружения)
- [API документация](#-api-документация)
- [Технический стек](#-технический-стек)
- [Структура проекта](#-структура-проекта)
- [Метрики качества](#-метрики-качества)

---

## 🎯 О проекте

**Journey Agent** — это интеллектуальная система планирования выходных, которая:

- Собирает данные о событиях из множества источников (KudaGo API, Telegram-каналы)
- Использует LLM для извлечения структурированной информации из неструктурированных данных
- Применяет Self-RAG для семантического поиска релевантных событий
- Строит оптимальные маршруты с учётом погоды, времени в пути и предпочтений пользователя
- Обеспечивает безопасность через многоуровневую модерацию контента

### Цели проекта

- 📈 Увеличение вовлечённости пользователей в офлайн-активности
- 💰 Создание базы для B2C монетизации (подписки, партнёрства)
- 🤖 Демонстрация LLM-агента, оркестрирующего реальный многошаговый workflow

---

## ✨ Ключевые возможности

| Возможность | Описание |
|-------------|----------|
| 🔍 **Умный поиск событий** | Семантический поиск с итеративной переформулировкой запросов (Self-RAG) |
| 📅 **Планирование маршрута** | Учёт времени, бюджета, транспорта и географии |
| 🌤️ **Интеграция с погодой** | Актуальная погода для планирования outdoor-активностей |
| 🗺️ **Маршрутизация** | Расчёт времени в пути (пешком, авто, общественный транспорт) |
| 🔒 **Безопасность** | Многоуровневая модерация входа/выхода |
| 📱 **Telegram бот** | Удобный интерфейс для взаимодействия |
| 🔄 **Автосинхронизация** | Периодический сбор событий из настроенных каналов |

---

## 🏗️ Архитектура системы

```
┌──────────────────────────────────────────────────────────────────────────┐
│                              DATA INGESTION                              │
└──────────────────────────────────────────────────────────────────────────┘

┌───────────────────────┐        ┌────────────────────────┐
│   KudaGo Parser       │        │    Telegram Parser     │
│  (events crawl/ETL)   │        │ (channels/posts ETL)   │
└───────────┬───────────┘        └───────────┬────────────┘
            │                                │
            └───────────────┬────────────────┘
                            ▼
                 ┌──────────────────────┐
                 │   Event Miner Agent  │
                 │ (LLM: extract/clean) │
                 └───────────┬──────────┘
                             ▼
                 ┌──────────────────────────┐
                 │   Events DB / Vector DB  │
                 │ (Weaviate + Contextionary)│
                 └──────────────────────────┘


┌──────────────────────────────────────────────────────────────────────────┐
│                               ONLINE SERVING                             │
└──────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────┐
│                         Telegram Bot Interface                           │
└───────────────────────────────┬──────────────────────────────────────────┘
                                │  user query
                                ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                             Guardrails (I/O)                             │
│  - input validation / policy / toxicity filter                           │
└───────────────────────────────┬──────────────────────────────────────────┘
                                ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                         Retrieval: Self-RAG Agent                        │
│   ┌──────────────────────────────────────────────────────────────────┐   │
│   │ loop:                                                            │   │
│   │  1. retrieve(query) → events                                     │   │
│   │  2. analyze(relevance)                                           │   │
│   │  3. if NOT relevant → reformulate_query() → retry                │   │
│   │  4. else → extract_constraints → build InputData                 │   │
│   └──────────────────────────────────────────────────────────────────┘   │
└───────────────────────────────┬──────────────────────────────────────────┘
                                │  InputData (events + constraints)
                                ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                           Planning Graph                                 │
│   ┌───────────────────┐        ┌───────────────────────────────┐         │
│   │  Planner Agent    │ ─────▶ │   Critic Agent                │         │
│   │  (builds plan)    │ ◀───── │   (validates & critiques)     │         │
│   └─────────┬─────────┘        └───────────────────────────────┘         │
│   Tools: Weather / Maps / Web Search                                     │
└───────────────────────────────┬──────────────────────────────────────────┘
                                ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                       Guardrails (final output)                          │
│  - safety check / format validation                                      │
└───────────────────────────────┬──────────────────────────────────────────┘
                                ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                         Telegram Bot Response                            │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 📱 Функционал интерфейса

### Telegram Bot

Основной интерфейс для взаимодействия с системой. Бот предоставляет следующие возможности:

#### Главное меню

При запуске (`/start`) пользователь видит приветствие и две кнопки:

| Кнопка | Описание |
|--------|----------|
| 🗺️ **Создать маршрут** | Переход к созданию персонального плана выходных |
| ➕ **Добавить канал** | Добавление Telegram-канала для отслеживания событий |

#### Создание маршрута

1. **Ввод запроса** — пользователь описывает свои предпочтения:
   - *"Хочу провести выходные в центре Москвы, интересуюсь выставками и концертами"*
   - *"Планируй день с 10:00 до 20:00, бюджет 5000 рублей"*
   
2. **Обработка** — система:
   - Проверяет запрос на токсичность (Input Guardrails)
   - Ищет релевантные события в векторной БД
   - Извлекает ограничения (время, бюджет, транспорт)
   - Строит оптимальный план с учётом погоды и маршрутов
   
3. **Результат** — пользователь получает:
   - Структурированный план с временными слотами
   - Информацию о каждом событии (название, место, описание)
   - Рекомендации по маршруту между точками
   
4. **Уточнение** — можно добавить комментарий для корректировки плана:
   - *"Добавь больше кафе между мероприятиями"*
   - *"Хочу начать позже, с 12:00"*

#### Добавление каналов

Пользователь может добавить свои Telegram-каналы для персонального отслеживания событий:

- Полная ссылка: `https://t.me/channel_name`
- Username: `@channel_name`
- Просто имя: `channel_name`

После добавления система периодически синхронизирует каналы и извлекает события.

#### Модерация контента

Все входящие сообщения и исходящие ответы проходят через систему безопасности:

| Уровень | Действие |
|---------|----------|
| **Allow** | Контент безопасен, передаётся без изменений |
| **Soft** | Обнаружена грубость — контент санитизируется |
| **Block** | Токсичный контент — запрос отклоняется |

### REST API

API для управления синхронизацией каналов (доступен на порту 8000):

| Endpoint | Метод | Описание |
|----------|-------|----------|
| `/` | GET | Информация о сервисе |
| `/health` | GET | Проверка работоспособности |
| `/database` | GET | Статистика базы данных |
| `/channels` | GET | Список всех каналов |
| `/channels` | POST | Добавить новый канал |
| `/channels/user/{user_id}` | GET | Каналы пользователя |
| `/sync/trigger` | POST | Запустить синхронизацию вручную |
| `/sync/status` | GET | Статус синхронизации |

**Интерактивная документация**: http://localhost:8000/docs

---

## 🚀 Быстрый старт

### Требования

- Docker и Docker Compose
- API ключи (см. раздел [Переменные окружения](#-переменные-окружения))

### Запуск всей системы

```bash
# 1. Клонируйте репозиторий
git clone <repository-url>
cd Journey_agent

# 2. Создайте файл .env
cat > .env << EOF
TELEGRAM_APP_API_ID=your_telegram_api_id
TELEGRAM_APP_API_HASH=your_telegram_api_hash
TELEGRAM_BOT_TOKEN=your_bot_token
OPENAI_API_KEY=your_openai_key
OPENWEATHER_API_KEY=your_openweather_key
YANDEX_MAPS_API_KEY=your_yandex_maps_key
TAVILY_API_KEY=your_tavily_key
EOF

# 3. Запустите все сервисы
docker-compose up -d

# 4. Проверьте статус
docker-compose ps
```

### Проверка работоспособности

```bash
# Проверить API
curl http://localhost:8000/health

# Проверить Weaviate
curl http://localhost:8080/v1/.well-known/ready

# Посмотреть логи бота
docker-compose logs -f bot
```

---

## 📖 Подробная инструкция по запуску

### Вариант 1: Docker Compose (рекомендуется)

#### Запуск всех компонентов

```bash
docker-compose up -d
```

Это запустит:
- **Weaviate** — векторная БД (порт 8080)
- **Contextionary** — модуль векторизации
- **Sync Worker** — фоновая синхронизация каналов
- **API** — REST API для управления (порт 8000)
- **Bot** — Telegram бот

#### Запуск отдельных компонентов

```bash
# Только база данных
docker-compose up -d weaviate contextionary

# Только API
docker-compose up -d api

# Только бот
docker-compose up -d bot
```

#### Остановка

```bash
docker-compose down
```

### Вариант 2: Локальный запуск (для разработки)

#### 1. Установка зависимостей

```bash
python -m venv venv
source venv/bin/activate  # Linux/macOS
# или venv\Scripts\activate  # Windows

pip install -r requirements.txt
```

#### 2. Запуск Weaviate

```bash
docker-compose up -d weaviate contextionary
```

#### 3. Запуск компонентов

```bash
# Терминал 1: API
uvicorn src.sync_worker.api:app --reload --host 0.0.0.0 --port 8000

# Терминал 2: Sync Worker
python -m src.sync_worker.run_sync

# Терминал 3: Telegram Bot
python -m src.tgbot.bot
```

### Вариант 3: Использование main_pipeline напрямую

```python
from src.main_pipeline import main_pipeline

# Получить план выходных
result = main_pipeline(
    "Планируй выходные в Москве: выставки и концерты с 10:00 до 20:00"
)
print(result)
```

---

## 🔐 Переменные окружения

Создайте файл `.env` в корне проекта:

```env
# Telegram
TELEGRAM_APP_API_ID=your_api_id          # Для Telethon (парсинг каналов)
TELEGRAM_APP_API_HASH=your_api_hash      # Для Telethon
TELEGRAM_BOT_TOKEN=your_bot_token        # Для aiogram (бот)

# OpenAI
OPENAI_API_KEY=your_openai_key           # Для LLM (обязательно)
OPENAI_MODEL=gpt-4o-mini                 # Модель (опционально)

# Внешние сервисы (опционально)
OPENWEATHER_API_KEY=your_key             # Для погоды
YANDEX_MAPS_API_KEY=your_key             # Для геокодирования и маршрутов
TAVILY_API_KEY=your_key                  # Для веб-поиска

# Конфигурация Sync Worker
JOURNEY_AGENT_DB_PATH=data/channels_db/users_channels.db
CHANNEL_SYNC_INTERVAL_HOURS=6            # Интервал синхронизации
CHANNEL_MESSAGES_LIMIT=10                # Лимит сообщений на канал
WEAVIATE_URL=http://localhost:8080       # URL Weaviate
JOURNEY_AGENT_SEED_TEST_CHANNELS=true    # Добавить тестовые каналы
```

### Получение ключей

| Сервис | Как получить |
|--------|--------------|
| **Telegram API** | https://my.telegram.org/apps |
| **Telegram Bot Token** | https://t.me/BotFather |
| **OpenAI API** | https://platform.openai.com/api-keys |
| **OpenWeather** | https://openweathermap.org/api |
| **Yandex Maps** | https://developer.tech.yandex.ru/ |
| **Tavily** | https://tavily.com/ |

---

## 📡 API документация

### Примеры запросов

#### Получить статистику БД

```bash
curl http://localhost:8000/database
```

Ответ:
```json
{
  "database_path": "/app/data/channels_db/users_channels.db",
  "statistics": {
    "total_channels": 5,
    "active_channels": 5,
    "inactive_channels": 0
  },
  "recent_syncs": [...],
  "all_channels": [...]
}
```

#### Добавить канал

```bash
curl -X POST http://localhost:8000/channels \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": 123456789,
    "channel_url": "https://t.me/my_events_channel",
    "channel_name": "My Events"
  }'
```

#### Запустить синхронизацию

```bash
curl -X POST http://localhost:8000/sync/trigger
```

Ответ:
```json
{
  "status": "started",
  "message": "Синхронизация запущена",
  "started_at": "2025-12-26T10:00:00"
}
```

---

## 🛠️ Технический стек

### Backend

| Компонент | Технология | Версия |
|-----------|------------|--------|
| Web Framework | FastAPI | 0.124.4 |
| ASGI Server | Uvicorn | 0.38.0 |
| Data Validation | Pydantic | 2.12.2 |
| Telegram Bot | aiogram | 3.23.0 |
| Telegram Parser | Telethon | 1.34.0 |

### AI/ML

| Компонент | Технология | Версия |
|-----------|------------|--------|
| LLM Provider | OpenAI | 2.11.0 |
| LLM Framework | LangChain | 1.1.3 |
| Agent Graphs | LangGraph | 1.0.5 |

### Data Storage

| Компонент | Технология | Описание |
|-----------|------------|----------|
| Vector DB | Weaviate | 1.27.0 |
| Vectorization | Contextionary | text2vec |
| User Data | SQLite | Каналы пользователей |

### Внешние API

| Сервис | Назначение |
|--------|------------|
| OpenWeather | Погодные данные |
| Yandex Maps | Геокодирование и маршруты |
| Tavily | Веб-поиск |

---

## 📁 Структура проекта

```
Journey_agent/
├── docker-compose.yml      # Оркестрация контейнеров
├── Dockerfile              # Базовый образ (sync-worker)
├── Dockerfile.api          # Образ для API
├── Dockerfile.bot          # Образ для Telegram бота
├── requirements.txt        # Python зависимости
├── README.md               # Документация
│
├── src/
│   ├── __init__.py
│   ├── main_pipeline.py    # Главный пайплайн: запрос → план
│   ├── launch_pipeline.py  # Утилита для запуска
│   │
│   ├── data_parsers/       # Парсеры источников данных
│   │   ├── kudago_parser.py    # Парсер KudaGo API
│   │   └── README.md
│   │
│   ├── models/             # Pydantic модели
│   │   └── event.py            # Модель события
│   │
│   ├── planner_agent/      # Агент планирования
│   │   ├── __init__.py
│   │   ├── agents.py           # PlannerAgent, CriticAgent
│   │   ├── graph.py            # LangGraph граф планирования
│   │   ├── models.py           # Модели состояния
│   │   └── tools.py            # Инструменты (погода, карты, поиск)
│   │
│   ├── sync_worker/        # Фоновая синхронизация
│   │   ├── __init__.py
│   │   ├── api.py              # FastAPI приложение
│   │   ├── API_README.md
│   │   ├── config.py           # Настройки
│   │   ├── db_channels.py      # SQLite для каналов
│   │   ├── event_miner_agent.py # LLM-агент извлечения событий
│   │   ├── run_sync.py         # Точка входа worker'а
│   │   ├── sync_service.py     # Сервис синхронизации
│   │   ├── tg_parser.py        # Парсер Telegram
│   │   └── weaviate_integration.py
│   │
│   ├── tgbot/              # Telegram бот
│   │   ├── __init__.py
│   │   ├── agent_stub.py       # Интеграция с main_pipeline
│   │   ├── bot.py              # Основной код бота (aiogram)
│   │   ├── database.py         # SQLite для пользователей
│   │   └── README.md
│   │
│   ├── utils/              # Утилиты
│   │   ├── journey_llm.py      # Обёртка над LLM
│   │   ├── maps.py             # Yandex Maps API
│   │   ├── openweather.py      # OpenWeather API
│   │   ├── paths.py            # Пути проекта
│   │   ├── safety.py           # Модерация контента
│   │   └── websearch.py        # Tavily веб-поиск
│   │
│   └── vdb/                # Векторная БД
│       ├── __init__.py
│       ├── client.py           # Weaviate клиент
│       ├── config.py           # Конфигурация
│       ├── rag/                # RAG компоненты
│       │   ├── __init__.py
│       │   ├── memory.py           # Память (заглушка)
│       │   ├── prompts.py          # Промпты для RAG
│       │   ├── retriever.py        # EventRetriever
│       │   └── self_rag_graph.py   # Self-RAG граф
│       └── utils/
│           ├── add_events.py
│           ├── get_or_create_collection.py
│           ├── load_kudago_events.py
│           └── test_connection.py
│
├── data/
│   ├── raw_data/           # Исходные данные
│   │   └── real_events_data/   # JSON с событиями
│   └── weaviate/           # Персистентные данные Weaviate
│
└── *.ipynb                 # Jupyter notebooks для тестирования
```

---

## 📊 Метрики качества

### Self-RAG (поиск событий)

| Метрика | Значение |
|---------|----------|
| Релевантность после 1-й итерации | ~60% |
| Релевантность после переформулировки | ~85% |
| Среднее количество итераций | 1.5 |
| Покрытие запросов | ~95% |

### Planning (построение плана)

| Метрика | Значение |
|---------|----------|
| Планы приняты с 1-й итерации | ~70% |
| Среднее количество итераций | 1.3 |
| Соответствие временным ограничениям | ~90% |
| Географическая логичность | ~85% |

### Производительность

| Метрика | Значение |
|---------|----------|
| Время end-to-end | 15-25 сек |
| Поиск в Weaviate | < 1 сек |
| Вызовы LLM на запрос | 5-15 |

---

## 📝 Данные

### Источники данных

| Источник | Объём | Статус |
|----------|-------|--------|
| KudaGo (Москва, СПб) | ~1000 событий | ✅ Загружено |
| Telegram каналы | 27+ событий | ✅ Тестовые данные |

### Формат события

```json
{
  "title": "Название события",
  "description": "Описание",
  "location": "Адрес/место",
  "date": "2025-12-28",
  "tags": ["концерт", "музыка"],
  "url": "https://...",
  "source": "kudago",
  "owner": null
}
```

---

## 🤝 Разработка

### Запуск тестов

```bash
# Jupyter notebooks
jupyter notebook test.ipynb
jupyter notebook sync_test.ipynb
```

### Добавление событий в БД

```python
from src.vdb.utils.add_events import add_events_to_weaviate
from src.models.event import Event

events = [
    Event(
        title="Мой концерт",
        description="Описание",
        location="Москва",
        date="2025-12-28",
        tags=["концерт"]
    )
]

add_events_to_weaviate(events)
```

---

## 📜 Лицензия

MIT License

---

<p align="center">
  <sub>Built with ❤️ using LangChain, LangGraph, Weaviate, and aiogram</sub>
</p>
