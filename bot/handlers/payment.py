from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext

from database.database import AsyncSessionLocal
from services.payment_service import PaymentService
from services.subscription_service import SubscriptionService
from services.user_service import UserService
from services.marzban_service import marzban_service
from bot.keyboards.inline import payment_keyboard, subscription_plans_keyboard, payment_method_keyboard
from loguru import logger

router = Router()
payment_service = PaymentService()
subscription_service = SubscriptionService()


async def send_connection_info(callback: CallbackQuery, subscription, is_trial: bool = False):
    """Отправить информацию о подключении пользователю"""
    # Получаем ссылки из Marzban
    try:
        connection_info = await subscription_service.get_connection_info(subscription)

        if "error" in connection_info:
            raise Exception(connection_info["error"])

        subscription_url = connection_info.get("subscription_url", "")
        links = connection_info.get("links", [])

        # Берём первую VLESS ссылку
        vless_link = ""
        for link in links:
            if link.startswith("vless://"):
                vless_link = link
                break

        title = "🎁 Тестовый период активирован!" if is_trial else "✅ Оплата прошла успешно!"
        subtitle = "Ваша подписка на 72 часа активна!" if is_trial else "Ваша подписка активирована!"

        success_text = f"""
{title}

{subtitle}

🔐 **Подключение VLESS + Reality**

🔗 **Прямая ссылка для подключения (нажмите чтобы скопировать):**
`{vless_link}`

📆 **Действует до:** {subscription.expires_at.strftime('%d.%m.%Y %H:%M')} МСК

━━━━━━━━━━━━━━━━━━━━━━

📲 **Как подключиться:**

**Android:** v2rayNG
**iPhone / iPad:** Streisand, Shadowrocket
**Windows:** v2rayN, Nekoray
**macOS:** V2rayU, Nekoray

1. Скопируйте ссылку подписки
2. Откройте приложение
3. Импортируйте конфигурацию из буфера
4. Подключитесь!

🔗 QR-код отправлен следующим сообщением.
"""

        await callback.message.edit_text(success_text, parse_mode="Markdown")

        # Отправляем QR-код с ссылкой подписки
        qr_url = marzban_service.generate_qr_code_url(subscription_url)
        await callback.message.answer_photo(
            photo=qr_url,
            caption="📱 Отсканируйте QR-код в приложении v2rayNG/Streisand"
        )

    except Exception as e:
        logger.error(f"Failed to get connection info: {e}")
        await callback.message.edit_text(
            f"✅ Подписка активирована!\n\n"
            f"⚠️ Не удалось получить ссылку для подключения.\n"
            f"Попробуйте команду /status для получения данных."
        )


@router.callback_query(F.data == "buy_trial")
async def process_trial_subscription(callback: CallbackQuery):
    """Обработка бесплатного тестового периода"""
    async with AsyncSessionLocal() as session:
        # Проверяем, не использовал ли пользователь уже тестовый период
        trial_used = await subscription_service.has_used_trial(
            session, callback.from_user.id
        )

        if trial_used:
            await callback.message.edit_text(
                "❌ Вы уже использовали тестовый период.\n\n"
                "Выберите один из платных тарифов:",
                reply_markup=subscription_plans_keyboard(show_trial=False)
            )
            await callback.answer()
            return

        # Проверяем активную подписку
        existing_subscription = await subscription_service.get_active_subscription(
            session, callback.from_user.id
        )

        if existing_subscription:
            await callback.message.edit_text(
                "⚠️ У вас уже есть активная подписка!\n\n"
                "Тестовый период доступен только новым пользователям.",
                reply_markup=subscription_plans_keyboard(show_trial=False)
            )
            await callback.answer()
            return

        try:
            # Создаём тестовую подписку на 24 часа
            subscription = await subscription_service.create_subscription(
                session,
                telegram_id=callback.from_user.id,
                plan_type="trial",
                first_name=callback.from_user.first_name or "User",
            )
            await session.commit()

            # Отправляем информацию о подключении
            await send_connection_info(callback, subscription, is_trial=True)

            logger.info(f"Trial subscription created for user {callback.from_user.id}")

        except Exception as e:
            logger.error(f"Failed to create trial subscription: {e}")
            await callback.message.edit_text(
                "❌ Ошибка при создании тестовой подписки. Попробуйте позже.",
                reply_markup=subscription_plans_keyboard()
            )

    await callback.answer()


