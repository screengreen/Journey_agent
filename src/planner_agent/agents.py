"""
Агенты для системы планирования: планировщик и критик.

Фикс:
- JourneyLLM.parse() не принимает keyword argument 'tools'
- но инструменты можно использовать через llm.llm.bind_tools(...)
- поэтому на время parse подменяем self.llm.llm на self.llm_with_tools
"""

import sys
from pathlib import Path
from typing import Any, Dict, Optional
from contextlib import contextmanager

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.journey_llm import JourneyLLM
from src.planner_agent.models import GraphState, Reasoning, Plan, Critique, InputData
from src.planner_agent.tools import get_all_tools


# ---------------- Helpers ----------------

def _sget(state: Any, key: str, default=None):
    """Безопасно достаёт поле из dict/TypedDict или объекта."""
    if isinstance(state, dict):
        return state.get(key, default)
    return getattr(state, key, default)


def _ensure_input_data(x: Any) -> InputData:
    """Гарантирует InputData (на случай если пришёл dict)."""
    if isinstance(x, InputData):
        return x

    # pydantic v2
    if hasattr(InputData, "model_validate"):
        return InputData.model_validate(x)

    # pydantic v1
    return InputData.parse_obj(x)


def _fmt_event_line(e: Any) -> str:
    # твои события: title, location, date, url, tags...
    title = getattr(e, "title", None) or getattr(e, "name", None) or "Без названия"
    location = getattr(e, "location", None) or getattr(e, "address", None) or "адрес не указан"
    date = getattr(e, "date", None)
    url = getattr(e, "url", None)

    parts = [f"- {title}"]
    if location:
        parts.append(f"({location})")
    if date:
        parts.append(f"время: {date}")
    if url:
        parts.append(f"ссылка: {url}")

    return " — ".join(parts)



@contextmanager
def _temp_bound_tools(journey_llm: JourneyLLM, bound_llm: Any):
    """
    Подменяем journey_llm.llm на версию с bind_tools.
    Это позволяет пользоваться инструментами без передачи tools= в parse().
    """
    old = journey_llm.llm
    journey_llm.llm = bound_llm
    try:
        yield
    finally:
        journey_llm.llm = old


# ---------------- Planner ----------------

