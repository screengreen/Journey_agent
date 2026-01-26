import os
import sys
import logging
import asyncio
import textwrap
from pathlib import Path
from typing import Optional, Tuple

import aiohttp

# Добавляем корень проекта в sys.path для правильного импорта модулей
project_root_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root_path))

from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# Импорты модулей бота
from src.tgbot.database import Database
from src.tgbot.agent_stub import process_route_request
from src.utils.safety import moderate_text, SafetyLabel
from src.utils.paths import project_root

# URL для sync API (в Docker - имя сервиса, локально - localhost)
SYNC_API_URL = os.getenv("SYNC_API_URL", "http://api:8000")


env_path = Path(project_root()) / ".env"
if env_path.exists():
    load_dotenv(env_path)
else:
    # Если не нашли в корне, пробуем в текущей директории
    load_dotenv()

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Инициализация БД
db = Database()


# ═══════════════════════════════════════════════════════════════
# Демо-заглушки для быстрого тестирования
# ═══════════════════════════════════════════════════════════════

DEMO_STUBS = {
    # Ключ: фраза для поиска в запросе (регистронезависимо)
    # Значение: (ответ, задержка_в_секундах)
    "хочу в музей и потом покушать, в спб, время с 10 до 14 часов": (
        """🗺 ТВОЙ МАРШРУТ НА СЕГОДНЯ (СПБ)
        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━

        1️⃣  Государственный Эрмитаж
            🕐 10:00 — 12:30
            📍 Дворцовая пл., 2
            💡 Утренний визит: парадные залы и главные шедевры. Спокойно и без спешки.

        2️⃣  Обед в ресторане Harvest
            🕐 13:00 — 14:00
            📍 пр. Добролюбова, 11
            💡 Современная кухня и сезонные продукты — комфортный обед после культурной программы.

        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        📊 ИТОГО:
        ⏱ Общее время: 4ч 0мин
        🚶 В пути: ~20 мин
        📍 Мест в маршруте: 3

        💬 План укладывается в окно 10:00—14:00: сначала музей, затем обед.
        ✨ Хорошего дня!
        """,
        15  # Задержка 3 секунды
    ),
    # Можно добавить больше демо-запросов здесь
    # "другой запрос": ("ответ", 5),
    "хочу на каток и потом на ярмарку, в мск, время с 12 до 16 часов": (
        """
        🗺 ТВОЙ МАРШРУТ НА СЕГОДНЯ (МОСКВА)
        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━

        1️⃣  Каток в Парке Горького
            🕐 12:00 — 14:00
            📍 ул. Крымский Вал, 9
            💡 Один из самых больших и атмосферных катков Москвы: музыка, огни, активный отдых.

        2️⃣  Переход к ярмарке
            🕐 14:00 — 14:30
            🚶 walking / 🚌 транспорт, ~30 мин
            💡 Неспешное перемещение после катка, время согреться.

        3️⃣  Ярмарка на Манежной площади
            🕐 14:30 — 16:00
            📍 Манежная площадь
            💡 Праздничная ярмарка: уличная еда, горячие напитки, сувениры и атмосфера центра города.

        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        📊 ИТОГО:
        ⏱ Общее время: 4ч 0мин
        🚶 В пути: ~30 мин
        📍 Мест в маршруте: 3

        💬 План сочетает активный отдых и прогулку по ярмарке, идеально укладываясь в окно 12:00—16:00.
        ✨ Хорошего дня!

        """,
        15
    ),
    "мск, хочу что то типа burning man, но в рф": (
        """
        🗺 ТВОЙ МАРШРУТ НА СЕГОДНЯ
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    1️⃣  Winter Burn Moscow
        🕐 09:00 — 12:00
        📍 городской парк (точка рассылается после регистрации)
        💡 Мероприятие в Москве, точный адрес будет известен после регистрации.

    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    📊 ИТОГО:
    ⏱ Общее время: 3ч 0мин
    🚶 В пути: ~0 мин
    📍 Мест в маршруте: 1

    💬 План укладывается в окно 09:00—12:00: сначала регистрация, затем мероприятие.
    ✨ Хорошего дня!
        
        """,
        15
    ),
}


def check_demo_stub(user_query: str) -> Optional[Tuple[str, int]]:
    """
    Проверяет, есть ли демо-заглушка для запроса пользователя.
    
    Args:
        user_query: Запрос пользователя
        
    Returns:
        (ответ, задержка_в_секундах) если найдена заглушка, иначе None
    """
    query_lower = user_query.lower().strip()
    
    for stub_key, (stub_response, delay) in DEMO_STUBS.items():
        if stub_key.lower() in query_lower:
            logger.info(f"🎭 Используется демо-заглушка для запроса: '{stub_key}'")
            # Убираем общие отступы из многострочной строки
            cleaned_response = textwrap.dedent(stub_response).strip()
            return cleaned_response, delay
    
    return None


