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
    business_units,
    cash_shifts,
    inventory_items,
    inventory_movements,
    inventory_units,
    legal_entities,
    metadata,
    orders,
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
from restaurant_os.operations import _next_folio
from restaurant_os.platform_data import list_catalog_products
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

UTC = timezone.utc
ADMIN_USER_ID = "018f6f73-2d0a-74f0-8f1c-000000000006"
BRANCH_ID = "018f6f73-2d0a-74f0-8f1c-000000000003"


def _admin_headers() -> dict[str, str]:
    return {"X-Actor-User-Id": ADMIN_USER_ID}


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


def test_admin_creates_business_unit_and_assigns_new_branch() -> None:
    client = _client_with_seeded_database()
    legal_entity_id = "018f6f73-2d0a-74f0-8f1c-000000000002"

    unit_response = client.post(
        "/api/v1/business-units",
        headers=_admin_headers(),
        json={
            "name": "Unidad Norte",
            "code": "NORTE",
            "unit_type": "restaurant",
            "legal_entity_id": legal_entity_id,
        },
    )
    assert unit_response.status_code == 200
    business_unit = unit_response.json()
    assert business_unit["code"] == "NORTE"

    branch_response = client.post(
        "/api/v1/branches",
        headers=_admin_headers(),
        json={
            "name": "Sucursal Norte",
            "code": "SUC-NORTE",
            "business_unit_id": business_unit["id"],
        },
    )
    assert branch_response.status_code == 200
    assert branch_response.json()["business_unit_id"] == business_unit["id"]

    branches_response = client.get("/api/v1/branches", headers=_admin_headers())
    assert branches_response.status_code == 200
    north = next(row for row in branches_response.json() if row["code"] == "SUC-NORTE")
    assert north["business_unit_name"] == "Unidad Norte"
    assert north["legal_entity_name"] == "Kiwi Restaurante - Razon Social Pendiente"


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

    organizations_response = client.get("/api/v1/organizations", headers=_admin_headers())
    branches_response = client.get("/api/v1/branches", headers=_admin_headers())

    assert organizations_response.status_code == 200
    assert branches_response.status_code == 200
    assert organizations_response.json()[0]["name"] == "Kiwi Restaurante"
    assert branches_response.json()[0]["warehouse_name"] == "Almacen Sucursal Piloto"


def test_catalog_products_are_listed_with_prices_and_availability() -> None:
    client = _client_with_seeded_database()

    response = client.get("/api/v1/catalog/products", headers=_admin_headers())

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


def test_catalog_inherits_branch_availability_and_keeps_products_without_price_visible() -> None:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    metadata.create_all(engine)
    with Session(engine) as session:
        _seed(session)
        product_id = (
            session.execute(products.select().where(products.c.sku == "KIWI-BURGER"))
            .mappings()
            .one()["id"]
        )
        session.execute(
            branch_product_availability.delete().where(
                branch_product_availability.c.branch_id == BRANCH_ID,
                branch_product_availability.c.product_id == product_id,
            )
        )
        session.commit()

        inherited = list_catalog_products(session, BRANCH_ID)
        assert any(item["id"] == product_id and item["is_available"] for item in inherited)

        session.execute(
            branch_product_availability.insert().values(
                branch_id=BRANCH_ID,
                product_id=product_id,
                is_available=False,
                updated_at=datetime.now(UTC),
            )
        )
        session.commit()
        unavailable = list_catalog_products(session, BRANCH_ID)
        assert all(item["id"] != product_id for item in unavailable)

        session.execute(price_versions.delete().where(price_versions.c.product_id == product_id))
        session.execute(
            branch_product_availability.delete().where(
                branch_product_availability.c.product_id == product_id
            )
        )
        session.commit()
        incomplete = list_catalog_products(session)
        product = next(item for item in incomplete if item["id"] == product_id)
        assert product["price_cents"] is None


