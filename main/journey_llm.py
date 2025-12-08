from __future__ import annotations

import os
from typing import Any, List, Optional, Type, TypeVar, Literal

from pydantic import BaseModel
from langchain_core.messages import SystemMessage, HumanMessage, BaseMessage, AIMessage, ToolMessage
from langchain_openai import ChatOpenAI
from langchain_mistralai import ChatMistralAI


T = TypeVar("T", bound=BaseModel)


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
        tools: Optional[List[Any]] = None,
    ) -> T:
        """
        Обёртка над with_structured_output с поддержкой инструментов.
        Если переданы инструменты, LLM может их вызывать перед возвратом результата.
        
        Пример использования:
            result = llm.parse(MySchema, "Сделай расписание выходных", tools=[...])
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

        # Если есть инструменты, используем их с обработкой tool calls
        if tools:
            return self._parse_with_tools(output_model, messages, tools)
        
        # Иначе используем обычный structured output
        structured = self.llm.with_structured_output(output_model)
        result: T = structured.invoke(messages)
        return result
    
    def _parse_with_tools(
        self,
        output_model: Type[T],
        messages: List[BaseMessage],
        tools: List[Any],
        max_iterations: int = 10
    ) -> T:
        """
        Парсинг с поддержкой инструментов: обрабатывает tool calls в цикле.
        """
        llm_with_tools = self.llm.bind_tools(tools)
        tool_map = {tool.name: tool for tool in tools}
        
        for iteration in range(max_iterations):
            # Получаем ответ от LLM
            response = llm_with_tools.invoke(messages)
            messages.append(response)
            
            # Проверяем наличие tool calls
            tool_calls = getattr(response, 'tool_calls', None) or []
            if not tool_calls:
                # Если нет tool calls, получаем финальный результат
                structured = self.llm.with_structured_output(output_model)
                final_messages = messages + [HumanMessage(
                    content="Верни результат в структурированном формате согласно схеме на основе всей собранной информации."
                )]
                result: T = structured.invoke(final_messages)
                return result
            
            # Обрабатываем tool calls
            for tool_call in tool_calls:
                # Обрабатываем разные форматы tool_call
                if isinstance(tool_call, dict):
                    tool_name = tool_call.get("name", "")
                    tool_args = tool_call.get("args", {})
                    tool_call_id = tool_call.get("id", f"call_{iteration}_{tool_name}")
                else:
                    # Если это объект
                    tool_name = getattr(tool_call, "name", "")
                    tool_args = getattr(tool_call, "args", {})
                    tool_call_id = getattr(tool_call, "id", f"call_{iteration}_{tool_name}")
                
                if not tool_name or tool_name not in tool_map:
                    error_msg = f"Инструмент {tool_name} не найден"
                    messages.append(ToolMessage(content=error_msg, tool_call_id=tool_call_id))
                    continue
                
                # Вызываем инструмент
                tool = tool_map[tool_name]
                try:
                    print(f"   🔧 Вызываю инструмент: {tool_name}")
                    tool_result = tool.invoke(tool_args)
                    # Преобразуем результат в JSON строку для передачи обратно
                    if not isinstance(tool_result, str):
                        import json
                        tool_result = json.dumps(tool_result, ensure_ascii=False, default=str)
                    
                    messages.append(ToolMessage(content=str(tool_result), tool_call_id=tool_call_id))
                    print(f"   ✅ Результат инструмента {tool_name} получен")
                except Exception as e:
                    error_msg = f"Ошибка при вызове инструмента {tool_name}: {str(e)}"
                    messages.append(ToolMessage(content=error_msg, tool_call_id=tool_call_id))
                    print(f"   ❌ Ошибка при вызове инструмента {tool_name}: {e}")
        
        # Если достигли максимального количества итераций, пытаемся получить результат
        structured = self.llm.with_structured_output(output_model)
        final_messages = messages + [HumanMessage(
            content="Верни результат в структурированном формате согласно схеме на основе всей собранной информации."
        )]
        result: T = structured.invoke(final_messages)
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
