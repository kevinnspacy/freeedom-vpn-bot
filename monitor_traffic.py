#!/usr/bin/env python3
"""
Скрипт мониторинга трафика VPS сервера
Отправляет уведомление админу при достижении 50% лимита (500 GB из 1 TB)
"""
import asyncio
import sys
from pathlib import Path

# Добавляем путь к проекту
sys.path.append(str(Path(__file__).parent))

from aiogram import Bot
from config import settings
from loguru import logger
import json
import subprocess

# Лимит трафика в GB
TRAFFIC_LIMIT_GB = 1000  # 1 TB
WARNING_THRESHOLD = 0.5  # 50%
WARNING_THRESHOLD_GB = TRAFFIC_LIMIT_GB * WARNING_THRESHOLD

# Файл для хранения состояния уведомлений
STATE_FILE = "/var/lib/freedomvpn/traffic_alert_state.json"


def get_network_traffic() -> dict:
    """
    Получить статистику сетевого трафика за текущий месяц
    Использует /proc/net/dev для подсчета трафика
    """
    try:
        # Читаем статистику из /proc/net/dev
        with open('/proc/net/dev', 'r') as f:
            lines = f.readlines()

        total_rx_bytes = 0
        total_tx_bytes = 0

        # Пропускаем первые 2 строки (заголовки)
        for line in lines[2:]:
            parts = line.split()
            interface = parts[0].rstrip(':')

            # Игнорируем loopback интерфейс
            if interface == 'lo':
                continue

            rx_bytes = int(parts[1])  # Received bytes
            tx_bytes = int(parts[9])  # Transmitted bytes

            total_rx_bytes += rx_bytes
            total_tx_bytes += tx_bytes

        # Конвертируем в GB
        total_rx_gb = total_rx_bytes / (1024 ** 3)
        total_tx_gb = total_tx_bytes / (1024 ** 3)
        total_gb = total_rx_gb + total_tx_gb

        return {
            "rx_gb": round(total_rx_gb, 2),
            "tx_gb": round(total_tx_gb, 2),
            "total_gb": round(total_gb, 2)
        }
    except Exception as e:
        logger.error(f"Failed to get network traffic: {e}")
        return {"rx_gb": 0, "tx_gb": 0, "total_gb": 0}


def get_vnstat_traffic() -> dict:
    """
    Получить статистику трафика через vnstat (если установлен)
    Более точный метод, который отслеживает только месячный трафик
    """
    try:
        # Проверяем, установлен ли vnstat
        result = subprocess.run(['vnstat', '--json', 'm'],
                              capture_output=True,
                              text=True,
                              timeout=10)

        if result.returncode == 0:
            data = json.loads(result.stdout)

            # Получаем данные за текущий месяц
            if (data.get('interfaces') and
                len(data['interfaces']) > 0 and
                data['interfaces'][0].get('traffic', {}).get('month') and
                len(data['interfaces'][0]['traffic']['month']) > 0):

                current_month = data['interfaces'][0]['traffic']['month'][0]

                rx_bytes = current_month['rx']
                tx_bytes = current_month['tx']

                rx_gb = rx_bytes / (1024 ** 3)
                tx_gb = tx_bytes / (1024 ** 3)
                total_gb = rx_gb + tx_gb

                return {
                    "rx_gb": round(rx_gb, 2),
                    "tx_gb": round(tx_gb, 2),
                    "total_gb": round(total_gb, 2),
                    "method": "vnstat"
                }
            else:
                logger.warning("vnstat has no data yet, using /proc/net/dev")
    except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError, KeyError, IndexError) as e:
        logger.warning(f"vnstat not available, using /proc/net/dev: {e}")

    # Fallback на /proc/net/dev
    traffic = get_network_traffic()
    traffic['method'] = 'proc'
    return traffic


