"""
Обработчики реферальной системы и промокодов
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from database.database import AsyncSessionLocal
from services.user_service import UserService
from services.referral_service import referral_service
from services.promocode_service import promocode_service
from services.subscription_service import SubscriptionService
from bot.keyboards.inline import referral_keyboard, back_to_menu_keyboard, main_menu_keyboard
from config import settings
from loguru import logger


router = Router()
subscription_service = SubscriptionService()


class PromocodeStates(StatesGroup):
    """Состояния для ввода промокода"""
    waiting_for_code = State()


@router.message(Command("referral", "ref"))
async def cmd_referral(message: Message):
    """Команда /referral - показать реферальную программу"""
    await show_referral_info(message.from_user.id, message)


@router.callback_query(F.data == "referral")
async def callback_referral(callback: CallbackQuery):
    """Кнопка 'Реферальная программа'"""
    await show_referral_info(callback.from_user.id, callback.message, callback)


async def show_referral_info(telegram_id: int, message: Message, callback: CallbackQuery | None = None):
    """Показать информацию о реферальной программе"""

    async with AsyncSessionLocal() as session:
        # Получаем или создаём реферальный код
        referral_code = await referral_service.create_or_get_referral_code(session, telegram_id)

        # Получаем статистику
        stats = await referral_service.get_referral_stats(session, telegram_id)

        # Получаем информацию о пользователе
        user = await UserService.get_user_by_telegram_id(session, telegram_id)

        referral_link = f"https://t.me/{settings.BOT_USERNAME}?start={referral_code}"

        text = f"""
👥 **Реферальная программа**

Приглашайте друзей и получайте **{referral_service.REFERRAL_PERCENTAGE}%** от их платежей!

🔗 **Ваша реферальная ссылка:**
`{referral_link}`

📊 **Ваша статистика:**
• Рефералов: **{stats['referrals_count']}**
• Заработано: **{stats['total_earned']:.2f}₽**
• Баланс: **{user.balance:.2f}₽**

💡 **Как это работает:**
1. Отправьте ссылку другу
2. Друг регистрируется по вашей ссылке
3. Когда друг оплачивает подписку, вы получаете {referral_service.REFERRAL_PERCENTAGE}% на баланс
4. Баланс можно использовать для оплаты подписки

🎁 **Выгода:**
• При оплате 1499₽ вы получаете **{1499 * referral_service.REFERRAL_PERCENTAGE / 100:.0f}₽**
• 10 друзей = **{10 * 1499 * referral_service.REFERRAL_PERCENTAGE / 100:.0f}₽** на баланс!
"""

        if stats['recent_referrals']:
            text += "\n👤 **Последние рефералы:**\n"
            for ref in stats['recent_referrals'][:3]:
                name = ref.first_name or "Пользователь"
                text += f"• {name} - {ref.created_at.strftime('%d.%m.%Y')}\n"

        if callback:
            await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=referral_keyboard(referral_link))
            await callback.answer()
        else:
            await message.answer(text, parse_mode="Markdown", reply_markup=referral_keyboard(referral_link))


@router.callback_query(F.data == "copy_referral_link")
async def callback_copy_link(callback: CallbackQuery):
    """Отправить ссылку отдельным сообщением для копирования"""
    async with AsyncSessionLocal() as session:
        referral_code = await referral_service.create_or_get_referral_code(session, callback.from_user.id)
        referral_link = f"https://t.me/{settings.BOT_USERNAME}?start={referral_code}"

        # Отправляем ссылку отдельным сообщением (легко скопировать)
        await callback.message.answer(
            f"📋 <b>Ваша реферальная ссылка:</b>\n\n"
            f"<code>{referral_link}</code>\n\n"
            f"👆 Нажмите на ссылку, чтобы скопировать",
            parse_mode="HTML"
        )
        await callback.answer("Ссылка отправлена!")


@router.callback_query(F.data == "withdraw_balance")
async def callback_withdraw(callback: CallbackQuery):
    """Вывод средств с баланса (пока недоступно)"""
    await callback.answer(
        "🔜 Функция вывода средств появится в ближайшее время!\n"
        "Пока вы можете использовать баланс для оплаты подписки.",
        show_alert=True
    )


@router.callback_query(F.data == "enter_promocode")
async def callback_enter_promocode(callback: CallbackQuery, state: FSMContext):
    """Ввод промокода"""
    from bot.keyboards.inline import back_to_menu_keyboard

    text = """
🎁 <b>Введите промокод</b>

Отправьте промокод в чат, чтобы активировать скидку или бонус.

