"""
Инструменты для агентов (погода, карты, веб-поиск).
"""
import sys
from pathlib import Path

# Добавляем путь к main для импорта
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.openweather import OpenWeatherClient  
from src.utils.maps import YandexGeocoder, YandexRouteService
from src.utils.websearch import TavilyHtmlFetcher
from typing import Dict, Any, List, Optional
from langchain_core.tools import tool
from bs4 import BeautifulSoup


# Инициализация клиентов
_weather_client: Optional[OpenWeatherClient] = None
_geocoder: Optional[YandexGeocoder] = None
_route_service: Optional[YandexRouteService] = None
_web_fetcher: Optional[TavilyHtmlFetcher] = None


def _get_weather_client() -> OpenWeatherClient:
    """Ленивая инициализация клиента погоды."""
    global _weather_client
    if _weather_client is None:
        _weather_client = OpenWeatherClient()
    return _weather_client


def _get_geocoder() -> YandexGeocoder:
    """Ленивая инициализация геокодера."""
    global _geocoder
    if _geocoder is None:
        _geocoder = YandexGeocoder()
    return _geocoder


def _get_route_service() -> YandexRouteService:
    """Ленивая инициализация сервиса маршрутов."""
    global _route_service
    if _route_service is None:
        _route_service = YandexRouteService(geocoder=_get_geocoder())
    return _route_service


def _get_web_fetcher() -> TavilyHtmlFetcher:
    """Ленивая инициализация веб-поиска."""
    global _web_fetcher
    if _web_fetcher is None:
        _web_fetcher = TavilyHtmlFetcher()
    return _web_fetcher


def _get_weather_impl(lat: float, lon: float) -> Dict[str, Any]:
    """Внутренняя реализация получения погоды по координатам."""
    weather = _get_weather_client().get_weather(lat, lon)
    return {
        "description": weather.description,
        "temperature": weather.temperature,
        "feels_like": weather.feels_like,
        "humidity": weather.humidity,
        "wind_speed": weather.wind_speed,
        "success": True
    }


@tool
def get_weather(lat: float, lon: float) -> Dict[str, Any]:
    """
    Получить текущую погоду по координатам.
    
    Args:
        lat: Широта
        lon: Долгота
    
    Returns:
        Словарь с информацией о погоде
    """
    try:
        return _get_weather_impl(lat, lon)
    except Exception as e:
        return {"success": False, "error": str(e)}


def _get_weather_by_address_impl(address: str) -> Dict[str, Any]:
    """Внутренняя реализация получения погоды по адресу."""
    geocoder = _get_geocoder()
    point = geocoder.adress_to_geopoint(address)
    if point is None:
        raise ValueError(f"Не удалось найти координаты для адреса: {address}")
    lon, lat = point
    weather = _get_weather_client().get_weather(lat, lon)
    return {
        "address": address,
        "coordinates": {"lat": lat, "lon": lon},
        "description": weather.description,
        "temperature": weather.temperature,
        "feels_like": weather.feels_like,
        "humidity": weather.humidity,
        "wind_speed": weather.wind_speed,
        "success": True
    }


@tool
def get_weather_by_address(address: str) -> Dict[str, Any]:
    """
    Получить текущую погоду по адресу.
    
    Args:
        address: Адрес места
    
    Returns:
        Словарь с информацией о погоде и координатами
    """
    try:
        return _get_weather_by_address_impl(address)
    except Exception as e:
        return {"success": False, "error": str(e)}


def _get_route_info_impl(from_address: str, to_address: str, modes: Optional[List[str]] = None) -> Dict[str, Any]:
    """Внутренняя реализация получения маршрута."""
    route_service = _get_route_service()
    modes_tuple = tuple(modes) if modes else ("walking", "car", "bus")
    route_info = route_service.route_by_addresses(from_address, to_address, modes=modes_tuple)
    return {
        "success": True,
        "from_address": route_info.get("from_address"),
        "to_address": route_info.get("to_address"),
        "distance_km_straight": route_info.get("distance_km_straight"),
        "modes": route_info.get("modes", {})
    }


@tool
def get_route_info(from_address: str, to_address: str, modes: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Получить информацию о маршруте между двумя адресами.
    
    Args:
        from_address: Адрес начала маршрута
        to_address: Адрес конца маршрута
        modes: Список режимов транспорта (walking, car, bus). По умолчанию все.
    
    Returns:
        Словарь с информацией о маршруте
    """
    try:
        return _get_route_info_impl(from_address, to_address, modes)
    except Exception as e:
        return {"success": False, "error": str(e)}


def _search_web_impl(query: str, max_results: int = 5) -> Dict[str, Any]:
    """Внутренняя реализация веб-поиска."""
    from bs4 import BeautifulSoup
    fetcher = _get_web_fetcher()
    pages = fetcher.search(query, max_results=max_results)
    results = [{"url": p.url, "title": p.title, "text_preview": BeautifulSoup(p.html, 'html.parser').get_text()[:1000]} for p in pages]
    return {"success": True, "query": query, "results": results, "count": len(results)}


@tool
def search_web(query: str, max_results: int = 5) -> Dict[str, Any]:
    """
    Поиск информации в интернете.
    
    Args:
        query: Поисковый запрос
        max_results: Максимальное количество результатов
    
    Returns:
        Словарь с результатами поиска
    """
    try:
        return _search_web_impl(query, max_results)
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_all_tools():
    """Получить все инструменты для агентов."""
    return [
        get_weather,
        get_weather_by_address,
        get_route_info,
        search_web
    ]

