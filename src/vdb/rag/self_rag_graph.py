"""Self-RAG граф на LangGraph. Возвращает InputData."""

from __future__ import annotations

import json
from typing import List, Literal, Optional, Tuple, TypedDict, Union

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph

from src.vdb.config import OPENAI_API_KEY, OPENAI_MODEL, MAX_ITERATIONS
from src.models.event import Event
from src.vdb.rag.memory import check_memory
from src.vdb.rag.prompts import (
    CITY_EXTRACTION_PROMPT,
    QUERY_REFORMULATION_PROMPT,
    RELEVANCE_EVALUATION_PROMPT,
)
from src.vdb.rag.retriever import EventRetriever
from src.planner_agent.models import InputData, Constraints


# --- Вспомогательный промпт для extraction constraints ---
CONSTRAINTS_EXTRACTION_PROMPT = """
Извлеки ограничения для планирования из текста пользователя.

Верни ТОЛЬКО валидный JSON объект (без пояснений, без markdown), строго с ключами:
- start_time: "HH:MM" или null (например: "10:00", "14:30")
- end_time: "HH:MM" или null (например: "18:00", "20:00")
- max_total_time_minutes: integer или null (общая длительность плана в минутах)
- preferred_transport: string или null (например: "walking", "bus", "car")
- budget: number или null (бюджет в рублях)
- max_events: integer или null (сколько событий/мест максимум включить в план)
- other_constraints: array[string] (другие ограничения)

ВАЖНО при извлечении max_events:
- Если пользователь явно указал количество мест ("2 места", "3 события", "пару мест", "немного мест") - извлеки это число
- "пару" = 2, "несколько" = 3, "немного" = 3-4
- Если количество НЕ указано - верни null
- Если указано "много" или "максимум" - верни null (не ограничиваем)

ВАЖНО при извлечении времени:
- Извлекай ТОЛЬКО явно указанное время
- Формат времени СТРОГО "HH:MM" (например: "09:00", "14:30", "18:00")
- Если время не указано - верни null
- "утром" = null (не конкретное время), "с 10 утра" = "10:00"

Текст пользователя:
{user_query}
""".strip()


class SelfRAGState(TypedDict):
    """Состояние графа Self-RAG."""

    user_query: str
    owner: Optional[str]

    # extracted city for filtering public events
    city: Optional[str]

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


def extract_city_node(state: SelfRAGState, llm: BaseChatModel) -> SelfRAGState:
    """Узел извлечения города из запроса пользователя."""
    logs = state.get("logs", [])

    prompt = CITY_EXTRACTION_PROMPT.format_messages(user_query=state["user_query"])

    try:
        response = llm.invoke(prompt)
        city_text = (response.content or "").strip()

        # Если модель вернула null или пустую строку, город не найден
        if city_text.lower() in ("null", "", "none", "не указан"):
            city = None
            logs.append("🏙️ Город не указан в запросе")
        else:
            city = city_text
            logs.append(f"🏙️ Извлечён город: {city}")
    except Exception as e:
        city = None
        logs.append(f"🏙️ Ошибка извлечения города: {e}")

    return {
        **state,
        "city": city,
        "logs": logs,
    }


def retrieve_events_node(state: SelfRAGState, retriever: EventRetriever) -> SelfRAGState:
    """Узел поиска событий."""
    query = state.get("current_query") or state["user_query"]
    owner = state.get("owner")
    city = state.get("city")

    events = retriever.retrieve(query, owner=owner, city=city)

    logs = state.get("logs", [])
    city_info = f", город='{city}'" if city else ""
    logs.append(f"🔎 Поиск событий: запрос='{query}', владелец='{owner}'{city_info}, найдено={len(events)}")

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
    from datetime import time as time_type
    
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

        # Конвертируем строковое время в объекты time
        if data.get("start_time") and isinstance(data["start_time"], str):
            try:
                hours, minutes = data["start_time"].split(":")
                data["start_time"] = time_type(int(hours), int(minutes))
            except (ValueError, AttributeError):
                logs.append(f"⚠️ Не удалось распарсить start_time: {data['start_time']}")
                data["start_time"] = None
        
        if data.get("end_time") and isinstance(data["end_time"], str):
            try:
                hours, minutes = data["end_time"].split(":")
                data["end_time"] = time_type(int(hours), int(minutes))
            except (ValueError, AttributeError):
                logs.append(f"⚠️ Не удалось распарсить end_time: {data['end_time']}")
                data["end_time"] = None

        # pydantic v1/v2 совместимость
        if hasattr(Constraints, "model_validate"):
            constraints = Constraints.model_validate(data)
        else:
            constraints = Constraints.parse_obj(data)

        # Логируем извлеченные constraints
        constraint_details = []
        if constraints.start_time:
            constraint_details.append(f"start_time={constraints.start_time}")
        if constraints.end_time:
            constraint_details.append(f"end_time={constraints.end_time}")
        if constraints.max_events:
            constraint_details.append(f"max_events={constraints.max_events}")
        if constraints.max_total_time_minutes:
            constraint_details.append(f"max_total_time={constraints.max_total_time_minutes}мин")
        
        if constraint_details:
            logs.append(f"🧩 Constraints извлечены: {', '.join(constraint_details)}")
        else:
            logs.append("🧩 Constraints извлечены (пустые)")
            
    except Exception as e:
        constraints = Constraints()
        logs.append(f"🧩 Не удалось извлечь Constraints через LLM → использую пустые Constraints() (ошибка: {str(e)[:100]})")
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

def create_self_rag_graph(
    llm: Optional[BaseChatModel] = None,
    retriever: Optional[EventRetriever] = None,
) -> Tuple[StateGraph, Optional[EventRetriever]]:
    """Создает граф Self-RAG."""
    if llm is None:
        if not OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY не установлен")
        llm = ChatOpenAI(model=OPENAI_MODEL, api_key=OPENAI_API_KEY, temperature=0)

    created_retriever = None
    if retriever is None:
        retriever = EventRetriever()
        created_retriever = retriever

    workflow = StateGraph(SelfRAGState)

    workflow.add_node("check_memory", check_memory_node)
    workflow.add_node("extract_city", lambda state: extract_city_node(state, llm))
    workflow.add_node("retrieve_events", lambda state: retrieve_events_node(state, retriever))
    workflow.add_node("evaluate_relevance", lambda state: evaluate_relevance_node(state, llm, retriever))
    workflow.add_node("reformulate_queries", lambda state: reformulate_queries_node(state, llm, retriever))
    workflow.add_node("extract_constraints", lambda state: extract_constraints_node(state, llm))
    workflow.add_node("build_input_data", build_input_data_node)

    # Flow:
    # check_memory -> extract_city -> retrieve -> evaluate -> (reformulate loop) -> extract_constraints -> build_input_data -> END
    workflow.set_entry_point("check_memory")
    workflow.add_edge("check_memory", "extract_city")
    workflow.add_edge("extract_city", "retrieve_events")
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
