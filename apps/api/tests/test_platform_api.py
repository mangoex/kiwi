from __future__ import annotations

from collections.abc import Generator
from datetime import datetime, timezone

from fastapi.testclient import TestClient
from restaurant_os.database import get_session
from restaurant_os.main import create_app
from restaurant_os.models import (
    audit_events,
    branch_product_availability,
    branches,
    inventory_items,
    inventory_movements,
    inventory_units,
    legal_entities,
    metadata,
    organizations,
    permissions,
    price_versions,
    product_categories,
    products,
    recipe_components,
    recipes,
    role_permissions,
    roles,
    user_credentials,
    user_roles,
    users,
    warehouses,
)
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

UTC = timezone.utc


def test_bootstrap_status_reads_seeded_platform_data() -> None:
    client = _client_with_seeded_database()

    response = client.get("/api/v1/platform/bootstrap-status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["counts"]["organizations"] == 1
    assert payload["counts"]["branches"] == 1
    assert payload["counts"]["warehouses"] == 1
    assert payload["counts"]["products"] == 3
    assert payload["primary_organization"]["name"] == "Kiwi Restaurante"
    assert payload["primary_branch"]["name"] == "Sucursal Piloto"


def test_superadmin_can_login_and_create_active_admin_user() -> None:
    client = _client_with_seeded_database()

    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": "mangoex@gmail.com", "password": "superadmin-test-password"},
    )
    assert login_response.status_code == 200
    session = login_response.json()
    assert session["user"]["email"] == "mangoex@gmail.com"
    assert session["user"]["status"] == "active"
    assert session["user"]["is_superadmin"] is True
    assert "Administrador corporativo" in session["user"]["roles"]
    assert "admin.manage" in session["user"]["permissions"]
    assert "catalog.manage" in session["user"]["permissions"]
    assert session["token"]

    headers = {"Authorization": f"Bearer {session['token']}"}
    user_response = client.post(
        "/api/v1/users",
        headers=headers,
        json={
            "email": "admin.negocio@kiwi.local",
            "display_name": "Admin Negocio",
            "password": "Temporal123+",
        },
    )
    assert user_response.status_code == 200
    assert user_response.json()["status"] == "active"

    created_login = client.post(
        "/api/v1/auth/login",
        json={"email": "admin.negocio@kiwi.local", "password": "Temporal123+"},
    )
    assert created_login.status_code == 200
    assert created_login.json()["user"]["display_name"] == "Admin Negocio"
    assert created_login.json()["user"]["is_superadmin"] is False


def test_organizations_and_branches_are_listed() -> None:
    client = _client_with_seeded_database()

    organizations_response = client.get("/api/v1/organizations")
    branches_response = client.get("/api/v1/branches")

    assert organizations_response.status_code == 200
    assert branches_response.status_code == 200
    assert organizations_response.json()[0]["name"] == "Kiwi Restaurante"
    assert branches_response.json()[0]["warehouse_name"] == "Almacen Sucursal Piloto"


def test_catalog_products_are_listed_with_prices_and_availability() -> None:
    client = _client_with_seeded_database()

    response = client.get("/api/v1/catalog/products")

    assert response.status_code == 200
    products_payload = response.json()
    assert [product["sku"] for product in products_payload] == [
        "KIWI-SODA",
        "KIWI-BURGER",
        "KIWI-FRIES",
    ]
    assert products_payload[0]["price_cents"] == 3000
    assert products_payload[0]["currency"] == "MXN"
    assert products_payload[0]["is_available"] is True


def test_admin_can_create_branch_and_product_catalog_entries() -> None:
    client = _client_with_seeded_database()

    branch_response = client.post(
        "/api/v1/branches",
        json={"name": "Sucursal Norte", "code": "norte"},
    )
    assert branch_response.status_code == 200
    branch = branch_response.json()
    assert branch["name"] == "Sucursal Norte"
    assert branch["code"] == "NORTE"
    assert branch["warehouse"]["name"] == "Almacen Sucursal Norte"

    duplicate_branch = client.post(
        "/api/v1/branches",
        json={"name": "Sucursal Norte Bis", "code": "NORTE"},
    )
    assert duplicate_branch.status_code == 409
    assert duplicate_branch.json()["detail"]["code"] == "branch_already_exists"

    product_response = client.post(
        "/api/v1/catalog/products",
        json={
            "name": "Wrap Kiwi",
            "sku": "kiwi-wrap",
            "category_name": "Comida",
            "station": "kitchen",
            "price_cents": 8900,
        },
    )
    assert product_response.status_code == 200
    product = product_response.json()
    assert product["name"] == "Wrap Kiwi"
    assert product["sku"] == "KIWI-WRAP"
    assert product["category_name"] == "Comida"
    assert product["price_cents"] == 8900
    assert product["is_available"] is True

    duplicate_product = client.post(
        "/api/v1/catalog/products",
        json={
            "name": "Wrap Kiwi Repetido",
            "sku": "KIWI-WRAP",
            "category_name": "Comida",
            "station": "kitchen",
            "price_cents": 8900,
        },
    )
    assert duplicate_product.status_code == 409
    assert duplicate_product.json()["detail"]["code"] == "product_already_exists"

    branches_response = client.get("/api/v1/branches")
    assert branches_response.status_code == 200
    created_branch = next(item for item in branches_response.json() if item["code"] == "NORTE")
    assert created_branch["warehouse_name"] == "Almacen Sucursal Norte"

    products_response = client.get("/api/v1/catalog/products")
    assert products_response.status_code == 200
    created_product = next(item for item in products_response.json() if item["sku"] == "KIWI-WRAP")
    assert created_product["price_cents"] == 8900

    bootstrap_response = client.get("/api/v1/platform/bootstrap-status")
    assert bootstrap_response.status_code == 200
    assert bootstrap_response.json()["counts"]["branches"] == 2
    assert bootstrap_response.json()["counts"]["products"] == 4
    assert bootstrap_response.json()["counts"]["audit_events"] == 3