class PlannerAgent:
    """Агент планировщик."""

    def __init__(self, llm: JourneyLLM):
        self.llm = llm
        self.tools = get_all_tools()
        self.llm_with_tools = llm.llm.bind_tools(self.tools)

    def create_reasoning(self, state: GraphState) -> Reasoning:
        """Создать рассуждения перед планированием."""
        print("\n" + "=" * 60)
        print("🤔 ПЛАНИРОВЩИК: Начинаю анализ и рассуждения...")
        print("=" * 60)

        input_data = _ensure_input_data(_sget(state, "input_data"))
        events = input_data.events or []
        constraints = input_data.constraints

        print(f"Анализирую {len(events)} событий")

        events_str = "\n".join([_fmt_event_line(e) for e in events])

        constraints_str = f"""
Ограничения:
- Время начала: {constraints.start_time or 'не указано'}
- Время окончания: {constraints.end_time or 'не указано'}
- Максимальное время: {constraints.max_total_time_minutes or 'не указано'} минут
- Предпочтительный транспорт: {constraints.preferred_transport or 'не указано'}
- Бюджет: {constraints.budget or 'не указано'}
- Другие ограничения: {', '.join(constraints.other_constraints) or 'нет'}
""".strip()

        system_prompt = """Ты опытный планировщик маршрутов и походов. 
Твоя задача - проанализировать доступные события и ограничения, чтобы подготовиться к созданию оптимального плана.

Сначала проанализируй ситуацию, выяви важные соображения, возможные проблемы и определи стратегию планирования.
Используй доступные инструменты для получения дополнительной информации (погода, маршруты, информация из интернета), если это необходимо.

При планировании учитывай выбор транспорта:
- Для коротких расстояний (< 10 минут пешком) - walking
- Для длинных расстояний (> 10 минут пешком) - bus или car (выбирай оптимальный)

Доступные инструменты:
- get_route_info: получить информацию о маршруте между двумя адресами (возвращает время для walking, bus, car)
- get_weather_by_address: получить погоду по адресу
- search_web: поиск информации в интернете"""

        user_prompt = f"""Пользователь хочет создать план похода со следующими событиями:

{events_str}

{constraints_str}

Промпт пользователя: {input_data.user_prompt}

Проанализируй ситуацию и подготовь рассуждения перед созданием плана. 
Используй инструменты для получения дополнительной информации, если нужно."""

        print("Отправляю запрос к LLM для анализа...")
        print("💡 LLM может использовать инструменты для получения дополнительной информации")

        # ВАЖНО: tools= НЕ передаём, потому что JourneyLLM.parse не поддерживает
        with _temp_bound_tools(self.llm, self.llm_with_tools):
            reasoning = self.llm.parse(
                Reasoning,
                user_prompt=user_prompt,
                system_prompt=system_prompt,
            )

        print("✅ Рассуждения получены:")
        print(f"   - Соображений: {len(reasoning.considerations)}")
        print(f"   - Проблем выявлено: {len(reasoning.challenges)}")
        print(
            f"   - Стратегия: {reasoning.strategy[:100]}..."
            if len(reasoning.strategy) > 100
            else f"   - Стратегия: {reasoning.strategy}"
        )

        return reasoning

    def create_plan(self, state: GraphState) -> Plan:
        """Создать план на основе событий и ограничений."""
        print("\n" + "=" * 60)
        print("📋 ПЛАНИРОВЩИК: Создаю план похода...")
        print("=" * 60)

        input_data = _ensure_input_data(_sget(state, "input_data"))
        events = input_data.events or []
        constraints = input_data.constraints

        reasoning: Optional[Reasoning] = _sget(state, "reasoning")
        critique: Optional[Critique] = _sget(state, "critique")

        if reasoning:
            print("Использую предыдущие рассуждения")
        if critique:
            print("Учитываю критику предыдущего плана")

        maps_info: Dict = _sget(state, "maps_info", {}) or {}
        weather_info: Dict = _sget(state, "weather_info", {}) or {}
        web_info = _sget(state, "web_info")

        events_str = "\n".join([_fmt_event_line(e) for e in events])

        constraints_str = f"""
Ограничения:
- Время начала: {constraints.start_time or 'не указано'}
- Время окончания: {constraints.end_time or 'не указано'}
- Максимальное время: {constraints.max_total_time_minutes or 'не указано'} минут
- Предпочтительный транспорт: {constraints.preferred_transport or 'не указано'}
- Бюджет: {constraints.budget or 'не указано'}
- Другие ограничения: {', '.join(constraints.other_constraints) or 'нет'}
""".strip()

        reasoning_str = ""
        if reasoning:
            reasoning_str = f"""
Предыдущие рассуждения:
Анализ: {reasoning.analysis}
Соображения: {', '.join(reasoning.considerations)}
Проблемы: {', '.join(reasoning.challenges)}
Стратегия: {reasoning.strategy}
""".strip()

        critique_str = ""
        if critique:
            critique_str = f"""
Критика предыдущего плана:
Общая оценка: {critique.overall_assessment}
Сильные стороны: {', '.join(critique.strengths)}
Слабые стороны: {', '.join(critique.weaknesses)}
Предложения: {', '.join(critique.suggestions)}
Критические проблемы: {', '.join(critique.critical_issues)}
""".strip()

        weather_info_str = ""
        if weather_info:
            weather_info_str = "\nИнформация о погоде:\n"
            for address, w_data in weather_info.items():
                if isinstance(w_data, dict) and w_data.get("success"):
                    weather_info_str += (
                        f"- {address}: {w_data.get('description', 'N/A')}, "
                        f"температура: {w_data.get('temperature', 'N/A')}°C\n"
                    )

        maps_info_str = ""
        if maps_info:
            maps_info_str = "\n📍 ВАЖНО: Информация о времени в пути между событиями:\n"
            maps_info_str += "СРАВНИВАЙ время для разных видов транспорта и выбирай оптимальный!\n"
            maps_info_str += "Рекомендация: если walking > 10 минут, используй bus или car (выбирай самый быстрый).\n\n"
            for route_key, route_data in maps_info.items():
                if not isinstance(route_data, dict) or not route_data.get("success"):
                    continue
                modes = route_data.get("modes", {}) or {}
                maps_info_str += f"Маршрут: {route_key}\n"

                sorted_modes = sorted(
                    modes.items(),
                    key=lambda x: (x[1] or {}).get("duration_min", float("inf")),
                )

                for mode, mode_info in sorted_modes:
                    mode_info = mode_info or {}
                    duration_min = mode_info.get("duration_min", 0) or 0
                    distance_km = mode_info.get("distance_km", 0) or 0

                    hours = int(duration_min // 60)
                    minutes = int(duration_min % 60)
                    time_str = f"{hours}ч {minutes}мин" if hours > 0 else f"{minutes}мин"

                    recommendation = ""
                    if mode == "walking" and duration_min > 10:
                        recommendation = " ⚠️ (слишком долго, лучше использовать bus/car)"
                    elif sorted_modes and mode == sorted_modes[0][0]:
                        recommendation = " ✅ (самый быстрый вариант)"

                    maps_info_str += f"  • {mode}: {time_str} ({distance_km:.2f} км){recommendation}\n"
                maps_info_str += "\n"

        web_info_str = f"\nИнформация из интернета: {web_info}\n" if web_info else ""

        if maps_info_str:
            route_instruction = """
КРИТИЧЕСКИ ВАЖНО: Используй точные данные о времени в пути из раздела ниже!
Для каждого перехода между событиями:
1. Сравни время в пути для всех видов транспорта (walking, bus, car)
2. Выбирай оптимальный транспорт:
   - Если walking < 10 минут → используй walking
   - Если walking > 10 минут → используй bus или car (выбирай самый быстрый)
3. Бери время в пути из предоставленных данных для выбранного транспорта, а не придумывай сам.
""".strip()
        else:
            route_instruction = """
КРИТИЧЕСКИ ВАЖНО: Для получения точного времени в пути между событиями ОБЯЗАТЕЛЬНО используй инструмент get_route_info!
Инструмент вернет время для walking, bus и car - сравнивай их и выбирай оптимальный:
- Если walking < 10 минут → используй walking
- Если walking > 10 минут → используй bus или car (выбирай самый быстрый)
Не придумывай время в пути сам - всегда вызывай инструмент для каждой пары событий.
""".strip()

        system_prompt = """Ты опытный планировщик маршрутов и походов. 
Твоя задача - создать оптимальный план похода, учитывая все события, ограничения и доступную информацию.

ВАЖНО: Используй точные данные о времени в пути между событиями! Если информация о маршрутах не предоставлена, используй инструменты для её получения.
План должен быть реалистичным, учитывать время в пути между событиями, погодные условия и другие факторы.
Если есть критика предыдущего плана, обязательно учти её при создании нового плана.

ВЫБОР ТРАНСПОРТА:
- Если время в пути пешком (walking) меньше 10 минут - используй walking (пешком)
- Если время в пути пешком больше 10 минут - используй bus (автобус) или car (машина), если доступно
- Всегда сравнивай время в пути для разных видов транспорта и выбирай самый быстрый и удобный вариант
- Учитывай предпочтения пользователя из ограничений, но не следуй им слепо, если это неоптимально

Доступные инструменты:
- get_route_info: получить информацию о маршруте между двумя адресами (ОБЯЗАТЕЛЬНО используй для получения точного времени в пути!)
  Этот инструмент возвращает время в пути для walking, car и bus - сравнивай их и выбирай оптимальный!
- get_weather_by_address: получить погоду по адресу
- search_web: поиск информации в интернете"""

        user_prompt = f"""Создай план похода со следующими событиями:

{events_str}

{constraints_str}

{reasoning_str}

{critique_str}

{weather_info_str if weather_info_str else ""}

{maps_info_str if maps_info_str else ""}

{web_info_str if web_info_str else ""}

Промпт пользователя: {input_data.user_prompt}

{route_instruction}

Создай детальный план, который включает все обязательные события и максимально возможное количество других событий с учетом ограничений.
Для каждого события укажи:
- Время начала и окончания
- Режим транспорта (walking, car, bus) - ВЫБИРАЙ ОПТИМАЛЬНЫЙ на основе времени в пути:
  * walking - только если время в пути < 10 минут
  * bus или car - если время в пути пешком > 10 минут (выбирай самый быстрый вариант)
- Время в пути до этого события (в минутах) - ИСПОЛЬЗУЙ ТОЧНЫЕ ДАННЫЕ ИЗ МАРШРУТОВ для выбранного транспорта!

ВАЖНО: При выборе транспорта сравнивай время в пути для всех доступных вариантов (walking, bus, car) и выбирай самый быстрый и удобный!

Даже если тебе не хватает данных (например, отсутствует информация о маршрутах, времени в пути или других деталях), ОБЯЗАТЕЛЬНО все равно составь итоговый план похода на основе доступной информации, с учетом всех имеющихся ограничений и событий.
Если чего-то не хватает, используй инструменты для получения информации, но всё равно выдай итоговый детальный план."""

        print("Отправляю запрос к LLM для создания плана...")
        print("💡 LLM может использовать инструменты для получения информации о маршрутах и погоде")

        # ВАЖНО: tools= НЕ передаём
        with _temp_bound_tools(self.llm, self.llm_with_tools):
            plan = self.llm.parse(
                Plan,
                user_prompt=user_prompt,
                system_prompt=system_prompt,
            )

        print("✅ План создан:")
        print(f"   - Событий в плане: {len(plan.items)}")
        print(f"   - Общая продолжительность: {plan.total_duration_minutes} минут")
        print(f"   - Время в пути: {plan.total_travel_time_minutes} минут")
        print(f"   - Включено событий: {len(plan.included_events)}")
        if plan.excluded_events:
            print(f"   - Исключено событий: {len(plan.excluded_events)}")

        return plan

    def revise_plan(self, state: GraphState):
        """Пересмотреть план на основе критики."""
        print("\n" + "=" * 60)
        print("🔄 ПЛАНИРОВЩИК: Пересматриваю план на основе критики...")
        print("=" * 60)

        critique: Optional[Critique] = _sget(state, "critique")
        if critique:
            print(f"Учитываю критику: {len(critique.suggestions)} предложений, {len(critique.critical_issues)} критических проблем")

        return self.create_plan(state)
    def render_telegram_message(self, state: GraphState) -> str:
        """Красивый форматированный текст маршрута для Telegram."""
        plan = _sget(state, "final_plan") or _sget(state, "plan")
        if not plan:
            return "❌ Не удалось составить план."

        # если модель вернула пустой items — верни хотя бы summary
        if not getattr(plan, "items", None):
            return getattr(plan, "summary", None) or "❌ Не удалось составить план."

        lines: list[str] = []
        
        # Заголовок
        lines.append("🗺 ТВОЙ МАРШРУТ НА СЕГОДНЯ")
        lines.append("━" * 28)
        lines.append("")
        
        # Эмодзи для разных видов транспорта
        transport_emoji = {
            "walking": "🚶",
            "walk": "🚶",
            "пешком": "🚶",
            "bus": "🚌",
            "автобус": "🚌",
            "car": "🚗",
            "машина": "🚗",
            "такси": "🚕",
            "taxi": "🚕",
            "metro": "🚇",
            "метро": "🚇",
            "bike": "🚲",
            "велосипед": "🚲",
        }
        
        # Эмодзи для нумерации
        number_emoji = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]

        for i, item in enumerate(plan.items):
            # Номер с эмодзи
            num = number_emoji[i] if i < len(number_emoji) else f"▸ {i + 1}."
            
            # Форматирование времени
            start = str(item.start_time)[:5] if item.start_time else "—"
            end = str(item.end_time)[:5] if item.end_time else "—"
            time_str = f"🕐 {start} — {end}"
            
            # Название события
            event_name = item.event_name or "Без названия"
            
            # Адрес
            address = getattr(item, "event_address", None)
            address_line = f"📍 {address}" if address else ""
            
            # Транспорт
            transport = getattr(item, "transport_mode", None) or ""
            transport_lower = transport.lower() if transport else ""
            t_emoji = transport_emoji.get(transport_lower, "➡️")
            
            travel_time = getattr(item, "travel_time_minutes", None)
            if travel_time and i > 0:
                transport_line = f"{t_emoji} {transport}, {travel_time} мин в пути"
            elif transport and i > 0:
                transport_line = f"{t_emoji} {transport}"
            else:
                transport_line = ""
            
            # Заметки
            notes = getattr(item, "notes", None)
            notes_line = f"💡 {notes}" if notes else ""
            
            # Собираем блок
            lines.append(f"{num}  {event_name}")
            lines.append(f"    {time_str}")
            if address_line:
                lines.append(f"    {address_line}")
            if transport_line:
                lines.append(f"    {transport_line}")
            if notes_line:
                lines.append(f"    {notes_line}")
            lines.append("")
        
        # Итоговая статистика
        lines.append("━" * 28)
        lines.append("📊 ИТОГО:")
        
        total_duration = getattr(plan, "total_duration_minutes", None)
        total_travel = getattr(plan, "total_travel_time_minutes", None)
        
        if total_duration:
            hours = total_duration // 60
            mins = total_duration % 60
            if hours > 0:
                lines.append(f"⏱ Общее время: {hours}ч {mins}мин")
            else:
                lines.append(f"⏱ Общее время: {mins} мин")
        
        if total_travel:
            lines.append(f"🚶 В пути: {total_travel} мин")
        
        lines.append(f"📍 Мест в маршруте: {len(plan.items)}")
        
        # Краткое описание плана, если есть
        summary = getattr(plan, "summary", None)
        if summary:
            lines.append("")
            lines.append(f"💬 {summary}")
        
        lines.append("")
        lines.append("✨ Хорошего дня!")

        return "\n".join(lines)

