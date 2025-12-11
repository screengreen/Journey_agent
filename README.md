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

---

## Получение API-ключа Yandex Geocoder

Документ описывает процесс получения токена (**apikey**) для работы с **Yandex Geocoder HTTP API**.

### 1. Войти в аккаунт Яндекса

Перейдите на страницу любого сервиса Яндекса, например:
https://yandex.ru

Выполните вход.

![Вход в Яндекс](https://drive.google.com/uc?export=view&id=1Kf05RUGFgpDaY2_aedOCzvuXmd8IyPSY)

### 2. Открыть кабинет разработчика Yandex Maps API

Откройте официальный кабинет разработчика:

**https://developer.tech.yandex.ru**

![Кабинет разработчика](https://drive.google.com/uc?export=view&id=1fHEKdiBhJqsZSJTiFZ2xc6-9WCYO78LU)

### 3. Нажать «Получить ключ» / «Подключить API»

На главной странице нажмите:

- **«Получить ключ»**  
- или **«Подключить API»**

![Получить ключ](https://drive.google.com/uc?export=view&id=1KMd6ohWFQGz3gFhRHIlzppWLT8bnO3RS)

### 4. Выбрать пакет с Geocoder HTTP API

Выберите пакет:

**JavaScript API и HTTP Геокодер (Geocoder HTTP API)**

Документация по API:
https://yandex.ru/dev/maps/jsapi  
https://yandex.ru/dev/geocode  

![Выбор API](https://drive.google.com/uc?export=view&id=1m2Y5bIFwM3pNHHdkHYOYQjBew2bfitTp)

### 5. Заполнить форму подключения

Укажите:

- название проекта  
- email  
- назначение API  
- при необходимости домен  

Поставьте все необходимые галочки.

Условия использования API:  
https://yandex.ru/legal/maps_termsofuse/

![Форма подключения](https://drive.google.com/uc?export=view&id=1UmZWPuiXRCAuc3vGCBBHJHHcn_dnXsV2)

### 6. Получить API-ключ

После создания ключ появится в разделе:

**Мои ключи → API keys**

![Список ключей](https://drive.google.com/uc?export=view&id=1Z1btXG2EX82SGaffafmbCaQbvFPtdwvK)

Скопируйте ключ — это ваш **YANDEX_GEOCODER_API_KEY**.

### 7. Проверить работу ключа (опционально)

Пример проверки Geocoder API:

```bash
curl "https://geocode-maps.yandex.ru/1.x/?apikey=ВАШ_API_KEY&geocode=Москва,+Красная+площадь&format=json"
```
