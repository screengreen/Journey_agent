"""FastAPI приложение для управления синхронизацией каналов."""
from __future__ import annotations

import asyncio
import sqlite3
from typing import List, Dict, Any, Optional
from datetime import datetime

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

from src.sync_worker.config import AppSettings
from src.sync_worker.db_channels import (
    init_db,
    get_active_channels,
    add_channel,
    UserChannel,
)
from src.sync_worker.sync_service import ChannelSyncServiceAsync
from src.sync_worker.tg_parser import TelegramParser
from src.sync_worker.event_miner_agent import EventMinerAgent
from src.vdb import get_weaviate_client, create_collection_if_not_exists, COLLECTION_NAME


app = FastAPI(
    title="Journey Agent Sync API",
    description="API для управления синхронизацией Telegram каналов",
    version="1.0.0",
)

# Глобальные настройки
settings = AppSettings.from_env()

# Флаг для отслеживания синхронизации
sync_in_progress = False
sync_lock = asyncio.Lock()


class ChannelResponse(BaseModel):
    """Модель для ответа с информацией о канале."""
    id: int
    user_id: int
    username: Optional[str]
    channel_name: Optional[str]
    channel_url: str
    is_active: bool
    last_synced_at: Optional[str]


class AddChannelRequest(BaseModel):
    """Модель запроса для добавления канала."""
    user_id: int
    channel_url: str
    username: Optional[str] = None
    channel_name: Optional[str] = None
    is_active: bool = True


class SyncResponse(BaseModel):
    """Модель ответа при запуске синхронизации."""
    status: str
    message: str
    started_at: str


@app.on_event("startup")
async def startup_event():
    """Инициализация при старте приложения."""
    init_db(settings.db_path, seed_test_channels=settings.seed_test_channels)
    print(f"✅ База данных инициализирована: {settings.db_path}")


