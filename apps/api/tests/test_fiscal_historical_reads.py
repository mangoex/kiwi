"""Corporate and historical fiscal reads preserve authority, no external provider."""

import pytest
import sqlalchemy as sa
import test_fiscal_authority_audit as review
import test_fiscal_authority_remediation as authority
import test_fiscal_downloads as downloads
from restaurant_os import models

test_db = downloads.test_db
client = downloads.client
auth_headers = downloads.auth_headers
fiscal_data = downloads.fiscal_data
download_provider = downloads.download_provider
v2 = review.v2


@pytest.mark.parametrize("operation", ["list", "detail", "pdf", "xml"])
def test_corporate_history_remains_readable_after_branch_deactivation(
    client, auth_headers, fiscal_data, download_provider, v2, operation
):
    session, _ = fiscal_data
    authority._grant(session, "invoicing.read")
    session.execute(
        models.branches.update()
        .where(models.branches.c.id == authority.BRANCH_B)
        .values(status="inactive")
    )
    session.commit()
    before = list(session.execute(sa.select(models.cfdi_invoices)).mappings())
    session.rollback()
    if operation == "list":
        path = "/api/v1/invoicing/invoices?branch_id=" + authority.BRANCH_B
    else:
        path = "/api/v1/invoicing/invoices/" + authority.INVOICE_B
        if operation in {"pdf", "xml"}:
            path += "/" + operation
    response = client.get(path, headers=auth_headers)
    assert response.status_code == 200, response.text
    if operation == "list":
        assert {row["id"] for row in response.json()} == {authority.INVOICE_B}
    elif operation == "detail":
        assert response.json()["id"] == authority.INVOICE_B
    else:
        assert response.content == (b"%PDF-synthetic" if operation == "pdf" else b"<synthetic/>")
        assert download_provider == [("remote-" + authority.INVOICE_B, operation)]
    assert list(session.execute(sa.select(models.cfdi_invoices)).mappings()) == before
    assert (
        session.scalar(sa.select(sa.func.count()).select_from(models.branch_workspace_sessions))
        == 0
    )


@pytest.mark.parametrize("operation", ["detail", "pdf", "xml"])
def test_corporate_active_branch_read_does_not_require_operational_context(
    client, auth_headers, fiscal_data, download_provider, v2, operation
):
    session, _ = fiscal_data
    authority._grant(session, "invoicing.read")
    path = "/api/v1/invoicing/invoices/" + authority.INVOICE_B
    if operation != "detail":
        path += "/" + operation
    response = client.get(path, headers=auth_headers)
    assert response.status_code == 200, response.text
    assert (
        session.scalar(sa.select(sa.func.count()).select_from(models.branch_workspace_sessions))
        == 0
    )


@pytest.mark.parametrize("operation", ["list", "detail", "pdf", "xml"])
def test_closed_branch_reader_retains_only_current_granted_history(
    client, auth_headers, fiscal_data, download_provider, v2, operation
):
    session, _ = fiscal_data
    authority._grant(session, "invoicing.read", branch_scoped=True)
    session.execute(
        models.branches.update()
        .where(models.branches.c.id == downloads.legacy.BRANCH_ID)
        .values(status="inactive")
    )
    session.commit()
    path = "/api/v1/invoicing/invoices"
    if operation != "list":
        path += "/" + authority.INVOICE_A
        if operation in {"pdf", "xml"}:
            path += "/" + operation
    response = client.get(path, headers=auth_headers)
    assert response.status_code == 200, response.text
    if operation == "list":
        assert {row["id"] for row in response.json()} == {authority.INVOICE_A}
    assert (
        session.scalar(sa.select(sa.func.count()).select_from(models.branch_workspace_sessions))
        == 0
    )
    denied = client.get("/api/v1/invoicing/invoices/" + authority.INVOICE_B, headers=auth_headers)
    assert denied.status_code == 403, denied.text


@pytest.mark.parametrize(
    "failure", ["no_permission", "actor_inactive", "role_unrelated", "foreign_organization"]
)
def test_closed_history_does_not_bypass_authority(
    client, auth_headers, fiscal_data, download_provider, v2, failure
):
    from datetime import datetime, timezone

    session, _ = fiscal_data
    if failure != "no_permission":
        authority._grant(session, "invoicing.read", branch_scoped=failure == "role_unrelated")
    session.execute(
        models.branches.update()
        .where(models.branches.c.id == authority.BRANCH_B)
        .values(status="inactive")
    )
    if failure == "actor_inactive":
        session.execute(
            models.users.update()
            .where(models.users.c.id == downloads.legacy.USER_ID)
            .values(status="suspended")
        )
    elif failure == "role_unrelated":
        session.execute(
            models.roles.insert().values(
                id="historical-unrelated-role",
                organization_id=downloads.legacy.ORGANIZATION_ID,
                name="Unrelated corporate role",
                scope="organization",
                created_at=datetime.now(timezone.utc),
            )
        )
        session.execute(
            models.user_roles.insert().values(
                user_id=downloads.legacy.USER_ID,
                role_id="historical-unrelated-role",
                branch_id=None,
            )
        )
    elif failure == "foreign_organization":
        session.execute(
            models.branches.update()
            .where(models.branches.c.id == authority.BRANCH_B)
            .values(organization_id="historical-other-tenant")
        )
    session.commit()
    denied = client.get(
        "/api/v1/invoicing/invoices/" + authority.INVOICE_B + "/pdf", headers=auth_headers
    )
    assert denied.status_code == 403, denied.text
    assert download_provider == []


