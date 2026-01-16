from aiogram import Router, F
from aiogram.types import Message
from sqlalchemy import select, func
from database.database import AsyncSessionLocal
from database.models import User
from services.user_service import UserService

router = Router()

@router.message(F.text == "👥 Реферальная программа")
async def show_referral_stats(message: Message):
    """Показать статистику реферальной программы"""
    user_id = message.from_user.id
    
    async with AsyncSessionLocal() as session:
        user = await UserService.get_user_by_telegram_id(session, user_id)
        if not user:
            return

        # Count referrals
        result = await session.execute(
            select(func.count(User.id)).where(User.referrer_id == user_id)
        )
        referral_count = result.scalar()
        
        bot_username = (await message.bot.get_me()).username
        referral_link = f"https://t.me/{bot_username}?start={user_id}"
        
        text = f"""
👥 **Реферальная программа**

Приглашайте друзей и получайте **15%** от суммы их пополнений на свой баланс!

🔗 **Ваша ссылка для приглашения:**
`{referral_link}`
(нажмите чтобы скопировать)

📊 **Статистика:**
👤 Приглашено людей: **{referral_count}**
💰 Ваш баланс: **{user.balance:.2f}₽**

💡 Баланс можно использовать для оплаты подписки.
"""
        await message.answer(text)
