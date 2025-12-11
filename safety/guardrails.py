from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Set

from langchain_core.tools import BaseTool


class GuardViolation(Exception):
    """Любое нарушение правил guardrails."""


@dataclass
class GuardConfig:
    """
    Базовая конфигурация "рейлгарда".
    Её можно переиспользовать в любом LLM-проекте.
    """
    max_user_chars: int = 4000
    max_model_chars: int = 12000

    allowed_tools: Set[str] = field(
        default_factory=lambda: {"search", "geocode", "weather", "routing"}
    )

    blocked_domains: Set[str] = field(
        default_factory=lambda: {"facebook.com", "vk.com"}
    )

    redact_pii: bool = True


PHONE_RE = re.compile(r"\+?\d[\d\-\s]{8,}\d")
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def redact_pii(text: str) -> str:
    """Очень простая маскировка телефонов и email."""
    text = PHONE_RE.sub("[PHONE_REDACTED]", text)
    text = EMAIL_RE.sub("[EMAIL_REDACTED]", text)
    return text


# ---------- INPUT GUARD ----------


def guard_user_input(text: str, config: GuardConfig) -> str:
    """
    Проверка пользовательского ввода:
    - ограничение длины
    - простая фильтрация PII (опционально)
    - (при желании) фильтрация токсичности и т.д. — можно расширить
    """
    if not isinstance(text, str):
        raise GuardViolation("Ожидалась строка user_input")

    if len(text) > config.max_user_chars:
        raise GuardViolation(
            f"User input слишком длинный ({len(text)} символов). "
            f"Максимум: {config.max_user_chars}"
        )

    if config.redact_pii:
        text = redact_pii(text)

    # Здесь можно добавить:
    # - фильтр мата
    # - фильтр jailbreak-паттернов
    # - фильтр запрещённых тем
    return text


# ---------- OUTPUT GUARD ----------


def guard_model_output(text: str, config: GuardConfig) -> str:
    """
    Проверка текста, который агент возвращает пользователю.
    """
    if not isinstance(text, str):
        raise GuardViolation("Ожидалась строка model_output")

    if len(text) > config.max_model_chars:
        text = text[: config.max_model_chars] + "\n\n[TRUNCATED BY GUARD]"

    if config.redact_pii:
        text = redact_pii(text)

    # тут же можно запретить определённый контент, ключевые слова и т.п.
    return text


# ---------- TOOL GUARD ----------


def guard_tool_call(
    tool_name: str,
    args: Dict[str, Any],
    config: GuardConfig,
) -> None:
    """
    Проверка вызова инструмента:
    - разрешён ли инструмент
    - базовая проверка аргументов
    """
    if tool_name not in config.allowed_tools:
        raise GuardViolation(f"Инструмент `{tool_name}` запрещён guardrails")

    url_like_fields = ("url", "urls", "domain")
    for key, value in args.items():
        if key in url_like_fields and isinstance(value, str):
            for blocked in config.blocked_domains:
                if blocked in value:
                    raise GuardViolation(
                        f"Домен `{blocked}` запрещён для инструмента `{tool_name}`"
                    )

    # Дополнительно можно проверять:
    # - размеры списков
    # - диапазоны чисел (например, радиус поиска <= 100 км)
    # - и т.д.


class ToolWithGuard(BaseTool):
    """
    Обёртка над любым LangChain-Tool, которая пропускает вызовы через guard_tool_call.
    """

    def __init__(self, inner_tool: BaseTool, config: GuardConfig):
        super().__init__(
            name=inner_tool.name,
            description=inner_tool.description,
            args_schema=getattr(inner_tool, "args_schema", None),
        )
        self._inner_tool = inner_tool
        self._config = config

    def _run(self, *args: Any, **kwargs: Any) -> Any:
        arg_dict: Dict[str, Any] = {}
        if args:
            arg_dict["__args"] = list(args)
        arg_dict.update(kwargs)

        guard_tool_call(self.name, arg_dict, self._config)
        return self._inner_tool._run(*args, **kwargs)

    async def _arun(self, *args: Any, **kwargs: Any) -> Any:
        arg_dict: Dict[str, Any] = {}
        if args:
            arg_dict["__args"] = list(args)
        arg_dict.update(kwargs)

        guard_tool_call(self.name, arg_dict, self._config)
        return await self._inner_tool._arun(*args, **kwargs)


def wrap_tools_with_guard(
    tools: Iterable[BaseTool],
    config: GuardConfig,
) -> List[BaseTool]:
    """Удобная функция: обернуть целый список tools сразу."""
    return [ToolWithGuard(t, config) for t in tools]
