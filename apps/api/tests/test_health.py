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


def test_ready_health_check_reports_missing_dependencies() -> None:
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


def test_platform_shell_root_is_visible() -> None:
    client = TestClient(create_app())

    response = client.get("/")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "RestaurantOS" in response.text
    assert "/admin" in response.text
    assert "/pos" in response.text
    assert "/kds" in response.text
    assert "/health/ready" in response.text
    assert "organization-name" in response.text
    assert "/api/v1/platform/bootstrap-status" in response.text


def test_platform_module_routes_are_visible() -> None:
    client = TestClient(create_app())

    for path, title in [("/admin", "Admin"), ("/pos", "POS"), ("/kds", "KDS")]:
        response = client.get(path)

        assert response.status_code == 200
        assert title in response.text


def test_pos_shell_loads_catalog_endpoint() -> None:
    client = TestClient(create_app())

    response = client.get("/pos")

    assert response.status_code == 200
    assert "pos-catalog" in response.text
    assert "/api/v1/catalog/products" in response.text
    assert "Venta local" in response.text
    assert "/api/v1/print-jobs" in response.text
