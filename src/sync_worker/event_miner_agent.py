"""
Event Miner Agent
LangGraph агент для извлечения событий (лекции, встречи и т.д.) из сообщений Telegram
"""

import json
from typing import List, Dict, Optional, TypedDict, Union

from pydantic import BaseModel
from langgraph.graph import StateGraph, END

# Импорт универсальной модели Event
from src.models.event import Event

# Импорт типа Message из telethon
try:
    from telethon.tl.types import Message as TelegramMessage
except ImportError:
    TelegramMessage = None


class EventsList(BaseModel):
    """Обертка для списка событий для парсинга через OpenAI"""
    events: List[Event] = []


class EventExtractor:
    
    def __init__(self, llm):

        self.llm = llm
    
    @staticmethod
    def _message_to_dict(message: Union[Dict, 'TelegramMessage']) -> Dict:
        if isinstance(message, dict):
            return message
        
        if TelegramMessage and isinstance(message, TelegramMessage):
            return {
                'id': message.id,
                'date': message.date.isoformat() if message.date else None,
                'text': message.message or ""
            }
        
        raise TypeError(f"Неподдерживаемый тип сообщения: {type(message)}")
    
    def extract_events(
        self, 
        messages: List[Union[Dict, 'TelegramMessage']]
    ) -> List[Event]:
        if not messages:
            return []
        
        messages_dict = [self._message_to_dict(msg) for msg in messages]
        
        messages_text = "\n\n".join([
            f"Сообщение #{i+1} (ID: {msg['id']}, Дата: {msg['date']}):\n{msg['text']}"
            for i, msg in enumerate(messages_dict)
        ])
        
        prompt = f"""Проанализируй следующие сообщения из Telegram и извлеки из них все события (лекции, встречи, семинары, конференции и т.д.).

Для каждого события определи:
- title: название события (обязательное)
- description: описание события (обязательное, можешь скопировать из title если нет описания)
- tags: список тегов/категорий события
- location: место проведения (адрес, ссылка на Zoom/Teams, название зала и т.д.)
- date: дата события в формате YYYY-MM-DD
- url: URL события если есть
- source: укажи 'telegram'
- event_type: тип события (лекция, встреча, семинар, конференция, мастер-класс и т.д.) - дополнительное поле
- is_online: True если онлайн, False если офлайн, null если не указано - дополнительное поле
- time: время события в формате HH:MM - дополнительное поле
- source_message_id: ID исходного сообщения - дополнительное поле
- original_text: оригинальный текст из которого извлечено событие - дополнительное поле

Если информации нет, используй null для соответствующих полей.

Сообщения:
{messages_text}

Верни результат СТРОГО в формате JSON массива объектов. Если событий нет, верни пустой массив [].
Отвечай ТОЛЬКО валидным JSON, без дополнительных комментариев и markdown разметки."""

        try:
            if hasattr(self.llm, 'chat') and hasattr(self.llm.chat, 'completions'):
                # Используем встроенный парсинг OpenAI с Pydantic моделью
                # Проверяем наличие метода parse в beta или в основном API
                parse_method = None
                if hasattr(self.llm, 'beta') and hasattr(self.llm.beta, 'chat') and hasattr(self.llm.beta.chat.completions, 'parse'):
                    parse_method = self.llm.beta.chat.completions.parse
                elif hasattr(self.llm.chat.completions, 'parse'):
                    parse_method = self.llm.chat.completions.parse
                
                if parse_method:
                    # Используем метод parse для автоматического парсинга через Pydantic
                    response = parse_method(
                        model="gpt-4o",
                        messages=[
                            {
                                "role": "system",
                                "content": "Ты помощник для извлечения событий из текстовых сообщений."
                            },
                            {"role": "user", "content": prompt}
                        ],
                        response_format=EventsList,
                        temperature=0.3
                    )
                    # Парсинг происходит автоматически через Pydantic модель
                    events_list = response.choices[0].message.parsed
                    events = events_list.events if events_list else []
                else:
                    # Fallback: используем create с response_format через JSON schema
                    response = self.llm.chat.completions.create(
                        model="gpt-4o",
                        messages=[
                            {
                                "role": "system",
                                "content": "Ты помощник для извлечения событий из текстовых сообщений. Отвечаешь только валидным JSON."
                            },
                            {"role": "user", "content": prompt}
                        ],
                        temperature=0.3,
                        response_format={"type": "json_object"}
                    )
                    result_text = response.choices[0].message.content.strip()
                    result_text = self._clean_json_response(result_text)
                    # Используем parse_from_json для парсинга через Pydantic
                    events = self._parse_from_json(result_text)
            else:
                # Fallback для других LLM провайдеров
                try:
                    from langchain_core.messages import HumanMessage
                    messages_lc = [HumanMessage(content=prompt)]
                    response = self.llm.invoke(messages_lc)
                    result_text = response.content.strip()
                    result_text = self._clean_json_response(result_text)
                    events = self._parse_from_json(result_text)
                except Exception:
                    result_text = str(self.llm.invoke(prompt))
                    result_text = self._clean_json_response(result_text)
                    events = self._parse_from_json(result_text)
            
            # Добавляем source_message_id и original_text из исходных сообщений
            for idx, event in enumerate(events):
                if idx < len(messages_dict):
                    # Обновляем через дополнительные атрибуты (работает через extra='allow')
                    if not hasattr(event, 'source_message_id') or not event.source_message_id:
                        setattr(event, 'source_message_id', messages_dict[idx]['id'])
                    if not hasattr(event, 'original_text') or not event.original_text:
                        setattr(event, 'original_text', messages_dict[idx]['text'])
            
            return events
            
        except Exception as e:
            print(f"Ошибка при извлечении событий: {e}")
            return []
    
    def _parse_from_json(self, json_string: str) -> List[Event]:
        """Парсинг JSON в список Event"""
        try:
            parsed_data = json.loads(json_string)
        except json.JSONDecodeError:
            return []
        
        if isinstance(parsed_data, dict):
            events_data = parsed_data.get('events', [])
        elif isinstance(parsed_data, list):
            events_data = parsed_data
        else:
            return []
        
        events = []
        for event_data in events_data:
            if isinstance(event_data, dict):
                try:
                    # Парсим напрямую в Event
                    if hasattr(Event, 'model_validate'):
                        event = Event.model_validate(event_data)
                    else:
                        event = Event.parse_obj(event_data)
                    events.append(event)
                except Exception as e:
                    print(f"Ошибка парсинга события: {e}")
                    continue
        
        return events
    
    @staticmethod
    def _clean_json_response(text: str) -> str:
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        return text.strip()


