"""Сервис для геолокации и расчета расстояний."""

import os
from typing import List, Optional, Tuple

from geopy.distance import geodesic
from geopy.geocoders import Nominatim, Yandex

from src.models.event import Event
from src.models.location import Location


class GeolocationService:
    """Сервис для работы с геолокацией."""

    def __init__(self):
        """Инициализация сервиса геолокации."""
        # Используем Yandex Geocoder, если есть API ключ, иначе Nominatim
        yandex_api_key = os.getenv("YANDEX_GEOCODING_API_KEY")
        if yandex_api_key:
            self.geocoder = Yandex(api_key=yandex_api_key)
        else:
            self.geocoder = Nominatim(user_agent="journey_agent")

    def geocode(self, address: str) -> Optional[Location]:
        """
        Геокодирует адрес в координаты.

        Args:
            address: Адрес для геокодирования

        Returns:
            Location с координатами или None, если не удалось найти
        """
        try:
            location_data = self.geocoder.geocode(address, timeout=10)
            if location_data:
                return Location(
                    address=address,
                    latitude=location_data.latitude,
                    longitude=location_data.longitude,
                    city=self._extract_city(location_data),
                    country=self._extract_country(location_data),
                )
        except Exception as e:
            print(f"Ошибка геокодирования адреса '{address}': {e}")
        return None

    def calculate_distance(
        self, lat1: float, lon1: float, lat2: float, lon2: float
    ) -> float:
        """
        Вычисляет расстояние между двумя точками в километрах.

        Args:
            lat1: Широта первой точки
            lon1: Долгота первой точки
            lat2: Широта второй точки
            lon2: Долгота второй точки

        Returns:
            Расстояние в километрах
        """
        point1 = (lat1, lon1)
        point2 = (lat2, lon2)
        return geodesic(point1, point2).kilometers

    def add_distances_to_events(
        self, events: List[Event], user_lat: float, user_lon: float
    ) -> List[Tuple[Event, float]]:
        """
        Добавляет расстояния от пользователя до событий.

        Args:
            events: Список событий
            user_lat: Широта пользователя
            user_lon: Долгота пользователя

        Returns:
            Список кортежей (событие, расстояние в км)
        """
        events_with_distances = []

        for event in events:
            if event.latitude and event.longitude:
                distance = self.calculate_distance(
                    user_lat, user_lon, event.latitude, event.longitude
                )
                events_with_distances.append((event, distance))
            else:
                # Если координат нет, пытаемся геокодировать адрес
                if event.location:
                    location = self.geocode(event.location)
                    if location:
                        event.latitude = location.latitude
                        event.longitude = location.longitude
                        distance = self.calculate_distance(
                            user_lat, user_lon, location.latitude, location.longitude
                        )
                        events_with_distances.append((event, distance))
                    else:
                        # Если не удалось геокодировать, добавляем с большим расстоянием
                        events_with_distances.append((event, float("inf")))
                else:
                    events_with_distances.append((event, float("inf")))

        return events_with_distances

    def sort_events_by_distance(
        self, events: List[Event], user_lat: float, user_lon: float
    ) -> List[Event]:
        """
        Сортирует события по расстоянию от пользователя.

        Args:
            events: Список событий
            user_lat: Широта пользователя
            user_lon: Долгота пользователя

        Returns:
            Отсортированный список событий (ближайшие первыми)
        """
        events_with_distances = self.add_distances_to_events(events, user_lat, user_lon)
        events_with_distances.sort(key=lambda x: x[1])  # Сортируем по расстоянию
        return [event for event, _ in events_with_distances]

    def _extract_city(self, location_data) -> Optional[str]:
        """Извлекает город из данных геокодирования."""
        if hasattr(location_data, "raw") and isinstance(location_data.raw, dict):
            address = location_data.raw.get("address", {})
            return address.get("city") or address.get("town") or address.get("village")
        return None

    def _extract_country(self, location_data) -> Optional[str]:
        """Извлекает страну из данных геокодирования."""
        if hasattr(location_data, "raw") and isinstance(location_data.raw, dict):
            address = location_data.raw.get("address", {})
            return address.get("country")
        return None