def test_admin_can_read_inventory_and_record_opening_balance() -> None:
    client = _client_with_seeded_database()

    stock_response = client.get("/api/v1/inventory/stock")
    assert stock_response.status_code == 200
    stock = stock_response.json()
    beef = next(item for item in stock if item["sku"] == "INV-BEEF")
    assert beef["quantity_on_hand"] == 25000
    assert beef["unit_code"] == "g"
    assert beef["warehouse_name"] == "Almacen Sucursal Piloto"

    recipes_response = client.get("/api/v1/recipes")
    assert recipes_response.status_code == 200
    burger_recipe = next(
        item for item in recipes_response.json() if item["product_sku"] == "KIWI-BURGER"
    )
    assert burger_recipe["version"] == 1
    assert any(component["item_sku"] == "INV-BEEF" for component in burger_recipe["components"])

    movement_response = client.post(
        "/api/v1/inventory/opening-balances",
        json={
            "item_id": beef["id"],
            "quantity_base_units": 5000,
            "reason": "Conteo inicial adicional",
        },
    )
    assert movement_response.status_code == 200
    movement = movement_response.json()
    assert movement["movement_type"] == "OPENING_BALANCE"
    assert movement["quantity_delta"] == 5000
    assert movement["item_name"] == "Carne molida"

    invalid_movement = client.post(
        "/api/v1/inventory/opening-balances",
        json={"item_id": beef["id"], "quantity_base_units": 0},
    )
    assert invalid_movement.status_code == 409
    assert invalid_movement.json()["detail"]["code"] == "invalid_inventory_quantity"

    updated_stock_response = client.get("/api/v1/inventory/stock")
    assert updated_stock_response.status_code == 200
    updated_beef = next(item for item in updated_stock_response.json() if item["sku"] == "INV-BEEF")
    assert updated_beef["quantity_on_hand"] == 30000

    kardex_response = client.get(f"/api/v1/inventory/kardex?item_id={beef['id']}")
    assert kardex_response.status_code == 200
    kardex = kardex_response.json()
    assert [item["quantity_delta"] for item in kardex] == [5000, 25000]
    assert kardex[0]["reason"] == "Conteo inicial adicional"

    bootstrap_response = client.get("/api/v1/platform/bootstrap-status")
    assert bootstrap_response.status_code == 200
    assert bootstrap_response.json()["counts"]["inventory_items"] == 4
    assert bootstrap_response.json()["counts"]["inventory_movements"] == 5
    assert bootstrap_response.json()["counts"]["audit_events"] == 2


def test_rbac_rejects_inventory_adjustment_without_permission() -> None:
    client = _client_with_seeded_database()

    role_response = client.post("/api/v1/roles", json={"name": "Cajero", "scope": "branch"})
    assert role_response.status_code == 200
    role = role_response.json()

    user_response = client.post(
        "/api/v1/users",
        json={"email": "cajero-rbac@kiwi.local", "display_name": "Cajero RBAC"},
    )
    assert user_response.status_code == 200
    user = user_response.json()

    assignment_response = client.post(
        f"/api/v1/users/{user['id']}/roles",
        json={"role_id": role["id"]},
    )
    assert assignment_response.status_code == 200

    stock_response = client.get("/api/v1/inventory/stock")
    assert stock_response.status_code == 200
    beef = next(item for item in stock_response.json() if item["sku"] == "INV-BEEF")

    denied_response = client.post(
        "/api/v1/inventory/opening-balances",
        headers={"X-Actor-User-Id": user["id"]},
        json={
            "item_id": beef["id"],
            "quantity_base_units": 1000,
            "reason": "Intento no autorizado",
        },
    )
    assert denied_response.status_code == 403
    assert denied_response.json()["detail"]["code"] == "permission_denied"

    updated_stock_response = client.get("/api/v1/inventory/stock")
    assert updated_stock_response.status_code == 200
    updated_beef = next(item for item in updated_stock_response.json() if item["sku"] == "INV-BEEF")
    assert updated_beef["quantity_on_hand"] == 25000

    admin_response = client.post(
        "/api/v1/inventory/opening-balances",
        json={
            "item_id": beef["id"],
            "quantity_base_units": 1000,
            "reason": "Ajuste autorizado",
        },
    )
    assert admin_response.status_code == 200

    bootstrap_response = client.get("/api/v1/platform/bootstrap-status")
    assert bootstrap_response.status_code == 200
    assert bootstrap_response.json()["counts"]["inventory_movements"] == 5
    assert bootstrap_response.json()["counts"]["audit_events"] == 6


def test_admin_can_create_user_role_and_assignment() -> None:
    client = _client_with_seeded_database()

    role_response = client.post("/api/v1/roles", json={"name": "Cajero", "scope": "branch"})
    assert role_response.status_code == 200
    role = role_response.json()
    assert role["name"] == "Cajero"
    assert role["scope"] == "branch"

    duplicate_role = client.post("/api/v1/roles", json={"name": "Cajero", "scope": "branch"})
    assert duplicate_role.status_code == 409
    assert duplicate_role.json()["detail"]["code"] == "role_already_exists"

    user_response = client.post(
        "/api/v1/users",
        json={"email": "cajero@kiwi.local", "display_name": "Cajero Piloto"},
    )
    assert user_response.status_code == 200
    user = user_response.json()
    assert user["email"] == "cajero@kiwi.local"
    assert user["status"] == "invited"

    assignment_response = client.post(
        f"/api/v1/users/{user['id']}/roles",
        json={"role_id": role["id"]},
    )
    assert assignment_response.status_code == 200
    assert assignment_response.json()["branch_id"] == "018f6f73-2d0a-74f0-8f1c-000000000003"

    users_response = client.get("/api/v1/users")
    assert users_response.status_code == 200
    created_user = next(item for item in users_response.json() if item["id"] == user["id"])
    assert created_user["roles"][0]["role_name"] == "Cajero"

    roles_response = client.get("/api/v1/roles")
    assert roles_response.status_code == 200
    assert any(item["name"] == "Cajero" for item in roles_response.json())

    bootstrap_response = client.get("/api/v1/platform/bootstrap-status")
    assert bootstrap_response.status_code == 200
    assert bootstrap_response.json()["counts"]["audit_events"] == 4


