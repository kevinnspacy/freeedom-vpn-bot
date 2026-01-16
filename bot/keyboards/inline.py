from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from config import settings


def subscription_plans_keyboard(show_trial: bool = True) -> InlineKeyboardMarkup:
    """Клавиатура с планами подписки"""
    builder = InlineKeyboardBuilder()

    # Тестовый период (только для новых пользователей)
    if show_trial:
        builder.row(
            InlineKeyboardButton(text="🎁 Попробовать БЕСПЛАТНО (24 часа)", callback_data="buy_trial")
        )

    builder.row(
        InlineKeyboardButton(text=f"1️⃣ День - {settings.PRICE_DAY}₽", callback_data="buy_day")
    )
    builder.row(
        InlineKeyboardButton(text=f"7️⃣ Неделя - {settings.PRICE_WEEK}₽", callback_data="buy_week")
    )
    builder.row(
        InlineKeyboardButton(text=f"🗓 Месяц - {settings.PRICE_MONTH}₽", callback_data="buy_month")
    )
    builder.row(
        InlineKeyboardButton(text=f"📆 3 месяца - {settings.PRICE_3MONTH}₽", callback_data="buy_3month")
    )
    builder.row(
        InlineKeyboardButton(text=f"📅 Год - {settings.PRICE_YEAR}₽", callback_data="buy_year")
    )
    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_menu")
    )

    return builder.as_markup()


def payment_keyboard(payment_url: str) -> InlineKeyboardMarkup:
    """Клавиатура для оплаты"""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="💳 Оплатить", url=payment_url)
    )
    builder.row(
        InlineKeyboardButton(text="✅ Проверить оплату", callback_data="check_payment")
    )
    builder.row(
        InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_payment")
    )

    return builder.as_markup()


def payment_method_keyboard(plan_type: str, price: int, balance: float) -> InlineKeyboardMarkup:
    """Клавиатура выбора метода оплаты"""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text=f"💰 С баланса ({price}₽)", callback_data=f"pay_balance_{plan_type}")
    )
    builder.row(
        InlineKeyboardButton(text="💳 Картой / SberPay", callback_data=f"pay_card_{plan_type}")
    )
    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_menu")
    )

    return builder.as_markup()


def connection_guide_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура с инструкциями"""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="📱 iPhone / iPad", callback_data="guide_ios"),
        InlineKeyboardButton(text="🤖 Android", callback_data="guide_android")
    )
    builder.row(
        InlineKeyboardButton(text="💻 Windows", callback_data="guide_windows"),
        InlineKeyboardButton(text="🍎 macOS", callback_data="guide_macos")
    )
    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_menu")
    )

    return builder.as_markup()


def admin_panel_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура админ-панели"""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="👥 Пользователи", callback_data="admin_users")
    )
    builder.row(
        InlineKeyboardButton(text="💰 Платежи", callback_data="admin_payments")
    )
    builder.row(
        InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")
    )
    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_menu")
    )

    return builder.as_markup()