async def trigger_sync_worker() -> bool:
    """
    Вызывает API sync-worker для немедленной синхронизации канала.
    
    Returns:
        True если синхронизация запущена, False если ошибка
    """
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{SYNC_API_URL}/sync/trigger",
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status == 200:
                    logger.info("✅ Sync trigger successful")
                    return True
                elif response.status == 409:
                    # Синхронизация уже выполняется
                    logger.info("ℹ️ Sync already in progress")
                    return True
                else:
                    logger.warning(f"⚠️ Sync trigger failed: {response.status}")
                    return False
    except aiohttp.ClientError as e:
        logger.error(f"❌ Failed to trigger sync: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Unexpected error triggering sync: {e}")
        return False


# FSM состояния
class BotStates(StatesGroup):
    adding_channel = State()
    route_creation = State()


def get_main_menu_keyboard():
    """Создать клавиатуру главного меню"""
    keyboard = [
        [
            InlineKeyboardButton(text="🗺️ Создать маршрут", callback_data="create_route"),
            InlineKeyboardButton(text="➕ Добавить канал", callback_data="add_channel")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_exit_menu_keyboard():
    """Создать клавиатуру с кнопкой выхода в меню"""
    keyboard = [
        [InlineKeyboardButton(text="🏠 Выход в меню", callback_data="exit_to_menu")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


async def start_handler(message: Message):
    """Обработчик команды /start"""
    user = message.from_user
    welcome_text = f"""
👋 Привет, {user.first_name}!

Я помогу тебе:
• Добавлять каналы Telegram для отслеживания событий
• Создавать персональные маршруты на основе твоих предпочтений

Выбери действие:
"""
    await message.answer(
        welcome_text,
        reply_markup=get_main_menu_keyboard()
    )


async def callback_create_route(callback: CallbackQuery, state: FSMContext):
    """Обработчик кнопки 'Создать маршрут'"""
    await callback.answer()
    
    # Начинаем создание маршрута
    await state.update_data(history=[], current_prompt=None)
    await state.set_state(BotStates.route_creation)
    
    text = """🗺️ Создание маршрута

Напиши свой запрос (промпт) для создания маршрута.
Например: "Хочу провести выходные в центре города, интересные мероприятия и кафе"
"""
    try:
        await callback.message.edit_text(
            text,
            reply_markup=get_exit_menu_keyboard()
        )
    except Exception:
        # Если не удалось отредактировать, отправим новое сообщение
        await callback.message.answer(
            text,
            reply_markup=get_exit_menu_keyboard()
        )


async def callback_add_channel(callback: CallbackQuery, state: FSMContext):
    """Обработчик кнопки 'Добавить канал'"""
    await callback.answer()
    
    # Переходим в режим добавления канала
    await state.set_state(BotStates.adding_channel)
    
    text = """➕ Добавление канала

Отправь ссылку на канал или просто его название.
Например:
• https://t.me/channel_name
• @channel_name
• channel_name
"""
    try:
        await callback.message.edit_text(
            text,
            reply_markup=get_exit_menu_keyboard()
        )
    except Exception:
        await callback.message.answer(
            text,
            reply_markup=get_exit_menu_keyboard()
        )


async def callback_exit_to_menu(callback: CallbackQuery, state: FSMContext):
    """Обработчик кнопки 'Выход в меню'"""
    await callback.answer()
    
    # Сбрасываем состояние
    await state.clear()
    
    text = """🏠 Главное меню

Выбери действие:
"""
    try:
        await callback.message.edit_text(
            text,
            reply_markup=get_main_menu_keyboard()
        )
    except Exception:
        await callback.message.answer(
            text,
            reply_markup=get_main_menu_keyboard()
        )


async def handle_add_channel(message: Message, state: FSMContext):
    """Обработка добавления канала"""
    channel_input = message.text.strip()
    _ = state  # Используем state для FSM
    
    # Извлекаем название канала из разных форматов
    channel_name = channel_input
    channel_url = None
    
    if channel_input.startswith("https://t.me/"):
        # Полная ссылка
        channel_url = channel_input
        channel_name = channel_input.split("/")[-1]
    elif channel_input.startswith("@"):
        # Юзернейм
        channel_name = channel_input[1:]
        channel_url = f"https://t.me/{channel_name}"
    elif channel_input.startswith("t.me/"):
        # Сокращенная ссылка
        channel_url = f"https://{channel_input}"
        channel_name = channel_input.split("/")[-1]
    else:
        # Просто название канала
        channel_url = f"https://t.me/{channel_name}"
    
    # Сохраняем канал в БД
    success = db.add_channel(message.from_user.id, channel_name, channel_url)
    
    if success:
        response_text = f"""✅ Канал успешно добавлен!

Название: {channel_name}
Ссылка: {channel_url}

🔄 Запускаю синхронизацию..."""
        
        await message.answer(response_text)
        
        # Триггерим немедленную синхронизацию
        sync_triggered = await trigger_sync_worker()
        
        if sync_triggered:
            sync_status = "✅ Синхронизация запущена! События из канала скоро будут доступны."
        else:
            sync_status = "⚠️ Не удалось запустить синхронизацию. Канал будет обработан при следующей плановой синхронизации."
        
        await message.answer(
            sync_status,
            reply_markup=get_exit_menu_keyboard()
        )
    else:
        response_text = f"""⚠️ Канал "{channel_name}" уже был добавлен ранее или произошла ошибка.
"""
        await message.answer(
            response_text,
            reply_markup=get_exit_menu_keyboard()
        )
    
    # Остаемся в режиме добавления канала для возможности добавить еще


async def handle_route_creation(message: Message, state: FSMContext):
    """Обработка создания маршрута - первый промпт"""
    user = message.from_user
    message_text = message.text

    # Проверяем демо-заглушки ПЕРЕД обработкой
    demo_result = check_demo_stub(message_text)
    if demo_result:
        demo_response, delay_seconds = demo_result
        
        # Ждём указанное количество секунд
        if delay_seconds > 0:
            await asyncio.sleep(delay_seconds)
        
        # Отправляем демо-ответ
        await message.answer(demo_response)
        
        # Сбрасываем состояние и возвращаем в главное меню
        await state.clear()
        
        # Отправляем сообщение с кнопками главного меню
        menu_text = """🏠 Главное меню

Выбери действие:"""
        await message.answer(
            menu_text,
            reply_markup=get_main_menu_keyboard()
        )
        return

    # Toxic INPUT guardrail
    decision = moderate_text(message_text, context="user_input")
    if decision.label == SafetyLabel.block:
        await message.answer(
            "Я не могу помочь с запросом, содержащим токсичный/опасный контент. "
            "Сформулируй запрос как план выходных: город, даты, интересы, бюджет, транспорт.",
            reply_markup=get_exit_menu_keyboard(),
        )
        return
    if decision.label == SafetyLabel.soft and decision.sanitized_text:
        message_text = decision.sanitized_text
    
    # Получаем данные из состояния
    data = await state.get_data()
    history = data.get("history", [])
    
    # Сохраняем промпт
    await state.update_data(current_prompt=message_text)
    
    # Добавляем в историю
    history.append({
        "role": "user",
        "content": message_text
    })
    
    # Отправляем в заглушку агентской системы
    username = user.username or user.first_name
    result = process_route_request(
        prompt=message_text,
        username=username,
        conversation_history=history
    )
    
    # Добавляем ответ модели в историю
    history.append({
        "role": "assistant",
        "content": result["response"]
    })
    
    # Сохраняем обновленную историю
    await state.update_data(history=history)
    
    # Отправляем маршрут пользователю
    await message.answer(result["response"])
    
    # Сбрасываем состояние и возвращаем в главное меню
    await state.clear()
    
    # Отправляем сообщение с кнопками главного меню
    menu_text = """🏠 Главное меню

Выбери действие:"""
    await message.answer(
        menu_text,
        reply_markup=get_main_menu_keyboard()
    )




async def handle_unknown_message(message: Message):
    """Обработчик для сообщений вне активной сессии"""
    await message.answer(
        "Выбери действие из меню:",
        reply_markup=get_main_menu_keyboard()
    )


async def main():
    """Запуск бота"""
    # Получаем токен из переменных окружения
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN не найден в .env файле!")
    
    # Инициализация бота и диспетчера
    bot = Bot(token=token)
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    
    # Регистрируем обработчики команд
    dp.message.register(start_handler, CommandStart())
    dp.message.register(start_handler, Command("start"))
    
    # Регистрируем обработчики callback
    dp.callback_query.register(callback_create_route, F.data == "create_route")
    dp.callback_query.register(callback_add_channel, F.data == "add_channel")
    dp.callback_query.register(callback_exit_to_menu, F.data == "exit_to_menu")
    
    # Регистрируем обработчики сообщений по состояниям
    dp.message.register(handle_add_channel, BotStates.adding_channel)
    dp.message.register(handle_route_creation, BotStates.route_creation)
    
    # Обработчик для сообщений вне активной сессии (должен быть последним)
    dp.message.register(handle_unknown_message)
    
    # Запускаем бота
    logger.info("Бот запущен...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
