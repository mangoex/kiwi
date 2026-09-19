"""Central write fencing regressions for ORD-OFF001 gateway leases."""

from __future__ import annotations

from datetime import timedelta

import pytest
import sqlalchemy as sa
from restaurant_os import models
from restaurant_os.operations import (
    BusinessError,
    accept_pending_order,
    accept_public_order_intent,
    advance_kds_task,
    amend_order,
    apply_order_reopen_request,
    cancel_order,
    create_local_order,
    create_public_order_intent,
    fulfill_order,
    pay_order,
)
from restaurant_os.order_execution import ExecutionContext, order_execution_context
from test_cash_concepts import ORG_ID
from test_cash_ledger import BRANCH_A, NOW, _new_session
from test_combo_compositions import ACTOR, COMBO
from test_domain_offline_orders import _seed_combo_order_scope

LEASE_DEVICE = "018f6f73-2d0a-74f0-8f1c-00000000fd01"
LEASE_COMMAND = "018f6f73-2d0a-74f0-8f1c-00000000fd02"
PUBLIC_KEY = "fence-public-order-key"
REOPEN_REQUEST_ID = "018f6f73-2d0a-74f0-8f1c-00000000fd03"


def _active_lease(session, *, status: str = "ACTIVE") -> None:
    session.execute(
        models.offline_order_gateway_leases.insert().values(
            branch_id=BRANCH_A,
            organization_id=ORG_ID,
            device_id=LEASE_DEVICE,
            actor_id=ACTOR,
            public_key="synthetic-public-key",
            lease_epoch=7,
            fencing_token="f" * 64,
            status=status,
            issued_at=NOW - timedelta(hours=3),
            # Expiry alone does not reopen central direct writes.
            expires_at=NOW - timedelta(hours=1),
        )
    )
    session.commit()


def test_active_gateway_lease_fences_every_direct_order_writer_and_expiry_does_not_release() -> (
    None
):
    engine, session = _new_session()
    try:
        _seed_combo_order_scope(session)
        order = create_local_order(
            session,
            [{"product_id": COMBO, "quantity": 1}],
            register_id="CAJA-01",
            actor_user_id=ACTOR,
            idempotency_key="fence-baseline-order",
        )
        version = session.scalar(
            sa.select(models.orders.c.version).where(models.orders.c.id == order["id"])
        )
        task_id = session.scalar(
            sa.select(models.production_tasks.c.id).where(
                models.production_tasks.c.order_id == order["id"]
            )
        )
        _active_lease(session)

        def fenced(call) -> None:
            with pytest.raises(BusinessError, match="active gateway lease"):
                call()
            session.rollback()

        fenced(
            lambda: create_local_order(
                session,
                [{"product_id": COMBO, "quantity": 1}],
                register_id="CAJA-01",
                actor_user_id=ACTOR,
                idempotency_key="fence-create-order",
            )
        )
        fenced(
            lambda: pay_order(
                session,
                str(order["id"]),
                15_900,
                actor_user_id=ACTOR,
                register_id="CAJA-01",
                idempotency_key="fence-pay-order",
            )
        )
        fenced(
            lambda: advance_kds_task(
                session, str(task_id), "IN_PROGRESS", BRANCH_A, actor_user_id=ACTOR
            )
        )
        fenced(
            lambda: amend_order(
                session,
                str(order["id"]),
                [{"product_id": COMBO, "quantity": 1}],
                int(version),
                "fence-amend-order",
                ACTOR,
            )
        )
        fenced(lambda: cancel_order(session, str(order["id"]), actor_user_id=ACTOR))
        fenced(
            lambda: fulfill_order(
                session,
                str(order["id"]),
                "ready",
                "fence-fulfill-order",
                ACTOR,
            )
        )
        assert session.scalar(sa.select(sa.func.count()).select_from(models.orders)) == 1
        assert (
            session.scalar(
                sa.select(models.production_tasks.c.status).where(
                    models.production_tasks.c.id == task_id
                )
            )
            == "PENDING"
        )
    finally:
        session.close()
        engine.dispose()


