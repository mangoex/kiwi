from collections.abc import Generator
from datetime import UTC, datetime

from fastapi.testclient import TestClient
from restaurant_os.database import get_session
from restaurant_os.main import create_app
from restaurant_os.models import (
    audit_events,
    branch_product_availability,
    branches,
    legal_entities,
    metadata,
    organizations,
    price_versions,
    product_categories,
    products,
    roles,
    user_roles,
    users,
    warehouses,
)
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


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
        users.insert(),
        [
            {
                "id": user_id,
                "organization_id": organization_id,
                "email": "admin@kiwi.local",
                "display_name": "Administrador Kiwi",
                "status": "invited",
                "created_at": now,
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
    session.commit()
