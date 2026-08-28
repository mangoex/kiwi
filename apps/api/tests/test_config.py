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


def test_assisted_order_openrouter_defaults_to_disabled(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.delenv("RESTAURANTOS_ASSISTED_ORDER_ENABLED", raising=False)
    monkeypatch.delenv("RESTAURANTOS_OPENROUTER_API_KEY", raising=False)

    settings = get_settings()

    assert settings.assisted_order_enabled is False
    assert settings.openrouter_api_key is None
    assert settings.openrouter_model == "google/gemini-3.1-flash-lite"


def test_assisted_order_reads_server_side_openrouter_configuration(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setenv("RESTAURANTOS_ASSISTED_ORDER_ENABLED", "true")
    monkeypatch.setenv("RESTAURANTOS_OPENROUTER_API_KEY", "synthetic-key-with-safe-length")
    monkeypatch.setenv("RESTAURANTOS_OPENROUTER_MODEL", "provider/model")

    settings = get_settings()

    assert settings.assisted_order_enabled is True
    assert settings.openrouter_api_key == "synthetic-key-with-safe-length"
    assert settings.openrouter_model == "provider/model"
