from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "postgresql+psycopg://cc:cc@localhost:5432/content_creator"
    redis_url: str = "redis://localhost:6379/0"
    storage_path: str = "./storage"
    use_celery: bool = False
    openai_api_key: str | None = None
    langchain_tracing_v2: bool = False
    langchain_api_key: str | None = None
    langchain_project: str = "content-creator-etl"
    max_executor_retries: int = 3


@lru_cache
def get_settings() -> Settings:
    return Settings()
