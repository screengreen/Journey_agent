"""
Telegram бот для работы с каналами и созданием маршрутов
Использует aiogram
"""
import os
import logging
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# Импорты с обработкой разных способов запуска
try:
    from bot.database import Database
    from bot.agent_stub import process_route_request
except ImportError:
    from database import Database
    from agent_stub import process_route_request

# Загружаем переменные окружения (ищем .env в корне проекта)
from pathlib import Path
env_path = Path(__file__).parent.parent / ".env"
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

# FSM состояния
class BotStates(StatesGroup):
    adding_channel = State()
    route_creation = State()
    route_comment = State()


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
    
    text = """
🗺️ <b>Создание маршрута</b>

Напиши свой запрос (промпт) для создания маршрута.
Например: "Хочу провести выходные в центре города, интересные мероприятия и кафе"
"""
    await callback.message.edit_text(
        text,
        reply_markup=get_exit_menu_keyboard(),
        parse_mode='HTML'
    )


async def callback_add_channel(callback: CallbackQuery, state: FSMContext):
    """Обработчик кнопки 'Добавить канал'"""
    await callback.answer()
    
    # Переходим в режим добавления канала
    await state.set_state(BotStates.adding_channel)
    
    text = """
➕ <b>Добавление канала</b>

Отправь ссылку на канал или просто его название.
Например:
• https://t.me/channel_name
• @channel_name
• channel_name
"""
    await callback.message.edit_text(
        text,
        reply_markup=get_exit_menu_keyboard(),
        parse_mode='HTML'
    )


async def callback_exit_to_menu(callback: CallbackQuery, state: FSMContext):
    """Обработчик кнопки 'Выход в меню'"""
    await callback.answer()
    
    # Сбрасываем состояние
    await state.clear()
    
    text = """
🏠 <b>Главное меню</b>

Выбери действие:
"""
    await callback.message.edit_text(
        text,
        reply_markup=get_main_menu_keyboard(),
        parse_mode='HTML'
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
    
    # Сохраняем канал в БД
    success = db.add_channel(message.from_user.id, channel_name, channel_url)
    
    if success:
        response_text = f"""
✅ <b>Канал успешно добавлен!</b>

Название: {channel_name}
Ссылка: {channel_url or 'не указана'}
"""
    else:
        response_text = f"""
⚠️ Канал "{channel_name}" уже был добавлен ранее или произошла ошибка.
"""
    
    await message.answer(
        response_text,
        reply_markup=get_exit_menu_keyboard(),
        parse_mode='HTML'
    )
    
    # Остаемся в режиме добавления канала для возможности добавить еще


async def handle_route_creation(message: Message, state: FSMContext):
    """Обработка создания маршрута - первый промпт"""
    user = message.from_user
    message_text = message.text
    
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
    
    # Переходим в режим ожидания комментария
    await state.set_state(BotStates.route_comment)
    
    # Отправляем ответ пользователю одним сообщением
    response_text = f"{result['response']}\n\n💬 Можешь написать комментарий к этому результату, или нажми 'Выход в меню'"
    await message.answer(
        response_text,
        reply_markup=get_exit_menu_keyboard()
    )


async def handle_route_comment(message: Message, state: FSMContext):
    """Обработка комментария к результату маршрута"""
    user = message.from_user
    comment = message.text
    
    # Получаем данные из состояния
    data = await state.get_data()
    history = data.get("history", [])
    original_prompt = data.get("current_prompt", "")
    
    # Получаем последний ответ модели
    last_assistant_response = ""
    if history and history[-1].get("role") == "assistant":
        last_assistant_response = history[-1].get("content", "")
    
    updated_prompt = f"""
Исходный запрос: {original_prompt}

Результат модели:
{last_assistant_response}

Комментарий пользователя: {comment}
"""
    
    # Добавляем комментарий в историю
    history.append({
        "role": "user",
        "content": f"Комментарий: {comment}"
    })
    
    # Отправляем обновленный запрос в заглушку
    username = user.username or user.first_name
    result = process_route_request(
        prompt=updated_prompt,
        username=username,
        conversation_history=history
    )
    
    # Добавляем новый ответ в историю
    history.append({
        "role": "assistant",
        "content": result["response"]
    })
    
    # Сохраняем обновленную историю
    await state.update_data(history=history)
    
    # Отправляем ответ пользователю одним сообщением
    response_text = f"{result['response']}\n\n💬 Можешь написать еще комментарий, или нажми 'Выход в меню'"
    await message.answer(
        response_text,
        reply_markup=get_exit_menu_keyboard()
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
    dp.message.register(handle_route_comment, BotStates.route_comment)
    
    # Обработчик для сообщений вне активной сессии (должен быть последним)
    dp.message.register(handle_unknown_message)
    
    # Запускаем бота
    logger.info("Бот запущен...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
