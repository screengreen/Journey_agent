import os
import sys
import logging
from pathlib import Path

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


async def send_long_message(message: Message, text: str, max_length: int = 4096):
    """
    Отправляет длинное сообщение, разбивая его на части если необходимо.
    
    Args:
        message: Объект сообщения для ответа
        text: Текст для отправки
        max_length: Максимальная длина одного сообщения (по умолчанию 4096 для Telegram)
    """
    if len(text) <= max_length:
        await message.answer(text)
        return
    
    # Разбиваем текст на части
    parts = []
    current_part = ""
    
    # Разбиваем по строкам, чтобы не разрывать слова
    lines = text.split('\n')
    
    for line in lines:
        # Если добавление строки не превышает лимит
        if len(current_part) + len(line) + 1 <= max_length:
            current_part += line + '\n'
        else:
            # Сохраняем текущую часть
            if current_part:
                parts.append(current_part.rstrip())
            # Если одна строка слишком длинная, разбиваем её
            if len(line) > max_length:
                # Разбиваем по словам
                words = line.split(' ')
                current_part = ""
                for word in words:
                    if len(current_part) + len(word) + 1 <= max_length:
                        current_part += word + ' '
                    else:
                        if current_part:
                            parts.append(current_part.rstrip())
                        current_part = word + ' '
            else:
                current_part = line + '\n'
    
    # Добавляем последнюю часть
    if current_part:
        parts.append(current_part.rstrip())
    
    # Отправляем все части
    for i, part in enumerate(parts):
        if i == 0:
            await message.answer(part)
        else:
            await message.answer(part)


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
    
    # Отправляем маршрут пользователю (с разбиением на части если нужно)
    await send_long_message(message, result["response"])
    
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