def test_admin_can_create_branch_and_product_catalog_entries() -> None:
    client = _client_with_seeded_database()

    branch_response = client.post(
        "/api/v1/branches",
        headers=_admin_headers(),
        json={"name": "Sucursal Norte", "code": "norte"},
    )
    assert branch_response.status_code == 200
    branch = branch_response.json()
    assert branch["name"] == "Sucursal Norte"
    assert branch["code"] == "NORTE"
    assert branch["warehouse"]["name"] == "Almacen Sucursal Norte"

    duplicate_branch = client.post(
        "/api/v1/branches",
        headers=_admin_headers(),
        json={"name": "Sucursal Norte Bis", "code": "NORTE"},
    )
    assert duplicate_branch.status_code == 409
    assert duplicate_branch.json()["detail"]["code"] == "branch_already_exists"

    product_response = client.post(
        "/api/v1/catalog/products",
        headers=_admin_headers(),
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
        headers=_admin_headers(),
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

    branches_response = client.get("/api/v1/branches", headers=_admin_headers())
    assert branches_response.status_code == 200
    created_branch = next(item for item in branches_response.json() if item["code"] == "NORTE")
    assert created_branch["warehouse_name"] == "Almacen Sucursal Norte"

    products_response = client.get("/api/v1/catalog/products", headers=_admin_headers())
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

    stock_response = client.get("/api/v1/inventory/stock", headers=_admin_headers())
    assert stock_response.status_code == 200
    stock = stock_response.json()
    beef = next(item for item in stock if item["sku"] == "INV-BEEF")
    assert beef["quantity_on_hand"] == 25000
    assert beef["unit_code"] == "g"
    assert beef["branch_id"] == BRANCH_ID
    assert beef["warehouse_name"] == "Almacen Sucursal Piloto"

    recipes_response = client.get("/api/v1/recipes", headers=_admin_headers())
    assert recipes_response.status_code == 200
    burger_recipe = next(
        item for item in recipes_response.json() if item["product_sku"] == "KIWI-BURGER"
    )
    assert burger_recipe["version"] == 1
    assert any(component["item_sku"] == "INV-BEEF" for component in burger_recipe["components"])

    movement_response = client.post(
        "/api/v1/inventory/opening-balances",
        headers=_admin_headers(),
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
        headers=_admin_headers(),
        json={"item_id": beef["id"], "quantity_base_units": 0},
    )
    assert invalid_movement.status_code == 409
    assert invalid_movement.json()["detail"]["code"] == "invalid_inventory_quantity"

    updated_stock_response = client.get(
        "/api/v1/inventory/stock", headers=_admin_headers()
    )
    assert updated_stock_response.status_code == 200
    updated_beef = next(item for item in updated_stock_response.json() if item["sku"] == "INV-BEEF")
    assert updated_beef["quantity_on_hand"] == 30000

    kardex_response = client.get(
        f"/api/v1/inventory/kardex?item_id={beef['id']}", headers=_admin_headers()
    )
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

    role_response = client.post(
        "/api/v1/roles", headers=_admin_headers(), json={"name": "Cajero", "scope": "branch"}
    )
    assert role_response.status_code == 200
    role = role_response.json()

    user_response = client.post(
        "/api/v1/users",
        headers=_admin_headers(),
        json={
            "email": "cajero-rbac@kiwi.local",
            "display_name": "Cajero RBAC",
            "password": "Temporal123+",
        },
    )
    assert user_response.status_code == 200
    user = user_response.json()

    assignment_response = client.post(
        f"/api/v1/users/{user['id']}/roles",
        headers=_admin_headers(),
        json={"role_id": role["id"]},
    )
    assert assignment_response.status_code == 200

    stock_response = client.get("/api/v1/inventory/stock", headers=_admin_headers())
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

    updated_stock_response = client.get(
        "/api/v1/inventory/stock", headers=_admin_headers()
    )
    assert updated_stock_response.status_code == 200
    updated_beef = next(item for item in updated_stock_response.json() if item["sku"] == "INV-BEEF")
    assert updated_beef["quantity_on_hand"] == 25000

    admin_response = client.post(
        "/api/v1/inventory/opening-balances",
        headers=_admin_headers(),
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


def test_supplier_contacts_and_purchase_presentation_do_not_change_inventory_cost() -> None:
    client = _client_with_seeded_database()
    before = client.get("/api/v1/platform/bootstrap-status").json()["counts"]["inventory_movements"]

    kilogram = client.post(
        "/api/v1/inventory/units",
        headers=_admin_headers(),
        json={"code": "KG", "name": "Kilogramo", "precision_scale": 3, "dimension": "mass"},
    )
    assert kilogram.status_code == 200
    sugar = client.post(
        "/api/v1/inventory/items",
        headers=_admin_headers(),
        json={
            "name": "Azucar",
            "sku": "INV-SUGAR",
            "base_unit_id": kilogram.json()["id"],
            "item_type": "ingredient",
        },
    )
    assert sugar.status_code == 200
    supplier_response = client.post(
        "/api/v1/suppliers",
        headers=_admin_headers(),
        json={
            "code": "PROV-AZ",
            "commercial_name": "Azucares del Pacifico",
            "legal_name": "Azucares del Pacifico SA de CV",
            "tax_id": "APA010101AB1",
            "credit_days": 15,
            "delivery_days": ["monday", "thursday"],
            "payment_methods": ["cash", "transfer"],
        },
    )
    assert supplier_response.status_code == 200
    supplier = supplier_response.json()
    contact = client.post(
        f"/api/v1/suppliers/{supplier['id']}/contacts",
        headers=_admin_headers(),
        json={
            "name": "Ana Compras",
            "contact_type": "orders",
            "phone": "6691234567",
            "primary_for_orders": True,
        },
    )
    assert contact.status_code == 200
    terms = client.put(
        f"/api/v1/suppliers/{supplier['id']}/branches/{BRANCH_ID}",
        headers=_admin_headers(),
        json={"is_enabled": True, "lead_time_days": 2, "minimum_amount": "500.00"},
    )
    assert terms.status_code == 200

    presentation_response = client.post(
        "/api/v1/purchase-presentations",
        headers=_admin_headers(),
        json={
            "supplier_id": supplier["id"],
            "item_id": sugar.json()["id"],
            "code": "AZ-10KG",
            "name": "Bolsa azucar 10 kg",
            "package_type": "bag",
            "commercial_quantity": "1",
            "commercial_unit_id": "018f6f73-2d0a-74f0-8f1c-000000000303",
            "base_unit_id": kilogram.json()["id"],
            "base_unit_yield": "10",
            "usable_content": "10",
            "yield_percent": "1",
            "last_net_price": "280.00",
            "tax_rate": "0",
        },
    )
    assert presentation_response.status_code == 200
    presentation = presentation_response.json()
    assert float(presentation["cost_per_base_unit"]) == 28.0

    price_update = client.put(
        f"/api/v1/purchase-presentations/{presentation['id']}/price",
        headers=_admin_headers(),
        json={"net_price": "300.00"},
    )
    assert price_update.status_code == 200
    assert float(price_update.json()["cost_per_base_unit"]) == 30.0
    listed = client.get(
        f"/api/v1/purchase-presentations?branch_id={BRANCH_ID}", headers=_admin_headers()
    )
    assert listed.status_code == 200
    stored = next(row for row in listed.json() if row["id"] == presentation["id"])
    assert len(stored["price_history"]) == 2
    suppliers = client.get(
        f"/api/v1/suppliers?branch_id={BRANCH_ID}", headers=_admin_headers()
    ).json()
    stored_supplier = next(row for row in suppliers if row["id"] == supplier["id"])
    assert stored_supplier["contacts"][0]["primary_for_orders"] is True
    assert stored_supplier["branch_terms"][0]["lead_time_days"] == 2
    after = client.get("/api/v1/platform/bootstrap-status").json()["counts"]["inventory_movements"]
    assert after == before


def test_direct_purchase_cash_reconciliation_average_cost_idempotency_and_reversal() -> None:
    client = _client_with_seeded_database()
    kilogram = client.post(
        "/api/v1/inventory/units",
        headers=_admin_headers(),
        json={"code": "KG", "name": "Kilogramo", "precision_scale": 3, "dimension": "mass"},
    ).json()
    sugar = client.post(
        "/api/v1/inventory/items",
        headers=_admin_headers(),
        json={
            "name": "Azucar",
            "sku": "INV-SUGAR",
            "base_unit_id": kilogram["id"],
            "item_type": "ingredient",
        },
    ).json()
    supplier = client.post(
        "/api/v1/suppliers",
        headers=_admin_headers(),
        json={
            "code": "PROV-COST",
            "commercial_name": "Proveedor Costeo",
            "delivery_days": [],
            "payment_methods": ["cash"],
        },
    ).json()
    assert (
        client.put(
            f"/api/v1/suppliers/{supplier['id']}/branches/{BRANCH_ID}",
            headers=_admin_headers(),
            json={"is_enabled": True},
        ).status_code
        == 200
    )
    presentation = client.post(
        "/api/v1/purchase-presentations",
        headers=_admin_headers(),
        json={
            "supplier_id": supplier["id"],
            "item_id": sugar["id"],
            "code": "SUGAR-10",
            "name": "Bolsa 10 kg",
            "package_type": "bag",
            "commercial_quantity": "1",
            "commercial_unit_id": "018f6f73-2d0a-74f0-8f1c-000000000303",
            "base_unit_id": kilogram["id"],
            "base_unit_yield": "10",
            "usable_content": "10",
            "yield_percent": "1",
            "last_net_price": "200",
            "tax_rate": "0",
        },
    ).json()

    first = client.post(
        "/api/v1/purchases",
        headers=_admin_headers(),
        json={
            "branch_id": BRANCH_ID,
            "supplier_id": supplier["id"],
            "document_type": "invoice",
            "folio": "FAC-001",
            "payment_method": "transfer",
            "paid_from_cash": False,
            "lines": [
                {
                    "presentation_id": presentation["id"],
                    "quantity": "1",
                    "unit_price": "200",
                    "discount": "0",
                    "tax": "32",
                }
            ],
        },
    )
    assert first.status_code == 200
    first_confirm = client.post(
        f"/api/v1/purchases/{first.json()['id']}/confirm",
        headers={**_admin_headers(), "Idempotency-Key": "purchase-first"},
        json={},
    )
    assert first_confirm.status_code == 200
    first_cost = client.get(
        f"/api/v1/inventory/costs?branch_id={BRANCH_ID}", headers=_admin_headers()
    ).json()[0]
    assert float(first_cost["quantity_on_hand"]) == 10
    assert float(first_cost["average_unit_cost"]) == 20

    assert (
        client.post(
            "/api/v1/cash-shifts/open",
            headers=_admin_headers(),
            json={"opening_cash_cents": 100000},
        ).status_code
        == 200
    )
    second = client.post(
        "/api/v1/purchases",
        headers=_admin_headers(),
        json={
            "branch_id": BRANCH_ID,
            "supplier_id": supplier["id"],
            "document_type": "invoice",
            "folio": "FAC-002",
            "payment_method": "cash",
            "paid_from_cash": True,
            "lines": [
                {
                    "presentation_id": presentation["id"],
                    "quantity": "1",
                    "unit_price": "300",
                    "discount": "0",
                    "tax": "48",
                }
            ],
        },
    )
    assert second.status_code == 200
    assert float(second.json()["total"]) == 348
    confirmation_headers = {**_admin_headers(), "Idempotency-Key": "purchase-second"}
    second_confirm = client.post(
        f"/api/v1/purchases/{second.json()['id']}/confirm",
        headers=confirmation_headers,
        json={},
    )
    assert second_confirm.status_code == 200
    confirmed = second_confirm.json()
    assert confirmed["status"] == "confirmed"
    assert len(confirmed["inventory_movements"]) == 1
    assert len(confirmed["cash_movements"]) == 1
    assert confirmed["cash_movements"][0]["amount_cents"] == 34800

    costs = client.get(
        f"/api/v1/inventory/costs?branch_id={BRANCH_ID}", headers=_admin_headers()
    ).json()
    sugar_cost = next(row for row in costs if row["item_id"] == sugar["id"])
    assert float(sugar_cost["quantity_on_hand"]) == 20
    assert float(sugar_cost["average_unit_cost"]) == 25
    summary = client.get(
        f"/api/v1/cash-shifts/summary?branch_id={BRANCH_ID}", headers=_admin_headers()
    ).json()["summary"]
    assert summary["cash_withdrawal_total_cents"] == 34800
    assert summary["expected_cash_cents"] == 65200

    retry = client.post(
        f"/api/v1/purchases/{second.json()['id']}/confirm",
        headers=confirmation_headers,
        json={},
    )
    assert retry.status_code == 200
    assert len(retry.json()["inventory_movements"]) == 1
    assert len(retry.json()["cash_movements"]) == 1

    cancellation = client.post(
        f"/api/v1/purchases/{second.json()['id']}/cancel",
        headers=_admin_headers(),
        json={"reason": "Factura capturada por error"},
    )
    assert cancellation.status_code == 200
    cancelled = cancellation.json()
    assert cancelled["status"] == "cancelled"
    assert {movement["movement_type"] for movement in cancelled["inventory_movements"]} == {
        "PURCHASE_RECEIPT",
        "PURCHASE_REVERSAL",
    }
    assert {movement["movement_type"] for movement in cancelled["cash_movements"]} == {
        "withdrawal",
        "cash_reversal",
    }
    costs_after = client.get(
        f"/api/v1/inventory/costs?branch_id={BRANCH_ID}", headers=_admin_headers()
    ).json()
    sugar_after = next(row for row in costs_after if row["item_id"] == sugar["id"])
    assert float(sugar_after["quantity_on_hand"]) == 10
    assert float(sugar_after["average_unit_cost"]) == 20
    summary_after = client.get(
        f"/api/v1/cash-shifts/summary?branch_id={BRANCH_ID}", headers=_admin_headers()
    ).json()["summary"]
    assert summary_after["expected_cash_cents"] == 100000


def test_purchase_confirmation_rejects_negative_inventory_without_partial_effects() -> None:
    client = _client_with_seeded_database()
    assert (
        client.post(
            "/api/v1/cash-shifts/open",
            headers=_admin_headers(),
            json={"opening_cash_cents": 100000},
        ).status_code
        == 200
    )
    order = client.post(
        "/api/v1/orders",
        headers=_admin_headers(),
        json={"lines": [{"product_id": "018f6f73-2d0a-74f0-8f1c-000000000111", "quantity": 1000}]},
    ).json()
    task_id = order["production_tasks"][0]["id"]
    assert (
        client.post(
            f"/api/v1/kds/tasks/{task_id}/transition", json={"status": "IN_PROGRESS"}
        ).status_code
        == 200
    )
    assert (
        client.post(
            f"/api/v1/kds/tasks/{task_id}/transition", json={"status": "COMPLETED"}
        ).status_code
        == 200
    )

    supplier = client.post(
        "/api/v1/suppliers",
        headers=_admin_headers(),
        json={
            "code": "PROV-NEG",
            "commercial_name": "Proveedor Negativo",
            "delivery_days": [],
            "payment_methods": [],
        },
    ).json()
    presentation = client.post(
        "/api/v1/purchase-presentations",
        headers=_admin_headers(),
        json={
            "supplier_id": supplier["id"],
            "item_id": "018f6f73-2d0a-74f0-8f1c-000000000311",
            "code": "BEEF-1KG",
            "name": "Carne 1 kg",
            "package_type": "package",
            "commercial_quantity": "1",
            "commercial_unit_id": "018f6f73-2d0a-74f0-8f1c-000000000303",
            "base_unit_id": "018f6f73-2d0a-74f0-8f1c-000000000301",
            "base_unit_yield": "1000",
            "usable_content": "1000",
            "yield_percent": "1",
            "last_net_price": "100",
            "tax_rate": "0",
        },
    ).json()
    purchase = client.post(
        "/api/v1/purchases",
        headers=_admin_headers(),
        json={
            "branch_id": BRANCH_ID,
            "supplier_id": supplier["id"],
            "document_type": "ticket",
            "folio": "NEG-001",
            "payment_method": "cash",
            "paid_from_cash": True,
            "lines": [
                {
                    "presentation_id": presentation["id"],
                    "quantity": "1",
                    "unit_price": "100",
                    "tax": "0",
                }
            ],
        },
    ).json()
    before_movements = client.get("/api/v1/platform/bootstrap-status").json()["counts"][
        "inventory_movements"
    ]
    confirmation = client.post(
        f"/api/v1/purchases/{purchase['id']}/confirm",
        headers={**_admin_headers(), "Idempotency-Key": "negative-policy"},
        json={},
    )
    assert confirmation.status_code == 409
    assert confirmation.json()["detail"]["code"] == "negative_inventory_cost_policy_required"
    purchases = client.get(
        f"/api/v1/purchases?branch_id={BRANCH_ID}", headers=_admin_headers()
    ).json()
    stored = next(row for row in purchases if row["id"] == purchase["id"])
    assert stored["status"] == "draft"
    assert stored["inventory_movements"] == []
    assert stored["cash_movements"] == []
    assert (
        client.get("/api/v1/platform/bootstrap-status").json()["counts"]["inventory_movements"]
        == before_movements
    )


def test_recipe_versions_standard_waste_and_historical_order_snapshot() -> None:
    client = _client_with_seeded_database()
    burger_id = "018f6f73-2d0a-74f0-8f1c-000000000111"
    beef_id = "018f6f73-2d0a-74f0-8f1c-000000000311"
    gram_id = "018f6f73-2d0a-74f0-8f1c-000000000301"
    piece_id = "018f6f73-2d0a-74f0-8f1c-000000000303"

    assert (
        client.post(
            "/api/v1/cash-shifts/open",
            headers=_admin_headers(),
            json={"opening_cash_cents": 50000},
        ).status_code
        == 200
    )
    order = client.post(
        "/api/v1/orders",
        headers=_admin_headers(),
        json={"lines": [{"product_id": burger_id, "quantity": 1}]},
    ).json()
    snapshot = order["consumption_snapshots"][0]
    original_beef = next(row for row in snapshot["components"] if row["item_id"] == beef_id)
    assert float(original_beef["gross_quantity"]) == 120

    updated = client.put(
        f"/api/v1/products/{burger_id}/recipe",
        headers=_admin_headers(),
        json={
            "yield_quantity": "1",
            "yield_unit_id": piece_id,
            "components": [
                {
                    "item_id": beef_id,
                    "unit_id": gram_id,
                    "net_quantity": "100",
                    "waste_percent": "20",
                }
            ],
        },
    )
    assert updated.status_code == 200
    assert updated.json()["version"] == 2
    component = updated.json()["components"][0]
    assert float(component["net_quantity"]) == 100
    assert float(component["gross_quantity"]) == 125
    assert float(component["waste_rate"]) == 0.2

    current = client.get(f"/api/v1/products/{burger_id}/recipe").json()
    assert current["version"] == 2
    assert float(current["components"][0]["gross_quantity"]) == 125

    task_id = order["production_tasks"][0]["id"]
    assert (
        client.post(
            f"/api/v1/kds/tasks/{task_id}/transition", json={"status": "IN_PROGRESS"}
        ).status_code
        == 200
    )
    assert (
        client.post(
            f"/api/v1/kds/tasks/{task_id}/transition", json={"status": "COMPLETED"}
        ).status_code
        == 200
    )
    movements = client.get(
        f"/api/v1/inventory/kardex?item_id={beef_id}", headers=_admin_headers()
    ).json()
    assert any(
        row["movement_type"] == "SALE_CONSUMPTION" and float(row["quantity_delta"]) == -120
        for row in movements
    )
    assert not any(
        row["movement_type"] == "SALE_CONSUMPTION" and float(row["quantity_delta"]) == -125
        for row in movements
    )


def test_production_batch_is_idempotent_and_production_recipes_reject_cycles() -> None:
    client = _client_with_seeded_database()
    gram_id = "018f6f73-2d0a-74f0-8f1c-000000000301"
    beef_id = "018f6f73-2d0a-74f0-8f1c-000000000311"

    sauce = client.post(
        "/api/v1/inventory/items",
        headers=_admin_headers(),
        json={
            "name": "Salsa elaborada",
            "sku": "INV-SAUCE",
            "base_unit_id": gram_id,
            "item_type": "elaborated",
        },
    ).json()
    recipe_response = client.post(
        "/api/v1/production-recipes",
        headers=_admin_headers(),
        json={
            "output_item_id": sauce["id"],
            "yield_quantity": "1000",
            "yield_unit_id": gram_id,
            "branch_id": BRANCH_ID,
            "components": [{"item_id": beef_id, "net_quantity": "500", "waste_percent": "0"}],
        },
    )
    assert recipe_response.status_code == 200
    recipe = recipe_response.json()

    batch_response = client.post(
        "/api/v1/production-batches",
        headers=_admin_headers(),
        json={
            "branch_id": BRANCH_ID,
            "recipe_id": recipe["id"],
            "lot_code": "SALSA-001",
            "planned_quantity": "1000",
            "actual_quantity": "900",
        },
    )
    assert batch_response.status_code == 200
    batch = batch_response.json()
    headers = {**_admin_headers(), "Idempotency-Key": "production-salsa-001"}
    confirmed = client.post(
        f"/api/v1/production-batches/{batch['id']}/confirm", headers=headers, json={}
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["status"] == "confirmed"
    assert sorted(
        (row["movement_type"], float(row["quantity_delta"]))
        for row in confirmed.json()["movements"]
    ) == [("PRODUCTION_INPUT", -500.0), ("PRODUCTION_OUTPUT", 900.0)]

    replay = client.post(
        f"/api/v1/production-batches/{batch['id']}/confirm", headers=headers, json={}
    )
    assert replay.status_code == 200
    assert len(replay.json()["movements"]) == 2
    conflict = client.post(
        f"/api/v1/production-batches/{batch['id']}/confirm",
        headers={**_admin_headers(), "Idempotency-Key": "different-key"},
        json={},
    )
    assert conflict.status_code == 409
    assert conflict.json()["detail"]["code"] == "production_batch_already_confirmed"

    product = client.post(
        "/api/v1/catalog/products",
        headers=_admin_headers(),
        json={
            "name": "Platillo con salsa",
            "sku": "KIWI-SAUCE-DISH",
            "category_name": "Comida",
            "station": "kitchen",
            "price_cents": 7500,
        },
    ).json()
    sale_recipe = client.put(
        f"/api/v1/products/{product['id']}/recipe",
        headers=_admin_headers(),
        json={
            "yield_quantity": "1",
            "yield_unit_id": "018f6f73-2d0a-74f0-8f1c-000000000303",
            "components": [{"item_id": sauce["id"], "net_quantity": "100"}],
        },
    )
    assert sale_recipe.status_code == 200
    assert (
        client.post(
            "/api/v1/cash-shifts/open", headers=_admin_headers(), json={"opening_cash_cents": 10000}
        ).status_code
        == 200
    )
    order = client.post(
        "/api/v1/orders",
        headers=_admin_headers(),
        json={"lines": [{"product_id": product["id"], "quantity": 1}]},
    ).json()
    task_id = order["production_tasks"][0]["id"]
    assert (
        client.post(
            f"/api/v1/kds/tasks/{task_id}/transition", json={"status": "IN_PROGRESS"}
        ).status_code
        == 200
    )
    assert (
        client.post(
            f"/api/v1/kds/tasks/{task_id}/transition", json={"status": "COMPLETED"}
        ).status_code
        == 200
    )
    sauce_movements = client.get(
        f"/api/v1/inventory/kardex?item_id={sauce['id']}", headers=_admin_headers()
    ).json()
    assert any(
        row["movement_type"] == "SALE_CONSUMPTION" and float(row["quantity_delta"]) == -100
        for row in sauce_movements
    )
    beef_movements = client.get(
        f"/api/v1/inventory/kardex?item_id={beef_id}", headers=_admin_headers()
    ).json()
    assert not any(row["movement_type"] == "SALE_CONSUMPTION" for row in beef_movements)

    filling = client.post(
        "/api/v1/inventory/items",
        headers=_admin_headers(),
        json={
            "name": "Relleno elaborado",
            "sku": "INV-FILLING",
            "base_unit_id": gram_id,
            "item_type": "elaborated",
        },
    ).json()
    replace_sauce_recipe = client.post(
        "/api/v1/production-recipes",
        headers=_admin_headers(),
        json={
            "output_item_id": sauce["id"],
            "yield_quantity": "100",
            "yield_unit_id": gram_id,
            "components": [{"item_id": filling["id"], "net_quantity": "50"}],
        },
    )
    assert replace_sauce_recipe.status_code == 200
    cycle = client.post(
        "/api/v1/production-recipes",
        headers=_admin_headers(),
        json={
            "output_item_id": filling["id"],
            "yield_quantity": "100",
            "yield_unit_id": gram_id,
            "components": [{"item_id": sauce["id"], "net_quantity": "50"}],
        },
    )
    assert cycle.status_code == 409
    assert cycle.json()["detail"]["code"] == "recipe_cycle_detected"


def test_modifiers_validate_groups_price_snapshot_kitchen_text_and_inventory() -> None:
    client = _client_with_seeded_database()
    burger_id = "018f6f73-2d0a-74f0-8f1c-000000000111"
    beef_id = "018f6f73-2d0a-74f0-8f1c-000000000311"
    bun_id = "018f6f73-2d0a-74f0-8f1c-000000000312"

    extras = client.post(
        f"/api/v1/products/{burger_id}/modifier-groups",
        headers=_admin_headers(),
        json={
            "name": "Extras",
            "minimum_selections": 0,
            "maximum_selections": 1,
            "station": "kitchen",
        },
    ).json()
    extra_beef = client.post(
        f"/api/v1/modifier-groups/{extras['id']}/options",
        headers=_admin_headers(),
        json={
            "name": "Carne extra",
            "effect_type": "add",
            "affected_item_id": beef_id,
            "add_quantity": "50",
            "price_delta_cents": 2000,
            "kitchen_text": "Agregar carne extra",
        },
    ).json()
    extra_beef_two = client.post(
        f"/api/v1/modifier-groups/{extras['id']}/options",
        headers=_admin_headers(),
        json={
            "name": "Doble carne extra",
            "effect_type": "add",
            "affected_item_id": beef_id,
            "add_quantity": "100",
            "price_delta_cents": 3500,
        },
    ).json()
    instructions = client.post(
        f"/api/v1/products/{burger_id}/modifier-groups",
        headers=_admin_headers(),
        json={"name": "Instrucciones", "minimum_selections": 0, "maximum_selections": 1},
    ).json()
    instruction = client.post(
        f"/api/v1/modifier-groups/{instructions['id']}/options",
        headers=_admin_headers(),
        json={"name": "Comentario libre", "effect_type": "instruction", "inventory_effect": False},
    ).json()
    removals = client.post(
        f"/api/v1/products/{burger_id}/modifier-groups",
        headers=_admin_headers(),
        json={"name": "Quitar", "minimum_selections": 0, "maximum_selections": 1},
    ).json()
    no_bun = client.post(
        f"/api/v1/modifier-groups/{removals['id']}/options",
        headers=_admin_headers(),
        json={
            "name": "Sin pan",
            "effect_type": "remove",
            "affected_item_id": bun_id,
            "remove_quantity": "0",
        },
    ).json()

    catalog = client.get(
        f"/api/v1/products/{burger_id}/modifiers?branch_id={BRANCH_ID}",
        headers=_admin_headers(),
    ).json()
    assert len(catalog) == 3
    assert (
        next(group for group in catalog if group["id"] == extras["id"])["options"][0][
            "price_delta_cents"
        ]
        == 2000
    )
    assert (
        client.post(
            "/api/v1/cash-shifts/open", headers=_admin_headers(), json={"opening_cash_cents": 10000}
        ).status_code
        == 200
    )

    too_many = client.post(
        "/api/v1/orders",
        headers=_admin_headers(),
        json={
            "lines": [
                {
                    "product_id": burger_id,
                    "quantity": 1,
                    "modifiers": [
                        {"option_id": extra_beef["id"]},
                        {"option_id": extra_beef_two["id"]},
                    ],
                }
            ]
        },
    )
    assert too_many.status_code == 409
    assert too_many.json()["detail"]["code"] == "modifier_group_maximum_exceeded"

    order = client.post(
        "/api/v1/orders",
        headers=_admin_headers(),
        json={
            "lines": [
                {
                    "product_id": burger_id,
                    "quantity": 2,
                    "modifiers": [
                        {"option_id": extra_beef["id"]},
                        {"option_id": instruction["id"], "text": "Cortar por la mitad"},
                    ],
                }
            ]
        },
    )
    assert order.status_code == 200
    payload = order.json()
    assert payload["total_cents"] == 23000
    assert payload["lines"][0]["modifier_total_cents"] == 4000
    snapshot = payload["consumption_snapshots"][0]
    beef = next(
        component for component in snapshot["components"] if component["item_id"] == beef_id
    )
    assert float(beef["gross_quantity"]) == 340
    assert any(
        modifier["kitchen_text"] == "Cortar por la mitad" for modifier in snapshot["modifiers"]
    )

    assert (
        client.put(
            f"/api/v1/modifier-options/{extra_beef['id']}/branches/{BRANCH_ID}",
            headers=_admin_headers(),
            json={"is_enabled": True, "price_delta_cents": 3000},
        ).status_code
        == 200
    )
    task_id = payload["production_tasks"][0]["id"]
    kds_task = next(
        task for task in client.get("/api/v1/kds/tasks").json() if task["id"] == task_id
    )
    assert any(
        modifier["kitchen_text"] == "Cortar por la mitad"
        for modifier in kds_task["selected_modifiers"]
    )
    assert (
        client.post(
            f"/api/v1/kds/tasks/{task_id}/transition", json={"status": "IN_PROGRESS"}
        ).status_code
        == 200
    )
    assert (
        client.post(
            f"/api/v1/kds/tasks/{task_id}/transition", json={"status": "COMPLETED"}
        ).status_code
        == 200
    )
    beef_movements = client.get(
        f"/api/v1/inventory/kardex?item_id={beef_id}", headers=_admin_headers()
    ).json()
    assert any(
        row["movement_type"] == "SALE_CONSUMPTION" and float(row["quantity_delta"]) == -340
        for row in beef_movements
    )

    without_bun = client.post(
        "/api/v1/orders",
        headers=_admin_headers(),
        json={
            "lines": [
                {"product_id": burger_id, "quantity": 1, "modifiers": [{"option_id": no_bun["id"]}]}
            ]
        },
    )
    assert without_bun.status_code == 200
    assert not any(
        component["item_id"] == bun_id
        for component in without_bun.json()["consumption_snapshots"][0]["components"]
    )

    required = client.post(
        f"/api/v1/products/{burger_id}/modifier-groups",
        headers=_admin_headers(),
        json={
            "name": "Cocción",
            "is_required": True,
            "minimum_selections": 1,
            "maximum_selections": 1,
        },
    )
    assert required.status_code == 200
    missing = client.post(
        "/api/v1/orders",
        headers=_admin_headers(),
        json={"lines": [{"product_id": burger_id, "quantity": 1}]},
    )
    assert missing.status_code == 409
    assert missing.json()["detail"]["code"] == "modifier_group_minimum_not_met"


def test_real_waste_draft_confirmation_costing_idempotency_and_reversal() -> None:
    client = _client_with_seeded_database()
    piece_id = "018f6f73-2d0a-74f0-8f1c-000000000303"
    kilogram = client.post(
        "/api/v1/inventory/units",
        headers=_admin_headers(),
        json={
            "code": "KG-WASTE",
            "name": "Kilogramo merma",
            "precision_scale": 3,
            "dimension": "mass",
        },
    ).json()
    item = client.post(
        "/api/v1/inventory/items",
        headers=_admin_headers(),
        json={
            "name": "Pulpa para merma",
            "sku": "INV-WASTE-PULP",
            "base_unit_id": kilogram["id"],
            "item_type": "ingredient",
        },
    ).json()
    supplier = client.post(
        "/api/v1/suppliers",
        headers=_admin_headers(),
        json={
            "code": "PROV-WASTE",
            "commercial_name": "Proveedor Merma",
            "delivery_days": [],
            "payment_methods": ["transfer"],
        },
    ).json()
    assert (
        client.put(
            f"/api/v1/suppliers/{supplier['id']}/branches/{BRANCH_ID}",
            headers=_admin_headers(),
            json={"is_enabled": True},
        ).status_code
        == 200
    )
    presentation = client.post(
        "/api/v1/purchase-presentations",
        headers=_admin_headers(),
        json={
            "supplier_id": supplier["id"],
            "item_id": item["id"],
            "code": "PULP-10",
            "name": "Cubeta 10 kg",
            "package_type": "bucket",
            "commercial_quantity": "1",
            "commercial_unit_id": piece_id,
            "base_unit_id": kilogram["id"],
            "base_unit_yield": "10",
            "usable_content": "10",
            "yield_percent": "1",
            "last_net_price": "250",
            "tax_rate": "0",
        },
    ).json()
    purchase = client.post(
        "/api/v1/purchases",
        headers=_admin_headers(),
        json={
            "branch_id": BRANCH_ID,
            "supplier_id": supplier["id"],
            "document_type": "invoice",
            "folio": "WASTE-COST-001",
            "payment_method": "transfer",
            "paid_from_cash": False,
            "lines": [
                {
                    "presentation_id": presentation["id"],
                    "quantity": "1",
                    "unit_price": "250",
                    "discount": "0",
                    "tax": "0",
                }
            ],
        },
    ).json()
    assert (
        client.post(
            f"/api/v1/purchases/{purchase['id']}/confirm",
            headers={**_admin_headers(), "Idempotency-Key": "purchase-waste-cost"},
            json={},
        ).status_code
        == 200
    )

    reason = client.post(
        "/api/v1/inventory/waste-reasons",
        headers=_admin_headers(),
        json={"code": "TEST_SPILL", "name": "Derrame de prueba", "classification": "operation"},
    ).json()
    before_movements = client.get("/api/v1/platform/bootstrap-status").json()["counts"][
        "inventory_movements"
    ]
    draft_response = client.post(
        "/api/v1/inventory/wastes",
        headers=_admin_headers(),
        json={
            "branch_id": BRANCH_ID,
            "item_id": item["id"],
            "unit_id": kilogram["id"],
            "reason_id": reason["id"],
            "quantity": "2",
            "stage": "preparation",
            "notes": "Cubeta derramada",
            "evidence": ["evidence://photo/waste-001"],
        },
    )
    assert draft_response.status_code == 200
    draft = draft_response.json()
    assert draft["status"] == "draft"
    assert draft["movements"] == []
    assert (
        client.get("/api/v1/platform/bootstrap-status").json()["counts"]["inventory_movements"]
        == before_movements
    )

    confirmation_headers = {**_admin_headers(), "Idempotency-Key": "waste-confirm-001"}
    confirmation = client.post(
        f"/api/v1/inventory/wastes/{draft['id']}/confirm",
        headers=confirmation_headers,
        json={},
    )
    assert confirmation.status_code == 200
    confirmed = confirmation.json()
    assert confirmed["status"] == "confirmed"
    assert float(confirmed["unit_cost"]) == 25
    assert float(confirmed["total_cost"]) == 50
    assert confirmed["created_by"] == ADMIN_USER_ID
    assert confirmed["confirmed_by"] == ADMIN_USER_ID
    assert len(confirmed["movements"]) == 1
    movement = confirmed["movements"][0]
    assert movement["movement_type"] == "WASTE_REAL"
    assert float(movement["quantity_delta"]) == -2
    assert float(movement["total_cost"]) == -50

    replay = client.post(
        f"/api/v1/inventory/wastes/{draft['id']}/confirm",
        headers=confirmation_headers,
        json={},
    )
    assert replay.status_code == 200
    assert len(replay.json()["movements"]) == 1
    costs = client.get(
        f"/api/v1/inventory/costs?branch_id={BRANCH_ID}", headers=_admin_headers()
    ).json()
    cost = next(row for row in costs if row["item_id"] == item["id"])
    assert float(cost["quantity_on_hand"]) == 8
    assert float(cost["average_unit_cost"]) == 25

    wrong_key = client.post(
        f"/api/v1/inventory/wastes/{draft['id']}/confirm",
        headers={**_admin_headers(), "Idempotency-Key": "waste-other-key"},
        json={},
    )
    assert wrong_key.status_code == 409
    assert wrong_key.json()["detail"]["code"] == "waste_already_confirmed"

    reversal_headers = {**_admin_headers(), "Idempotency-Key": "waste-reverse-001"}
    reversal = client.post(
        f"/api/v1/inventory/wastes/{draft['id']}/reverse",
        headers=reversal_headers,
        json={"reason": "Cantidad capturada por error"},
    )
    assert reversal.status_code == 200
    reversed_waste = reversal.json()
    assert reversed_waste["status"] == "reversed"
    assert len(reversed_waste["movements"]) == 2
    reverse_movement = next(
        row for row in reversed_waste["movements"] if row["movement_type"] == "WASTE_REVERSAL"
    )
    assert float(reverse_movement["quantity_delta"]) == 2
    assert reverse_movement["reversal_of_id"] == movement["id"]
    reversal_replay = client.post(
        f"/api/v1/inventory/wastes/{draft['id']}/reverse",
        headers=reversal_headers,
        json={"reason": "Cantidad capturada por error"},
    )
    assert reversal_replay.status_code == 200
    assert len(reversal_replay.json()["movements"]) == 2
    costs_after = client.get(
        f"/api/v1/inventory/costs?branch_id={BRANCH_ID}", headers=_admin_headers()
    ).json()
    cost_after = next(row for row in costs_after if row["item_id"] == item["id"])
    assert float(cost_after["quantity_on_hand"]) == 10
    assert float(cost_after["average_unit_cost"]) == 25

    insufficient = client.post(
        "/api/v1/inventory/wastes",
        headers=_admin_headers(),
        json={
            "branch_id": BRANCH_ID,
            "item_id": item["id"],
            "reason_id": reason["id"],
            "quantity": "11",
            "stage": "storage",
            "evidence": [],
        },
    ).json()
    insufficient_confirmation = client.post(
        f"/api/v1/inventory/wastes/{insufficient['id']}/confirm",
        headers={**_admin_headers(), "Idempotency-Key": "waste-insufficient"},
        json={},
    )
    assert insufficient_confirmation.status_code == 409
    assert insufficient_confirmation.json()["detail"]["code"] == "insufficient_waste_inventory"
    listed = client.get(f"/api/v1/inventory/wastes?branch_id={BRANCH_ID}", headers=_admin_headers())
    assert listed.status_code == 200
    stored_insufficient = next(row for row in listed.json() if row["id"] == insufficient["id"])
    assert stored_insufficient["status"] == "draft"
    assert stored_insufficient["movements"] == []

    assert (
        client.put(
            f"/api/v1/inventory/waste-reasons/{reason['id']}",
            headers=_admin_headers(),
            json={"status": "inactive"},
        ).status_code
        == 200
    )
    inactive_reason = client.post(
        "/api/v1/inventory/wastes",
        headers=_admin_headers(),
        json={
            "branch_id": BRANCH_ID,
            "item_id": item["id"],
            "reason_id": reason["id"],
            "quantity": "1",
            "stage": "storage",
        },
    )
    assert inactive_reason.status_code == 409
    assert inactive_reason.json()["detail"]["code"] == "active_waste_reason_not_found"


def test_inventory_transfer_partial_receipt_preserves_cost_and_idempotency() -> None:
    client = _client_with_seeded_database()
    piece_id = "018f6f73-2d0a-74f0-8f1c-000000000303"
    destination = client.post(
        "/api/v1/branches",
        headers=_admin_headers(),
        json={"name": "Sucursal Destino", "code": "DESTINO"},
    ).json()
    kilogram = client.post(
        "/api/v1/inventory/units",
        headers=_admin_headers(),
        json={
            "code": "KG-TRANSFER",
            "name": "Kilogramo traspaso",
            "precision_scale": 3,
            "dimension": "mass",
        },
    ).json()
    item = client.post(
        "/api/v1/inventory/items",
        headers=_admin_headers(),
        json={
            "name": "Pulpa transferible",
            "sku": "INV-TRANSFER-PULP",
            "base_unit_id": kilogram["id"],
            "item_type": "ingredient",
        },
    ).json()
    supplier = client.post(
        "/api/v1/suppliers",
        headers=_admin_headers(),
        json={
            "code": "PROV-TRANSFER",
            "commercial_name": "Proveedor Traspaso",
            "delivery_days": [],
            "payment_methods": ["transfer"],
        },
    ).json()
    assert (
        client.put(
            f"/api/v1/suppliers/{supplier['id']}/branches/{BRANCH_ID}",
            headers=_admin_headers(),
            json={"is_enabled": True},
        ).status_code
        == 200
    )
    presentation = client.post(
        "/api/v1/purchase-presentations",
        headers=_admin_headers(),
        json={
            "supplier_id": supplier["id"],
            "item_id": item["id"],
            "code": "TRANSFER-10",
            "name": "Cubeta transferible 10 kg",
            "package_type": "bucket",
            "commercial_quantity": "1",
            "commercial_unit_id": piece_id,
            "base_unit_id": kilogram["id"],
            "base_unit_yield": "10",
            "usable_content": "10",
            "yield_percent": "1",
            "last_net_price": "250",
            "tax_rate": "0",
        },
    ).json()
    purchase = client.post(
        "/api/v1/purchases",
        headers=_admin_headers(),
        json={
            "branch_id": BRANCH_ID,
            "supplier_id": supplier["id"],
            "document_type": "invoice",
            "folio": "TRANSFER-COST-001",
            "payment_method": "transfer",
            "paid_from_cash": False,
            "lines": [
                {
                    "presentation_id": presentation["id"],
                    "quantity": "1",
                    "unit_price": "250",
                    "discount": "0",
                    "tax": "0",
                }
            ],
        },
    ).json()
    assert (
        client.post(
            f"/api/v1/purchases/{purchase['id']}/confirm",
            headers={**_admin_headers(), "Idempotency-Key": "purchase-transfer-cost"},
            json={},
        ).status_code
        == 200
    )

    before_movements = client.get("/api/v1/platform/bootstrap-status").json()["counts"][
        "inventory_movements"
    ]
    draft_response = client.post(
        "/api/v1/inventory/transfers",
        headers=_admin_headers(),
        json={
            "source_branch_id": BRANCH_ID,
            "destination_branch_id": destination["id"],
            "notes": "Traspaso de prueba",
            "lines": [{"item_id": item["id"], "unit_id": kilogram["id"], "quantity": "10"}],
        },
    )
    assert draft_response.status_code == 200
    draft = draft_response.json()
    assert draft["status"] == "draft"
    assert draft["movements"] == []
    assert (
        client.get("/api/v1/platform/bootstrap-status").json()["counts"]["inventory_movements"]
        == before_movements
    )

    send_headers = {**_admin_headers(), "Idempotency-Key": "transfer-send-001"}
    sent_response = client.post(
        f"/api/v1/inventory/transfers/{draft['id']}/send",
        headers=send_headers,
        json={},
    )
    assert sent_response.status_code == 200
    sent = sent_response.json()
    assert sent["status"] == "sent"
    line = sent["lines"][0]
    assert float(line["sent_quantity"]) == 10
    assert float(line["unit_cost"]) == 25
    assert float(line["sent_total_cost"]) == 250
    transfer_out = next(row for row in sent["movements"] if row["movement_type"] == "TRANSFER_OUT")
    assert float(transfer_out["quantity_delta"]) == -10
    assert float(transfer_out["total_cost"]) == -250
    sent_replay = client.post(
        f"/api/v1/inventory/transfers/{draft['id']}/send",
        headers=send_headers,
        json={},
    )
    assert sent_replay.status_code == 200
    assert len(sent_replay.json()["movements"]) == 1
    wrong_send_key = client.post(
        f"/api/v1/inventory/transfers/{draft['id']}/send",
        headers={**_admin_headers(), "Idempotency-Key": "transfer-send-other"},
        json={},
    )
    assert wrong_send_key.status_code == 409
    assert wrong_send_key.json()["detail"]["code"] == "transfer_already_sent"

    receive_headers = {**_admin_headers(), "Idempotency-Key": "transfer-receive-001"}
    received_response = client.post(
        f"/api/v1/inventory/transfers/{draft['id']}/receive",
        headers=receive_headers,
        json={
            "lines": [
                {
                    "line_id": line["id"],
                    "received_quantity": "9.5",
                    "condition": "damaged",
                    "difference_reason": "Envase dañado durante traslado",
                }
            ]
        },
    )
    assert received_response.status_code == 200
    received = received_response.json()
    assert received["status"] == "received_with_difference"
    received_line = received["lines"][0]
    assert float(received_line["received_quantity"]) == 9.5
    assert float(received_line["difference_quantity"]) == 0.5
    assert float(received_line["received_total_cost"]) == 237.5
    assert float(received_line["difference_cost"]) == 12.5
    transfer_in = next(
        row for row in received["movements"] if row["movement_type"] == "TRANSFER_IN"
    )
    assert float(transfer_in["quantity_delta"]) == 9.5
    assert float(transfer_in["total_cost"]) == 237.5
    assert all(row["movement_type"] != "PURCHASE_RECEIPT" for row in received["movements"])

    received_replay = client.post(
        f"/api/v1/inventory/transfers/{draft['id']}/receive",
        headers=receive_headers,
        json={
            "lines": [
                {"line_id": line["id"], "received_quantity": "9.5", "difference_reason": "retry"}
            ]
        },
    )
    assert received_replay.status_code == 200
    assert len(received_replay.json()["movements"]) == 2
    wrong_receive_key = client.post(
        f"/api/v1/inventory/transfers/{draft['id']}/receive",
        headers={**_admin_headers(), "Idempotency-Key": "transfer-receive-other"},
        json={
            "lines": [
                {"line_id": line["id"], "received_quantity": "9.5", "difference_reason": "retry"}
            ]
        },
    )
    assert wrong_receive_key.status_code == 409
    assert wrong_receive_key.json()["detail"]["code"] == "transfer_already_received"

    source_costs = client.get(
        f"/api/v1/inventory/costs?branch_id={BRANCH_ID}", headers=_admin_headers()
    ).json()
    source_cost = next(row for row in source_costs if row["item_id"] == item["id"])
    assert float(source_cost["quantity_on_hand"]) == 0
    assert float(source_cost["average_unit_cost"]) == 25
    destination_costs = client.get(
        f"/api/v1/inventory/costs?branch_id={destination['id']}",
        headers=_admin_headers(),
    ).json()
    destination_cost = next(row for row in destination_costs if row["item_id"] == item["id"])
    assert float(destination_cost["quantity_on_hand"]) == 9.5
    assert float(destination_cost["average_unit_cost"]) == 25
    destination_list = client.get(
        f"/api/v1/inventory/transfers?branch_id={destination['id']}",
        headers=_admin_headers(),
    )
    assert destination_list.status_code == 200
    assert destination_list.json()[0]["id"] == draft["id"]

    insufficient = client.post(
        "/api/v1/inventory/transfers",
        headers=_admin_headers(),
        json={
            "source_branch_id": BRANCH_ID,
            "destination_branch_id": destination["id"],
            "lines": [{"item_id": item["id"], "quantity": "1"}],
        },
    ).json()
    insufficient_send = client.post(
        f"/api/v1/inventory/transfers/{insufficient['id']}/send",
        headers={**_admin_headers(), "Idempotency-Key": "transfer-insufficient"},
        json={},
    )
    assert insufficient_send.status_code == 409
    assert insufficient_send.json()["detail"]["code"] == "insufficient_transfer_inventory"
    stored_insufficient = next(
        row
        for row in client.get(
            f"/api/v1/inventory/transfers?branch_id={BRANCH_ID}",
            headers=_admin_headers(),
        ).json()
        if row["id"] == insufficient["id"]
    )
    assert stored_insufficient["status"] == "draft"
    assert stored_insufficient["movements"] == []


def test_physical_count_blind_snapshot_preserves_intermediate_movements() -> None:
    client = _client_with_seeded_database()
    beef_id = "018f6f73-2d0a-74f0-8f1c-000000000311"
    burger_id = "018f6f73-2d0a-74f0-8f1c-000000000111"
    before_movements = client.get("/api/v1/platform/bootstrap-status").json()["counts"][
        "inventory_movements"
    ]
    opened_response = client.post(
        "/api/v1/inventory/physical-counts",
        headers=_admin_headers(),
        json={"branch_id": BRANCH_ID, "item_ids": [beef_id], "notes": "Conteo selectivo de carne"},
    )
    assert opened_response.status_code == 200
    opened = opened_response.json()
    assert opened["status"] == "counting"
    assert opened["blind"] is True
    assert len(opened["lines"]) == 1
    line = opened["lines"][0]
    assert "theoretical_quantity" not in line
    assert "snapshot_difference" not in line
    assert opened["movements"] == []
    assert (
        client.get("/api/v1/platform/bootstrap-status").json()["counts"]["inventory_movements"]
        == before_movements
    )

    duplicate = client.post(
        "/api/v1/inventory/physical-counts",
        headers=_admin_headers(),
        json={"branch_id": BRANCH_ID, "item_ids": [beef_id]},
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"]["code"] == "active_physical_count_exists"
    incomplete = client.post(
        f"/api/v1/inventory/physical-counts/{opened['id']}/submit",
        headers=_admin_headers(),
        json={},
    )
    assert incomplete.status_code == 409
    assert incomplete.json()["detail"]["code"] == "physical_count_incomplete"

    captured_response = client.put(
        f"/api/v1/inventory/physical-counts/{opened['id']}/lines/{line['id']}",
        headers=_admin_headers(),
        json={"counted_quantity": "24800", "notes": "Dos paquetes faltantes"},
    )
    assert captured_response.status_code == 200
    captured_line = captured_response.json()["lines"][0]
    assert float(captured_line["counted_quantity"]) == 24800
    assert "theoretical_quantity" not in captured_line
    submitted_response = client.post(
        f"/api/v1/inventory/physical-counts/{opened['id']}/submit",
        headers=_admin_headers(),
        json={},
    )
    assert submitted_response.status_code == 200
    submitted = submitted_response.json()
    assert submitted["status"] == "submitted"
    assert submitted["blind"] is False
    submitted_line = submitted["lines"][0]
    assert float(submitted_line["theoretical_quantity"]) == 25000
    assert float(submitted_line["snapshot_difference"]) == -200
    immutable_capture = client.put(
        f"/api/v1/inventory/physical-counts/{opened['id']}/lines/{line['id']}",
        headers=_admin_headers(),
        json={"counted_quantity": "24900"},
    )
    assert immutable_capture.status_code == 409
    assert immutable_capture.json()["detail"]["code"] == "physical_count_not_editable"

    assert (
        client.post(
            "/api/v1/cash-shifts/open",
            headers=_admin_headers(),
            json={"opening_cash_cents": 10000},
        ).status_code
        == 200
    )
    order = client.post(
        "/api/v1/orders",
        headers=_admin_headers(),
        json={"lines": [{"product_id": burger_id, "quantity": 1}]},
    ).json()
    task_id = order["production_tasks"][0]["id"]
    assert (
        client.post(
            f"/api/v1/kds/tasks/{task_id}/transition",
            json={"status": "IN_PROGRESS"},
        ).status_code
        == 200
    )
    assert (
        client.post(
            f"/api/v1/kds/tasks/{task_id}/transition",
            json={"status": "COMPLETED"},
        ).status_code
        == 200
    )
    stock_before_approval = next(
        row
        for row in client.get(
            "/api/v1/inventory/stock", headers=_admin_headers()
        ).json()
        if row["id"] == beef_id
    )
    assert float(stock_before_approval["quantity_on_hand"]) == 24880

    approval_headers = {**_admin_headers(), "Idempotency-Key": "physical-count-approve-001"}
    approved_response = client.post(
        f"/api/v1/inventory/physical-counts/{opened['id']}/approve",
        headers=approval_headers,
        json={},
    )
    assert approved_response.status_code == 200
    approved = approved_response.json()
    assert approved["status"] == "approved"
    approved_line = approved["lines"][0]
    assert float(approved_line["snapshot_difference"]) == -200
    assert float(approved_line["approval_ledger_quantity"]) == 24880
    assert float(approved_line["adjustment_quantity"]) == -80
    assert len(approved["movements"]) == 1
    adjustment = approved["movements"][0]
    assert adjustment["movement_type"] == "COUNT_ADJUSTMENT"
    assert float(adjustment["quantity_delta"]) == -80

    replay = client.post(
        f"/api/v1/inventory/physical-counts/{opened['id']}/approve",
        headers=approval_headers,
        json={},
    )
    assert replay.status_code == 200
    assert len(replay.json()["movements"]) == 1
    wrong_key = client.post(
        f"/api/v1/inventory/physical-counts/{opened['id']}/approve",
        headers={**_admin_headers(), "Idempotency-Key": "physical-count-other"},
        json={},
    )
    assert wrong_key.status_code == 409
    assert wrong_key.json()["detail"]["code"] == "physical_count_already_approved"
    closed = client.post(
        f"/api/v1/inventory/physical-counts/{opened['id']}/close",
        headers=_admin_headers(),
        json={},
    )
    assert closed.status_code == 200
    assert closed.json()["status"] == "closed"
    final_stock = next(
        row
        for row in client.get(
            "/api/v1/inventory/stock", headers=_admin_headers()
        ).json()
        if row["id"] == beef_id
    )
    assert float(final_stock["quantity_on_hand"]) == 24800

    cancellable = client.post(
        "/api/v1/inventory/physical-counts",
        headers=_admin_headers(),
        json={"branch_id": BRANCH_ID, "item_ids": [beef_id]},
    ).json()
    cancelled = client.post(
        f"/api/v1/inventory/physical-counts/{cancellable['id']}/cancel",
        headers=_admin_headers(),
        json={"reason": "Conteo abierto por error"},
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"
    assert cancelled.json()["movements"] == []


def test_admin_can_create_user_role_and_assignment() -> None:
    client = _client_with_seeded_database()

    role_response = client.post(
        "/api/v1/roles", headers=_admin_headers(), json={"name": "Cajero", "scope": "branch"}
    )
    assert role_response.status_code == 200
    role = role_response.json()
    assert role["name"] == "Cajero"
    assert role["scope"] == "branch"

    duplicate_role = client.post(
        "/api/v1/roles", headers=_admin_headers(), json={"name": "Cajero", "scope": "branch"}
    )
    assert duplicate_role.status_code == 409
    assert duplicate_role.json()["detail"]["code"] == "role_already_exists"

    user_response = client.post(
        "/api/v1/users",
        headers=_admin_headers(),
        json={"email": "cajero@kiwi.local", "display_name": "Cajero Piloto"},
    )
    assert user_response.status_code == 200
    user = user_response.json()
    assert user["email"] == "cajero@kiwi.local"
    assert user["status"] == "invited"

    assignment_response = client.post(
        f"/api/v1/users/{user['id']}/roles",
        headers=_admin_headers(),
        json={"role_id": role["id"]},
    )
    assert assignment_response.status_code == 200
    assert assignment_response.json()["branch_id"] == "018f6f73-2d0a-74f0-8f1c-000000000003"

    users_response = client.get("/api/v1/users", headers=_admin_headers())
    assert users_response.status_code == 200
    created_user = next(item for item in users_response.json() if item["id"] == user["id"])
    assert created_user["roles"][0]["role_name"] == "Cajero"

    roles_response = client.get("/api/v1/roles", headers=_admin_headers())
    assert roles_response.status_code == 200
    assert any(item["name"] == "Cajero" for item in roles_response.json())

    bootstrap_response = client.get("/api/v1/platform/bootstrap-status")
    assert bootstrap_response.status_code == 200
    assert bootstrap_response.json()["counts"]["audit_events"] == 4


def test_cash_order_and_kds_flow() -> None:
    client = _client_with_seeded_database()

    current_response = client.get("/api/v1/cash-shifts/current", headers=_admin_headers())
    assert current_response.status_code == 200
    assert current_response.json()["cash_shift"] is None

    order_without_shift = client.post(
        "/api/v1/orders",
        headers=_admin_headers(),
        json={"lines": [{"product_id": "018f6f73-2d0a-74f0-8f1c-000000000111", "quantity": 1}]},
    )
    assert order_without_shift.status_code == 409
    assert order_without_shift.json()["detail"]["code"] == "cash_shift_required"

    open_response = client.post(
        "/api/v1/cash-shifts/open", headers=_admin_headers(), json={"opening_cash_cents": 50000}
    )
    assert open_response.status_code == 200
    assert open_response.json()["status"] == "OPEN"

    duplicate_open = client.post(
        "/api/v1/cash-shifts/open", headers=_admin_headers(), json={"opening_cash_cents": 50000}
    )
    assert duplicate_open.status_code == 409
    assert duplicate_open.json()["detail"]["code"] == "cash_shift_already_open"

    order_response = client.post(
        "/api/v1/orders",
        headers=_admin_headers(),
        json={"lines": [{"product_id": "018f6f73-2d0a-74f0-8f1c-000000000111", "quantity": 2}]},
    )
    assert order_response.status_code == 200
    order_payload = order_response.json()
    assert order_payload["status"] == "ACCEPTED"
    assert order_payload["folio"] == "PILOTO-000001"
    assert order_payload["total_cents"] == 19000
    assert order_payload["lines"][0]["product_name"] == "Hamburguesa Kiwi"
    assert order_payload["production_tasks"][0]["status"] == "PENDING"

    reserved_stock_response = client.get(
        "/api/v1/inventory/stock", headers=_admin_headers()
    )
    assert reserved_stock_response.status_code == 200
    reserved_stock = reserved_stock_response.json()
    reserved_beef = next(item for item in reserved_stock if item["sku"] == "INV-BEEF")
    reserved_bun = next(item for item in reserved_stock if item["sku"] == "INV-BUN")
    assert reserved_beef["quantity_on_hand"] == 24760
    assert reserved_bun["quantity_on_hand"] == 118

    reservation_kardex = client.get(
        f"/api/v1/inventory/kardex?item_id={reserved_beef['id']}",
        headers=_admin_headers(),
    )
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

    consumed_stock_response = client.get(
        "/api/v1/inventory/stock", headers=_admin_headers()
    )
    assert consumed_stock_response.status_code == 200
    consumed_beef = next(
        item for item in consumed_stock_response.json() if item["sku"] == "INV-BEEF"
    )
    assert consumed_beef["quantity_on_hand"] == 24760

    consumption_kardex = client.get(
        f"/api/v1/inventory/kardex?item_id={reserved_beef['id']}",
        headers=_admin_headers(),
    )
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

    close_response = client.post("/api/v1/cash-shifts/close", headers=_admin_headers())
    assert close_response.status_code == 200
    assert close_response.json()["status"] == "CLOSED"


def test_next_folio_uses_max_existing_suffix_instead_of_row_count() -> None:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)

    with session_factory() as session:
        _seed(session)
        now = datetime(2026, 7, 10, 19, 45, tzinfo=UTC)
        session.execute(
            cash_shifts.insert().values(
                id="018f6f73-2d0a-74f0-8f1c-000000000701",
                organization_id="018f6f73-2d0a-74f0-8f1c-000000000001",
                branch_id=BRANCH_ID,
                register_code="CAJA-01",
                status="OPEN",
                opening_cash_cents=10000,
                opened_at=now,
                closed_at=None,
                created_at=now,
            )
        )
        for order_id, folio in [
            ("018f6f73-2d0a-74f0-8f1c-000000000711", "PILOTO-000001"),
            ("018f6f73-2d0a-74f0-8f1c-000000000712", "PILOTO-000010"),
        ]:
            session.execute(
                orders.insert().values(
                    id=order_id,
                    organization_id="018f6f73-2d0a-74f0-8f1c-000000000001",
                    branch_id=BRANCH_ID,
                    cash_shift_id="018f6f73-2d0a-74f0-8f1c-000000000701",
                    folio=folio,
                    channel="POS",
                    status="ACCEPTED",
                    total_cents=9500,
                    currency="MXN",
                    owner_name="Cliente General",
                    order_type="dine-in",
                    created_at=now,
                    accepted_at=now,
                )
            )

        assert _next_folio(session, BRANCH_ID) == "PILOTO-000011"


def test_customer_multiple_addresses_and_delivery_order_snapshot() -> None:
    client = _client_with_seeded_database()
    branch_id = BRANCH_ID
    customer_response = client.post(
        "/api/v1/customers",
        headers=_admin_headers(),
        json={
            "branch_id": branch_id,
            "name": "Renata Cliente",
            "email": "RENATA@example.com",
            "phones": [
                {"number": "669 123 4567", "is_primary": True, "whatsapp_enabled": True},
                {"number": "+52 669 765 4321", "type": "work"},
            ],
        },
    )
    assert customer_response.status_code == 200
    customer = customer_response.json()
    assert [phone["normalized_number"] for phone in customer["phones"]] == [
        "+526691234567",
        "+526697654321",
    ]

    duplicate_response = client.post(
        "/api/v1/customers",
        headers=_admin_headers(),
        json={"branch_id": branch_id, "name": "Coincidencia", "phones": [{"number": "6691234567"}]},
    )
    assert duplicate_response.status_code == 200
    duplicate = duplicate_response.json()
    assert duplicate["id"] != customer["id"]

    addresses = []
    for alias, street, is_default in [
        ("Casa", "Calle Mango", True),
        ("Oficina", "Avenida Kiwi", False),
        ("Escuela", "Calle Naranja", False),
    ]:
        response = client.post(
            f"/api/v1/customers/{customer['id']}/addresses",
            headers=_admin_headers(),
            json={
                "branch_id": branch_id,
                "alias": alias,
                "street": street,
                "exterior_number": "10",
                "neighborhood": "Centro",
                "postal_code": "82000",
                "city": "Mazatlan",
                "municipality": "Mazatlan",
                "state": "Sinaloa",
                "is_default": is_default,
            },
        )
        assert response.status_code == 200
        addresses.append(response.json())

    search = client.get(
        f"/api/v1/customers?phone=6691234567&branch_id={branch_id}", headers=_admin_headers()
    )
    assert search.status_code == 200
    assert {row["id"] for row in search.json()} == {customer["id"], duplicate["id"]}
    selected = next(row for row in search.json() if row["id"] == customer["id"])
    assert len(selected["addresses"]) == 3

    assert (
        client.post(
            "/api/v1/cash-shifts/open", headers=_admin_headers(), json={"opening_cash_cents": 50000}
        ).status_code
        == 200
    )
    order_response = client.post(
        "/api/v1/orders",
        headers=_admin_headers(),
        json={
            "branch_id": branch_id,
            "order_type": "delivery",
            "customer_id": customer["id"],
            "delivery_address_id": addresses[0]["id"],
            "lines": [{"product_id": "018f6f73-2d0a-74f0-8f1c-000000000111", "quantity": 1}],
        },
    )
    assert order_response.status_code == 200
    order = order_response.json()
    assert order["customer_snapshot"]["name"] == "Renata Cliente"
    assert order["delivery_address_snapshot"]["alias"] == "Casa"
    assert order["delivery_address_snapshot"]["street"] == "Calle Mango"

    address_update = client.put(
        f"/api/v1/customers/{customer['id']}/addresses/{addresses[0]['id']}",
        headers=_admin_headers(),
        json={"branch_id": branch_id, "street": "Calle Mango Nueva", "is_default": True},
    )
    assert address_update.status_code == 200
    customer_update = client.put(
        f"/api/v1/customers/{customer['id']}",
        headers=_admin_headers(),
        json={"branch_id": branch_id, "name": "Renata Actualizada", "customer_type": "person"},
    )
    assert customer_update.status_code == 200
    tax_response = client.put(
        f"/api/v1/customers/{customer['id']}/tax-profile",
        headers=_admin_headers(),
        json={
            "branch_id": branch_id,
            "legal_name": "RENATA CLIENTE SA DE CV",
            "tax_id": "RCL010101AB1",
            "tax_regime": "601",
            "fiscal_postal_code": "82000",
            "cfdi_use": "G03",
            "billing_email": "FACTURAS@example.com",
        },
    )
    assert tax_response.status_code == 200
    assert tax_response.json()["billing_email"] == "facturas@example.com"

    historical_orders = client.get(
        f"/api/v1/orders?branch_id={branch_id}", headers=_admin_headers()
    )
    historical = next(row for row in historical_orders.json() if row["id"] == order["id"])
    assert historical["customer_snapshot"]["name"] == "Renata Cliente"
    assert historical["delivery_address_snapshot"]["street"] == "Calle Mango"
    refreshed_customers = client.get(
        f"/api/v1/customers?phone=6691234567&branch_id={branch_id}", headers=_admin_headers()
    ).json()
    refreshed = next(row for row in refreshed_customers if row["id"] == customer["id"])
    assert refreshed["name"] == "Renata Actualizada"
    assert refreshed["addresses"][0]["street"] == "Calle Mango Nueva"
    assert refreshed["tax_profile"]["tax_id"] == "RCL010101AB1"

    repeated_response = client.post(
        f"/api/v1/orders/{order['id']}/repeat",
        headers=_admin_headers(),
        json={"register_id": "CAJA-01"},
    )
    assert repeated_response.status_code == 200
    repeated = repeated_response.json()
    assert repeated["id"] != order["id"]
    assert repeated["folio"] != order["folio"]
    assert repeated["customer_snapshot"]["name"] == "Renata Actualizada"
    assert repeated["delivery_address_snapshot"]["street"] == "Calle Mango Nueva"
    final_customer = next(
        row
        for row in client.get(
            f"/api/v1/customers?phone=6691234567&branch_id={branch_id}", headers=_admin_headers()
        ).json()
        if row["id"] == customer["id"]
    )
    assert final_customer["order_summary"]["order_count"] == 2
    assert final_customer["order_summary"]["average_ticket_cents"] == order["total_cents"]
    assert (
        final_customer["order_summary"]["frequent_products"][0]["product_name"]
        == "Hamburguesa Kiwi"
    )

    mismatch = client.post(
        "/api/v1/orders",
        headers=_admin_headers(),
        json={
            "branch_id": branch_id,
            "order_type": "delivery",
            "customer_id": duplicate["id"],
            "delivery_address_id": addresses[0]["id"],
            "lines": [{"product_id": "018f6f73-2d0a-74f0-8f1c-000000000111", "quantity": 1}],
        },
    )
    assert mismatch.status_code == 409
    assert mismatch.json()["detail"]["code"] == "customer_address_mismatch"


def test_order_cancellation_releases_reserved_inventory_before_production() -> None:
    client = _client_with_seeded_database()

    open_response = client.post(
        "/api/v1/cash-shifts/open", headers=_admin_headers(), json={"opening_cash_cents": 50000}
    )
    assert open_response.status_code == 200

    order_response = client.post(
        "/api/v1/orders",
        headers=_admin_headers(),
        json={"lines": [{"product_id": "018f6f73-2d0a-74f0-8f1c-000000000111", "quantity": 1}]},
    )
    assert order_response.status_code == 200
    order = order_response.json()

    reserved_stock_response = client.get(
        "/api/v1/inventory/stock", headers=_admin_headers()
    )
    assert reserved_stock_response.status_code == 200
    reserved_beef = next(
        item for item in reserved_stock_response.json() if item["sku"] == "INV-BEEF"
    )
    assert reserved_beef["quantity_on_hand"] == 24880

    cancel_response = client.post(
        f"/api/v1/orders/{order['id']}/cancel",
        headers=_admin_headers(),
        json={"reason": "Cliente cancela antes de cocina"},
    )
    assert cancel_response.status_code == 200
    cancelled = cancel_response.json()
    assert cancelled["status"] == "CANCELLED"
    assert cancelled["production_tasks"][0]["status"] == "CANCELLED"

    stock_response = client.get("/api/v1/inventory/stock", headers=_admin_headers())
    assert stock_response.status_code == 200
    beef = next(item for item in stock_response.json() if item["sku"] == "INV-BEEF")
    assert beef["quantity_on_hand"] == 25000

    kardex_response = client.get(
        f"/api/v1/inventory/kardex?item_id={beef['id']}", headers=_admin_headers()
    )
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
        headers=_admin_headers(),
        json={"amount_cents": 9500, "method": "cash"},
    )
    assert payment_response.status_code == 409
    assert payment_response.json()["detail"]["code"] == "order_cancelled"

    orders_response = client.get("/api/v1/orders", headers=_admin_headers())
    assert orders_response.status_code == 200
    assert orders_response.json()[0]["status"] == "CANCELLED"

    bootstrap_response = client.get("/api/v1/platform/bootstrap-status")
    assert bootstrap_response.status_code == 200
    assert bootstrap_response.json()["counts"]["inventory_movements"] == 8
    assert bootstrap_response.json()["counts"]["audit_events"] == 4


def test_order_cancellation_is_rejected_while_production_is_in_progress() -> None:
    client = _client_with_seeded_database()

    open_response = client.post(
        "/api/v1/cash-shifts/open", headers=_admin_headers(), json={"opening_cash_cents": 50000}
    )
    assert open_response.status_code == 200

    order_response = client.post(
        "/api/v1/orders",
        headers=_admin_headers(),
        json={"lines": [{"product_id": "018f6f73-2d0a-74f0-8f1c-000000000111", "quantity": 1}]},
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
        headers=_admin_headers(),
        json={"reason": "Demasiado tarde"},
    )
    assert cancel_response.status_code == 409
    assert cancel_response.json()["detail"]["code"] == "production_in_progress"


def test_post_production_cancellation_records_waste_without_restocking() -> None:
    client = _client_with_seeded_database()

    open_response = client.post(
        "/api/v1/cash-shifts/open", headers=_admin_headers(), json={"opening_cash_cents": 50000}
    )
    assert open_response.status_code == 200

    order_response = client.post(
        "/api/v1/orders",
        headers=_admin_headers(),
        json={"lines": [{"product_id": "018f6f73-2d0a-74f0-8f1c-000000000111", "quantity": 1}]},
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
        headers=_admin_headers(),
        json={"reason": "Cliente cancela pedido producido"},
    )
    assert missing_classification.status_code == 409
    assert missing_classification.json()["detail"]["code"] == "cancellation_classification_required"

    cancel_response = client.post(
        f"/api/v1/orders/{order['id']}/cancel",
        headers=_admin_headers(),
        json={"reason": "Cliente cancela pedido producido", "classification": "waste"},
    )
    assert cancel_response.status_code == 200
    cancelled = cancel_response.json()
    assert cancelled["status"] == "CANCELLED"
    assert cancelled["classification"] == "waste"
    assert cancelled["production_tasks"][0]["status"] == "COMPLETED"

    stock_response = client.get("/api/v1/inventory/stock", headers=_admin_headers())
    assert stock_response.status_code == 200
    beef = next(item for item in stock_response.json() if item["sku"] == "INV-BEEF")
    assert beef["quantity_on_hand"] == 24880

    kardex_response = client.get(
        f"/api/v1/inventory/kardex?item_id={beef['id']}", headers=_admin_headers()
    )
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
        headers=_admin_headers(),
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

    open_response = client.post(
        "/api/v1/cash-shifts/open", headers=_admin_headers(), json={"opening_cash_cents": 50000}
    )
    assert open_response.status_code == 200

    order_response = client.post(
        "/api/v1/orders",
        headers=_admin_headers(),
        json={"lines": [{"product_id": "018f6f73-2d0a-74f0-8f1c-000000000111", "quantity": 1}]},
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
        headers=_admin_headers(),
        json={"reason": "Produccion recuperable", "classification": "recovery"},
    )
    assert cancel_response.status_code == 200
    cancelled = cancel_response.json()
    assert cancelled["status"] == "CANCELLED"
    assert cancelled["classification"] == "recovery"

    stock_response = client.get("/api/v1/inventory/stock", headers=_admin_headers())
    assert stock_response.status_code == 200
    beef = next(item for item in stock_response.json() if item["sku"] == "INV-BEEF")
    assert beef["quantity_on_hand"] == 25000

    kardex_response = client.get(
        f"/api/v1/inventory/kardex?item_id={beef['id']}", headers=_admin_headers()
    )
    assert kardex_response.status_code == 200
    beef_movements = kardex_response.json()
    assert any(
        item["movement_type"] == "RECOVERY" and item["quantity_delta"] == 120
        for item in beef_movements
    )


def test_payment_cut_and_print_flow() -> None:
    client = _client_with_seeded_database()

    open_response = client.post(
        "/api/v1/cash-shifts/open", headers=_admin_headers(), json={"opening_cash_cents": 50000}
    )
    assert open_response.status_code == 200

    order_response = client.post(
        "/api/v1/orders",
        headers=_admin_headers(),
        json={"lines": [{"product_id": "018f6f73-2d0a-74f0-8f1c-000000000111", "quantity": 1}]},
    )
    assert order_response.status_code == 200
    order = order_response.json()

    mismatch_payment = client.post(
        f"/api/v1/orders/{order['id']}/payments",
        headers=_admin_headers(),
        json={"amount_cents": 9400, "method": "cash"},
    )
    assert mismatch_payment.status_code == 409
    assert mismatch_payment.json()["detail"]["code"] == "payment_total_mismatch"

    payment_response = client.post(
        f"/api/v1/orders/{order['id']}/payments",
        headers=_admin_headers(),
        json={"amount_cents": 9500, "method": "cash"},
    )
    assert payment_response.status_code == 200
    payment = payment_response.json()
    assert payment["status"] == "CONFIRMED"
    assert payment["order_status"] == "CLOSED"
    assert [job["job_type"] for job in payment["print_jobs"]] == ["ticket", "kitchen"]

    duplicate_payment = client.post(
        f"/api/v1/orders/{order['id']}/payments",
        headers=_admin_headers(),
        json={"amount_cents": 9500, "method": "cash"},
    )
    assert duplicate_payment.status_code == 409
    assert duplicate_payment.json()["detail"]["code"] == "order_already_closed"

    orders_response = client.get("/api/v1/orders", headers=_admin_headers())
    assert orders_response.status_code == 200
    assert orders_response.json()[0]["status"] == "CLOSED"

    payments_response = client.get("/api/v1/payments", headers=_admin_headers())
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

    summary_response = client.get("/api/v1/cash-shifts/summary", headers=_admin_headers())
    assert summary_response.status_code == 200
    summary = summary_response.json()["summary"]
    assert summary["sales_total_cents"] == 9500
    assert summary["payment_total_cents"] == 9500
    assert summary["cash_payment_total_cents"] == 9500
    assert summary["expected_cash_cents"] == 59500

    close_response = client.post(
        "/api/v1/cash-shifts/close",
        headers=_admin_headers(),
        json={"counted_cash_cents": 59000},
    )
    assert close_response.status_code == 200
    cut = close_response.json()["cut"]
    assert cut["expected_cash_cents"] == 59500
    assert cut["counted_cash_cents"] == 59000
    assert cut["difference_cents"] == -500


def test_sensitive_pos_endpoints_require_authenticated_actor() -> None:
    client = _client_with_seeded_database()

    current_response = client.get("/api/v1/cash-shifts/current")
    assert current_response.status_code == 401
    assert current_response.json()["detail"]["code"] == "actor_required"

    order_response = client.post(
        "/api/v1/orders",
        json={"lines": [{"product_id": "018f6f73-2d0a-74f0-8f1c-000000000111", "quantity": 1}]},
    )
    assert order_response.status_code == 401
    assert order_response.json()["detail"]["code"] == "actor_required"


def test_cashier_can_operate_pos_and_admin_dashboard_reflects_payment() -> None:
    client = _client_with_seeded_database()

    role_response = client.post(
        "/api/v1/roles",
        headers=_admin_headers(),
        json={"name": "Cajero", "scope": "branch"},
    )
    assert role_response.status_code == 200
    role = role_response.json()
    assert "cash.shift.open" in role["permissions"]
    assert "orders.create" in role["permissions"]
    assert "payments.confirm" in role["permissions"]

    user_response = client.post(
        "/api/v1/users",
        headers=_admin_headers(),
        json={
            "email": "cajero-pos@kiwi.local",
            "display_name": "Cajero POS",
            "password": "Temporal123+",
            "role_id": role["id"],
        },
    )
    assert user_response.status_code == 200

    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": "cajero-pos@kiwi.local", "password": "Temporal123+"},
    )
    assert login_response.status_code == 200
    session_payload = login_response.json()
    cashier_headers = {"Authorization": f"Bearer {session_payload['token']}"}
    assert session_payload["user"]["assigned_branch_id"] == BRANCH_ID
    assert "pos.operate" in session_payload["user"]["permissions"]
    assert "dashboard.read" not in session_payload["user"]["permissions"]

    cashier_dashboard = client.get("/api/v1/dashboard/overview", headers=cashier_headers)
    assert cashier_dashboard.status_code == 403
    assert cashier_dashboard.json()["detail"]["code"] == "permission_denied"

    open_response = client.post(
        "/api/v1/cash-shifts/open",
        headers=cashier_headers,
        json={"opening_cash_cents": 10000},
    )
    assert open_response.status_code == 200

    order_response = client.post(
        "/api/v1/orders",
        headers=cashier_headers,
        json={"lines": [{"product_id": "018f6f73-2d0a-74f0-8f1c-000000000111", "quantity": 1}]},
    )
    assert order_response.status_code == 200
    order = order_response.json()
    assert order["total_cents"] == 9500

    payment_response = client.post(
        f"/api/v1/orders/{order['id']}/payments",
        headers=cashier_headers,
        json={"amount_cents": order["total_cents"], "method": "cash"},
    )
    assert payment_response.status_code == 200
    assert payment_response.json()["status"] == "CONFIRMED"

    payments_response = client.get("/api/v1/payments", headers=cashier_headers)
    assert payments_response.status_code == 403
    assert payments_response.json()["detail"]["code"] == "permission_denied"

    dashboard_response = client.get("/api/v1/dashboard/overview", headers=_admin_headers())
    assert dashboard_response.status_code == 200
    dashboard = dashboard_response.json()
    assert dashboard["total_revenue_cents"] == 9500
    assert dashboard["total_orders"] == 1
    assert dashboard["recent_transactions"][0]["amount_cents"] == 9500


def test_cashier_cannot_operate_outside_assigned_branch() -> None:
    client = _client_with_seeded_database()

    branch_response = client.post(
        "/api/v1/branches",
        headers=_admin_headers(),
        json={"name": "Sucursal Norte", "code": "NORTE"},
    )
    assert branch_response.status_code == 200
    other_branch_id = branch_response.json()["id"]

    role_response = client.post(
        "/api/v1/roles",
        headers=_admin_headers(),
        json={"name": "Cajero", "scope": "branch"},
    )
    assert role_response.status_code == 200

    user_response = client.post(
        "/api/v1/users",
        headers=_admin_headers(),
        json={
            "email": "cajero-scope@kiwi.local",
            "display_name": "Cajero Scope",
            "password": "Temporal123+",
            "role_id": role_response.json()["id"],
        },
    )
    assert user_response.status_code == 200

    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": "cajero-scope@kiwi.local", "password": "Temporal123+"},
    )
    assert login_response.status_code == 200
    cashier_headers = {"Authorization": f"Bearer {login_response.json()['token']}"}

    denied_response = client.post(
        "/api/v1/cash-shifts/open",
        headers=cashier_headers,
        json={"opening_cash_cents": 10000, "branch_id": other_branch_id},
    )
    assert denied_response.status_code == 403
    assert denied_response.json()["detail"]["code"] == "permission_denied"


def test_pos_account_uses_assigned_branch_and_can_update_own_profile() -> None:
    client = _client_with_seeded_database()

    branch_response = client.post(
        "/api/v1/branches",
        headers=_admin_headers(),
        json={"name": "Sucursal Centro", "code": "CENTRO"},
    )
    assert branch_response.status_code == 200
    branch_id = branch_response.json()["id"]

    role_response = client.post(
        "/api/v1/roles",
        headers=_admin_headers(),
        json={"name": "Cajero", "scope": "branch"},
    )
    assert role_response.status_code == 200

    user_response = client.post(
        "/api/v1/users",
        headers=_admin_headers(),
        json={
            "email": "cajero-centro@kiwi.local",
            "display_name": "Cajero Centro",
            "password": "Temporal123+",
            "role_id": role_response.json()["id"],
            "branch_id": branch_id,
        },
    )
    assert user_response.status_code == 200
    user_id = user_response.json()["id"]

    users_response = client.get("/api/v1/users", headers=_admin_headers())
    assert users_response.status_code == 200
    created_user = next(item for item in users_response.json() if item["id"] == user_id)
    assert created_user["roles"][0]["branch_id"] == branch_id
    assert created_user["roles"][0]["branch_name"] == "Sucursal Centro"

    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": "cajero-centro@kiwi.local", "password": "Temporal123+"},
    )
    assert login_response.status_code == 200
    session_payload = login_response.json()
    cashier_headers = {"Authorization": f"Bearer {session_payload['token']}"}
    assert session_payload["user"]["assigned_branch_id"] == branch_id

    open_response = client.post(
        "/api/v1/cash-shifts/open",
        headers=cashier_headers,
        json={
            "opening_cash_cents": 10000,
            "branch_id": branch_id,
            "register_id": "CAJA-CENTRO-01",
        },
    )
    assert open_response.status_code == 200
    assert open_response.json()["branch_id"] == branch_id
    assert open_response.json()["register_code"] == "CAJA-CENTRO-01"

    order_response = client.post(
        "/api/v1/orders",
        headers=cashier_headers,
        json={
            "branch_id": branch_id,
            "register_id": "CAJA-CENTRO-01",
            "lines": [{"product_id": "018f6f73-2d0a-74f0-8f1c-000000000111", "quantity": 1}],
        },
    )
    assert order_response.status_code == 200
    order = order_response.json()
    assert order["branch_id"] == branch_id
    assert order["cash_shift_id"] == open_response.json()["id"]

    payment_response = client.post(
        f"/api/v1/orders/{order['id']}/payments",
        headers=cashier_headers,
        json={"amount_cents": order["total_cents"], "method": "cash"},
    )
    assert payment_response.status_code == 200
    assert payment_response.json()["status"] == "CONFIRMED"

    denied_response = client.post(
        "/api/v1/cash-shifts/open",
        headers=cashier_headers,
        json={
            "opening_cash_cents": 10000,
            "branch_id": BRANCH_ID,
            "register_id": "CAJA-PILOTO-01",
        },
    )
    assert denied_response.status_code == 403
    assert denied_response.json()["detail"]["code"] == "permission_denied"

    profile_response = client.put(
        f"/api/v1/users/{user_id}",
        headers=cashier_headers,
        json={
            "display_name": "Cajero Centro Actualizado",
            "email": "cajero-centro@kiwi.local",
        },
    )
    assert profile_response.status_code == 200
    assert profile_response.json()["display_name"] == "Cajero Centro Actualizado"

    dashboard_response = client.get("/api/v1/dashboard/overview", headers=_admin_headers())
    assert dashboard_response.status_code == 200
    dashboard = dashboard_response.json()
    assert dashboard["total_orders"] == 1
    assert dashboard["recent_transactions"][0]["amount_cents"] == order["total_cents"]
    notifications = dashboard["recent_notifications"]
    assert notifications[0]["action"] == "cash_shift.opened"
    assert notifications[0]["actor_name"] == "Cajero Centro Actualizado"
    assert notifications[0]["register_code"] == "CAJA-CENTRO-01"


