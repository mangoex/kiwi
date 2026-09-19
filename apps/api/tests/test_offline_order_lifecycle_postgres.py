"""ORD-OFF001 PostgreSQL lifecycle locking for offline gateway authority."""

from __future__ import annotations

import base64
from datetime import timedelta
from uuid import uuid4

import pytest
import sqlalchemy as sa
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from restaurant_os import models
from restaurant_os.offline_orders import (
    acquire_gateway_lease,
    lock_gateway_branch,
)
from restaurant_os.operations import BusinessError
from restaurant_os.order_lifecycle import (
    canonical_handoff_manifest,
    recover_gateway_lease,
    release_gateway_lease,
    renew_gateway_catalog,
)
from sqlalchemy.orm import Session
from test_cash_concepts import _seed_cash_concept_scope
from test_combo_compositions import ACTOR, BRANCH_A, ORG_ID
from test_domain_offline_orders import ACCEPTED_AT, _seed_combo_order_scope
from test_offline_order_reconcile_postgres import _engine


def _signature(key: Ed25519PrivateKey, manifest: dict[str, object]) -> str:
    return (
        base64.urlsafe_b64encode(key.sign(canonical_handoff_manifest(manifest)))
        .decode()
        .rstrip("=")
    )


def _manifest(*, device_id: str, lease_epoch: int) -> dict[str, object]:
    return {
        "schema_version": "ord-off-handoff/v1",
        "handoff_id": str(uuid4()),
        "organization_id": ORG_ID,
        "branch_id": BRANCH_A,
        "device_id": device_id,
        "lease_epoch": lease_epoch,
        "watermark": 0,
        "commands": [],
    }


def _assert_branch_state(engine: sa.Engine, *, device_id: str, epoch: int, status: str) -> None:
    with Session(engine) as observer:
        lease = (
            observer.execute(
                sa.select(models.offline_order_gateway_leases).where(
                    models.offline_order_gateway_leases.c.organization_id == ORG_ID,
                    models.offline_order_gateway_leases.c.branch_id == BRANCH_A,
                )
            )
            .mappings()
            .one()
        )
    assert lease["device_id"] == device_id
    assert lease["lease_epoch"] == epoch
    assert lease["status"] == status


def test_postgres_handoff_and_recovery_wait_for_branch_writer_before_transition() -> None:
    engine = _engine()
    first_key, second_key, issuer = (
        Ed25519PrivateKey.generate(),
        Ed25519PrivateKey.generate(),
        Ed25519PrivateKey.generate(),
    )
    first_id, second_id = str(uuid4()), str(uuid4())
    manifest = _manifest(device_id=first_id, lease_epoch=1)
    try:
        with Session(engine) as seed:
            _seed_cash_concept_scope(seed)
            _seed_combo_order_scope(seed)
            acquire_gateway_lease(
                seed,
                organization_id=ORG_ID,
                branch_id=BRANCH_A,
                device_id=first_id,
                actor_id=ACTOR,
                public_key=first_key.public_key(),
                now=ACCEPTED_AT,
            )
            seed.commit()

        # An online writer owns the same branch row.  The handoff must time out
        # before it can release the active epoch, leaving authority unchanged.
        with Session(engine) as writer, Session(engine) as handoff:
            lock_gateway_branch(writer, organization_id=ORG_ID, branch_id=BRANCH_A)
            handoff.execute(sa.text("SET LOCAL lock_timeout = '100ms'"))
            with pytest.raises(sa.exc.OperationalError) as blocked:
                release_gateway_lease(
                    handoff,
                    manifest=manifest,
                    signature=_signature(first_key, manifest),
                    now=ACCEPTED_AT,
                    commit=True,
                )
            assert getattr(blocked.value.orig, "sqlstate", None) == "55P03"
            handoff.rollback()
            _assert_branch_state(engine, device_id=first_id, epoch=1, status="ACTIVE")
            writer.rollback()

        with Session(engine) as handoff:
            receipt = release_gateway_lease(
                handoff,
                manifest=manifest,
                signature=_signature(first_key, manifest),
                now=ACCEPTED_AT,
                commit=True,
            )
        assert receipt["status"] == "released"
        assert receipt["lease_epoch"] == 1
        _assert_branch_state(engine, device_id=first_id, epoch=1, status="RELEASED")

        # Recovery has the same lock boundary.  It cannot increment epoch or
        # change device ownership until the competing branch writer completes.
        with Session(engine) as writer, Session(engine) as recovery:
            lock_gateway_branch(writer, organization_id=ORG_ID, branch_id=BRANCH_A)
            recovery.execute(sa.text("SET LOCAL lock_timeout = '100ms'"))
            with pytest.raises(sa.exc.OperationalError) as blocked:
                recover_gateway_lease(
                    recovery,
                    organization_id=ORG_ID,
                    branch_id=BRANCH_A,
                    device_id=second_id,
                    actor_id=ACTOR,
                    public_key=second_key.public_key(),
                    handoff_id=str(manifest["handoff_id"]),
                    now=ACCEPTED_AT + timedelta(minutes=1),
                    commit=True,
                )
            assert getattr(blocked.value.orig, "sqlstate", None) == "55P03"
            recovery.rollback()
            _assert_branch_state(engine, device_id=first_id, epoch=1, status="RELEASED")
            writer.rollback()

        with Session(engine) as recovery:
            restored = recover_gateway_lease(
                recovery,
                organization_id=ORG_ID,
                branch_id=BRANCH_A,
                device_id=second_id,
                actor_id=ACTOR,
                public_key=second_key.public_key(),
                handoff_id=str(manifest["handoff_id"]),
                now=ACCEPTED_AT + timedelta(minutes=1),
                commit=True,
            )
        assert restored["lease_epoch"] == 2
        _assert_branch_state(engine, device_id=second_id, epoch=2, status="ACTIVE")

        with Session(engine) as old_epoch:
            with pytest.raises(BusinessError) as rejected:
                renew_gateway_catalog(
                    old_epoch,
                    organization_id=ORG_ID,
                    branch_id=BRANCH_A,
                    device_id=first_id,
                    lease_epoch=1,
                    public_key=first_key.public_key(),
                    private_key=issuer,
                    kid="issuer",
                    now=ACCEPTED_AT + timedelta(minutes=2),
                )
            assert rejected.value.code == "offline_gateway_lease_invalid"
    finally:
        engine.dispose()