@pytest.mark.parametrize("operation", ["issue", "receipt", "prepare", "cancel"])
def test_closed_read_does_not_allow_new_fiscal_operations(
    client, auth_headers, fiscal_data, v2, operation
):
    from restaurant_os.invoicing.authority import require_branch_permission
    from restaurant_os.operations import AuthorizationError

    session, calls = fiscal_data
    permission = {
        "issue": "invoicing.issue",
        "receipt": "invoicing.receipt.create",
        "prepare": "invoicing.issue",
        "cancel": "invoicing.cancel",
    }[operation]
    authority._grant(session, permission)
    session.execute(
        models.branches.update()
        .where(models.branches.c.id == authority.BRANCH_B)
        .values(status="inactive")
    )
    session.commit()
    with pytest.raises(AuthorizationError):
        require_branch_permission(
            session,
            downloads.legacy.USER_ID,
            downloads.legacy.ORGANIZATION_ID,
            authority.BRANCH_B,
            permission,
        )
    assert calls == []


@pytest.mark.parametrize("failure", ["actor_revoked", "read_revoked", "branch_rebound"])
def test_history_download_revalidates_after_transport(
    client, auth_headers, fiscal_data, monkeypatch, v2, failure
):
    from restaurant_os import api

    session, _ = fiscal_data
    authority._grant(session, "invoicing.read")
    session.execute(
        models.branches.update()
        .where(models.branches.c.id == authority.BRANCH_B)
        .values(status="inactive")
    )
    session.commit()
    transported = []

    class Provider:
        def download_invoice(self, *_):
            assert not session.in_transaction()
            transported.append(True)
            if failure == "actor_revoked":
                session.execute(
                    models.users.update()
                    .where(models.users.c.id == downloads.legacy.USER_ID)
                    .values(status="suspended")
                )
            elif failure == "read_revoked":
                permission = session.scalar(
                    sa.select(models.permissions.c.id).where(
                        models.permissions.c.code == "invoicing.read"
                    )
                )
                session.execute(
                    models.role_permissions.delete().where(
                        models.role_permissions.c.permission_id == permission
                    )
                )
            else:
                session.execute(
                    models.cfdi_invoices.update()
                    .where(models.cfdi_invoices.c.id == authority.INVOICE_B)
                    .values(branch_id=downloads.legacy.BRANCH_ID)
                )
            session.commit()
            return b"historical-private-content"

    monkeypatch.setattr(api.invoicing_service, "get_client", lambda *_: Provider())
    response = client.get(
        "/api/v1/invoicing/invoices/" + authority.INVOICE_B + "/pdf", headers=auth_headers
    )
    assert response.status_code in {403, 409}, response.text
    assert transported == [True]
    assert "historical-private-content" not in response.text
    assert (
        session.scalar(
            sa.select(sa.func.count())
            .select_from(models.audit_events)
            .where(models.audit_events.c.action == "invoicing.document.downloaded")
        )
        == 0
    )


def test_active_context_and_closed_branch_role_list_both_authorized_histories(
    client, auth_headers, fiscal_data, v2
):
    from datetime import datetime, timezone
    from uuid import uuid4

    session, _ = fiscal_data
    authority._grant(session, "invoicing.read", branch_scoped=True)
    secret = review._workspace(session)
    role = str(uuid4())
    permission = session.scalar(
        sa.select(models.permissions.c.id).where(models.permissions.c.code == "invoicing.read")
    )
    session.execute(
        models.roles.insert().values(
            id=role,
            organization_id=downloads.legacy.ORGANIZATION_ID,
            name="Historical branch reader",
            scope="branch",
            created_at=datetime.now(timezone.utc),
        )
    )
    session.execute(models.role_permissions.insert().values(role_id=role, permission_id=permission))
    session.execute(
        models.user_roles.insert().values(
            user_id=downloads.legacy.USER_ID, role_id=role, branch_id=authority.BRANCH_B
        )
    )
    session.execute(
        models.branches.update()
        .where(models.branches.c.id == authority.BRANCH_B)
        .values(status="inactive")
    )
    session.commit()
    response = client.get(
        "/api/v1/invoicing/invoices", headers={**auth_headers, "X-Branch-Context": secret}
    )
    assert response.status_code == 200, response.text
    assert {row["id"] for row in response.json()} == {authority.INVOICE_A, authority.INVOICE_B}
    assert (
        session.scalar(sa.select(sa.func.count()).select_from(models.branch_workspace_sessions))
        == 1
    )


def test_mobile_workspace_portability_does_not_grant_closed_branch_history(
    client, auth_headers, fiscal_data, download_provider, v2
):
    from datetime import datetime, timezone

    session, _ = fiscal_data
    authority._grant(session, "invoicing.read", branch_scoped=True)
    session.execute(
        models.role_authority_grants.insert().values(
            role_id=downloads.legacy.ROLE_ID,
            authority_kind="organization_branch_workspaces",
            created_at=datetime.now(timezone.utc),
        )
    )
    session.execute(
        models.branches.update()
        .where(models.branches.c.id == authority.BRANCH_B)
        .values(status="inactive")
    )
    session.commit()
    response = client.get(
        "/api/v1/invoicing/invoices/" + authority.INVOICE_B + "/pdf", headers=auth_headers
    )
    assert response.status_code == 403, response.text
    assert download_provider == []
