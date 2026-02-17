import os
import json
import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.exceptions import TelegramBadRequest

# Конфигурация
TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = 964200005  # Твой ID
CONFIG_FILE = "bot_config.json"

logging.basicConfig(level=logging.INFO)

bot = Bot(token=TOKEN)
dp = Dispatcher()

# Функция для загрузки настроек из файла
def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    return {"target_channel": -1001003028461152, "target_group": None}

# Функция для сохранения настроек
def save_config(new_config):
    with open(CONFIG_FILE, "w") as f:
        json.dump(new_config, f)

config = load_config()

async def check_subscription(user_id: int):
    if not config["target_channel"]:
        return True
    try:
        member = await bot.get_chat_member(chat_id=config["target_channel"], user_id=user_id)
        return member.status in ["member", "administrator", "creator"]
    except Exception:
        return False

async def is_chat_admin(chat_id: int, user_id: int):
    try:
        member = await bot.get_chat_member(chat_id=chat_id, user_id=user_id)
        return member.status in ["administrator", "creator"]
    except Exception:
        return False

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    if message.from_user.id != OWNER_ID:
        return
    
    help_text = (
        "Команды управления ботом:\n\n"
        "1. /set_channel [ID] — установить ID канала для проверки (например, /set_channel -100123)\n"
        "2. /set_group — напиши это В ГРУППЕ, которую нужно защищать\n"
        "3. /status — показать текущие настройки"
    )
    await message.answer(help_text)

@dp.message(Command("set_channel"))
async def set_channel_cmd(message: types.Message):
    if message.from_user.id != OWNER_ID:
        return
    args = message.text.split()
    if len(args) > 1:
        try:
            config["target_channel"] = int(args[1])
            save_config(config)
            await message.answer(f"Канал для проверки сохранен: {config['target_channel']}")
        except ValueError:
            await message.answer("Ошибка: ID должен быть числом.")

@dp.message(Command("set_group"))
async def set_group_cmd(message: types.Message):
    if message.from_user.id != OWNER_ID:
        return
    config["target_group"] = message.chat.id
    save_config(config)
    await message.answer(f"Защита установлена для этого чата (ID: {message.chat.id})")

@dp.message(Command("status"))
async def status_cmd(message: types.Message):
    if message.from_user.id != OWNER_ID:
        return
    await message.answer(f"Текущий канал: {config['target_channel']}\nТекущая группа: {config['target_group']}")

@dp.message(F.chat.type.in_({"group", "supergroup"}))
async def message_filter(message: types.Message):
    # ПРОВЕРКА ВЛАДЕЛЬЦА (тебя)
    if int(message.from_user.id) == int(OWNER_ID):
        return

    # Если группа не та, что в настройках — игнорируем
    if config["target_group"] and message.chat.id != config["target_group"]:
        return

    # Проверка админов группы
    if await is_chat_admin(message.chat.id, message.from_user.id):
        return

    is_subscribed = await check_subscription(message.from_user.id)
    
    if not is_subscribed:
        try:
            await message.delete()
            warning = await message.answer(f"{message.from_user.first_name}, подпишитесь на канал!")
            await asyncio.sleep(7)
            await warning.delete()
        except TelegramBadRequest:
            pass

async def main():
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
    
