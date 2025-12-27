#!/usr/bin/env python3
"""
Скрипт для создания Telegram session файла.
Запускается через get_telegram_session.sh
"""

import os
import sys
import asyncio
from pathlib import Path


def get_project_root() -> Path:
    """Определяет корень проекта."""
    return Path(__file__).parent.parent


async def create_session():
    """Создаёт Telegram session файл."""
    from telethon import TelegramClient
    from dotenv import load_dotenv
    
    # Загружаем .env из корня проекта
    project_root = get_project_root()
    env_path = project_root / ".env"
    
    if env_path.exists():
        load_dotenv(env_path)
        print(f"✅ Загружен .env файл: {env_path}")
    else:
        print(f"⚠️  .env файл не найден: {env_path}")
        print("   Введите данные вручную или создайте .env файл с переменными:")
        print("   TELEGRAM_APP_API_ID=ваш_api_id")
        print("   TELEGRAM_APP_API_HASH=ваш_api_hash")
        print()
    
    # Получаем credentials
    api_id = os.getenv("TELEGRAM_APP_API_ID")
    api_hash = os.getenv("TELEGRAM_APP_API_HASH")
    
    # Если credentials не найдены в .env, запрашиваем вручную
    if not api_id:
        print("📱 Введите API ID (получить на https://my.telegram.org):")
        api_id = input("> ").strip()
    
    if not api_hash:
        print("🔑 Введите API Hash (получить на https://my.telegram.org):")
        api_hash = input("> ").strip()
    
    if not api_id or not api_hash:
        print("❌ Ошибка: API ID и API Hash обязательны!")
        print("   Получите их на https://my.telegram.org -> API development tools")
        sys.exit(1)
    
    try:
        api_id = int(api_id)
    except ValueError:
        print("❌ Ошибка: API ID должен быть числом!")
        sys.exit(1)
    
    # Путь для session файла - в корне проекта
    session_path = project_root / "tg_session"
    
    print()
    print("=" * 50)
    print("🔐 АВТОРИЗАЦИЯ В TELEGRAM")
    print("=" * 50)
    print()
    print(f"📁 Session будет сохранён: {session_path}.session")
    print()
    
    # Создаём клиент
    client = TelegramClient(str(session_path), api_id, api_hash)
    
    try:
        await client.start()
        
        # Проверяем авторизацию
        me = await client.get_me()
        
        print()
        print("=" * 50)
        print("✅ УСПЕШНО!")
        print("=" * 50)
        print()
        print(f"👤 Авторизован как: {me.first_name} {me.last_name or ''}")
        print(f"📞 Телефон: +{me.phone}")
        print(f"🆔 ID: {me.id}")
        if me.username:
            print(f"📧 Username: @{me.username}")
        print()
        print(f"📁 Session файл создан: {session_path}.session")
        print()
        print("💡 Теперь вы можете использовать этот session файл")
        print("   для парсинга Telegram каналов без повторной авторизации.")
        print()
        
    except Exception as e:
        print(f"❌ Ошибка авторизации: {e}")
        sys.exit(1)
    finally:
        await client.disconnect()


def main():
    """Точка входа."""
    print()
    print("╔" + "═" * 48 + "╗")
    print("║" + " СОЗДАНИЕ TELEGRAM SESSION ".center(48) + "║")
    print("╚" + "═" * 48 + "╝")
    print()
    
    try:
        asyncio.run(create_session())
    except KeyboardInterrupt:
        print("\n\n⚠️  Прервано пользователем")
        sys.exit(0)


if __name__ == "__main__":
    main()

