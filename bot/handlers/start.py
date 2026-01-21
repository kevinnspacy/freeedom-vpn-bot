from aiogram import Router, F
from aiogram.filters import CommandStart, Command, CommandObject
from aiogram.types import Message, ReplyKeyboardRemove
from sqlalchemy.ext.asyncio import AsyncSession

from database.database import AsyncSessionLocal
from services.user_service import UserService
from services.referral_service import referral_service
from services.subscription_service import SubscriptionService
from bot.keyboards.inline import main_menu_keyboard as inline_main_menu
from config import settings

router = Router()
subscription_service = SubscriptionService()


@router.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject):
    """Обработчик команды /start"""
    from loguru import logger
    logger.info(f"START command from user {message.from_user.id}")

    try:
        referrer_id = None
        referral_message = ""
        show_trial = True

        args = command.args

        async with AsyncSessionLocal() as session:
            # Проверяем реферальный код
            if args:
                # Новый формат: ref_code
                if args.startswith("ref_"):
                    referrer = await referral_service.get_user_by_referral_code(session, args)
                    if referrer and referrer.telegram_id != message.from_user.id:
                        referrer_id = referrer.telegram_id
                        referral_message = f"\n\n🎁 Вы пришли по реферальной ссылке от {referrer.first_name or 'пользователя'}!"
                # Старый формат: telegram_id
                elif args.isdigit():
                    referrer_id = int(args)
                    if referrer_id == message.from_user.id:
                        referrer_id = None

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

            # Проверяем, использовал ли пользователь тестовый период
            show_trial = not await subscription_service.has_used_trial(session, message.from_user.id)

            if is_admin and not user.is_admin:
                user.is_admin = True
                await session.commit()

            await session.commit()

        import html
        safe_first_name = html.escape(message.from_user.first_name or "друг")

        if show_trial:
            welcome_text = f"""
👋 Привет, {safe_first_name}!

🚀 <b>FreedomVPN</b> — твой свободный интернет без границ.
Протокол <b>VLESS + Reality</b> невозможно заблокировать!

⚡️ <b>YouTube 4K</b> без тормозов и буферизации
🛡 <b>Полная анонимность</b> и шифрование
🌍 <b>Доступ</b> к Instagram, Netflix, ChatGPT
📱 Работает на <b>iPhone, Android, PC и Mac</b>

🎁 <b>ПОПРОБУЙ БЕСПЛАТНО (72 часа)</b>
Жми кнопку ниже!

👇 Начни прямо сейчас!
"""
        else:
            welcome_text = f"""
👋 С возвращением, {safe_first_name}!

🚀 <b>FreedomVPN</b> — твой свободный интернет без границ.

👇 Выберите действие:
"""

        # Убираем старую reply-клавиатуру и отправляем inline-кнопки
        await message.answer(
            welcome_text + referral_message,
            reply_markup=inline_main_menu(is_admin=is_admin, show_trial=show_trial),
            parse_mode="HTML"
        )
        logger.info(f"START command completed for user {message.from_user.id}")
    except Exception as e:
        logger.error(f"START command FAILED for user {message.from_user.id}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        await message.answer("Произошла ошибка. Попробуйте ещё раз /start")


@router.message(Command("myid"))
async def cmd_myid(message: Message):
    """Показать Telegram ID пользователя"""
    await message.answer(
        f"🆔 Ваш Telegram ID: `{message.from_user.id}`\n\n"
        f"Скопируйте это значение для настройки бота.",
        parse_mode="Markdown"
    )


@router.message(Command("menu"))
async def cmd_menu(message: Message):
    """Команда /menu - показать главное меню"""
    is_admin = message.from_user.id in settings.admin_ids_list

    text = """
🚀 <b>FreedomVPN</b> — твой свободный интернет без границ.

Выберите действие:
"""
    await message.answer(text, reply_markup=inline_main_menu(is_admin=is_admin), parse_mode="HTML")


@router.message(Command("help"))
@router.message(F.text == "❓ Помощь")
async def cmd_help(message: Message):
    """Обработчик команды /help"""
    is_admin = message.from_user.id in settings.admin_ids_list

    help_text = f"""
📖 <b>Справка по использованию бота:</b>

💰 <b>Купить подписку</b> - выбрать и оплатить тариф
📊 <b>Мой статус</b> - проверить активную подписку
📱 <b>Инструкция</b> - как подключиться к VPN
❓ <b>Помощь</b> - это сообщение

📞 <b>Поддержка:</b> @{settings.SUPPORT_USERNAME}

Команды:
/start - начать работу
/menu - главное меню
/help - справка
/status - проверить статус подписки
/myid - показать ваш Telegram ID
"""
    await message.answer(help_text, reply_markup=inline_main_menu(is_admin=is_admin), parse_mode="HTML")