def test_legacy_caja_role_keeps_pos_permissions() -> None:
    client = _client_with_seeded_database()

    role_response = client.post(
        "/api/v1/roles",
        headers=_admin_headers(),
        json={"name": "Caja", "scope": "branch"},
    )
    assert role_response.status_code == 200
    role = role_response.json()
    assert "pos.operate" in role["permissions"]
    assert "cash.shift.open" in role["permissions"]
    assert "payments.confirm" in role["permissions"]

    user_response = client.post(
        "/api/v1/users",
        headers=_admin_headers(),
        json={
            "email": "legacy-caja@kiwi.local",
            "display_name": "Caja Legacy",
            "password": "Temporal123+",
            "role_id": role["id"],
        },
    )
    assert user_response.status_code == 200

    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": "legacy-caja@kiwi.local", "password": "Temporal123+"},
    )
    assert login_response.status_code == 200
    session_payload = login_response.json()
    assert "Caja" in session_payload["user"]["roles"]
    assert "pos.operate" in session_payload["user"]["permissions"]
    assert session_payload["user"]["assigned_branch_id"] == BRANCH_ID

    open_response = client.post(
        "/api/v1/cash-shifts/open",
        headers={"Authorization": f"Bearer {session_payload['token']}"},
        json={"opening_cash_cents": 10000, "register_id": "CAJA-01"},
    )
    assert open_response.status_code == 200


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
    app.state.test_session_factory = session_factory
    return TestClient(app)


