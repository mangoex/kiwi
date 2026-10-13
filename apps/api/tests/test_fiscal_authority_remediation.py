# SEC001-SYNTHETIC-FIXTURE provenance=restaurantos-audit-test-fiscal-authority-remediation-v1
"""FISCAL-001 directed API authority regressions; every provider call is synthetic."""

from datetime import datetime, timezone
from uuid import uuid4

import pytest
import sqlalchemy as sa
import test_facturapi_integration as legacy
from restaurant_os import api, models

test_db = legacy.test_db
client = legacy.client
auth_headers = legacy.auth_headers

BRANCH_B = "018f6f73-2d0a-74f0-8f1c-000000009002"
ORDER_A = "018f6f73-2d0a-74f0-8f1c-000000009003"
ORDER_B = "018f6f73-2d0a-74f0-8f1c-000000009004"
INVOICE_A = "018f6f73-2d0a-74f0-8f1c-000000009005"
INVOICE_B = "018f6f73-2d0a-74f0-8f1c-000000009006"


@pytest.fixture
def fiscal_data(test_db, monkeypatch):
    _, session = test_db
    now = datetime.now(timezone.utc)
    branch = dict(session.execute(sa.select(models.branches)).mappings().one())
    session.execute(
        models.branches.insert().values(
            **{
                **branch,
                "id": BRANCH_B,
                "name": "Sucursal B",
                "code": "B",
            }
        )
    )
    for order, branch_id in [(ORDER_A, legacy.BRANCH_ID), (ORDER_B, BRANCH_B)]:
        session.execute(
            models.orders.insert().values(
                id=order,
                organization_id=legacy.ORGANIZATION_ID,
                branch_id=branch_id,
                folio=order[-4:],
                channel="UBER_EATS",
                status="COMPLETED",
                total_cents=1999,
                currency="MXN",
                created_at=now,
            )
        )
    for invoice, branch_id, order in [
        (INVOICE_A, legacy.BRANCH_ID, ORDER_A),
        (INVOICE_B, BRANCH_B, ORDER_B),
    ]:
        session.execute(
            models.cfdi_invoices.insert().values(
                id=invoice,
                organization_id=legacy.ORGANIZATION_ID,
                branch_id=branch_id,
                order_id=order,
                facturapi_invoice_id="remote-" + invoice,
                uuid_sat=str(uuid4()),
                folio_number=invoice[-4:],
                rfc_emisor="KIW210101ABC",
                rfc_receptor="XAXX010101000",
                nombre_receptor="Fixture receptor",
                codigo_postal_receptor="80000",
                regimen_fiscal_receptor="616",
                uso_cfdi="S01",
                forma_pago_sat="01",
                metodo_pago_sat="PUE",
                total_cents=1999,
                currency="MXN",
                status="issued",
                raw_sat_response={"private": "fiscal-original-sensitive"},
                created_at=now,
            )
        )
    session.execute(
        models.facturapi_config.insert().values(
            id="config-qa",
            organization_id=legacy.ORGANIZATION_ID,
            is_enabled=True,
            api_key="synthetic-sensitive-key",
            organization_legal_name="Fixture emisor",
            organization_rfc="KIW210101ABC",
            organization_tax_system="601",
            organization_zip="80000",
            created_at=now,
            updated_at=now,
        )
    )
    session.commit()
    calls = []

    class SyntheticPAC:
        def create_receipt(self, payload):
            calls.append("receipt")
            return {"id": "synthetic-receipt", "status": "open"}

        def create_invoice(self, payload):
            calls.append("issue")
            return {"id": "synthetic-invoice", "uuid": str(uuid4()), "status": "valid"}

        def cancel_invoice(self, *args):
            calls.append("cancel")
            return {"status": "canceled", "cancellation_status": "accepted"}

        def validate_api_key(self):
            calls.append("test_connection")
            return {"status": "ok"}

    monkeypatch.setattr(api.invoicing_service, "get_client", lambda *_args: SyntheticPAC())
    return session, calls


def _grant(session, code, *, branch_scoped=False):
    permission = str(uuid4())
    session.execute(
        models.permissions.insert().values(
            id=permission,
            code=code,
            description="Synthetic " + code,
            created_at=datetime.now(timezone.utc),
        )
    )
    session.execute(
        models.role_permissions.insert().values(
            role_id=legacy.ROLE_ID,
            permission_id=permission,
        )
    )
    if branch_scoped:
        session.execute(
            models.roles.update().where(models.roles.c.id == legacy.ROLE_ID).values(scope="branch")
        )
    session.commit()


@pytest.mark.parametrize(
    "method,path,payload",
    [
        ("get", "/invoicing/invoices", None),
        ("get", "/invoicing/invoices/" + INVOICE_A, None),
        ("post", "/invoicing/invoices/issue", {"order_ids": [ORDER_A], "receptor": {}}),
        ("post", "/invoicing/invoices/" + INVOICE_A + "/cancel", {"motive": "02"}),
        ("post", "/invoicing/orders/" + ORDER_A + "/receipt", None),
        ("get", "/integrations/facturapi/config", None),
        ("post", "/integrations/facturapi/config", {"is_enabled": False}),
        ("post", "/integrations/facturapi/test-connection", None),
    ],
)
def test_order_reader_or_generic_admin_does_not_acquire_fiscal_authority(
    client, auth_headers, fiscal_data, method, path, payload
):
    session, calls = fiscal_data
    response = getattr(client, method)(
        "/api/v1" + path, headers=auth_headers, **({"json": payload} if payload is not None else {})
    )
    assert response.status_code == 403, response.text
    assert response.json()["detail"]["code"] == "permission_denied"
    assert calls == []
    assert session.scalar(sa.select(sa.func.count()).select_from(models.cfdi_invoices)) == 2
    assert session.scalar(sa.select(models.facturapi_config.c.is_enabled)) is True


