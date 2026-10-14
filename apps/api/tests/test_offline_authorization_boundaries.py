"""Offline authority lifetime, recovery and credential error boundaries."""

from datetime import timedelta, timezone
from uuid import uuid4

import pytest
import sqlalchemy as sa
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from restaurant_os import api as api_module
from restaurant_os import models, offline_authorization, operations
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from test_branch_workspace_authority import _reissue, _select
from test_branch_workspace_authority import workspace as workspace
from test_offline_authorization_registry import _cash_grant, _order_fixture
from test_platform_api import BRANCH_ID

UTC = timezone.utc


@pytest.mark.parametrize(
    "resource,code",
    [
        ("device", "gateway_device_inactive"),
        ("bundle", "offline_order_bundle_unavailable"),
        ("gateway", "offline_gateway_lease_invalid"),
    ],
)
def test_order_issuer_refreshes_clock_after_resource_locks(workspace, monkeypatch, resource, code):
    client, _, factory, headers, payload = _order_fixture(workspace, monkeypatch)
    start = operations._now()
    table = {
        "device": models.device_credentials,
        "bundle": models.offline_order_bundles,
        "gateway": models.offline_order_gateway_leases,
    }[resource]
    with factory() as session:
        session.execute(table.update().values(expires_at=start + timedelta(seconds=2)))
        session.commit()
    clocks = iter((start, start + timedelta(seconds=3)))
    monkeypatch.setattr(operations, "_now", lambda: next(clocks))

    def forbidden_signer():
        pytest.fail("A resource expired while locks were acquired; no token may be signed")

    monkeypatch.setattr(api_module, "offline_order_signing_material", forbidden_signer)
    response = client.post("/api/v1/offline-orders/grants", headers=headers, json=payload)
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["code"] == code
    with factory() as session:
        assert (
            session.scalar(
                sa.select(sa.func.count()).select_from(models.offline_authorization_leases)
            )
            == 0
        )
        assert (
            session.scalar(sa.select(sa.func.count()).select_from(models.offline_order_grants)) == 0
        )


@pytest.mark.parametrize("known", [True, False])
def test_foreign_organization_denial_is_audited_without_signing(workspace, monkeypatch, known):
    _, fixture, factory, headers, payload = _order_fixture(workspace, monkeypatch)

    def forbidden_signer():
        pytest.fail("Signing configuration must not be read before organization authorization")

    monkeypatch.setattr(operations, "_offline_grant_signing_material", forbidden_signer)
    actor = fixture["supervisor_id"] if known else str(uuid4())
    branch = fixture["branch_id"] if known else str(uuid4())
    with factory() as session:
        with pytest.raises(operations.AuthorizationError) as denied:
            operations.issue_offline_cash_grant(
                session,
                actor_user_id=actor,
                organization_id=str(uuid4()),
                branch_id=branch,
                source_device_id=payload["source_device_id"],
                branch_context=headers["X-Branch-Context"],
            )
        assert denied.value.code == "permission_denied"
        session.commit()
        event = (
            session.execute(
                sa.select(models.audit_events).where(
                    models.audit_events.c.action == "authorization.denied"
                )
            )
            .mappings()
            .one()
        )
        assert event["actor_user_id"] == (actor if known else None)
        assert event["branch_id"] == (branch if known else None)
        assert event["payload"] == {"permission": "offline.grant", "reason": "permission_denied"}
        assert (
            session.scalar(
                sa.select(sa.func.count()).select_from(models.offline_authorization_leases)
            )
            == 0
        )


@pytest.mark.parametrize("seconds,blocked", [(0.9, True), (1.0, False)])
def test_expiration_keeps_last_valid_integer_second_blocked(
    workspace, monkeypatch, seconds, blocked
):
    client, _, factory, headers = workspace
    _cash_grant(workspace, monkeypatch)
    with factory() as session:
        expiry = session.scalar(sa.select(models.offline_authorization_leases.c.expires_at))
    expiry = expiry.replace(tzinfo=UTC) if expiry.tzinfo is None else expiry
    monkeypatch.setattr(
        offline_authorization, "authority_now", lambda: expiry + timedelta(seconds=seconds)
    )
    response = _select(client, headers, BRANCH_ID)
    assert response.status_code == (409 if blocked else 200), response.text
    if blocked:
        assert response.json()["detail"]["code"] == "branch_switch_offline_grant"


