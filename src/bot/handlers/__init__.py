"""Обработчики команд и сообщений бота."""

from src.bot.handlers.commands import register_commands
from src.bot.handlers.channels import register_channel_handlers
from src.bot.handlers.search import register_search_handlers

__all__ = ["register_commands", "register_channel_handlers", "register_search_handlers"]