def test_cash_order_and_kds_flow() -> None:
    client = _client_with_seeded_database()

    current_response = client.get("/api/v1/cash-shifts/current")
    assert current_response.status_code == 200
    assert current_response.json()["cash_shift"] is None

    order_without_shift = client.post(
        "/api/v1/orders",
        json={
            "lines": [
                {"product_id": "018f6f73-2d0a-74f0-8f1c-000000000111", "quantity": 1}
            ]
        },
    )
    assert order_without_shift.status_code == 409
    assert order_without_shift.json()["detail"]["code"] == "cash_shift_required"

    open_response = client.post("/api/v1/cash-shifts/open", json={"opening_cash_cents": 50000})
    assert open_response.status_code == 200
    assert open_response.json()["status"] == "OPEN"

    duplicate_open = client.post("/api/v1/cash-shifts/open", json={"opening_cash_cents": 50000})
    assert duplicate_open.status_code == 409
    assert duplicate_open.json()["detail"]["code"] == "cash_shift_already_open"

    order_response = client.post(
        "/api/v1/orders",
        json={
            "lines": [
                {"product_id": "018f6f73-2d0a-74f0-8f1c-000000000111", "quantity": 2}
            ]
        },
    )
    assert order_response.status_code == 200
    order_payload = order_response.json()
    assert order_payload["status"] == "ACCEPTED"
    assert order_payload["folio"] == "PILOTO-000001"
    assert order_payload["total_cents"] == 19000
    assert order_payload["lines"][0]["product_name"] == "Hamburguesa Kiwi"
    assert order_payload["production_tasks"][0]["status"] == "PENDING"

    reserved_stock_response = client.get("/api/v1/inventory/stock")
    assert reserved_stock_response.status_code == 200
    reserved_stock = reserved_stock_response.json()
    reserved_beef = next(item for item in reserved_stock if item["sku"] == "INV-BEEF")
    reserved_bun = next(item for item in reserved_stock if item["sku"] == "INV-BUN")
    assert reserved_beef["quantity_on_hand"] == 24760
    assert reserved_bun["quantity_on_hand"] == 118

    reservation_kardex = client.get(f"/api/v1/inventory/kardex?item_id={reserved_beef['id']}")
    assert reservation_kardex.status_code == 200
    assert any(
        item["movement_type"] == "SALE_RESERVATION" and item["quantity_delta"] == -240
        for item in reservation_kardex.json()
    )

    tasks_response = client.get("/api/v1/kds/tasks")
    assert tasks_response.status_code == 200
    task = tasks_response.json()[0]
    assert task["folio"] == "PILOTO-000001"
    assert task["status"] == "PENDING"

    started_response = client.post(
        f"/api/v1/kds/tasks/{task['id']}/transition",
        json={"status": "IN_PROGRESS"},
    )
    assert started_response.status_code == 200
    assert started_response.json()["status"] == "IN_PROGRESS"

    completed_response = client.post(
        f"/api/v1/kds/tasks/{task['id']}/transition",
        json={"status": "COMPLETED"},
    )
    assert completed_response.status_code == 200
    assert completed_response.json()["status"] == "COMPLETED"

    consumed_stock_response = client.get("/api/v1/inventory/stock")
    assert consumed_stock_response.status_code == 200
    consumed_beef = next(
        item for item in consumed_stock_response.json() if item["sku"] == "INV-BEEF"
    )
    assert consumed_beef["quantity_on_hand"] == 24760

    consumption_kardex = client.get(f"/api/v1/inventory/kardex?item_id={reserved_beef['id']}")
    assert consumption_kardex.status_code == 200
    beef_movements = consumption_kardex.json()
    assert any(
        item["movement_type"] == "RESERVATION_RELEASE" and item["quantity_delta"] == 240
        for item in beef_movements
    )
    assert any(
        item["movement_type"] == "SALE_CONSUMPTION" and item["quantity_delta"] == -240
        for item in beef_movements
    )

    invalid_transition = client.post(
        f"/api/v1/kds/tasks/{task['id']}/transition",
        json={"status": "PENDING"},
    )
    assert invalid_transition.status_code == 409
    assert invalid_transition.json()["detail"]["code"] == "invalid_task_transition"

    close_response = client.post("/api/v1/cash-shifts/close")
    assert close_response.status_code == 200
    assert close_response.json()["status"] == "CLOSED"


