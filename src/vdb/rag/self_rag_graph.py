"""Self-RAG граф на LangGraph. Возвращает InputData."""

from __future__ import annotations

import json
from typing import List, Literal, Optional, Tuple, TypedDict, Union

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI
try:
    from langchain_mistralai import ChatMistralAI
except ImportError:
    ChatMistralAI = None
from langgraph.graph import END, StateGraph

from src.vdb.config import (
    OPENAI_API_KEY,
    OPENAI_MODEL,
    MISTRAL_API_KEY,
    MISTRAL_MODEL,
    MAX_ITERATIONS,
)
from src.models.event import Event
from src.vdb.rag.memory import check_memory
from src.vdb.rag.prompts import (
    QUERY_REFORMULATION_PROMPT,
    RELEVANCE_EVALUATION_PROMPT,
)
from src.vdb.rag.retriever import EventRetriever
from src.vdb.rag.query_parser import parse_query_filters
from src.planner_agent.models import InputData, Constraints


# --- Вспомогательный промпт для extraction constraints ---
CONSTRAINTS_EXTRACTION_PROMPT = """
Извлеки ограничения для планирования из текста пользователя.

Верни ТОЛЬКО валидный JSON объект (без пояснений, без markdown), строго с ключами:
- start_time: "HH:MM" или null
- end_time: "HH:MM" или null
- max_total_time_minutes: integer или null
- preferred_transport: string или null
- budget: number или null
- other_constraints: array[string]

Текст пользователя:
{user_query}
""".strip()


class SelfRAGState(TypedDict):
    """Состояние графа Self-RAG."""

    user_query: str
    owner: Optional[str]

    # filters
    city: Optional[str]
    date: Optional[str]

    # retrieval loop
    retrieved_events: List[Event]
    reformulated_queries: List[str]
    iteration_count: int
    current_query: str

    # flags
    memory_found: bool
    is_relevant: bool

    # output
    constraints: Optional[Constraints]
    response: Optional[InputData]

    # logs
    logs: List[str]


# ---------------- Nodes ----------------

def parse_filters_node(state: SelfRAGState, llm: BaseChatModel) -> SelfRAGState:
    """Узел парсинга города и даты из запроса пользователя."""
    user_query = state["user_query"]
    logs = state.get("logs", [])

    try:
        filters = parse_query_filters(user_query, llm=llm)
        city = filters.city
        date = filters.date

        logs.append(
            f"🔍 Парсинг фильтров: город={city or 'не указан'}, дата={date or 'не указана'}"
        )
    except Exception as e:
        import warnings
        warnings.warn(f"Ошибка при парсинге фильтров: {e}")
        city = None
        date = None
        logs.append(f"⚠️ Ошибка при парсинге фильтров: {e}")

    return {
        **state,
        "city": city,
        "date": date,
        "logs": logs,
    }


def check_memory_node(state: SelfRAGState) -> SelfRAGState:
    """Узел проверки памяти (не прерывает граф, только логирует)."""
    has_memory = check_memory(state["user_query"], state.get("owner"))
    logs = state.get("logs", [])
    logs.append(f"🔍 Проверка памяти: {'найдено' if has_memory else 'не найдено'}")

    return {
        **state,
        "memory_found": has_memory,
        # is_relevant тут НЕ трогаем — это про релевантность retrieved_events
        "logs": logs,
    }


def retrieve_events_node(state: SelfRAGState, retriever: EventRetriever) -> SelfRAGState:
    """Узел поиска событий с фильтрацией по городу и дате."""
    query = state.get("current_query") or state["user_query"]
    owner = state.get("owner")
    city = state.get("city")
    date = state.get("date")

    events = retriever.retrieve(query, owner=owner, city=city, date=date)

    logs = state.get("logs", [])
    log_msg = f"🔎 Поиск событий: запрос='{query}', владелец='{owner}'"
    if city:
        log_msg += f", город='{city}'"
    if date:
        log_msg += f", дата='{date}'"
    log_msg += f", найдено={len(events)}"
    logs.append(log_msg)

    # Логируем распределение событий
    if owner:
        user_count = sum(1 for e in events if e.tags and owner in e.tags)
        common_count = len(events) - user_count
        logs.append(f"   События пользователя: {user_count}, общие: {common_count}")

    return {
        **state,
        "retrieved_events": events,
        "logs": logs,
    }


