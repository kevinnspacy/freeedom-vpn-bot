"""
Планировщик задач для автоматической проверки истекших подписок
"""
import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from loguru import logger

from database.database import AsyncSessionLocal
from services.subscription_service import SubscriptionService


async def check_expired_subscriptions_task():
    """Задача для проверки истекших подписок"""
    logger.info("Checking expired subscriptions...")

    subscription_service = SubscriptionService()

    async with AsyncSessionLocal() as session:
        try:
            await subscription_service.check_expired_subscriptions(session)
            await session.commit()
            logger.info("Expired subscriptions check completed")
        except Exception as e:
            logger.error(f"Failed to check expired subscriptions: {e}")
            await session.rollback()


def start_scheduler():
    """Запуск планировщика"""
    scheduler = AsyncIOScheduler()

    # Проверяем истекшие подписки каждый час
    scheduler.add_job(
        check_expired_subscriptions_task,
        'interval',
        hours=1,
        id='check_expired_subscriptions'
    )

    scheduler.start()
    logger.info("Scheduler started")

    return scheduler


if __name__ == "__main__":
    # Тестовый запуск
    async def test():
        await check_expired_subscriptions_task()

    asyncio.run(test())
