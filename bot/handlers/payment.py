from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext

from database.database import AsyncSessionLocal
from services.payment_service import PaymentService
from services.subscription_service import SubscriptionService
from bot.keyboards.inline import payment_keyboard, subscription_plans_keyboard
from loguru import logger

router = Router()
payment_service = PaymentService()
subscription_service = SubscriptionService()


@router.callback_query(F.data.startswith("buy_"))
async def process_buy_subscription(callback: CallbackQuery, state: FSMContext):
    """Обработка покупки подписки"""
    plan_type = callback.data.split("_")[1]  # day, week, month, year

    # Проверяем, есть ли уже активная подписка
    async with AsyncSessionLocal() as session:
        existing_subscription = await subscription_service.get_active_subscription(
            session, callback.from_user.id
        )

        if existing_subscription:
            await callback.message.edit_text(
                "⚠️ У вас уже есть активная подписка!\n\n"
                "Новая подписка будет добавлена к текущей.",
            )

    # Создаём платёж
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

                if existing_subscription:
                    # Продлеваем существующую подписку
                    subscription = await subscription_service.extend_subscription(
                        session, existing_subscription, payment.plan_type
                    )
                else:
                    # Создаём новую подписку
                    subscription = await subscription_service.create_subscription(
                        session,
                        telegram_id=callback.from_user.id,
                        plan_type=payment.plan_type,
                    )

                await session.commit()

                # Генерируем данные для подключения
                from services.shadowsocks_service import ShadowsocksService
                ss_service = ShadowsocksService()

                connection_string = ss_service.generate_connection_string(
                    subscription.ss_password, subscription.ss_port
                )
                qr_url = ss_service.generate_qr_code_url(connection_string)

                success_text = f"""
✅ Оплата прошла успешно!

Ваша подписка активирована!

🔐 Данные для подключения:

Сервер: {ss_service.server_host}
Порт: {subscription.ss_port}
Пароль: `{subscription.ss_password}`
Метод: {subscription.ss_method}

📱 Строка подключения:
`{connection_string}`

📆 Действует до: {subscription.expires_at.strftime('%d.%m.%Y %H:%M')}

🔗 QR-код отправлен в следующем сообщении.
"""

                await callback.message.edit_text(success_text, parse_mode="Markdown")
                await callback.message.answer_photo(
                    photo=qr_url,
                    caption="📱 Отсканируйте QR-код в приложении Shadowsocks"
                )

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
    await callback.message.delete()
    await callback.answer()
