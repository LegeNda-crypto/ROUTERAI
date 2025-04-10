from aiogram import Bot, Dispatcher, types
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from openai import OpenAI
from dotenv import load_dotenv
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Text, ForeignKey, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
import os
import html
import platform
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

# Загрузка конфигурации
load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENROUTER_KEY = os.getenv("OPENROUTER_API_KEY")

if not TOKEN or not OPENROUTER_KEY:
    raise ValueError("Проверьте TOKEN и OPENROUTER_API_KEY в .env!")

# Инициализация бота
bot = Bot(token=TOKEN)
dp = Dispatcher(bot)
dp.middleware.setup(LoggingMiddleware())

# Настройка OpenRouter
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_KEY,
    default_headers={
        "HTTP-Referer": "https://github.com/local",
        "X-Title": "Telegram AI Assistant"
    }
)

# SQLAlchemy настройки
Base = declarative_base()
engine = create_engine('sqlite:///bot.db', echo=True)
Session = sessionmaker(bind=engine)


# Модели данных
class User(Base):
    __tablename__ = 'users'

    user_id = Column(Integer, primary_key=True)
    username = Column(String(50))
    first_name = Column(String(50))
    last_name = Column(String(50))
    registered_at = Column(DateTime)

    messages = relationship("Message", back_populates="user")


class Message(Base):
    __tablename__ = 'messages'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.user_id'))
    message_text = Column(Text)
    response_text = Column(Text)
    created_at = Column(DateTime)

    user = relationship("User", back_populates="messages")


# Инициализация БД
def init_db():
    Base.metadata.create_all(engine)


# Регистрация пользователя
def register_user(user: types.User):
    session = Session()
    try:
        existing_user = session.query(User).filter_by(user_id=user.id).first()
        if not existing_user:
            new_user = User(
                user_id=user.id,
                username=user.username,
                first_name=user.first_name,
                last_name=user.last_name,
                registered_at=datetime.now()
            )
            session.add(new_user)
            session.commit()
    finally:
        session.close()


def save_message(user_id: int, message_text: str, response_text: str):
    session = Session()
    try:
        # Очищаем текст перед сохранением
        clean_msg = message_text.encode('utf-8', 'ignore').decode('utf-8').strip()
        clean_ans = response_text.encode('utf-8', 'ignore').decode('utf-8').strip()

        message = Message(
            user_id=user_id,
            message_text=clean_msg,
            response_text=clean_ans,
            created_at=datetime.now()
        )
        session.add(message)
        session.commit()
    finally:
        session.close()


def get_history(user_id: int, limit=5):
    session = Session()
    try:
        messages = session.query(Message).filter_by(user_id=user_id) \
            .order_by(Message.created_at.desc()) \
            .limit(limit).all()

        # Очищаем текст от бинарных символов и лишних пробелов
        cleaned_history = []
        for msg in messages:
            clean_msg = (msg.message_text or "").encode('utf-8', 'ignore').decode('utf-8').strip()
            clean_ans = (msg.response_text or "").encode('utf-8', 'ignore').decode('utf-8').strip()
            cleaned_history.append((clean_msg, clean_ans))

        return cleaned_history
    finally:
        session.close()


# Временно добавьте эту команду
@dp.message_handler(commands=['clean_db'])
async def clean_database(message: types.Message):
    session = Session()
    try:
        for msg in session.query(Message).all():
            msg.message_text = (msg.message_text or "").encode('utf-8', 'ignore').decode('utf-8').strip()
            msg.response_text = (msg.response_text or "").encode('utf-8', 'ignore').decode('utf-8').strip()
        session.commit()
        await message.reply("База данных очищена от бинарных данных")
    finally:
        session.close()


