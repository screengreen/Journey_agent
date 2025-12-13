from src.utils.journey_llm import JourneyLLM
from src.vdb import EventRetriever
from src.planner_agent.graph import PlanningGraph
from src.vdb.rag.self_rag_graph import run_self_rag



llm = JourneyLLM()
retriever = EventRetriever()

def main_pipeline(query: str) -> str:
    res = run_self_rag(query, retriever=retriever, llm=llm)
    graph = PlanningGraph(llm)

    output = graph.run(res)
    return output.final_text
