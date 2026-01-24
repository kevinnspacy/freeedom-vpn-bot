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
                telegram_username = metadata.get("telegram_username")

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
                        session, telegram_id, plan_type,
                        telegram_username=telegram_username
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


# ============== FLUTTER APP API ==============

@app.get("/api/subscription/{telegram_id}")
async def get_subscription_status(telegram_id: int, api_key: str = ""):
    """
    API для Flutter-приложения: получить статус подписки пользователя
    
    Args:
        telegram_id: Telegram ID пользователя
        api_key: API ключ для аутентификации
    
    Returns:
        JSON с информацией о подписке
    """
    from datetime import datetime
    
    # Проверка API ключа
    if not settings.FLUTTER_API_KEY or api_key != settings.FLUTTER_API_KEY:
        raise HTTPException(status_code=403, detail="Invalid or missing API key")
    
    try:
        async with AsyncSessionLocal() as session:
            subscription = await subscription_service.get_active_subscription(
                session, telegram_id
            )
            
            if not subscription:
                return {
                    "active": False,
                    "message": "No active subscription"
                }
            
            # Рассчитываем оставшиеся дни
            now = datetime.utcnow()
            days_left = max(0, (subscription.expires_at - now).days)
            hours_left = max(0, int((subscription.expires_at - now).total_seconds() / 3600))
            
            return {
                "active": True,
                "plan_type": subscription.plan_type,
                "expires_at": subscription.expires_at.isoformat(),
                "days_left": days_left,
                "hours_left": hours_left,
                "subscription_url": subscription.subscription_url,
                "marzban_username": subscription.marzban_username
            }
    
    except Exception as e:
        logger.error(f"Error getting subscription status: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/subscription/by-username/{marzban_username}")
async def get_subscription_by_username(marzban_username: str, api_key: str = ""):
    """
    API для Flutter-приложения: получить статус подписки по marzban username.
    Автоматически определяет подписку из VLESS конфига (FreedomVPN_xxx_yyy).
    
    Args:
        marzban_username: Username из VLESS конфига (напр. FreedomVPN_ivan_abc1)
        api_key: API ключ для аутентификации
    """
    from datetime import datetime
    from sqlalchemy import select
    from database.models import Subscription, SubscriptionStatus
    
    # Проверка API ключа
    if not settings.FLUTTER_API_KEY or api_key != settings.FLUTTER_API_KEY:
        raise HTTPException(status_code=403, detail="Invalid or missing API key")
    
    try:
        async with AsyncSessionLocal() as session:
            # Поиск по marzban_username
            result = await session.execute(
                select(Subscription).where(
                    Subscription.marzban_username == marzban_username,
                    Subscription.status == SubscriptionStatus.ACTIVE
                )
            )
            subscription = result.scalar_one_or_none()
            
            if not subscription:
                return {
                    "active": False,
                    "message": "Subscription not found"
                }
            
            # Рассчитываем оставшиеся дни
            now = datetime.utcnow()
            if subscription.expires_at < now:
                return {
                    "active": False,
                    "message": "Subscription expired"
                }
            
            days_left = max(0, (subscription.expires_at - now).days)
            hours_left = max(0, int((subscription.expires_at - now).total_seconds() / 3600))
            
            return {
                "active": True,
                "plan_type": subscription.plan_type,
                "expires_at": subscription.expires_at.isoformat(),
                "days_left": days_left,
                "hours_left": hours_left,
                "telegram_id": subscription.telegram_id,
                "marzban_username": subscription.marzban_username
            }
    
    except Exception as e:
        logger.error(f"Error getting subscription by username: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/servers")
async def get_servers(api_key: str = ""):
    """
    API для Flutter: получить список доступных серверов
    """
    # Проверка API ключа
    if not settings.FLUTTER_API_KEY or api_key != settings.FLUTTER_API_KEY:
        raise HTTPException(status_code=403, detail="Invalid or missing API key")
    
    try:
        # Возвращаем информацию о сервере из Marzban
        from services.marzban_service import marzban_service
        
        # Получаем информацию о сервере
        server_info = await marzban_service.get_server_info()
        
        return [
            {
                "name": f"🚀 {settings.SERVER_LOCATION}",
                "location": settings.SERVER_LOCATION,
                "protocol": "VLESS + Reality",
                "host": server_info.get("host", "107.189.23.38"),
                "port": server_info.get("port", 443),
                "available": True
            }
        ]
    except Exception as e:
        logger.error(f"Error getting servers: {e}")
        # Fallback - вернуть дефолтный сервер
        return [
            {
                "name": f"🚀 {settings.SERVER_LOCATION}",
                "location": settings.SERVER_LOCATION,
                "protocol": "VLESS + Reality",
                "host": "107.189.23.38",
                "port": 443,
                "available": True
            }
        ]


@app.get("/api/vless/{telegram_id}")
async def get_vless_link(telegram_id: int, api_key: str = ""):
    """
    API для Flutter: получить VLESS ссылку для подключения
    """
    # Проверка API ключа
    if not settings.FLUTTER_API_KEY or api_key != settings.FLUTTER_API_KEY:
        raise HTTPException(status_code=403, detail="Invalid or missing API key")
    
    try:
        async with AsyncSessionLocal() as session:
            subscription = await subscription_service.get_active_subscription(
                session, telegram_id
            )
            
            if not subscription:
                raise HTTPException(status_code=404, detail="No active subscription")
            
            if not subscription.subscription_url:
                raise HTTPException(status_code=404, detail="No VLESS configuration found")
            
            # Получаем ссылки из Marzban
            from services.marzban_service import marzban_service
            
            try:
                links = await marzban_service.get_user_links(subscription.marzban_username)
                vless_links = links.get("links", [])
                
                # Находим первую VLESS ссылку
                vless_link = next(
                    (link for link in vless_links if link.startswith("vless://")),
                    subscription.subscription_url
                )
                
                return {
                    "vless_link": vless_link,
                    "subscription_url": subscription.subscription_url,
                    "all_links": vless_links
                }
            except Exception as e:
                logger.error(f"Error getting VLESS links from Marzban: {e}")
                return {
                    "vless_link": subscription.subscription_url,
                    "subscription_url": subscription.subscription_url,
                    "all_links": []
                }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting VLESS link: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)

