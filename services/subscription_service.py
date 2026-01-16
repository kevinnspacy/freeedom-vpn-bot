from datetime import datetime, timedelta
import random
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import Subscription, SubscriptionStatus
from services.marzban_service import marzban_service
from loguru import logger


class SubscriptionService:
    """Сервис для работы с подписками (VLESS + Reality через Marzban)"""

    @staticmethod
    def calculate_expiry_date(plan_type: str) -> datetime:
        """Рассчитать дату истечения подписки"""
        now = datetime.utcnow()

        if plan_type == "trial":
            return now + timedelta(hours=24)
        elif plan_type == "day":
            return now + timedelta(days=1)
        elif plan_type == "week":
            return now + timedelta(weeks=1)
        elif plan_type == "month":
            return now + timedelta(days=30)
        elif plan_type == "3month":
            return now + timedelta(days=90)
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
        """Создать новую подписку через Marzban (VLESS + Reality)"""

        # Создаём пользователя в Marzban
        try:
            marzban_user = await marzban_service.create_user(
                telegram_id=telegram_id,
                plan_type=plan_type
            )
            marzban_username = marzban_user.get("username")
            subscription_url = marzban_user.get("subscription_url", "")

            logger.info(f"Marzban user created: {marzban_username} for telegram_id={telegram_id}")

        except Exception as e:
            logger.error(f"Failed to create Marzban user for {telegram_id}: {e}")
            raise

        # Создаём подписку в БД
        subscription = Subscription(
            telegram_id=telegram_id,
            user_id=telegram_id,
            marzban_username=marzban_username,
            subscription_url=subscription_url,
            plan_type=plan_type,
            expires_at=self.calculate_expiry_date(plan_type),
            status=SubscriptionStatus.ACTIVE,
            # Заглушки для старых полей Shadowsocks (так как в БД они NOT NULL)
            ss_port=random.randint(100000, 999999), # Фейковый порт, чтобы был уникальным
            ss_password="vless-migrated",
            ss_method="vless",
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

    async def has_used_trial(
        self, session: AsyncSession, telegram_id: int
    ) -> bool:
        """Проверить, использовал ли пользователь тестовый период"""
        result = await session.execute(
            select(Subscription)
            .where(
                and_(
                    Subscription.telegram_id == telegram_id,
                    Subscription.plan_type == "trial"
                )
            )
        )
        return result.scalar_one_or_none() is not None

    async def extend_subscription(
        self,
        session: AsyncSession,
        subscription: Subscription,
        plan_type: str,
    ) -> Subscription:
        """Продлить существующую подписку"""

        # Продлеваем в Marzban
        if subscription.marzban_username:
            try:
                await marzban_service.extend_user(subscription.marzban_username, plan_type)
            except Exception as e:
                logger.error(f"Failed to extend Marzban user: {e}")
                raise

        # Обновляем дату в БД
        if subscription.expires_at < datetime.utcnow():
            subscription.started_at = datetime.utcnow()
            subscription.expires_at = self.calculate_expiry_date(plan_type)
        else:
            # Добавляем время к текущей дате истечения
            if plan_type == "trial":
                subscription.expires_at += timedelta(hours=24)
            elif plan_type == "day":
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

        # Удаляем пользователя из Marzban
        if subscription.marzban_username:
            try:
                await marzban_service.delete_user(subscription.marzban_username)
            except Exception as e:
                logger.error(f"Failed to delete Marzban user: {e}")

        # Обновляем статус в БД
        subscription.status = SubscriptionStatus.CANCELLED
        await session.flush()

        logger.info(f"Subscription cancelled for user {subscription.telegram_id}")
        return True

    async def get_connection_info(self, subscription: Subscription) -> dict:
        """Получить информацию для подключения"""
        if not subscription.marzban_username:
            return {"error": "No Marzban username found"}

        try:
            user_links = await marzban_service.get_user_links(subscription.marzban_username)
            return {
                "subscription_url": user_links.get("subscription_url", ""),
                "links": user_links.get("links", []),
                "expires_at": subscription.expires_at,
                "status": subscription.status
            }
        except Exception as e:
            logger.error(f"Failed to get connection info: {e}")
            return {"error": str(e)}

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
