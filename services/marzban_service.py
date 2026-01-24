"""
Сервис для работы с Marzban API
Управление пользователями VLESS + Reality
"""
import httpx
import secrets
import string
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from loguru import logger
from config import settings


class MarzbanService:
    """Сервис для работы с Marzban API"""

    def __init__(self):
        self.base_url = settings.MARZBAN_API_URL
        self.username = settings.MARZBAN_USERNAME
        self.password = settings.MARZBAN_PASSWORD
        self._token: Optional[str] = None
        self._token_expires: Optional[datetime] = None

    async def _get_token(self) -> str:
        """Получить или обновить токен авторизации"""
        # Если токен действителен, возвращаем его
        if self._token and self._token_expires and datetime.now() < self._token_expires:
            return self._token

        # Получаем новый токен
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.base_url}/api/admin/token",
                data={
                    "username": self.username,
                    "password": self.password
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            response.raise_for_status()
            data = response.json()

            self._token = data["access_token"]
            # Токен действителен 24 часа, обновляем за час до истечения
            self._token_expires = datetime.now() + timedelta(hours=23)

            logger.info("Marzban token refreshed")
            return self._token

    async def _request(
        self,
        method: str,
        endpoint: str,
        json_data: Optional[Dict] = None,
        params: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Выполнить запрос к Marzban API"""
        token = await self._get_token()

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.request(
                method,
                f"{self.base_url}{endpoint}",
                json=json_data,
                params=params,
                headers={"Authorization": f"Bearer {token}"}
            )
            response.raise_for_status()
            return response.json() if response.text else {}

    @staticmethod
    def generate_username(telegram_id: int, telegram_username: Optional[str] = None) -> str:
        """
        Генерация информативного username для Marzban.
        Формат: user_{telegram_id}_{telegram_username}
        Пример: user_123456789_durov
        """
        if telegram_username:
            import re
            # Очищаем username от спецсимволов, оставляем только буквы, цифры и underscore
            clean_username = re.sub(r'[^a-zA-Z0-9_]', '', telegram_username)
            return f"user_{telegram_id}_{clean_username}"
        else:
            return f"user_{telegram_id}"

    def _generate_note(self, plan_type: str, first_name: str, expire_timestamp: int) -> str:
        """Генерация note для отображения в VPN-клиенте (как у Sparta VPN)"""
        expire_date = datetime.fromtimestamp(expire_timestamp)
        days_left = max(1, (expire_date - datetime.now()).days)

        # Эмодзи в зависимости от типа подписки
        plan_emoji = "🎁" if plan_type == "trial" else "💎"

        # Ограничиваем имя до 12 символов
        name = (first_name or "User")[:12]

        return f"FreedomVPN {days_left}д {plan_emoji} {name}\n✅ До {expire_date.strftime('%d.%m.%Y')}\n🤖 t.me/freeddomm_bot"

    def calculate_expire_timestamp(self, plan_type: str) -> int:
        """Рассчитать timestamp истечения подписки"""
        now = datetime.now()

        if plan_type == "trial":
            expire = now + timedelta(hours=72)
        elif plan_type == "day":
            expire = now + timedelta(days=1)
        elif plan_type == "week":
            expire = now + timedelta(weeks=1)
        elif plan_type == "month":
            expire = now + timedelta(days=30)
        elif plan_type == "3month":
            expire = now + timedelta(days=90)
        elif plan_type == "year":
            expire = now + timedelta(days=365)
        else:
            raise ValueError(f"Unknown plan type: {plan_type}")

        return int(expire.timestamp())

    async def create_user(
        self,
        telegram_id: int,
        plan_type: str,
        first_name: str = "User",
        telegram_username: Optional[str] = None,
        data_limit_gb: int = 0  # 0 = безлимит
    ) -> Dict[str, Any]:
        """
        Создать пользователя в Marzban

        Returns:
            Dict с данными пользователя включая subscription_url
        """
        username = self.generate_username(telegram_id, telegram_username)
        expire_timestamp = self.calculate_expire_timestamp(plan_type)

        # Генерируем note для отображения в VPN-клиенте
        note = self._generate_note(plan_type, first_name, expire_timestamp)

        user_data = {
            "username": username,
            "proxies": {
                "vless": {
                    "flow": "xtls-rprx-vision"
                }
            },
            "inbounds": {
                "vless": ["VLESS TCP REALITY"]
            },
            "expire": expire_timestamp,
            "data_limit": data_limit_gb * 1024 * 1024 * 1024 if data_limit_gb > 0 else 0,
            "data_limit_reset_strategy": "no_reset",
            "status": "active",
            "note": note
        }

        try:
            result = await self._request("POST", "/api/user", json_data=user_data)
            logger.info(f"Marzban user created: {username} for telegram_id={telegram_id}")
            return result
        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to create Marzban user: {e.response.text}")
            raise

    async def get_all_users(self) -> List[Dict[str, Any]]:
        """Получить всех пользователей"""
        try:
            # Endpoint /api/users returns list of users
            # Need to handle pagination if Marzban uses it. 
            # Marzban API /api/users returns {users: [...], total: ...}
            response = await self._request("GET", "/api/users")
            return response.get("users", [])
        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to get all users: {e}")
            return []

    async def get_user(self, username: str) -> Optional[Dict[str, Any]]:
        """Получить данные пользователя"""
        try:
            return await self._request("GET", f"/api/user/{username}")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise

    async def delete_user(self, username: str) -> bool:
        """Удалить пользователя"""
        try:
            await self._request("DELETE", f"/api/user/{username}")
            logger.info(f"Marzban user deleted: {username}")
            return True
        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to delete Marzban user {username}: {e.response.text}")
            return False

    async def extend_user(self, username: str, plan_type: str, first_name: str = "User") -> Dict[str, Any]:
        """Продлить подписку пользователя"""
        # Получаем текущие данные пользователя
        user = await self.get_user(username)
        if not user:
            raise ValueError(f"User {username} not found")

        # Рассчитываем новую дату истечения
        current_expire = user.get("expire", 0)
        now_timestamp = int(datetime.now().timestamp())

        # Если подписка еще активна, добавляем время к текущей дате
        # Если истекла, начинаем с текущего момента
        base_timestamp = max(current_expire, now_timestamp)

        if plan_type == "trial":
            new_expire = base_timestamp + (24 * 3600)
        elif plan_type == "day":
            new_expire = base_timestamp + (24 * 3600)
        elif plan_type == "week":
            new_expire = base_timestamp + (7 * 24 * 3600)
        elif plan_type == "month":
            new_expire = base_timestamp + (30 * 24 * 3600)
        elif plan_type == "3month":
            new_expire = base_timestamp + (90 * 24 * 3600)
        elif plan_type == "year":
            new_expire = base_timestamp + (365 * 24 * 3600)
        else:
            raise ValueError(f"Unknown plan type: {plan_type}")

        # Генерируем обновлённый note для отображения в VPN-клиенте
        note = self._generate_note(plan_type, first_name, new_expire)

        # Обновляем пользователя
        update_data = {
            "expire": new_expire,
            "status": "active",
            "note": note
        }

        result = await self._request("PUT", f"/api/user/{username}", json_data=update_data)
        logger.info(f"Marzban user extended: {username}")
        return result

    async def get_subscription_url(self, username: str) -> str:
        """Получить URL подписки для пользователя"""
        user = await self.get_user(username)
        if not user:
            raise ValueError(f"User {username} not found")

        subscription_url = user.get("subscription_url", "")
        return subscription_url

    async def get_user_links(self, username: str) -> Dict[str, Any]:
        """Получить все ссылки для подключения"""
        user = await self.get_user(username)
        if not user:
            raise ValueError(f"User {username} not found")

        return {
            "subscription_url": user.get("subscription_url", ""),
            "links": user.get("links", []),
            "expire": user.get("expire"),
            "status": user.get("status"),
            "used_traffic": user.get("used_traffic", 0),
            "data_limit": user.get("data_limit", 0)
        }

    def generate_qr_code_url(self, data: str) -> str:
        """Генерация URL для QR-кода"""
        from urllib.parse import quote
        return f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={quote(data)}"


# Глобальный экземпляр сервиса
marzban_service = MarzbanService()
