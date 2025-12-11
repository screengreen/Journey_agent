"""Модель данных для событий."""

from typing import List, Optional
from pydantic import BaseModel, Field


class Event(BaseModel):
    """Модель события из базы данных."""

    title: str = Field(description="Название события")
    description: str = Field(description="Описание события")
    tags: List[str] = Field(default_factory=list, description="Теги события")
    source: Optional[str] = Field(default=None, description="Источник события")
    country: Optional[str] = Field(default=None, description="Страна события")
    location: Optional[str] = Field(default=None, description="Местоположение события")
    latitude: Optional[float] = Field(default=None, description="Широта события")
    longitude: Optional[float] = Field(default=None, description="Долгота события")
    date: Optional[str] = Field(default=None, description="Дата события")
    url: Optional[str] = Field(default=None, description="URL события")

    class Config:
        """Конфигурация модели."""

        extra = "allow"  # Разрешаем дополнительные поля из Weaviate