def evaluate_relevance_node(
    state: SelfRAGState, llm: BaseChatModel, retriever: Optional[EventRetriever] = None
) -> SelfRAGState:
    """Узел оценки релевантности извлеченной информации."""
    if retriever is None:
        retriever = EventRetriever()

    events_context = retriever.format_events_for_context(state["retrieved_events"])

    prompt = RELEVANCE_EVALUATION_PROMPT.format_messages(
        user_query=state["user_query"],
        retrieved_events=events_context,
    )

    response = llm.invoke(prompt)
    relevance_text = response.content.strip().upper()
    is_relevant = relevance_text.startswith("YES")

    logs = state.get("logs", [])
    logs.append(f"📊 Оценка релевантности: {relevance_text} ({'релевантно' if is_relevant else 'не релевантно'})")
    logs.append(f"   Найдено событий: {len(state['retrieved_events'])}")

    return {
        **state,
        "is_relevant": is_relevant,
        "logs": logs,
    }


def reformulate_queries_node(
    state: SelfRAGState, llm: BaseChatModel, retriever: Optional[EventRetriever] = None
) -> SelfRAGState:
    """Узел переформулировки запросов."""
    if retriever is None:
        retriever = EventRetriever()

    events_context = retriever.format_events_for_context(state["retrieved_events"])

    prompt = QUERY_REFORMULATION_PROMPT.format_messages(
        user_query=state["user_query"],
        retrieved_events=events_context,
    )

    response = llm.invoke(prompt)
    reformulated_text = response.content.strip()

    new_queries = [q.strip() for q in reformulated_text.split("\n") if q.strip()]
    current_query = new_queries[0] if new_queries else state["user_query"]

    logs = state.get("logs", [])
    iteration = state.get("iteration_count", 0) + 1
    logs.append(f"🔄 Переформулировка запроса (итерация {iteration}):")
    for i, q in enumerate(new_queries[:3], 1):
        logs.append(f"   {i}. {q}")

    return {
        **state,
        "reformulated_queries": state.get("reformulated_queries", []) + new_queries,
        "current_query": current_query,
        "iteration_count": iteration,
        "logs": logs,
    }


def extract_constraints_node(state: SelfRAGState, llm: BaseChatModel) -> SelfRAGState:
    """Достаём Constraints из user_query через LLM (JSON), с безопасным fallback."""
    logs = state.get("logs", [])

    prompt = CONSTRAINTS_EXTRACTION_PROMPT.format(user_query=state["user_query"])
    raw = ""
    constraints = None

    try:
        resp = llm.invoke(prompt)
        raw = (resp.content or "").strip()

        # на случай, если модель всё-таки завернула в ```...```
        raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()

        data = json.loads(raw)

        # pydantic v1/v2 совместимость
        if hasattr(Constraints, "model_validate"):
            constraints = Constraints.model_validate(data)
        else:
            constraints = Constraints.parse_obj(data)

        logs.append("🧩 Constraints извлечены из запроса через LLM")
    except Exception:
        constraints = Constraints()
        logs.append("🧩 Не удалось извлечь Constraints через LLM → использую пустые Constraints()")
        if raw:
            logs.append(f"   (сырое содержимое модели: {raw[:200]}...)")

    return {
        **state,
        "constraints": constraints,
        "logs": logs,
    }


def build_input_data_node(state: SelfRAGState) -> SelfRAGState:
    """Собираем финальный InputData."""
    logs = state.get("logs", [])
    constraints = state.get("constraints") or Constraints()

    input_data = InputData(
        events=state.get("retrieved_events", []),
        user_prompt=state["user_query"],
        constraints=constraints,
    )

    logs.append("✅ Сформирован InputData")

    return {
        **state,
        "response": input_data,
        "logs": logs,
    }


# ---------------- Conditions ----------------

def should_reformulate_or_finish(state: SelfRAGState) -> Literal["reformulate", "finish"]:
    """Если релевантно или достигнут лимит итераций — завершаем, иначе реформулируем."""
    iteration_count = state.get("iteration_count", 0)
    is_relevant = state.get("is_relevant", False)

    if is_relevant or iteration_count >= MAX_ITERATIONS:
        return "finish"
    return "reformulate"


