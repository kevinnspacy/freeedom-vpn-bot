from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.exceptions import TelegramBadRequest
from sqlalchemy import select, func
from datetime import datetime

from database.database import AsyncSessionLocal
from database.models import User, Subscription, Payment, SubscriptionStatus, PaymentStatus
from services.user_service import UserService
from services.marzban_service import marzban_service
from services.promocode_service import promocode_service
from bot.keyboards.inline import admin_panel_keyboard
from config import settings
from loguru import logger

router = Router()


async def is_admin(telegram_id: int) -> bool:
    """Проверка прав администратора"""
    return telegram_id in settings.admin_ids_list


@router.message(F.text == "👨‍💼 Админ-панель")
async def show_admin_panel(message: Message):
    """Показать админ-панель (reply keyboard)"""
    if not await is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав администратора")
        return

    text = """
👨‍💼 Админ-панель

Выберите раздел:
"""
    await message.answer(text, reply_markup=admin_panel_keyboard())


@router.callback_query(F.data == "admin_panel")
async def show_admin_panel_callback(callback: CallbackQuery):
    """Показать админ-панель (inline keyboard)"""
    if not await is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return

    text = """
👨‍💼 <b>Админ-панель</b>

Выберите раздел:
"""
    try:
        await callback.message.edit_text(text, reply_markup=admin_panel_keyboard(), parse_mode="HTML")
    except TelegramBadRequest:
        pass
    await callback.answer()


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

        # Трафик из Marzban
        marzban_users = await marzban_service.get_all_users()
        total_traffic_bytes = sum(u.get("used_traffic", 0) for u in marzban_users)
        total_traffic_gb = total_traffic_bytes / (1024 ** 3)
        total_traffic_formatted = f"{total_traffic_gb:.2f} GB"
        if total_traffic_gb > 1024:
            total_traffic_formatted = f"{total_traffic_gb / 1024:.2f} TB"

    stats_text = f"""
📊 Статистика

👥 Всего пользователей: {total_users}
✅ Активных подписок: {active_subscriptions}
🌐 Использовано трафика: {total_traffic_formatted}

💰 Платежей сегодня: {payments_today}
💵 Выручка сегодня: {revenue_today:.2f}₽

💸 Общая выручка: {total_revenue:.2f}₽
"""

    try:
        await callback.message.edit_text(stats_text, reply_markup=admin_panel_keyboard())
    except TelegramBadRequest:
        pass
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
            try:
                await callback.message.edit_text(
                    "👥 Пользователи не найдены",
                    reply_markup=admin_panel_keyboard()
                )
            except TelegramBadRequest:
                pass
            return

        users_text = "👥 <b>Последние 10 пользователей:</b>\n\n"
        for user in users:
            username = f"@{user.username}" if user.username else "без username"
            reg_date = user.created_at.strftime('%d.%m.%Y') if user.created_at else "N/A"
            users_text += (
                f"🆔 <code>{user.telegram_id}</code>\n"
                f"👤 {user.first_name or 'N/A'} {user.last_name or ''}\n"
                f"📱 {username}\n"
                f"📅 {reg_date}\n"
                f"{'─' * 20}\n"
            )

        try:
            await callback.message.edit_text(users_text, reply_markup=admin_panel_keyboard(), parse_mode="HTML")
        except TelegramBadRequest:
            pass

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
            try:
                await callback.message.edit_text(
                    "💰 Платежи не найдены",
                    reply_markup=admin_panel_keyboard()
                )
            except TelegramBadRequest:
                pass
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

    try:
        await callback.message.edit_text(payments_text, reply_markup=admin_panel_keyboard())
    except TelegramBadRequest:
        pass
    await callback.answer()


@router.message(Command("createpromo"))
async def cmd_create_promocode(message: Message):
    """
    Создать промокод (только для админов)

    Формат: /createpromo CODE TYPE VALUE [MAX_USES]

    TYPE:
    - bonus_days: бонусные дни (VALUE = количество дней)
    - percent: процентная скидка (VALUE = процент)
    - fixed: фиксированная скидка (VALUE = сумма в рублях)

    Примеры:
    /createpromo FREEWEEK bonus_days 7 100
    /createpromo SALE50 percent 50
    /createpromo DISCOUNT100 fixed 100 50
    """
    if not await is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав администратора")
        return

    args = message.text.split()[1:]  # Убираем /createpromo

    if len(args) < 3:
        await message.answer(
            "❌ <b>Неверный формат команды</b>\n\n"
            "Формат: <code>/createpromo CODE TYPE VALUE [MAX_USES]</code>\n\n"
            "<b>TYPE:</b>\n"
            "• <code>bonus_days</code> - бонусные дни (VALUE = дни)\n"
            "• <code>percent</code> - скидка в % (VALUE = процент)\n"
            "• <code>fixed</code> - скидка в ₽ (VALUE = сумма)\n\n"
            "<b>Примеры:</b>\n"
            "<code>/createpromo FREEWEEK bonus_days 7 100</code>\n"
            "<code>/createpromo SALE50 percent 50</code>\n"
            "<code>/createpromo VIP100 fixed 100 50</code>",
            parse_mode="HTML"
        )
        return

    code = args[0].upper()
    discount_type = args[1].lower()

    try:
        discount_value = float(args[2])
    except ValueError:
        await message.answer("❌ VALUE должно быть числом")
        return

    max_uses = None
    if len(args) >= 4:
        try:
            max_uses = int(args[3])
        except ValueError:
            await message.answer("❌ MAX_USES должно быть целым числом")
            return

    # Проверяем тип скидки
    if discount_type not in ["bonus_days", "percent", "fixed"]:
        await message.answer(
            "❌ Неверный тип скидки.\n"
            "Доступные: bonus_days, percent, fixed"
        )
        return

    async with AsyncSessionLocal() as session:
        try:
            promocode = await promocode_service.create_promocode(
                session,
                code=code,
                discount_type=discount_type,
                discount_value=discount_value,
                max_uses=max_uses,
                expires_at=None,
                applicable_plans=None
            )

            type_description = {
                "bonus_days": f"{int(discount_value)} дней бесплатно",
                "percent": f"скидка {int(discount_value)}%",
                "fixed": f"скидка {int(discount_value)}₽"
            }

            max_uses_text = f"{max_uses} использований" if max_uses else "без лимита"

            await message.answer(
                f"✅ <b>Промокод создан!</b>\n\n"
                f"🎟 Код: <code>{code}</code>\n"
                f"🎁 Тип: {type_description[discount_type]}\n"
                f"📊 Лимит: {max_uses_text}\n\n"
                f"Пользователи могут ввести этот код в боте.",
                parse_mode="HTML"
            )

            logger.info(f"Admin {message.from_user.id} created promocode {code}: {discount_type}={discount_value}, max_uses={max_uses}")

        except Exception as e:
            logger.error(f"Failed to create promocode: {e}")
            await message.answer(f"❌ Ошибка при создании промокода: {e}")
