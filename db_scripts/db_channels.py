from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple


TEST_CHANNELS: List[Tuple[str, str]] = [
    ("user_test_1", "https://t.me/meropriyatiye"),
    ("user_test_2", "https://t.me/redeventsmoscow"),
    ("user_test_3", "https://t.me/spbgul"),
]


@dataclass
class UserChannel:
    id: int
    username: str
    channel_url: str
    is_active: bool
    last_synced_at: Optional[str]


def init_db(db_path: str, seed_test_channels: bool = False) -> None:
    """
    Создаёт таблицу с каналами пользователей.

    Если seed_test_channels=True — добавляет тестовые каналы
    (только если их там ещё нет).
    """
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_channels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,             -- username клиента
                channel_url TEXT NOT NULL,          -- URL личного телеграм-канала
                is_active INTEGER NOT NULL DEFAULT 1,
                last_synced_at TEXT,                -- ISO-время последней синхронизации
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
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
    либо конкретной пары (username, channel_url) ещё нет.

    Работает только внутри init_db, с уже открытым соединением.
    """
    cur = conn.execute("SELECT COUNT(*) FROM user_channels;")
    (count,) = cur.fetchone() or (0,)

    print(f"ℹ️  В таблице user_channels сейчас {count} записей")

    for username, url in TEST_CHANNELS:
        cur = conn.execute(
            """
            SELECT id FROM user_channels
            WHERE username = ? AND channel_url = ?
            """,
            (username, url),
        )
        row = cur.fetchone()
        if row:
            print(f"  ↳ Тестовый канал уже есть: username={username}, url={url} (id={row[0]})")
            continue

        cur = conn.execute(
            """
            INSERT INTO user_channels (username, channel_url, is_active)
            VALUES (?, ?, 1)
            """,
            (username, url),
        )
        print(f"  ✅ Добавлен тестовый канал id={cur.lastrowid} | username={username} | url={url}")


def _row_to_channel(row: sqlite3.Row) -> UserChannel:
    return UserChannel(
        id=row["id"],
        username=row["username"],
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
            SELECT id, username, channel_url, is_active, last_synced_at
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


def add_channel(db_path: str, username: str, channel_url: str, is_active: bool = True) -> int:
    """Утилита для ручного добавления канала (можно вызвать из админки / миграции)."""
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.execute(
            """
            INSERT INTO user_channels (username, channel_url, is_active)
            VALUES (?, ?, ?)
            """,
            (username, channel_url, 1 if is_active else 0),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()
