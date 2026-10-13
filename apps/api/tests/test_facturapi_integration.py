# SEC001-SYNTHETIC-FIXTURE provenance=restaurantos-facturapi-mock-key-fixtures-v1
"""Synthetic legacy integration fixtures; fiscal authority is PRD-FR-276.

These fixtures do not certify the new eligibility, authority or recovery contract.
"""

import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from fiscal_test_support import configuration_payload, configure_issuer, encryption_environment
from restaurant_os import models
from restaurant_os.auth import create_session_token
from restaurant_os.config import get_settings
from restaurant_os.database import get_session
from restaurant_os.invoicing import emitters
from restaurant_os.invoicing.facturapi_client import FacturapiClient
from restaurant_os.invoicing.service import InvoicingService
from restaurant_os.main import create_app
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

app = create_app()

ORGANIZATION_ID = "018f6f73-2d0a-74f0-8f1c-000000000001"
BRANCH_ID = "018f6f73-2d0a-74f0-8f1c-000000000002"
USER_ID = "018f6f73-2d0a-74f0-8f1c-000000000003"
ROLE_ID = "018f6f73-2d0a-74f0-8f1c-000000000004"


@pytest.fixture
def test_db():
    engine = create_engine(
        "sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    models.metadata.create_all(engine)
    SessionFactory = sessionmaker(bind=engine, expire_on_commit=False)
    session = SessionFactory()

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
    for perm in ["admin.manage", "orders.read", "orders.create", "catalog.manage"]:
        perm_id = str(uuid.uuid4())
        session.execute(
            models.permissions.insert().values(
                id=perm_id, code=perm, description=perm, created_at=now
            )
        )
        session.execute(
            models.role_permissions.insert().values(role_id=ROLE_ID, permission_id=perm_id)
        )

    session.commit()
    yield engine, session
    session.close()


@pytest.fixture
def client(test_db):
    engine, _ = test_db
    SessionFactory = sessionmaker(bind=engine, expire_on_commit=False)

    def override_get_session():
        s = SessionFactory()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_session] = override_get_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers():
    token = create_session_token({"sub": USER_ID}, get_settings().secret_key)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def invoicing_svc():
    return InvoicingService()


@pytest.fixture
def fiscal_actor(test_db, monkeypatch):
    """Positive legacy cases receive explicit fiscal capabilities, never a role-name bypass."""
    _, session = test_db
    for code in (
        "invoicing.read",
        "invoicing.issue",
        "invoicing.cancel",
        "invoicing.receipt.create",
        "invoicing.config.manage",
    ):
        permission = str(uuid.uuid4())
        session.execute(
            models.permissions.insert().values(
                id=permission,
                code=code,
                description=code,
                created_at=datetime.now(timezone.utc),
            )
        )
        session.execute(
            models.role_permissions.insert().values(role_id=ROLE_ID, permission_id=permission)
        )
    session.commit()
    encryption_environment(monkeypatch)
    # The test explicitly injects a synthetic provider; runtime factories remain fail closed.
    monkeypatch.setattr(
        InvoicingService, "get_client", lambda *_args: FacturapiClient(is_mock=True)
    )
    yield USER_ID
    get_settings.cache_clear()


@pytest.fixture
def enabled_config(test_db, invoicing_svc, fiscal_actor):
    _, session = test_db
    return configure_issuer(session, fiscal_actor, BRANCH_ID)


def _confirm_order_payment(session, order_id, amount):
    now, shift = datetime.now(timezone.utc), str(uuid.uuid4())
    session.execute(
        models.cash_shifts.insert().values(
            id=shift,
            organization_id=ORGANIZATION_ID,
            branch_id=BRANCH_ID,
            register_code="FISCAL-LEGACY-QA",
            status="CLOSED",
            opening_cash_cents=0,
            opened_at=now,
            closed_at=now,
            created_at=now,
        )
    )
    session.execute(
        models.payments.insert().values(
            id=str(uuid.uuid4()),
            organization_id=ORGANIZATION_ID,
            branch_id=BRANCH_ID,
            order_id=order_id,
            cash_shift_id=shift,
            method="cash",
            status="CONFIRMED",
            amount_cents=amount,
            currency="MXN",
            confirmed_at=now,
            created_at=now,
        )
    )
    session.commit()


def test_facturapi_config_crud(test_db, invoicing_svc, fiscal_actor):
    _, session = test_db
    assert invoicing_svc.get_config(session, ORGANIZATION_ID) is None
    saved = configure_issuer(session, fiscal_actor, BRANCH_ID)
    assert saved["is_enabled"] is True and saved["version"] == 1
    assert saved["organization_rfc"] == "KIW210101ABC"
    assert saved["environment"] == "sandbox" and "api_key" not in saved
    fetched = emitters.read_configuration(session, fiscal_actor, saved["legal_entity_id"])
    assert fetched["organization_legal_name"] == "RESTAURANTE KIWI SA DE CV"
    assert fetched["api_key_configured"] is True
    assert invoicing_svc.get_config(session, ORGANIZATION_ID) is None


