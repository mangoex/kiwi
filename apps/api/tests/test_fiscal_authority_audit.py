"""Independent synthetic refutations of the fiscal permission boundary."""

import hashlib
from datetime import datetime, timezone

import pytest
import sqlalchemy as sa
import test_facturapi_integration as legacy
import test_fiscal_authority_remediation as directed
from restaurant_os import api, models
from restaurant_os.config import get_settings
from restaurant_os.invoicing.authority import require_branch_permission
from restaurant_os.operations import AuthorizationError


def test_configuration_audit_failure_cannot_be_committed_later(fiscal_data, monkeypatch):
    from restaurant_os.invoicing import service

    session, _ = fiscal_data
    directed._grant(session, "invoicing.config.manage")

    def fail_audit(*args, **kwargs):
        raise RuntimeError("synthetic audit sink failure")

    monkeypatch.setattr(service, "_audit", fail_audit)
    with pytest.raises(RuntimeError, match="synthetic audit sink failure"):
        service.InvoicingService().save_config(
            session, legacy.ORGANIZATION_ID, {"is_enabled": False},
            actor_user_id=legacy.USER_ID,
        )
    session.commit()
    assert session.scalar(sa.select(models.facturapi_config.c.is_enabled)) is True

test_db = directed.test_db
client = directed.client
auth_headers = directed.auth_headers
fiscal_data = directed.fiscal_data


@pytest.fixture
def v2(monkeypatch):
    monkeypatch.setenv("RESTAURANTOS_BRANCH_SCOPE_V2_ENABLED", "true")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _workspace(session, secret="q" * 40):
    now = datetime.now(timezone.utc)
    session.execute(
        models.branch_workspace_sessions.insert().values(
            id="independent-fiscal-workspace",
            organization_id=legacy.ORGANIZATION_ID,
            actor_user_id=legacy.USER_ID,
            branch_id=legacy.BRANCH_ID,
            authorization_version=1,
            token_hash=hashlib.sha256(secret.encode()).hexdigest(),
            secret_version=1,
            state="active",
            created_at=now,
            updated_at=now,
        )
    )
    session.commit()
    return secret


def test_v2_valid_context_gives_reader_only_actual_branch(client, auth_headers, fiscal_data, v2):
    session, calls = fiscal_data
    directed._grant(session, "invoicing.read", branch_scoped=True)
    secret = _workspace(session)
    response = client.get(
        "/api/v1/invoicing/invoices", headers={**auth_headers, "X-Branch-Context": secret}
    )
    assert response.status_code == 200
    assert {row["id"] for row in response.json()} == {directed.INVOICE_A}
    assert calls == []


@pytest.mark.parametrize("failure", ["missing", "wrong", "stale", "recovery"])
def test_v2_context_denial_is_audited_without_secret(
    client,
    auth_headers,
    fiscal_data,
    v2,
    failure,
):
    session, calls = fiscal_data
    directed._grant(session, "invoicing.read", branch_scoped=True)
    secret = _workspace(session)
    if failure == "stale":
        session.execute(
            models.users.update()
            .where(models.users.c.id == legacy.USER_ID)
            .values(authorization_version=2)
        )
        session.commit()
    if failure == "recovery":
        session.execute(models.branch_workspace_sessions.update().values(state="recovery_only"))
        session.commit()
    headers = dict(auth_headers)
    if failure != "missing":
        headers["X-Branch-Context"] = "x" * 40 if failure == "wrong" else secret
    response = client.get("/api/v1/invoicing/invoices/" + directed.INVOICE_A, headers=headers)
    assert response.status_code == 403
    assert calls == []
    events = (
        session.execute(
            sa.select(models.audit_events).where(
                models.audit_events.c.action == "authorization.denied"
            )
        )
        .mappings()
        .all()
    )
    assert len(events) == 1, "Context denial must persist an authorization audit event"
    assert events[0]["branch_id"] == legacy.BRANCH_ID
    assert secret not in str(dict(events[0]))


def test_inactive_actor_with_fiscal_capability_cannot_read(client, auth_headers, fiscal_data):
    session, calls = fiscal_data
    directed._grant(session, "invoicing.read")
    session.execute(
        models.users.update().where(models.users.c.id == legacy.USER_ID).values(status="suspended")
    )
    session.commit()
    response = client.get("/api/v1/invoicing/invoices", headers=auth_headers)
    assert response.status_code == 403
    assert calls == []


def test_mixed_scopes_do_not_borrow_corporate_config_authority(
    client,
    auth_headers,
    fiscal_data,
):
    session, calls = fiscal_data
    directed._grant(session, "invoicing.config.manage", branch_scoped=True)
    now = datetime.now(timezone.utc)
    session.execute(
        models.roles.insert().values(
            id="unrelated-corporate-role",
            organization_id=legacy.ORGANIZATION_ID,
            name="Unrelated org role",
            scope="organization",
            created_at=now,
        )
    )
    session.execute(
        models.user_roles.insert().values(
            user_id=legacy.USER_ID, role_id="unrelated-corporate-role"
        )
    )
    session.commit()
    response = client.get("/api/v1/integrations/facturapi/config", headers=auth_headers)
    assert response.status_code == 403
    assert calls == []


def test_public_config_omitted_key_preserves_secret_and_does_not_echo_it(
    client,
    auth_headers,
    fiscal_data,
):
    session, calls = fiscal_data
    directed._grant(session, "invoicing.config.manage")
    response = client.post(
        "/api/v1/integrations/facturapi/config", headers=auth_headers, json={"is_enabled": False}
    )
    assert response.status_code == 200
    assert response.json()["api_key_configured"] is True
    assert "api_key" not in response.json()
    assert session.scalar(sa.select(models.facturapi_config.c.api_key)) == "synthetic-sensitive-key"
    assert calls == []


def test_successful_config_write_is_audited(client, auth_headers, fiscal_data):
    session, _ = fiscal_data
    directed._grant(session, "invoicing.config.manage")
    response = client.post(
        "/api/v1/integrations/facturapi/config", headers=auth_headers, json={"is_enabled": False}
    )
    assert response.status_code == 200
    actions = list(session.scalars(sa.select(models.audit_events.c.action)))
    assert actions, "A fiscal configuration change must persist its audit event"


def test_unknown_actor_and_branch_have_safe_denial_foreign_keys(fiscal_data):
    session, calls = fiscal_data
    session.execute(sa.text("PRAGMA foreign_keys=ON"))
    assert session.scalar(sa.text("PRAGMA foreign_keys")) == 1
    with pytest.raises(AuthorizationError):
        require_branch_permission(
            session, "unknown-actor", legacy.ORGANIZATION_ID, "unknown-branch", "invoicing.read"
        )
    event = session.execute(sa.select(models.audit_events)).mappings().one()
    assert event["actor_user_id"] is None
    assert event["branch_id"] is None
    assert calls == []


def test_database_failure_does_not_return_or_log_sensitive_sql(
    client,
    auth_headers,
    fiscal_data,
    monkeypatch,
    caplog,
):
    session, calls = fiscal_data
    directed._grant(session, "invoicing.config.manage")
    marker = "independent-private-sql-marker"

    def failure(*args):
        raise sa.exc.OperationalError("SELECT " + marker, {"key": marker}, Exception(marker))

    monkeypatch.setattr(api.invoicing_service, "get_config", failure)
    response = client.get("/api/v1/integrations/facturapi/config", headers=auth_headers)
    assert response.status_code == 503
    assert marker not in response.text + caplog.text
    assert calls == []
