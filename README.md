# Journey_agent
# Получение API-ключа Yandex Geocoder

Документ описывает процесс получения токена (**apikey**) для работы с **Yandex Geocoder HTTP API**.

---

## 1. Войти в аккаунт Яндекса

Перейдите на страницу любого сервиса Яндекса, например:
https://yandex.ru

Выполните вход.

![Вход в Яндекс](https://drive.google.com/uc?export=view&id=1Kf05RUGFgpDaY2_aedOCzvuXmd8IyPSY)

---

## 2. Открыть кабинет разработчика Yandex Maps API

Откройте официальный кабинет разработчика:

**https://developer.tech.yandex.ru**

![Кабинет разработчика](https://drive.google.com/uc?export=view&id=1fHEKdiBhJqsZSJTiFZ2xc6-9WCYO78LU)

---

## 3. Нажать «Получить ключ» / «Подключить API»

На главной странице нажмите:

- **«Получить ключ»**  
- или **«Подключить API»**

![Получить ключ](https://drive.google.com/uc?export=view&id=1KMd6ohWFQGz3gFhRHIlzppWLT8bnO3RS)

---

## 4. Выбрать пакет с Geocoder HTTP API

Выберите пакет:

**JavaScript API и HTTP Геокодер (Geocoder HTTP API)**

Документация по API:
https://yandex.ru/dev/maps/jsapi  
https://yandex.ru/dev/geocode  

![Выбор API](https://drive.google.com/uc?export=view&id=1m2Y5bIFwM3pNHHdkHYOYQjBew2bfitTp)

---

## 5. Заполнить форму подключения

Укажите:

- название проекта  
- email  
- назначение API  
- при необходимости домен  

Поставьте все необходимые галочки.

Условия использования API:  
https://yandex.ru/legal/maps_termsofuse/

![Форма подключения](https://drive.google.com/uc?export=view&id=1UmZWPuiXRCAuc3vGCBBHJHHcn_dnXsV2)

---

## 6. Получить API-ключ

После создания ключ появится в разделе:

**Мои ключи → API keys**

![Список ключей](https://drive.google.com/uc?export=view&id=1Z1btXG2EX82SGaffafmbCaQbvFPtdwvK)

Скопируйте ключ — это ваш **YANDEX_GEOCODER_API_KEY**.

---

## 7. Проверить работу ключа (опционально)

Пример проверки Geocoder API:

```bash
curl "https://geocode-maps.yandex.ru/1.x/?apikey=ВАШ_API_KEY&geocode=Москва,+Красная+площадь&format=json"

