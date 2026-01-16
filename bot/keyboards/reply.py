from aiogram.types import ReplyKeyboardMarkup, KeyboardButton


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    """Главное меню"""
    keyboard = [
        [KeyboardButton(text="💰 Купить подписку")],
        [KeyboardButton(text="📊 Мой статус"), KeyboardButton(text="👥 Реферальная программа")],
        [KeyboardButton(text="📱 Инструкция подключения"), KeyboardButton(text="❓ Помощь")],
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


def admin_menu_keyboard() -> ReplyKeyboardMarkup:
    """Меню администратора"""
    keyboard = [
        [KeyboardButton(text="💰 Купить подписку")],
        [KeyboardButton(text="📊 Мой статус"), KeyboardButton(text="❓ Помощь")],
        [KeyboardButton(text="📱 Инструкция подключения")],
        [KeyboardButton(text="👨‍💼 Админ-панель")],
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
