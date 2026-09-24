"""Signed CAT-CLASS rollout transport and central transition regressions."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
import sqlalchemy as sa
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from restaurant_os import models
from restaurant_os.catalog_classification import category_command
from restaurant_os.catalog_classification_rollout import (
    acknowledge_installation,
    get_branch_classification_mode,
    next_bundle_metadata,
    record_bundle_hash,
    rollout_status,
    transition_rollout,
)
from restaurant_os.offline_orders import sign_bundle, verify_bundle
from restaurant_os.operations import AuthorizationError, BusinessError, create_category
from test_admin_catalog import _seed_admin_catalog_scope
from test_cash_concepts import CASHIER_ID, OWNER_ID
from test_cash_ledger import _new_session
from test_offline_order_catalog import BRANCH_A, ORG_ID, _bundle_source


def test_signed_classification_generation_is_verified():
    engine, session, catalog, seed = _bundle_source()
    try:
        key = Ed25519PrivateKey.generate()
        now = int(datetime.now(UTC).timestamp())
        catalog["schema_version"] = "ord-off-catalog/v3"
        signed = sign_bundle(
            {
                "manifest": {
                    "schema_version": "ord-off/v1",
                    "organization_id": ORG_ID,
                    "branch_id": BRANCH_A,
                    "device_id": str(uuid4()),
                    "bundle_id": str(uuid4()),
                    "lease_epoch": 1,
                    "issued_at": now,
                    "expires_at": now + 7200,
                    "catalog_generation": 1,
                    "catalog_classification_mode": "legacy",
                },
                "catalog": catalog,
                "operational_seed": seed,
            },
            key,
            kid="test",
        )
        assert (
            verify_bundle(signed, {"test": key.public_key()})["manifest"]["catalog_generation"] == 1
        )
    finally:
        session.close()
        engine.dispose()




@pytest.fixture
def rollout_session():
    engine, session = _new_session()
    _seed_admin_catalog_scope(session)
    session.commit()
    yield session
    session.close()
    engine.dispose()


def _classify(session):
    for row in rollout_status(session, OWNER_ID)["groups"]:
        current = (
            session.execute(
                sa.select(models.product_categories).where(
                    models.product_categories.c.id == row["id"]
                )
            )
            .mappings()
            .one()
        )
        category_command(
            session,
            OWNER_ID,
            {
                "name": current["name"].upper(),
                "classification_code": "food",
                "expected_version": row["configuration_version"],
            },
            category_id=row["id"],
            idempotency_key="mapping-" + row["id"],
        )


def _prepare(session):
    status = rollout_status(session, OWNER_ID)
    return transition_rollout(
        session,
        OWNER_ID,
        {
            "action": "prepare",
            "expected_version": status["version"],
            "online_readiness": {row["branch_id"]: "cat-class/v1" for row in status["branches"]},
        },
        "prepare",
    )


def _issue(session, branch):
    now = datetime.now(UTC)
    if not session.scalar(
        sa.select(models.offline_order_gateway_leases.c.branch_id).where(
            models.offline_order_gateway_leases.c.branch_id == branch
        )
    ):
        session.execute(
            models.offline_order_gateway_leases.insert().values(
                branch_id=branch,
                organization_id=ORG_ID,
                device_id="device-" + branch[-8:],
                actor_id=OWNER_ID,
                public_key="synthetic",
                lease_epoch=1,
                fencing_token="test",
                status="ACTIVE",
                issued_at=now,
                expires_at=now + timedelta(hours=1),
            )
        )
    metadata = next_bundle_metadata(
        session,
        organization_id=ORG_ID,
        branch_id=branch,
        device_id="device-" + branch[-8:],
        lease_epoch=1,
        catalog_schema="ord-off-catalog/v3",
    )
    digest = str(metadata["catalog_generation"]).zfill(64)
    record_bundle_hash(session, branch, digest)
    session.commit()
    return {**metadata, "bundle_hash": digest, "lease_epoch": 1}


def _ack(session, branch, payload):
    return acknowledge_installation(
        session,
        organization_id=ORG_ID,
        branch_id=branch,
        device_id="device-" + branch[-8:],
        payload=payload,
    )


def test_prepare_requires_explicit_mapping_and_corporate_actor(rollout_session):
    session = rollout_session
    with pytest.raises(AuthorizationError):
        rollout_status(session, CASHIER_ID)
    with pytest.raises(BusinessError, match="Classify every"):
        _prepare(session)
    _classify(session)
    prepared = _prepare(session)
    assert prepared["state"] == "preparing"
    with pytest.raises(BusinessError, match="requires classification"):
        create_category(session, "UNCLASSIFIED", actor_user_id=OWNER_ID)
    assert not session.scalar(
        sa.select(models.product_categories.c.id).where(
            models.product_categories.c.name == "UNCLASSIFIED"
        )
    )


def test_prepare_is_not_installation_and_reversion_requires_new_acks(rollout_session):
    session = rollout_session
    _classify(session)
    prepared = _prepare(session)
    with pytest.raises(BusinessError, match="acknowledgement required"):
        transition_rollout(
            session,
            OWNER_ID,
            {"action": "publish", "expected_version": prepared["version"]},
            "publish",
        )
    branches = [b["branch_id"] for b in rollout_status(session, OWNER_ID)["branches"]]
    for branch in branches:
        _ack(session, branch, _issue(session, branch))
    published = transition_rollout(
        session, OWNER_ID, {"action": "publish", "expected_version": prepared["version"]}, "publish"
    )
    assert published["state"] == "adopting"
    for branch in branches:
        assert get_branch_classification_mode(session, branch) == "legacy"
        payload = _issue(session, branch)
        assert payload["catalog_classification_mode"] == "explicit"
        # Delivery and capability are not installation.
        assert rollout_status(session, OWNER_ID)["state"] == "adopting"
        with pytest.raises(BusinessError, match="exact issued"):
            _ack(session, branch, {**payload, "bundle_hash": "f" * 64})
        _ack(session, branch, payload)
        before = session.scalar(sa.select(sa.func.count()).select_from(models.audit_events))
        _ack(session, branch, payload)
        assert session.scalar(sa.select(sa.func.count()).select_from(models.audit_events)) == before
    status = rollout_status(session, OWNER_ID)
    assert status["state"] == "explicit"
    transition_rollout(
        session, OWNER_ID, {"action": "revert", "expected_version": status["version"]}, "revert"
    )
    assert rollout_status(session, OWNER_ID)["state"] == "reverting"
    for branch in branches:
        assert get_branch_classification_mode(session, branch) == "explicit"
        payload = _issue(session, branch)
        assert payload["catalog_classification_mode"] == "legacy"
        _ack(session, branch, payload)
    assert rollout_status(session, OWNER_ID)["state"] == "legacy"


def test_preparation_rejects_changed_mapping_and_ack_rejects_foreign_device(rollout_session):
    session = rollout_session
    _classify(session)
    prepared = _prepare(session)
    branch = rollout_status(session, OWNER_ID)["branches"][0]["branch_id"]
    payload = _issue(session, branch)
    with pytest.raises(BusinessError, match="Current gateway"):
        acknowledge_installation(
            session, organization_id=ORG_ID, branch_id=branch, device_id="foreign", payload=payload
        )
    category_command(
        session,
        OWNER_ID,
        {"name": "NEW GROUP", "classification_code": "drinks", "expected_version": 0},
        idempotency_key="new",
    )
    with pytest.raises(BusinessError, match="Prepare current"):
        transition_rollout(
            session,
            OWNER_ID,
            {"action": "publish", "expected_version": prepared["version"]},
            "publish",
        )


def test_rollout_audit_failure_rolls_back_and_replay_reauthorizes(rollout_session, monkeypatch):
    session = rollout_session
    _classify(session)
    from restaurant_os import catalog_classification_rollout as module

    before = session.scalar(sa.select(sa.func.count()).select_from(models.audit_events))
    with monkeypatch.context() as fault:

        def fail(*args, **kwargs):
            raise RuntimeError("injected")

        fault.setattr(module, "_audit", fail)
        with pytest.raises(RuntimeError, match="injected"):
            _prepare(session)
    assert rollout_status(session, OWNER_ID)["version"] == 0
    assert session.scalar(sa.select(sa.func.count()).select_from(models.audit_events)) == before
    saved = _prepare(session)
    assert _prepare_replay(session) == saved
    session.execute(
        models.users.update().where(models.users.c.id == OWNER_ID).values(status="inactive")
    )
    session.commit()
    with pytest.raises(AuthorizationError):
        _prepare_replay(session)


def _prepare_replay(session):
    return transition_rollout(
        session,
        OWNER_ID,
        {
            "action": "prepare",
            "expected_version": 0,
            "online_readiness": {
                b: "cat-class/v1"
                for b in session.scalars(
                    sa.select(models.branches.c.id).where(
                        models.branches.c.status == "active",
                        models.branches.c.organization_id == ORG_ID,
                    )
                )
            },
        },
        "prepare",
    )