def _seed(session: Session) -> None:
    now = datetime(2026, 7, 7, 17, 30, tzinfo=UTC)
    organization_id = "018f6f73-2d0a-74f0-8f1c-000000000001"
    legal_entity_id = "018f6f73-2d0a-74f0-8f1c-000000000002"
    business_unit_id = "018f6f73-2d0a-74f0-8f1c-000000000015"
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
        business_units.insert(),
        [
            {
                "id": business_unit_id,
                "organization_id": organization_id,
                "legal_entity_id": legal_entity_id,
                "name": "Operaciones Kiwi",
                "code": "KIWI",
                "unit_type": "restaurant",
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
                "business_unit_id": business_unit_id,
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
            {
                "id": "018f6f73-2d0a-74f0-8f1c-000000000903",
                "code": "inventory.adjust",
                "description": "Registrar ajustes de inventario",
                "created_at": now,
            },
            {
                "id": "018f6f73-2d0a-74f0-8f1c-000000000904",
                "code": "orders.cancel",
                "description": "Cancelar pedidos",
                "created_at": now,
            },
            {
                "id": "018f6f73-2d0a-74f0-8f1c-000000000905",
                "code": "cash.shift.read",
                "description": "Consultar turnos de caja",
                "created_at": now,
            },
            {
                "id": "018f6f73-2d0a-74f0-8f1c-000000000906",
                "code": "cash.shift.open",
                "description": "Abrir turnos de caja",
                "created_at": now,
            },
            {
                "id": "018f6f73-2d0a-74f0-8f1c-000000000907",
                "code": "cash.shift.close",
                "description": "Cerrar turnos de caja",
                "created_at": now,
            },
            {
                "id": "018f6f73-2d0a-74f0-8f1c-000000000908",
                "code": "orders.read",
                "description": "Consultar pedidos POS",
                "created_at": now,
            },
            {
                "id": "018f6f73-2d0a-74f0-8f1c-000000000909",
                "code": "orders.create",
                "description": "Crear pedidos POS",
                "created_at": now,
            },
            {
                "id": "018f6f73-2d0a-74f0-8f1c-000000000910",
                "code": "payments.read",
                "description": "Consultar pagos",
                "created_at": now,
            },
            {
                "id": "018f6f73-2d0a-74f0-8f1c-000000000911",
                "code": "payments.confirm",
                "description": "Confirmar pagos POS",
                "created_at": now,
            },
            {
                "id": "018f6f73-2d0a-74f0-8f1c-000000000912",
                "code": "dashboard.read",
                "description": "Consultar dashboard operativo",
                "created_at": now,
            },
            {
                "id": "018f6f73-2d0a-74f0-8f1c-000000000913",
                "code": "pos.operate",
                "description": "Operar interfaz POS",
                "created_at": now,
            },
            {
                "id": "018f6f73-2d0a-74f0-8f1c-000000000914",
                "code": "production.manage",
                "description": "Gestionar produccion",
                "created_at": now,
            },
            {
                "id": "018f6f73-2d0a-74f0-8f1c-000000000915",
                "code": "inventory.waste",
                "description": "Registrar mermas reales",
                "created_at": now,
            },
            {
                "id": "018f6f73-2d0a-74f0-8f1c-000000000916",
                "code": "inventory.transfer.send",
                "description": "Enviar traspasos",
                "created_at": now,
            },
            {
                "id": "018f6f73-2d0a-74f0-8f1c-000000000917",
                "code": "inventory.transfer.receive",
                "description": "Recibir traspasos",
                "created_at": now,
            },
            {
                "id": "018f6f73-2d0a-74f0-8f1c-000000000918",
                "code": "inventory.count",
                "description": "Gestionar conteos físicos",
                "created_at": now,
            },
            {
                "id": "018f6f73-2d0a-74f0-8f1c-000000000919",
                "code": "cash.withdraw",
                "description": "Registrar retiros autorizados",
                "created_at": now,
            },
            {
                "id": "018f6f73-2d0a-74f0-8f1c-000000000920",
                "code": "inventory.read",
                "description": "Consultar inventario de sucursal",
                "created_at": now,
            },
            {
                "id": "018f6f73-2d0a-74f0-8f1c-000000000921",
                "code": "purchases.read",
                "description": "Consultar compras de sucursal",
                "created_at": now,
            },
            {
                "id": "018f6f73-2d0a-74f0-8f1c-000000000922",
                "code": "purchases.manage",
                "description": "Gestionar compras de sucursal",
                "created_at": now,
            },
            {
                "id": "018f6f73-2d0a-74f0-8f1c-000000000923",
                "code": "branch.admin.access",
                "description": "Entrar a administración de sucursal",
                "created_at": now,
            },
            {
                "id": "018f6f73-2d0a-74f0-8f1c-000000000924",
                "code": "branch.staff.read",
                "description": "Consultar personal de sucursal",
                "created_at": now,
            },
            {
                "id": "018f6f73-2d0a-74f0-8f1c-000000000925",
                "code": "catalog.branch.manage",
                "description": "Gestionar excepciones de catálogo por sucursal",
                "created_at": now,
            },
        ],
    )
    session.execute(
        role_permissions.insert(),
        [
            {"role_id": role_id, "permission_id": f"018f6f73-2d0a-74f0-8f1c-0000000009{suffix:02d}"}
            for suffix in range(1, 26)
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
                "output_item_id": None,
                "branch_id": None,
                "recipe_type": "sale",
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
                "valid_from": now,
                "valid_to": None,
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": fries_recipe_id,
                "organization_id": organization_id,
                "product_id": fries_product_id,
                "output_item_id": None,
                "branch_id": None,
                "recipe_type": "sale",
                "version": 1,
                "status": "active",
                "yield_quantity": 1,
                "yield_unit_id": unit_piece_id,
                "valid_from": now,
                "valid_to": None,
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": soda_recipe_id,
                "organization_id": organization_id,
                "product_id": soda_product_id,
                "output_item_id": None,
                "branch_id": None,
                "recipe_type": "sale",
                "version": 1,
                "status": "active",
                "yield_quantity": 1,
                "yield_unit_id": unit_piece_id,
                "valid_from": now,
                "valid_to": None,
                "created_at": now,
                "updated_at": now,
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
                "unit_id": unit_gram_id,
                "net_quantity": 120,
                "waste_rate": 0,
                "gross_quantity": 120,
                "sort_order": 0,
                "notes": None,
            },
            {
                "recipe_id": burger_recipe_id,
                "item_id": bun_item_id,
                "quantity_base_units": 1,
                "unit_id": unit_piece_id,
                "net_quantity": 1,
                "waste_rate": 0,
                "gross_quantity": 1,
                "sort_order": 1,
                "notes": None,
            },
            {
                "recipe_id": fries_recipe_id,
                "item_id": potato_item_id,
                "quantity_base_units": 180,
                "unit_id": unit_gram_id,
                "net_quantity": 180,
                "waste_rate": 0,
                "gross_quantity": 180,
                "sort_order": 0,
                "notes": None,
            },
            {
                "recipe_id": soda_recipe_id,
                "item_id": syrup_item_id,
                "quantity_base_units": 80,
                "unit_id": unit_ml_id,
                "net_quantity": 80,
                "waste_rate": 0,
                "gross_quantity": 80,
                "sort_order": 0,
                "notes": None,
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
    get_res = client.get("/api/v1/catalog/products", headers=_admin_headers())
    assert get_res.status_code == 200
    products = get_res.json()
    assert len(products) > 0
    # The seeded products don't have image_url, so it should be None/null
    assert all("image_url" in p for p in products)

    # 2. Update a product with an image_url
    product_id = products[0]["id"]
    update_res = client.put(
        f"/api/v1/catalog/products/{product_id}",
        headers=_admin_headers(),
        json={
            "name": products[0]["name"],
            "sku": products[0]["sku"],
            "price_cents": products[0]["price_cents"],
            "image_url": "https://example.com/test-image.png",
        },
    )
    assert update_res.status_code == 200
    assert update_res.json()["image_url"] == "https://example.com/test-image.png"

    # Verify it persists in subsequent GET request
    get_res2 = client.get("/api/v1/catalog/products", headers=_admin_headers())
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
        },
    )
    assert update_res.status_code == 200
    assert update_res.json()["display_name"] == "Miguel G. Espino"


