import os
import asyncio
import json
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from dotenv import load_dotenv

load_dotenv()

API_TOKEN = os.getenv("API_TOKEN")
ADMIN_IDS = list(map(int, os.getenv("ADMIN_IDS").split(',')))

logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

DATA_FILE = "user_messages.json"

def load_data():
    try:
        with open(DATA_FILE, 'r') as file:
            return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_data(data):
    with open(DATA_FILE, 'w') as file:
        json.dump(data, file)

user_messages = load_data()

class AdminStates(StatesGroup):
    waiting_for_reply = State()

def get_reply_keyboard(user_id, message_id):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Тык для ответа", callback_data=f"reply_{user_id}_{message_id}")]
        ]
    )

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    user_id = message.from_user.id
    user_name = message.from_user.full_name
    await message.answer("🤫 Внимательно слушаю...")
    user_messages.setdefault(str(user_id), [])
    save_data(user_messages)

@dp.message(lambda message: message.from_user.id not in ADMIN_IDS)
async def handle_user_message(message: types.Message):
    user_id = str(message.from_user.id)
    user_name = message.from_user.full_name
    username = message.from_user.username

    user_messages.setdefault(user_id, []).append(message.text or "Voice Message")
    save_data(user_messages)

    # Отправляем сообщение администраторам в зависимости от типа сообщения
    if message.photo:
        for admin_id in ADMIN_IDS:
            await bot.send_photo(
                admin_id, message.photo[-1].file_id,
                caption=f"{user_id} ({user_name}): Фото от {user_name} (@{username if username else 'no_username'})",
                reply_markup=get_reply_keyboard(user_id, message.message_id)
            )
    elif message.sticker:
        for admin_id in ADMIN_IDS:
            await bot.send_sticker(
                admin_id, message.sticker.file_id,
                reply_markup=get_reply_keyboard(user_id, message.message_id)
            )
    elif message.voice:
        for admin_id in ADMIN_IDS:
            await bot.send_voice(
                admin_id, message.voice.file_id,
                caption=f"{user_id} ({user_name}): Голосовое сообщение от {user_name} (@{username if username else 'no_username'})",
                reply_markup=get_reply_keyboard(user_id, message.message_id)
            )
    else:
        for admin_id in ADMIN_IDS:
            await bot.send_message(
                admin_id,
                f"\nСообщение от {user_name} (@{username if username else 'no_username'}):\n\n\n{message.text}",
                reply_markup=get_reply_keyboard(user_id, message.message_id)
            )
    await message.answer("🦉~✉️ Сообщение улетело Асе.")

@dp.callback_query(lambda call: call.data.startswith("reply_"))
async def reply_to_user(call: CallbackQuery, state: FSMContext):
    user_id, message_id = call.data.split("_")[1:]
    user_data = user_messages.get(user_id, [])
    user_name = (await bot.get_chat(user_id)).full_name

    if not user_data:
        await call.answer("Пользователь не найден.")
        return

    await state.set_state(AdminStates.waiting_for_reply)
    await state.update_data(user_id=user_id, message_id=message_id)
    await call.message.answer(
        f"Напиши ответ этому => \n{user_data[-1]}\n"
    )
    await call.answer()

@dp.message(lambda message: message.from_user.id in ADMIN_IDS)
async def process_reply(message: types.Message, state: FSMContext):
    admin_id = message.from_user.id
    data = await state.get_data()
    user_id = data.get("user_id")

    if not user_id:
        await message.answer("Ти не тыкнула кнопку Ответить )")
        return

    user_name = (await bot.get_chat(user_id)).full_name

    # Отправка ответа пользователю от администратора
    if message.text:
        await bot.send_message(user_id, f"✨Ответ от Аси:\n{message.text}")
        response_text = message.text
    elif message.sticker:
        await bot.send_sticker(user_id, message.sticker.file_id)
        response_text = "Стикер улител"
    elif message.voice:
        await bot.send_voice(user_id, message.voice.file_id)
        response_text = "Голосовое сообщение отправлено"
    elif message.photo:
        await bot.send_photo(user_id, message.photo[-1].file_id)
        response_text = "Фото отправлено"
    else:
        response_text = "Неподдерживаемый тип сообщения :-("

    # Уведомление других администраторов об ответе
    for other_admin_id in ADMIN_IDS:
        if other_admin_id != admin_id:
            await bot.send_message(
                other_admin_id,
                f"Ответ челу => {user_id} ({user_name}):\n{response_text}"
            )
    await message.answer(f"Ответ отправлен этоиу =>({user_name}).")
    await state.clear()

async def main():
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
