#!/bin/bash

# Скрипт для быстрого запуска проекта

set -e

echo "Starting Shadowsocks VPN Bot..."

# Проверка наличия .env файла
if [ ! -f .env ]; then
    echo "Error: .env file not found!"
    echo "Please copy .env.example to .env and configure it."
    exit 1
fi

# Активация виртуального окружения
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3.11 -m venv venv
fi

source venv/bin/activate

# Установка зависимостей
echo "Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Создание директории для логов
mkdir -p logs

# Запуск бота
echo "Starting bot..."
python main.py