def _login_headers(client: TestClient, email: str, password: str) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['token']}"}


def _branch_admin_fixture(client: TestClient) -> dict[str, str]:
    branch_response = client.post(
        "/api/v1/branches",
        headers=_admin_headers(),
        json={"name": "Sucursal Norte", "code": "NORTE"},
    )
    assert branch_response.status_code == 200
    branch = branch_response.json()

    supervisor_role = client.post(
        "/api/v1/roles",
        headers=_admin_headers(),
        json={"name": "Supervisor de sucursal", "scope": "branch"},
    )
    assert supervisor_role.status_code == 200
    supervisor_permissions = set(supervisor_role.json()["permissions"])
    assert {
        "branch.admin.access",
        "branch.staff.read",
        "catalog.branch.manage",
        "production.manage",
    } <= supervisor_permissions

    cashier_role = client.post(
        "/api/v1/roles",
        headers=_admin_headers(),
        json={"name": "Cajero", "scope": "branch"},
    )
    assert cashier_role.status_code == 200
    assert "branch.admin.access" not in cashier_role.json()["permissions"]

    def create_user(
        email: str,
        display_name: str,
        role_id: str,
        branch_id: str,
    ) -> str:
        response = client.post(
            "/api/v1/users",
            headers=_admin_headers(),
            json={
                "email": email,
                "display_name": display_name,
                "password": "Temporal123+",
                "role_id": role_id,
                "branch_id": branch_id,
            },
        )
        assert response.status_code == 200
        return str(response.json()["id"])

    supervisor_id = create_user(
        "supervisor.norte@kiwi.local",
        "Supervisora Norte",
        supervisor_role.json()["id"],
        branch["id"],
    )
    cashier_id = create_user(
        "cajero.norte@kiwi.local",
        "Cajero Norte",
        cashier_role.json()["id"],
        branch["id"],
    )
    outsider_id = create_user(
        "cajero.piloto@kiwi.local",
        "Cajero Piloto",
        cashier_role.json()["id"],
        BRANCH_ID,
    )
    return {
        "branch_id": branch["id"],
        "warehouse_id": branch["warehouse"]["id"],
        "supervisor_id": supervisor_id,
        "cashier_id": cashier_id,
        "outsider_id": outsider_id,
    }


