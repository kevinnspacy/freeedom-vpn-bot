# Пошаговое руководство по развёртыванию на VPS

## Шаг 1: Выбор и настройка VPS

### Рекомендуемые характеристики:
- **CPU**: 2+ ядра
- **RAM**: 2+ GB
- **Диск**: 20+ GB SSD
- **ОС**: Ubuntu 22.04 LTS
- **Локация**: страна без цензуры (Нидерланды, Германия, США)

### Рекомендуемые провайдеры:
- DigitalOcean (от $12/месяц)
- Vultr (от $6/месяц)
- Hetzner (от €4.5/месяц)
- Linode (от $12/месяц)

## Шаг 2: Первоначальная настройка сервера

### Подключение по SSH

```bash
ssh root@your_server_ip
```

### Обновление системы

```bash
apt update && apt upgrade -y
```

### Установка необходимых пакетов

```bash
apt install -y python3.11 python3.11-venv python3-pip postgresql postgresql-contrib nginx git curl
```

### Настройка firewall

```bash
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw allow 8388/tcp  # Shadowsocks порт
ufw enable
```

## Шаг 3: Настройка PostgreSQL

```bash
# Переключение на пользователя postgres
sudo -u postgres psql

# Создание базы данных и пользователя
CREATE DATABASE shadowsocks_db;
CREATE USER shadowsocks_user WITH PASSWORD 'your_very_secure_password_here';
ALTER ROLE shadowsocks_user SET client_encoding TO 'utf8';
ALTER ROLE shadowsocks_user SET default_transaction_isolation TO 'read committed';
ALTER ROLE shadowsocks_user SET timezone TO 'UTC';
GRANT ALL PRIVILEGES ON DATABASE shadowsocks_db TO shadowsocks_user;

# Для PostgreSQL 15+ нужно дополнительно выдать права на схему
\c shadowsocks_db
GRANT ALL ON SCHEMA public TO shadowsocks_user;

\q
```

### Настройка удалённого доступа (опционально)

```bash
# Редактирование конфига PostgreSQL
nano /etc/postgresql/14/main/postgresql.conf
# Раскомментируйте и измените:
# listen_addresses = 'localhost'

# Редактирование pg_hba.conf
nano /etc/postgresql/14/main/pg_hba.conf
# Добавьте:
# local   all             all                                     peer
# host    all             all             127.0.0.1/32            md5

# Перезапуск PostgreSQL
systemctl restart postgresql
```

## Шаг 4: Установка и настройка Shadowsocks (Outline VPN)

### Вариант 1: Через Docker (рекомендуется)

```bash
# Установка Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Установка Outline Server
sudo bash -c "$(wget -qO- https://raw.githubusercontent.com/Jigsaw-Code/outline-server/master/src/server_manager/install_scripts/install_server.sh)"
```

После установки вы получите:
- Management API URL
- Management API Certificate

Сохраните эти данные для настройки бота.

### Вариант 2: Ручная установка Shadowsocks-rust

```bash
# Скачивание последней версии
wget https://github.com/shadowsocks/shadowsocks-rust/releases/download/v1.18.2/shadowsocks-v1.18.2.x86_64-unknown-linux-gnu.tar.xz

# Распаковка
tar xf shadowsocks-v1.18.2.x86_64-unknown-linux-gnu.tar.xz
sudo mv ssserver /usr/local/bin/
sudo chmod +x /usr/local/bin/ssserver

# Создание конфига
sudo mkdir -p /etc/shadowsocks
sudo nano /etc/shadowsocks/config.json
```

Пример конфига `/etc/shadowsocks/config.json`:

```json
{
    "server": "0.0.0.0",
    "server_port": 8388,
    "password": "your_default_password",
    "method": "chacha20-ietf-poly1305",
    "mode": "tcp_and_udp",
    "fast_open": true
}
```

Создание systemd службы:

```bash
sudo nano /etc/systemd/system/shadowsocks.service
```

