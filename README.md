# Shadowsocks VPN Telegram Bot

Telegram-бот для автоматизированной продажи доступа к Shadowsocks VPN.

## Возможности

- Автоматическое создание и управление Shadowsocks подключениями
- Интеграция с ЮKassa для приёма платежей
- Тарифы: день, неделя, месяц, год
- Автоматическая проверка истечения подписок
- Админ-панель с статистикой
- QR-коды для быстрого подключения
- Инструкции для всех платформ (iOS, Android, Windows, macOS)

## Архитектура

```
shadowsocks-proxy-bot/
├── bot/                      # Telegram бот
│   ├── handlers/            # Обработчики команд
│   │   ├── start.py        # /start, /help
│   │   ├── subscription.py # Управление подписками
│   │   ├── payment.py      # Обработка платежей
│   │   └── admin.py        # Админ-панель
│   └── keyboards/          # Клавиатуры
├── database/               # База данных
│   ├── models.py          # SQLAlchemy модели
│   └── database.py        # Подключение к БД
├── services/              # Бизнес-логика
│   ├── user_service.py
│   ├── subscription_service.py
│   ├── payment_service.py
│   └── shadowsocks_service.py
├── main.py               # Запуск бота
├── webhook.py           # Webhook сервер для ЮKassa
├── scheduler.py         # Планировщик задач
├── config.py           # Конфигурация
└── requirements.txt    # Зависимости
```

## Требования

- Python 3.11+
- PostgreSQL 14+
- Redis (опционально)
- VPS с установленным Shadowsocks (Outline VPN)

## Установка

### 1. Клонирование репозитория

```bash
cd /opt
git clone <your-repo-url> shadowsocks-bot
cd shadowsocks-bot
```

### 2. Создание виртуального окружения

```bash
python3.11 -m venv venv
source venv/bin/activate
```

### 3. Установка зависимостей

```bash
pip install -r requirements.txt
```

### 4. Настройка PostgreSQL

```bash
sudo -u postgres psql
CREATE DATABASE shadowsocks_db;
CREATE USER shadowsocks_user WITH PASSWORD 'your_secure_password';
GRANT ALL PRIVILEGES ON DATABASE shadowsocks_db TO shadowsocks_user;
\q
```

### 5. Настройка переменных окружения

```bash
cp .env.example .env
nano .env
```

Заполните все необходимые параметры в `.env`:

```env
BOT_TOKEN=your_telegram_bot_token
ADMIN_IDS=123456789,987654321
DATABASE_URL=postgresql+asyncpg://shadowsocks_user:your_secure_password@localhost:5432/shadowsocks_db
YUKASSA_SHOP_ID=your_shop_id
YUKASSA_SECRET_KEY=your_secret_key
SS_SERVER_HOST=your_vps_ip
SS_SERVER_PORT=8388
SS_API_URL=http://localhost:8000/shadowsocks
```

### 6. Инициализация базы данных

База данных инициализируется автоматически при первом запуске бота.

### 7. Запуск бота

```bash
python main.py
```

## Развёртывание с Systemd

### Создание службы для бота

```bash
sudo nano /etc/systemd/system/shadowsocks-bot.service
```

```ini
[Unit]
Description=Shadowsocks VPN Telegram Bot
After=network.target postgresql.service

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/shadowsocks-bot
Environment="PATH=/opt/shadowsocks-bot/venv/bin"
ExecStart=/opt/shadowsocks-bot/venv/bin/python main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### Создание службы для webhook

```bash
sudo nano /etc/systemd/system/shadowsocks-webhook.service
```

```ini
[Unit]
Description=Shadowsocks Bot Webhook Server
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/shadowsocks-bot
Environment="PATH=/opt/shadowsocks-bot/venv/bin"
ExecStart=/opt/shadowsocks-bot/venv/bin/uvicorn webhook:app --host 0.0.0.0 --port 8080
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### Запуск служб

```bash
sudo systemctl daemon-reload
sudo systemctl enable shadowsocks-bot shadowsocks-webhook
sudo systemctl start shadowsocks-bot shadowsocks-webhook
sudo systemctl status shadowsocks-bot shadowsocks-webhook
```

## Настройка Nginx для webhook

```bash
sudo nano /etc/nginx/sites-available/shadowsocks-webhook
```

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location /webhook/yukassa {
        proxy_pass http://localhost:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/shadowsocks-webhook /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### SSL сертификат

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

## Настройка Shadowsocks (Outline VPN)

Рекомендуется использовать Outline VPN для управления Shadowsocks:

```bash
# Установка Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Установка Outline Manager
# Следуйте инструкциям на https://getoutline.org/
```

После установки Outline, настройте Management API URL в `.env`:

```env
SS_API_URL=https://your-outline-api-url/
```

## Настройка ЮKassa

1. Зарегистрируйтесь на https://yookassa.ru/
2. Создайте магазин
3. Получите Shop ID и Secret Key
4. Настройте webhook URL: `https://your-domain.com/webhook/yukassa`
5. Добавьте данные в `.env`

## Мониторинг логов

```bash
# Логи бота
sudo journalctl -u shadowsocks-bot -f

# Логи webhook
sudo journalctl -u shadowsocks-webhook -f

# Логи приложения
tail -f logs/bot.log
```

## Резервное копирование

### База данных

```bash
pg_dump -U shadowsocks_user shadowsocks_db > backup_$(date +%Y%m%d).sql
```

### Восстановление

```bash
psql -U shadowsocks_user shadowsocks_db < backup_20260115.sql
```

## Масштабирование

Для масштабирования на несколько серверов:

1. Разверните несколько Shadowsocks серверов в разных странах
2. Добавьте балансировщик нагрузки
3. Используйте Redis для хранения сессий
4. Настройте репликацию PostgreSQL

## Безопасность

- Используйте сильные пароли для БД
- Регулярно обновляйте зависимости
- Настройте firewall (ufw)
- Используйте SSL для всех подключений
- Ограничьте доступ к API

## Поддержка

Для вопросов и предложений создавайте issue в репозитории.

## Лицензия

MIT
