import os
import math
from dataclasses import dataclass, field
from typing import Dict, Tuple, Literal, Optional

import requests


GeoPoint = Tuple[float, float]
Mode = Literal["walking", "car", "bus"]


def haversine_distance_m(p1: GeoPoint, p2: GeoPoint) -> float:
    """
    Геодезическое расстояние между двумя точками на сфере (Земля) в метрах.
    p1, p2: (lon, lat) в градусах, WGS84.
    """
    lon1, lat1 = p1
    lon2, lat2 = p2

    lon1_rad, lat1_rad = math.radians(lon1), math.radians(lat1)
    lon2_rad, lat2_rad = math.radians(lon2), math.radians(lat2)

    dlon = lon2_rad - lon1_rad
    dlat = lat2_rad - lat1_rad

    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.asin(math.sqrt(a))

    R = 6371000  # радиус Земли, м
    return R * c


@dataclass
class YandexGeocoder:
    geocoder_url: str = "https://geocode-maps.yandex.ru/1.x"

    def adress_to_geopoint(self, address: str) -> Optional[GeoPoint]:
        """
        Преобразование адреса в геокоординаты.
        Возвращает (lon, lat) или None, если адрес не найден.
        """
        api_key = os.getenv("YANDEX_GEOCODER_API_KEY")
        if not api_key:
            raise ValueError("YANDEX_GEOCODER_API_KEY не установлен в переменных окружения")
        
        try:
            resp = requests.get(
                self.geocoder_url,
                params={
                    "apikey": api_key,
                    "geocode": address,
                    "format": "json",
                },
                timeout=10,
            )
            resp.raise_for_status()

            members = resp.json()["response"]["GeoObjectCollection"]["featureMember"]
            if not members:
                return None

            pos = members[0]["GeoObject"]["Point"]["pos"]
            lon_str, lat_str = pos.split(" ")

            return float(lon_str), float(lat_str)
        except requests.exceptions.HTTPError as e:
            error_msg = f"HTTP ошибка {e.response.status_code}"
            try:
                error_detail = e.response.json()
                if "error" in error_detail:
                    error_msg += f": {error_detail['error']}"
            except:
                error_msg += f": {e.response.text[:200]}"
            raise ValueError(error_msg) from e
        except requests.exceptions.RequestException as e:
            raise ValueError(f"Ошибка запроса к геокодеру: {str(e)}") from e
    

@dataclass
class SimpleRouteEstimator:
    """
    Простейший "роутер":
    1. Считает геодезическое расстояние по прямой (haversine).
    2. Умножает на коэффициент "дорожности" для каждого режима.
    3. Делит на среднюю скорость → получает примерное время в пути.
    """

    # Средние скорости (км/ч)
    speeds_kmh: Dict[Mode, float] = field(
        default_factory=lambda: {
            "walking": 5.0,   # средняя скорость пешехода
            "car": 40.0,      # средняя скорость авто в городе
            "bus": 25.0,      # условная средняя скорость автобуса
        }
    )

    # Во сколько раз реальный путь длиннее прямой
    road_coefficients: Dict[Mode, float] = field(
        default_factory=lambda: {
            "walking": 1.75,
            "car": 1.8,
            "bus": 2,
        }
    )

    def estimate_route(
        self,
        start: GeoPoint,
        end: GeoPoint,
        modes: Tuple[Mode, ...] = ("walking", "car", "bus"),
    ) -> Dict[str, object]:
        """
        start, end: (lon, lat)
        modes: режимы, для которых хотим посчитать маршрут.

        Возвращает:
        {
          "distance_m_straight": float,
          "distance_km_straight": float,
          "modes": {
             "walking": {
                "distance_m": float,
                "distance_km": float,
                "duration_h": float,
                "duration_min": float,
                "speed_kmh": float,
                "road_coefficient": float,
             },
             ...
          }
        }
        """
        straight_m = haversine_distance_m(start, end)
        straight_km = straight_m / 1000.0

        result: Dict[str, object] = {
            "distance_m_straight": straight_m,
            "distance_km_straight": straight_km,
            "modes": {},
        }

        modes_result: Dict[str, dict] = {}

        for mode in modes:
            speed_kmh = self.speeds_kmh[mode]
            coeff = self.road_coefficients[mode]

            # Оценка реального расстояния
            distance_m = straight_m * coeff
            distance_km = distance_m / 1000.0

            # Время = расстояние / скорость
            duration_hours = distance_km / speed_kmh
            duration_min = duration_hours * 60.0

            modes_result[mode] = {
                "distance_m": distance_m,
                "distance_km": distance_km,
                "duration_h": duration_hours,
                "duration_min": duration_min,
                "speed_kmh": speed_kmh,
                "road_coefficient": coeff,
            }

        result["modes"] = modes_result
        return result


@dataclass
class YandexRouteService:
    geocoder: YandexGeocoder
    estimator: SimpleRouteEstimator = field(default_factory=SimpleRouteEstimator)

    def route_by_addresses(
        self,
        from_address: str,
        to_address: str,
        modes: Tuple[Mode, ...] = ("walking", "car", "bus"),
    ) -> Dict[str, object]:
        """
        Высокоуровневый метод:
        1) Геокодит оба адреса.
        2) Считает расстояние и время для указанных режимов.

        Возвращает dict с метаданными + результатом estimate_route.
        """
        start = self.geocoder.adress_to_geopoint(from_address)
        end = self.geocoder.adress_to_geopoint(to_address)

        if start is None or end is None:
            raise ValueError("Не удалось получить координаты одного из адресов")

        route_info = self.estimator.estimate_route(start, end, modes=modes)

        route_info.update(
            {
                "from_address": from_address,
                "to_address": to_address,
                "from_point": start,
                "to_point": end,
            }
        )

        return route_info