```ini
[Unit]
Description=Shadowsocks Server
After=network.target

[Service]
Type=simple
ExecStart=/usr/local/bin/ssserver -c /etc/shadowsocks/config.json
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable shadowsocks
sudo systemctl start shadowsocks
sudo systemctl status shadowsocks
```

## Шаг 5: Клонирование и настройка бота

```bash
# Создание директории
cd /opt
git clone <your-repository-url> shadowsocks-bot
cd shadowsocks-bot

# Или если нет git репозитория, загрузите файлы через scp
# scp -r ./shadowsocks-proxy-bot root@your_server_ip:/opt/shadowsocks-bot

# Создание виртуального окружения
python3.11 -m venv venv
source venv/bin/activate

# Установка зависимостей
pip install --upgrade pip
pip install -r requirements.txt
```

## Шаг 6: Создание Telegram бота

1. Откройте Telegram и найдите @BotFather
2. Отправьте команду `/newbot`
3. Следуйте инструкциям и получите Bot Token
4. Сохраните токен для следующего шага

### Получение вашего Telegram ID

1. Найдите бота @userinfobot
2. Отправьте команду `/start`
3. Бот пришлёт ваш ID

## Шаг 7: Регистрация в ЮKassa

1. Перейдите на https://yookassa.ru/
2. Зарегистрируйтесь как ИП или самозанятый
3. Создайте магазин
4. Получите Shop ID и Secret Key в настройках магазина
5. В настройках магазина добавьте Webhook URL:
   `https://your-domain.com/webhook/yukassa`

## Шаг 8: Настройка переменных окружения

```bash
cd /opt/shadowsocks-bot
cp .env.example .env
nano .env
```

Заполните все параметры:

```env
# Telegram Bot
BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz  # Токен от @BotFather
ADMIN_IDS=123456789  # Ваш Telegram ID

# Database
DATABASE_URL=postgresql+asyncpg://shadowsocks_user:your_very_secure_password_here@localhost:5432/shadowsocks_db

# ЮKassa
YUKASSA_SHOP_ID=123456
YUKASSA_SECRET_KEY=live_aBcDeFgHiJkLmNoPqRsTuVwXyZ

# Shadowsocks Server
SS_SERVER_HOST=123.45.67.89  # IP вашего VPS
SS_SERVER_PORT=8388
SS_METHOD=chacha20-ietf-poly1305
SS_API_URL=http://localhost:8000/shadowsocks  # Для Outline используйте Management API URL

# Redis
REDIS_URL=redis://localhost:6379/0

# Pricing (в рублях)
PRICE_DAY=100
PRICE_WEEK=500
PRICE_MONTH=1500
PRICE_YEAR=15000

# Server Location
SERVER_LOCATION=Netherlands  # Или ваша локация
```

## Шаг 9: Создание службы для бота

```bash
sudo nano /etc/systemd/system/shadowsocks-bot.service
```

```ini
[Unit]
Description=Shadowsocks VPN Telegram Bot
After=network.target postgresql.service

[Service]
Type=simple
User=root
WorkingDirectory=/opt/shadowsocks-bot
Environment="PATH=/opt/shadowsocks-bot/venv/bin"
ExecStart=/opt/shadowsocks-bot/venv/bin/python main.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

## Шаг 10: Создание службы для webhook

```bash
sudo nano /etc/systemd/system/shadowsocks-webhook.service
```

```ini
[Unit]
Description=Shadowsocks Bot Webhook Server
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/shadowsocks-bot
Environment="PATH=/opt/shadowsocks-bot/venv/bin"
ExecStart=/opt/shadowsocks-bot/venv/bin/uvicorn webhook:app --host 0.0.0.0 --port 8080
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

## Шаг 11: Настройка Nginx

```bash
sudo nano /etc/nginx/sites-available/shadowsocks-webhook
```

```nginx
server {
    listen 80;
    server_name your-domain.com;  # Замените на ваш домен

    location /webhook/yukassa {
        proxy_pass http://localhost:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /health {
        proxy_pass http://localhost:8080;
    }
}
```

