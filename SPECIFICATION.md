# FreedomVPN Bot — Полная спецификация

## 1. Общее описание

**Название:** FreedomVPN Bot
**Платформа:** Telegram
**Технология VPN:** VLESS + Reality (через Marzban)
**Назначение:** Продажа VPN-подписок с автоматической выдачей ключей

---

## 2. Технический стек

### Backend
- **Язык:** Python 3.11+
- **Фреймворк бота:** aiogram 3.x (polling mode)
- **База данных:** SQLite (aiosqlite) или PostgreSQL
- **ORM:** SQLAlchemy 2.x (async)
- **Валидация:** Pydantic v2
- **Логирование:** Loguru

### VPN Backend
- **Панель:** Marzban (REST API)
- **Протокол:** VLESS + Reality
- **Сервер:** Xray-core

### Платежи
- **Провайдер:** ЮKassa
- **Метод:** Telegram Payments API (invoice)

### Деплой
- **Сервер:** Ubuntu 22.04 VPS
- **Процесс-менеджер:** systemd (ТОЛЬКО systemd, без pm2)
- **Reverse proxy:** Не требуется (polling mode)

---

## 3. Структура базы данных

### Таблица: users
```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    telegram_id BIGINT UNIQUE NOT NULL,
    username VARCHAR(255),
    first_name VARCHAR(255),
    last_name VARCHAR(255),
    referrer_id BIGINT,              -- telegram_id пригласившего
    referral_code VARCHAR(20) UNIQUE, -- уникальный код ref_XXXXX
    balance FLOAT DEFAULT 0,          -- реферальный баланс
    is_admin BOOLEAN DEFAULT FALSE,
    created_at DATETIME DEFAULT NOW(),
    updated_at DATETIME
);
```

### Таблица: subscriptions
```sql
CREATE TABLE subscriptions (
    id INTEGER PRIMARY KEY,
    telegram_id BIGINT NOT NULL,
    plan_type VARCHAR(20) NOT NULL,   -- trial, day, week, month, 3month, year
    marzban_username VARCHAR(100),    -- имя пользователя в Marzban
    vless_key TEXT,                   -- полный VLESS URL
    start_date DATETIME NOT NULL,
    end_date DATETIME NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at DATETIME DEFAULT NOW()
);
```

### Таблица: payments
```sql
CREATE TABLE payments (
    id INTEGER PRIMARY KEY,
    telegram_id BIGINT NOT NULL,
    amount FLOAT NOT NULL,
    currency VARCHAR(3) DEFAULT 'RUB',
    plan_type VARCHAR(20) NOT NULL,
    status VARCHAR(20) DEFAULT 'pending', -- pending, completed, failed, refunded
    payment_id VARCHAR(255),          -- ID от ЮKassa
    created_at DATETIME DEFAULT NOW(),
    completed_at DATETIME
);
```

### Таблица: promocodes
```sql
CREATE TABLE promocodes (
    id INTEGER PRIMARY KEY,
    code VARCHAR(50) UNIQUE NOT NULL,
    discount_type VARCHAR(20) NOT NULL, -- percent, fixed, bonus_days
    discount_value FLOAT NOT NULL,
    max_uses INTEGER,                   -- NULL = безлимит
    current_uses INTEGER DEFAULT 0,
    expires_at DATETIME,                -- NULL = бессрочный
    applicable_plans VARCHAR(255),      -- NULL = все планы
    is_active BOOLEAN DEFAULT TRUE,
    created_at DATETIME DEFAULT NOW()
);
```

### Таблица: promocode_usages
```sql
CREATE TABLE promocode_usages (
    id INTEGER PRIMARY KEY,
    promocode_id INTEGER NOT NULL,
    telegram_id BIGINT NOT NULL,
    discount_amount FLOAT,
    bonus_days INTEGER,
    used_at DATETIME DEFAULT NOW(),
    UNIQUE(promocode_id, telegram_id)  -- один промокод на пользователя
);
```

### Таблица: referral_bonuses
```sql
CREATE TABLE referral_bonuses (
    id INTEGER PRIMARY KEY,
    referrer_id BIGINT NOT NULL,       -- кто получил бонус
    referred_id BIGINT NOT NULL,       -- кто оплатил
    payment_id INTEGER,
    bonus_amount FLOAT NOT NULL,
    bonus_type VARCHAR(20) DEFAULT 'balance', -- balance или days
    created_at DATETIME DEFAULT NOW()
);
```

---

## 4. Тарифные планы