def test_matching_reconcile_epoch_bypasses_fence_and_released_allows_online() -> None:
    engine, session = _new_session()
    try:
        _seed_combo_order_scope(session)
        _active_lease(session)

        def context(epoch: int) -> ExecutionContext:
            return ExecutionContext(
                command_id=LEASE_COMMAND,
                accepted_at=NOW,
                gateway_epoch=epoch,
                execution_mode="offline_reconcile",
            )

        with order_execution_context(context(8)):
            with pytest.raises(BusinessError, match="active gateway lease"):
                create_local_order(
                    session,
                    [{"product_id": COMBO, "quantity": 1}],
                    register_id="CAJA-01",
                    actor_user_id=ACTOR,
                    idempotency_key="fence-wrong-epoch",
                    commit=False,
                )
        session.rollback()

        with order_execution_context(context(7)):
            accepted = create_local_order(
                session,
                [{"product_id": COMBO, "quantity": 1}],
                register_id="CAJA-01",
                actor_user_id=ACTOR,
                idempotency_key="fence-matching-epoch",
                commit=False,
            )
        assert accepted["status"] == "ACCEPTED"
        session.rollback()

        session.execute(
            models.offline_order_gateway_leases.update()
            .where(models.offline_order_gateway_leases.c.branch_id == BRANCH_A)
            .values(status="RELEASED")
        )
        session.commit()
        allowed = create_local_order(
            session,
            [{"product_id": COMBO, "quantity": 1}],
            register_id="CAJA-01",
            actor_user_id=ACTOR,
            idempotency_key="fence-released-online",
            commit=False,
        )
        assert allowed["status"] == "ACCEPTED"
        session.rollback()
    finally:
        session.close()
        engine.dispose()


def test_active_gateway_lease_also_fences_pending_public_and_reopen_application() -> None:
    engine, session = _new_session()
    try:
        _seed_combo_order_scope(session)
        order = create_local_order(
            session,
            [{"product_id": COMBO, "quantity": 1}],
            register_id="CAJA-01",
            actor_user_id=ACTOR,
            idempotency_key="fence-special-order-001",
        )
        session.execute(
            models.orders.update()
            .where(models.orders.c.id == order["id"])
            .values(status="PENDING", accepted_at=None)
        )
        session.execute(
            models.public_order_keys.insert().values(
                public_key=PUBLIC_KEY,
                organization_id=ORG_ID,
                branch_id=BRANCH_A,
                status="active",
            )
        )
        public, _ = create_public_order_intent(
            session,
            PUBLIC_KEY,
            {
                "customer_name": "Cliente de cerca",
                "customer_phone": "5512345678",
                "order_type": "takeout",
                "lines": [{"product_id": COMBO, "quantity": 1, "modifiers": []}],
            },
            "fence-public-create-001",
        )
        public_id = session.scalar(
            sa.select(models.public_order_intents.c.id).where(
                models.public_order_intents.c.public_reference == public["public_reference"]
            )
        )
        session.execute(
            models.order_reopen_requests.insert().values(
                id=REOPEN_REQUEST_ID,
                organization_id=ORG_ID,
                branch_id=BRANCH_A,
                order_id=order["id"],
                status="REQUESTED",
                order_version_snapshot=1,
                order_status_snapshot="PENDING",
                before_snapshot={},
                reason="Solicitud de reapertura cercada",
                evidence_refs=["ticket:fence"],
                requested_by_user_id=ACTOR,
                requested_at=NOW,
                decided_by_user_id=None,
                decided_at=None,
                decision_reason=None,
                applied_by_user_id=None,
                applied_at=None,
                created_at=NOW,
                updated_at=NOW,
            )
        )
        session.commit()
        assert public_id is not None
        _active_lease(session)

        def fenced(call) -> None:
            with pytest.raises(BusinessError, match="active gateway lease"):
                call()
            session.rollback()

        fenced(lambda: accept_pending_order(session, str(order["id"]), ACTOR))
        fenced(
            lambda: accept_public_order_intent(
                session,
                str(public_id),
                1,
                "fence-public-accept-001",
                ACTOR,
            )
        )
        fenced(
            lambda: apply_order_reopen_request(
                session,
                REOPEN_REQUEST_ID,
                {},
                "fence-reopen-apply-001",
                ACTOR,
            )
        )
        assert (
            session.scalar(
                sa.select(models.orders.c.status).where(models.orders.c.id == order["id"])
            )
            == "PENDING"
        )
        assert (
            session.scalar(
                sa.select(models.public_order_intents.c.status).where(
                    models.public_order_intents.c.id == public_id
                )
            )
            == "PENDING_REVIEW"
        )
    finally:
        session.close()
        engine.dispose()


def test_fence_uses_persisted_branch_organization_outside_default_tenant():
    from restaurant_os.operations import _require_order_write_fence
    from test_sec001_operational_boundary import _operational_scope, _session

    session = _session()
    try:
        _operational_scope(session, "org-other", "branch-other")
        session.commit()
        _require_order_write_fence(session, "branch-other")
        session.execute(
            models.offline_order_gateway_leases.insert().values(
                organization_id="org-other",
                branch_id="branch-other",
                device_id=LEASE_DEVICE,
                actor_id=ACTOR,
                public_key="synthetic-public-key",
                lease_epoch=7,
                fencing_token="f" * 64,
                status="ACTIVE",
                issued_at=NOW,
                expires_at=NOW + timedelta(hours=2),
            )
        )
        session.commit()
        with pytest.raises(BusinessError) as rejected:
            _require_order_write_fence(session, "branch-other")
        assert rejected.value.code == "offline_gateway_fence_active"
    finally:
        session.close()
