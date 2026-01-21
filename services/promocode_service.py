"""
Сервис для работы с промокодами
"""
from datetime import datetime
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import Promocode, PromocodeUsage
from loguru import logger


class PromocodeService:
    """Сервис промокодов"""

    async def validate_promocode(
        self, session: AsyncSession, code: str, telegram_id: int, plan_type: str
    ) -> dict:
        """Проверить промокод на валидность"""

        # Получаем промокод
        result = await session.execute(
            select(Promocode).where(and_(Promocode.code == code.upper(), Promocode.is_active == True))
        )
        promocode = result.scalar_one_or_none()

        if not promocode:
            return {"valid": False, "error": "Промокод не найден"}

        # Проверяем срок действия
        if promocode.expires_at and promocode.expires_at < datetime.utcnow():
            return {"valid": False, "error": "Промокод истёк"}

        # Проверяем лимит использований
        if promocode.max_uses and promocode.current_uses >= promocode.max_uses:
            return {"valid": False, "error": "Промокод исчерпан"}

        # Проверяем применимость к тарифу
        if promocode.applicable_plans:
            applicable = promocode.applicable_plans.split(",")
            if plan_type not in applicable:
                return {
                    "valid": False,
                    "error": f"Промокод не применим к тарифу '{plan_type}'"
                }

        # Проверяем, использовал ли пользователь этот промокод
        result = await session.execute(
            select(PromocodeUsage).where(
                and_(
                    PromocodeUsage.promocode_id == promocode.id,
                    PromocodeUsage.telegram_id == telegram_id,
                )
            )
        )
        existing_usage = result.scalar_one_or_none()

        if existing_usage:
            return {"valid": False, "error": "Вы уже использовали этот промокод"}

        return {
            "valid": True,
            "promocode": promocode,
            "discount_type": promocode.discount_type,
            "discount_value": promocode.discount_value,
        }

    async def apply_promocode(
        self,
        session: AsyncSession,
        promocode: Promocode,
        telegram_id: int,
        original_amount: float,
        payment_id: int | None = None,
    ) -> dict:
        """Применить промокод и вернуть результат"""

        discount_amount = 0.0
        final_amount = original_amount
        bonus_days = 0

        if promocode.discount_type == "percent":
            # Процентная скидка
            discount_amount = original_amount * (promocode.discount_value / 100.0)
            final_amount = original_amount - discount_amount

        elif promocode.discount_type == "fixed":
            # Фиксированная скидка
            discount_amount = min(promocode.discount_value, original_amount)
            final_amount = original_amount - discount_amount

        elif promocode.discount_type == "bonus_days":
            # Бонусные дни (скидка не применяется к цене)
            bonus_days = int(promocode.discount_value)
            discount_amount = 0.0

        # Записываем использование промокода
        usage = PromocodeUsage(
            promocode_id=promocode.id,
            telegram_id=telegram_id,
            payment_id=payment_id,
            discount_amount=discount_amount,
        )
        session.add(usage)

        # Увеличиваем счетчик использований
        promocode.current_uses += 1

        await session.commit()

        logger.info(
            f"Promocode '{promocode.code}' applied for user {telegram_id}: "
            f"discount={discount_amount}₽, bonus_days={bonus_days}"
        )

        return {
            "original_amount": original_amount,
            "discount_amount": discount_amount,
            "final_amount": final_amount,
            "bonus_days": bonus_days,
            "discount_type": promocode.discount_type,
        }

    async def create_promocode(
        self,
        session: AsyncSession,
        code: str,
        discount_type: str,
        discount_value: float,
        max_uses: int | None = None,
        expires_at: datetime | None = None,
        applicable_plans: str | None = None,
    ) -> Promocode:
        """Создать промокод (для админа)"""

        promocode = Promocode(
            code=code.upper(),
            discount_type=discount_type,
            discount_value=discount_value,
            max_uses=max_uses,
            expires_at=expires_at,
            applicable_plans=applicable_plans,
        )

        session.add(promocode)
        await session.commit()

        logger.info(f"Created promocode '{code}' with {discount_type}={discount_value}")
        return promocode

    async def get_promocode_stats(
        self, session: AsyncSession, code: str
    ) -> dict | None:
        """Получить статистику по промокоду"""

        result = await session.execute(
            select(Promocode).where(Promocode.code == code.upper())
        )
        promocode = result.scalar_one_or_none()

        if not promocode:
            return None

        # Количество использований
        result = await session.execute(
            select(PromocodeUsage).where(PromocodeUsage.promocode_id == promocode.id)
        )
        usages = result.scalars().all()

        total_discount = sum(usage.discount_amount for usage in usages)

        return {
            "code": promocode.code,
            "discount_type": promocode.discount_type,
            "discount_value": promocode.discount_value,
            "current_uses": promocode.current_uses,
            "max_uses": promocode.max_uses,
            "total_discount": total_discount,
            "is_active": promocode.is_active,
            "expires_at": promocode.expires_at,
        }


# Singleton instance
promocode_service = PromocodeService()