<i>Пример: PROMOCODE</i>
"""
    await callback.message.edit_text(text, reply_markup=back_to_menu_keyboard(), parse_mode="HTML")
    await state.set_state(PromocodeStates.waiting_for_code)
    await state.update_data(attempts=0)
    await callback.answer()


@router.message(PromocodeStates.waiting_for_code)
async def process_promocode_input(message: Message, state: FSMContext):
    """Обработка введённого промокода"""
    code = message.text.strip().upper()

    # Получаем количество попыток
    data = await state.get_data()
    attempts = data.get("attempts", 0) + 1
    await state.update_data(attempts=attempts)

    async with AsyncSessionLocal() as session:
        # Валидируем промокод (plan_type пока не важен для bonus_days)
        validation = await promocode_service.validate_promocode(
            session, code, message.from_user.id, "any"
        )

        if not validation["valid"]:
            if attempts >= 5:
                # После 5 неудачных попыток - возврат в главное меню
                is_admin = message.from_user.id in settings.admin_ids_list
                await message.answer(
                    f"❌ {validation['error']}\n\n"
                    f"Вы исчерпали 5 попыток ввода промокода.",
                    reply_markup=main_menu_keyboard(is_admin=is_admin),
                    parse_mode="HTML"
                )
                await state.clear()
            else:
                # Предлагаем попробовать ещё раз
                await message.answer(
                    f"❌ {validation['error']}\n\n"
                    f"Попробуйте другой промокод (попытка {attempts}/5)",
                    reply_markup=back_to_menu_keyboard(),
                    parse_mode="HTML"
                )
            return

        promocode = validation["promocode"]

        # Если это промокод на бонусные дни - создаём подписку бесплатно
        if promocode.discount_type == "bonus_days":
            bonus_days = int(promocode.discount_value)

            # Проверяем активную подписку
            existing_subscription = await subscription_service.get_active_subscription(
                session, message.from_user.id
            )

            first_name = message.from_user.first_name or "User"

            if existing_subscription:
                # Продлеваем существующую подписку
                # Конвертируем дни в тип плана (приблизительно)
                if bonus_days <= 1:
                    plan_type = "day"
                elif bonus_days <= 7:
                    plan_type = "week"
                elif bonus_days <= 30:
                    plan_type = "month"
                else:
                    plan_type = "month"

                subscription = await subscription_service.extend_subscription(
                    session, existing_subscription, plan_type, first_name
                )
            else:
                # Создаём новую подписку
                if bonus_days <= 1:
                    plan_type = "day"
                elif bonus_days <= 7:
                    plan_type = "week"
                elif bonus_days <= 30:
                    plan_type = "month"
                else:
                    plan_type = "month"

                subscription = await subscription_service.create_subscription(
                    session, message.from_user.id, plan_type, first_name
                )

            # Применяем промокод (записываем использование)
            await promocode_service.apply_promocode(
                session, promocode, message.from_user.id, 0, None
            )

            await session.commit()

            # Получаем ссылку для подключения
            connection_info = await subscription_service.get_connection_info(subscription)
            links = connection_info.get("links", [])
            vless_link = ""
            for link in links:
                if link.startswith("vless://"):
                    vless_link = link
                    break

            success_text = f"""
🎉 <b>Промокод активирован!</b>

✅ Вам начислено <b>{bonus_days} дней</b> подписки!

📆 <b>Действует до:</b> {subscription.expires_at.strftime('%d.%m.%Y %H:%M')}

🔗 <b>Ваша ссылка для подключения:</b>
<code>{vless_link}</code>

💡 <i>Нажмите на ссылку, чтобы скопировать</i>
"""
            is_admin = message.from_user.id in settings.admin_ids_list
            await message.answer(success_text, parse_mode="HTML", reply_markup=main_menu_keyboard(is_admin=is_admin))

            # Отправляем QR-код
            from services.marzban_service import marzban_service
            subscription_url = connection_info.get("subscription_url", "")
            if subscription_url:
                qr_url = marzban_service.generate_qr_code_url(subscription_url)
                await message.answer_photo(
                    photo=qr_url,
                    caption="📱 QR-код для подключения"
                )

            logger.info(f"Promocode {code} activated for user {message.from_user.id}: {bonus_days} days")

        else:
            # Для промокодов со скидкой - сохраняем в состояние и показываем сообщение
            await state.update_data(promocode_id=promocode.id, promocode_code=code)

            discount_text = ""
            if promocode.discount_type == "percent":
                discount_text = f"скидка {int(promocode.discount_value)}%"
            elif promocode.discount_type == "fixed":
                discount_text = f"скидка {int(promocode.discount_value)}₽"

            is_admin = message.from_user.id in settings.admin_ids_list
            await message.answer(
                f"✅ <b>Промокод {code} принят!</b>\n\n"
                f"🎁 Вы получите: <b>{discount_text}</b>\n\n"
                f"Теперь выберите тариф для покупки:",
                parse_mode="HTML",
                reply_markup=main_menu_keyboard(is_admin=is_admin)
            )

    await state.clear()


@router.callback_query(F.data == "referral_stats")
async def callback_referral_stats(callback: CallbackQuery):
    """Подробная статистика рефералов"""
    async with AsyncSessionLocal() as session:
        stats = await referral_service.get_referral_stats(session, callback.from_user.id)
        user = await UserService.get_user_by_telegram_id(session, callback.from_user.id)

        text = f"""
📊 <b>Подробная статистика</b>

👥 Всего рефералов: <b>{stats['referrals_count']}</b>
💰 Всего заработано: <b>{stats['total_earned']:.2f}₽</b>
💳 Текущий баланс: <b>{user.balance:.2f}₽</b>

<i>Баланс можно использовать для оплаты подписки</i>
"""

        if stats['recent_referrals']:
            text += "\n\n👤 <b>Последние рефералы:</b>\n"
            for ref in stats['recent_referrals'][:5]:
                name = ref.first_name or "Пользователь"
                text += f"• {name} - {ref.created_at.strftime('%d.%m.%Y')}\n"

        from bot.keyboards.inline import back_to_menu_keyboard
        await callback.message.edit_text(text, reply_markup=back_to_menu_keyboard(), parse_mode="HTML")
        await callback.answer()
