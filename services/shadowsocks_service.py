import secrets
import string
import httpx
from loguru import logger
from config import settings


class ShadowsocksService:
    """Сервис для управления Shadowsocks сервером"""

    def __init__(self):
        self.server_host = settings.SS_SERVER_HOST
        self.server_port = settings.SS_SERVER_PORT
        self.method = settings.SS_METHOD
        self.api_url = settings.SS_API_URL
        self.used_ports = set()

    @staticmethod
    def generate_password(length: int = 16) -> str:
        """Генерация случайного пароля"""
        alphabet = string.ascii_letters + string.digits
        return ''.join(secrets.choice(alphabet) for _ in range(length))

    def generate_port(self, start: int = 10000, end: int = 60000) -> int:
        """Генерация свободного порта"""
        while True:
            port = secrets.randbelow(end - start) + start
            if port not in self.used_ports:
                self.used_ports.add(port)
                return port

    async def create_user(self, user_port: int, password: str) -> dict:
        """
        Создание пользователя на Shadowsocks сервере

        Для Outline VPN (управление через API):
        POST /access-keys
        {
            "method": "chacha20-ietf-poly1305",
            "password": "password",
            "port": 10000
        }
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.api_url}/access-keys",
                    json={
                        "method": self.method,
                        "password": password,
                        "port": user_port,
                    }
                )
                response.raise_for_status()
                logger.info(f"Shadowsocks user created: port={user_port}")
                return response.json()
        except Exception as e:
            logger.error(f"Failed to create Shadowsocks user: {e}")
            raise

    async def delete_user(self, user_port: int) -> bool:
        """
        Удаление пользователя с Shadowsocks сервера

        DELETE /access-keys/{port}
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.delete(
                    f"{self.api_url}/access-keys/{user_port}"
                )
                response.raise_for_status()
                logger.info(f"Shadowsocks user deleted: port={user_port}")
                self.used_ports.discard(user_port)
                return True
        except Exception as e:
            logger.error(f"Failed to delete Shadowsocks user: {e}")
            return False

    def generate_connection_string(self, password: str, port: int) -> str:
        """
        Генерация строки подключения Shadowsocks

        Format: ss://method:password@server:port
        """
        import base64

        user_info = f"{self.method}:{password}"
        encoded = base64.urlsafe_b64encode(user_info.encode()).decode().rstrip('=')

        return f"ss://{encoded}@{self.server_host}:{port}"

    def generate_qr_code_url(self, connection_string: str) -> str:
        """Генерация URL для QR-кода"""
        from urllib.parse import quote
        return f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={quote(connection_string)}"
