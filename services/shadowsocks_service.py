import secrets
import string
import base64
from loguru import logger
from config import settings
from shadowsocks_api import ss_manager, get_available_port


class ShadowsocksService:
    """Сервис для управления Shadowsocks сервером"""

    def __init__(self):
        self.server_host = settings.SS_SERVER_HOST
        self.method = settings.SS_METHOD

    @staticmethod
    def generate_password(length: int = 16) -> str:
        """Генерация случайного пароля"""
        alphabet = string.ascii_letters + string.digits
        return ''.join(secrets.choice(alphabet) for _ in range(length))

    async def create_user(self, user_port: int, password: str) -> dict:
        """
        Создание пользователя на Shadowsocks сервере через ss-manager
        """
        try:
            # Добавляем порт в ss-manager
            success = await ss_manager.add_port(user_port, password)

            if not success:
                raise Exception(f"Failed to add port {user_port} to ss-manager")

            logger.info(f"Shadowsocks user created: port={user_port}")

            # Возвращаем данные для подключения
            return {
                "port": user_port,
                "password": password,
                "method": self.method,
                "server": self.server_host
            }
        except Exception as e:
            logger.error(f"Failed to create Shadowsocks user: {e}")
            raise

    async def delete_user(self, user_port: int) -> bool:
        """
        Удаление пользователя с Shadowsocks сервера
        """
        try:
            success = await ss_manager.remove_port(user_port)

            if success:
                logger.info(f"Shadowsocks user deleted: port={user_port}")
            else:
                logger.error(f"Failed to delete port {user_port}")

            return success
        except Exception as e:
            logger.error(f"Failed to delete Shadowsocks user: {e}")
            return False

    async def get_available_port(self) -> int:
        """Получить свободный порт"""
        return await get_available_port()

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
