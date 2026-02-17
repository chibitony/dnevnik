import os
import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.exceptions import TelegramBadRequest

# Берем только токен из переменных окружения
TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = 964200005

# Эти данные теперь можно менять через команды
# По умолчанию поставил те, что ты дала
config = {
    "target_channel": -1001003028461152,
    "target_group": None # Можно будет установить через команду
}

logging.basicConfig(level=logging.INFO)

bot = Bot(token=TOKEN)
dp = Dispatcher()

# Проверка подписки
async def check_subscription(user_id: int):
    if not config["target_channel"]:
        return True
    try:
        member = await bot.get_chat_member(chat_id=config["target_channel"], user_id=user_id)
        return member.status in ["member", "administrator", "creator"]
    except Exception:
        return False

# Проверка на админа в группе
async def is_chat_admin(chat_id: int, user_id: int):
    try:
        member = await bot.get_chat_member(chat_id=chat_id, user_id=user_id)
        return member.status in ["administrator", "creator"]
    except Exception:
        return False

# Команда для установки ID канала
@dp.message(Command("set_channel"))
async def set_channel(message: types.Message):
    if message.from_user.id != OWNER_ID:
        return
    
    args = message.text.split()
    if len(args) > 1:
        try:
            config["target_channel"] = int(args[1])
            await message.answer(f"Канал для проверки успешно установлен: {config['target_channel']}")
        except ValueError:
            await message.answer("Ошибка: ID канала должен быть числом.")
    else:
        await message.answer("Использование: /set_channel -100xxxxxxxxxx")

# Команда для установки ID группы
@dp.message(Command("set_group"))
async def set_group(message: types.Message):
    if message.from_user.id != OWNER_ID:
        return
    
    args = message.text.split()
    if len(args) > 1:
        try:
            config["target_group"] = int(args[1])
            await message.answer(f"Группа для защиты успешно установлена: {config['target_group']}")
        except ValueError:
            await message.answer("Ошибка: ID группы должен быть числом.")
    else:
        # Если аргументов нет, можно установить текущий чат
        config["target_group"] = message.chat.id
        await message.answer(f"Этот чат установлен как целевая группа: {config['target_group']}")

# Основной фильтр сообщений
@dp.message(F.chat.type.in_({"group", "supergroup"}))
async def message_filter(message: types.Message):
    # Если группа еще не настроена или это другая группа — игнорируем
    if config["target_group"] and message.chat.id != config["target_group"]:
        return

    # Пропускаем тебя и админов группы
    if message.from_user.id == OWNER_ID or await is_chat_admin(message.chat.id, message.from_user.id):
        return

    is_subscribed = await check_subscription(message.from_user.id)
    
    if not is_subscribed:
        try:
            await message.delete()
            warning = await message.answer(
                f"{message.from_user.first_name}, пожалуйста, подпишитесь на канал, чтобы писать сообщения."
            )
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
    