def test_create_receipt_for_order(test_db, invoicing_svc, fiscal_actor, enabled_config):
    _, session = test_db
    order_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    # Create test order with UBER_EATS channel to satisfy check constraint
    session.execute(
        models.orders.insert().values(
            id=order_id,
            organization_id=ORGANIZATION_ID,
            branch_id=BRANCH_ID,
            folio="UBER-U100",
            channel="UBER_EATS",
            status="COMPLETED",
            total_cents=25000,
            currency="MXN",
            created_at=now,
        )
    )
    session.commit()

    _confirm_order_payment(session, order_id, 25000)
    # Generate receipt for order
    receipt = invoicing_svc.create_receipt_for_order(
        session, ORGANIZATION_ID, BRANCH_ID, order_id, actor_user_id=fiscal_actor
    )
    assert receipt is not None
    assert "self_invoice_url" in receipt
    assert "receipt_id" in receipt
    assert (
        "factura.space" in receipt["self_invoice_url"] or "kiwirest" in receipt["self_invoice_url"]
    )


def test_issue_invoice_for_orders(test_db, invoicing_svc, fiscal_actor, enabled_config):
    _, session = test_db
    order_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    # Create order
    session.execute(
        models.orders.insert().values(
            id=order_id,
            organization_id=ORGANIZATION_ID,
            branch_id=BRANCH_ID,
            folio="UBER-U101",
            channel="UBER_EATS",
            status="COMPLETED",
            total_cents=35000,
            currency="MXN",
            created_at=now,
        )
    )
    session.commit()

    _confirm_order_payment(session, order_id, 35000)
    receptor_data = {
        "rfc": "XAXX010101000",
        "legal_name": "PUBLICO EN GENERAL",
        "zip": "80000",
        "tax_system": "616",
        "use": "S01",
        "payment_form": "01",
        "payment_method": "PUE",
        "email": "cliente@example.com",
    }

    invoice = invoicing_svc.issue_invoice(
        session,
        org_id=ORGANIZATION_ID,
        branch_id=BRANCH_ID,
        order_ids=[order_id],
        receptor=receptor_data,
        actor_user_id=fiscal_actor,
    )

    assert invoice is not None
    assert invoice["status"] == "issued"
    assert invoice["uuid_sat"] is not None
    assert invoice["total_cents"] == 35000
    assert invoice["pdf_url"] is not None
    assert invoice["xml_url"] is not None

    # List invoices
    invoices = invoicing_svc.list_invoices(
        session, ORGANIZATION_ID, BRANCH_ID, actor_user_id=fiscal_actor
    )
    assert len(invoices) >= 1
    assert any(i["id"] == invoice["id"] for i in invoices)


def test_cancel_invoice(test_db, invoicing_svc, fiscal_actor, enabled_config):
    _, session = test_db
    order_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    session.execute(
        models.orders.insert().values(
            id=order_id,
            organization_id=ORGANIZATION_ID,
            branch_id=BRANCH_ID,
            folio="UBER-U102",
            channel="UBER_EATS",
            status="COMPLETED",
            total_cents=18000,
            currency="MXN",
            created_at=now,
        )
    )
    session.commit()

    _confirm_order_payment(session, order_id, 18000)
    invoice = invoicing_svc.issue_invoice(
        session,
        org_id=ORGANIZATION_ID,
        branch_id=BRANCH_ID,
        order_ids=[order_id],
        receptor={
            "rfc": "XAXX010101000",
            "legal_name": "PUBLICO EN GENERAL",
            "zip": "80000",
            "tax_system": "616",
            "use": "S01",
            "payment_form": "04",
            "payment_method": "PUE",
        },
        actor_user_id=fiscal_actor,
    )

    # Cancel invoice with SAT reason '02'
    cancelled = invoicing_svc.cancel_invoice(
        session,
        org_id=ORGANIZATION_ID,
        invoice_id=invoice["id"],
        motive="02",
        actor_user_id=fiscal_actor,
    )
    assert cancelled["status"] == "cancelled"
    assert cancelled["cancellation_reason"] == "02"


def test_api_facturapi_endpoints(client, auth_headers, fiscal_actor, enabled_config, monkeypatch):
    legacy = client.get("/api/v1/integrations/facturapi/config", headers=auth_headers)
    assert legacy.status_code == 200 and legacy.json()["emitter_binding_required"] is True
    assert "environment" not in legacy.json()
    emitter = enabled_config["legal_entity_id"]
    path = f"/api/v1/invoicing/emitters/{emitter}/configuration"
    response = client.get(path, headers=auth_headers)
    assert response.status_code == 200 and response.json()["version"] == 1
    response = client.put(
        path, headers=auth_headers, json=configuration_payload(expected_version=1, series="QA")
    )
    assert response.status_code == 200 and response.json()["version"] == 2
    monkeypatch.setattr(
        FacturapiClient, "validate_api_key", lambda self: {"id": "synthetic-org", "legal": {}}
    )
    response = client.post(
        f"/api/v1/invoicing/emitters/{emitter}/test-connection", headers=auth_headers
    )
    assert response.status_code == 200 and response.json()["success"] is True