| План | Код | Цена (₽) | Длительность |
|------|-----|----------|--------------|
| Триал | trial | 0 | 72 часа |
| День | day | 9 | 1 день |
| Неделя | week | 49 | 7 дней |
| Месяц | month | 149 | 30 дней |
| 3 месяца | 3month | 399 | 90 дней |
| Год | year | 1499 | 365 дней |

---

## 5. Функционал бота

### 5.1 Команды

| Команда | Описание | Доступ |
|---------|----------|--------|
| /start | Приветствие + главное меню | Все |
| /menu | Показать главное меню | Все |
| /status | Статус подписки | Все |
| /help | Справка | Все |
| /myid | Показать Telegram ID | Все |
| /admin | Админ-панель | Админы |
| /stats | Статистика бота | Админы |
| /broadcast | Рассылка | Админы |
| /createpromo | Создать промокод | Админы |

### 5.2 Главное меню (inline-кнопки)

```
[🎁 Попробовать бесплатно (72ч)]  -- только если триал не использован
[💳 Купить подписку]
[📊 Мой статус]
[📱 Инструкция]
[👥 Пригласить друга]
[🎁 Промокод]
[❓ Помощь]
[⚙️ Админ-панель]  -- только для админов
```

### 5.3 Процесс покупки

1. Пользователь выбирает тариф
2. (Опционально) Вводит промокод
3. Получает invoice через Telegram Payments
4. Оплачивает через ЮKassa
5. Бот получает successful_payment
6. Создаётся/продлевается подписка в Marzban
7. Пользователь получает VLESS-ключ + QR-код

### 5.4 Триал (тестовый период)

- **Длительность:** 72 часа
- **Лимит:** 1 раз на пользователя
- **Активация:** Без оплаты, по нажатию кнопки
- **Для админов:** Кнопка триала всегда видна (для тестирования)

### 5.5 Реферальная система

- **Формат ссылки:** `https://t.me/bot_username?start=ref_XXXXX`
- **Бонус рефереру:** 15% от оплаты приглашённого (на баланс)
- **Вывод:** Конвертация баланса в дни подписки

### 5.6 Промокоды

**Типы:**
- `percent` — скидка в % (например, 20%)
- `fixed` — фиксированная скидка в ₽ (например, 50₽)
- `bonus_days` — бонусные дни (например, 7 дней бесплатно)

**Создание (админ):**
```
/createpromo КОД тип значение макс_использований
/createpromo FREEWEEK bonus_days 7 100
/createpromo SALE20 percent 20 50
```

### 5.7 Статус подписки

Показывает:
- Активна/неактивна
- Дата окончания
- Оставшееся время
- Использованный трафик (если доступно)
- Кнопки: Продлить, Показать ключ, Показать QR

### 5.8 Инструкция подключения

Отправляется после активации подписки:
- Ссылки на приложения (iOS, Android, Windows, macOS)
- VLESS-ключ (копируемый)
- QR-код (по запросу)
- Пошаговая инструкция

---

## 6. Интеграция с Marzban

### API Endpoints

```python
# Авторизация
POST /api/admin/token
Body: username, password
Response: access_token

# Создание пользователя
POST /api/user
Headers: Authorization: Bearer {token}
Body: {
    "username": "FreedomVPN_telegram_id_xxxx",
    "proxies": {"vless": {"flow": "xtls-rprx-vision"}},
    "inbounds": {"vless": ["VLESS TCP REALITY"]},
    "expire": unix_timestamp,
    "data_limit": 0  # безлимит
}

# Получение пользователя
GET /api/user/{username}

# Продление подписки
PUT /api/user/{username}
Body: {"expire": new_unix_timestamp}

# Удаление пользователя
DELETE /api/user/{username}

# Получение ссылки
GET /api/user/{username}
Response: links[] -> первая ссылка = VLESS URL
```

### Формат имени пользователя Marzban
```
FreedomVPN_{username или telegram_id}_{random_4_chars}
Пример: FreedomVPN_john_a3x9
```

---

## 7. Интеграция с ЮKassa

### Настройки
- Shop ID и Secret Key в .env
- Webhook: Telegram Payments (не нужен отдельный webhook)

### Процесс оплаты
```python
# 1. Создаём invoice
await bot.send_invoice(
    chat_id=user_id,
    title="VPN подписка",
    description=f"Тариф: {plan_name}",
    payload=f"sub_{plan_type}_{user_id}",
    provider_token=YUKASSA_TOKEN,
    currency="RUB",
    prices=[LabeledPrice(label=plan_name, amount=price * 100)]
)

# 2. Обрабатываем pre_checkout_query
@router.pre_checkout_query()
async def process_pre_checkout(query):
    await query.answer(ok=True)

# 3. Обрабатываем successful_payment
@router.message(F.successful_payment)
async def process_payment(message):
    # Создаём подписку
    # Отправляем ключ пользователю
```