def test_branch_admin_session_and_scope_guards() -> None:
    client = _client_with_seeded_database()
    fixture = _branch_admin_fixture(client)
    supervisor_headers = _login_headers(
        client, "supervisor.norte@kiwi.local", "Temporal123+"
    )

    assert client.get("/api/v1/auth/session").status_code == 401
    assert client.get(
        "/api/v1/auth/session", headers={"Authorization": "Bearer invalid"}
    ).status_code == 401
    assert client.get("/api/v1/branches").status_code == 401

    session_response = client.get("/api/v1/auth/session", headers=supervisor_headers)
    assert session_response.status_code == 200
    profile = session_response.json()
    assert profile["scope"] == {
        "level": "branch",
        "assigned_branch_id": fixture["branch_id"],
        "allowed_branch_ids": [fixture["branch_id"]],
    }
    assert profile["active_branch"]["id"] == fixture["branch_id"]
    assert profile["active_branch"]["business_unit"]["unit_type"] == "restaurant"
    assert profile["active_branch"]["warehouse"]["id"] == fixture["warehouse_id"]
    assert "branch.admin.access" in profile["permissions"]
    assert "password_hash" not in str(profile)
    assert "password_salt" not in str(profile)

    wrong_branch = client.get(
        f"/api/v1/branch-administration/context?branch_id={BRANCH_ID}",
        headers=supervisor_headers,
    )
    assert wrong_branch.status_code == 403
    assert wrong_branch.json()["detail"]["code"] == "permission_denied"

    cashier_headers = _login_headers(client, "cajero.norte@kiwi.local", "Temporal123+")
    cashier_context = client.get(
        "/api/v1/branch-administration/context", headers=cashier_headers
    )
    assert cashier_context.status_code == 403
    assert cashier_context.json()["detail"]["code"] == "permission_denied"

    delete_response = client.delete(
        f"/api/v1/users/{fixture['supervisor_id']}", headers=_admin_headers()
    )
    assert delete_response.status_code == 200
    assert client.get("/api/v1/auth/session", headers=supervisor_headers).status_code == 403