# ---------------- Critic ----------------

class CriticAgent:
    """Агент критик."""

    def __init__(self, llm: JourneyLLM):
        self.llm = llm
        self.tools = get_all_tools()
        self.llm_with_tools = llm.llm.bind_tools(self.tools)

    def critique_plan(self, state: GraphState) -> Critique:
        """Проанализировать план и дать критику."""
        print("\n" + "=" * 60)
        print("🔍 КРИТИК: Анализирую план...")
        print("=" * 60)

        plan: Optional[Plan] = _sget(state, "final_plan") or _sget(state, "plan")
        if not plan:
            raise ValueError("Нет плана для критики")

        input_data = _ensure_input_data(_sget(state, "input_data"))
        events = input_data.events or []
        constraints = input_data.constraints

        print(f"Анализирую план с {len(plan.items)} событиями")
        print(f"Общая продолжительность: {plan.total_duration_minutes} минут")

        plan_str = f"""
План:
Общая продолжительность: {plan.total_duration_minutes} минут
Общее время в пути: {plan.total_travel_time_minutes} минут
Краткое описание: {plan.summary}

Элементы плана:
""".strip()

        for item in plan.items:
            plan_str += f"""

- {item.event_name} ({item.event_address})
  Время: {item.start_time} - {item.end_time}
  Продолжительность: {item.duration_minutes} минут
  Транспорт: {item.transport_mode}
  Время в пути: {item.travel_time_minutes or 'не указано'} минут
  Заметки: {item.notes}
""".rstrip()

        events_str = "\n".join([_fmt_event_line(e) for e in events])

        constraints_str = f"""
Ограничения:
- Время начала: {constraints.start_time or 'не указано'}
- Время окончания: {constraints.end_time or 'не указано'}
- Максимальное время: {constraints.max_total_time_minutes or 'не указано'} минут
- Предпочтительный транспорт: {constraints.preferred_transport or 'не указано'}
- Бюджет: {constraints.budget or 'не указано'}
- Другие ограничения: {', '.join(constraints.other_constraints) or 'нет'}
""".strip()

        weather_info = _sget(state, "weather_info")
        maps_info = _sget(state, "maps_info")

        weather_info_str = f"\nИнформация о погоде: {weather_info}\n" if weather_info else ""
        maps_info_str = f"\nИнформация о маршрутах: {maps_info}\n" if maps_info else ""

        system_prompt = """Ты опытный критик планов маршрутов и походов.
Твоя задача - тщательно проанализировать предложенный план, выявить его сильные и слабые стороны,
найти возможные проблемы и предложить конкретные улучшения.

Будь конструктивным, но честным. Укажи как на сильные стороны, так и на проблемы.
Если нужно проверить информацию (например, погоду или маршруты), используй доступные инструменты."""

        user_prompt = f"""Проанализируй следующий план похода:

{plan_str}

Исходные события:
{events_str}

{constraints_str}

{weather_info_str}

{maps_info_str}

Промпт пользователя: {input_data.user_prompt}

Оцени план по следующим критериям:
1. Соответствие ограничениям (время, транспорт, бюджет)
2. Реалистичность временных интервалов
3. Логичность последовательности событий
4. Учет всех обязательных событий
5. Оптимальность использования времени
6. Учет погодных условий и других факторов

Дай конструктивную критику с конкретными предложениями по улучшению."""

        print("Отправляю запрос к LLM для анализа плана...")
        print("💡 LLM может использовать инструменты для проверки информации")

        # ВАЖНО: tools= НЕ передаём
        with _temp_bound_tools(self.llm, self.llm_with_tools):
            critique = self.llm.parse(
                Critique,
                user_prompt=user_prompt,
                system_prompt=system_prompt,
            )

        print("✅ Критика получена:")
        print(f"   - Сильных сторон: {len(critique.strengths)}")
        print(f"   - Слабых сторон: {len(critique.weaknesses)}")
        print(f"   - Предложений: {len(critique.suggestions)}")
        print(f"   - Критических проблем: {len(critique.critical_issues)}")
        print(f"   - Требуется пересмотр: {'Да' if critique.needs_revision else 'Нет'}")

        return critique
