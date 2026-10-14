"""W04 retained authority and transition blocker regressions, no production grants."""

import hashlib
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
import sqlalchemy as sa
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from restaurant_os import api as api_module
from restaurant_os import models, operations
from restaurant_os.config import get_settings
from restaurant_os.offline_order_catalog import build_operational_seed
from test_branch_workspace_authority import _reissue, _select
from test_branch_workspace_authority import workspace as workspace
from test_platform_api import BRANCH_ID

UTC = timezone.utc


def _device(session, branch):
    now = datetime.now(UTC)
    device_id = str(uuid4())
    session.execute(
        models.device_credentials.insert().values(
            id=device_id,
            organization_id=operations.ORGANIZATION_ID,
            branch_id=branch,
            capability="gateway.sync",
            token_hash="0" * 64,
            key_version="synthetic",
            expires_at=now + timedelta(hours=3),
            revoked_at=None,
            created_at=now,
        )
    )
    session.commit()
    return device_id


def _cash_grant(workspace, monkeypatch):
    monkeypatch.setenv("RESTAURANTOS_SIGNED_OFFLINE_AUTHORITY_ENABLED", "true")
    get_settings.cache_clear()
    client, fixture, factory, headers = workspace
    issued = _reissue(client, headers).json()
    private_key = Ed25519PrivateKey.generate()
    monkeypatch.setattr(operations, "_offline_grant_signing_material", lambda: (private_key, "qa"))
    with factory() as session:
        device_id = _device(session, fixture["branch_id"])
        grant = operations.issue_offline_cash_grant(
            session,
            actor_user_id=fixture["supervisor_id"],
            organization_id=operations.ORGANIZATION_ID,
            branch_id=fixture["branch_id"],
            source_device_id=device_id,
            branch_context=issued["branch_workspace_context"],
        )
    return issued, grant


def test_cash_issuance_retains_authority_hash_and_audit(workspace, monkeypatch):
    _, fixture, factory, _ = workspace
    _, grant = _cash_grant(workspace, monkeypatch)
    with factory() as session:
        row = session.execute(sa.select(models.offline_authorization_leases)).mappings().one()
        assert row["grant_hash"] == hashlib.sha256(grant["offline_grant"].encode()).hexdigest()
        assert row["authorization_version"] == 1
        assert row["actor_user_id"] == fixture["supervisor_id"]
        assert row["provenance"] == "registered"
        assert row["grant_kind"] == "cash"
        audit = (
            session.execute(
                sa.select(models.audit_events).where(
                    models.audit_events.c.action == "auth.offline_grant_registered"
                )
            )
            .mappings()
            .one()
        )
        assert audit["entity_id"] == row["id"]
        assert grant["offline_grant"] not in str([dict(row), dict(audit)])


def _order_fixture(workspace, monkeypatch):
    monkeypatch.setenv("RESTAURANTOS_SIGNED_OFFLINE_AUTHORITY_ENABLED", "true")
    get_settings.cache_clear()
    client, fixture, factory, headers = workspace
    issued = _reissue(client, headers).json()
    issuer = Ed25519PrivateKey.generate()
    monkeypatch.setattr(api_module, "offline_order_signing_material", lambda: (issuer, "qa"))
    now = datetime.now(UTC)
    with factory() as session:
        device_id = _device(session, fixture["branch_id"])
        bundle_id = str(uuid4())
        session.execute(
            models.offline_order_gateway_leases.insert().values(
                organization_id=operations.ORGANIZATION_ID,
                branch_id=fixture["branch_id"],
                device_id=device_id,
                actor_id=device_id,
                public_key="synthetic retained gateway",
                lease_epoch=1,
                fencing_token="0" * 64,
                status="ACTIVE",
                issued_at=now,
                expires_at=now + timedelta(hours=2),
            )
        )
        session.execute(
            models.offline_order_bundles.insert().values(
                id=bundle_id,
                organization_id=operations.ORGANIZATION_ID,
                branch_id=fixture["branch_id"],
                device_id=device_id,
                bundle_hash="0" * 64,
                manifest={},
                catalog={},
                operational_seed=build_operational_seed(
                    session, organization_id=operations.ORGANIZATION_ID,
                    branch_id=fixture["branch_id"], actor_ids=[fixture["supervisor_id"]],
                ),
                kid="qa",
                signature="synthetic retained catalog",
                issued_at=now,
                expires_at=now + timedelta(hours=2),
            )
        )
        session.commit()
    return (
        client,
        fixture,
        factory,
        {**headers, "X-Branch-Context": issued["branch_workspace_context"]},
        {
            "branch_id": fixture["branch_id"],
            "source_device_id": device_id,
            "bundle_id": bundle_id,
            "lease_epoch": 1,
        },
    )


