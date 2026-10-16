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
    cfg_resp = client.post(
        "/api/v1/integrations/whatsapp/config",
        json={"is_enabled": True, "auto_accept": False},
        headers=auth_headers,
    )
    secret = cfg_resp.json().get("webhook_secret")

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
        headers={"Authorization": f"Bearer {secret}"},
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


# ---------------------------------------------------------------------------
# TDD-TC-402: Autogeneración, Preservación y Regeneración de Webhook Secret
# ---------------------------------------------------------------------------


def test_tc402_whatsapp_autogenerate_and_regenerate_webhook_secret(client, test_db, auth_headers):
    # 1. Al consultar configuración por primera vez sin registro en base de datos,
    # debe autogenerar un webhook_secret válido que comience con 'whsec_'
    get_resp = client.get("/api/v1/integrations/whatsapp/config", headers=auth_headers)
    assert get_resp.status_code == 200
    cfg1 = get_resp.json()
    secret1 = cfg1.get("webhook_secret")
    assert secret1 is not None
    assert secret1.startswith("whsec_")
    assert len(secret1) > 10

    # 2. Al guardar la configuración sin modificar el webhook_secret (o enviando string vacío),
    # el secreto existente debe preservarse y no borrarse ni quedar en blanco.
    put_resp = client.put(
        "/api/v1/integrations/whatsapp/config",
        json={
            "is_enabled": True,
            "environment": "production",
            "client_id": "phone_12345",
            "webhook_secret": "",  # Formulario enviado sin tocar secreto
            "master_prompt": "Prompt de prueba",
        },
        headers=auth_headers,
    )
    assert put_resp.status_code == 200
    cfg2 = put_resp.json()
    assert cfg2.get("webhook_secret") == secret1
    assert cfg2.get("is_enabled") is True

    # 3. Al llamar al endpoint de regeneración explícita, debe generar un nuevo secreto con 'whsec_'
    # diferente al anterior y persistirlo en la base de datos.
    regen_resp = client.post(
        "/api/v1/integrations/whatsapp/regenerate-secret",
        headers=auth_headers,
    )
    assert regen_resp.status_code == 200
    regen_data = regen_resp.json()
    secret2 = regen_data["webhook_secret"]
    assert secret2.startswith("whsec_")
    assert secret2 != secret1

    # Verificar que al volver a consultar la configuración persista el nuevo secreto
    get_resp_after = client.get("/api/v1/integrations/whatsapp/config", headers=auth_headers)
    assert get_resp_after.status_code == 200
    assert get_resp_after.json()["webhook_secret"] == secret2


# ---------------------------------------------------------------------------
# TDD-TC-403: Verificación GET de Meta / Asistto y Compatibilidad Dual de Rutas
# ---------------------------------------------------------------------------


def test_tc403_meta_webhook_get_verification_and_dual_routing(client, test_db, auth_headers):
    # Configure webhook secret
    secret = "whsec_meta_handshake_secret_123"
    client.put(
        "/api/v1/integrations/whatsapp/config",
        json={"is_enabled": True, "webhook_secret": secret},
        headers=auth_headers,
    )

    challenge_val = "1158201444983271"

    # 1. GET con /api/v1 y token correcto -> 200 con challenge en texto plano
    resp_api = client.get(
        f"/api/v1/integrations/whatsapp/webhook?hub.mode=subscribe&hub.challenge={challenge_val}&hub.verify_token={secret}"
    )
    assert resp_api.status_code == 200
    assert resp_api.text == challenge_val

    # 2. GET con /v1 (ruta de compatibilidad sin /api) -> 200 con challenge en texto plano
    resp_v1 = client.get(
        f"/v1/integrations/whatsapp/webhook?hub.mode=subscribe&hub.challenge={challenge_val}&hub.verify_token={secret}"
    )
    assert resp_v1.status_code == 200
    assert resp_v1.text == challenge_val

    # 3. GET con token incorrecto -> 403 Forbidden
    resp_forbidden = client.get(
        f"/api/v1/integrations/whatsapp/webhook?hub.mode=subscribe&hub.challenge={challenge_val}&hub.verify_token=wrong_token"
    )
    assert resp_forbidden.status_code == 403


# ---------------------------------------------------------------------------
# TDD-TC-404: Respuesta Conversacional Inteligente y Despacho Saliente
# ---------------------------------------------------------------------------


