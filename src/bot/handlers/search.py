"""Обработчики для поиска событий."""

import logging
import re
from typing import Optional

from telegram import Update
from telegram.ext import ContextTypes, MessageHandler, filters

from src.bot.keyboards import get_main_keyboard, get_event_keyboard
from src.services.geolocation import GeolocationService
from src.services.vector_search import VectorSearchService
from src.storage.user_storage import UserStorage

logger = logging.getLogger(__name__)


async def handle_search_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик поисковых запросов."""
    user = update.effective_user
    query = update.message.text
    user_storage: UserStorage = context.bot_data["user_storage"]
    vector_search: VectorSearchService = context.bot_data["vector_search"]
    geolocation: GeolocationService = context.bot_data["geolocation"]

    # Показываем, что обрабатываем запрос
    await update.message.reply_text("🔍 Ищу события...")

    # Получаем пользователя
    db_user = user_storage.get_user(user.id)
    if not db_user:
        await update.message.reply_text(
            "❌ Ошибка: пользователь не найден. Используй /start",
            reply_markup=get_main_keyboard(),
        )
        return

    # Извлекаем локацию из запроса или используем сохраненную
    user_lat, user_lon = extract_user_location(query, db_user, geolocation)

    if not user_lat or not user_lon:
        await update.message.reply_text(
            "📍 Для поиска ближайших событий нужно установить локацию.\n\n"
            "Используй кнопку '📍 Установить локацию' или укажи город в запросе.",
            reply_markup=get_main_keyboard(),
        )
        return

    # Выполняем поиск
    user_tag = f"user{user.id}"
    events = vector_search.search(query=query, user_tag=user_tag, limit=10)

    if not events:
        await update.message.reply_text(
            "😔 События не найдены.\n\n"
            "Попробуй изменить запрос или добавь каналы с событиями.",
            reply_markup=get_main_keyboard(),
        )
        return

    # Сортируем по расстоянию
    sorted_events = geolocation.sort_events_by_distance(events, user_lat, user_lon)

    # Отправляем результаты
    events_with_distances = geolocation.add_distances_to_events(
        sorted_events[:5], user_lat, user_lon
    )

    message = f"✅ Найдено {len(sorted_events)} событий. Ближайшие:\n\n"
    for i, (event, distance) in enumerate(events_with_distances[:5], 1):
        message += f"**{i}. {event.title}**\n"
        if event.description:
            desc = event.description[:100] + "..." if len(event.description) > 100 else event.description
            message += f"   {desc}\n"
        if event.location:
            message += f"   📍 {event.location}\n"
        if distance != float("inf"):
            message += f"   📏 {distance:.1f} км\n"
        if event.date:
            message += f"   📅 {event.date}\n"
        message += "\n"

    await update.message.reply_text(
        message,
        reply_markup=get_main_keyboard(),
        parse_mode="Markdown",
    )

    # Отправляем детали для ближайшего события
    if events_with_distances:
        nearest_event, distance = events_with_distances[0]
        detail_message = f"🎯 **Ближайшее событие:**\n\n"
        detail_message += f"**{nearest_event.title}**\n\n"
        if nearest_event.description:
            detail_message += f"{nearest_event.description}\n\n"
        if nearest_event.location:
            detail_message += f"📍 {nearest_event.location}\n"
        if distance != float("inf"):
            detail_message += f"📏 Расстояние: {distance:.1f} км\n"
        if nearest_event.date:
            detail_message += f"📅 {nearest_event.date}\n"
        if nearest_event.url:
            detail_message += f"🔗 {nearest_event.url}"

        keyboard = get_event_keyboard(nearest_event.url) if nearest_event.url else None
        await update.message.reply_text(
            detail_message,
            reply_markup=keyboard,
            parse_mode="Markdown",
        )


async def handle_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик геолокации пользователя."""
    user = update.effective_user
    location = update.message.location
    user_storage: UserStorage = context.bot_data["user_storage"]

    # Получаем пользователя
    db_user = user_storage.get_user(user.id)
    if not db_user:
        db_user = User(user_id=user.id, username=user.username, first_name=user.first_name)
        user_storage.save_user(db_user)

    # Обновляем локацию
    db_user.latitude = location.latitude
    db_user.longitude = location.longitude
    user_storage.save_user(db_user)

    logger.info(f"Пользователь {user.id} установил локацию: {location.latitude}, {location.longitude}")

    await update.message.reply_text(
        "✅ Локация сохранена!\n\nТеперь я смогу находить ближайшие события.",
        reply_markup=get_main_keyboard(),
    )


def extract_user_location(query: str, user, geolocation: GeolocationService) -> tuple[Optional[float], Optional[float]]:
    """
    Извлекает локацию пользователя из запроса или использует сохраненную.

    Args:
        query: Поисковый запрос
        user: Пользователь из БД
        geolocation: Сервис геолокации

    Returns:
        Кортеж (широта, долгота) или (None, None)
    """
    # Если у пользователя есть сохраненная локация, используем её
    if user.latitude and user.longitude:
        return user.latitude, user.longitude

    # Пытаемся извлечь город из запроса
    cities = {
        "москва": (55.7558, 37.6173),
        "санкт-петербург": (59.9343, 30.3351),
        "питер": (59.9343, 30.3351),
        "спб": (59.9343, 30.3351),
    }

    query_lower = query.lower()
    for city, coords in cities.items():
        if city in query_lower:
            return coords

    # Пытаемся геокодировать запрос
    # TODO: Более умное извлечение локации из запроса

    return None, None


def register_search_handlers(application):
    """
    Регистрирует обработчики для поиска.

    Args:
        application: Application из python-telegram-bot
    """
    # Обработчик текстовых сообщений (поисковые запросы)
    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND & ~filters.Regex(r"(t\.me|telegram\.me|@)"),
            handle_search_query,
        )
    )

    # Обработчик геолокации
    application.add_handler(MessageHandler(filters.LOCATION, handle_location))

