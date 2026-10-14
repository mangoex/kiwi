"""A fiscal-only reader must be able to obtain the required branch fence."""

import sqlalchemy as sa
import test_fiscal_authority_audit as review
import test_fiscal_authority_remediation as authority
from restaurant_os import models

test_db = review.test_db
client = review.client
auth_headers = review.auth_headers
fiscal_data = review.fiscal_data
v2 = review.v2


def _clear_seed_permissions(session):
    # The legacy seed has admin/catalog aliases that also authorize document purchases.
    session.execute(
        models.role_permissions.delete().where(
            models.role_permissions.c.role_id == authority.legacy.ROLE_ID,
        )
    )
    session.commit()


def test_fiscal_only_reader_can_recover_required_workspace(client, auth_headers, fiscal_data, v2):
    session, calls = fiscal_data
    _clear_seed_permissions(session)
    authority._grant(session, "invoicing.read", branch_scoped=True)
    profile = client.get("/api/v1/auth/session", headers=auth_headers).json()
    assert profile["admin_capabilities"]["invoicing.read"] is True
    assert profile["permissions"] == ["invoicing.read"]
    assert profile["admin_capabilities"]["purchases.manage"] is False
    assert profile["admin_capabilities"]["expenses.manage"] is False
    assert profile["admin_capabilities"]["pos.operate"] is False
    initial = client.get("/api/v1/invoicing/invoices", headers=auth_headers)
    assert initial.status_code == 403
    assert initial.json()["detail"]["code"] == "branch_context_required"
    response = client.post(
        "/api/v1/auth/branch-context-reissues",
        headers={**auth_headers, "Idempotency-Key": "sol-fiscal-only-reader"},
        json={"context_id": None, "expected_authorization_version": 1},
    )
    assert calls == []
    assert response.status_code == 200, (
        "Fiscal read is independent of POS operation, but the reader cannot acquire its mandatory "
        "branch context and has no successful list/download path with V2 enabled",
        response.text,
    )

    secret = response.json()["branch_workspace_context"]
    assert isinstance(secret, str) and secret
    scoped = {**auth_headers, "X-Branch-Context": secret}
    visible = client.get("/api/v1/invoicing/invoices", headers=scoped)
    assert visible.status_code == 200, visible.text
    assert {row["id"] for row in visible.json()} == {authority.INVOICE_A}
    hydrated = client.get("/api/v1/auth/session", headers=auth_headers).json()
    assert hydrated["admin_capabilities"]["pos.operate"] is False
    assert "pos.operate" not in hydrated["permissions"]
    denied = client.post(
        "/api/v1/cash-shifts/open",
        headers={**scoped, "Idempotency-Key": "qa-fiscal-reader-cash-denial"},
        json={
            "branch_id": authority.legacy.BRANCH_ID,
            "register_id": "QA-FISCAL",
            "opening_cash_cents": 0,
        },
    )
    assert denied.status_code == 403, denied.text
    assert denied.json()["detail"]["code"] == "permission_denied"
    assert calls == []


def test_config_only_actor_cannot_recover_operational_workspace(
    client, auth_headers, fiscal_data, v2
):
    session, calls = fiscal_data
    _clear_seed_permissions(session)
    authority._grant(session, "invoicing.config.manage")
    profile = client.get("/api/v1/auth/session", headers=auth_headers).json()
    assert profile["permissions"] == ["invoicing.config.manage"]
    for capability in (
        "pos.operate",
        "invoicing.read",
        "purchases.manage",
        "expenses.manage",
        "expenses.cancel",
    ):
        assert profile["admin_capabilities"][capability] is False
    response = client.post(
        "/api/v1/auth/branch-context-reissues",
        headers={**auth_headers, "Idempotency-Key": "qa-config-only-workspace-denial"},
        json={"context_id": None, "expected_authorization_version": 1},
    )
    assert response.status_code == 403, response.text
    assert response.json()["detail"]["code"] == "permission_denied"
    assert calls == []


def test_config_and_catalog_alias_actor_can_recover_document_workspace(
    client, auth_headers, fiscal_data, v2
):
    session, calls = fiscal_data
    _clear_seed_permissions(session)
    authority._grant(session, "invoicing.config.manage")
    catalog_permission = session.scalar(
        sa.select(models.permissions.c.id).where(models.permissions.c.code == "catalog.manage")
    )
    assert catalog_permission
    session.execute(
        models.role_permissions.insert().values(
            role_id=authority.legacy.ROLE_ID, permission_id=catalog_permission
        )
    )
    session.commit()
    profile = client.get("/api/v1/auth/session", headers=auth_headers).json()
    assert profile["admin_capabilities"]["invoicing.config.manage"] is True
    assert profile["admin_capabilities"]["purchases.manage"] is True
    assert profile["admin_capabilities"]["invoicing.read"] is False
    assert profile["admin_capabilities"]["pos.operate"] is False
    response = client.post(
        "/api/v1/auth/branch-context-reissues",
        headers={**auth_headers, "Idempotency-Key": "qa-config-catalog-document-context"},
        json={"context_id": None, "expected_authorization_version": 1},
    )
    assert response.status_code == 200, response.text
    scoped = {**auth_headers, "X-Branch-Context": response.json()["branch_workspace_context"]}
    denied = client.get("/api/v1/invoicing/invoices", headers=scoped)
    assert denied.status_code == 403, denied.text
    assert denied.json()["detail"]["code"] == "permission_denied"
    assert calls == []
