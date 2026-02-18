import os
import json
import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.exceptions import TelegramBadRequest
from aiogram.client.default import DefaultBotProperties


# --- НАСТРОЙКИ ---
TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = 964200005
CONFIG_FILE = "bot_config.json"
WARNINGS_FILE = "warnings.json"


logging.basicConfig(level=logging.INFO)


# Исправленная инициализация для новых версий aiogram
bot = Bot(
    token=TOKEN,
    default=DefaultBotProperties(parse_mode="HTML")
)
dp = Dispatcher()


# --- ФУНКЦИИ РАБОТЫ С ДАННЫМИ ---


def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            try:
                data = json.load(f)
                if data.get("target_channel"): data["target_channel"] = int(data["target_channel"])
                if data.get("target_group"): data["target_group"] = int(data["target_group"])
                return data
            except: pass
    # Значения по умолчанию, если файл пуст
    return {"target_channel": -1003771574688, "target_group": None}


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


async def check_subscription(user_id: int):
    try:
        member = await bot.get_chat_member(chat_id=config["target_channel"], user_id=user_id)
        return member.status in ["member", "administrator", "creator", "restricted"]
    except Exception:
        return False


# --- КОМАНДЫ УПРАВЛЕНИЯ (ВЕРНУЛИ!) ---


@dp.message(Command("start"))
async def start_handler(message: types.Message):
    if message.from_user.id == OWNER_ID:
        await message.answer(
            "Бот активен.\n\n"
            "Команды:\n"
            "/set_channel ID — привязать канал\n"
            "/set_group ID — привязать группу\n"
            "/status — проверить текущие ID"
        )


@dp.message(Command("set_channel"))
async def set_channel_handler(message: types.Message):
    if message.from_user.id == OWNER_ID:
        args = message.text.split()
        if len(args) > 1:
            try:
                config["target_channel"] = int(args[1])
                save_config(config)
                await message.answer(f"Канал успешно изменен на: {config['target_channel']}")
            except ValueError:
                await message.answer("Ошибка: ID должен быть числом.")


@dp.message(Command("set_group"))
async def set_group_handler(message: types.Message):
    if message.from_user.id == OWNER_ID:
        args = message.text.split()
        # Если ID не указан, берем ID текущего чата
        new_id = int(args[1]) if len(args) > 1 else message.chat.id
        config["target_group"] = int(new_id)
        save_config(config)
        await message.answer(f"Группа успешно изменена на: {config['target_group']}")


@dp.message(Command("status"))
async def status_handler(message: types.Message):
    if message.from_user.id == OWNER_ID:
        await message.answer(
            f"Текущие настройки:\n"
            f"ID Канала: {config['target_channel']}\n"
            f"ID Группы: {config['target_group']}"
        )


# --- ПРИВЕТСТВИЕ И ПРОВЕРКА ПРИ ВХОДЕ ---


@dp.message(F.new_chat_members)
async def welcome_new_member(message: types.Message):
    if not config["target_group"] or message.chat.id != config["target_group"]:
        return


    for user in message.new_chat_members:
        if user.id == OWNER_ID or user.id == bot.id:
            continue


        is_sub = await check_subscription(user.id)
        if not is_sub:
            user_mention = user.mention_html()
            warn_text = (
                f"Внимание, {user_mention}. Вы не подписаны на канал.\n"
                f"Ваши сообщения будут удаляться автоматически. После 3 попыток последует бан."
            )
            try:
                msg = await message.answer(warn_text)
                await asyncio.sleep(15)
                await msg.delete()
            except: pass


# --- ОСНОВНАЯ ЗАЩИТА И СИСТЕМА СТРАЙКОВ ---


@dp.message()
async def main_filter(message: types.Message):
    # Игнорируем личку и чужие группы
    if message.chat.type == "private" or not config["target_group"]:
        return
    if message.chat.id != config["target_group"]:
        return


    # Исключения для админа и служебных сообщений
    if message.from_user and message.from_user.id == OWNER_ID:
        return
    if message.is_automatic_forward or message.sender_chat:
        return
    if not message.from_user:
        return


    is_sub = await check_subscription(message.from_user.id)
   
    if not is_sub:
        user_id_str = str(message.from_user.id)
        user_mention = message.from_user.mention_html()
       
        # Считаем нарушения (сохраняются в warnings.json)
        current_strikes = warnings.get(user_id_str, 0) + 1
        warnings[user_id_str] = current_strikes
        save_warnings(warnings)


        try:
            await message.delete()


            if current_strikes < 3:
                warn_msg = await message.answer(
                    f"Нарушение {current_strikes}/3 от {user_mention}.\n"
                    f"Подпишитесь на канал, чтобы ваши сообщения не удалялись."
                )
                await asyncio.sleep(5)
                await warn_msg.delete()
            else:
                # Бан на 3-е нарушение
                await bot.ban_chat_member(chat_id=config["target_group"], user_id=message.from_user.id)
                await message.answer(f"Пользователь {user_mention} забанен за игнорирование правил подписки.")
                if user_id_str in warnings:
                    del warnings[user_id_str]
                    save_warnings(warnings)
        except Exception as e:
            logging.error(f"Ошибка в блоке защиты: {e}")


async def main():
    print("Бот запущен. Команды управления доступны владельцу.")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())