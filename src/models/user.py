"""Модель пользователя."""

from typing import List, Optional
from pydantic import BaseModel, Field


class User(BaseModel):
    """Модель пользователя Telegram."""

    user_id: int = Field(description="Telegram user ID")
    username: Optional[str] = Field(default=None, description="Telegram username")
    first_name: Optional[str] = Field(default=None, description="Имя пользователя")
    subscribed_channels: List[str] = Field(default_factory=list, description="Список подписанных каналов")
    location: Optional[str] = Field(default=None, description="Текущая локация пользователя")
    latitude: Optional[float] = Field(default=None, description="Широта")
    longitude: Optional[float] = Field(default=None, description="Долгота")

    class Config:
        """Конфигурация модели."""

        extra = "allow"