def test_order_cancellation_releases_reserved_inventory_before_production() -> None:
    client = _client_with_seeded_database()

    open_response = client.post("/api/v1/cash-shifts/open", json={"opening_cash_cents": 50000})
    assert open_response.status_code == 200

    order_response = client.post(
        "/api/v1/orders",
        json={
            "lines": [
                {"product_id": "018f6f73-2d0a-74f0-8f1c-000000000111", "quantity": 1}
            ]
        },
    )
    assert order_response.status_code == 200
    order = order_response.json()

    reserved_stock_response = client.get("/api/v1/inventory/stock")
    assert reserved_stock_response.status_code == 200
    reserved_beef = next(
        item for item in reserved_stock_response.json() if item["sku"] == "INV-BEEF"
    )
    assert reserved_beef["quantity_on_hand"] == 24880

    cancel_response = client.post(
        f"/api/v1/orders/{order['id']}/cancel",
        json={"reason": "Cliente cancela antes de cocina"},
    )
    assert cancel_response.status_code == 200
    cancelled = cancel_response.json()
    assert cancelled["status"] == "CANCELLED"
    assert cancelled["production_tasks"][0]["status"] == "CANCELLED"

    stock_response = client.get("/api/v1/inventory/stock")
    assert stock_response.status_code == 200
    beef = next(item for item in stock_response.json() if item["sku"] == "INV-BEEF")
    assert beef["quantity_on_hand"] == 25000

    kardex_response = client.get(f"/api/v1/inventory/kardex?item_id={beef['id']}")
    assert kardex_response.status_code == 200
    beef_movements = kardex_response.json()
    assert any(
        item["movement_type"] == "SALE_RESERVATION" and item["quantity_delta"] == -120
        for item in beef_movements
    )
    assert any(
        item["movement_type"] == "RESERVATION_RELEASE" and item["quantity_delta"] == 120
        for item in beef_movements
    )

    payment_response = client.post(
        f"/api/v1/orders/{order['id']}/payments",
        json={"amount_cents": 9500, "method": "cash"},
    )
    assert payment_response.status_code == 409
    assert payment_response.json()["detail"]["code"] == "order_cancelled"

    orders_response = client.get("/api/v1/orders")
    assert orders_response.status_code == 200
    assert orders_response.json()[0]["status"] == "CANCELLED"

    bootstrap_response = client.get("/api/v1/platform/bootstrap-status")
    assert bootstrap_response.status_code == 200
    assert bootstrap_response.json()["counts"]["inventory_movements"] == 8
    assert bootstrap_response.json()["counts"]["audit_events"] == 4


def test_order_cancellation_is_rejected_while_production_is_in_progress() -> None:
    client = _client_with_seeded_database()

    open_response = client.post("/api/v1/cash-shifts/open", json={"opening_cash_cents": 50000})
    assert open_response.status_code == 200

    order_response = client.post(
        "/api/v1/orders",
        json={
            "lines": [
                {"product_id": "018f6f73-2d0a-74f0-8f1c-000000000111", "quantity": 1}
            ]
        },
    )
    assert order_response.status_code == 200
    order = order_response.json()

    task_id = order["production_tasks"][0]["id"]
    started_response = client.post(
        f"/api/v1/kds/tasks/{task_id}/transition",
        json={"status": "IN_PROGRESS"},
    )
    assert started_response.status_code == 200

    cancel_response = client.post(
        f"/api/v1/orders/{order['id']}/cancel",
        json={"reason": "Demasiado tarde"},
    )
    assert cancel_response.status_code == 409
    assert cancel_response.json()["detail"]["code"] == "production_in_progress"


def test_post_production_cancellation_records_waste_without_restocking() -> None:
    client = _client_with_seeded_database()

    open_response = client.post("/api/v1/cash-shifts/open", json={"opening_cash_cents": 50000})
    assert open_response.status_code == 200

    order_response = client.post(
        "/api/v1/orders",
        json={
            "lines": [
                {"product_id": "018f6f73-2d0a-74f0-8f1c-000000000111", "quantity": 1}
            ]
        },
    )
    assert order_response.status_code == 200
    order = order_response.json()
    task_id = order["production_tasks"][0]["id"]

    started_response = client.post(
        f"/api/v1/kds/tasks/{task_id}/transition",
        json={"status": "IN_PROGRESS"},
    )
    assert started_response.status_code == 200
    completed_response = client.post(
        f"/api/v1/kds/tasks/{task_id}/transition",
        json={"status": "COMPLETED"},
    )
    assert completed_response.status_code == 200

    missing_classification = client.post(
        f"/api/v1/orders/{order['id']}/cancel",
        json={"reason": "Cliente cancela pedido producido"},
    )
    assert missing_classification.status_code == 409
    assert missing_classification.json()["detail"]["code"] == "cancellation_classification_required"

    cancel_response = client.post(
        f"/api/v1/orders/{order['id']}/cancel",
        json={"reason": "Cliente cancela pedido producido", "classification": "waste"},
    )
    assert cancel_response.status_code == 200
    cancelled = cancel_response.json()
    assert cancelled["status"] == "CANCELLED"
    assert cancelled["classification"] == "waste"
    assert cancelled["production_tasks"][0]["status"] == "COMPLETED"

    stock_response = client.get("/api/v1/inventory/stock")
    assert stock_response.status_code == 200
    beef = next(item for item in stock_response.json() if item["sku"] == "INV-BEEF")
    assert beef["quantity_on_hand"] == 24880

    kardex_response = client.get(f"/api/v1/inventory/kardex?item_id={beef['id']}")
    assert kardex_response.status_code == 200
    beef_movements = kardex_response.json()
    assert any(
        item["movement_type"] == "SALE_CONSUMPTION" and item["quantity_delta"] == -120
        for item in beef_movements
    )
    assert any(
        item["movement_type"] == "WASTE" and item["quantity_delta"] == 0 for item in beef_movements
    )

    payment_response = client.post(
        f"/api/v1/orders/{order['id']}/payments",
        json={"amount_cents": 9500, "method": "cash"},
    )
    assert payment_response.status_code == 409
    assert payment_response.json()["detail"]["code"] == "order_cancelled"

    bootstrap_response = client.get("/api/v1/platform/bootstrap-status")
    assert bootstrap_response.status_code == 200
    assert bootstrap_response.json()["counts"]["inventory_movements"] == 12
    assert bootstrap_response.json()["counts"]["audit_events"] == 6


