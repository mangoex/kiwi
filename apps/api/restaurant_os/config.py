from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="RESTAURANTOS_", env_file=".env")

    environment: str = Field(default="local")
    service_name: str = Field(default="restaurant-os-api")
    app_version: str = Field(default="0.0.0")
    git_commit: str = Field(default="unknown")


@lru_cache
def get_settings() -> Settings:
    return Settings()