---

## 8. Конфигурация (.env)

```env
# Telegram
BOT_TOKEN=123456:ABC...
ADMIN_IDS=123456789,987654321

# Database
DATABASE_URL=sqlite+aiosqlite:///data/freedomvpn.db

# ЮKassa
YUKASSA_SHOP_ID=123456
YUKASSA_SECRET_KEY=live_xxx

# Marzban
MARZBAN_API_URL=http://localhost:8000
MARZBAN_USERNAME=admin
MARZBAN_PASSWORD=password

# Pricing (₽)
PRICE_TRIAL=0
PRICE_DAY=9
PRICE_WEEK=49
PRICE_MONTH=149
PRICE_3MONTH=399
PRICE_YEAR=1499

# Referral
REFERRAL_PERCENT=0.15

# Server
SERVER_LOCATION=Netherlands
SUPPORT_USERNAME=support_user
```

---

## 9. Структура проекта (рекомендуемая)

```
freedomvpn-bot/
├── bot/
│   ├── __init__.py
│   ├── handlers/
│   │   ├── __init__.py
│   │   ├── start.py          # /start, /menu, /help
│   │   ├── subscription.py   # выбор тарифа, статус
│   │   ├── payment.py        # оплата, successful_payment
│   │   ├── referral.py       # реферальная система, промокоды
│   │   └── admin.py          # админ-команды
│   ├── keyboards/
│   │   ├── __init__.py
│   │   └── inline.py         # все inline-клавиатуры
│   ├── middlewares/
│   │   └── __init__.py
│   └── states/
│       └── __init__.py       # FSM states
├── database/
│   ├── __init__.py
│   ├── database.py           # engine, session, init_db
│   └── models.py             # SQLAlchemy models
├── services/
│   ├── __init__.py
│   ├── user_service.py
│   ├── subscription_service.py
│   ├── marzban_service.py
│   ├── payment_service.py
│   ├── promocode_service.py
│   └── referral_service.py
├── config.py                 # Pydantic Settings
├── main.py                   # точка входа
├── requirements.txt
├── .env
├── .env.example
└── data/
    └── freedomvpn.db
```

---

## 10. Деплой

### Единственный способ запуска — systemd

```ini
# /etc/systemd/system/freedomvpn-bot.service
[Unit]
Description=FreedomVPN Telegram Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/bot
Environment=PATH=/root/bot/venv/bin
ExecStart=/root/bot/venv/bin/python main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### Команды управления
```bash
systemctl start freedomvpn-bot
systemctl stop freedomvpn-bot
systemctl restart freedomvpn-bot
systemctl status freedomvpn-bot
journalctl -u freedomvpn-bot -f  # логи
```

### ЗАПРЕЩЕНО
- Запускать `python main.py` вручную
- Использовать pm2
- Запускать бота локально с тем же токеном

---

## 11. Важные правила

### Один токен = один экземпляр
Бот с одним токеном может работать только в ОДНОМ экземпляре. Иначе — конфликт getUpdates.

### Логирование
- Все ошибки логируются в файл и journalctl
- Формат: `{time} | {level} | {message}`

### Безопасность
- Токены только в .env (не в коде)
- .env в .gitignore
- Проверка is_admin для админ-команд

### Обработка ошибок
- Все хендлеры обёрнуты в try/except
- Пользователь получает понятное сообщение при ошибке
- Ошибка логируется с traceback

---

## 12. Известные edge cases

1. **Пользователь блокирует бота** — нельзя отправить сообщение, ловить BotBlocked
2. **Marzban недоступен** — показать ошибку, не брать деньги
3. **Двойная оплата** — проверять по payment_id, не создавать дубли
4. **Истёкший промокод** — проверять expires_at
5. **Превышен лимит промокода** — проверять current_uses < max_uses
6. **Пользователь уже использовал триал** — проверять has_used_trial()

---

## 13. Метрики для отслеживания

- Количество пользователей
- Количество активных подписок
- Выручка за период
- Конверсия триал → платная подписка
- Использование промокодов
- Реферальные бонусы

---

## 14. Возможные улучшения (v2)

- [ ] Несколько VPN-серверов (выбор локации)
- [ ] Автопродление подписки
- [ ] Уведомления за N дней до окончания
- [ ] Webhook mode вместо polling (для масштабирования)
- [ ] PostgreSQL вместо SQLite
- [ ] Redis для кэширования и rate limiting
- [ ] Мониторинг трафика пользователей
- [ ] Telegram Mini App для красивого UI

---

*Документ создан: 2026-01-21*
*Версия: 1.0*
