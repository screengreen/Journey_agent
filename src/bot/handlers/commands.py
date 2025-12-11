"""Обработчики команд бота."""

import logging

from telegram import Update
from telegram.ext import ContextTypes

from src.bot.keyboards import get_main_keyboard, get_location_keyboard
from src.models.user import User
from src.storage.user_storage import UserStorage

logger = logging.getLogger(__name__)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start."""
    user = update.effective_user
    user_storage: UserStorage = context.bot_data["user_storage"]

    # Создаем или обновляем пользователя
    db_user = user_storage.get_user(user.id)
    if not db_user:
        db_user = User(
            user_id=user.id,
            username=user.username,
            first_name=user.first_name,
        )
        user_storage.save_user(db_user)
        logger.info(f"Новый пользователь: {user.id} (@{user.username})")

    welcome_message = (
        f"Привет, {user.first_name}! 👋\n\n"
        "Я помогу тебе найти интересные события рядом с тобой.\n\n"
        "Что я умею:\n"
        "• 🔍 Искать события по запросу (например, 'концерт в Москве')\n"
        "• 📋 Парсить события из твоих Telegram каналов\n"
        "• 📍 Показывать ближайшие события с учетом твоей локации\n\n"
        "Начни с установки локации или добавления каналов!"
    )

    await update.message.reply_text(
        welcome_message, reply_markup=get_main_keyboard()
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /help."""
    help_text = (
        "📖 Справка по использованию бота:\n\n"
        "🔍 **Поиск событий**\n"
        "Просто напиши, что хочешь найти. Например:\n"
        "• 'концерт в Москве'\n"
        "• 'выставка рядом со мной'\n"
        "• 'фестиваль в Санкт-Петербурге'\n\n"
        "➕ **Добавление каналов**\n"
        "Отправь ссылку на Telegram канал или @username.\n"
        "Бот будет автоматически парсить события из этих каналов.\n\n"
        "📍 **Установка локации**\n"
        "Используй кнопку 'Установить локацию' для отправки своей геолокации.\n"
        "Это поможет находить ближайшие события.\n\n"
        "📋 **Мои каналы**\n"
        "Просмотр всех добавленных каналов.\n\n"
        "Команды:\n"
        "/start - начать работу\n"
        "/help - эта справка"
    )

    await update.message.reply_text(help_text, reply_markup=get_main_keyboard())


async def set_location_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды установки локации."""
    message = (
        "📍 Отправь свою геолокацию, чтобы я мог находить ближайшие события.\n\n"
        "Нажми на кнопку ниже или отправь локацию вручную."
    )
    await update.message.reply_text(
        message, reply_markup=get_location_keyboard()
    )


async def my_channels_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды просмотра каналов."""
    user = update.effective_user
    user_storage: UserStorage = context.bot_data["user_storage"]

    channels = user_storage.get_user_channels(user.id)

    if not channels:
        message = "📋 У тебя пока нет добавленных каналов.\n\nИспользуй '➕ Добавить канал' для добавления."
    else:
        message = f"📋 Твои каналы ({len(channels)}):\n\n"
        for i, channel in enumerate(channels, 1):
            channel_name = channel.title or channel.channel_id
            status = "✅" if channel.is_active else "❌"
            message += f"{i}. {status} {channel_name}\n"
            if channel.channel_id.startswith("@"):
                message += f"   @{channel.channel_id}\n"

    await update.message.reply_text(message, reply_markup=get_main_keyboard())


def register_commands(application):
    """
    Регистрирует обработчики команд.

    Args:
        application: Application из python-telegram-bot
    """
    from telegram.ext import CommandHandler

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("location", set_location_command))
    application.add_handler(CommandHandler("channels", my_channels_command))


