"""
Простая БД для хранения каналов пользователей
Использует SQLite для простоты
"""
import sqlite3
import os
from typing import List, Optional
from pathlib import Path


class Database:
    def __init__(self, db_path: str = None):
        # Определяем путь к БД относительно корня проекта
        if db_path is None:
            # Получаем путь к директории этого файла
            current_dir = Path(__file__).parent
            db_path = str(current_dir / "users_channels.db")
        
        # Создаем директорию если её нет (если путь содержит директории)
        db_dir = os.path.dirname(db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        self.db_path = db_path
        self.init_db()
    
    def get_connection(self):
        """Получить соединение с БД"""
        return sqlite3.connect(self.db_path)
    
    def init_db(self):
        """Инициализировать таблицы БД"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_channels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                channel_name TEXT NOT NULL,
                channel_url TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, channel_name)
            )
        """)
        
        conn.commit()
        conn.close()
    
    def add_channel(self, user_id: int, channel_name: str, channel_url: Optional[str] = None) -> bool:
        """Добавить канал для пользователя"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT OR IGNORE INTO user_channels (user_id, channel_name, channel_url)
                VALUES (?, ?, ?)
            """, (user_id, channel_name, channel_url))
            
            conn.commit()
            conn.close()
            return cursor.rowcount > 0
        except Exception as e:
            print(f"Error adding channel: {e}")
            return False
    
    def get_user_channels(self, user_id: int) -> List[dict]:
        """Получить все каналы пользователя"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT channel_name, channel_url 
            FROM user_channels 
            WHERE user_id = ?
            ORDER BY created_at DESC
        """, (user_id,))
        
        channels = [
            {"name": row[0], "url": row[1]} 
            for row in cursor.fetchall()
        ]
        
        conn.close()
        return channels
    
    def delete_channel(self, user_id: int, channel_name: str) -> bool:
        """Удалить канал пользователя"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                DELETE FROM user_channels 
                WHERE user_id = ? AND channel_name = ?
            """, (user_id, channel_name))
            
            conn.commit()
            conn.close()
            return cursor.rowcount > 0
        except Exception as e:
            print(f"Error deleting channel: {e}")
            return False

