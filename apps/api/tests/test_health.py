from fastapi.testclient import TestClient
from restaurant_os.main import create_app


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

