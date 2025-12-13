# Sync Worker API

FastAPI приложение для управления синхронизацией Telegram каналов с векторной базой данных Weaviate.

## Возможности

API предоставляет следующие эндпоинты:

### Health Check
- `GET /` - Корневой эндпоинт, информация о сервисе
- `GET /health` - Проверка работоспособности сервиса

### База данных
- `GET /database` - Получить полную информацию о БД (статистика, все каналы, последние синхронизации)

### Управление каналами
- `GET /channels` - Получить список всех каналов (параметр `active_only` для фильтрации)
- `GET /channels/user/{username}` - Получить каналы конкретного пользователя
- `POST /channels` - Добавить новый канал

### Синхронизация
- `POST /sync/trigger` - Запустить синхронизацию вне очереди
- `GET /sync/status` - Получить статус текущей синхронизации

## Запуск

### С помощью Docker Compose

Запустить только API сервис:

```bash
docker-compose up api
```

Это автоматически запустит также необходимые зависимости (Weaviate и Contextionary).

### Локально (для разработки)

```bash
# Установить зависимости
pip install fastapi uvicorn[standard] pydantic

# Запустить сервер
uvicorn src.sync_worker.api:app --reload --host 0.0.0.0 --port 8000
```

## Использование

После запуска API будет доступен на `http://localhost:8000`

### Документация

FastAPI автоматически генерирует интерактивную документацию:

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### Примеры запросов

#### Получить информацию о базе данных

```bash
curl http://localhost:8000/database
```

#### Получить каналы пользователя

```bash
curl http://localhost:8000/channels/user/user_test_1
```

#### Получить все активные каналы

```bash
curl "http://localhost:8000/channels?active_only=true"
```

#### Добавить новый канал

```bash
curl -X POST http://localhost:8000/channels \
  -H "Content-Type: application/json" \
  -d '{
    "username": "my_user",
    "channel_url": "https://t.me/mychannel",
    "is_active": true
  }'
```

#### Запустить синхронизацию вне очереди

```bash
curl -X POST http://localhost:8000/sync/trigger
```

#### Проверить статус синхронизации

```bash
curl http://localhost:8000/sync/status
```

## Переменные окружения

Настройки берутся из тех же переменных окружения, что и основной sync-worker:

- `JOURNEY_AGENT_DB_PATH` - путь к SQLite базе данных (по умолчанию: `data/channels_db/users_channels.db`)
- `CHANNEL_SYNC_INTERVAL_HOURS` - интервал синхронизации в часах (по умолчанию: `6`)
- `CHANNEL_MESSAGES_LIMIT` - лимит сообщений для парсинга (по умолчанию: `10`)
- `WEAVIATE_URL` - URL Weaviate сервера (по умолчанию: `http://localhost:8080`)
- `JOURNEY_AGENT_SEED_TEST_CHANNELS` - добавить тестовые каналы при старте (по умолчанию: `true`)
- `TELEGRAM_APP_API_ID` - API ID Telegram приложения
- `TELEGRAM_APP_API_HASH` - API Hash Telegram приложения
- `OPENAI_API_KEY` - API ключ OpenAI для обработки событий

## Архитектура

API использует следующие компоненты:

- **FastAPI** - веб-фреймворк
- **SQLite** - база данных для хранения информации о каналах
- **Weaviate** - векторная база данных для хранения событий
- **Telethon** - библиотека для работы с Telegram API
- **EventMinerAgent** - агент для извлечения событий из сообщений

## Особенности

- Синхронизация запускается в фоновой задаче, не блокируя API
- Защита от одновременного запуска нескольких синхронизаций
- Автоматическая инициализация базы данных при старте
- Интерактивная документация через Swagger UI
- Поддержка фильтрации и поиска каналов