def load_alert_state() -> dict:
    """Загрузить состояние уведомлений"""
    try:
        with open(STATE_FILE, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {
            "50_percent_sent": False,
            "75_percent_sent": False,
            "90_percent_sent": False
        }


def save_alert_state(state: dict):
    """Сохранить состояние уведомлений"""
    Path(STATE_FILE).parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f)


async def send_admin_notification(message: str):
    """Отправить уведомление всем админам"""
    bot = Bot(token=settings.BOT_TOKEN)

    try:
        for admin_id in settings.admin_ids_list:
            await bot.send_message(
                chat_id=admin_id,
                text=message,
                parse_mode="HTML"
            )
            logger.info(f"Sent traffic alert to admin {admin_id}")
    except Exception as e:
        logger.error(f"Failed to send admin notification: {e}")
    finally:
        await bot.session.close()


async def check_traffic():
    """Проверить использование трафика и отправить уведомление при необходимости"""
    traffic = get_vnstat_traffic()
    total_gb = traffic['total_gb']
    rx_gb = traffic['rx_gb']
    tx_gb = traffic['tx_gb']
    method = traffic.get('method', 'unknown')

    logger.info(f"Traffic check: {total_gb} GB used (RX: {rx_gb} GB, TX: {tx_gb} GB, method: {method})")

    # Загружаем состояние уведомлений
    state = load_alert_state()

    # Рассчитываем процент использования
    usage_percent = (total_gb / TRAFFIC_LIMIT_GB) * 100

    # Проверяем пороги и отправляем уведомления
    notification_sent = False

    if usage_percent >= 90 and not state.get("90_percent_sent"):
        message = f"""
🚨 <b>КРИТИЧЕСКОЕ ПРЕДУПРЕЖДЕНИЕ: Трафик почти исчерпан!</b>

📊 Использовано: <b>{total_gb} GB</b> из {TRAFFIC_LIMIT_GB} GB ({usage_percent:.1f}%)
📥 Получено: {rx_gb} GB
📤 Отправлено: {tx_gb} GB

⚠️ Осталось всего <b>{TRAFFIC_LIMIT_GB - total_gb:.2f} GB</b>!

Рекомендуется срочно принять меры для снижения трафика.
"""
        await send_admin_notification(message)
        state["90_percent_sent"] = True
        notification_sent = True

    elif usage_percent >= 75 and not state.get("75_percent_sent"):
        message = f"""
⚠️ <b>ПРЕДУПРЕЖДЕНИЕ: Высокое использование трафика!</b>

📊 Использовано: <b>{total_gb} GB</b> из {TRAFFIC_LIMIT_GB} GB ({usage_percent:.1f}%)
📥 Получено: {rx_gb} GB
📤 Отправлено: {tx_gb} GB

Осталось: <b>{TRAFFIC_LIMIT_GB - total_gb:.2f} GB</b>

Рекомендуется мониторить трафик более внимательно.
"""
        await send_admin_notification(message)
        state["75_percent_sent"] = True
        notification_sent = True

    elif usage_percent >= 50 and not state.get("50_percent_sent"):
        message = f"""
📊 <b>Уведомление: Половина трафика использована</b>

📊 Использовано: <b>{total_gb} GB</b> из {TRAFFIC_LIMIT_GB} GB ({usage_percent:.1f}%)
📥 Получено: {rx_gb} GB
📤 Отправлено: {tx_gb} GB

Осталось: <b>{TRAFFIC_LIMIT_GB - total_gb:.2f} GB</b>

Трафик в пределах нормы, но следите за расходом.
"""
        await send_admin_notification(message)
        state["50_percent_sent"] = True
        notification_sent = True

    if notification_sent:
        save_alert_state(state)
        logger.info(f"Alert sent and state saved: {state}")


async def main():
    """Главная функция"""
    logger.info("Starting traffic monitoring check...")
    await check_traffic()
    logger.info("Traffic monitoring check completed")


if __name__ == "__main__":
    asyncio.run(main())
