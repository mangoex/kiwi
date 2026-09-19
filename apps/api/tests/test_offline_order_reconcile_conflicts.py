"""R3 reconciliation conflicts preserve the canonical transaction boundary."""

from __future__ import annotations

import base64
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy as sa
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from edge_gateway.order_outbox import OrderOutbox
from edge_gateway.order_service import LocalOrderService
from restaurant_os import models
from restaurant_os.offline_order_catalog import (
    build_catalog_snapshot,
    build_operational_seed,
    hydrate_bundle,
)
from restaurant_os.offline_order_contracts import canonical_envelope, command_hash
from restaurant_os.offline_orders import (
    _require_predecessor,
    acquire_gateway_lease,
    reconcile_order_command,
    retain_bundle,
    sign_bundle,
)
from restaurant_os.operations import AuthorizationError, BusinessError
from restaurant_os.order_execution import (
    ExecutionContext,
    next_id,
    order_execution_context,
)
from sqlalchemy.orm import Session
from test_cash_concepts import SECOND_OWNER_ID
from test_cash_ledger import BRANCH_A, _new_session
from test_combo_compositions import ACTOR, COMBO, ORG_ID
from test_domain_offline_orders import ACCEPTED_AT, _seed_combo_order_scope
from test_gateway_order_service import _token


def _claims(bundle: dict[str, object], device_id: str, actor_id: str) -> dict[str, object]:
    issued = int(ACCEPTED_AT.timestamp())
    manifest = bundle["manifest"]
    assert isinstance(manifest, dict)
    return {
        "schema_version": "ord-off-grant/v3",
        "organization_id": ORG_ID,
        "branch_id": BRANCH_A,
        "device_id": device_id,
        "bundle_id": manifest["bundle_id"],
        "bundle_hash": bundle["hash"],
        "actor_id": actor_id,
        "lease_epoch": 1,
        "capabilities": ["orders.create"],
        "iat": issued,
        "exp": issued + 7200,
    }


def _central_and_pending_envelopes(
    tmp_path: Path,
) -> tuple[
    sa.Engine,
    dict[str, object],
    dict[str, object],
    dict[str, object],
    Ed25519PrivateKey,
]:
    engine, session = _new_session()
    issuer, device = Ed25519PrivateKey.generate(), Ed25519PrivateKey.generate()
    device_id = str(uuid4())
    issued = int(ACCEPTED_AT.timestamp())
    try:
        _seed_combo_order_scope(session)
        bundle = sign_bundle(
            {
                "manifest": {
                    "schema_version": "ord-off/v1",
                    "organization_id": ORG_ID,
                    "branch_id": BRANCH_A,
                    "device_id": device_id,
                    "bundle_id": str(uuid4()),
                    "lease_epoch": 1,
                    "issued_at": issued,
                    "expires_at": issued + 7200,
                },
                "catalog": build_catalog_snapshot(
                    session, organization_id=ORG_ID, branch_id=BRANCH_A
                ),
                "operational_seed": build_operational_seed(
                    session,
                    organization_id=ORG_ID,
                    branch_id=BRANCH_A,
                    actor_ids=[ACTOR, SECOND_OWNER_ID],
                ),
            },
            issuer,
            kid="central",
        )
        acquire_gateway_lease(
            session,
            organization_id=ORG_ID,
            branch_id=BRANCH_A,
            device_id=device_id,
            actor_id=ACTOR,
            public_key=device.public_key(),
            now=ACCEPTED_AT,
        )
        retain_bundle(session, bundle, {"central": issuer.public_key()}, now=ACCEPTED_AT)
        session.commit()

        orders, catalog = OrderOutbox(tmp_path / "orders.db"), OrderOutbox(tmp_path / "catalog.db")
        hydrate_bundle(orders.engine, bundle, include_operational_seed=True)
        hydrate_bundle(catalog.engine, bundle)
        service = LocalOrderService(
            orders, catalog.engine, bundle, {"central": issuer.public_key()}, device
        )
        payload = {"lines": [{"product_id": COMBO, "quantity": 1}], "register_id": "CAJA-01"}
        service.execute(
            _token(issuer, _claims(bundle, device_id, ACTOR)),
            "create",
            payload,
            "offline-conflict-primary-001",
            now=ACCEPTED_AT,
        )
        service.execute(
            _token(issuer, _claims(bundle, device_id, SECOND_OWNER_ID)),
            "create",
            payload,
            "offline-conflict-independent-001",
            now=ACCEPTED_AT,
        )
        pending = orders.pending()
        by_actor = {row["actor_id"]: row["envelope"] for row in pending}
        return (
            engine,
            by_actor[ACTOR],
            by_actor[SECOND_OWNER_ID],
            {"central": issuer.public_key()},
            device,
        )
    finally:
        session.close()


