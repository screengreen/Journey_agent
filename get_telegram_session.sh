#!/bin/bash
#
# Скрипт для создания Telegram session файла
# Автоматически устанавливает необходимые зависимости
#
# Использование:
#   chmod +x get_telegram_session.sh
#   ./get_telegram_session.sh
#

set -e

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Получаем директорию скрипта (корень проекта)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv_tg_session"
PYTHON_SCRIPT="$SCRIPT_DIR/scripts/create_telegram_session.py"

echo -e "${BLUE}"
echo "╔════════════════════════════════════════════════════╗"
echo "║     🔐 TELEGRAM SESSION CREATOR                    ║"
echo "╚════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Проверяем наличие Python
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
else
    echo -e "${RED}❌ Python не найден! Установите Python 3.8+${NC}"
    exit 1
fi

echo -e "${GREEN}✓${NC} Python найден: $($PYTHON_CMD --version)"

# Проверяем версию Python (минимум 3.8)
PYTHON_VERSION=$($PYTHON_CMD -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
MAJOR=$(echo $PYTHON_VERSION | cut -d'.' -f1)
MINOR=$(echo $PYTHON_VERSION | cut -d'.' -f2)

if [ "$MAJOR" -lt 3 ] || ([ "$MAJOR" -eq 3 ] && [ "$MINOR" -lt 8 ]); then
    echo -e "${RED}❌ Требуется Python 3.8+, найден $PYTHON_VERSION${NC}"
    exit 1
fi

# Создаём временное виртуальное окружение
echo -e "${YELLOW}📦 Создаю временное виртуальное окружение...${NC}"

if [ -d "$VENV_DIR" ]; then
    echo -e "${YELLOW}   Удаляю старое окружение...${NC}"
    rm -rf "$VENV_DIR"
fi

$PYTHON_CMD -m venv "$VENV_DIR"
echo -e "${GREEN}✓${NC} Виртуальное окружение создано"

# Активируем окружение
if [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "win32" ]]; then
    # Windows
    source "$VENV_DIR/Scripts/activate"
else
    # Linux/macOS
    source "$VENV_DIR/bin/activate"
fi

echo -e "${GREEN}✓${NC} Виртуальное окружение активировано"

# Обновляем pip
echo -e "${YELLOW}📦 Обновляю pip...${NC}"
pip install --upgrade pip --quiet

# Устанавливаем только необходимые зависимости
echo -e "${YELLOW}📦 Устанавливаю зависимости (telethon, python-dotenv)...${NC}"
pip install telethon python-dotenv --quiet
echo -e "${GREEN}✓${NC} Зависимости установлены"

# Проверяем наличие Python скрипта
if [ ! -f "$PYTHON_SCRIPT" ]; then
    echo -e "${RED}❌ Скрипт не найден: $PYTHON_SCRIPT${NC}"
    deactivate
    rm -rf "$VENV_DIR"
    exit 1
fi

echo ""
echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  Запускаю скрипт авторизации...${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"
echo ""

# Запускаем Python скрипт
python "$PYTHON_SCRIPT"
EXIT_CODE=$?

# Деактивируем и удаляем временное окружение
deactivate 2>/dev/null || true

echo ""
echo -e "${YELLOW}🧹 Удаляю временное виртуальное окружение...${NC}"
rm -rf "$VENV_DIR"
echo -e "${GREEN}✓${NC} Временные файлы удалены"

if [ $EXIT_CODE -eq 0 ]; then
    echo ""
    echo -e "${GREEN}════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}  ✅ ГОТОВО!${NC}"
    echo -e "${GREEN}════════════════════════════════════════════════════════${NC}"
    echo ""
    echo -e "  Session файл создан: ${BLUE}$SCRIPT_DIR/tg_session.session${NC}"
    echo ""
else
    echo ""
    echo -e "${RED}❌ Произошла ошибка при создании session${NC}"
    exit $EXIT_CODE
fi

