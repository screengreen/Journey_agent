<<<<<<< HEAD
# LLM-powered Weekend Planner
A personal **"weekend concierge"** powered by LLMs.

## About
The system collects local events from Telegram channels and aggregators, filters them based on user preferences, builds an optimal route, and adds selected activities to the user's calendar.

## Key Features
- Input: city + dates + preferences/budget → personalized weekend plan.
- Integrates with 3–5 Telegram channels and 1–2 event aggregators (MVP: one city).
- Smart routing using geography and event timing.
- Export to Google Calendar / ICS with title, time, address, and description.
- Short summaries and 1–3 historical facts for each location.

## MVP Architecture
- Interface: Telegram bot.
- Pipeline: data collection → LLM extraction → personalization → routing → text generation.

## Goals
- Increase user engagement in offline activities.
- Build a foundation for B2C monetization (subscriptions, partnerships).
- Demonstrate an LLM-agent orchestrating a real multi-step workflow.


### DATA 

## data acquisition
1) Via KudaGo open API collect data about events on 10 topics, data is already structured and splitted. Data is saved as json file and is transfered to vector db via scripts
2) Data From personal Telegram channels. For tests collected a small personal amount. In prod is collected individually. Data is saved as json file and is transfered to vector db via scripts

## Data storage
the data from KudaGo is stored in Json files and moved to Vector database. Later the data will be moved to vector db skipping json files part. As for personal data, it will follow same path as KudaGos data

## Link to Json file to see sample of data
link - 

## Data volume
KuddGos data - 2 (SPB and MOSCOW)*10 (topics)*100(amount of events from each topic) = 1000 samples of data
Personal data - 27 test samples


## Setup

```bash
pip install -r requirements.txt
```

Create `.env`: # from .env.example
```
TELEGRAM_APP_API_ID=your_api_id
TELEGRAM_APP_API_HASH=your_api_hash
OPENAI_API_KEY=your_openai_key
```

## Usage

### Telegram Parser

```python
from tg_parser import TelegramParser

async with TelegramParser() as parser:
    messages = await parser.get_channel_messages('https://t.me/s/channel', limit=10)
    saved = await parser.get_saved_messages(limit=20, text_only=True)
```

### Event Miner Agent

```python
from openai import OpenAI
from event_miner_agent import EventMinerAgent

llm = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
agent = EventMinerAgent(llm)

events = agent.process_messages(messages)  # messages: List[Message] or List[Dict]
```

### Full Example

```python
from tg_parser import TelegramParser
from event_miner_agent import EventMinerAgent
from openai import OpenAI

llm = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
agent = EventMinerAgent(llm)

async with TelegramParser() as parser:
    messages = await parser.get_saved_messages(limit=50, text_only=True)
    events = agent.process_messages(messages)
```
=======
# Journey_agent

## Быстрый запуск Weaviate

1. Установите Docker и Docker Compose (версия плагина `docker compose` 2.x или выше).
2. Поднимите сервис:

   ```bash
   docker compose up -d
   ```

3. Проверьте готовность базы: откройте `http://localhost:8080/v1/.well-known/ready` — сервер должен вернуть `{"status":"READY"}`.

`docker-compose.yml` разворачивает два контейнера:

- `contextionary` — модуль векторизации `text2vec-contextionary`, не требующий внешних API ключей;
- `weaviate` — сама векторная БД с открытым (анонимным) доступом и сохранением данных в volume `weaviate-data`.

Остановить кластер можно командой `docker compose down`, а удалить сохранённые данные — `docker compose down -v`.

## Замена contextionary на свой векторизатор

`contextionary` — это предобученная модель эмбеддингов, которую Weaviate использует в модуле `text2vec-contextionary`. Вы можете заменить её на свой векторизатор (например, OpenAI, Hugging Face или собственный сервис). Общий порядок действий:

1. Выберите модуль векторизации:
   - `text2vec-openai` — использует API OpenAI/compatible;
   - `text2vec-transformers` — подключается к self-hosted inference (Docker-образ `semitechnologies/transformers-inference` или любой HTTP сервис, который принимает текст и возвращает вектор);
   - другие модули перечислены в [документации Weaviate](https://weaviate.io/developers/weaviate/modules/retrieval).
2. Обновите `docker-compose.yml`:
   - удалите блок `contextionary` (если он больше не нужен) или добавьте свой сервис с моделью;
   - в сервисе `weaviate` поменяйте `ENABLE_MODULES` и `DEFAULT_VECTORIZER_MODULE` на выбранный модуль;
   - добавьте переменные, требуемые модулем (например, `OPENAI_APIKEY` или `TRANSFORMERS_INFERENCE_API`).
3. Пересоздайте контейнеры: `docker compose down && docker compose up -d`.
4. При смене векторизатора заново создайте коллекции, чтобы объекты были переиндексированы новыми векторами.

### Пример для собственного Hugging Face-инференса

```yaml
services:
  embeddings:
    image: semitechnologies/transformers-inference:sentence-transformers-multilingual-e5-large
    restart: unless-stopped
    environment:
      ENABLE_CUDA: "0"        # включите 1, если есть GPU
    expose:
      - "8080"

  weaviate:
    environment:
      ENABLE_MODULES: text2vec-transformers
      DEFAULT_VECTORIZER_MODULE: text2vec-transformers
      TRANSFORMERS_INFERENCE_API: http://embeddings:8080
```

### Пример для OpenAI/совместимого API

```yaml
  weaviate:
    environment:
      ENABLE_MODULES: text2vec-openai
      DEFAULT_VECTORIZER_MODULE: text2vec-openai
      OPENAI_APIKEY: ${OPENAI_APIKEY}
      OPENAI_APIKEY_PATH: ""   # если передаёте ключ через переменную
```

Для VLLM/собственных HTTP-сервисов настройка аналогична: главное — указать модуль и параметры подключения. После переключения векторизатора код клиента остаётся прежним, достаточно поменять `vectorizer_config` при создании коллекции на соответствующую функцию, например `wvc.config.Configure.Vectorizer.text2vec_openai()`.

## Скрипт для smoke-теста

В репозитории есть `scripts/test_weaviate.py`, который:

- проверяет готовность сервера Weaviate;
- пересоздаёт временную коллекцию;
- добавляет тестовые объекты и выполняет запрос `near_text`.

Запуск:

```bash
pip install "weaviate-client>=4.6,<5" requests
python scripts/test_weaviate.py
```

Переменные окружения:

- `WEAVIATE_URL` — адрес сервера (по умолчанию `http://localhost:8080`);
- `WEAVIATE_TEST_COLLECTION` — имя временной коллекции;
- `DROP_COLLECTION_AFTER_TEST` — установите в `0`, чтобы оставить коллекцию после теста.

## Работа с БД через Python‑клиент

1. Установите клиент:

   ```bash
   pip install "weaviate-client>=4.6,<5"
   ```

2. Выполните пример ниже (его можно сохранить в файл `examples/weaviate_demo.py` и запустить `python examples/weaviate_demo.py`):

```python
import weaviate
import weaviate.classes as wvc

client = weaviate.Client("http://localhost:8080")
collection_name = "Journeys"

# Удаляем коллекцию, если она уже существует
if collection_name in client.collections.list_all():
    client.collections.delete(collection_name)

# 1. Создание новой коллекции (схемы)
client.collections.create(
    name=collection_name,
    description="Путевые заметки и рекомендации",
    properties=[
        wvc.config.Property(
            name="title",
            description="Короткое название заметки",
            data_type=wvc.config.DataType.TEXT,
        ),
        wvc.config.Property(
            name="description",
            description="Развёрнутое описание маршрута",
            data_type=wvc.config.DataType.TEXT,
        ),
        wvc.config.Property(
            name="country",
            description="Страна, к которой относится заметка",
            data_type=wvc.config.DataType.TEXT,
        ),
    ],
    vectorizer_config=wvc.config.Configure.Vectorizer.text2vec_contextionary(),
)

collection = client.collections.get(collection_name)

# 2. Добавление объектов (batch ускоряет загрузку)
journeys = [
    {
        "title": "Сёрф-кэмп на Бали",
        "description": "Уютная деревня Чангу, уроки серфинга и коворкинги рядом с океаном.",
        "country": "Indonesia",
    },
    {
        "title": "Пеший тур в Доломитах",
        "description": "Маршрут по хребту Тре-Чиме с ночёвками в rifugio и рассветами в горах.",
        "country": "Italy",
    },
    {
        "title": "Зимний Саппоро",
        "description": "Фестиваль снежных скульптур и поездки на горячие источники Хоккайдо.",
        "country": "Japan",
    },
]

with collection.batch.dynamic() as batch:
    for journey in journeys:
        batch.add_object(properties=journey)

# 3. Поиск по похожести текста
result = collection.query.near_text(
    query="тёплый океан, сёрф и коворкинг",
    limit=2,
    return_metadata=wvc.query.MetadataQuery(distance=True),
)

for obj in result.objects:
    print(f"{obj.properties['title']} ({obj.properties['country']}) — distance={obj.metadata.distance:.3f}")

client.close()
```

В примере показаны три базовые операции:

- создание коллекции (схемы) с текстовыми полями;
- добавление записей батчем;
- семантический поиск `near_text`, возвращающий объекты, близкие к пользовательскому запросу.

Аналогичным образом можно добавлять числовые, гео- и мультимедийные свойства или комбинировать `near_vector`, фильтры и сортировки — см. официальную документацию Weaviate для расширенных сценариев.
>>>>>>> feature/vdb
