from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Telegram
    BOT_TOKEN: str
    ADMIN_IDS: str

    # Database
    DATABASE_URL: str

    # ЮKassa
    YUKASSA_SHOP_ID: str
    YUKASSA_SECRET_KEY: str

    # Shadowsocks
    SS_SERVER_HOST: str
    SS_SERVER_PORT: int = 8388
    SS_METHOD: str = "chacha20-ietf-poly1305"
    SS_API_URL: str

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Pricing
    PRICE_DAY: int = 100
    PRICE_WEEK: int = 500
    PRICE_MONTH: int = 1500
    PRICE_YEAR: int = 15000

    # Server
    SERVER_LOCATION: str = "Netherlands"

    @property
    def admin_ids_list(self) -> List[int]:
        return [int(id.strip()) for id in self.ADMIN_IDS.split(",")]


settings = Settings()
