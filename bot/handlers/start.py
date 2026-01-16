from aiogram import Router, F
from aiogram.filters import CommandStart, Command, CommandObject
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from database.database import AsyncSessionLocal
from services.user_service import UserService
from bot.keyboards.reply import main_menu_keyboard, admin_menu_keyboard
from config import settings

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject):
    """Обработчик команды /start"""
    referrer_id = None
    args = command.args
    if args and args.isdigit():
        referrer_id = int(args)
        if referrer_id == message.from_user.id:
            referrer_id = None  # Нельзя пригласить самого себя

    async with AsyncSessionLocal() as session:
        # Создаём или обновляем пользователя
        user = await UserService.get_or_create_user(
            session,
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name,
            referrer_id=referrer_id,
        )

        # Проверяем, является ли пользователь админом
        is_admin = user.telegram_id in settings.admin_ids_list

        if is_admin and not user.is_admin:
            user.is_admin = True
            await session.commit()

        await session.commit()

    # Выбираем клавиатуру
    keyboard = admin_menu_keyboard() if is_admin else main_menu_keyboard()

    import html
    safe_first_name = html.escape(message.from_user.first_name)
    
    welcome_text = f"""
👋 Привет, {safe_first_name}!

🚀 <b>FreedomVPN</b> — твой свободный интернет без границ.
Протокол <b>VLESS + Reality</b> невозможно заблокировать!

⚡️ <b>YouTube 4K</b> без тормозов и буферизации
🛡 <b>Полная анонимность</b> и шифрование
🌍 <b>Доступ</b> к Instagram, Netflix, ChatGPT
📱 Работает на <b>iPhone, Android, PC и Mac</b>

🎁 <b>ПОПРОБУЙ БЕСПЛАТНО (24 часа)</b>
Жми "💰 Купить подписку" ➡️ "Попробовать БЕСПЛАТНО"

👇 Начни прямо сейчас!
"""

    await message.answer(welcome_text, reply_markup=keyboard, parse_mode="HTML")


@router.message(Command("myid"))
async def cmd_myid(message: Message):
    """Показать Telegram ID пользователя"""
    await message.answer(
        f"🆔 Ваш Telegram ID: `{message.from_user.id}`\n\n"
        f"Скопируйте это значение для настройки бота.",
        parse_mode="Markdown"
    )


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
/myid - показать ваш Telegram ID
"""
    await message.answer(help_text)
