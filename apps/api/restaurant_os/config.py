from __future__ import annotations

from functools import lru_cache

from pydantic import AliasChoices, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="RESTAURANTOS_", env_file=".env", populate_by_name=True
    )

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

    @field_validator("environment", mode="before")
    @classmethod
    def normalize_environment(cls, value: object) -> str:
        normalized = str(value).strip().lower()
        if normalized not in {"local", "test", "production"}:
            raise ValueError("RESTAURANTOS_ENVIRONMENT must be local, test or production")
        return normalized

    @model_validator(mode="after")
    def production_settings_are_safe(self) -> Settings:
        """Production must never silently fall back to development credentials."""
        if self.environment == "production" and (
            self.secret_key == "dev-secret-change-me" or len(self.secret_key.strip()) < 32
        ):
            raise ValueError(
                "RESTAURANTOS_SECRET_KEY must contain at least 32 characters in production"
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
