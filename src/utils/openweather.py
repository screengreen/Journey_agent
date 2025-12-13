from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, Any

import requests


@dataclass
class Weather:
    description: str
    temperature: float
    feels_like: float
    humidity: int
    wind_speed: float
    raw: Dict[str, Any]


class OpenWeatherClient:
    """
    Клиент для получения погоды по координатам через OpenWeather.
    API-ключ загружается из OPENWEATHER_API_KEY.
    """

    BASE_URL = "https://api.openweathermap.org/data/2.5/weather"

    def __init__(self, timeout: int = 10):
        api_key = os.getenv("OPENWEATHER_API_KEY")
        if not api_key:
            raise RuntimeError(
                "Переменная окружения OPENWEATHER_API_KEY не найдена. "
                "Проверь .env или окружение."
            )
        self.api_key = api_key
        self.timeout = timeout

    def get_weather(self, lat: float, lon: float, units: str = "metric") -> Weather:
        """
        Возвращает текущую погоду для точки.
        """

        params = {
            "lat": lat,
            "lon": lon,
            "appid": self.api_key,
            "units": units,
        }

        resp = requests.get(self.BASE_URL, params=params, timeout=self.timeout)

        try:
            resp.raise_for_status()
        except requests.HTTPError as e:
            raise RuntimeError(
                f"Ошибка при обращении к OpenWeather: {e}\n"
                f"URL: {resp.url}\n"
                f"Ответ: {resp.text}"
            )

        data = resp.json()

        weather_list = data.get("weather") or []
        if not weather_list:
            raise ValueError("Некорректный ответ OpenWeather: нет поля 'weather'")

        weather_desc = weather_list[0].get("description", "")

        main = data.get("main") or {}
        wind = data.get("wind") or {}

        return Weather(
            description=weather_desc,
            temperature=main.get("temp"),
            feels_like=main.get("feels_like"),
            humidity=main.get("humidity"),
            wind_speed=wind.get("speed"),
            raw=data,
        )
