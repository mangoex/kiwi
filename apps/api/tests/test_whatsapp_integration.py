# SEC001-SYNTHETIC-FIXTURE provenance=restaurantos-whatsapp-asistto-fixtures-v1
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from restaurant_os import models
from restaurant_os.auth import create_session_token
from restaurant_os.config import get_settings
from restaurant_os.database import get_session
from restaurant_os.integrations import WhatsAppAdapter
from restaurant_os.main import create_app
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

app = create_app()

ORGANIZATION_ID = "018f6f73-2d0a-74f0-8f1c-000000000001"
BRANCH_ID = "018f6f73-2d0a-74f0-8f1c-000000000002"
USER_ID = "018f6f73-2d0a-74f0-8f1c-000000000003"
ROLE_ID = "018f6f73-2d0a-74f0-8f1c-000000000004"
CUSTOMER_ID = "018f6f73-2d0a-74f0-8f1c-000000000005"
PHONE_ID = "018f6f73-2d0a-74f0-8f1c-000000000006"
PRODUCT_ID = "018f6f73-2d0a-74f0-8f1c-000000000007"


@pytest.fixture
def test_db():
    engine = create_engine(
        "sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    models.metadata.create_all(engine)
    SessionFactory = sessionmaker(bind=engine, expire_on_commit=False)
    session = SessionFactory()

    # Seed base organization and branch
    now = datetime.now(timezone.utc)
    session.execute(
        models.organizations.insert().values(
            id=ORGANIZATION_ID,
            name="Kiwi Corporativo",
            status="active",
            created_at=now,
            updated_at=now,
        )
    )
    session.execute(
        models.legal_entities.insert().values(
            id=str(uuid.uuid4()),
            organization_id=ORGANIZATION_ID,
            name="Kiwi SA de CV",
            created_at=now,
            updated_at=now,
        )
    )
    legal_id = session.execute(models.legal_entities.select()).scalar_one()
    session.execute(
        models.business_units.insert().values(
            id=str(uuid.uuid4()),
            organization_id=ORGANIZATION_ID,
            legal_entity_id=legal_id,
            name="Kiwi Fast Food",
            code="KFF",
            unit_type="restaurant",
            created_at=now,
            updated_at=now,
        )
    )
    bu_id = session.execute(models.business_units.select()).scalar_one()
    session.execute(
        models.branches.insert().values(
            id=BRANCH_ID,
            organization_id=ORGANIZATION_ID,
            legal_entity_id=legal_id,
            business_unit_id=bu_id,
            name="Sucursal Principal",
            code="SUC01",
            status="active",
            created_at=now,
            updated_at=now,
        )
    )
    session.execute(
        models.users.insert().values(
            id=USER_ID,
            organization_id=ORGANIZATION_ID,
            email="admin@kiwi.com",
            display_name="Admin",
            status="active",
            created_at=now,
            updated_at=now,
        )
    )
    session.execute(
        models.roles.insert().values(
            id=ROLE_ID,
            organization_id=ORGANIZATION_ID,
            name="Dueño",
            scope="organization",
            created_at=now,
        )
    )
    session.execute(
        models.user_roles.insert().values(user_id=USER_ID, role_id=ROLE_ID, branch_id=BRANCH_ID)
    )
    for perm in ["admin.manage", "orders.read", "orders.create", "orders.manage"]:
        perm_id = str(uuid.uuid4())
        session.execute(
            models.permissions.insert().values(
                id=perm_id, code=perm, description=perm, created_at=now
            )
        )
        session.execute(
            models.role_permissions.insert().values(role_id=ROLE_ID, permission_id=perm_id)
        )

    # Seed product catalog
    cat_id = str(uuid.uuid4())
    session.execute(
        models.product_categories.insert().values(
            id=cat_id,
            organization_id=ORGANIZATION_ID,
            name="Hamburguesas",
            created_at=now,
            updated_at=now,
        )
    )
    session.execute(
        models.products.insert().values(
            id=PRODUCT_ID,
            organization_id=ORGANIZATION_ID,
            category_id=cat_id,
            name="Hamburguesa Clásica",
            sku="HAM-01",
            status="active",
            station="kitchen",
            created_at=now,
            updated_at=now,
        )
    )

    # Seed CRM customer with phone and address
    session.execute(
        models.customers.insert().values(
            id=CUSTOMER_ID,
            organization_id=ORGANIZATION_ID,
            name="Carlos Mendoza",
            email="carlos@example.com",
            customer_type="person",
            status="active",
            created_at=now,
            updated_at=now,
        )
    )
    session.execute(
        models.customer_phones.insert().values(
            id=PHONE_ID,
            customer_id=CUSTOMER_ID,
            captured_number="3312345678",
            normalized_number="3312345678",
            phone_type="mobile",
            is_primary=True,
            whatsapp_enabled=True,
            is_verified=True,
            status="active",
            created_at=now,
            updated_at=now,
        )
    )
    session.execute(
        models.customer_addresses.insert().values(
            id=str(uuid.uuid4()),
            customer_id=CUSTOMER_ID,
            alias="Casa",
            street="Av. Hidalgo",
            exterior_number="123",
            neighborhood="Americana",
            postal_code="44100",
            city="Guadalajara",
            municipality="Guadalajara",
            state="Jalisco",
            country="MX",
            references="Portón negro, timbre 2",
            is_default=True,
            status="active",
            created_at=now,
            updated_at=now,
        )
    )

    session.commit()
    yield session
    session.close()


@pytest.fixture
def auth_headers():
    token = create_session_token({"sub": USER_ID}, get_settings().secret_key)
    return {"Authorization": f"Bearer {token}"}



@pytest.fixture
def client(test_db):
    def override_get_session():
        try:
            yield test_db
        finally:
            pass

    app.dependency_overrides[get_session] = override_get_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# TDD-TC-398: Autenticación de Webhook y Control de Idempotencia
# ---------------------------------------------------------------------------


def test_tc398_whatsapp_webhook_authentication_and_idempotency(client, test_db, auth_headers):
    secret = "asistto_test_secret_key_123"
    client.post(
        "/api/v1/integrations/whatsapp/config",
        json={
            "is_enabled": True,
            "webhook_secret": secret,
            "return_url": "https://asistto.humanio.ai/api/v1/meta/whatsapp/webhook/kiwi-return",
            "auto_accept": False,
        },
        headers=auth_headers,
    )

    order_payload = {
        "event_type": "NEW_ORDER",
        "order_id": "wa_order_tc398_abc",
        "display_id": "W001",
        "customer": {"name": "Carlos Mendoza", "phone": "3312345678"},
        "delivery_address": "Av. Hidalgo 123",
        "items": [
            {
                "item_id": "item_1",
                "name": "Hamburguesa Clásica",
                "quantity": 1,
                "unit_price_cents": 12000,
            }
        ],
        "total_cents": 12000,
        "currency": "MXN",
    }
    raw_body = json.dumps(order_payload).encode("utf-8")

    # 1. Invalid token / signature -> 401
    resp_invalid = client.post(
        "/api/v1/integrations/whatsapp/webhook",
        content=raw_body,
        headers={"Authorization": "Bearer wrong_secret", "Content-Type": "application/json"},
    )
    assert resp_invalid.status_code == 401

    # 2. Valid bearer token -> 200
    resp_valid = client.post(
        "/api/v1/integrations/whatsapp/webhook",
        content=raw_body,
        headers={"Authorization": f"Bearer {secret}", "Content-Type": "application/json"},
    )
    assert resp_valid.status_code == 200
    data = resp_valid.json()
    assert data["status"] == "ok"
    assert data["result"]["status"] == "created"
    order_id = data["result"]["order_id"]

    # 3. Duplicate payload -> Idempotent already_processed
    resp_duplicate = client.post(
        "/api/v1/integrations/whatsapp/webhook",
        content=raw_body,
        headers={"Authorization": f"Bearer {secret}", "Content-Type": "application/json"},
    )
    assert resp_duplicate.status_code == 200
    dup_data = resp_duplicate.json()
    assert dup_data["result"]["status"] == "already_processed"
    assert dup_data["result"]["order_id"] == order_id


# ---------------------------------------------------------------------------
# TDD-TC-399: Identificación del Cliente, Dirección y Favoritos
# ---------------------------------------------------------------------------


def test_tc399_customer_identification_and_address_lookup(test_db):
    adapter = WhatsAppAdapter()

    # Match by 10-digit national number
    customer = adapter.lookup_customer(test_db, ORGANIZATION_ID, "3312345678")
    assert customer is not None
    assert customer["found"] is True
    assert customer["name"] == "Carlos Mendoza"
    assert len(customer["addresses"]) > 0
    assert "Hidalgo" in customer["addresses"][0]["street"]

    # Match by E.164 international format (+52 1 33 1234 5678 or +52 33 1234 5678)
    customer_intl = adapter.lookup_customer(test_db, ORGANIZATION_ID, "+523312345678")
    assert customer_intl is not None
    assert customer_intl["found"] is True
    assert customer_intl["customer_id"] == CUSTOMER_ID

    # Non-existent customer -> returns found: False without error
    unknown = adapter.lookup_customer(test_db, ORGANIZATION_ID, "5500000000")
    assert unknown is not None
    assert unknown["found"] is False


# ---------------------------------------------------------------------------
# TDD-TC-400: Persistencia de Orden de WhatsApp con Caja Cerrada
# ---------------------------------------------------------------------------


def test_tc400_whatsapp_order_persistence_with_closed_shift(client, test_db, auth_headers):
    # Setup mapping of WA to main branch
    client.post(
        "/api/v1/integrations/whatsapp/stores",
        json={"branch_id": BRANCH_ID, "external_store_id": "wa_branch_01", "is_active": True},
        headers=auth_headers,
    )

    # Disable auto_accept so it stays PENDING
    client.post(
        "/api/v1/integrations/whatsapp/config",
        json={"is_enabled": True, "auto_accept": False},
        headers=auth_headers,
    )

    # Simulate WhatsApp order webhook
    payload = {
        "event_type": "NEW_ORDER",
        "order_id": "wa_order_shift_closed_101",
        "display_id": "W101",
        "store_id": "wa_branch_01",
        "customer": {"name": "Carlos Mendoza", "phone": "3312345678"},
        "delivery_address": "Av. Hidalgo 123",
        "delivery_notes": "Dejar con el portero",
        "items": [
            {
                "item_id": "item_1",
                "name": "Hamburguesa Clásica",
                "quantity": 2,
                "unit_price_cents": 12000,
            }
        ],
        "total_cents": 24000,
        "currency": "MXN",
    }

    resp = client.post(
        "/api/v1/integrations/whatsapp/webhook",
        json=payload,
    )
    assert resp.status_code == 200
    res_data = resp.json()["result"]
    assert res_data["status"] == "created"
    order_id = res_data["order_id"]

    # Verify order in DB: cash_shift_id is None, channel is WHATSAPP, branch_id is BRANCH_ID
    order_row = test_db.execute(
        models.orders.select().where(models.orders.c.id == order_id)
    ).mappings().first()
    assert order_row is not None
    assert order_row["cash_shift_id"] is None
    assert order_row["channel"] == "WHATSAPP"
    assert order_row["branch_id"] == BRANCH_ID
    assert order_row["status"] == "PENDING"
    assert order_row["customer_id"] == CUSTOMER_ID

    # Verify POS list includes this order
    pos_resp = client.get(
        f"/api/v1/pos/whatsapp/orders?branch_id={BRANCH_ID}",
        headers=auth_headers,
    )
    assert pos_resp.status_code == 200
    pos_orders = pos_resp.json()
    assert any(o["id"] == order_id for o in pos_orders)


# ---------------------------------------------------------------------------
# TDD-TC-401: Configuración en Administrador y Master Prompt
# ---------------------------------------------------------------------------


def test_tc401_whatsapp_admin_config_and_outbound_dispatch(client, test_db, auth_headers):
    # Save config with master_prompt and return_url
    prompt_text = (
        "Eres el sommelier virtual de Kiwi. Conoce a Carlos, recomiéndale sus hamburguesas favoritas."
    )
    return_url = "https://asistto.humanio.ai/api/v1/meta/whatsapp/webhook/kiwi-return"

    put_resp = client.put(
        "/api/v1/integrations/whatsapp/config",
        json={
            "is_enabled": True,
            "environment": "production",
            "client_id": "asistto_waba_123",
            "webhook_secret": "my_secret_token",
            "return_url": return_url,
            "master_prompt": prompt_text,
            "auto_accept": False,
        },
        headers=auth_headers,
    )
    assert put_resp.status_code == 200

    # Retrieve config
    get_resp = client.get("/api/v1/integrations/whatsapp/config", headers=auth_headers)
    assert get_resp.status_code == 200
    cfg = get_resp.json()
    assert cfg["is_enabled"] is True
    assert cfg["return_url"] == return_url
    assert cfg["master_prompt"] == prompt_text
    assert cfg["client_id"] == "asistto_waba_123"

    # Test outgoing dispatch with adapter
    adapter = WhatsAppAdapter()
    sent = adapter.dispatch_outgoing_response(
        return_url="https://mock.localhost/return",
        outgoing_secret="test_token",
        recipient_phone="3312345678",
        message_text="¡Hola Carlos! Tu pedido ha sido recibido.",
    )
    assert sent is True
