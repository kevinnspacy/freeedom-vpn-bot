from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from sqlalchemy import select, func
from datetime import datetime

from database.database import AsyncSessionLocal
from database.models import User, Subscription, Payment, SubscriptionStatus, PaymentStatus
from services.user_service import UserService
from bot.keyboards.inline import admin_panel_keyboard
from config import settings

router = Router()


async def is_admin(telegram_id: int) -> bool:
    """Проверка прав администратора"""
    return telegram_id in settings.admin_ids_list


@router.message(F.text == "👨‍💼 Админ-панель")
async def show_admin_panel(message: Message):
    """Показать админ-панель"""
    if not await is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав администратора")
        return

    text = """
👨‍💼 Админ-панель

Выберите раздел:
"""
    await message.answer(text, reply_markup=admin_panel_keyboard())


@router.callback_query(F.data == "admin_stats")
async def show_admin_stats(callback: CallbackQuery):
    """Показать статистику"""
    if not await is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return

    async with AsyncSessionLocal() as session:
        # Общее количество пользователей
        total_users = await session.scalar(select(func.count(User.id)))

        # Активные подписки
        active_subscriptions = await session.scalar(
            select(func.count(Subscription.id)).where(
                Subscription.status == SubscriptionStatus.ACTIVE
            )
        )

        # Количество платежей сегодня
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        payments_today = await session.scalar(
            select(func.count(Payment.id)).where(
                Payment.created_at >= today_start,
                Payment.status == PaymentStatus.SUCCEEDED
            )
        )

        # Выручка сегодня
        revenue_today = await session.scalar(
            select(func.sum(Payment.amount)).where(
                Payment.created_at >= today_start,
                Payment.status == PaymentStatus.SUCCEEDED
            )
        ) or 0

        # Общая выручка
        total_revenue = await session.scalar(
            select(func.sum(Payment.amount)).where(
                Payment.status == PaymentStatus.SUCCEEDED
            )
        ) or 0

    stats_text = f"""
📊 Статистика

👥 Всего пользователей: {total_users}
✅ Активных подписок: {active_subscriptions}

💰 Платежей сегодня: {payments_today}
💵 Выручка сегодня: {revenue_today:.2f}₽

💸 Общая выручка: {total_revenue:.2f}₽
"""

    await callback.message.edit_text(stats_text, reply_markup=admin_panel_keyboard())
    await callback.answer()


@router.callback_query(F.data == "admin_users")
async def show_admin_users(callback: CallbackQuery):
    """Показать список пользователей"""
    if not await is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return

    async with AsyncSessionLocal() as session:
        # Последние 10 пользователей
        result = await session.execute(
            select(User).order_by(User.created_at.desc()).limit(10)
        )
        users = result.scalars().all()

        if not users:
            await callback.message.edit_text(
                "👥 Пользователи не найдены",
                reply_markup=admin_panel_keyboard()
            )
            return

        users_text = "👥 Последние 10 пользователей:\n\n"
        for user in users:
            username = f"@{user.username}" if user.username else "без username"
            users_text += (
                f"ID: {user.telegram_id}\n"
                f"Имя: {user.first_name or 'N/A'} {user.last_name or ''}\n"
                f"Username: {username}\n"
                f"Регистрация: {user.created_at.strftime('%d.%m.%Y')}\n\n"
            )

    await callback.message.edit_text(users_text, reply_markup=admin_panel_keyboard())
    await callback.answer()


@router.callback_query(F.data == "admin_payments")
async def show_admin_payments(callback: CallbackQuery):
    """Показать последние платежи"""
    if not await is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return

    async with AsyncSessionLocal() as session:
        # Последние 10 платежей
        result = await session.execute(
            select(Payment).order_by(Payment.created_at.desc()).limit(10)
        )
        payments = result.scalars().all()

        if not payments:
            await callback.message.edit_text(
                "💰 Платежи не найдены",
                reply_markup=admin_panel_keyboard()
            )
            return

        payments_text = "💰 Последние 10 платежей:\n\n"
        for payment in payments:
            status_emoji = "✅" if payment.status == PaymentStatus.SUCCEEDED else "⏳"
            payments_text += (
                f"{status_emoji} {payment.amount}₽ - {payment.plan_type}\n"
                f"User ID: {payment.telegram_id}\n"
                f"Дата: {payment.created_at.strftime('%d.%m.%Y %H:%M')}\n"
                f"Статус: {payment.status}\n\n"
            )

    await callback.message.edit_text(payments_text, reply_markup=admin_panel_keyboard())
    await callback.answer()