# ---------------- Graph factory ----------------

def _create_llm() -> BaseChatModel:
    """
    Создает LLM модель в зависимости от доступных API ключей.
    Приоритет: Mistral (если доступен ключ), иначе OpenAI.
    """
    if MISTRAL_API_KEY and ChatMistralAI is not None:
        return ChatMistralAI(
            model=MISTRAL_MODEL,
            api_key=MISTRAL_API_KEY,
            temperature=0,
        )
    elif OPENAI_API_KEY:
        return ChatOpenAI(
            model=OPENAI_MODEL,
            api_key=OPENAI_API_KEY,
            temperature=0,
        )
    else:
        raise ValueError(
            "Не установлен ни один API ключ. "
            "Установите MISTRAL_API_KEY или OPENAI_API_KEY"
        )


def create_self_rag_graph(
    llm: Optional[BaseChatModel] = None,
    retriever: Optional[EventRetriever] = None,
) -> Tuple[StateGraph, Optional[EventRetriever]]:
    """Создает граф Self-RAG."""
    if llm is None:
        llm = _create_llm()

    created_retriever = None
    if retriever is None:
        retriever = EventRetriever()
        created_retriever = retriever

    workflow = StateGraph(SelfRAGState)

    workflow.add_node("parse_filters", lambda state: parse_filters_node(state, llm))
    workflow.add_node("check_memory", check_memory_node)
    workflow.add_node("retrieve_events", lambda state: retrieve_events_node(state, retriever))
    workflow.add_node("evaluate_relevance", lambda state: evaluate_relevance_node(state, llm, retriever))
    workflow.add_node("reformulate_queries", lambda state: reformulate_queries_node(state, llm, retriever))
    workflow.add_node("extract_constraints", lambda state: extract_constraints_node(state, llm))
    workflow.add_node("build_input_data", build_input_data_node)

    # Flow:
    # parse_filters -> check_memory -> retrieve -> evaluate -> (reformulate loop) -> extract_constraints -> build_input_data -> END
    workflow.set_entry_point("parse_filters")
    workflow.add_edge("parse_filters", "check_memory")
    workflow.add_edge("check_memory", "retrieve_events")
    workflow.add_edge("retrieve_events", "evaluate_relevance")

    workflow.add_conditional_edges(
        "evaluate_relevance",
        should_reformulate_or_finish,
        {
            "reformulate": "reformulate_queries",
            "finish": "extract_constraints",
        },
    )

    workflow.add_edge("reformulate_queries", "retrieve_events")
    workflow.add_edge("extract_constraints", "build_input_data")
    workflow.add_edge("build_input_data", END)

    return workflow.compile(), created_retriever


# ---------------- Runner ----------------

def run_self_rag(
    user_query: str,
    owner: Optional[str] = None,
    llm: Optional[BaseChatModel] = None,
    retriever: Optional[EventRetriever] = None,
    return_logs: bool = False,
) -> Union[InputData, Tuple[InputData, List[str]]]:
    """Запускает Self-RAG и возвращает InputData (или InputData + логи)."""
    graph, created_retriever = create_self_rag_graph(llm=llm, retriever=retriever)

    initial_state: SelfRAGState = {
        "user_query": user_query,
        "owner": owner,

        "city": None,
        "date": None,

        "retrieved_events": [],
        "reformulated_queries": [],
        "iteration_count": 0,
        "current_query": user_query,

        "memory_found": False,
        "is_relevant": False,

        "constraints": None,
        "response": None,

        "logs": [],
    }

    try:
        result = graph.invoke(initial_state)

        input_data: Optional[InputData] = result.get("response")
        logs: List[str] = result.get("logs", [])

        if input_data is None:
            # на всякий пожарный, чтобы тип всегда был InputData
            input_data = InputData(
                events=result.get("retrieved_events", []),
                user_prompt=user_query,
                constraints=Constraints(),
            )
            logs.append("⚠️ response был None → собрал InputData fallback")

        if return_logs:
            return input_data, logs
        return input_data

    finally:
        if created_retriever is not None:
            created_retriever.close()
        if retriever is not None:
            retriever.close()
