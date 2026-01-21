from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from datetime import datetime

from database.database import AsyncSessionLocal
from services.subscription_service import SubscriptionService

from bot.keyboards.inline import subscription_plans_keyboard
from config import settings

router = Router()
subscription_service = SubscriptionService()



@router.message(F.text == "💰 Купить подписку")
async def show_subscription_plans(message: Message):
    """Показать планы подписки (текстовая кнопка)"""
    await _show_subscription_plans(message)


@router.callback_query(F.data == "buy_subscription")
async def callback_buy_subscription(callback: CallbackQuery):
    """Показать планы подписки (inline кнопка)"""
    text = f"""
💰 <b>Выберите тариф:</b>

1️⃣ День - {settings.PRICE_DAY}₽
   • Идеально для тестирования

7️⃣ Неделя - {settings.PRICE_WEEK}₽
   • Выгода 22%

🗓 Месяц - {settings.PRICE_MONTH}₽
   • Выгода 45%

📆 3 месяца - {settings.PRICE_3MONTH}₽
   • Выгода 51%

📅 Год - {settings.PRICE_YEAR}₽
   • Выгода 54%

✨ <b>Все тарифы включают:</b>
• Безлимитный трафик
• Высокая скорость
• Техподдержка 24/7
"""
    await callback.message.edit_text(text, reply_markup=subscription_plans_keyboard(), parse_mode="HTML")
    await callback.answer()


async def _show_subscription_plans(message: Message):
    """Внутренняя функция показа планов"""
    text = f"""
💰 Выберите тариф:

1️⃣ День - {settings.PRICE_DAY}₽
   • Идеально для тестирования

7️⃣ Неделя - {settings.PRICE_WEEK}₽
   • Выгода 22%

🗓 Месяц - {settings.PRICE_MONTH}₽
   • Выгода 45%

📆 3 месяца - {settings.PRICE_3MONTH}₽
   • Выгода 51%

📅 Год - {settings.PRICE_YEAR}₽
   • Выгода 54%

✨ Все тарифы включают:
• Безлимитный трафик
• Высокая скорость
• Техподдержка 24/7
"""
    await message.answer(text, reply_markup=subscription_plans_keyboard())


@router.message(Command("status"))
@router.message(F.text == "📊 Мой статус")
async def show_status(message: Message):
    """Показать статус подписки (текстовая команда)"""
    await _show_status(message)


@router.callback_query(F.data == "my_status")
async def callback_my_status(callback: CallbackQuery):
    """Показать статус подписки (inline кнопка)"""
    await _show_status(callback.message, callback)


async def _show_status(message: Message, callback: CallbackQuery = None):
    """Показать статус подписки"""
    user_id = callback.from_user.id if callback else message.from_user.id
    async with AsyncSessionLocal() as session:
        subscription = await subscription_service.get_active_subscription(
            session, user_id
        )

        if not subscription:
            no_sub_text = "❌ У вас нет активной подписки.\n\n💰 Купите подписку, чтобы получить доступ к VPN!"
            if callback:
                await callback.message.edit_text(no_sub_text, reply_markup=subscription_plans_keyboard())
                await callback.answer()
            else:
                await message.answer(no_sub_text, reply_markup=subscription_plans_keyboard())
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

        # Определяем статус
        if days_left < 1:
            time_status = f"⏰ <b>{hours_left} часов</b>"
            urgency = "🔴" if hours_left < 3 else "🟡"
        else:
            time_status = f"⏳ <b>{days_left} дней {hours_left} часов</b>"
            urgency = "🟢" if days_left > 3 else "🟡"

        # Название тарифа
        plan_names = {
            "trial": "Тестовый (24 часа)",
            "day": "1 день",
            "week": "1 неделя",
            "month": "1 месяц",
            "3month": "3 месяца",
            "year": "1 год"
        }
        plan_name = plan_names.get(subscription.plan_type, subscription.plan_type)

        status_text = f"""
{urgency} <b>Подписка активна!</b>

📋 <b>Информация о подписке:</b>
├ Тариф: <b>{plan_name}</b>
├ Осталось: {time_status}
└ Истекает: <b>{subscription.expires_at.strftime('%d.%m.%Y в %H:%M')}</b>

🔐 <b>Подключение VLESS + Reality</b>

🔗 <b>Ваша ссылка подключения:</b>
<code>{vless_link}</code>

💡 <i>Нажмите на ссылку для копирования</i>

━━━━━━━━━━━━━━━━━━━━━
📱 <b>Как подключиться:</b>
• <b>Android:</b> v2rayNG
• <b>iPhone:</b> Streisand, Shadowrocket
• <b>Windows:</b> v2rayN, Nekoray
• <b>macOS:</b> V2rayU, Nekoray

📥 <i>QR-код для быстрого подключения ↓</i>
"""
        from services.marzban_service import marzban_service
        from bot.keyboards.inline import status_keyboard
        qr_url = marzban_service.generate_qr_code_url(subscription_url)

        await message.answer(status_text, parse_mode="HTML", reply_markup=status_keyboard())
        await message.answer_photo(
            photo=qr_url,
            caption=f"📱 <b>QR-код для подключения</b>\n\nОтсканируйте в приложении VLESS-клиента\n\n⏰ Действителен до: {subscription.expires_at.strftime('%d.%m.%Y %H:%M')}",
            parse_mode="HTML"
        )


@router.message(F.text == "📱 Инструкция подключения")
async def show_connection_guide(message: Message):
    """Показать инструкцию по подключению (текстовая кнопка)"""
    from bot.keyboards.inline import connection_guide_keyboard

    text = """
📱 <b>Инструкция по подключению к VPN</b>
<i>(VLESS + Reality)</i>

Выберите вашу платформу:
"""
    await message.answer(text, reply_markup=connection_guide_keyboard(), parse_mode="HTML")


@router.callback_query(F.data == "connection_guide")
async def callback_connection_guide(callback: CallbackQuery):
    """Показать инструкцию по подключению (inline кнопка)"""
    from bot.keyboards.inline import connection_guide_keyboard

    text = """
📱 <b>Инструкция по подключению к VPN</b>
<i>(VLESS + Reality)</i>

Выберите вашу платформу:
"""
    await callback.message.edit_text(text, reply_markup=connection_guide_keyboard(), parse_mode="HTML")
    await callback.answer()


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
    from bot.keyboards.inline import back_to_menu_keyboard
    await callback.message.edit_text(guide_text, reply_markup=back_to_menu_keyboard())
    await callback.answer()