def test_tc404_conversational_message_reply_and_outbound_dispatch(client, test_db, auth_headers):
    secret = "whsec_convo_secret_999"
    client.put(
        "/api/v1/integrations/whatsapp/config",
        json={
            "is_enabled": True,
            "webhook_secret": secret,
            "return_url": "https://mock.localhost/return-asistto",
            "client_secret": "asistto_bearer_outbound",
            "master_prompt": "Eres el asistente saludable de Kiwi. Saluda a Carlos y recomienda ensaladas.",
        },
        headers=auth_headers,
    )

    # 1. Mensaje de Carlos Mendoza pidiendo opciones
    msg_payload = {
        "event": "message",
        "from": "3312345678",
        "message": "Hola, qué opciones tienen?",
    }
    resp = client.post(
        "/api/v1/integrations/whatsapp/webhook",
        json=msg_payload,
        headers={"Authorization": f"Bearer {secret}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["event_type"] == "MESSAGE"
    assert data["customer"]["found"] is True
    assert data["customer"]["name"] == "Carlos Mendoza"
    assert data["reply"] is not None
    assert "Carlos" in data["reply"]
    assert "Kiwi" in data["reply"]
    assert data["dispatched"] is True

    # 2. Mensaje enviado a la ruta de compatibilidad /v1/...
    resp_v1 = client.post(
        "/v1/integrations/whatsapp/webhook",
        json=msg_payload,
        headers={"Authorization": f"Bearer {secret}"},
    )
    assert resp_v1.status_code == 200
    data_v1 = resp_v1.json()
    assert data_v1["status"] == "ok"
    assert data_v1["customer"]["found"] is True

    # 3. Formato anidado de Meta Cloud API con mensaje
    meta_payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "waba_1",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "contacts": [{"wa_id": "3312345678", "profile": {"name": "Carlos"}}],
                            "messages": [
                                {
                                    "from": "3312345678",
                                    "id": "wamid.HBgL",
                                    "text": {"body": "Menú por favor"},
                                    "type": "text",
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }
    resp_meta = client.post(
        "/api/v1/integrations/whatsapp/webhook",
        json=meta_payload,
        headers={"Authorization": f"Bearer {secret}"},
    )
    assert resp_meta.status_code == 200
    meta_data = resp_meta.json()
    assert meta_data["status"] == "ok"
    assert "Menú" in meta_data["reply"] or "Kiwi" in meta_data["reply"]

    # 4. Notificación de entrega / lectura de Meta (statuses) no debe reaccionar ni fallar
    status_payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "waba_1",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "statuses": [
                                {"id": "wamid.HBgL", "status": "delivered", "recipient_id": "3312345678"}
                            ]
                        },
                    }
                ],
            }
        ],
    }
    resp_status = client.post(
        "/api/v1/integrations/whatsapp/webhook",
        json=status_payload,
        headers={"Authorization": f"Bearer {secret}"},
    )
    assert resp_status.status_code == 200
    assert resp_status.json()["event_type"] == "STATUS_RECEIPT"


# ---------------------------------------------------------------------------
# TDD-TC-405: Interpolación de Variables en Tiempo de Ejecución (Menú con Precios, Sucursales y Cliente)
# ---------------------------------------------------------------------------


def test_tc405_master_prompt_interpolation_and_live_db_context(client, test_db, auth_headers):
    now = datetime.now(timezone.utc)
    # Seed official price for Hamburguesa Clásica ($145.00 MXN = 14500 cents)
    test_db.execute(
        models.price_versions.insert().values(
            id=str(uuid.uuid4()),
            organization_id=ORGANIZATION_ID,
            product_id=PRODUCT_ID,
            price_cents=14500,
            currency="MXN",
            valid_from=now,
            valid_to=None,
            created_at=now,
        )
    )
    test_db.commit()

    adapter = WhatsAppAdapter()
    ctx = adapter.build_runtime_context(
        session=test_db,
        organization_id=ORGANIZATION_ID,
        sender_phone="5213312345678",
        payload={"from": "5213312345678", "message": "Qué tienen en el menú?"},
        default_prep_time_minutes=25,
    )

    assert ctx["customer_found"] is True
    assert ctx["customer_name"] == "Carlos Mendoza"
    assert "Av. Hidalgo #123" in ctx["delivery_address"]
    assert "Hamburguesa Clásica — $145.00 MXN" in ctx["menu_items"]
    assert "Sucursal Principal (SUC01)" in ctx["branches"]

    raw_prompt = (
        "Hola {customer_name}, tu dirección es {delivery_address}. "
        "Menú: {menu_items}. Favoritos: {favorite_dishes}. "
        "Sucursales: {active_branch}. Tiempo: {default_prep_time_minutes} min."
    )
    rendered = adapter.render_system_prompt(
        system_prompt=raw_prompt,
        customer_name=ctx["customer_name"],
        menu_items=ctx["menu_items"],
        context=ctx,
    )

    assert "{customer_name}" not in rendered
    assert "{menu_items}" not in rendered
    assert "{delivery_address}" not in rendered
    assert "{favorite_dishes}" not in rendered
    assert "{active_branch}" not in rendered
    assert "{default_prep_time_minutes}" not in rendered
    assert "Carlos Mendoza" in rendered
    assert "$145.00 MXN" in rendered
    assert "Sucursal Principal" in rendered

