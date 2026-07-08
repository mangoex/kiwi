import re
import shutil
import subprocess
import tempfile
from pathlib import Path

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


def test_admin_shell_exposes_saas_catalog_workbench() -> None:
    client = TestClient(create_app())

    response = client.get("/admin")

    assert response.status_code == 200
    assert "Admin RestaurantOS" in response.text
    assert "data-admin-tab=\"catalogs\"" in response.text
    assert "create-branch" in response.text
    assert "create-product" in response.text
    assert "/api/v1/branches" in response.text
    assert "/api/v1/catalog/products" in response.text
    assert "inventory-stock-table" in response.text
    assert "/api/v1/inventory/stock" in response.text
    assert "/api/v1/recipes" in response.text
    assert "catalog-workbench" in response.text
    assert "inventory-workbench" in response.text
    assert "Abrir POS" in response.text
    assert "Abrir KDS" in response.text
    assert "Sucursales y productos" in response.text
    assert "Existencias, recetas y kardex" in response.text
    assert "inventory-kardex-table" in response.text
    assert "saas-command-center" in response.text
    assert "readiness-steps" in response.text
    assert "ops-pulse" in response.text
    assert "Centro de mando SaaS" in response.text
    assert "updateSaasCommandCenter" in response.text
    assert "login-panel" in response.text
    assert "/api/v1/auth/login" in response.text
    assert "mangoex@gmail.com" in response.text


def test_platform_shell_embedded_javascript_is_valid() -> None:
    if not shutil.which("node"):
        pytest.skip("Node is not available")

    client = TestClient(create_app())
    response = client.get("/admin")
    assert response.status_code == 200

    match = re.search(r"<script>(.*?)</script>", response.text, re.S)
    assert match is not None

    with tempfile.TemporaryDirectory() as temp_dir:
        script_path = Path(temp_dir) / "platform-shell.js"
        script_path.write_text(match.group(1), encoding="utf-8")
        result = subprocess.run(
            ["node", "--check", str(script_path)],
            check=False,
            capture_output=True,
            text=True,
        )

    assert result.returncode == 0, result.stderr


def test_pos_shell_loads_catalog_endpoint() -> None:
    client = TestClient(create_app())

    response = client.get("/pos")

    assert response.status_code == 200
    assert "pos-catalog" in response.text
    assert "/api/v1/catalog/products" in response.text
    assert "Venta local" in response.text
    assert "/api/v1/print-jobs" in response.text