@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    register_user(message.from_user)

    start_text = """
🤖 <b>Добро пожаловать в AI-бота с OpenRouter!</b>

<u>Основные возможности:</u>
• Общение с ИИ (Llama3/Mistral/Gemini)
• Сохранение истории диалогов
• Поддержка длинных сообщений

<u>📌 Команды:</u>
/start - Показать это сообщение
/help - Подробная справка
/history - Последние 5 сообщений
/clear - Очистить историю
/model - Сменить модель ИИ
/features - Все возможности бота

<u>🔍 Доступные модели:</u>
• llama3 - Meta Llama 3 70B
• mistral - Mistral 7B
• gemini - Google Gemini Pro

Просто напишите сообщение, и я отвечу с помощью выбранной модели ИИ!

<code>Сейчас активна: llama3-70b</code>
"""
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(KeyboardButton('/help'))
    keyboard.add(KeyboardButton('/history'))
    keyboard.add(KeyboardButton('/model'))
    start_text += f"\n\n<code>Версия Python: {platform.python_version()}</code>"
    await message.reply(start_text, parse_mode="HTML")


@dp.message_handler(commands=['help'])
async def help_command(message: types.Message):
    help_text = """
🆘 *Помощь по использованию бота*

Основные команды:
/start - Начало работы
/history - Показать историю сообщений
/clear - Очистить историю диалога
/features - Возможности бота

Просто напишите сообщение, и я отвечу с помощью ИИ!
"""
    await message.reply(help_text, parse_mode="Markdown")


@dp.message_handler(commands=['features'])
async def features_command(message: types.Message):
    features_text = """
🌟 *Возможности бота:*
• Ответы на вопросы с помощью Llama 3 70B
• Поддержка контекста диалога
• История сообщений
• Поддержка Markdown-разметки
• Быстрые и развернутые ответы
"""
    await message.reply(features_text, parse_mode="Markdown")


@dp.message_handler(commands=['history'])
async def show_history(message: types.Message):
    history = get_history(message.from_user.id)
    if not history:
        await message.reply("История сообщений пуста")
        return

    response = "📜 <b>Последние сообщения:</b>\n\n"
    for i, (msg, ans) in enumerate(history, 1):
        # Форматируем текст для телеграма
        msg_text = html.escape(msg) if msg else "[сообщение удалено]"
        ans_text = html.escape(ans) if ans else "[ответ удален]"

        response += (
            f"{i}. <b>Вы:</b> {msg_text[:100]}{'...' if len(msg_text) > 100 else ''}\n"
            f"   <b>Бот:</b> {ans_text[:100]}{'...' if len(ans_text) > 100 else ''}\n\n"
        )

    await message.reply(response, parse_mode="HTML")


@dp.message_handler(commands=['clear'])
async def clear_history(message: types.Message):
    session = Session()
    try:
        deleted_count = session.query(Message) \
            .filter_by(user_id=message.from_user.id) \
            .delete()
        session.commit()
        await message.reply(f"🗑 Удалено сообщений: {deleted_count}")
    except Exception as e:
        await message.reply(f"⚠️ Ошибка при очистке: {str(e)}")
    finally:
        session.close()


@dp.message_handler(commands=['model'])
async def change_model(message: types.Message):
    models = {
        'llama3': 'meta-llama/llama-3-70b-instruct',
        'mistral': 'mistralai/mistral-7b-instruct',
        'gemini': 'google/gemini-pro'
    }

    args = message.get_args()
    if args in models:
        await message.reply(f"Модель изменена на {args}")
    else:
        await message.reply("Доступные модели: /model llama3|mistral|gemini")


@dp.message_handler()
async def handle_message(message: types.Message):
    try:
        history = get_history(message.from_user.id)

        messages = [{"role": "system", "content": "Ты полезный ассистент."}]
        for msg, ans in reversed(history):
            messages.extend([
                {"role": "user", "content": msg},
                {"role": "assistant", "content": ans}
            ])
        messages.append({"role": "user", "content": message.text})

        response = client.chat.completions.create(
            model="meta-llama/llama-3-70b-instruct",
            messages=messages,
            max_tokens=1500
        )

        answer = response.choices[0].message.content
        save_message(message.from_user.id, message.text, answer)
        await message.reply(answer)

    except Exception as e:
        await message.reply(f" Ошибка: {str(e)}")


if __name__ == '__main__':
    init_db()
    from aiogram import executor

    executor.start_polling(dp, skip_updates=True)
