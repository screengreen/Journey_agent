"""FastAPI приложение для работы с VDB и Self-RAG системой."""
from __future__ import annotations

from typing import Optional, List
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from src.vdb import run_self_rag, check_memory, get_weaviate_client
from src.planner_agent.models import InputData, Constraints
from src.utils.journey_llm import JourneyLLM


app = FastAPI(
    title="Journey Agent VDB API",
    description="API для работы с векторной базой данных и Self-RAG системой",
    version="1.0.0",
)


class SearchRequest(BaseModel):
    """Запрос на поиск событий."""
    query: str = Field(description="Поисковый запрос пользователя")
    owner: Optional[str] = Field(None, description="Владелец (username) для фильтрации событий")
    return_logs: bool = Field(False, description="Вернуть логи выполнения")


class EventResponse(BaseModel):
    """Модель события для ответа."""
    title: str
    description: str
    owner: Optional[str] = None
    location: Optional[str] = None
    country: Optional[str] = None
    date: Optional[str] = None
    url: Optional[str] = None
    source: Optional[str] = None
    tags: Optional[List[str]] = None


class SearchResponse(BaseModel):
    """Ответ на поисковый запрос."""
    events: List[EventResponse]
    user_prompt: str
    constraints: Constraints
    logs: Optional[List[str]] = None


class MemoryCheckRequest(BaseModel):
    """Запрос на проверку памяти."""
    query: str = Field(description="Запрос для проверки")
    owner: Optional[str] = Field(None, description="Владелец (username)")


class MemoryCheckResponse(BaseModel):
    """Ответ на проверку памяти."""
    has_memory: bool
    query: str
    owner: Optional[str] = None


@app.get("/", tags=["Health"])
async def root():
    """Корневой эндпоинт для проверки работоспособности."""
    return {
        "service": "Journey Agent VDB API",
        "status": "running",
        "version": "1.0.0",
        "description": "API для работы с векторной базой данных Weaviate и Self-RAG системой",
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """Проверка здоровья сервиса."""
    try:
        # Проверяем подключение к Weaviate
        client = get_weaviate_client()
        is_ready = client.is_ready()
        client.close()
        
        return {
            "status": "healthy" if is_ready else "unhealthy",
            "weaviate_connected": is_ready,
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
        }


@app.post("/search", response_model=SearchResponse, tags=["Search"])
async def search_events(request: SearchRequest) -> SearchResponse:
    """
    Поиск событий с помощью Self-RAG системы.
    
    - **query**: Поисковый запрос пользователя
    - **owner**: Владелец (username) для фильтрации событий пользователя (опционально)
    - **return_logs**: Вернуть логи выполнения (по умолчанию False)
    """
    try:
        llm = JourneyLLM(temperature=0)
        
        # Запускаем Self-RAG
        if request.return_logs:
            input_data, logs = run_self_rag(
                user_query=request.query,
                owner=request.owner,
                llm=llm.llm,
                return_logs=True,
            )
        else:
            input_data = run_self_rag(
                user_query=request.query,
                owner=request.owner,
                llm=llm.llm,
                return_logs=False,
            )
            logs = None
        
        # Преобразуем события в формат ответа
        events_response = [
            EventResponse(
                title=event.title,
                description=event.description,
                owner=event.owner,
                location=event.location,
                country=event.country,
                date=event.date,
                url=event.url,
                source=event.source,
                tags=event.tags,
            )
            for event in input_data.events
        ]
        
        return SearchResponse(
            events=events_response,
            user_prompt=input_data.user_prompt,
            constraints=input_data.constraints,
            logs=logs,
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при поиске: {str(e)}")


@app.post("/memory/check", response_model=MemoryCheckResponse, tags=["Memory"])
async def check_memory_endpoint(request: MemoryCheckRequest) -> MemoryCheckResponse:
    """
    Проверка наличия памяти для запроса.
    
    - **query**: Запрос для проверки
    - **owner**: Владелец (username) (опционально)
    """
    try:
        has_memory = check_memory(request.query, request.owner)
        
        return MemoryCheckResponse(
            has_memory=has_memory,
            query=request.query,
            owner=request.owner,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при проверке памяти: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)