def test_branch_admin_staff_availability_and_audit_are_branch_scoped() -> None:
    client = _client_with_seeded_database()
    fixture = _branch_admin_fixture(client)
    headers = _login_headers(client, "supervisor.norte@kiwi.local", "Temporal123+")

    staff_response = client.get(
        "/api/v1/branch-administration/staff", headers=headers
    )
    assert staff_response.status_code == 200
    staff_ids = {row["id"] for row in staff_response.json()}
    assert fixture["supervisor_id"] in staff_ids
    assert fixture["cashier_id"] in staff_ids
    assert fixture["outsider_id"] not in staff_ids
    assert "password" not in str(staff_response.json()).lower()

    catalog_response = client.get(
        "/api/v1/branch-administration/catalog/products", headers=headers
    )
    assert catalog_response.status_code == 200
    product = catalog_response.json()[0]
    assert product["has_local_override"] is False
    assert product["availability_source"] == "central"
    assert product["effective_availability"] is True

    missing = client.put(
        "/api/v1/branch-administration/catalog/products/missing/availability",
        headers=headers,
        json={"action": "unavailable"},
    )
    assert missing.status_code == 404
    assert missing.json()["detail"]["code"] == "product_not_found"

    unavailable = client.put(
        f"/api/v1/branch-administration/catalog/products/{product['id']}/availability",
        headers=headers,
        json={"action": "unavailable"},
    )
    assert unavailable.status_code == 200
    assert unavailable.json()["effective_availability"] is False
    branch_catalog = client.get(
        "/api/v1/branch-administration/catalog/products", headers=headers
    ).json()
    changed = next(row for row in branch_catalog if row["id"] == product["id"])
    assert changed["has_local_override"] is True
    assert changed["availability_source"] == "branch_override"
    assert changed["sellable"] is False

    inherited = client.put(
        f"/api/v1/branch-administration/catalog/products/{product['id']}/availability",
        headers=headers,
        json={"action": "inherit"},
    )
    assert inherited.status_code == 200
    assert inherited.json()["has_local_override"] is False

    session_factory = client.app.state.test_session_factory
    with session_factory() as session:
        override = session.execute(
            branch_product_availability.select().where(
                branch_product_availability.c.branch_id == fixture["branch_id"],
                branch_product_availability.c.product_id == product["id"],
            )
        ).first()
        assert override is None
        audit_rows = session.execute(
            audit_events.select().where(
                audit_events.c.branch_id == fixture["branch_id"],
                audit_events.c.action == "branch_product_availability.updated",
            )
        ).mappings().all()
        assert len(audit_rows) == 2
        assert audit_rows[0]["payload"]["previous"] is None
        assert audit_rows[0]["payload"]["new"] is False


