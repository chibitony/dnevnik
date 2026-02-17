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
            try:
                return json.load(f)
            except:
                pass
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
        return member.status in ["member", "administrator", "creator"]
    except Exception:
        return False

async def is_chat_admin(chat_id: int, user_id: int):
    try:
        member = await bot.get_chat_member(chat_id=chat_id, user_id=user_id)
        return member.status in ["administrator", "creator"]
    except Exception:
        return False

# --- КОМАНДЫ ---

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    if message.from_user.id != OWNER_ID:
        return
    
    help_text = (
        "Команды управления:\n"
        "/set_channel [ID] — сменить канал\n"
        "/set_group — (в группе) защищать этот чат\n"
        "/status — проверить текущие ID"
    )
    await message.answer(help_text)

@dp.message(Command("status"))
async def status_cmd(message: types.Message):
    if message.from_user.id != OWNER_ID:
        return
    await message.answer(f"Канал: {config['target_channel']}\nГруппа: {config['target_group']}")

@dp.message(Command("set_channel"))
async def set_channel_cmd(message: types.Message):
    if message.from_user.id != OWNER_ID:
        return
    args = message.text.split()
    if len(args) > 1:
        config["target_channel"] = int(args[1])
        save_config(config)
        await message.answer("Канал обновлен.")

@dp.message(Command("set_group"))
async def set_group_cmd(message: types.Message):
    if message.from_user.id != OWNER_ID:
        return
    config["target_group"] = message.chat.id
    save_config(config)
    await message.answer(f"Этот чат (ID: {message.chat.id}) теперь под защитой.")

# --- ОСНОВНОЙ ФИЛЬТР ---

@dp.message(F.chat.type.in_({"group", "supergroup"}))
async def message_filter(message: types.Message):
    # 1. Игнорируем команды (чтобы они работали и не удалялись)
    if message.text and message.text.startswith("/"):
        return

    # 2. Игнорируем автоматическую пересылку из канала в группу
    if message.is_automatic_forward:
        return

    # 3. Игнорируем сообщения от лица самого канала или группы (анонимные админы)
    if message.sender_chat:
        # Если ID отправителя совпадает с ID группы или нашего канала — пропускаем
        if message.sender_chat.id == message.chat.id or message.sender_chat.id == config["target_channel"]:
            return

    # 4. Проверка владельца по ID
    if message.from_user and message.from_user.id == OWNER_ID:
        return

    # 5. Если чат не тот, что мы защищаем — ничего не делаем
    if config["target_group"] and message.chat.id != config["target_group"]:
        return

    # 6. Проверка обычных админов
    if message.from_user and await is_chat_admin(message.chat.id, message.from_user.id):
        return

    # 7. Проверка подписки
    if message.from_user:
        is_subscribed = await check_subscription(message.from_user.id)
        if not is_subscribed:
            try:
                await message.delete()
                warning = await message.answer(f"{message.from_user.first_name}, подпишитесь на канал, чтобы писать!")
                await asyncio.sleep(5)
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
    
