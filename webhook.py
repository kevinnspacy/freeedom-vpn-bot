"""
Webhook сервер для обработки уведомлений от ЮKassa
"""
from fastapi import FastAPI, Request, HTTPException
from loguru import logger

from database.database import AsyncSessionLocal
from services.payment_service import PaymentService
from services.subscription_service import SubscriptionService
from services.user_service import UserService
from config import settings

app = FastAPI(title="Shadowsocks VPN Bot - Webhook Server")

payment_service = PaymentService()
subscription_service = SubscriptionService()


@app.post("/webhook/yukassa")
async def yukassa_webhook(request: Request):
    """Обработка webhook от ЮKassa"""
    try:
        data = await request.json()
        logger.info(f"Received webhook: {data}")

        async with AsyncSessionLocal() as session:
            # Обрабатываем webhook
            success = await payment_service.process_webhook(session, data)

            if not success:
                raise HTTPException(status_code=400, detail="Failed to process webhook")

            # Если платёж успешен, создаём или продлеваем подписку
            if data.get("event") == "payment.succeeded":
                payment_object = data.get("object", {})
                metadata = payment_object.get("metadata", {})

                telegram_id = int(metadata.get("telegram_id"))
                plan_type = metadata.get("plan_type")

                # Проверяем, есть ли активная подписка
                existing_subscription = await subscription_service.get_active_subscription(
                    session, telegram_id
                )

                if existing_subscription:
                    # Продлеваем подписку
                    await subscription_service.extend_subscription(
                        session, existing_subscription, plan_type
                    )
                else:
                    # Создаём новую подписку
                    await subscription_service.create_subscription(
                        session, telegram_id, plan_type
                    )

                # Начисляем реферальный бонус
                amount_value = payment_object.get("amount", {}).get("value")
                if amount_value:
                    await UserService.accrue_referral_bonus(session, telegram_id, float(amount_value))

            await session.commit()

        return {"status": "ok"}

    except Exception as e:
        logger.error(f"Webhook error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health_check():
    """Проверка здоровья сервера"""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
