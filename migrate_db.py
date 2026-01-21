#!/usr/bin/env python3
"""
Скрипт миграции базы данных для добавления новых полей и таблиц
"""
import asyncio
import sqlite3
from database.database import init_db
from loguru import logger


async def migrate():
    """Выполнить миграцию базы данных"""

    # Путь к базе данных
    db_path = "/var/lib/freedomvpn/freedomvpn.db"

    logger.info("Starting database migration...")

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Проверяем существующие столбцы в таблице users
        cursor.execute("PRAGMA table_info(users)")
        existing_columns = {row[1] for row in cursor.fetchall()}

        # Добавляем новые столбцы если их нет
        new_columns = {
            "referral_code": "VARCHAR(50) UNIQUE",
            "total_referrals": "INTEGER DEFAULT 0",
            "total_earned": "FLOAT DEFAULT 0.0",
            "notify_expiration": "BOOLEAN DEFAULT 1",
            "notify_referrals": "BOOLEAN DEFAULT 1",
        }

        for column, column_type in new_columns.items():
            if column not in existing_columns:
                try:
                    cursor.execute(f"ALTER TABLE users ADD COLUMN {column} {column_type}")
                    logger.info(f"Added column '{column}' to users table")
                except sqlite3.OperationalError as e:
                    logger.warning(f"Column '{column}' may already exist: {e}")

        conn.commit()

        # Создаем новые таблицы через init_db()
        logger.info("Creating new tables...")
        await init_db()

        logger.success("✅ Database migration completed successfully!")

        conn.close()

    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(migrate())