def test_post_production_cancellation_records_recovery_and_restocks() -> None:
    client = _client_with_seeded_database()

    open_response = client.post("/api/v1/cash-shifts/open", json={"opening_cash_cents": 50000})
    assert open_response.status_code == 200

    order_response = client.post(
        "/api/v1/orders",
        json={
            "lines": [
                {"product_id": "018f6f73-2d0a-74f0-8f1c-000000000111", "quantity": 1}
            ]
        },
    )
    assert order_response.status_code == 200
    order = order_response.json()
    task_id = order["production_tasks"][0]["id"]

    started_response = client.post(
        f"/api/v1/kds/tasks/{task_id}/transition",
        json={"status": "IN_PROGRESS"},
    )
    assert started_response.status_code == 200
    completed_response = client.post(
        f"/api/v1/kds/tasks/{task_id}/transition",
        json={"status": "COMPLETED"},
    )
    assert completed_response.status_code == 200

    cancel_response = client.post(
        f"/api/v1/orders/{order['id']}/cancel",
        json={"reason": "Produccion recuperable", "classification": "recovery"},
    )
    assert cancel_response.status_code == 200
    cancelled = cancel_response.json()
    assert cancelled["status"] == "CANCELLED"
    assert cancelled["classification"] == "recovery"

    stock_response = client.get("/api/v1/inventory/stock")
    assert stock_response.status_code == 200
    beef = next(item for item in stock_response.json() if item["sku"] == "INV-BEEF")
    assert beef["quantity_on_hand"] == 25000

    kardex_response = client.get(f"/api/v1/inventory/kardex?item_id={beef['id']}")
    assert kardex_response.status_code == 200
    beef_movements = kardex_response.json()
    assert any(
        item["movement_type"] == "RECOVERY" and item["quantity_delta"] == 120
        for item in beef_movements
    )


def test_payment_cut_and_print_flow() -> None:
    client = _client_with_seeded_database()

    open_response = client.post("/api/v1/cash-shifts/open", json={"opening_cash_cents": 50000})
    assert open_response.status_code == 200

    order_response = client.post(
        "/api/v1/orders",
        json={
            "lines": [
                {"product_id": "018f6f73-2d0a-74f0-8f1c-000000000111", "quantity": 1}
            ]
        },
    )
    assert order_response.status_code == 200
    order = order_response.json()

    mismatch_payment = client.post(
        f"/api/v1/orders/{order['id']}/payments",
        json={"amount_cents": 9400, "method": "cash"},
    )
    assert mismatch_payment.status_code == 409
    assert mismatch_payment.json()["detail"]["code"] == "payment_total_mismatch"

    payment_response = client.post(
        f"/api/v1/orders/{order['id']}/payments",
        json={"amount_cents": 9500, "method": "cash"},
    )
    assert payment_response.status_code == 200
    payment = payment_response.json()
    assert payment["status"] == "CONFIRMED"
    assert payment["order_status"] == "CLOSED"
    assert [job["job_type"] for job in payment["print_jobs"]] == ["ticket", "kitchen"]

    duplicate_payment = client.post(
        f"/api/v1/orders/{order['id']}/payments",
        json={"amount_cents": 9500, "method": "cash"},
    )
    assert duplicate_payment.status_code == 409
    assert duplicate_payment.json()["detail"]["code"] == "order_already_closed"

    orders_response = client.get("/api/v1/orders")
    assert orders_response.status_code == 200
    assert orders_response.json()[0]["status"] == "CLOSED"

    payments_response = client.get("/api/v1/payments")
    assert payments_response.status_code == 200
    assert payments_response.json()[0]["amount_cents"] == 9500

    print_jobs_response = client.get("/api/v1/print-jobs")
    assert print_jobs_response.status_code == 200
    print_jobs = print_jobs_response.json()
    assert len(print_jobs) == 2
    assert {job["status"] for job in print_jobs} == {"PENDING"}

    retry_response = client.post(f"/api/v1/print-jobs/{print_jobs[0]['id']}/retry")
    assert retry_response.status_code == 200
    assert retry_response.json()["status"] == "PRINTED"
    assert retry_response.json()["attempts"] == 1

    summary_response = client.get("/api/v1/cash-shifts/summary")
    assert summary_response.status_code == 200
    summary = summary_response.json()["summary"]
    assert summary["sales_total_cents"] == 9500
    assert summary["payment_total_cents"] == 9500
    assert summary["cash_payment_total_cents"] == 9500
    assert summary["expected_cash_cents"] == 59500

    close_response = client.post(
        "/api/v1/cash-shifts/close",
        json={"counted_cash_cents": 59000},
    )
    assert close_response.status_code == 200
    cut = close_response.json()["cut"]
    assert cut["expected_cash_cents"] == 59500
    assert cut["counted_cash_cents"] == 59000
    assert cut["difference_cents"] == -500


