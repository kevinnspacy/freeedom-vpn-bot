from yookassa import Configuration, Payment as YooPayment
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import Payment, PaymentStatus
from config import settings
from loguru import logger
import uuid


# Настройка ЮKassa
Configuration.account_id = settings.YUKASSA_SHOP_ID
Configuration.secret_key = settings.YUKASSA_SECRET_KEY


class PaymentService:
    """Сервис для работы с платежами через ЮKassa"""

    PLAN_PRICES = {
        "day": settings.PRICE_DAY,
        "week": settings.PRICE_WEEK,
        "month": settings.PRICE_MONTH,
        "year": settings.PRICE_YEAR,
    }

    PLAN_NAMES = {
        "day": "1 день",
        "week": "1 неделя",
        "month": "1 месяц",
        "year": "1 год",
    }

    @classmethod
    def get_price(cls, plan_type: str) -> int:
        """Получить цену для плана"""
        return cls.PLAN_PRICES.get(plan_type, 0)

    @classmethod
    def get_plan_name(cls, plan_type: str) -> str:
        """Получить название плана"""
        return cls.PLAN_NAMES.get(plan_type, plan_type)

    async def create_payment(
        self,
        session: AsyncSession,
        telegram_id: int,
        plan_type: str,
        return_url: str | None = None,
    ) -> Payment:
        """Создать платёж через ЮKassa"""

        amount = self.get_price(plan_type)
        description = f"Подписка Shadowsocks VPN: {self.get_plan_name(plan_type)}"

        # Генерируем уникальный idempotence_key
        idempotence_key = str(uuid.uuid4())

        try:
            # Создаём платёж в ЮKassa
            yukassa_payment = YooPayment.create({
                "amount": {
                    "value": f"{amount}.00",
                    "currency": "RUB"
                },
                "confirmation": {
                    "type": "redirect",
                    "return_url": return_url or "https://t.me/your_bot_username"
                },
                "capture": True,
                "description": description,
                "metadata": {
                    "telegram_id": telegram_id,
                    "plan_type": plan_type,
                }
            }, idempotence_key)

            # Сохраняем платёж в БД
            payment = Payment(
                telegram_id=telegram_id,
                yukassa_payment_id=yukassa_payment.id,
                amount=float(amount),
                currency="RUB",
                plan_type=plan_type,
                status=PaymentStatus.PENDING,
                description=description,
                confirmation_url=yukassa_payment.confirmation.confirmation_url,
            )

            session.add(payment)
            await session.flush()

            logger.info(f"Payment created: {yukassa_payment.id} for user {telegram_id}")
            return payment

        except Exception as e:
            logger.error(f"Failed to create payment: {e}")
            raise

    async def get_payment_by_yukassa_id(
        self, session: AsyncSession, yukassa_payment_id: str
    ) -> Payment | None:
        """Получить платёж по ID ЮKassa"""
        result = await session.execute(
            select(Payment).where(Payment.yukassa_payment_id == yukassa_payment_id)
        )
        return result.scalar_one_or_none()

    async def check_payment_status(
        self, session: AsyncSession, yukassa_payment_id: str
    ) -> str:
        """Проверить статус платежа в ЮKassa"""
        try:
            yukassa_payment = YooPayment.find_one(yukassa_payment_id)
            payment = await self.get_payment_by_yukassa_id(session, yukassa_payment_id)

            if payment and yukassa_payment.status != payment.status:
                # Обновляем статус в БД
                if yukassa_payment.status == "succeeded":
                    payment.status = PaymentStatus.SUCCEEDED
                elif yukassa_payment.status == "canceled":
                    payment.status = PaymentStatus.CANCELLED

                await session.flush()
                logger.info(f"Payment status updated: {yukassa_payment_id} -> {yukassa_payment.status}")

            return yukassa_payment.status

        except Exception as e:
            logger.error(f"Failed to check payment status: {e}")
            return "unknown"

    async def process_webhook(self, session: AsyncSession, webhook_data: dict) -> bool:
        """Обработка webhook от ЮKassa"""
        try:
            payment_object = webhook_data.get("object")
            if not payment_object:
                return False

            yukassa_payment_id = payment_object.get("id")
            status = payment_object.get("status")

            payment = await self.get_payment_by_yukassa_id(session, yukassa_payment_id)
            if not payment:
                logger.warning(f"Payment not found: {yukassa_payment_id}")
                return False

            # Обновляем статус
            if status == "succeeded":
                payment.status = PaymentStatus.SUCCEEDED
            elif status == "canceled":
                payment.status = PaymentStatus.CANCELLED

            await session.flush()
            logger.info(f"Webhook processed: {yukassa_payment_id} -> {status}")
            return True

        except Exception as e:
            logger.error(f"Failed to process webhook: {e}")
            return False
