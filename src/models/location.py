"""Модель локации."""

from typing import Optional
from pydantic import BaseModel, Field


class Location(BaseModel):
    """Модель географической локации."""

    address: str = Field(description="Адрес")
    latitude: float = Field(description="Широта")
    longitude: float = Field(description="Долгота")
    city: Optional[str] = Field(default=None, description="Город")
    country: Optional[str] = Field(default=None, description="Страна")

    class Config:
        """Конфигурация модели."""

        extra = "allow"


