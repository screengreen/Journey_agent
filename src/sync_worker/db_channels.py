from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple


TEST_CHANNELS: List[Tuple[int, str, str, str]] = [
    # (user_id, username, channel_name, channel_url)
    (1001, "test_user_1", "Мероприятия", "https://t.me/meropriyatiye"),
    (1002, "test_user_2", "Red Events Moscow", "https://t.me/redeventsmoscow"),
    (1003, "test_user_3", "SPB Gul", "https://t.me/spbgul"),
]


@dataclass
class UserChannel:
    id: int
    user_id: int
    username: Optional[str]
    channel_name: Optional[str]
    channel_url: str
    is_active: bool
    last_synced_at: Optional[str]


def init_db(db_path: str, seed_test_channels: bool = False) -> None:
    """
    Создаёт таблицу с каналами пользователей.
    Единая схема для TG бота и sync worker.

    Если seed_test_channels=True — добавляет тестовые каналы
    (только если их там ещё нет).
    """
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        # Создаем таблицу с объединенной схемой
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_channels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,           -- ID пользователя в Telegram
                username TEXT,                      -- username пользователя (опционально)
                channel_name TEXT,                  -- название канала (для отображения)
                channel_url TEXT NOT NULL,          -- URL телеграм-канала
                is_active INTEGER NOT NULL DEFAULT 1,
                last_synced_at TEXT,                -- ISO-время последней синхронизации
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, channel_url)        -- один пользователь не может добавить канал дважды
            );
            """
        )

        if seed_test_channels:
            _seed_test_channels(conn)

        conn.commit()
    finally:
        conn.close()


def _seed_test_channels(conn: sqlite3.Connection) -> None:
    """
    Добавляет тестовые каналы, если таблица либо пуста,
    либо конкретной пары (user_id, channel_url) ещё нет.

    Работает только внутри init_db, с уже открытым соединением.
    """
    cur = conn.execute("SELECT COUNT(*) FROM user_channels;")
    (count,) = cur.fetchone() or (0,)

    print(f"ℹ️  В таблице user_channels сейчас {count} записей")

    for user_id, username, channel_name, url in TEST_CHANNELS:
        cur = conn.execute(
            """
            SELECT id FROM user_channels
            WHERE user_id = ? AND channel_url = ?
            """,
            (user_id, url),
        )
        row = cur.fetchone()
        if row:
            print(f"  ↳ Тестовый канал уже есть: user_id={user_id}, url={url} (id={row[0]})")
            continue

        cur = conn.execute(
            """
            INSERT INTO user_channels (user_id, username, channel_name, channel_url, is_active)
            VALUES (?, ?, ?, ?, 1)
            """,
            (user_id, username, channel_name, url),
        )
        print(f"  ✅ Добавлен тестовый канал id={cur.lastrowid} | user_id={user_id} | {channel_name} | {url}")


def _row_to_channel(row: sqlite3.Row) -> UserChannel:
    return UserChannel(
        id=row["id"],
        user_id=row["user_id"],
        username=row["username"],
        channel_name=row["channel_name"],
        channel_url=row["channel_url"],
        is_active=bool(row["is_active"]),
        last_synced_at=row["last_synced_at"],
    )


def get_active_channels(db_path: str) -> List[UserChannel]:
    """Возвращает все активные каналы клиентов."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.execute(
            """
            SELECT id, user_id, username, channel_name, channel_url, is_active, last_synced_at
            FROM user_channels
            WHERE is_active = 1
            """
        )
        return [_row_to_channel(r) for r in cur.fetchall()]
    finally:
        conn.close()


def update_last_synced(db_path: str, channel_id: int, when: Optional[datetime] = None) -> None:
    """Обновляет время последней синхронизации для канала."""
    when = when or datetime.utcnow()
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            UPDATE user_channels
            SET last_synced_at = ?
            WHERE id = ?
            """,
            (when.isoformat(), channel_id),
        )
        conn.commit()
    finally:
        conn.close()


def add_channel(db_path: str, user_id: int, channel_url: str, username: Optional[str] = None, 
                channel_name: Optional[str] = None, is_active: bool = True) -> int:
    """
    Добавить канал для пользователя.
    
    Args:
        db_path: путь к базе данных
        user_id: ID пользователя в Telegram
        channel_url: URL канала
        username: username пользователя (опционально)
        channel_name: название канала для отображения (опционально)
        is_active: активен ли канал
    
    Returns:
        ID добавленной записи или -1 если канал уже существует
    """
    conn = sqlite3.connect(db_path)
    try:
        # Проверяем, не добавлен ли уже такой канал для этого пользователя
        cur = conn.execute(
            """
            SELECT id FROM user_channels
            WHERE user_id = ? AND channel_url = ?
            """,
            (user_id, channel_url),
        )
        existing = cur.fetchone()
        if existing:
            return -1  # Канал уже существует
        
        cur = conn.execute(
            """
            INSERT INTO user_channels (user_id, username, channel_name, channel_url, is_active)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user_id, username, channel_name, channel_url, 1 if is_active else 0),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()
