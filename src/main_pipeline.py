from src.utils.journey_llm import JourneyLLM
from src.vdb import EventRetriever
from src.planner_agent.graph import PlanningGraph
from src.vdb.rag.self_rag_graph import run_self_rag
from src.utils.safety import moderate_text, SafetyLabel


llm = JourneyLLM()
retriever = EventRetriever()


def main_pipeline(query: str) -> str:
    res = run_self_rag(query, retriever=retriever, llm=llm)
    graph = PlanningGraph(llm)

    output = graph.run(res)
    final_text = output.final_text

    # ✅ Final toxic OUTPUT safety net
    decision = moderate_text(final_text, llm=llm, context="model_output")
    if decision.label == SafetyLabel.block:
        return "Не удалось сформировать безопасный ответ. Попробуй переформулировать запрос (город, даты, интересы, бюджет)."
    if decision.label == SafetyLabel.soft and decision.sanitized_text:
        return decision.sanitized_text

    return final_text
