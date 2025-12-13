"""
Единая БД для хранения каналов пользователей.
Используется как TG ботом, так и sync worker.
Использует SQLite для простоты.
"""
import sqlite3
import os
from typing import List, Optional
from pathlib import Path

from src.utils.paths import project_root


class Database:
    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = str(project_root()/ "data"/"channels_db" / "users_channels.db")
        
        db_dir = os.path.dirname(db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        self.db_path = db_path
        self.init_db()
    
    def get_connection(self):
        """Получить соединение с БД"""
        return sqlite3.connect(self.db_path)
    
    def init_db(self):
        """
        Инициализировать таблицы БД.
        Единая схема для TG бота и sync worker.
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_channels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                username TEXT,
                channel_name TEXT,
                channel_url TEXT NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1,
                last_synced_at TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, channel_url)
            )
        """)
        
        conn.commit()
        conn.close()
    
    def add_channel(self, user_id: int, channel_name: str, channel_url: str, 
                    username: Optional[str] = None) -> bool:
        """
        Добавить канал для пользователя.
        
        Args:
            user_id: ID пользователя в Telegram
            channel_name: Название канала для отображения
            channel_url: URL канала
            username: username пользователя (опционально)
        
        Returns:
            True если канал добавлен, False если уже существует или ошибка
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT OR IGNORE INTO user_channels 
                (user_id, username, channel_name, channel_url, is_active)
                VALUES (?, ?, ?, ?, 1)
            """, (user_id, username, channel_name, channel_url))
            
            affected_rows = cursor.rowcount
            conn.commit()
            conn.close()
            return affected_rows > 0
        except Exception as e:
            print(f"Error adding channel: {e}")
            return False
    
    def get_user_channels(self, user_id: int) -> List[dict]:
        """
        Получить все активные каналы пользователя.
        
        Returns:
            Список словарей с ключами: id, name, url, last_synced_at
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, channel_name, channel_url, last_synced_at
            FROM user_channels 
            WHERE user_id = ? AND is_active = 1
            ORDER BY created_at DESC
        """, (user_id,))
        
        channels = [
            {
                "id": row[0],
                "name": row[1], 
                "url": row[2],
                "last_synced_at": row[3]
            } 
            for row in cursor.fetchall()
        ]
        
        conn.close()
        return channels
    
    def delete_channel(self, user_id: int, channel_id: int) -> bool:
        """
        Деактивировать канал пользователя (мягкое удаление).
        
        Args:
            user_id: ID пользователя
            channel_id: ID канала в базе
        
        Returns:
            True если канал деактивирован, False если ошибка
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # Мягкое удаление - ставим is_active = 0
            cursor.execute("""
                UPDATE user_channels 
                SET is_active = 0
                WHERE user_id = ? AND id = ?
            """, (user_id, channel_id))
            
            affected_rows = cursor.rowcount
            conn.commit()
            conn.close()
            return affected_rows > 0
        except Exception as e:
            print(f"Error deleting channel: {e}")
            return False
    
    def delete_channel_by_name(self, user_id: int, channel_name: str) -> bool:
        """
        Деактивировать канал пользователя по имени (для обратной совместимости).
        
        Args:
            user_id: ID пользователя
            channel_name: Название канала
        
        Returns:
            True если канал деактивирован, False если ошибка
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE user_channels 
                SET is_active = 0
                WHERE user_id = ? AND channel_name = ?
            """, (user_id, channel_name))
            
            affected_rows = cursor.rowcount
            conn.commit()
            conn.close()
            return affected_rows > 0
        except Exception as e:
            print(f"Error deleting channel: {e}")
            return False

