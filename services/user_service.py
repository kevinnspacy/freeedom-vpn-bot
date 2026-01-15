from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import User
from loguru import logger


class UserService:
    """Сервис для работы с пользователями"""

    @staticmethod
    async def get_or_create_user(
        session: AsyncSession,
        telegram_id: int,
        username: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
    ) -> User:
        """Получить или создать пользователя"""
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            user = User(
                telegram_id=telegram_id,
                username=username,
                first_name=first_name,
                last_name=last_name,
            )
            session.add(user)
            await session.flush()
            logger.info(f"New user created: {telegram_id} (@{username})")
        else:
            # Обновляем данные пользователя
            user.username = username
            user.first_name = first_name
            user.last_name = last_name

        return user

    @staticmethod
    async def get_user_by_telegram_id(
        session: AsyncSession, telegram_id: int
    ) -> User | None:
        """Получить пользователя по telegram_id"""
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def is_admin(session: AsyncSession, telegram_id: int) -> bool:
        """Проверить, является ли пользователь администратором"""
        user = await UserService.get_user_by_telegram_id(session, telegram_id)
        return user.is_admin if user else False
