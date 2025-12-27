#!/bin/bash
#
# 🚀 Journey Agent — Скрипт запуска проекта
#
# Этот скрипт:
#   1. Проверяет наличие Docker
#   2. Создаёт/проверяет .env файл с токенами
#   3. Спрашивает о парсинге Telegram каналов
#   4. При необходимости создаёт Telegram session
#   5. Запускает Docker Compose
#
# Использование:
#   chmod +x launch.sh
#   ./launch.sh
#

set -e

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m' # No Color

# Получаем директорию скрипта (корень проекта)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$SCRIPT_DIR/.env"
SESSION_FILE="$SCRIPT_DIR/sessions/tg_session.session"

# ═══════════════════════════════════════════════════════════════
# Функции
# ═══════════════════════════════════════════════════════════════

print_header() {
    echo -e "${BLUE}"
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║                                                              ║"
    echo "║     🗺️  JOURNEY AGENT — Weekend Planner                      ║"
    echo "║                                                              ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

print_step() {
    echo -e "\n${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${MAGENTA}📌 $1${NC}"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"
}

check_command() {
    if ! command -v $1 &> /dev/null; then
        echo -e "${RED}❌ $1 не найден!${NC}"
        echo -e "${YELLOW}   Установите $1 и повторите попытку.${NC}"
        return 1
    fi
    echo -e "${GREEN}✓${NC} $1 найден"
    return 0
}

prompt_yes_no() {
    local prompt="$1"
    local default="$2"
    local response
    
    if [ "$default" = "y" ]; then
        echo -ne "${YELLOW}$prompt [Y/n]: ${NC}"
    else
        echo -ne "${YELLOW}$prompt [y/N]: ${NC}"
    fi
    
    read response
    response=${response:-$default}
    
    case "$response" in
        [yY][eE][sS]|[yY]) return 0 ;;
        *) return 1 ;;
    esac
}

prompt_input() {
    local prompt="$1"
    local default="$2"
    local value
    
    if [ -n "$default" ]; then
        echo -ne "${YELLOW}$prompt [$default]: ${NC}"
    else
        echo -ne "${YELLOW}$prompt: ${NC}"
    fi
    
    read value
    echo "${value:-$default}"
}