def test_current_branch_lease_allows_recovery_and_same_branch_selection(workspace, monkeypatch):
    client, fixture, _, headers = workspace
    issued, _ = _cash_grant(workspace, monkeypatch)
    recovered = _reissue(
        client, headers, issued["branch_workspace_context_id"], "offline-safe-recovery"
    )
    assert recovered.status_code == 200, recovered.text
    selected = _select(client, headers, fixture["branch_id"])
    assert selected.status_code == 200, selected.text
    assert selected.json()["active_branch"]["id"] == fixture["branch_id"]


@pytest.mark.parametrize("kind", ["cash", "orders"])
def test_commit_failure_redacts_token_and_rolls_back_partial_evidence(
    workspace, monkeypatch, capsys, kind
):
    client, _, factory, headers, payload = _order_fixture(workspace, monkeypatch)
    issuer = Ed25519PrivateKey.generate()
    monkeypatch.setattr(operations, "_offline_grant_signing_material", lambda: (issuer, "qa"))
    audit, commit = operations._audit, Session.commit
    marker = "SYNTHETIC_SIGNED_TOKEN_MUST_NOT_LEAVE_ERROR"

    def mark_audit(session, *args, **kwargs):
        audit(session, *args, **kwargs)
        if kwargs.get("action") == "auth.offline_grant_registered":
            session.info["fail_offline_commit"] = True

    def fail_commit(session):
        if session.info.pop("fail_offline_commit", False):
            raise SQLAlchemyError(marker)
        return commit(session)

    monkeypatch.setattr(operations, "_audit", mark_audit)
    monkeypatch.setattr(Session, "commit", fail_commit)
    if kind == "cash":
        path = "/api/v1/auth/offline-grants"
        payload = {key: payload[key] for key in ("branch_id", "source_device_id")}
    else:
        path = "/api/v1/offline-orders/grants"
    response = client.post(path, headers=headers, json=payload)
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["code"] == "offline_authority_persistence_unavailable"
    assert marker not in response.text
    captured = capsys.readouterr()
    assert marker not in captured.out + captured.err
    with factory() as session:
        for table in (models.offline_authorization_leases, models.offline_order_grants):
            assert session.scalar(sa.select(sa.func.count()).select_from(table)) == 0
        assert (
            session.scalar(
                sa.select(sa.func.count())
                .select_from(models.audit_events)
                .where(models.audit_events.c.action == "auth.offline_grant_registered")
            )
            == 0
        )


@pytest.mark.parametrize("kind", ["cash", "orders"])
def test_missing_workspace_is_audited_before_signing_and_grant_write(workspace, monkeypatch, kind):
    client, fixture, factory, headers, payload = _order_fixture(workspace, monkeypatch)
    headers.pop("X-Branch-Context")

    def forbidden_signer():
        pytest.fail("Signing configuration must not be read before authorization")

    monkeypatch.setattr(operations, "_offline_grant_signing_material", forbidden_signer)
    monkeypatch.setattr(api_module, "offline_order_signing_material", forbidden_signer)
    if kind == "cash":
        path = "/api/v1/auth/offline-grants"
        payload = {key: payload[key] for key in ("branch_id", "source_device_id")}
    else:
        path = "/api/v1/offline-orders/grants"
    response = client.post(path, headers=headers, json=payload)
    assert response.status_code == 403, response.text
    assert response.json()["detail"]["code"] == "branch_context_required"
    with factory() as session:
        event = (
            session.execute(
                sa.select(models.audit_events).where(
                    models.audit_events.c.action == "authorization.denied"
                )
            )
            .mappings()
            .one()
        )
        assert event["actor_user_id"] == fixture["supervisor_id"]
        assert event["payload"]["permission"] == "offline.grant"
        assert event["payload"]["reason"] == "branch_context_required"
        assert (
            session.scalar(
                sa.select(sa.func.count()).select_from(models.offline_authorization_leases)
            )
            == 0
        )