def test_reconciliation_denial_conflicts_atomically_and_leaves_other_stream_available(
    tmp_path: Path,
) -> None:
    engine, denied_envelope, independent_envelope, keyring, device = _central_and_pending_envelopes(
        tmp_path
    )
    try:
        with Session(engine) as session:
            session.execute(
                models.users.update().where(models.users.c.id == ACTOR).values(status="inactive")
            )
            session.commit()

        with Session(engine) as session:
            uncommitted = reconcile_order_command(
                session,
                denied_envelope,
                keyring=keyring,
                now=ACCEPTED_AT,
                commit=False,
            )
            assert uncommitted["status"] == "conflict"
            assert (
                session.scalar(sa.select(sa.func.count()).select_from(models.offline_order_inbox))
                == 1
            )
            session.rollback()

        with Session(engine) as session:
            assert (
                session.scalar(sa.select(sa.func.count()).select_from(models.offline_order_inbox))
                == 0
            )
            result = reconcile_order_command(
                session,
                denied_envelope,
                keyring=keyring,
                now=ACCEPTED_AT,
                commit=True,
            )
            assert result["status"] == "conflict"
            assert result["code"] == "actor_not_authorized"
            assert session.scalar(sa.select(sa.func.count()).select_from(models.orders)) == 0
            assert (
                session.scalar(sa.select(sa.func.count()).select_from(models.inventory_movements))
                == 0
            )
            denial = (
                session.execute(
                    sa.select(models.audit_events).where(
                        models.audit_events.c.correlation_id == denied_envelope["command_id"]
                    )
                )
                .mappings()
                .one()
            )
            assert denial["action"] == "authorization.denied"
            assert denial["payload"]["reason"] == "inactive_actor"
            conflict_row = (
                session.execute(
                    sa.select(models.offline_order_inbox).where(
                        models.offline_order_inbox.c.command_id == denied_envelope["command_id"]
                    )
                )
                .mappings()
                .one()
            )
            with pytest.raises(BusinessError, match="predecessor") as predecessor:
                _require_predecessor(
                    session,
                    {
                        "aggregate_id": conflict_row["aggregate_id"],
                        "sequence": 2,
                        "previous_hash": conflict_row["command_hash"],
                    },
                )
            assert predecessor.value.code == "offline_order_predecessor_conflict"

            descendant = dict(denied_envelope)
            descendant.update(
                command_id=str(uuid4()),
                sequence=2,
                local_sequence=2,
                previous_hash=command_hash(denied_envelope),
                device_signature="",
            )
            descendant["device_signature"] = (
                base64.urlsafe_b64encode(device.sign(canonical_envelope(descendant)))
                .decode()
                .rstrip("=")
            )
            descendant_result = reconcile_order_command(
                session,
                descendant,
                keyring=keyring,
                now=ACCEPTED_AT,
                commit=True,
            )
            assert descendant_result["status"] == "conflict"
            assert descendant_result["code"] == "offline_order_predecessor_conflict"
            descendant_row = (
                session.execute(
                    sa.select(models.offline_order_inbox).where(
                        models.offline_order_inbox.c.command_id == descendant["command_id"]
                    )
                )
                .mappings()
                .one()
            )
            assert descendant_row["status"] == "CONFLICT"
            assert descendant_row["result"] == descendant_result

            wrong_hash = dict(descendant)
            wrong_hash.update(
                command_id=str(uuid4()),
                sequence=3,
                local_sequence=3,
                previous_hash="0" * 64,
                device_signature="",
            )
            wrong_hash["device_signature"] = (
                base64.urlsafe_b64encode(device.sign(canonical_envelope(wrong_hash)))
                .decode()
                .rstrip("=")
            )
            wrong_hash_result = reconcile_order_command(
                session,
                wrong_hash,
                keyring=keyring,
                now=ACCEPTED_AT,
                commit=True,
            )
            assert wrong_hash_result["status"] == "conflict"
            assert wrong_hash_result["code"] == "offline_order_predecessor_invalid"
            assert (
                session.scalar(
                    sa.select(models.offline_order_inbox.c.status).where(
                        models.offline_order_inbox.c.command_id == wrong_hash["command_id"]
                    )
                )
                == "CONFLICT"
            )

        with Session(engine) as session:
            independent = reconcile_order_command(
                session,
                independent_envelope,
                keyring=keyring,
                now=ACCEPTED_AT,
                commit=True,
            )
            assert independent["status"] == "confirmed"
            assert session.scalar(sa.select(sa.func.count()).select_from(models.orders)) == 1

            duplicate = dict(independent_envelope)
            duplicate_command_id = str(uuid4())
            duplicate_context = ExecutionContext(
                command_id=duplicate_command_id,
                accepted_at=ACCEPTED_AT,
                gateway_epoch=int(independent_envelope["lease_epoch"]),
                execution_mode="offline_reconcile",
            )
            with order_execution_context(duplicate_context):
                duplicate_aggregate_id = next_id()
            duplicate.update(
                command_id=duplicate_command_id,
                aggregate_id=duplicate_aggregate_id,
                device_signature="",
            )
            duplicate["device_signature"] = (
                base64.urlsafe_b64encode(device.sign(canonical_envelope(duplicate)))
                .decode()
                .rstrip("=")
            )
            duplicate_result = reconcile_order_command(
                session,
                duplicate,
                keyring=keyring,
                now=ACCEPTED_AT,
                commit=True,
            )
            assert duplicate_result["status"] == "conflict"
            assert duplicate_result["code"] == "offline_order_aggregate_mismatch"
            assert session.scalar(sa.select(sa.func.count()).select_from(models.orders)) == 1
            duplicate_row = (
                session.execute(
                    sa.select(models.offline_order_inbox).where(
                        models.offline_order_inbox.c.command_id == duplicate_command_id
                    )
                )
                .mappings()
                .one()
            )
            assert duplicate_row["status"] == "CONFLICT"
            assert duplicate_row["result"] == duplicate_result

        with Session(engine) as session:
            with pytest.raises(AuthorizationError, match="not authorized"):
                reconcile_order_command(
                    session,
                    denied_envelope,
                    keyring=keyring,
                    now=ACCEPTED_AT,
                    commit=True,
                )
            stored = (
                session.execute(
                    sa.select(models.offline_order_inbox).where(
                        models.offline_order_inbox.c.command_id == denied_envelope["command_id"]
                    )
                )
                .mappings()
                .one()
            )
            assert stored["result"] == result
            assert stored["status"] == "CONFLICT"
            assert session.scalar(sa.select(sa.func.count()).select_from(models.orders)) == 1
    finally:
        engine.dispose()


