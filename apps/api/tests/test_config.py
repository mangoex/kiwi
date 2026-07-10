from __future__ import annotations

from pytest import MonkeyPatch
from restaurant_os.config import get_settings


def setup_function() -> None:
    get_settings.cache_clear()


def test_settings_accept_standard_database_and_redis_urls(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:pass@postgres:5432/db")
    monkeypatch.setenv("REDIS_URL", "redis://redis:6379/0")

    settings = get_settings()

    assert settings.database_url == "postgresql+psycopg://user:pass@postgres:5432/db"
    assert settings.redis_url == "redis://redis:6379/0"


def test_settings_accept_prefixed_database_and_redis_urls(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv(
        "RESTAURANTOS_DATABASE_URL",
        "postgresql+psycopg://user:pass@kiwi-postgres:5432/restaurantos",
    )
    monkeypatch.setenv("RESTAURANTOS_REDIS_URL", "redis://kiwi-redis:6379/0")

    settings = get_settings()

    assert settings.database_url == "postgresql+psycopg://user:pass@kiwi-postgres:5432/restaurantos"
    assert settings.redis_url == "redis://kiwi-redis:6379/0"