def test_scoped_fiscal_reader_list_and_detail_cannot_cross_branch(
    client, auth_headers, fiscal_data
):
    session, calls = fiscal_data
    _grant(session, "invoicing.read", branch_scoped=True)
    visible = client.get("/api/v1/invoicing/invoices", headers=auth_headers)
    assert visible.status_code == 200, visible.text
    assert {row["id"] for row in visible.json()} == {INVOICE_A}
    crossed = client.get(
        "/api/v1/invoicing/invoices", headers=auth_headers, params={"branch_id": BRANCH_B}
    )
    detail = client.get("/api/v1/invoicing/invoices/" + INVOICE_B, headers=auth_headers)
    assert crossed.status_code == detail.status_code == 403
    assert calls == []


@pytest.mark.parametrize("kind", ["receipt", "issue", "cancel"])
def test_fiscal_write_permission_in_a_never_authorizes_resource_b(
    client, auth_headers, fiscal_data, kind
):
    session, calls = fiscal_data
    _grant(
        session,
        {
            "receipt": "invoicing.receipt.create",
            "issue": "invoicing.issue",
            "cancel": "invoicing.cancel",
        }[kind],
        branch_scoped=True,
    )
    path = {
        "receipt": "/invoicing/orders/" + ORDER_B + "/receipt",
        "issue": "/invoicing/invoices/issue",
        "cancel": "/invoicing/invoices/" + INVOICE_B + "/cancel",
    }[kind]
    payload = (
        {"order_ids": [ORDER_B], "branch_id": legacy.BRANCH_ID, "receptor": {}}
        if kind == "issue"
        else {"motive": "02"}
    )
    response = client.post("/api/v1" + path, headers=auth_headers, json=payload)
    assert response.status_code == 403, response.text
    assert calls == []


def test_fiscal_projection_excludes_credentials_and_original_response(
    client, auth_headers, fiscal_data
):
    session, calls = fiscal_data
    _grant(session, "invoicing.config.manage")
    _grant(session, "invoicing.read")
    config = client.get("/api/v1/integrations/facturapi/config", headers=auth_headers)
    listed = client.get("/api/v1/invoicing/invoices", headers=auth_headers)
    detail = client.get("/api/v1/invoicing/invoices/" + INVOICE_A, headers=auth_headers)
    assert config.status_code == listed.status_code == detail.status_code == 200
    assert "api_key" not in config.json()
    assert config.json()["api_key_configured"] is True
    assert all("raw_sat_response" not in row for row in listed.json())
    assert "raw_sat_response" not in detail.json()
    assert "synthetic-sensitive-key" not in config.text
    assert "fiscal-original-sensitive" not in listed.text + detail.text
    assert calls == []


def test_configuration_capability_from_branch_role_cannot_manage_corporate_config(
    client, auth_headers, fiscal_data
):
    session, calls = fiscal_data
    _grant(session, "invoicing.config.manage", branch_scoped=True)
    response = client.post(
        "/api/v1/integrations/facturapi/config", headers=auth_headers, json={"is_enabled": False}
    )
    assert response.status_code == 403, response.text
    assert calls == []
    assert session.scalar(sa.select(models.facturapi_config.c.is_enabled)) is True


@pytest.mark.parametrize("order_ids", [ORDER_A, None, [], [ORDER_A, ORDER_A], [ORDER_A, "missing"]])
def test_issue_requires_complete_unique_array_before_provider(
    client, auth_headers, fiscal_data, order_ids
):
    session, calls = fiscal_data
    _grant(session, "invoicing.issue")
    response = client.post(
        "/api/v1/invoicing/invoices/issue",
        headers=auth_headers,
        json={"order_ids": order_ids, "receptor": {}},
    )
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["code"] == "fiscal_order_set_invalid"
    assert calls == []


def test_missing_receipt_order_does_not_bypass_permission_check(client, auth_headers, fiscal_data):
    _, calls = fiscal_data
    response = client.post(
        "/api/v1/invoicing/orders/missing/receipt",
        headers=auth_headers,
    )
    assert response.status_code == 403, response.text
    assert response.json()["detail"]["code"] == "permission_denied"
    assert calls == []


@pytest.mark.parametrize("receptor", [[], "receptor", 123])
def test_invalid_receiver_is_business_error_not_internal_failure(
    client, auth_headers, fiscal_data, receptor
):
    session, calls = fiscal_data
    _grant(session, "invoicing.issue")
    response = client.post(
        "/api/v1/invoicing/invoices/issue",
        headers=auth_headers,
        json={"order_ids": [ORDER_A], "receptor": receptor},
    )
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["code"] == "fiscal_receiver_invalid"
    assert calls == []
