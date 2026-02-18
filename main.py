import os
import json
import asyncio
import logging
import hashlib
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.exceptions import TelegramBadRequest
from aiogram.client.default import DefaultBotProperties

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_PASSWORD_HASH = "45e486ecdca023554778721cd693fc7275ea99b8f2e7d34b0443542b3069b940"
CONFIG_FILE = "bot_config.json"
WARNINGS_FILE = "warnings.json"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            try:
                data = json.load(f)
                if "auth_users" not in data: data["auth_users"] = []
                if data.get("target_channel"): data["target_channel"] = int(data["target_channel"])
                if data.get("target_group"): data["target_group"] = int(data["target_group"])
                return data
            except: pass
    return {"target_channel": -1003771574688, "target_group": None, "auth_users": []}

def save_config(new_config):
    with open(CONFIG_FILE, "w") as f:
        json.dump(new_config, f)

def load_warnings():
    if os.path.exists(WARNINGS_FILE):
        with open(WARNINGS_FILE, "r") as f:
            try: return json.load(f)
            except: pass
    return {}

def save_warnings(data):
    with open(WARNINGS_FILE, "w") as f:
        json.dump(data, f)

config = load_config()
warnings = load_warnings()

def check_password(password: str):
    pwd_hash = hashlib.sha256(password.strip().encode()).hexdigest()
    return pwd_hash == ADMIN_PASSWORD_HASH

async def check_subscription(user_id: int):
    try:
        member = await bot.get_chat_member(chat_id=config["target_channel"], user_id=user_id)
        return member.status in ["member", "administrator", "creator", "restricted"]
    except Exception:
        return False

@dp.message(Command("start"), F.chat.type == "private")
async def start_handler(message: types.Message):
    if message.from_user.id in config["auth_users"]:
        await message.answer("Вы авторизованы. Команды: /status, /set_channel, /set_group")
    else:
        await message.answer("Введите пароль:")

@dp.message(F.chat.type == "private", Command("status"))
async def status_handler(message: types.Message):
    if message.from_user.id in config["auth_users"]:
        await message.answer(f"Настройки: \nКанал: {config['target_channel']}\nГруппа: {config['target_group']}")

@dp.message(F.chat.type == "private", Command("set_channel"))
async def set_channel_handler(message: types.Message):
    if message.from_user.id in config["auth_users"]:
        args = message.text.split()
        if len(args) > 1:
            config["target_channel"] = int(args[1])
            save_config(config)
            await message.answer(f"Канал обновлен: {config['target_channel']}")

@dp.message(Command("set_group"))
async def set_group_handler(message: types.Message):
    if message.from_user.id in config["auth_users"]:
        args = message.text.split()
        new_id = int(args[1]) if len(args) > 1 else message.chat.id
        config["target_group"] = int(new_id)
        save_config(config)
        await message.answer(f"Группа обновлена: {config['target_group']}")

@dp.message(F.chat.type == "private")
async def auth_handler(message: types.Message):
    if message.from_user.id in config["auth_users"]:
        return
    if message.text and check_password(message.text):
        config["auth_users"].append(message.from_user.id)
        save_config(config)
        await message.answer("Пароль принят.")
    else:
        if not message.text.startswith("/"):
            await message.answer("Неверный пароль.")

@dp.message(F.new_chat_members)
async def welcome_new_member(message: types.Message):
    if not config["target_group"] or message.chat.id != config["target_group"]:
        return
    for user in message.new_chat_members:
        if user.id == bot.id:
            continue
        is_sub = await check_subscription(user.id)
        if not is_sub:
            user_mention = user.mention_html()
            warn_text = f"Внимание, {user_mention}. Вы не подписаны на канал. Сообщения удаляются. 3 попытки - бан."
            try:
                msg = await message.answer(warn_text)
                await asyncio.sleep(15)
                await msg.delete()
            except: pass

@dp.message()
async def main_filter(message: types.Message):
    if message.chat.type == "private" or not config["target_group"]:
        return
    if message.chat.id != config["target_group"]:
        return
    if message.from_user.id in config["auth_users"]:
        return
    if message.is_automatic_forward or message.sender_chat:
        return
    if not message.from_user:
        return
    is_sub = await check_subscription(message.from_user.id)
    if not is_sub:
        user_id_str = str(message.from_user.id)
        user_mention = message.from_user.mention_html()
        current_strikes = warnings.get(user_id_str, 0) + 1
        warnings[user_id_str] = current_strikes
        save_warnings(warnings)
        try:
            await message.delete()
            if current_strikes < 3:
                warn_msg = await message.answer(f"Нарушение {current_strikes}/3 от {user_mention}. Подпишитесь.")
                await asyncio.sleep(5)
                await warn_msg.delete()
            else:
                await bot.ban_chat_member(chat_id=config["target_group"], user_id=message.from_user.id)
                await message.answer(f"Пользователь {user_mention} забанен.")
                if user_id_str in warnings:
                    del warnings[user_id_str]
                    save_warnings(warnings)
        except: pass

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
