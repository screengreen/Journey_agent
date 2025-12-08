from __future__ import annotations

import operator
from typing import Annotated, Optional, TypedDict

from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph, END

from safety.guardrails import (
    GuardConfig,
    GuardViolation,
    guard_user_input,
    guard_model_output,
)


# ---------- STATE ----------


class AgentState(TypedDict, total=False):
    messages: Annotated[list[BaseMessage], operator.add]
    blocked: bool
    guard_reason: Optional[str]


GUARD_CONFIG = GuardConfig(
    max_user_chars=4000,
    max_model_chars=8000,
    allowed_tools={"search", "geocode", "weather", "routing"},
    blocked_domains={"facebook.com", "vk.com"},
    redact_pii=True,
)


# ---------- Узел 1: INPUT GUARD ----------


def input_guard_node(state: AgentState, config: RunnableConfig) -> AgentState:
    """
    Берём последнее сообщение от пользователя из state["messages"],
    прогоняем через guard_user_input и кладём обратно.
    Если guard ломается — ставим blocked=True и текст с причиной.
    """
    messages = state.get("messages", [])
    if not messages:
        return state

    last = messages[-1]
    if isinstance(last, HumanMessage):
        try:
            cleaned_text = guard_user_input(last.content, GUARD_CONFIG)
            messages[-1] = HumanMessage(content=cleaned_text, additional_kwargs=last.additional_kwargs)
            return {
                **state,
                "messages": messages,
                "blocked": False,
            }
        except GuardViolation as e:
            return {
                **state,
                "blocked": True,
                "guard_reason": f"Запрос отклонён guardrails: {e}",
            }
        
    return state


# ---------- Узел 2: АГЕНТ (заглушка, сюда подставить Journey_agent) ----------


def run_agent_step(state: AgentState, config: RunnableConfig) -> AgentState:
    """
    Здесь ты вызываешь свой LLM / LangChain-агента / Journey_agent backend.
    Сейчас стоит простая заглушка, чтобы показать структуру.
    """
    messages = state.get("messages", [])
    user_msg = next((m for m in reversed(messages) if isinstance(m, HumanMessage)), None)

    if user_msg is None:
        return state

    user_text = user_msg.content

    # ТУТ ВАЖНО:
    # Вместо этого блока вставить свой объект:
    #   backend = create_backend(...)
    #   ai_text = backend(...), или lc_chain.invoke(...)
    #
    # Ниже — примитивный пример:
    ai_text = f"Echo (journey_agent заглушка): {user_text[:200]}"

    ai_msg = AIMessage(content=ai_text)
    return {
        **state,
        "messages": messages + [ai_msg],
    }


# ---------- Узел 3: OUTPUT GUARD ----------


def output_guard_node(state: AgentState, config: RunnableConfig) -> AgentState:
    """
    Проверяем последний AIMessage, редактируем/режем PII, длину и т.д.
    """
    messages = state.get("messages", [])
    if not messages:
        return state

    last = messages[-1]
    if not isinstance(last, AIMessage):
        return state

    try:
        safe_text = guard_model_output(last.content, GUARD_CONFIG)
        messages[-1] = AIMessage(content=safe_text, additional_kwargs=last.additional_kwargs)
        return {
            **state,
            "messages": messages,
        }
    except GuardViolation as e:
        err_msg = AIMessage(
            content=f"Ответ был заблокирован guardrails: {e}",
        )
        return {
            **state,
            "messages": messages[:-1] + [err_msg],
        }


# ---------- ROUTER: куда идти после input_guard ----------


def route_after_input_guard(state: AgentState) -> str:
    """
    Если запрос заблокирован — идём сразу в END.
    Иначе — в узел 'agent'.
    """
    if state.get("blocked"):
        return "blocked_output"
    return "agent"


def blocked_output_node(state: AgentState, config: RunnableConfig) -> AgentState:
    """
    Узел, который формирует финальный ответ пользователю,
    если input_guard заблокировал запрос.
    """
    reason = state.get("guard_reason") or "Запрос не может быть обработан."
    messages = state.get("messages", [])
    ai_msg = AIMessage(content=reason)
    return {
        **state,
        "messages": messages + [ai_msg],
    }


# ---------- Сборка графа ----------


def build_guarded_graph():
    """
    Возвращает скомпилированный LangGraph с guardrails.
    Его можно использовать как основной entrypoint агента.
    """
    builder = StateGraph(AgentState)

    # Узлы
    builder.add_node("input_guard", input_guard_node)
    builder.add_node("agent", run_agent_step)
    builder.add_node("output_guard", output_guard_node)
    builder.add_node("blocked_output", blocked_output_node)

    builder.set_entry_point("input_guard")

    builder.add_conditional_edges(
        "input_guard",
        route_after_input_guard,
        {
            "agent": "agent",
            "blocked_output": "blocked_output",
        },
    )

    builder.add_edge("agent", "output_guard")
    builder.add_edge("output_guard", END)
    builder.add_edge("blocked_output", END)

    return builder.compile()


# ---------- Пример использования ----------

if __name__ == "__main__":

    graph = build_guarded_graph()

    initial_state: AgentState = {
        "messages": [HumanMessage(content="Привет! Вот мой телефон +7 999 123-45-67")],
    }

    result = graph.invoke(initial_state)
    for m in result["messages"]:
        role = "user" if isinstance(m, HumanMessage) else "assistant"
        print(role, ":", m.content)
