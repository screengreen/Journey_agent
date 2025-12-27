from __future__ import annotations

import os
from typing import Any, List, Optional, Type, TypeVar, Literal

from pydantic import BaseModel
from langchain_core.messages import SystemMessage, HumanMessage, BaseMessage
from langchain_openai import ChatOpenAI
from langchain_mistralai import ChatMistralAI
import dotenv

T = TypeVar("T", bound=BaseModel)

dotenv.load_dotenv()


class JourneyLLM:
    """
    Универсальная LLM-модель для проекта:
    - сама выбирает провайдера по env:
        * если есть только OPENAI_API_KEY → openai
        * если есть только MISTRAL_API_KEY → mistral
        * если есть оба → openai
        * если нет ни одного → ошибка
    - внутри держит LangChain-модель (ChatOpenAI или ChatMistralAI)
      в атрибуте `.llm`
    - поддерживает:
        * .invoke() / .stream() / .bind_tools() и т.п. (через __getattr__)
        * .parse(output_model, user_prompt, system_prompt, web_context)
    """

    def __init__(
        self,
        provider: Optional[Literal["openai", "mistral"]] = None,
        model: Optional[str] = None,
        temperature: float = 0.2,
    ) -> None:
        self.provider = provider or self._detect_provider_from_env()

        if self.provider == "openai":
            self.model = model or "gpt-4o"
            self.llm = ChatOpenAI(
                model=self.model,
                temperature=temperature,
            )
        elif self.provider == "mistral":
            self.model = model or "open-mistral-7b"
            self.llm = ChatMistralAI(
                model=self.model,
                temperature=temperature,
            )
        else:
            raise ValueError(f"Unknown provider: {self.provider}")

    @staticmethod
    def _detect_provider_from_env() -> Literal["openai", "mistral"]:
        openai_key = os.getenv("OPENAI_API_KEY")
        mistral_key = os.getenv("MISTRAL_API_KEY")

        if openai_key and not mistral_key:
            return "openai"
        if mistral_key and not openai_key:
            return "mistral"
        if openai_key and mistral_key:
            return "openai"

        raise RuntimeError(
            "No LLM API keys found. "
            "Set at least one of: OPENAI_API_KEY or MISTRAL_API_KEY."
        )

    def parse(
        self,
        output_model: Type[T],
        user_prompt: str,
        system_prompt: Optional[str] = None,
        web_context: Optional[str] = None,
    ) -> T:
        """
        Обёртка над with_structured_output.
        Пример использования:
            result = llm.parse(MySchema, "Сделай расписание выходных")
        """

        messages: List[BaseMessage] = []

        if system_prompt:
            messages.append(SystemMessage(content=system_prompt))

        if web_context:
            messages.append(
                SystemMessage(
                    content=(
                        "Вот контекст, собранный из интернета. "
                        "Используй его при ответе:\n\n" + web_context
                    )
                )
            )

        messages.append(HumanMessage(content=user_prompt))

        structured = self.llm.with_structured_output(output_model)
        result: T = structured.invoke(messages)
        return result

    def __getattr__(self, name: str) -> Any:
        """
        Всё, чего нет у JourneyLLM, прокидываем на self.llm:
        .invoke(), .stream(), .bind_tools(), .with_structured_output() и т.д.
        """
        return getattr(self.llm, name)

    def __call__(self, *args, **kwargs) -> Any:
        """
        Чтобы можно было использовать как "модель":
            llm("привет")  или llm.invoke(...)
        """
        return self.llm(*args, **kwargs)