def test_sync_command_is_confirmed_idempotently() -> None:
    client = _client_with_seeded_database()
    command = {
        "schema_version": "1.0",
        "command_id": "018f6f73-2d0a-74f0-8f1c-000000000301",
        "idempotency_key": "PILOTO-CAJA-01-000001",
        "organization_id": "018f6f73-2d0a-74f0-8f1c-000000000001",
        "branch_id": "018f6f73-2d0a-74f0-8f1c-000000000003",
        "source_device_id": "018f6f73-2d0a-74f0-8f1c-000000000401",
        "command_type": "local_order.closed",
        "occurred_at": "2026-07-07T18:00:00Z",
        "payload": {"folio": "PILOTO-LOCAL-000001", "total_cents": 9500},
    }

    first_response = client.post("/api/v1/sync/commands", json=command)
    assert first_response.status_code == 200
    first = first_response.json()
    assert first["status"] == "CONFIRMED"
    assert first["checkpoint"] == 1
    assert first["replayed"] is False
    assert first["event"]["event_type"] == "local_order.closed.confirmed"

    retry_response = client.post("/api/v1/sync/commands", json=command)
    assert retry_response.status_code == 200
    retry = retry_response.json()
    assert retry["checkpoint"] == 1
    assert retry["command"]["id"] == first["command"]["id"]
    assert retry["event"]["id"] == first["event"]["id"]
    assert retry["replayed"] is True

    events_response = client.get("/api/v1/sync/events")
    assert events_response.status_code == 200
    events = events_response.json()
    assert len(events) == 1
    assert events[0]["checkpoint"] == 1

    after_checkpoint_response = client.get("/api/v1/sync/events?after_checkpoint=1")
    assert after_checkpoint_response.status_code == 200
    assert after_checkpoint_response.json() == []

    second_command = {
        **command,
        "command_id": "018f6f73-2d0a-74f0-8f1c-000000000302",
        "idempotency_key": "PILOTO-CAJA-01-000002",
        "payload": {"folio": "PILOTO-LOCAL-000002", "total_cents": 4500},
    }
    second_response = client.post("/api/v1/sync/commands", json=second_command)
    assert second_response.status_code == 200
    assert second_response.json()["checkpoint"] == 2

    pending_events_response = client.get("/api/v1/sync/events?after_checkpoint=1")
    assert pending_events_response.status_code == 200
    pending_events = pending_events_response.json()
    assert len(pending_events) == 1
    assert pending_events[0]["checkpoint"] == 2

    status_response = client.get("/api/v1/sync/status")
    assert status_response.status_code == 200
    status = status_response.json()
    assert status["branch_id"] == "018f6f73-2d0a-74f0-8f1c-000000000003"
    assert status["last_checkpoint"] == 2
    assert status["command_count"] == 2
    assert status["event_count"] == 2


def test_sync_command_rejects_invalid_payload() -> None:
    client = _client_with_seeded_database()

    response = client.post(
        "/api/v1/sync/commands",
        json={"schema_version": "1.0", "payload": {}},
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "invalid_sync_command"


def _client_with_seeded_database() -> TestClient:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)

    with session_factory() as session:
        _seed(session)

    app = create_app()

    def override_session() -> Generator[Session, None, None]:
        with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    return TestClient(app)