@app.get("/", tags=["Health"])
async def root():
    """Корневой эндпоинт для проверки работоспособности."""
    return {
        "service": "Journey Agent Sync API",
        "status": "running",
        "version": "1.0.0",
        "database": settings.db_path,
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """Проверка здоровья сервиса."""
    return {
        "status": "healthy",
        "database_path": settings.db_path,
        "weaviate_url": settings.weaviate_url,
        "sync_in_progress": sync_in_progress,
    }


@app.get("/database", tags=["Database"])
async def get_database_info() -> Dict[str, Any]:
    """
    Получить информацию о текущей базе данных.
    
    Возвращает статистику по каналам и последним синхронизациям.
    """
    try:
        conn = sqlite3.connect(settings.db_path)
        conn.row_factory = sqlite3.Row
        
        # Общая статистика
        cursor = conn.execute("SELECT COUNT(*) as total FROM user_channels")
        total_channels = cursor.fetchone()["total"]
        
        cursor = conn.execute("SELECT COUNT(*) as active FROM user_channels WHERE is_active = 1")
        active_channels = cursor.fetchone()["active"]
        
        # Последние синхронизированные каналы
        cursor = conn.execute("""
            SELECT user_id, username, channel_name, channel_url, last_synced_at 
            FROM user_channels 
            WHERE last_synced_at IS NOT NULL 
            ORDER BY last_synced_at DESC 
            LIMIT 10
        """)
        recent_syncs = [dict(row) for row in cursor.fetchall()]
        
        # Все каналы
        cursor = conn.execute("""
            SELECT id, user_id, username, channel_name, channel_url, is_active, last_synced_at, created_at
            FROM user_channels
            ORDER BY created_at DESC
        """)
        all_channels = [dict(row) for row in cursor.fetchall()]
        
        conn.close()
        
        return {
            "database_path": settings.db_path,
            "statistics": {
                "total_channels": total_channels,
                "active_channels": active_channels,
                "inactive_channels": total_channels - active_channels,
            },
            "recent_syncs": recent_syncs,
            "all_channels": all_channels,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при чтении БД: {str(e)}")


@app.get("/channels", response_model=List[ChannelResponse], tags=["Channels"])
async def get_all_channels(
    active_only: bool = Query(False, description="Вернуть только активные каналы")
) -> List[ChannelResponse]:
    """
    Получить список всех каналов.
    
    - **active_only**: если True, вернет только активные каналы
    """
    try:
        if active_only:
            channels = get_active_channels(settings.db_path)
        else:
            conn = sqlite3.connect(settings.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT id, user_id, username, channel_name, channel_url, is_active, last_synced_at
                FROM user_channels
                ORDER BY created_at DESC
            """)
            rows = cursor.fetchall()
            conn.close()
            
            channels = [
                UserChannel(
                    id=row["id"],
                    user_id=row["user_id"],
                    username=row["username"],
                    channel_name=row["channel_name"],
                    channel_url=row["channel_url"],
                    is_active=bool(row["is_active"]),
                    last_synced_at=row["last_synced_at"],
                )
                for row in rows
            ]
        
        return [
            ChannelResponse(
                id=ch.id,
                user_id=ch.user_id,
                username=ch.username,
                channel_name=ch.channel_name,
                channel_url=ch.channel_url,
                is_active=ch.is_active,
                last_synced_at=ch.last_synced_at,
            )
            for ch in channels
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при получении каналов: {str(e)}")


@app.get("/channels/user/{user_id}", response_model=List[ChannelResponse], tags=["Channels"])
async def get_user_channels(user_id: int) -> List[ChannelResponse]:
    """
    Получить все каналы конкретного пользователя.
    
    - **user_id**: Telegram ID пользователя
    """
    try:
        conn = sqlite3.connect(settings.db_path)
        conn.row_factory = sqlite3.Row
        
        cursor = conn.execute("""
            SELECT id, user_id, username, channel_name, channel_url, is_active, last_synced_at
            FROM user_channels
            WHERE user_id = ?
            ORDER BY created_at DESC
        """, (user_id,))
        
        rows = cursor.fetchall()
        conn.close()
        
        if not rows:
            raise HTTPException(status_code=404, detail=f"Каналы для пользователя '{user_id}' не найдены")
        
        return [
            ChannelResponse(
                id=row["id"],
                user_id=row["user_id"],
                username=row["username"],
                channel_name=row["channel_name"],
                channel_url=row["channel_url"],
                is_active=bool(row["is_active"]),
                last_synced_at=row["last_synced_at"],
            )
            for row in rows
        ]
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"Ошибка БД: {str(e)}")


@app.post("/channels", response_model=ChannelResponse, tags=["Channels"])
async def create_channel(request: AddChannelRequest) -> ChannelResponse:
    """
    Добавить новый канал в базу данных.
    
    - **user_id**: Telegram ID пользователя
    - **channel_url**: URL Telegram канала
    - **username**: username пользователя (опционально)
    - **channel_name**: название канала (опционально)
    - **is_active**: активен ли канал (по умолчанию True)
    """
    try:
        channel_id = add_channel(
            settings.db_path,
            request.user_id,
            request.channel_url,
            request.username,
            request.channel_name,
            request.is_active,
        )
        
        if channel_id == -1:
            raise HTTPException(status_code=409, detail="Канал уже существует для этого пользователя")
        
        return ChannelResponse(
            id=channel_id,
            user_id=request.user_id,
            username=request.username,
            channel_name=request.channel_name,
            channel_url=request.channel_url,
            is_active=request.is_active,
            last_synced_at=None,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при добавлении канала: {str(e)}")


@app.post("/sync/trigger", response_model=SyncResponse, tags=["Sync"])
async def trigger_sync() -> SyncResponse:
    """
    Запустить синхронизацию вне очереди.
    
    Запускает процесс синхронизации всех активных каналов немедленно,
    независимо от расписания.
    """
    global sync_in_progress
    
    async with sync_lock:
        if sync_in_progress:
            raise HTTPException(
                status_code=409,
                detail="Синхронизация уже выполняется. Дождитесь завершения."
            )
        
        sync_in_progress = True
    
    started_at = datetime.utcnow().isoformat()
    
    # Запускаем синхронизацию в фоновой задаче
    asyncio.create_task(_run_sync_task())
    
    return SyncResponse(
        status="started",
        message="Синхронизация запущена",
        started_at=started_at,
    )


@app.get("/sync/status", tags=["Sync"])
async def get_sync_status() -> Dict[str, Any]:
    """
    Получить статус синхронизации.
    
    Показывает, выполняется ли синхронизация в данный момент.
    """
    return {
        "sync_in_progress": sync_in_progress,
        "settings": {
            "interval_hours": settings.sync_interval_hours,
            "messages_limit": settings.channel_messages_limit,
            "weaviate_url": settings.weaviate_url,
        },
    }


async def _run_sync_task():
    """
    Внутренняя функция для выполнения синхронизации.
    """
    global sync_in_progress
    
    try:
        print("🚀 Запуск внеочередной синхронизации...")
        
        # Инициализируем компоненты
        parser = TelegramParser()
        event_agent = EventMinerAgent(llm=JourneyLLM())
        
        # Подключаемся к Weaviate
        weaviate_client = get_weaviate_client(url=settings.weaviate_url)
        create_collection_if_not_exists()
        collection = weaviate_client.collections.get(COLLECTION_NAME)
        
        # Создаем сервис синхронизации
        sync_service = ChannelSyncServiceAsync(
            db_path=settings.db_path,
            limit=settings.channel_messages_limit,
            parser=parser,
            event_agent=event_agent,
            weaviate_collection=collection,
        )
        
        # Выполняем синхронизацию
        await sync_service.sync_once()
        
        print("✅ Внеочередная синхронизация завершена")
        
    except Exception as e:
        print(f"❌ Ошибка при синхронизации: {e}")
        import traceback
        traceback.print_exc()
    finally:
        async with sync_lock:
            sync_in_progress = False


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

