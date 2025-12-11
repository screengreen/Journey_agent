"""Хранилище данных пользователей."""

import json
from pathlib import Path
from typing import Dict, List, Optional

from src.models.user import User
from src.models.channel import Channel

# Простое файловое хранилище (можно заменить на БД)
STORAGE_DIR = Path(__file__).parent.parent.parent / "data"
USERS_FILE = STORAGE_DIR / "users.json"
CHANNELS_FILE = STORAGE_DIR / "channels.json"


class UserStorage:
    """Хранилище данных пользователей и каналов."""

    def __init__(self):
        """Инициализация хранилища."""
        STORAGE_DIR.mkdir(exist_ok=True)
        self._users: Dict[int, User] = {}
        self._channels: Dict[str, Channel] = {}
        self._load_data()

    def _load_data(self):
        """Загружает данные из файлов."""
        if USERS_FILE.exists():
            try:
                with open(USERS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._users = {
                        int(uid): User(**user_data) for uid, user_data in data.items()
                    }
            except Exception as e:
                print(f"Ошибка загрузки пользователей: {e}")

        if CHANNELS_FILE.exists():
            try:
                with open(CHANNELS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._channels = {
                        cid: Channel(**channel_data) for cid, channel_data in data.items()
                    }
            except Exception as e:
                print(f"Ошибка загрузки каналов: {e}")

    def _save_data(self):
        """Сохраняет данные в файлы."""
        try:
            with open(USERS_FILE, "w", encoding="utf-8") as f:
                json.dump(
                    {str(uid): user.model_dump() for uid, user in self._users.items()},
                    f,
                    ensure_ascii=False,
                    indent=2,
                )
        except Exception as e:
            print(f"Ошибка сохранения пользователей: {e}")

        try:
            with open(CHANNELS_FILE, "w", encoding="utf-8") as f:
                json.dump(
                    {cid: channel.model_dump() for cid, channel in self._channels.items()},
                    f,
                    ensure_ascii=False,
                    indent=2,
                )
        except Exception as e:
            print(f"Ошибка сохранения каналов: {e}")

    def get_user(self, user_id: int) -> Optional[User]:
        """
        Получает пользователя по ID.

        Args:
            user_id: ID пользователя

        Returns:
            User или None
        """
        return self._users.get(user_id)

    def save_user(self, user: User):
        """
        Сохраняет пользователя.

        Args:
            user: Пользователь для сохранения
        """
        self._users[user.user_id] = user
        self._save_data()

    def add_channel(self, channel: Channel):
        """
        Добавляет канал.

        Args:
            channel: Канал для добавления
        """
        self._channels[channel.channel_id] = channel
        # Добавляем канал в список подписок пользователя
        user = self.get_user(channel.user_id)
        if user and channel.channel_id not in user.subscribed_channels:
            user.subscribed_channels.append(channel.channel_id)
            self.save_user(user)
        self._save_data()

    def get_user_channels(self, user_id: int) -> List[Channel]:
        """
        Получает все каналы пользователя.

        Args:
            user_id: ID пользователя

        Returns:
            Список каналов
        """
        return [
            channel
            for channel in self._channels.values()
            if channel.user_id == user_id and channel.is_active
        ]

    def get_channel(self, channel_id: str) -> Optional[Channel]:
        """
        Получает канал по ID.

        Args:
            channel_id: ID канала

        Returns:
            Channel или None
        """
        return self._channels.get(channel_id)


