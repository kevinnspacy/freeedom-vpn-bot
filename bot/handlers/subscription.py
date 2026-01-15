from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from datetime import datetime

from database.database import AsyncSessionLocal
from services.subscription_service import SubscriptionService
from services.shadowsocks_service import ShadowsocksService
from bot.keyboards.inline import subscription_plans_keyboard

router = Router()
subscription_service = SubscriptionService()
ss_service = ShadowsocksService()


@router.message(F.text == "💰 Купить подписку")
async def show_subscription_plans(message: Message):
    """Показать планы подписки"""
    text = """
💰 Выберите тариф:

1️⃣ День - 100₽
   • Идеально для тестирования

7️⃣ Неделя - 500₽
   • Выгода 30%

🗓 Месяц - 1500₽
   • Выгода 50%

📅 Год - 15000₽
   • Выгода 58%

✨ Все тарифы включают:
• Безлимитный трафик
• Высокая скорость
• Техподдержка 24/7
"""
    await message.answer(text, reply_markup=subscription_plans_keyboard())


@router.message(Command("status"))
@router.message(F.text == "📊 Мой статус")
async def show_status(message: Message):
    """Показать статус подписки"""
    async with AsyncSessionLocal() as session:
        subscription = await subscription_service.get_active_subscription(
            session, message.from_user.id
        )

        if not subscription:
            await message.answer(
                "❌ У вас нет активной подписки.\n\n"
                "💰 Купите подписку, чтобы получить доступ к VPN!",
                reply_markup=subscription_plans_keyboard()
            )
            return

        # Генерируем данные для подключения
        connection_string = ss_service.generate_connection_string(
            subscription.ss_password, subscription.ss_port
        )
        qr_url = ss_service.generate_qr_code_url(connection_string)

        # Рассчитываем оставшееся время
        time_left = subscription.expires_at - datetime.utcnow()
        days_left = time_left.days
        hours_left = time_left.seconds // 3600

        status_text = f"""
✅ Ваша подписка активна!

📅 Тариф: {subscription.plan_type}
⏳ Осталось: {days_left} дней {hours_left} часов
📆 Истекает: {subscription.expires_at.strftime('%d.%m.%Y %H:%M')}

🔐 Данные для подключения:

Сервер: {ss_service.server_host}
Порт: {subscription.ss_port}
Пароль: `{subscription.ss_password}`
Метод шифрования: {subscription.ss_method}

📱 Строка подключения (нажмите, чтобы скопировать):
`{connection_string}`

🔗 QR-код для быстрого подключения:
"""
        await message.answer(status_text, parse_mode="Markdown")
        await message.answer_photo(photo=qr_url, caption="📱 Отсканируйте QR-код в приложении Shadowsocks")


@router.message(F.text == "📱 Инструкция подключения")
async def show_connection_guide(message: Message):
    """Показать инструкцию по подключению"""
    from bot.keyboards.inline import connection_guide_keyboard

    text = """
📱 Инструкция по подключению к Shadowsocks VPN

Выберите вашу платформу:
"""
    await message.answer(text, reply_markup=connection_guide_keyboard())


@router.callback_query(F.data.startswith("guide_"))
async def show_platform_guide(callback: CallbackQuery):
    """Показать инструкцию для платформы"""
    platform = callback.data.split("_")[1]

    guides = {
        "ios": """
📱 Инструкция для iOS:

1. Скачайте Shadowsocks из App Store:
   https://apps.apple.com/app/shadowrocket/id932747118

2. Откройте приложение

3. Нажмите "+" в правом верхнем углу

4. Выберите "Import from QR Code" или введите данные вручную

5. Включите VPN переключателем

✅ Готово! Вы подключены к VPN.
""",
        "android": """
🤖 Инструкция для Android:

1. Скачайте Shadowsocks из Google Play:
   https://play.google.com/store/apps/details?id=com.github.shadowsocks

2. Откройте приложение

3. Нажмите "+" внизу справа

4. Отсканируйте QR-код или введите данные вручную

5. Нажмите на созданный профиль для подключения

✅ Готово! Вы подключены к VPN.
""",
        "windows": """
💻 Инструкция для Windows:

1. Скачайте Shadowsocks:
   https://github.com/shadowsocks/shadowsocks-windows/releases

2. Распакуйте архив и запустите Shadowsocks.exe

3. Правой кнопкой на иконку в трее → Servers → Scan QRCode from Screen

4. Или добавьте сервер вручную через Edit Servers

5. Выберите режим "Global" или "PAC"

✅ Готово! Вы подключены к VPN.
""",
        "macos": """
🍎 Инструкция для macOS:

1. Скачайте ShadowsocksX-NG:
   https://github.com/shadowsocks/ShadowsocksX-NG/releases

2. Установите и запустите приложение

3. Кликните на иконку в строке меню → Servers → Scan QR Code

4. Или добавьте сервер вручную через Server Preferences

5. Включите "Turn Shadowsocks On"

✅ Готово! Вы подключены к VPN.
"""
    }

    guide_text = guides.get(platform, "Инструкция не найдена")
    await callback.message.edit_text(guide_text)
    await callback.answer()
