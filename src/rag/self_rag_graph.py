"""Self-RAG граф на LangGraph."""

from typing import List, Literal, Optional, Tuple, TypedDict, Union

from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph

from src.config import OPENAI_API_KEY, OPENAI_MODEL, MAX_ITERATIONS
from src.models.event import Event
from src.rag.memory import check_memory
from src.rag.prompts import (
    QUERY_REFORMULATION_PROMPT,
    RELEVANCE_EVALUATION_PROMPT,
    RESPONSE_GENERATION_PROMPT,
)
from src.rag.retriever import EventRetriever


class SelfRAGState(TypedDict):
    """Состояние графа Self-RAG."""

    user_query: str
    user_tag: Optional[str]
    retrieved_events: List[Event]
    reformulated_queries: List[str]
    is_relevant: bool
    response: Optional[str]
    iteration_count: int
    current_query: str  # Текущий запрос для поиска (может быть переформулированным)
    logs: List[str]  # Логи решений графа


def check_memory_node(state: SelfRAGState) -> SelfRAGState:
    """Узел проверки памяти."""
    has_memory = check_memory(state["user_query"], state.get("user_tag"))
    logs = state.get("logs", [])
    logs.append(f"🔍 Проверка памяти: {'найдено' if has_memory else 'не найдено'}")
    return {
        **state,
        "is_relevant": has_memory,
        "logs": logs,
    }


def retrieve_events_node(state: SelfRAGState, retriever: EventRetriever) -> SelfRAGState:
    """Узел поиска событий."""
    query = state.get("current_query", state["user_query"])
    user_tag = state.get("user_tag")

    events = retriever.retrieve(query, user_tag=user_tag)
    
    logs = state.get("logs", [])
    logs.append(f"🔎 Поиск событий: запрос='{query}', тег='{user_tag}', найдено={len(events)}")

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

    # Парсим переформулированные запросы (каждый на новой строке)
    new_queries = [
        q.strip() for q in reformulated_text.split("\n") if q.strip()
    ]

    # Берем первый переформулированный запрос для следующей итерации
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


def generate_response_node(
    state: SelfRAGState, llm: BaseChatModel, retriever: Optional[EventRetriever] = None
) -> SelfRAGState:
    """Узел генерации финального ответа."""
    if retriever is None:
        retriever = EventRetriever()
    events_context = retriever.format_events_for_context(state["retrieved_events"])

    prompt = RESPONSE_GENERATION_PROMPT.format_messages(
        user_query=state["user_query"],
        retrieved_events=events_context,
    )

    response = llm.invoke(prompt)
    
    logs = state.get("logs", [])
    logs.append(f"✅ Генерация ответа завершена")

    return {
        **state,
        "response": response.content,
        "logs": logs,
    }


def should_retrieve(state: SelfRAGState) -> Literal["retrieve", "generate"]:
    """Условие: нужно ли искать события или генерировать ответ."""
    if state.get("is_relevant", False):
        return "generate"
    return "retrieve"


def should_reformulate(state: SelfRAGState) -> Literal["reformulate", "generate"]:
    """Условие: нужно ли переформулировать запрос или генерировать ответ."""
    iteration_count = state.get("iteration_count", 0)
    is_relevant = state.get("is_relevant", False)

    # Если релевантно или достигнут лимит итераций - генерируем ответ
    if is_relevant or iteration_count >= MAX_ITERATIONS:
        return "generate"
    return "reformulate"


def create_self_rag_graph(
    llm: Optional[BaseChatModel] = None,
    retriever: Optional[EventRetriever] = None,
) -> Tuple[StateGraph, Optional[EventRetriever]]:
    """
    Создает граф Self-RAG.

    Args:
        llm: Языковая модель (если None, создается новая)
        retriever: Retriever для поиска событий (если None, создается новый)

    Returns:
        Кортеж (граф LangGraph, retriever для закрытия)
    """
    if llm is None:
        if not OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY не установлен")
        llm = ChatOpenAI(model=OPENAI_MODEL, api_key=OPENAI_API_KEY, temperature=0)

    created_retriever = None
    if retriever is None:
        retriever = EventRetriever()
        created_retriever = retriever

    # Создаем граф
    workflow = StateGraph(SelfRAGState)

    # Добавляем узлы
    workflow.add_node("check_memory", check_memory_node)
    workflow.add_node(
        "retrieve_events",
        lambda state: retrieve_events_node(state, retriever),
    )
    workflow.add_node(
        "evaluate_relevance",
        lambda state: evaluate_relevance_node(state, llm, retriever),
    )
    workflow.add_node(
        "reformulate_queries",
        lambda state: reformulate_queries_node(state, llm, retriever),
    )
    workflow.add_node(
        "generate_response",
        lambda state: generate_response_node(state, llm, retriever),
    )

    # Определяем переходы
    workflow.set_entry_point("check_memory")

    # После check_memory: если память найдена -> generate_response, иначе -> retrieve_events
    workflow.add_conditional_edges(
        "check_memory",
        should_retrieve,
        {
            "retrieve": "retrieve_events",
            "generate": "generate_response",
        },
    )

    # После retrieve_events -> evaluate_relevance
    workflow.add_edge("retrieve_events", "evaluate_relevance")

    # После evaluate_relevance: если релевантно -> generate_response, иначе -> reformulate_queries
    workflow.add_conditional_edges(
        "evaluate_relevance",
        should_reformulate,
        {
            "reformulate": "reformulate_queries",
            "generate": "generate_response",
        },
    )

    # После reformulate_queries -> retrieve_events (с новым запросом)
    workflow.add_edge("reformulate_queries", "retrieve_events")

    # generate_response -> END
    workflow.add_edge("generate_response", END)

    return workflow.compile(), created_retriever


def run_self_rag(
    user_query: str,
    user_tag: Optional[str] = None,
    llm: Optional[BaseChatModel] = None,
    retriever: Optional[EventRetriever] = None,
    return_logs: bool = False,
) -> Union[str, Tuple[str, List[str]]]:
    """
    Запускает Self-RAG систему.

    Args:
        user_query: Запрос пользователя
        user_tag: Тег пользователя для фильтрации событий
        llm: Языковая модель (опционально)
        retriever: Retriever (опционально)
        return_logs: Если True, возвращает кортеж (ответ, логи)

    Returns:
        Финальный ответ системы или кортеж (ответ, логи) если return_logs=True
    """
    graph, created_retriever = create_self_rag_graph(llm=llm, retriever=retriever)

    initial_state: SelfRAGState = {
        "user_query": user_query,
        "user_tag": user_tag,
        "retrieved_events": [],
        "reformulated_queries": [],
        "is_relevant": False,
        "response": None,
        "iteration_count": 0,
        "current_query": user_query,
        "logs": [],
    }

    try:
        result = graph.invoke(initial_state)
        
        response = result.get("response", "Не удалось сгенерировать ответ.")
        logs = result.get("logs", [])
        
        if return_logs:
            return response, logs
        return response
    finally:
        # Закрываем соединение с Weaviate, если retriever был создан внутри
        if created_retriever is not None:
            created_retriever.close()
        # Закрываем соединение с Weaviate
        if retriever is not None:
            retriever.close()
        elif hasattr(graph, '_retriever'):
            # Если retriever был создан внутри графа, нужно его закрыть
            pass

