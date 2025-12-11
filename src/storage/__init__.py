"""Хранилища данных."""

from src.storage.weaviate_client import WeaviateClient
from src.storage.user_storage import UserStorage
from src.storage.event_storage import EventStorage

__all__ = ["WeaviateClient", "UserStorage", "EventStorage"]


