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