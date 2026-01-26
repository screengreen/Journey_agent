"""
Pydantic модели для агентской системы планирования.
"""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import time

from src.models.event import Event



class Constraints(BaseModel):
    """Ограничения для планирования."""
    start_time: Optional[time] = Field(description="Время начала похода", default=None)
    end_time: Optional[time] = Field(description="Время окончания похода", default=None)
    max_total_time_minutes: Optional[int] = Field(description="Максимальное общее время в минутах", default=None)
    preferred_transport: Optional[str] = Field(description="Предпочтительный транспорт", default=None)
    budget: Optional[float] = Field(description="Бюджет", default=None)
    max_events: Optional[int] = Field(description="Максимальное количество событий в плане", default=None)
    other_constraints: List[str] = Field(description="Другие ограничения", default_factory=list)


class InputData(BaseModel):
    """Входные данные для системы планирования."""
    events: List[Event] = Field(description="Список событий")
    user_prompt: str = Field(description="Промпт пользователя")
    constraints: Constraints = Field(description="Ограничения для планирования")


class Reasoning(BaseModel):
    """Рассуждения планировщика перед созданием плана."""
    analysis: str = Field(description="Анализ доступных событий и ограничений")
    considerations: List[str] = Field(description="Важные соображения при планировании")
    challenges: List[str] = Field(description="Выявленные проблемы и вызовы")
    strategy: str = Field(description="Стратегия планирования")


class PlanItem(BaseModel):
    """Элемент плана."""
    event_name: str = Field(description="Название события")
    event_address: str = Field(description="Адрес события")
    start_time: time = Field(description="Время начала")
    end_time: time = Field(description="Время окончания")
    duration_minutes: int = Field(description="Продолжительность в минутах")
    transport_mode: str = Field(description="Режим транспорта")
    travel_time_minutes: Optional[int] = Field(description="Время в пути до события в минутах", default=None)
    notes: str = Field(description="Заметки", default="")


class Plan(BaseModel):
    """План похода."""
    items: List[PlanItem] = Field(description="Элементы плана в хронологическом порядке")
    total_duration_minutes: int = Field(description="Общая продолжительность в минутах")
    total_travel_time_minutes: int = Field(description="Общее время в пути в минутах")
    summary: str = Field(description="Краткое описание плана")
    included_events: List[str] = Field(description="Список включенных событий")
    excluded_events: List[str] = Field(description="Список исключенных событий (если есть)")


class Critique(BaseModel):
    """Критика плана от агента-критика."""
    overall_assessment: str = Field(description="Общая оценка плана")
    strengths: List[str] = Field(description="Сильные стороны плана")
    weaknesses: List[str] = Field(description="Слабые стороны и проблемы")
    suggestions: List[str] = Field(description="Конкретные предложения по улучшению")
    critical_issues: List[str] = Field(description="Критические проблемы, требующие исправления")
    needs_revision: bool = Field(description="Требуется ли пересмотр плана")


class GraphState(BaseModel):
    """Состояние графа LangGraph."""
    model_config = {"extra": "forbid", "frozen": False}
    
    input_data: InputData = Field(description="Входные данные")
    reasoning: Optional[Reasoning] = Field(description="Рассуждения планировщика", default=None)
    plan: Optional[Plan] = Field(description="Текущий план", default=None)
    critique: Optional[Critique] = Field(description="Критика плана", default=None)
    iteration: int = Field(description="Номер итерации", default=0)
    max_iterations: int = Field(description="Максимальное количество итераций", default=3)
    weather_info: Dict[str, Any] = Field(description="Информация о погоде", default_factory=dict)
    maps_info: Dict[str, Any] = Field(description="Информация о маршрутах", default_factory=dict)
    web_info: Dict[str, Any] = Field(description="Информация из интернета", default_factory=dict)


class OutputResult(BaseModel):
    """Выходной результат графа."""
    final_plan: Plan = Field(description="Финальный план")
    reasoning: Optional[Reasoning] = Field(description="Рассуждения планировщика", default=None)
    critique: Optional[Critique] = Field(description="Последняя критика", default=None)
    iterations: int = Field(description="Количество итераций")
    weather_info: Dict[str, Any] = Field(description="Использованная информация о погоде", default_factory=dict)
    maps_info: Dict[str, Any] = Field(description="Использованная информация о маршрутах", default_factory=dict)
    web_info: Dict[str, Any] = Field(description="Использованная информация из интернета", default_factory=dict)
    final_text: str = Field(description="Финальный текст плана")
