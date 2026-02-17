import os
import json
import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.exceptions import TelegramBadRequest

# Конфигурация
TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = 964200005 
CONFIG_FILE = "bot_config.json"

logging.basicConfig(level=logging.INFO)

bot = Bot(token=TOKEN)
dp = Dispatcher()

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            try: return json.load(f)
            except: pass
    return {"target_channel": -1001003028461152, "target_group": None}

def save_config(new_config):
    with open(CONFIG_FILE, "w") as f:
        json.dump(new_config, f)

config = load_config()

async def check_subscription(user_id: int):
    if not config["target_channel"]:
        return True
    try:
        member = await bot.get_chat_member(chat_id=config["target_channel"], user_id=user_id)
        # Учитываем все активные статусы
        return member.status in ["member", "administrator", "creator", "restricted"]
    except Exception as e:
        logging.error(f"Ошибка проверки подписки: {e}")
        return False

async def is_chat_admin(chat_id: int, user_id: int):
    try:
        member = await bot.get_chat_member(chat_id=chat_id, user_id=user_id)
        return member.status in ["administrator", "creator"]
    except Exception:
        return False

# --- КОМАНДЫ (ТОЛЬКО ДЛЯ ТЕБЯ) ---

@dp.message(Command("start", "help"))
async def start_handler(message: types.Message):
    if message.from_user.id == OWNER_ID:
        await message.answer("Команды: /set_channel [ID], /set_group, /status")

@dp.message(Command("status"))
async def status_cmd(message: types.Message):
    if message.from_user.id != OWNER_ID:
        return
    
    # Проверка связи с каналом
    try:
        await bot.get_chat(config["target_channel"])
        channel_status = "✅ Доступ есть"
    except:
        channel_status = "❌ Нет доступа (сделайте бота админом в канале!)"
        
    await message.answer(
        f"Текущие настройки:\n"
        f"Канал: {config['target_channel']} ({channel_status})\n"
        f"Группа: {config['target_group']}"
    )

@dp.message(Command("set_channel"))
async def set_channel_cmd(message: types.Message):
    if message.from_user.id == OWNER_ID:
        args = message.text.split()
        if len(args) > 1:
            config["target_channel"] = int(args[1])
            save_config(config)
            await message.answer("ID канала обновлен.")

@dp.message(Command("set_group"))
async def set_group_cmd(message: types.Message):
    if message.from_user.id == OWNER_ID:
        config["target_group"] = message.chat.id
        save_config(config)
        await message.answer("Этот чат теперь под защитой.")

# --- ФИЛЬТР СООБЩЕНИЙ ---

@dp.message()
async def main_filter(message: types.Message):
    # 1. Если это не группа, которую мы защищаем — игнорируем (для ЛС)
    if message.chat.type not in ["group", "supergroup"]:
        return

    # 2. Игнорируем системные сообщения и пересылки из канала
    if message.is_automatic_forward or not message.from_user:
        return

    # 3. Игнорируем анонимных админов (от лица группы/канала)
    if message.sender_chat:
        return

    # 4. Пропускаем ТЕБЯ (владельца)
    if message.from_user.id == OWNER_ID:
        return

    # 5. Пропускаем админов группы
    if await is_chat_admin(message.chat.id, message.from_user.id):
        return

    # 6. Проверяем подписку
    is_subscribed = await check_subscription(message.from_user.id)
    
    if not is_subscribed:
        try:
            await message.delete()
            # Предупреждение (только если это не команда, чтобы не спамить)
            if not (message.text and message.text.startswith("/")):
                warn = await message.answer(f"{message.from_user.first_name}, подпишитесь на канал!")
                await asyncio.sleep(5)
                await warn.delete()
        except TelegramBadRequest:
            pass
            
