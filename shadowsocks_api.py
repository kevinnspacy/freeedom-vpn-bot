"""
Shadowsocks API для управления пользователями
Использует ss-manager для динамического управления портами
"""
import asyncio
import json
import socket
from typing import Dict, Optional
from pathlib import Path
from loguru import logger
from config import settings


class ShadowsocksManager:
    """Менеджер для управления Shadowsocks через ss-manager"""

    def __init__(self, manager_address: str = "127.0.0.1:6001"):
        """
        Args:
            manager_address: Адрес ss-manager в формате "host:port"
        """
        host, port = manager_address.split(":")
        self.manager_host = host
        self.manager_port = int(port)
        self.timeout = 5

    async def send_command(self, command: Dict) -> Optional[Dict]:
        """Отправить команду ss-manager"""
        try:
            # Создаем UDP socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(self.timeout)

            # Отправляем команду
            message = json.dumps(command).encode('utf-8')
            sock.sendto(message, (self.manager_host, self.manager_port))

            # Получаем ответ
            data, _ = sock.recvfrom(4096)
            sock.close()

            response = json.loads(data.decode('utf-8'))
            logger.debug(f"SS-Manager response: {response}")
            return response

        except socket.timeout:
            logger.error("SS-Manager timeout")
            return None
        except Exception as e:
            logger.error(f"SS-Manager error: {e}")
            return None

    async def add_port(self, port: int, password: str) -> bool:
        """Добавить новый порт с паролем"""
        command = {
            "server_port": port,
            "password": password
        }
        response = await self.send_command({"add": command})

        if response and response.get("stat") == "ok":
            logger.info(f"Added port {port} successfully")
            return True

        logger.error(f"Failed to add port {port}: {response}")
        return False

    async def remove_port(self, port: int) -> bool:
        """Удалить порт"""
        command = {"server_port": port}
        response = await self.send_command({"remove": command})

        if response and response.get("stat") == "ok":
            logger.info(f"Removed port {port} successfully")
            return True

        logger.error(f"Failed to remove port {port}: {response}")
        return False

    async def ping(self) -> bool:
        """Проверить доступность ss-manager"""
        response = await self.send_command({"ping": None})
        return response is not None and response.get("stat") == "ok"

    async def list_ports(self) -> Optional[Dict]:
        """Получить список всех портов"""
        response = await self.send_command({"list": None})
        return response if response else None


# Глобальный экземпляр менеджера
ss_manager = ShadowsocksManager()


async def create_user_config(port: int, password: str, method: str = "chacha20-ietf-poly1305") -> Dict:
    """
    Создать конфигурацию для пользователя

    Returns:
        Dict с данными для подключения
    """
    # Добавляем порт в ss-manager
    success = await ss_manager.add_port(port, password)

    if not success:
        raise Exception(f"Failed to add port {port} to ss-manager")

    # Формируем конфигурацию для клиента
    config = {
        "server": settings.SS_SERVER_HOST,
        "server_port": port,
        "password": password,
        "method": method,
        "timeout": 300,
        "fast_open": True,
        "reuse_port": True
    }

    # Формируем ss:// ссылку
    import base64
    auth_string = f"{method}:{password}@{settings.SS_SERVER_HOST}:{port}"
    encoded = base64.urlsafe_b64encode(auth_string.encode()).decode().rstrip('=')
    ss_link = f"ss://{encoded}"

    return {
        "config": config,
        "ss_link": ss_link,
        "qr_data": ss_link
    }


async def delete_user_config(port: int) -> bool:
    """Удалить конфигурацию пользователя"""
    return await ss_manager.remove_port(port)


async def get_available_port() -> int:
    """
    Получить свободный порт для нового пользователя
    Начинаем с 10000 и ищем свободный
    """
    from database.database import AsyncSessionLocal
    from database.models import Subscription
    from sqlalchemy import select

    async with AsyncSessionLocal() as session:
        # Получаем все используемые порты
        result = await session.execute(
            select(Subscription.ss_port)
        )
        used_ports = {row[0] for row in result.fetchall()}

    # Ищем свободный порт в диапазоне 10000-60000
    for port in range(10000, 60000):
        if port not in used_ports:
            return port

    raise Exception("No available ports")


async def init_ss_manager():
    """Инициализация ss-manager"""
    logger.info("Checking ss-manager availability...")

    # Проверяем доступность ss-manager
    retries = 5
    for i in range(retries):
        if await ss_manager.ping():
            logger.info("SS-Manager is ready")
            return True

        logger.warning(f"SS-Manager not ready, retry {i+1}/{retries}")
        await asyncio.sleep(2)

    logger.error("SS-Manager is not available")
    return False
