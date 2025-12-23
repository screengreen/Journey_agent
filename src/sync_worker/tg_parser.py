import os
import asyncio
from typing import List, Dict, Optional, Union
from urllib.parse import urlparse

from telethon import TelegramClient
from telethon.tl.types import Message
import dotenv


class TelegramParser:
    """Клиент для парсинга сообщений из Telegram каналов и избранного"""
    
    def __init__(
        self,
        api_id: Optional[Union[int, str]] = None,
        api_hash: Optional[str] = None,
        session_name: str = 'tg_session',
        load_env: bool = True
    ):
        """
        Инициализация клиента Telegram
        
        Args:
            api_id: API ID из my.telegram.org (int или str)
            api_hash: API Hash из my.telegram.org
            session_name: Имя файла сессии (без расширения)
            load_env: Загружать ли переменные из .env файла
        """
        if load_env:
            dotenv.load_dotenv()
        
        # Получаем credentials из параметров или переменных окружения
        self.api_id = int(api_id) if api_id else int(os.getenv("TELEGRAM_APP_API_ID", "0"))
        self.api_hash = api_hash or os.getenv("TELEGRAM_APP_API_HASH", "")
        self.session_name = session_name
        
        if not self.api_id or not self.api_hash:
            raise ValueError("Необходимо указать api_id и api_hash (через параметры или переменные окружения)")
        
        self.client: Optional[TelegramClient] = None
        self._is_connected = False
    
    async def __aenter__(self):
        """Асинхронный контекстный менеджер - вход"""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Асинхронный контекстный менеджер - выход"""
        await self.disconnect()
    
    async def connect(self) -> None:
        """Подключение к Telegram"""
        if not self._is_connected:
            self.client = TelegramClient(self.session_name, self.api_id, self.api_hash)

            self._is_connected = True
    
    async def disconnect(self) -> None:
        """Отключение от Telegram"""
        if self._is_connected and self.client:
            await self.client.disconnect()
            self._is_connected = False
    
    @staticmethod
    def extract_username_from_url(url: str) -> str:
        """
        Извлекает username канала из URL
        
        Args:
            url: URL канала (например, 'https://t.me/s/channel_name' или 'https://t.me/channel_name')
        
        Returns:
            username канала
        """
        parsed = urlparse(url)
        path = parsed.path.lstrip('/')
        # Если формат /s/channel_name
        if path.startswith('s/'):
            path = path[2:]
        return path
    
    async def get_channel_messages(
        self,
        channel: Union[str, int],
        limit: int = 10,
        reverse: bool = False
    ) -> List[Message]:
        """
        Получает сообщения из канала
        
        Args:
            channel: URL канала, username или ID канала
            limit: Максимальное количество сообщений
            reverse: Если True, вернуть сообщения в обратном порядке (от старых к новым)
        
        Returns:
            Список сообщений
        """
        if not self._is_connected:
            await self.connect()
        
        # Если передан URL, извлекаем username
        if isinstance(channel, str) and channel.startswith('http'):
            channel = self.extract_username_from_url(channel)
        
        # Получаем сущность канала
        entity = await self.client.get_entity(channel)
        
        messages = []
        async for msg in self.client.iter_messages(entity, limit=limit):
            messages.append(msg)
        
        if reverse:
            messages.reverse()
        
        return messages
    
    async def get_saved_messages(
        self,
        limit: int = 10,
        text_only: bool = False,
        reverse: bool = False
    ) -> List[Message]:
        """
        Получает сообщения из избранного (Saved Messages)
        
        Args:
            limit: Максимальное количество сообщений
            text_only: Если True, возвращать только сообщения с текстом
            reverse: Если True, вернуть сообщения в обратном порядке (от старых к новым)
        
        Returns:
            Список сообщений
        """
        if not self._is_connected:
            await self.connect()
        
        messages = []
        async for msg in self.client.iter_messages('me', limit=limit):
            if not text_only or msg.message:
                messages.append(msg)
        
        if reverse:
            messages.reverse()
        
        return messages
    
    async def get_saved_messages_dict(
        self,
        limit: int = 100,
        text_only: bool = True
    ) -> List[Dict]:
        """
        Получает сообщения из избранного в виде словарей
        
        Args:
            limit: Максимальное количество сообщений
            text_only: Если True, возвращать только сообщения с текстом
        
        Returns:
            Список словарей с полями: id, date, text
        """
        messages = await self.get_saved_messages(limit=limit, text_only=text_only)
        
        result = []
        for msg in messages:
            result.append({
                'id': msg.id,
                'date': msg.date.isoformat() if msg.date else None,
                'text': msg.message or ""
            })
        
        return result
    
    def format_message(self, msg: Message) -> str:
        """
        Форматирует сообщение для вывода
        
        Args:
            msg: Объект сообщения
        
        Returns:
            Отформатированная строка
        """
        text = msg.message or "<нет текста (медиа/документ)>"
        return f"[{msg.date}] (id={msg.id})\n{text}"
    
    def print_messages(self, messages: List[Message], separator: str = "-" * 40) -> None:
        """
        Выводит список сообщений в консоль
        
        Args:
            messages: Список сообщений
            separator: Разделитель между сообщениями
        """
        for msg in messages:
            print(self.format_message(msg))
            if separator:
                print(separator)
    
    @staticmethod
    def run_async(coro):
        """
        Запускает асинхронную функцию в синхронном контексте
        Совместимо с Jupyter и другими интерактивными средами
        
        Args:
            coro: Асинхронная корутина
        
        Returns:
            Результат выполнения корутины
        """
        try:
            return asyncio.run(coro)
        except RuntimeError as e:
            if "asyncio.run() cannot be called from a running event loop" in str(e):
                # Для Jupyter и других сред с уже запущенным event loop
                try:
                    import nest_asyncio
                    nest_asyncio.apply()
                    loop = asyncio.get_event_loop()
                    return loop.run_until_complete(coro)
                except ImportError:
                    raise ImportError(
                        "Для работы в Jupyter установите nest_asyncio: pip install nest_asyncio"
                    )
            else:
                raise

