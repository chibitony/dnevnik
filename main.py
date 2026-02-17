import os
import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.exceptions import TelegramBadRequest

# Конфигурация из твоих данных
# Токен мы не пишем текстом, а берем из настроек хостинга (Environment Variables)
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 964200005
CHANNEL_ID = -1001003028461152

logging.basicConfig(level=logging.INFO)

bot = Bot(token=TOKEN)
dp = Dispatcher()

async def check_subscription(user_id: int):
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        # Статусы, при которых пользователь считается подписанным
        return member.status in ["member", "administrator", "creator"]
    except Exception as e:
        logging.error(f"Ошибка проверки подписки: {e}")
        return False

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    # Бот реагирует на команду старт только если пишешь ты (твой ID)
    if message.from_user.id != ADMIN_ID:
        return
    
    await message.answer("Система модерации подписок активирована.")

@dp.message(F.chat.type.in_({"group", "supergroup"}))
async def message_filter(message: types.Message):
    # Игнорируем тебя (админа), чтобы ты мог писать без проверок
    if message.from_user.id == ADMIN_ID:
        return

    # Проверяем подписку пользователя
    is_subscribed = await check_subscription(message.from_user.id)
    
    if not is_subscribed:
        try:
            # Удаляем сообщение нарушителя
            await message.delete()
            
            # Отправляем краткое предупреждение
            warning = await message.answer(
                f"Уважаемый {message.from_user.first_name}, ваши сообщения удаляются. "
                "Чтобы писать в этом чате, пожалуйста, подпишитесь на наш канал."
            )
            
            # Удаляем предупреждение через 10 секунд, чтобы не спамить в группе
            await asyncio.sleep(10)
            await warning.delete()
        except TelegramBadRequest:
            logging.error("У бота нет прав администратора на удаление сообщений!")
        except Exception as e:
            logging.error(f"Произошла ошибка: {e}")

async def main():
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