def _seed(session: Session) -> None:
    now = datetime(2026, 7, 7, 17, 30, tzinfo=UTC)
    organization_id = "018f6f73-2d0a-74f0-8f1c-000000000001"
    legal_entity_id = "018f6f73-2d0a-74f0-8f1c-000000000002"
    branch_id = "018f6f73-2d0a-74f0-8f1c-000000000003"
    warehouse_id = "018f6f73-2d0a-74f0-8f1c-000000000004"
    role_id = "018f6f73-2d0a-74f0-8f1c-000000000005"
    user_id = "018f6f73-2d0a-74f0-8f1c-000000000006"
    food_category_id = "018f6f73-2d0a-74f0-8f1c-000000000101"
    drink_category_id = "018f6f73-2d0a-74f0-8f1c-000000000102"
    burger_product_id = "018f6f73-2d0a-74f0-8f1c-000000000111"
    fries_product_id = "018f6f73-2d0a-74f0-8f1c-000000000112"
    soda_product_id = "018f6f73-2d0a-74f0-8f1c-000000000113"
    unit_gram_id = "018f6f73-2d0a-74f0-8f1c-000000000301"
    unit_ml_id = "018f6f73-2d0a-74f0-8f1c-000000000302"
    unit_piece_id = "018f6f73-2d0a-74f0-8f1c-000000000303"
    beef_item_id = "018f6f73-2d0a-74f0-8f1c-000000000311"
    bun_item_id = "018f6f73-2d0a-74f0-8f1c-000000000312"
    potato_item_id = "018f6f73-2d0a-74f0-8f1c-000000000313"
    syrup_item_id = "018f6f73-2d0a-74f0-8f1c-000000000314"
    burger_recipe_id = "018f6f73-2d0a-74f0-8f1c-000000000321"
    fries_recipe_id = "018f6f73-2d0a-74f0-8f1c-000000000322"
    soda_recipe_id = "018f6f73-2d0a-74f0-8f1c-000000000323"

    session.execute(
        organizations.insert(),
        [
            {
                "id": organization_id,
                "name": "Kiwi Restaurante",
                "status": "active",
                "created_at": now,
                "updated_at": now,
            }
        ],
    )
    session.execute(
        legal_entities.insert(),
        [
            {
                "id": legal_entity_id,
                "organization_id": organization_id,
                "name": "Kiwi Restaurante - Razon Social Pendiente",
                "tax_id": None,
                "status": "active",
                "created_at": now,
                "updated_at": now,
            }
        ],
    )
    session.execute(
        branches.insert(),
        [
            {
                "id": branch_id,
                "organization_id": organization_id,
                "legal_entity_id": legal_entity_id,
                "name": "Sucursal Piloto",
                "code": "PILOTO",
                "timezone": "America/Chihuahua",
                "status": "active",
                "created_at": now,
                "updated_at": now,
            }
        ],
    )
    session.execute(
        warehouses.insert(),
        [
            {
                "id": warehouse_id,
                "organization_id": organization_id,
                "branch_id": branch_id,
                "name": "Almacen Sucursal Piloto",
                "status": "active",
                "created_at": now,
                "updated_at": now,
            }
        ],
    )
    session.execute(
        roles.insert(),
        [
            {
                "id": role_id,
                "organization_id": organization_id,
                "name": "Administrador corporativo",
                "scope": "organization",
                "created_at": now,
            }
        ],
    )
    session.execute(
        permissions.insert(),
        [
            {
                "id": "018f6f73-2d0a-74f0-8f1c-000000000901",
                "code": "admin.manage",
                "description": "Administrar usuarios y roles",
                "created_at": now,
            },
            {
                "id": "018f6f73-2d0a-74f0-8f1c-000000000902",
                "code": "catalog.manage",
                "description": "Administrar catalogos",
                "created_at": now,
            },
        ],
    )
    session.execute(
        role_permissions.insert(),
        [
            {
                "role_id": role_id,
                "permission_id": "018f6f73-2d0a-74f0-8f1c-000000000901",
            },
            {
                "role_id": role_id,
                "permission_id": "018f6f73-2d0a-74f0-8f1c-000000000902",
            },
        ],
    )
    session.execute(
        users.insert(),
        [
            {
                "id": user_id,
                "organization_id": organization_id,
                "email": "mangoex@gmail.com",
                "display_name": "Miguel Gonzalez",
                "status": "active",
                "created_at": now,
                "updated_at": now,
            }
        ],
    )
    session.execute(
        user_credentials.insert(),
        [
            {
                "user_id": user_id,
                "password_hash": "uLG4WrRginnX-XVp2zegYbfB-chwTzI2M1h328MDiJM",
                "password_salt": "oaj3szcvziQTFhGeTZSDXA",
                "password_algorithm": "pbkdf2_sha256",
                "updated_at": now,
            }
        ],
    )
    session.execute(
        user_roles.insert(),
        [{"user_id": user_id, "role_id": role_id, "branch_id": None}],
    )
    session.execute(
        audit_events.insert(),
        [
            {
                "id": "018f6f73-2d0a-74f0-8f1c-000000000007",
                "organization_id": organization_id,
                "branch_id": branch_id,
                "actor_user_id": user_id,
                "action": "platform.bootstrap_seeded",
                "entity_type": "organization",
                "entity_id": organization_id,
                "payload": {"source": "test"},
                "correlation_id": None,
                "created_at": now,
            }
        ],
    )
    session.execute(
        product_categories.insert(),
        [
            {
                "id": food_category_id,
                "organization_id": organization_id,
                "name": "Comida",
                "display_order": 10,
                "status": "active",
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": drink_category_id,
                "organization_id": organization_id,
                "name": "Bebidas",
                "display_order": 20,
                "status": "active",
                "created_at": now,
                "updated_at": now,
            },
        ],
    )
    session.execute(
        products.insert(),
        [
            {
                "id": burger_product_id,
                "organization_id": organization_id,
                "category_id": food_category_id,
                "name": "Hamburguesa Kiwi",
                "sku": "KIWI-BURGER",
                "description": "Producto semilla para flujo POS.",
                "station": "kitchen",
                "status": "active",
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": fries_product_id,
                "organization_id": organization_id,
                "category_id": food_category_id,
                "name": "Papas",
                "sku": "KIWI-FRIES",
                "description": "Producto semilla para empaque.",
                "station": "kitchen",
                "status": "active",
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": soda_product_id,
                "organization_id": organization_id,
                "category_id": drink_category_id,
                "name": "Refresco",
                "sku": "KIWI-SODA",
                "description": "Producto semilla para bebidas.",
                "station": "drinks",
                "status": "active",
                "created_at": now,
                "updated_at": now,
            },
        ],
    )
    session.execute(
        price_versions.insert(),
        [
            {
                "id": "018f6f73-2d0a-74f0-8f1c-000000000121",
                "organization_id": organization_id,
                "product_id": burger_product_id,
                "price_cents": 9500,
                "currency": "MXN",
                "valid_from": now,
                "valid_to": None,
                "created_at": now,
            },
            {
                "id": "018f6f73-2d0a-74f0-8f1c-000000000122",
                "organization_id": organization_id,
                "product_id": fries_product_id,
                "price_cents": 4500,
                "currency": "MXN",
                "valid_from": now,
                "valid_to": None,
                "created_at": now,
            },
            {
                "id": "018f6f73-2d0a-74f0-8f1c-000000000123",
                "organization_id": organization_id,
                "product_id": soda_product_id,
                "price_cents": 3000,
                "currency": "MXN",
                "valid_from": now,
                "valid_to": None,
                "created_at": now,
            },
        ],
    )
    session.execute(
        branch_product_availability.insert(),
        [
            {
                "branch_id": branch_id,
                "product_id": burger_product_id,
                "is_available": True,
                "updated_at": now,
            },
            {
                "branch_id": branch_id,
                "product_id": fries_product_id,
                "is_available": True,
                "updated_at": now,
            },
            {
                "branch_id": branch_id,
                "product_id": soda_product_id,
                "is_available": True,
                "updated_at": now,
            },
        ],
    )
    session.execute(
        inventory_units.insert(),
        [
            {
                "id": unit_gram_id,
                "organization_id": organization_id,
                "code": "g",
                "name": "Gramo",
                "precision_scale": 0,
                "created_at": now,
            },
            {
                "id": unit_ml_id,
                "organization_id": organization_id,
                "code": "ml",
                "name": "Mililitro",
                "precision_scale": 0,
                "created_at": now,
            },
            {
                "id": unit_piece_id,
                "organization_id": organization_id,
                "code": "pz",
                "name": "Pieza",
                "precision_scale": 0,
                "created_at": now,
            },
        ],
    )
    session.execute(
        inventory_items.insert(),
        [
            {
                "id": beef_item_id,
                "organization_id": organization_id,
                "name": "Carne molida",
                "sku": "INV-BEEF",
                "base_unit_id": unit_gram_id,
                "item_type": "ingredient",
                "status": "active",
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": bun_item_id,
                "organization_id": organization_id,
                "name": "Pan brioche",
                "sku": "INV-BUN",
                "base_unit_id": unit_piece_id,
                "item_type": "ingredient",
                "status": "active",
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": potato_item_id,
                "organization_id": organization_id,
                "name": "Papa blanca",
                "sku": "INV-POTATO",
                "base_unit_id": unit_gram_id,
                "item_type": "ingredient",
                "status": "active",
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": syrup_item_id,
                "organization_id": organization_id,
                "name": "Jarabe refresco",
                "sku": "INV-SYRUP",
                "base_unit_id": unit_ml_id,
                "item_type": "ingredient",
                "status": "active",
                "created_at": now,
                "updated_at": now,
            },
        ],
    )
    session.execute(
        recipes.insert(),
        [
            {
                "id": burger_recipe_id,
                "organization_id": organization_id,
                "product_id": burger_product_id,
                "version": 1,
                "status": "active",
                "yield_quantity": 1,
                "yield_unit_id": unit_piece_id,
                "created_at": now,
            },
            {
                "id": fries_recipe_id,
                "organization_id": organization_id,
                "product_id": fries_product_id,
                "version": 1,
                "status": "active",
                "yield_quantity": 1,
                "yield_unit_id": unit_piece_id,
                "created_at": now,
            },
            {
                "id": soda_recipe_id,
                "organization_id": organization_id,
                "product_id": soda_product_id,
                "version": 1,
                "status": "active",
                "yield_quantity": 1,
                "yield_unit_id": unit_piece_id,
                "created_at": now,
            },
        ],
    )
    session.execute(
        recipe_components.insert(),
        [
            {
                "recipe_id": burger_recipe_id,
                "item_id": beef_item_id,
                "quantity_base_units": 120,
            },
            {
                "recipe_id": burger_recipe_id,
                "item_id": bun_item_id,
                "quantity_base_units": 1,
            },
            {
                "recipe_id": fries_recipe_id,
                "item_id": potato_item_id,
                "quantity_base_units": 180,
            },
            {
                "recipe_id": soda_recipe_id,
                "item_id": syrup_item_id,
                "quantity_base_units": 80,
            },
        ],
    )
    session.execute(
        inventory_movements.insert(),
        [
            {
                "id": "018f6f73-2d0a-74f0-8f1c-000000000331",
                "organization_id": organization_id,
                "branch_id": branch_id,
                "warehouse_id": warehouse_id,
                "item_id": beef_item_id,
                "movement_type": "OPENING_BALANCE",
                "quantity_delta": 25000,
                "unit_id": unit_gram_id,
                "reason": "Saldo inicial semilla",
                "source_type": "test",
                "source_id": None,
                "created_at": now,
            },
            {
                "id": "018f6f73-2d0a-74f0-8f1c-000000000332",
                "organization_id": organization_id,
                "branch_id": branch_id,
                "warehouse_id": warehouse_id,
                "item_id": bun_item_id,
                "movement_type": "OPENING_BALANCE",
                "quantity_delta": 120,
                "unit_id": unit_piece_id,
                "reason": "Saldo inicial semilla",
                "source_type": "test",
                "source_id": None,
                "created_at": now,
            },
            {
                "id": "018f6f73-2d0a-74f0-8f1c-000000000333",
                "organization_id": organization_id,
                "branch_id": branch_id,
                "warehouse_id": warehouse_id,
                "item_id": potato_item_id,
                "movement_type": "OPENING_BALANCE",
                "quantity_delta": 35000,
                "unit_id": unit_gram_id,
                "reason": "Saldo inicial semilla",
                "source_type": "test",
                "source_id": None,
                "created_at": now,
            },
            {
                "id": "018f6f73-2d0a-74f0-8f1c-000000000334",
                "organization_id": organization_id,
                "branch_id": branch_id,
                "warehouse_id": warehouse_id,
                "item_id": syrup_item_id,
                "movement_type": "OPENING_BALANCE",
                "quantity_delta": 10000,
                "unit_id": unit_ml_id,
                "reason": "Saldo inicial semilla",
                "source_type": "test",
                "source_id": None,
                "created_at": now,
            },
        ],
    )
    session.commit()