@router.callback_query(F.data.startswith("buy_"))
async def process_buy_subscription(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора тарифа"""
    plan_type = callback.data.split("_")[1]  # day, week, month, year, trial

    # Если это trial, перенаправляем на специальный обработчик
    if plan_type == "trial":
        return await process_trial_subscription(callback)

    # Проверяем, есть ли уже активная подписка
    async with AsyncSessionLocal() as session:
        existing_subscription = await subscription_service.get_active_subscription(
            session, callback.from_user.id
        )

        text_prefix = ""
        if existing_subscription:
            text_prefix = "⚠️ У вас уже есть активная подписка!\nНовая подписка будет добавлена к текущей.\n\n"

        # Проверяем баланс пользователя
        user = await UserService.get_user_by_telegram_id(session, callback.from_user.id)
        amount = payment_service.get_price(plan_type)
        
        if user and user.balance >= amount:
            await callback.message.edit_text(
                f"{text_prefix}"
                f"💳 Тариф: {payment_service.get_plan_name(plan_type)}\n"
                f"💰 Стоимость: {amount}₽\n"
                f"🏦 Ваш баланс: {user.balance:.0f}₽\n\n"
                "Выберите способ оплаты:",
                reply_markup=payment_method_keyboard(plan_type, amount, user.balance)
            )
            await callback.answer()
            return

    # Если баланса недостаточно или пользователя нет, переходим к оплате картой
    await process_card_payment_logic(callback, state, plan_type)


@router.callback_query(F.data.startswith("pay_card_"))
async def process_card_payment_handler(callback: CallbackQuery, state: FSMContext):
    """Обработка нажатия 'Оплатить картой'"""
    plan_type = callback.data.split("_")[2] # pay_card_day
    await process_card_payment_logic(callback, state, plan_type)


@router.callback_query(F.data.startswith("pay_balance_"))
async def process_balance_payment(callback: CallbackQuery):
    """Обработка оплаты с баланса"""
    plan_type = callback.data.split("_")[2] # pay_balance_day
    amount = payment_service.get_price(plan_type)
    
    async with AsyncSessionLocal() as session:
        user = await UserService.get_user_by_telegram_id(session, callback.from_user.id)
        
        if not user or user.balance < amount:
            await callback.answer("❌ Недостаточно средств на балансе", show_alert=True)
            return

        # Списываем баланс
        user.balance -= amount
        
        # Создаем или продлеваем подписку
        existing_subscription = await subscription_service.get_active_subscription(
            session, callback.from_user.id
        )
        
        first_name = callback.from_user.first_name or "User"

        if existing_subscription:
            subscription = await subscription_service.extend_subscription(
                session, existing_subscription, plan_type, first_name
            )
        else:
            subscription = await subscription_service.create_subscription(
                session, callback.from_user.id, plan_type, first_name
            )

        # Начисляем реферальный бонус пригласившему (даже при оплате с баланса? Да, почему нет, если деньги реальные были)
        # Хотя стоп, баланс уже бонусный. Начислять бонусы с бонусов? Это инфляция.
        # Обычно с бонусных оплат реферальные НЕ начисляются. 
        # Давайте НЕ начислять реф. бонус при оплате с баланса.
        
        await session.commit()
        
        await send_connection_info(callback, subscription, is_trial=False)
        await callback.answer("✅ Оплата прошла успешно!")


async def process_card_payment_logic(callback: CallbackQuery, state: FSMContext, plan_type: str):
    """Логика создания платежа YooKassa"""
    async with AsyncSessionLocal() as session:
        try:
            payment = await payment_service.create_payment(
                session,
                telegram_id=callback.from_user.id,
                plan_type=plan_type,
            )
            await session.commit()

            # Сохраняем ID платежа в состояние
            await state.update_data(payment_id=payment.yukassa_payment_id)

            plan_name = payment_service.get_plan_name(plan_type)
            amount = payment_service.get_price(plan_type)

            payment_text = f"""
💳 Счёт на оплату создан!

📦 Тариф: {plan_name}
💰 Сумма: {amount}₽

Нажмите кнопку "Оплатить", чтобы перейти к оплате.
После оплаты нажмите "Проверить оплату".
"""

            await callback.message.edit_text(
                payment_text,
                reply_markup=payment_keyboard(payment.confirmation_url)
            )

        except Exception as e:
            logger.error(f"Failed to create payment: {e}")
            await callback.message.edit_text(
                "❌ Ошибка при создании платежа. Попробуйте позже.",
                reply_markup=subscription_plans_keyboard()
            )
    
    await callback.answer()


@router.callback_query(F.data == "check_payment")
async def check_payment_status(callback: CallbackQuery, state: FSMContext):
    """Проверка статуса платежа"""
    data = await state.get_data()
    payment_id = data.get("payment_id")

    if not payment_id:
        await callback.answer("❌ Платёж не найден", show_alert=True)
        return

    async with AsyncSessionLocal() as session:
        try:
            # Проверяем статус платежа
            status = await payment_service.check_payment_status(session, payment_id)

            if status == "succeeded":
                # Получаем данные о платеже
                payment = await payment_service.get_payment_by_yukassa_id(session, payment_id)

                if not payment:
                    await callback.answer("❌ Платёж не найден", show_alert=True)
                    return

                # Проверяем, есть ли активная подписка
                existing_subscription = await subscription_service.get_active_subscription(
                    session, callback.from_user.id
                )

                first_name = callback.from_user.first_name or "User"

                if existing_subscription:
                    # Продлеваем существующую подписку
                    subscription = await subscription_service.extend_subscription(
                        session, existing_subscription, payment.plan_type, first_name
                    )
                else:
                    # Создаём новую подписку
                    subscription = await subscription_service.create_subscription(
                        session,
                        telegram_id=callback.from_user.id,
                        plan_type=payment.plan_type,
                        first_name=first_name,
                    )

                # Начисляем реферальный бонус
                if payment.amount:
                    await UserService.accrue_referral_bonus(session, callback.from_user.id, payment.amount)

                await session.commit()

                # Отправляем информацию о подключении
                await send_connection_info(callback, subscription, is_trial=False)

                # Очищаем состояние
                await state.clear()

            elif status == "pending":
                await callback.answer(
                    "⏳ Платёж ещё не обработан. Попробуйте через минуту.",
                    show_alert=True
                )
            else:
                await callback.answer(
                    "❌ Платёж не прошёл. Попробуйте снова.",
                    show_alert=True
                )
                await state.clear()

        except Exception as e:
            logger.error(f"Failed to check payment: {e}")
            await callback.answer(
                "❌ Ошибка при проверке платежа",
                show_alert=True
            )


@router.callback_query(F.data == "cancel_payment")
async def cancel_payment(callback: CallbackQuery, state: FSMContext):
    """Отмена платежа"""
    await state.clear()
    await callback.message.edit_text(
        "❌ Платёж отменён.",
        reply_markup=subscription_plans_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "back_to_menu")
async def back_to_menu(callback: CallbackQuery):
    """Вернуться в главное меню"""
    from bot.keyboards.inline import main_menu_keyboard
    from config import settings

    is_admin = callback.from_user.id in settings.admin_ids_list

    text = """
🚀 <b>FreedomVPN</b> — твой свободный интернет без границ.

Выберите действие:
"""
    await callback.message.edit_text(
        text,
        reply_markup=main_menu_keyboard(is_admin=is_admin),
        parse_mode="HTML"
    )
    await callback.answer()