```bash
# Активация конфига
sudo ln -s /etc/nginx/sites-available/shadowsocks-webhook /etc/nginx/sites-enabled/

# Проверка конфигурации
sudo nginx -t

# Перезапуск Nginx
sudo systemctl reload nginx
```

## Шаг 12: Установка SSL сертификата

```bash
# Установка Certbot
sudo apt install certbot python3-certbot-nginx

# Получение сертификата
sudo certbot --nginx -d your-domain.com

# Автоматическое обновление
sudo certbot renew --dry-run
```

## Шаг 13: Запуск сервисов

```bash
# Перезагрузка systemd
sudo systemctl daemon-reload

# Включение автозапуска
sudo systemctl enable shadowsocks-bot shadowsocks-webhook

# Запуск служб
sudo systemctl start shadowsocks-bot shadowsocks-webhook

# Проверка статуса
sudo systemctl status shadowsocks-bot
sudo systemctl status shadowsocks-webhook
```

## Шаг 14: Проверка работоспособности

### Проверка логов

```bash
# Логи бота
sudo journalctl -u shadowsocks-bot -f

# Логи webhook
sudo journalctl -u shadowsocks-webhook -f

# Последние 100 строк
sudo journalctl -u shadowsocks-bot -n 100
```

### Проверка портов

```bash
# Проверка портов
sudo netstat -tlnp | grep -E '8080|8388'
```

### Тест webhook

```bash
curl http://localhost:8080/health
```

### Тест бота

1. Откройте Telegram
2. Найдите вашего бота
3. Отправьте команду `/start`
4. Проверьте работу кнопок и команд

## Шаг 15: Мониторинг и обслуживание

### Создание скрипта для мониторинга

```bash
nano /opt/shadowsocks-bot/monitor.sh
```

```bash
#!/bin/bash

# Проверка работы служб
if ! systemctl is-active --quiet shadowsocks-bot; then
    echo "Bot is down, restarting..."
    systemctl restart shadowsocks-bot
fi

if ! systemctl is-active --quiet shadowsocks-webhook; then
    echo "Webhook is down, restarting..."
    systemctl restart shadowsocks-webhook
fi

# Очистка старых логов (старше 7 дней)
find /opt/shadowsocks-bot/logs -name "*.log" -mtime +7 -delete
```

```bash
chmod +x /opt/shadowsocks-bot/monitor.sh
```

### Добавление в cron

```bash
crontab -e
```

```
# Проверка каждые 5 минут
*/5 * * * * /opt/shadowsocks-bot/monitor.sh

# Резервное копирование БД каждый день в 3:00
0 3 * * * pg_dump -U shadowsocks_user shadowsocks_db > /opt/backups/db_$(date +\%Y\%m\%d).sql
```

## Возможные проблемы и решения

### Бот не отвечает

```bash
# Проверьте логи
sudo journalctl -u shadowsocks-bot -n 50

# Проверьте токен бота
grep BOT_TOKEN /opt/shadowsocks-bot/.env

# Перезапустите бота
sudo systemctl restart shadowsocks-bot
```

### Не работают платежи

```bash
# Проверьте webhook
curl https://your-domain.com/webhook/yukassa

# Проверьте логи webhook
sudo journalctl -u shadowsocks-webhook -n 50

# Проверьте настройки ЮKassa
```

### Не создаются подключения Shadowsocks

```bash
# Проверьте статус Shadowsocks
sudo systemctl status shadowsocks

# Проверьте порт
sudo netstat -tlnp | grep 8388

# Проверьте логи
sudo journalctl -u shadowsocks -n 50
```

## Заключение

Ваш Telegram бот для продажи Shadowsocks VPN готов к работе!

Для расширения функционала:
- Добавьте больше серверов в разных странах
- Настройте систему рефералов
- Добавьте промокоды
- Интегрируйте дополнительные платёжные системы (криптовалюты)

Удачи в бизнесе!
