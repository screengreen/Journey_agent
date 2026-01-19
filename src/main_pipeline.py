from typing import Optional

from src.utils.journey_llm import JourneyLLM
from src.vdb import EventRetriever
from src.planner_agent.graph import PlanningGraph
from src.vdb.rag.self_rag_graph import run_self_rag
from src.utils.safety import moderate_text, SafetyLabel


llm = JourneyLLM()
retriever = EventRetriever()


def main_pipeline(query: str, city: Optional[str] = None, date: Optional[str] = None) -> str:
    res = run_self_rag(query, retriever=retriever, llm=llm, city=city, date=date)
    
    # Проверяем, есть ли события
    if not res.events or len(res.events) == 0:
        city_info = f" в городе {city}" if city else ""
        date_info = f" на дату {date}" if date else ""
        return (
            f"❌ Не найдено мероприятий{city_info}{date_info}.\n\n"
            f"Возможные причины:\n"
            f"• В базе данных нет событий для указанного города и даты\n"
            f"• События еще не загружены в систему\n"
            f"• Попробуй указать другую дату или город\n\n"
            f"Попробуй переформулировать запрос или выбрать другую дату."
        )
    
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
