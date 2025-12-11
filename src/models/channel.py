"""Модель канала."""

from typing import Optional
from pydantic import BaseModel, Field


class Channel(BaseModel):
    """Модель Telegram канала."""

    channel_id: str = Field(description="ID канала (username или ID)")
    title: Optional[str] = Field(default=None, description="Название канала")
    user_id: int = Field(description="ID пользователя, который добавил канал")
    last_parsed_message_id: Optional[int] = Field(default=None, description="ID последнего распарсенного сообщения")
    is_active: bool = Field(default=True, description="Активен ли канал для парсинга")

    class Config:
        """Конфигурация модели."""

        extra = "allow"