def test_reconciliation_closed_shift_conflicts_without_consuming_history(tmp_path: Path) -> None:
    engine, envelope, _, keyring, _ = _central_and_pending_envelopes(tmp_path)
    try:
        with Session(engine) as session:
            session.execute(models.cash_shifts.update().values(status="CLOSED"))
            session.commit()

        with Session(engine) as session:
            result = reconcile_order_command(
                session,
                envelope,
                keyring=keyring,
                now=ACCEPTED_AT,
                commit=True,
            )
            assert result["status"] == "conflict"
            assert result["code"] == "cash_shift_required"
            assert session.scalar(sa.select(sa.func.count()).select_from(models.orders)) == 0
            assert (
                session.scalar(sa.select(sa.func.count()).select_from(models.inventory_movements))
                == 0
            )
            assert (
                session.scalar(
                    sa.select(sa.func.count())
                    .select_from(models.audit_events)
                    .where(models.audit_events.c.action == "authorization.denied")
                )
                == 0
            )
            stored = (
                session.execute(
                    sa.select(models.offline_order_inbox).where(
                        models.offline_order_inbox.c.command_id == envelope["command_id"]
                    )
                )
                .mappings()
                .one()
            )
            assert stored["status"] == "CONFLICT"
            assert stored["result"] == result
    finally:
        engine.dispose()


def test_reconciliation_rejects_a_future_accepted_timestamp_without_receipt(tmp_path: Path) -> None:
    engine, envelope, _, keyring, _ = _central_and_pending_envelopes(tmp_path)
    try:
        future = dict(envelope)
        future["accepted_at"] = (ACCEPTED_AT + timedelta(seconds=1)).isoformat()
        with Session(engine) as session:
            with pytest.raises(BusinessError) as rejected:
                reconcile_order_command(
                    session,
                    future,
                    keyring=keyring,
                    now=ACCEPTED_AT,
                    commit=True,
                )
            assert rejected.value.code == "offline_order_accepted_at_future"
            assert session.scalar(sa.select(sa.func.count()).select_from(models.orders)) == 0
            assert (
                session.scalar(sa.select(sa.func.count()).select_from(models.offline_order_inbox))
                == 0
            )
    finally:
        engine.dispose()
