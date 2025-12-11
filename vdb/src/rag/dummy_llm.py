"""Dummy LLM для тестирования без реальных API вызовов."""

from typing import Any, List, Optional

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import Field


class DummyLLM(BaseChatModel):
    """Dummy LLM для тестирования Self-RAG системы."""

    relevance_response: str = Field(default="YES", description="Ответ для оценки релевантности")
    enable_reformulation: bool = Field(default=True, description="Включить ли переформулировку запросов")

    def __init__(
        self,
        relevance_response: str = "YES",
        enable_reformulation: bool = True,
        **kwargs: Any,
    ):
        """
        Инициализация Dummy LLM.

        Args:
            relevance_response: Ответ для оценки релевантности ("YES" или "NO")
            enable_reformulation: Включить ли переформулировку запросов
            **kwargs: Дополнительные параметры
        """
        # Преобразуем relevance_response в верхний регистр перед передачей в super
        relevance_response = relevance_response.upper()
        super().__init__(
            relevance_response=relevance_response,
            enable_reformulation=enable_reformulation,
            **kwargs,
        )

    @property
    def _llm_type(self) -> str:
        """Тип LLM."""
        return "dummy"

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[Any] = None,
        **kwargs: Any,
    ) -> ChatResult:
        """
        Генерирует ответ на основе сообщений.

        Args:
            messages: Список сообщений
            stop: Список стоп-слов
            run_manager: Менеджер выполнения
            **kwargs: Дополнительные параметры

        Returns:
            ChatResult с сгенерированным ответом
        """
        # Извлекаем текст из сообщений
        full_text_parts = []
        for msg in messages:
            if hasattr(msg, "content"):
                full_text_parts.append(msg.content)
            elif hasattr(msg, "get_content"):
                full_text_parts.append(msg.get_content())
            else:
                full_text_parts.append(str(msg))
        full_text = "\n".join(full_text_parts)

        # Определяем тип промпта по содержимому
        response_text = self._determine_response(full_text, messages)

        # Создаем AI сообщение (правильный тип для ChatGeneration)
        message = AIMessage(content=response_text)
        generation = ChatGeneration(message=message)
        return ChatResult(generations=[generation])

    def _determine_response(self, full_text: str, messages: List[BaseMessage]) -> str:
        """
        Определяет ответ на основе типа промпта.

        Args:
            full_text: Полный текст всех сообщений
            messages: Список сообщений

        Returns:
            Текст ответа
        """
        # Проверяем тип промпта по содержимому системного сообщения
        system_message = None
        human_message = None

        for msg in messages:
            # Извлекаем содержимое сообщения
            msg_content = None
            if hasattr(msg, "content"):
                msg_content = msg.content
            elif hasattr(msg, "get_content"):
                msg_content = msg.get_content()
            else:
                msg_content = str(msg)

            # Определяем тип сообщения
            msg_type = type(msg).__name__
            if "System" in msg_type or (hasattr(msg, "type") and msg.type == "system"):
                system_message = msg_content
            elif "Human" in msg_type or (hasattr(msg, "type") and msg.type == "human"):
                human_message = msg_content

        if system_message:
            # Оценка релевантности
            if "оценка релевантности" in system_message.lower() or "релевантности информации" in system_message.lower():
                return self.relevance_response

            # Переформулировка запросов
            if "переформулировке запросов" in system_message.lower() or "переформулировка" in system_message.lower():
                if self.enable_reformulation and human_message:
                    # Извлекаем исходный запрос
                    query = self._extract_user_query(human_message)
                    if query:
                        # Генерируем переформулированные запросы
                        return self._generate_reformulated_queries(query)
                return human_message or "Альтернативный запрос 1\nАльтернативный запрос 2"

            # Генерация ответа
            if "помощник" in system_message.lower() or "сформируй ответ" in system_message.lower():
                return self._generate_final_response(human_message or full_text)

        # По умолчанию возвращаем простой ответ
        return "Dummy response"

    def _extract_user_query(self, text: str) -> Optional[str]:
        """Извлекает запрос пользователя из текста."""
        if "Запрос пользователя:" in text or "Исходный запрос:" in text:
            for line in text.split("\n"):
                if "Запрос пользователя:" in line or "Исходный запрос:" in line:
                    parts = line.split(":", 1)
                    if len(parts) > 1:
                        return parts[1].strip()
        return None

    def _generate_reformulated_queries(self, original_query: str) -> str:
        """
        Генерирует переформулированные запросы.

        Args:
            original_query: Исходный запрос

        Returns:
            Список переформулированных запросов (каждый на новой строке)
        """
        # Простые варианты переформулировки
        reformulations = [
            f"{original_query} (расширенный поиск)",
            f"Найти события: {original_query}",
            f"Поиск по запросу: {original_query}",
        ]
        return "\n".join(reformulations[:2])  # Возвращаем 2 варианта

    def _generate_final_response(self, context: str) -> str:
        """
        Генерирует финальный ответ на основе контекста.

        Args:
            context: Контекст с событиями

        Returns:
            Финальный ответ
        """
        # Проверяем, есть ли события в контексте
        if "События не найдены" in context or "не найдены" in context.lower():
            return "К сожалению, по вашему запросу не найдено подходящих событий."

        # Подсчитываем количество событий
        event_count = context.count("1.") + context.count("2.") + context.count("3.")
        if event_count == 0:
            event_count = len([line for line in context.split("\n") if line.strip().startswith(("•", "-", "*"))])

        if event_count > 0:
            return f"""Найдено {event_count} релевантных событий:

{context}

Эти события соответствуют вашему запросу и могут быть интересны для посещения."""
        else:
            return f"""Ответ на ваш запрос:

{context}

Надеюсь, эта информация будет полезной."""

    def invoke(self, messages: List[BaseMessage], **kwargs: Any) -> AIMessage:
        """
        Удобный метод для вызова LLM (совместим с ChatOpenAI).

        Args:
            messages: Список сообщений или промпт
            **kwargs: Дополнительные параметры

        Returns:
            AIMessage с атрибутом content
        """
        # Если передан промпт напрямую (из ChatPromptTemplate)
        if not isinstance(messages, list):
            messages = [messages]

        result = self._generate(messages, **kwargs)
        if result.generations:
            message = result.generations[0].message
            return message
        return AIMessage(content="Dummy response")

    async def ainvoke(self, messages: List[BaseMessage], **kwargs: Any) -> AIMessage:
        """
        Асинхронная версия invoke (для совместимости).

        Args:
            messages: Список сообщений
            **kwargs: Дополнительные параметры

        Returns:
            Объект с атрибутом content
        """
        return self.invoke(messages, **kwargs)

