from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def subscription_plans_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура с планами подписки"""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="1️⃣ День - 100₽", callback_data="buy_day")
    )
    builder.row(
        InlineKeyboardButton(text="7️⃣ Неделя - 500₽", callback_data="buy_week")
    )
    builder.row(
        InlineKeyboardButton(text="🗓 Месяц - 1500₽", callback_data="buy_month")
    )
    builder.row(
        InlineKeyboardButton(text="📅 Год - 15000₽", callback_data="buy_year")
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


def connection_guide_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура с инструкциями"""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="📱 iOS", callback_data="guide_ios"),
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
