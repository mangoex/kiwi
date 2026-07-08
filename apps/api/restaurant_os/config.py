from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="RESTAURANTOS_", env_file=".env")

    environment: str = Field(default="local")
    service_name: str = Field(default="restaurant-os-api")
    app_version: str = Field(default="0.0.0")
    git_commit: str = Field(default="unknown")
    database_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("RESTAURANTOS_DATABASE_URL", "DATABASE_URL"),
    )
    redis_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("RESTAURANTOS_REDIS_URL", "REDIS_URL"),
    )
    secret_key: str = Field(
        default="dev-secret-change-me",
        validation_alias=AliasChoices("RESTAURANTOS_SECRET_KEY", "SECRET_KEY"),
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