def test_product_image_url_crud() -> None:
    client = _client_with_seeded_database()

    # 1. Get products and check image_url is present (should be None or string)
    get_res = client.get("/api/v1/catalog/products")
    assert get_res.status_code == 200
    products = get_res.json()
    assert len(products) > 0
    # The seeded products don't have image_url, so it should be None/null
    assert all("image_url" in p for p in products)
    
    # 2. Update a product with an image_url
    product_id = products[0]["id"]
    update_res = client.put(
        f"/api/v1/catalog/products/{product_id}",
        json={
            "name": products[0]["name"],
            "sku": products[0]["sku"],
            "price_cents": products[0]["price_cents"],
            "image_url": "https://example.com/test-image.png"
        }
    )
    assert update_res.status_code == 200
    assert update_res.json()["image_url"] == "https://example.com/test-image.png"

    # Verify it persists in subsequent GET request
    get_res2 = client.get("/api/v1/catalog/products")
    updated_product = next(p for p in get_res2.json() if p["id"] == product_id)
    assert updated_product["image_url"] == "https://example.com/test-image.png"


def test_update_user_profile() -> None:
    client = _client_with_seeded_database()

    # 1. Login to get token
    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": "mangoex@gmail.com", "password": "superadmin-test-password"},
    )
    assert login_res.status_code == 200
    token = login_res.json()["token"]
    user_id = login_res.json()["user"]["id"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Update display name and email
    update_res = client.put(
        f"/api/v1/users/{user_id}",
        headers=headers,
        json={
            "display_name": "Miguel G. Espino",
            "email": "mangoex@gmail.com",
        }
    )
    assert update_res.status_code == 200
    assert update_res.json()["display_name"] == "Miguel G. Espino"

