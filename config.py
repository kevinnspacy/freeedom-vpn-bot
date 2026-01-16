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

    # Marzban (VLESS + Reality)
    MARZBAN_API_URL: str = "http://localhost:8000"
    MARZBAN_USERNAME: str = "admin"
    MARZBAN_PASSWORD: str = "admin"

    # VPN Server
    VPN_SERVER_HOST: str = "107.189.23.38"

    # Legacy Shadowsocks (deprecated, kept for compatibility)
    SS_SERVER_HOST: str = "107.189.23.38"
    SS_SERVER_PORT: int = 8388
    SS_METHOD: str = "chacha20-ietf-poly1305"
    SS_API_URL: str = ""

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Pricing
    PRICE_TRIAL: int = 0  # Бесплатный тестовый период 24 часа
    PRICE_DAY: int = 9
    PRICE_WEEK: int = 49
    PRICE_MONTH: int = 149
    PRICE_3MONTH: int = 399
    PRICE_YEAR: int = 1499

    # Server
    SERVER_LOCATION: str = "Netherlands"

    @property
    def admin_ids_list(self) -> List[int]:
        return [int(id.strip()) for id in self.ADMIN_IDS.split(",")]


settings = Settings()
