"""Обработчики для работы с каналами."""

import logging
import re
from typing import Optional

from telegram import Update
from telegram.ext import ContextTypes, MessageHandler, filters

from src.bot.keyboards import get_main_keyboard
from src.models.channel import Channel
from src.storage.user_storage import UserStorage

logger = logging.getLogger(__name__)


async def handle_channel_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик сообщений с каналами."""
    user = update.effective_user
    text = update.message.text
    user_storage: UserStorage = context.bot_data["user_storage"]

    # Извлекаем канал из текста
    channel_id = extract_channel_id(text)
    if not channel_id:
        await update.message.reply_text(
            "❌ Не удалось распознать канал.\n\n"
            "Отправь ссылку на канал (например, https://t.me/channel или @channel)",
            reply_markup=get_main_keyboard(),
        )
        return

    # Проверяем, не добавлен ли уже канал
    existing_channel = user_storage.get_channel(channel_id)
    if existing_channel and existing_channel.user_id == user.id:
        await update.message.reply_text(
            f"ℹ️ Канал {channel_id} уже добавлен.",
            reply_markup=get_main_keyboard(),
        )
        return

    # Создаем канал
    channel = Channel(
        channel_id=channel_id,
        user_id=user.id,
        title=None,  # Будет заполнено при парсинге
    )

    user_storage.add_channel(channel)
    logger.info(f"Пользователь {user.id} добавил канал {channel_id}")

    await update.message.reply_text(
        f"✅ Канал {channel_id} успешно добавлен!\n\n"
        "События из этого канала будут автоматически парситься и добавляться в базу.",
        reply_markup=get_main_keyboard(),
    )


def extract_channel_id(text: str) -> Optional[str]:
    """
    Извлекает ID канала из текста.

    Args:
        text: Текст сообщения

    Returns:
        ID канала или None
    """
    # Паттерны для Telegram каналов
    patterns = [
        r"t\.me/([a-zA-Z0-9_]+)",  # t.me/channel
        r"telegram\.me/([a-zA-Z0-9_]+)",  # telegram.me/channel
        r"@([a-zA-Z0-9_]+)",  # @channel
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1)

    return None


def register_channel_handlers(application):
    """
    Регистрирует обработчики для работы с каналами.

    Args:
        application: Application из python-telegram-bot
    """
    # Обработчик текстовых сообщений с каналами
    # Срабатывает, когда пользователь нажимает "➕ Добавить канал"
    application.add_handler(
        MessageHandler(
            filters.TEXT & filters.Regex(r"(t\.me|telegram\.me|@)"),
            handle_channel_message,
        )
    )

