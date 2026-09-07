from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://flashsale:flashsale@localhost:5432/flashsale"
    redis_url: str = "redis://localhost:6379/0"
    item_id: str = "flash-sale-item"
    initial_stock: int = 1000
    rate_limit_capacity: int = 100
    rate_limit_refill_per_second: float = 50


settings = Settings()
