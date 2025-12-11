#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для запуска Telegram бота.

Запуск:
    python scripts/run_bot.py
"""

import sys
from pathlib import Path

# Добавляем корневую директорию проекта в путь
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.bot.bot import create_bot
from src.utils.logging import setup_logging

setup_logging()


def main():
    """Основная функция."""
    try:
        bot = create_bot()
        print("✅ Бот запущен. Нажмите Ctrl+C для остановки.")
        bot.run()
    except KeyboardInterrupt:
        print("\n✅ Бот остановлен.")
    except Exception as e:
        print(f"❌ Ошибка: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