def test_order_issuance_is_registered_with_source_lineage_and_blocks_switch(workspace, monkeypatch):
    client, fixture, factory, headers, payload = _order_fixture(workspace, monkeypatch)
    response = client.post("/api/v1/offline-orders/grants", headers=headers, json=payload)
    assert response.status_code == 200, response.text
    token = response.json()["grant"]
    with factory() as session:
        source = session.execute(sa.select(models.offline_order_grants)).mappings().one()
        retained = session.execute(sa.select(models.offline_authorization_leases)).mappings().one()
        assert retained["source_grant_id"] == source["id"]
        assert retained["grant_kind"] == "orders"
        assert retained["bundle_id"] == payload["bundle_id"]
        assert retained["grant_hash"] == hashlib.sha256(token.encode()).hexdigest()
        assert retained["authorization_version"] == 1
        assert retained["actor_user_id"] == fixture["supervisor_id"]
    rejected = _select(client, headers, BRANCH_ID)
    assert rejected.status_code == 409, rejected.text
    assert rejected.json()["detail"]["code"] == "branch_switch_offline_grant"


@pytest.mark.parametrize("state", ["active", "revoked"])
def test_unexpired_grant_blocks_incompatible_branch_even_after_central_revocation(
    workspace, monkeypatch, state
):
    client, fixture, factory, headers = workspace
    issued, _ = _cash_grant(workspace, monkeypatch)
    if state == "revoked":
        with factory() as session:
            session.execute(
                models.offline_authorization_leases.update().values(
                    state="revoked",
                    revoked_at=datetime.now(UTC),
                )
            )
            session.commit()
    rejected = _select(client, headers, BRANCH_ID)
    assert rejected.status_code == 409, rejected.text
    assert rejected.json()["detail"]["code"] == "branch_switch_offline_grant"
    with factory() as session:
        row = session.execute(sa.select(models.branch_workspace_sessions)).mappings().one()
        assert row["id"] == issued["branch_workspace_context_id"]
        assert row["branch_id"] == fixture["branch_id"]
        assert (
            session.scalar(sa.select(sa.func.count()).select_from(models.branch_selection_commands))
            == 0
        )


def test_unprepared_preflight_blocks_new_selection_without_making_readiness(workspace):
    client, _, factory, headers = workspace
    initial = _reissue(client, headers).json()
    with factory() as session:
        session.execute(
            models.offline_authorization_rollouts.update().values(
                state="unprepared",
                registration_started_at=None,
                legacy_drain_until=None,
            )
        )
        session.commit()
    rejected = _select(client, headers, BRANCH_ID)
    assert rejected.status_code == 409, rejected.text
    assert rejected.json()["detail"]["code"] == "branch_offline_preflight_required"
    recovered = _reissue(
        client, headers, initial["branch_workspace_context_id"], "offline-drain-recovery"
    )
    assert recovered.status_code == 200, recovered.text
    assert recovered.json()["active_branch"]["id"] == initial["active_branch"]["id"]
    with factory() as session:
        assert (
            session.scalar(sa.select(models.offline_authorization_rollouts.c.state)) == "unprepared"
        )
