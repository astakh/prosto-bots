import asyncio
import asyncpg
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from config import TELEGRAM_TOKEN, SERVICE_CONFIG, DB_CONFIG, API_BASE_URL
from auth import register_user
from rich.console import Console

console = Console()

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

user_data = {}

async def create_db_pool():
    return await asyncpg.create_pool(**DB_CONFIG)

@dp.message(Command("start"))
async def start_command(message: types.Message):
    telegram_id = str(message.from_user.id)
    pool = dp["db_pool"]
    
    async with pool.acquire() as conn:
        exists = await conn.fetchval("SELECT EXISTS(SELECT 1 FROM users WHERE telegram_id = $1)", telegram_id)
        if exists:
            await message.reply("Вы уже зарегистрированы! Войдите на сайте.")
            return
    
    user_data[telegram_id] = {"step": "username"}
    await message.reply("Введите ваш логин:")

@dp.message()
async def process_input(message: types.Message):
    telegram_id = str(message.from_user.id)
    pool = dp["db_pool"]
    
    if telegram_id not in user_data or "step" not in user_data[telegram_id]:
        await message.reply("Начните регистрацию с /start")
        return

    step = user_data[telegram_id]["step"]
    
    async with pool.acquire() as conn:
        if step == "username":
            username = message.text.strip()
            exists = await conn.fetchval("SELECT EXISTS(SELECT 1 FROM users WHERE username = $1)", username)
            if exists:
                await message.reply("Логин занят. Выберите другой:")
                return
            user_data[telegram_id]["username"] = username
            user_data[telegram_id]["step"] = "password"
            await message.reply("Введите пароль:")
        
        elif step == "password":
            password = message.text
            username = user_data[telegram_id]["username"]
            
            try:
                await register_user(telegram_id, username, password, conn)
            except Exception as e:
                await message.reply(f"Ошибка регистрации: {str(e)}. Попробуйте снова с /start")
                return
            
            del user_data[telegram_id]
            await message.reply(
                f"✅ Регистрация завершена!\nЛогин: {username}\nПароль: {password}\n"
                f"Войдите на сайт: {API_BASE_URL}"
            )
            await bot.send_message(telegram_id, "Регистрация завершена! Войдите на сайте.")

async def process_notifications():
    pool = dp["db_pool"]
    while True:
        async with pool.acquire() as conn:
            notifications = await conn.fetch("SELECT * FROM notifications WHERE status = 'pending'")
            for notification in notifications:
                try:
                    await bot.send_message(notification["telegram_id"], notification["text"])
                    await conn.execute(
                        "UPDATE notifications SET status = 'sent', sent_at = NOW() WHERE id = $1",
                        notification["id"]
                    )
                    console.log(f"[green]Notification sent to {notification['telegram_id']}: {notification['text']}")
                except Exception as e:
                    console.log(f"[red]Error sending notification to {notification['telegram_id']}: {e}")
                    await conn.execute(
                        "UPDATE notifications SET status = 'failed', sent_at = NOW() WHERE id = $1",
                        notification["id"]
                    )
        await asyncio.sleep(10)  # Проверять каждые 10 секунд

async def main():
    pool = await create_db_pool()
    dp["db_pool"] = pool
    asyncio.create_task(process_notifications())  # Запускаем задачу обработки уведомлений
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())