check_env_var() {
    local var_name="$1"
    local required="$2"
    local value
    value=$(grep "^${var_name}=" "$ENV_FILE" 2>/dev/null | cut -d'=' -f2-)
    
    # Проверяем что значение не пустое
    if [ -z "$value" ]; then
        if [ "$required" = "true" ]; then
            echo -e "${RED}✗${NC} $var_name — ${RED}НЕ УСТАНОВЛЕН (обязательный)${NC}"
            return 1
        else
            echo -e "${YELLOW}○${NC} $var_name — не установлен (опционально)"
            return 0
        fi
    else
        # Маскируем значение для безопасности
        local masked
        if [ ${#value} -gt 8 ]; then
            masked="${value:0:8}..."
        else
            masked="***"
        fi
        echo -e "${GREEN}✓${NC} $var_name = $masked"
        return 0
    fi
}

# ═══════════════════════════════════════════════════════════════
# Основной скрипт
# ═══════════════════════════════════════════════════════════════

print_header

# ───────────────────────────────────────────────────────────────
# Шаг 1: Проверка зависимостей
# ───────────────────────────────────────────────────────────────
print_step "Шаг 1/5: Проверка зависимостей"

DEPS_OK=true

if ! check_command "docker"; then
    echo -e "${RED}   Установка: https://docs.docker.com/get-docker/${NC}"
    DEPS_OK=false
fi

if ! check_command "docker-compose" && ! docker compose version &> /dev/null; then
    echo -e "${RED}   Docker Compose не найден${NC}"
    DEPS_OK=false
else
    echo -e "${GREEN}✓${NC} docker compose найден"
fi

if [ "$DEPS_OK" = false ]; then
    echo -e "\n${RED}❌ Установите недостающие зависимости и повторите запуск.${NC}"
    exit 1
fi

# Проверяем что Docker daemon запущен
if ! docker info &> /dev/null; then
    echo -e "${RED}❌ Docker daemon не запущен!${NC}"
    echo -e "${YELLOW}   Запустите Docker Desktop или docker daemon${NC}"
    exit 1
fi
echo -e "${GREEN}✓${NC} Docker daemon работает"

# ───────────────────────────────────────────────────────────────
# Шаг 2: Проверка/создание .env файла
# ───────────────────────────────────────────────────────────────
print_step "Шаг 2/5: Настройка переменных окружения (.env)"

if [ ! -f "$ENV_FILE" ]; then
    echo -e "${YELLOW}⚠️  Файл .env не найден. Создаю шаблон...${NC}\n"
    
    cat > "$ENV_FILE" << 'EOF'
# ═══════════════════════════════════════════════════════════════
# 🗺️ Journey Agent — Переменные окружения
# ═══════════════════════════════════════════════════════════════

# ─────────────────────────────────────────────────────────────
# 🤖 Telegram Bot (ОБЯЗАТЕЛЬНО)
# ─────────────────────────────────────────────────────────────
# Получить: https://t.me/BotFather → /newbot
TELEGRAM_BOT_TOKEN=

# ─────────────────────────────────────────────────────────────
# 🧠 OpenAI API (ОБЯЗАТЕЛЬНО)
# ─────────────────────────────────────────────────────────────
# Получить: https://platform.openai.com/api-keys
OPENAI_API_KEY=

# ─────────────────────────────────────────────────────────────
# 📱 Telegram API для парсинга каналов (ОПЦИОНАЛЬНО)
# ─────────────────────────────────────────────────────────────
# Нужно только если хотите парсить Telegram каналы
# Получить: https://my.telegram.org/apps
TELEGRAM_APP_API_ID=
TELEGRAM_APP_API_HASH=

# ─────────────────────────────────────────────────────────────
# 🌤️ Дополнительные сервисы (ОПЦИОНАЛЬНО)
# ─────────────────────────────────────────────────────────────
# OpenWeather для погоды: https://openweathermap.org/api
OPENWEATHER_API_KEY=

# Yandex Maps для геокодирования: https://developer.tech.yandex.ru/
YANDEX_GEOCODER_API_KEY=

# Tavily для веб-поиска: https://tavily.com/
TAVILY_API_KEY=

# ─────────────────────────────────────────────────────────────
# ⚙️ Настройки системы (можно не менять)
# ─────────────────────────────────────────────────────────────
OPENAI_MODEL=gpt-4o
EOF

    echo -e "${GREEN}✓${NC} Файл .env создан: $ENV_FILE"
    echo ""
    echo -e "${YELLOW}📝 Откройте файл .env и заполните обязательные поля:${NC}"
    echo -e "   ${CYAN}• TELEGRAM_BOT_TOKEN${NC} — токен бота от @BotFather"
    echo -e "   ${CYAN}• OPENAI_API_KEY${NC} — API ключ OpenAI"
    echo ""
    echo -e "${YELLOW}После заполнения запустите скрипт снова.${NC}"
    exit 0
fi

echo -e "Проверяю переменные окружения...\n"

# Проверяем обязательные переменные
REQUIRED_OK=true

if ! check_env_var "TELEGRAM_BOT_TOKEN" "true"; then
    REQUIRED_OK=false
fi

if ! check_env_var "OPENAI_API_KEY" "true"; then
    REQUIRED_OK=false
fi

# Проверяем опциональные переменные
echo ""
echo -e "${BLUE}Опциональные переменные:${NC}"
check_env_var "TELEGRAM_APP_API_ID" "false"
check_env_var "TELEGRAM_APP_API_HASH" "false"
check_env_var "OPENWEATHER_API_KEY" "false"
check_env_var "YANDEX_GEOCODER_API_KEY" "false"
check_env_var "TAVILY_API_KEY" "false"

if [ "$REQUIRED_OK" = false ]; then
    echo ""
    echo -e "${RED}❌ Заполните обязательные переменные в файле .env${NC}"
    echo -e "${YELLOW}   Файл: $ENV_FILE${NC}"
    exit 1
fi

# ───────────────────────────────────────────────────────────────
# Шаг 3: Проверка Telegram парсинга
# ───────────────────────────────────────────────────────────────
print_step "Шаг 3/5: Настройка парсинга Telegram каналов"

# Проверяем есть ли API credentials для Telegram
TG_API_ID=$(grep "^TELEGRAM_APP_API_ID=" "$ENV_FILE" 2>/dev/null | cut -d'=' -f2-)
TG_API_HASH=$(grep "^TELEGRAM_APP_API_HASH=" "$ENV_FILE" 2>/dev/null | cut -d'=' -f2-)

ENABLE_TG_PARSING=false
ENABLE_SYNC_WORKER=false

if [ -n "$TG_API_ID" ] && [ -n "$TG_API_HASH" ]; then
    echo -e "${GREEN}✓${NC} Найдены Telegram API credentials"
    echo ""
    echo -e "${BLUE}ℹ️  Парсинг Telegram каналов позволяет:${NC}"
    echo -e "   • Добавлять свои каналы для отслеживания событий"
    echo -e "   • Автоматически извлекать события из сообщений"
    echo -e "   • Синхронизировать данные в фоновом режиме"
    echo ""
    echo -e "${YELLOW}⚠️  ВНИМАНИЕ: Для авторизации потребуется:${NC}"
    echo -e "   • Ввести номер телефона Telegram"
    echo -e "   • Ввести код из Telegram"
    echo ""
    
    if prompt_yes_no "Включить парсинг Telegram каналов?" "y"; then
        ENABLE_TG_PARSING=true
        ENABLE_SYNC_WORKER=true
        
        # Проверяем наличие session файла
        mkdir -p "$SCRIPT_DIR/sessions"
        
        if [ ! -f "$SESSION_FILE" ] && [ ! -f "$SCRIPT_DIR/tg_session.session" ]; then
            echo ""
            echo -e "${YELLOW}📱 Требуется создать Telegram session...${NC}"
            
            if [ -f "$SCRIPT_DIR/get_telegram_session.sh" ]; then
                chmod +x "$SCRIPT_DIR/get_telegram_session.sh"
                "$SCRIPT_DIR/get_telegram_session.sh"
                
                # Перемещаем session файл в папку sessions
                if [ -f "$SCRIPT_DIR/tg_session.session" ]; then
                    mv "$SCRIPT_DIR/tg_session.session" "$SESSION_FILE"
                    echo -e "${GREEN}✓${NC} Session файл создан"
                fi
            else
                echo -e "${RED}❌ Скрипт get_telegram_session.sh не найден${NC}"
                ENABLE_TG_PARSING=false
            fi
        else
            echo -e "${GREEN}✓${NC} Telegram session уже существует"
        fi
    else
        echo -e "${YELLOW}ℹ️  Парсинг Telegram каналов отключён${NC}"
        echo -e "   Система будет работать только с данными из KudaGo"
    fi
else
    echo -e "${YELLOW}ℹ️  Telegram API credentials не настроены${NC}"
    echo -e "   Парсинг Telegram каналов будет недоступен"
    echo -e "   Для настройки добавьте в .env:"
    echo -e "   ${CYAN}• TELEGRAM_APP_API_ID${NC}"
    echo -e "   ${CYAN}• TELEGRAM_APP_API_HASH${NC}"
    echo ""
    echo -e "   Получить: ${BLUE}https://my.telegram.org/apps${NC}"
fi

# ───────────────────────────────────────────────────────────────
# Шаг 4: Сборка Docker образов
# ───────────────────────────────────────────────────────────────
print_step "Шаг 4/5: Сборка Docker образов"

cd "$SCRIPT_DIR"

echo -e "Собираю Docker образы (это может занять несколько минут)...\n"

if [ "$ENABLE_SYNC_WORKER" = true ]; then
    docker compose build --quiet
else
    # Собираем без sync-worker
    docker compose build weaviate api bot --quiet 2>/dev/null || docker compose build --quiet
fi

echo -e "\n${GREEN}✓${NC} Docker образы собраны"

# ───────────────────────────────────────────────────────────────
# Шаг 5: Запуск сервисов
# ───────────────────────────────────────────────────────────────
print_step "Шаг 5/5: Запуск сервисов"

echo -e "Запускаю сервисы...\n"

if [ "$ENABLE_SYNC_WORKER" = true ]; then
    docker compose up -d
else
    # Запускаем без sync-worker
    docker compose up -d weaviate contextionary api bot
fi

# Ждём немного для инициализации
echo -e "\n${YELLOW}⏳ Ожидаю инициализации сервисов...${NC}"
sleep 10

# ───────────────────────────────────────────────────────────────
# Финальный вывод
# ───────────────────────────────────────────────────────────────
echo -e "\n${GREEN}"
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║                                                              ║"
echo "║     ✅ JOURNEY AGENT ЗАПУЩЕН!                                ║"
echo "║                                                              ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

echo -e "${BLUE}📊 Статус сервисов:${NC}"
docker compose ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}"

echo ""
echo -e "${BLUE}🔗 Доступные адреса:${NC}"
echo -e "   • API:      ${CYAN}http://localhost:8000${NC}"
echo -e "   • Swagger:  ${CYAN}http://localhost:8000/docs${NC}"
echo -e "   • Weaviate: ${CYAN}http://localhost:8080${NC}"

echo ""
echo -e "${BLUE}📱 Telegram бот:${NC}"
echo -e "   Найдите вашего бота в Telegram и напишите ${CYAN}/start${NC}"

echo ""
echo -e "${BLUE}📋 Полезные команды:${NC}"
echo -e "   • Логи бота:        ${CYAN}docker compose logs -f bot${NC}"
echo -e "   • Логи API:         ${CYAN}docker compose logs -f api${NC}"
echo -e "   • Логи sync-worker: ${CYAN}docker compose logs -f sync-worker${NC}"
echo -e "   • Остановить:       ${CYAN}docker compose down${NC}"
echo -e "   • Перезапустить:    ${CYAN}docker compose restart${NC}"

if [ "$ENABLE_SYNC_WORKER" = false ]; then
    echo ""
    echo -e "${YELLOW}⚠️  Sync-worker не запущен (парсинг Telegram каналов отключён)${NC}"
fi

echo ""
echo -e "${GREEN}🎉 Готово! Приятного использования!${NC}"
echo ""

