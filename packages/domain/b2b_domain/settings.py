from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = (
        "postgresql+psycopg://sales_app:local_only_change_me@localhost:55432/"
        "sales_intelligence"
    )
    worker_poll_seconds: float = 2.0
    raw_data_dir: Path = Path("data/raw/imports")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