def test_branch_inventory_reads_do_not_leak_another_branch() -> None:
    client = _client_with_seeded_database()
    fixture = _branch_admin_fixture(client)
    headers = _login_headers(client, "supervisor.norte@kiwi.local", "Temporal123+")
    now = datetime(2026, 7, 12, 22, 0, tzinfo=UTC)
    beef_item_id = "018f6f73-2d0a-74f0-8f1c-000000000311"
    gram_unit_id = "018f6f73-2d0a-74f0-8f1c-000000000301"

    session_factory = client.app.state.test_session_factory
    with session_factory() as session:
        session.execute(
            inventory_movements.insert().values(
                id="018f6f73-2d0a-74f0-8f1c-000000009901",
                organization_id="018f6f73-2d0a-74f0-8f1c-000000000001",
                branch_id=fixture["branch_id"],
                warehouse_id=fixture["warehouse_id"],
                item_id=beef_item_id,
                movement_type="OPENING_BALANCE",
                quantity_delta=7,
                unit_id=gram_unit_id,
                reason="Aislamiento BA-001",
                source_type="test",
                created_at=now,
            )
        )
        session.commit()

    stock_response = client.get("/api/v1/inventory/stock", headers=headers)
    assert stock_response.status_code == 200
    stock = stock_response.json()
    assert stock
    assert {row["branch_id"] for row in stock} == {fixture["branch_id"]}
    beef = next(row for row in stock if row["id"] == beef_item_id)
    assert beef["quantity_on_hand"] == 7

    kardex_response = client.get("/api/v1/inventory/kardex", headers=headers)
    assert kardex_response.status_code == 200
    assert {row["branch_id"] for row in kardex_response.json()} == {fixture["branch_id"]}

    forged = client.get(
        f"/api/v1/inventory/stock?branch_id={BRANCH_ID}", headers=headers
    )
    assert forged.status_code == 403


def test_branch_supervisor_cannot_mutate_central_catalog_or_identity() -> None:
    client = _client_with_seeded_database()
    fixture = _branch_admin_fixture(client)
    headers = _login_headers(client, "supervisor.norte@kiwi.local", "Temporal123+")

    product_response = client.post(
        "/api/v1/catalog/products",
        headers=headers,
        json={
            "name": "Producto no autorizado",
            "sku": "NO-AUTH",
            "category_name": "Comida",
            "station": "kitchen",
            "price_cents": 100,
        },
    )
    assert product_response.status_code == 403

    user_response = client.post(
        "/api/v1/users",
        headers=headers,
        json={"email": "forbidden@kiwi.local", "display_name": "Prohibido"},
    )
    assert user_response.status_code == 403
    assert client.get("/api/v1/branches", headers=headers).status_code == 403

    context = client.get(
        "/api/v1/branch-administration/context", headers=headers
    )
    assert context.status_code == 200
    assert context.json()["id"] == fixture["branch_id"]

    legal_entity_id = "018f6f73-2d0a-74f0-8f1c-000000000002"
    for unit_type in ("bakery", "production"):
        response = client.post(
            "/api/v1/business-units",
            headers=_admin_headers(),
            json={
                "name": f"Unidad {unit_type}",
                "code": unit_type.upper(),
                "unit_type": unit_type,
                "legal_entity_id": legal_entity_id,
            },
        )
        assert response.status_code == 200
        assert response.json()["unit_type"] == unit_type

    invalid = client.post(
        "/api/v1/business-units",
        headers=_admin_headers(),
        json={
            "name": "Unidad inválida",
            "code": "INVALID",
            "unit_type": "factory",
            "legal_entity_id": legal_entity_id,
        },
    )
    assert invalid.status_code == 409
    assert invalid.json()["detail"]["code"] == "invalid_business_unit_type"
