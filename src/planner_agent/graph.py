"""
LangGraph граф для системы планирования.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from typing import Literal
from langgraph.graph import StateGraph, END
from src.utils.journey_llm import JourneyLLM
from src.planner_agent.models import GraphState, OutputResult
from src.planner_agent.agents import PlannerAgent, CriticAgent


class PlanningGraph:
    """Граф планирования с агентами планировщиком и критиком."""
    
    def __init__(self, llm: JourneyLLM):
        self.llm = llm or JourneyLLM()
        self.planner = PlannerAgent(self.llm)
        self.critic = CriticAgent(self.llm)
        self.graph = self._build_graph()
    
    def _build_graph(self) -> StateGraph:
        """Построить граф."""
        workflow = StateGraph(GraphState)
        
        # Добавляем узлы
        workflow.add_node("planner_reasoning", self._planner_reasoning_node)
        workflow.add_node("planner_create", self._planner_create_node)
        workflow.add_node("critic", self._critic_node)
        workflow.add_node("planner_revise", self._planner_revise_node)
        
        # Определяем входную точку
        workflow.set_entry_point("planner_reasoning")
        
        # Добавляем переходы
        workflow.add_edge("planner_reasoning", "planner_create")
        workflow.add_edge("planner_create", "critic")
        workflow.add_conditional_edges(
            "critic",
            self._should_revise,
            {
                "revise": "planner_revise",
                "finish": END
            }
        )
        workflow.add_edge("planner_revise", "critic")
        
        return workflow.compile()
    
    def _planner_reasoning_node(self, state) -> GraphState:
        """Узел рассуждений планировщика."""
        print("\n" + "▶"*30)
        print("УЗЕЛ: planner_reasoning")
        print("▶"*30)
        # Преобразуем состояние в GraphState, если это словарь
        if isinstance(state, dict):
            state = GraphState(**state)
        reasoning = self.planner.create_reasoning(state)
        # Создаем новое состояние с обновленными данными
        return state.model_copy(update={"reasoning": reasoning})
    
    def _planner_create_node(self, state) -> GraphState:
        """Узел создания плана."""
        print("\n" + "▶"*30)
        print("УЗЕЛ: planner_create")
        print("▶"*30)
        # Преобразуем состояние в GraphState, если это словарь
        if isinstance(state, dict):
            state = GraphState(**state)
        
        # Планировщик использует LLM с инструментами для создания плана
        plan = self.planner.create_plan(state)
        return state.model_copy(update={"plan": plan})
    
    def _critic_node(self, state) -> GraphState:
        """Узел критики."""
        print("\n" + "▶"*30)
        print("УЗЕЛ: critic")
        print("▶"*30)
        # Преобразуем состояние в GraphState, если это словарь
        if isinstance(state, dict):
            state = GraphState(**state)
        print(f"Итерация: {state.iteration + 1}/{state.max_iterations}")
        critique = self.critic.critique_plan(state)
        # Создаем новое состояние с обновленными данными
        return state.model_copy(update={
            "critique": critique,
            "iteration": state.iteration + 1
        })
    
    def _planner_revise_node(self, state) -> GraphState:
        """Узел пересмотра плана."""
        print("\n" + "▶"*30)
        print("УЗЕЛ: planner_revise")
        print("▶"*30)
        # Преобразуем состояние в GraphState, если это словарь
        if isinstance(state, dict):
            state = GraphState(**state)
        
        plan = self.planner.revise_plan(state)
        return state.model_copy(update={"plan": plan})
    
    def _should_revise(self, state) -> Literal["revise", "finish"]:
        """Определить, нужно ли пересматривать план."""
        # Преобразуем состояние в GraphState, если это словарь
        if isinstance(state, dict):
            state = GraphState(**state)
        if not state.critique:
            print("\n⚠️  Нет критики, завершаю работу")
            return "finish"
        
        # Пересматриваем, если есть критические проблемы или требуется пересмотр
        if state.critique.needs_revision and state.iteration < state.max_iterations:
            print(f"\n🔄 Требуется пересмотр плана (итерация {state.iteration + 1}/{state.max_iterations})")
            return "revise"
        
        # Завершаем, если достигли максимального количества итераций
        if state.iteration >= state.max_iterations:
            print(f"\n⏹️  Достигнуто максимальное количество итераций ({state.max_iterations}), завершаю")
            return "finish"
        
        # Завершаем, если критик не требует пересмотра
        if not state.critique.needs_revision:
            print("\n✅ Критик не требует пересмотра, план принят")
            return "finish"
        
        return "finish"


    
    def run(self, input_data) -> OutputResult:
        """
        Запустить граф.
        
        Args:
            input_data: InputData объект с событиями, промптом и ограничениями
        
        Returns:
            OutputResult с финальным планом
        """
        initial_state = GraphState(
            input_data=input_data,
            iteration=0,
            max_iterations=1
        )
        
        print("\n" + "🚀"*30)
        print("НАЧАЛО РАБОТЫ ГРАФА ПЛАНИРОВАНИЯ")
        print("🚀"*30)
        print(f"Событий для планирования: {len(input_data.events)}")
        print(f"Максимальное количество итераций: {initial_state.max_iterations}")
        
        # Запускаем граф
        final_state_dict = self.graph.invoke(initial_state)
        
        # Преобразуем словарь обратно в GraphState
        if isinstance(final_state_dict, dict):
            final_state = GraphState(**final_state_dict)
        else:
            final_state = final_state_dict
        
        # Формируем выходной результат
        print("\n" + "🏁"*30)
        print("ЗАВЕРШЕНИЕ РАБОТЫ ГРАФА")
        print("🏁"*30)
        print(f"Итоговое количество итераций: {final_state.iteration}")
        result_text = self.planner.render_telegram_message(final_state)
        
        result = OutputResult(
            final_plan=final_state.plan,
            reasoning=final_state.reasoning,
            critique=final_state.critique,
            iterations=final_state.iteration,
            weather_info=final_state.weather_info,
            maps_info=final_state.maps_info,
            web_info=final_state.web_info,
            final_text=result_text
        )
        return result