class AgentState(TypedDict):
    messages: List[Dict]  
    events: List[Event]  
    processed_count: int  


class EventMinerAgent:
    
    def __init__(self, llm, event_extractor: Optional[EventExtractor] = None):
        self.llm = llm
        self.event_extractor = event_extractor or EventExtractor(llm)
        self.graph = self._build_graph()
    
    def _build_graph(self) -> StateGraph:
        workflow = StateGraph(AgentState)
        
        workflow.add_node("extract_events", self._extract_events_node)
        workflow.add_node("validate_events", self._validate_events_node)
        
        workflow.set_entry_point("extract_events")
        workflow.add_edge("extract_events", "validate_events")
        workflow.add_edge("validate_events", END)
        
        return workflow.compile()
    
    def _extract_events_node(self, state: AgentState) -> AgentState:
        messages = state.get("messages", [])
        
        if not messages:
            return {
                **state,
                "events": [],
                "processed_count": 0
            }
        
        events = self.event_extractor.extract_events(messages)
        
        return {
            **state,
            "events": events,
            "processed_count": len(messages)
        }
    
    def _validate_events_node(self, state: AgentState) -> AgentState:
        events = state.get("events", [])
        
        validated_events = [
            event for event in events
            if event.title and event.description
        ]
        
        return {
            **state,
            "events": validated_events
        }
    
    def process_messages(
        self, 
        messages: List[Union[Dict, 'TelegramMessage']]
    ) -> List[Event]:
        messages_dict = [
            EventExtractor._message_to_dict(msg) for msg in messages
        ]
        
        initial_state: AgentState = {
            "messages": messages_dict,
            "events": [],
            "processed_count": 0
        }
        
        final_state = self.graph.invoke(initial_state)
        
        return final_state.get("events", [])
    
    def process_messages_batch(
        self,
        messages: List[Union[Dict, 'TelegramMessage']],
        batch_size: int = 10
    ) -> List[Event]:
        all_events = []
        
        for i in range(0, len(messages), batch_size):
            batch = messages[i:i + batch_size]
            events = self.process_messages(batch)
            all_events.extend(events)
        
        return all_events
