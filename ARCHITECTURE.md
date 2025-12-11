# Архитектура проекта Journey Agent

## Общее описание

Journey Agent - это Telegram бот для поиска событий (концерты, выставки и т.д.) на основе семантического поиска и геолокации.

## Компоненты системы

### 1. Telegram Bot (`src/bot/`)
- Обработка команд и сообщений пользователей
- Управление подписками на каналы
- Обработка запросов на поиск событий
- Отображение результатов с учетом расстояния

### 2. Parsers (`src/parsers/`)
- **Base Parser** - абстрактный класс для всех парсеров
- **Website Parsers** - парсеры для различных сайтов с событиями
  - Afisha.ru
  - Eventbrite
  - Timepad
  - И другие
- **Telegram Channel Parser** - парсер для Telegram каналов пользователей

### 3. Services (`src/services/`)
- **Vector Search Service** - работа с векторной БД (Weaviate)
- **Geolocation Service** - геокодирование адресов и расчет расстояний
- **Event Processing Service** - обработка и нормализация событий
- **Scheduler Service** - планировщик задач для периодического парсинга

### 4. Storage (`src/storage/`)
- **Weaviate Client** - клиент для работы с векторной БД
- **User Storage** - хранение данных пользователей (каналы, локация)
- **Event Storage** - работа с событиями в БД

### 5. Models (`src/models/`)
- **Event** - модель события
- **User** - модель пользователя
- **Channel** - модель канала
- **Location** - модель локации

## Поток данных

### Добавление событий
1. Пользователь отправляет ссылку на канал в Telegram бот
2. Парсер Telegram каналов периодически проверяет каналы
3. Парсеры сайтов периодически парсят события с сайтов
4. События обрабатываются и векторизуются
5. События сохраняются в Weaviate с тегами пользователей

### Поиск событий
1. Пользователь отправляет запрос (например, "концерт в Москве")
2. Бот извлекает локацию пользователя (из запроса или сохраненную)
3. Запрос отправляется в Vector Search Service
4. Сервис выполняет семантический поиск в Weaviate
5. Геолокационный сервис рассчитывает расстояния до событий
6. События сортируются по расстоянию
7. Бот возвращает ближайшие события пользователю

## Технологический стек

- **Python 3.11+**
- **python-telegram-bot** - для Telegram бота
- **Weaviate** - векторная БД
- **LangChain/LangGraph** - для RAG системы
- **geopy** - для геолокации и расчета расстояний
- **BeautifulSoup/Scrapy** - для парсинга сайтов
- **Telethon** - для парсинга Telegram каналов
- **APScheduler** - для планирования задач

## Структура директорий

```
Journey_agent/
├── src/
│   ├── bot/                    # Telegram бот
│   │   ├── __init__.py
│   │   ├── handlers/           # Обработчики команд и сообщений
│   │   │   ├── __init__.py
│   │   │   ├── commands.py     # Команды (/start, /help, etc.)
│   │   │   ├── channels.py     # Обработка каналов
│   │   │   └── search.py       # Обработка поисковых запросов
│   │   ├── keyboards.py         # Клавиатуры для бота
│   │   └── bot.py              # Основной класс бота
│   │
│   ├── parsers/                # Парсеры
│   │   ├── __init__.py
│   │   ├── base.py             # Базовый класс парсера
│   │   ├── telegram/           # Парсер Telegram каналов
│   │   │   ├── __init__.py
│   │   │   └── channel_parser.py
│   │   └── websites/           # Парсеры сайтов
│   │       ├── __init__.py
│   │       ├── afisha.py
│   │       ├── eventbrite.py
│   │       └── timepad.py
│   │
│   ├── services/               # Сервисы
│   │   ├── __init__.py
│   │   ├── vector_search.py    # Поиск в векторной БД
│   │   ├── geolocation.py      # Геолокация и расстояния
│   │   ├── event_processor.py  # Обработка событий
│   │   └── scheduler.py        # Планировщик задач
│   │
│   ├── storage/                # Хранение данных
│   │   ├── __init__.py
│   │   ├── weaviate_client.py  # Клиент Weaviate
│   │   ├── user_storage.py     # Хранение пользователей
│   │   └── event_storage.py    # Хранение событий
│   │
│   ├── models/                 # Модели данных
│   │   ├── __init__.py
│   │   ├── event.py
│   │   ├── user.py
│   │   ├── channel.py
│   │   └── location.py
│   │
│   ├── config.py               # Конфигурация
│   └── utils/                  # Утилиты
│       ├── __init__.py
│       ├── logging.py
│       └── validators.py
│
├── scripts/                    # Скрипты
│   ├── add_events.py
│   ├── run_parser.py           # Запуск парсеров
│   └── run_bot.py              # Запуск бота
│
├── tests/                      # Тесты
│   ├── __init__.py
│   ├── test_parsers.py
│   ├── test_services.py
│   └── test_bot.py
│
├── docker-compose.yml
├── requirements.txt
├── .env.example
└── README.md
```

## Конфигурация

Все настройки вынесены в переменные окружения (см. `.env.example`):
- `TELEGRAM_BOT_TOKEN` - токен Telegram бота
- `TELEGRAM_API_ID` - API ID для Telegram (для парсинга каналов)
- `TELEGRAM_API_HASH` - API Hash для Telegram
- `WEAVIATE_URL` - URL Weaviate сервера
- `OPENAI_API_KEY` - ключ OpenAI (для векторизации, если используется)
- `GEOCODING_API_KEY` - ключ для геокодирования (Yandex/Google)

## Развертывание

1. Установить зависимости: `pip install -r requirements.txt`
2. Настроить переменные окружения в `.env`
3. Запустить Weaviate: `docker compose up -d`
4. Запустить парсеры: `python scripts/run_parser.py`
5. Запустить бота: `python scripts/run_bot.py`


