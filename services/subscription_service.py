from datetime import datetime, timedelta
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import Subscription, SubscriptionStatus
from services.shadowsocks_service import ShadowsocksService
from loguru import logger


class SubscriptionService:
    """Сервис для работы с подписками"""

    def __init__(self):
        self.ss_service = ShadowsocksService()

    @staticmethod
    def calculate_expiry_date(plan_type: str) -> datetime:
        """Рассчитать дату истечения подписки"""
        now = datetime.utcnow()

        if plan_type == "day":
            return now + timedelta(days=1)
        elif plan_type == "week":
            return now + timedelta(weeks=1)
        elif plan_type == "month":
            return now + timedelta(days=30)
        elif plan_type == "year":
            return now + timedelta(days=365)
        else:
            raise ValueError(f"Unknown plan type: {plan_type}")

    async def create_subscription(
        self,
        session: AsyncSession,
        telegram_id: int,
        plan_type: str,
    ) -> Subscription:
        """Создать новую подписку"""

        # Генерируем учётные данные
        port = self.ss_service.generate_port()
        password = self.ss_service.generate_password()

        # Создаём пользователя на Shadowsocks сервере
        try:
            await self.ss_service.create_user(port, password)
        except Exception as e:
            logger.error(f"Failed to create Shadowsocks user for {telegram_id}: {e}")
            raise

        # Создаём подписку в БД
        subscription = Subscription(
            telegram_id=telegram_id,
            user_id=telegram_id,
            ss_port=port,
            ss_password=password,
            plan_type=plan_type,
            expires_at=self.calculate_expiry_date(plan_type),
            status=SubscriptionStatus.ACTIVE,
        )

        session.add(subscription)
        await session.flush()

        logger.info(f"Subscription created for user {telegram_id}: {plan_type}")
        return subscription

    async def get_active_subscription(
        self, session: AsyncSession, telegram_id: int
    ) -> Subscription | None:
        """Получить активную подписку пользователя"""
        result = await session.execute(
            select(Subscription)
            .where(
                and_(
                    Subscription.telegram_id == telegram_id,
                    Subscription.status == SubscriptionStatus.ACTIVE,
                    Subscription.expires_at > datetime.utcnow()
                )
            )
            .order_by(Subscription.expires_at.desc())
        )
        return result.scalar_one_or_none()

    async def extend_subscription(
        self,
        session: AsyncSession,
        subscription: Subscription,
        plan_type: str,
    ) -> Subscription:
        """Продлить существующую подписку"""

        # Если подписка истекла, обновляем дату начала
        if subscription.expires_at < datetime.utcnow():
            subscription.started_at = datetime.utcnow()
            subscription.expires_at = self.calculate_expiry_date(plan_type)
        else:
            # Иначе добавляем время к текущей дате истечения
            if plan_type == "day":
                subscription.expires_at += timedelta(days=1)
            elif plan_type == "week":
                subscription.expires_at += timedelta(weeks=1)
            elif plan_type == "month":
                subscription.expires_at += timedelta(days=30)
            elif plan_type == "year":
                subscription.expires_at += timedelta(days=365)

        subscription.status = SubscriptionStatus.ACTIVE
        await session.flush()

        logger.info(f"Subscription extended for user {subscription.telegram_id}")
        return subscription

    async def cancel_subscription(
        self, session: AsyncSession, subscription: Subscription
    ) -> bool:
        """Отменить подписку"""

        # Удаляем пользователя с Shadowsocks сервера
        try:
            await self.ss_service.delete_user(subscription.ss_port)
        except Exception as e:
            logger.error(f"Failed to delete Shadowsocks user: {e}")

        # Обновляем статус в БД
        subscription.status = SubscriptionStatus.CANCELLED
        await session.flush()

        logger.info(f"Subscription cancelled for user {subscription.telegram_id}")
        return True

    async def check_expired_subscriptions(self, session: AsyncSession):
        """Проверить и деактивировать истекшие подписки"""
        result = await session.execute(
            select(Subscription).where(
                and_(
                    Subscription.status == SubscriptionStatus.ACTIVE,
                    Subscription.expires_at <= datetime.utcnow()
                )
            )
        )

        expired_subscriptions = result.scalars().all()

        for subscription in expired_subscriptions:
            await self.cancel_subscription(session, subscription)
            logger.info(f"Expired subscription deactivated: user_id={subscription.telegram_id}")
