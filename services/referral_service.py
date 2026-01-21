"""
Сервис для работы с реферальной системой
"""
import random
import string
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import User, ReferralTransaction, Payment, PaymentStatus
from loguru import logger


class ReferralService:
    """Сервис реферальной системы"""

    REFERRAL_PERCENTAGE = 30.0  # 30% от платежа рефералу

    @staticmethod
    def generate_referral_code(telegram_id: int) -> str:
        """Генерировать уникальный реферальный код"""
        # Формат: ref_[6 случайных символов]_[последние 4 цифры telegram_id]
        random_part = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
        id_part = str(telegram_id)[-4:]
        return f"ref_{random_part}_{id_part}"

    async def create_or_get_referral_code(
        self, session: AsyncSession, telegram_id: int
    ) -> str:
        """Создать или получить реферальный код пользователя"""
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            return ""

        if user.referral_code:
            return user.referral_code

        # Генерируем новый код
        referral_code = self.generate_referral_code(telegram_id)

        # Проверяем уникальность
        while True:
            result = await session.execute(
                select(User).where(User.referral_code == referral_code)
            )
            existing = result.scalar_one_or_none()

            if not existing:
                break

            # Генерируем новый код если такой уже есть
            referral_code = self.generate_referral_code(telegram_id)

        # Сохраняем код
        user.referral_code = referral_code
        await session.commit()

        logger.info(f"Created referral code '{referral_code}' for user {telegram_id}")
        return referral_code

    async def get_user_by_referral_code(
        self, session: AsyncSession, referral_code: str
    ) -> User | None:
        """Получить пользователя по реферальному коду"""
        result = await session.execute(
            select(User).where(User.referral_code == referral_code)
        )
        return result.scalar_one_or_none()

    async def set_referrer(
        self, session: AsyncSession, telegram_id: int, referrer_id: int
    ) -> bool:
        """Установить реферера для пользователя"""
        # Проверяем что пользователь не пытается указать себя
        if telegram_id == referrer_id:
            return False

        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()

        if not user or user.referrer_id:
            # Пользователь не найден или реферер уже установлен
            return False

        user.referrer_id = referrer_id
        await session.commit()

        logger.info(f"Set referrer {referrer_id} for user {telegram_id}")
        return True

    async def process_referral_payment(
        self,
        session: AsyncSession,
        payment_id: int,
        telegram_id: int,
        amount: float,
    ) -> float:
        """Обработать реферальный платеж и начислить бонус рефереру"""

        # Получаем пользователя
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()

        if not user or not user.referrer_id:
            return 0.0

        # Рассчитываем бонус
        bonus_amount = amount * (self.REFERRAL_PERCENTAGE / 100.0)

        # Получаем реферера
        result = await session.execute(
            select(User).where(User.telegram_id == user.referrer_id)
        )
        referrer = result.scalar_one_or_none()

        if not referrer:
            logger.warning(f"Referrer {user.referrer_id} not found for user {telegram_id}")
            return 0.0

        # Начисляем бонус рефереру
        referrer.balance += bonus_amount
        referrer.total_earned += bonus_amount
        referrer.total_referrals = (
            await session.execute(
                select(func.count(User.id)).where(User.referrer_id == user.referrer_id)
            )
        ).scalar() or 0

        # Создаем запись транзакции
        transaction = ReferralTransaction(
            referrer_telegram_id=user.referrer_id,
            referred_telegram_id=telegram_id,
            payment_id=payment_id,
            amount=bonus_amount,
            percentage=self.REFERRAL_PERCENTAGE,
        )
        session.add(transaction)

        await session.commit()

        logger.info(
            f"Referral bonus {bonus_amount}₽ ({self.REFERRAL_PERCENTAGE}%) "
            f"credited to {user.referrer_id} from payment {payment_id}"
        )

        return bonus_amount

    async def get_referral_stats(
        self, session: AsyncSession, telegram_id: int
    ) -> dict:
        """Получить статистику рефералов"""

        # Количество рефералов
        referrals_count = (
            await session.execute(
                select(func.count(User.id)).where(User.referrer_id == telegram_id)
            )
        ).scalar() or 0

        # Общий заработок
        total_earned = (
            await session.execute(
                select(func.sum(ReferralTransaction.amount)).where(
                    ReferralTransaction.referrer_telegram_id == telegram_id
                )
            )
        ).scalar() or 0.0

        # Последние 5 рефералов
        result = await session.execute(
            select(User)
            .where(User.referrer_id == telegram_id)
            .order_by(User.created_at.desc())
            .limit(5)
        )
        recent_referrals = result.scalars().all()

        return {
            "referrals_count": referrals_count,
            "total_earned": total_earned,
            "recent_referrals": recent_referrals,
        }


# Singleton instance
referral_service = ReferralService()
