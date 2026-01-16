from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from datetime import datetime

from database.database import AsyncSessionLocal
from services.subscription_service import SubscriptionService

from bot.keyboards.inline import subscription_plans_keyboard

router = Router()
subscription_service = SubscriptionService()



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

        # Получаем данные о подключении из Marzban
        connection_info = await subscription_service.get_connection_info(subscription)
        
        if "error" in connection_info:
             await message.answer("⚠️ Ошибка получения данных подписки. Обратитесь к админу.")
             return

        subscription_url = connection_info.get("subscription_url", "")
        # Берем первую ссылку из списка или subscription url
        links = connection_info.get("links", [])
        vless_link = links[0] if links else subscription_url

        # Рассчитываем оставшееся время
        time_left = subscription.expires_at - datetime.utcnow()
        days_left = time_left.days
        hours_left = time_left.seconds // 3600

        status_text = f"""
✅ Ваша подписка активна!

📅 Тариф: {subscription.plan_type}
⏳ Осталось: {days_left} дней {hours_left} часов
📆 Истекает: {subscription.expires_at.strftime('%d.%m.%Y %H:%M')}

🔐 **Подключение VLESS + Reality**

🔗 **Прямая ссылка (нажмите чтобы скопировать):**
`{vless_link}`

"""
        from services.marzban_service import marzban_service
        qr_url = marzban_service.generate_qr_code_url(subscription_url)
        
        await message.answer(status_text, parse_mode="Markdown")
        await message.answer_photo(photo=qr_url, caption="📱 Отсканируйте QR-код или импортируйте ссылку в VLESS-клиент")


@router.message(F.text == "📱 Инструкция подключения")
async def show_connection_guide(message: Message):
    """Показать инструкцию по подключению"""
    from bot.keyboards.inline import connection_guide_keyboard

    text = """
📱 Инструкция по подключению к VPN (VLESS + Reality)

Выберите вашу платформу:
"""
    await message.answer(text, reply_markup=connection_guide_keyboard())


@router.callback_query(F.data.startswith("guide_"))
async def show_platform_guide(callback: CallbackQuery):
    """Показать инструкцию для платформы"""
    platform = callback.data.split("_")[1]

    guides = {
        "ios": """
📱 Инструкция для iPhone / iPad:

1. Скачайте Streisand из App Store (бесплатно):
   https://apps.apple.com/app/streisand/id6450534064

   Или Hiddify:
   https://apps.apple.com/app/hiddify-proxy-vpn/id6596777532

2. Откройте приложение

3. Скопируйте вашу VLESS-ссылку из бота

4. Нажмите "+" → "Добавить из буфера"

5. Нажмите на созданный профиль → Подключиться

✅ Готово! Вы подключены к VPN.

💡 Streisand — бесплатный и простой
💡 Hiddify — больше функций
""",
        "android": """
🤖 Инструкция для Android:

1. Скачайте v2rayNG из Google Play:
   https://play.google.com/store/apps/details?id=com.v2ray.ang

   Или Hiddify:
   https://play.google.com/store/apps/details?id=app.hiddify.com

2. Откройте приложение

3. Скопируйте вашу VLESS-ссылку из бота

4. Нажмите "+" → "Импорт из буфера обмена"

5. Нажмите на профиль → кнопка ▶️ внизу

✅ Готово! Вы подключены к VPN.

💡 v2rayNG — классика, работает стабильно
💡 Hiddify — современный интерфейс
""",
        "windows": """
💻 Инструкция для Windows:

1. Скачайте Hiddify:
   https://github.com/hiddify/hiddify-next/releases
   (файл Hiddify-Windows-Setup.exe)

2. Установите и запустите приложение

3. Скопируйте вашу VLESS-ссылку из бота

4. Нажмите "+" → "Добавить из буфера"

5. Выберите профиль и нажмите "Подключиться"

✅ Готово! Вы подключены к VPN.

💡 Альтернатива: v2rayN
   https://github.com/2dust/v2rayN/releases
""",
        "macos": """
🍎 Инструкция для macOS:

1. Скачайте Hiddify:
   https://github.com/hiddify/hiddify-next/releases
   (файл Hiddify-MacOS.dmg)

2. Установите и запустите приложение

3. Скопируйте вашу VLESS-ссылку из бота

4. Нажмите "+" → "Добавить из буфера"

5. Выберите профиль и нажмите "Подключиться"

✅ Готово! Вы подключены к VPN.

💡 Альтернатива: V2RayXS
   https://github.com/tzmax/V2RayXS/releases
"""
    }

    guide_text = guides.get(platform, "Инструкция не найдена")
    await callback.message.edit_text(guide_text)
    await callback.answer()
