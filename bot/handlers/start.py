from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from database.database import AsyncSessionLocal
from services.user_service import UserService
from bot.keyboards.reply import main_menu_keyboard, admin_menu_keyboard
from config import settings

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message):
    """Обработчик команды /start"""
    async with AsyncSessionLocal() as session:
        # Создаём или обновляем пользователя
        user = await UserService.get_or_create_user(
            session,
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name,
        )

        # Проверяем, является ли пользователь админом
        is_admin = user.telegram_id in settings.admin_ids_list

        if is_admin and not user.is_admin:
            user.is_admin = True
            await session.commit()

        await session.commit()

    # Выбираем клавиатуру
    keyboard = admin_menu_keyboard() if is_admin else main_menu_keyboard()

    welcome_text = f"""
👋 Добро пожаловать, {message.from_user.first_name}!

🔐 Я бот для предоставления доступа к Shadowsocks VPN.

🌍 Сервер расположен: {settings.SERVER_LOCATION}

С помощью нашего сервиса вы получите:
✅ Быстрый и стабильный VPN
✅ Безлимитный трафик
✅ Защищённое соединение
✅ Обход блокировок

💰 Выберите подходящий тариф и наслаждайтесь свободным интернетом!
"""

    await message.answer(welcome_text, reply_markup=keyboard)


@router.message(Command("help"))
@router.message(F.text == "❓ Помощь")
async def cmd_help(message: Message):
    """Обработчик команды /help"""
    help_text = """
📖 Справка по использованию бота:

💰 Купить подписку - выбрать и оплатить тариф
📊 Мой статус - проверить активную подписку
📱 Инструкция - как подключиться к VPN
❓ Помощь - это сообщение

📞 Поддержка: @your_support_username

Команды:
/start - начать работу
/help - справка
/status - проверить статус подписки
"""
    await message.answer(help_text)
