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
    max_upload_bytes: int = 100 * 1024 * 1024
    max_rows_per_source: int = 250_000
    max_fields_per_source: int = 200
    profile_distinct_value_limit: int = 10_000

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
