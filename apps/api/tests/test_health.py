from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from restaurant_os.config import get_settings
from restaurant_os.main import create_app


def setup_function() -> None:
    get_settings.cache_clear()


def test_live_health_check() -> None:
    client = TestClient(create_app())

    response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_version_health_check() -> None:
    client = TestClient(create_app())

    response = client.get("/health/version")

    assert response.status_code == 200
    assert response.json()["service"] == "restaurant-os-api"


def test_ready_health_check_reports_missing_dependencies(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("RESTAURANTOS_DATABASE_URL", raising=False)
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.delenv("RESTAURANTOS_REDIS_URL", raising=False)
    get_settings.cache_clear()

    client = TestClient(create_app())

    response = client.get("/health/ready")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "degraded"
    assert payload["dependencies"] == [
        {
            "name": "postgres",
            "status": "not_configured",
            "detail": "DATABASE_URL is missing",
        },
        {
            "name": "redis",
            "status": "not_configured",
            "detail": "REDIS_URL is missing",
        },
    ]
