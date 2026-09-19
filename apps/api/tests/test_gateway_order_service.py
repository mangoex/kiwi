"""Real canonical order creation through the durable gateway boundary."""

import base64
import json
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
from restaurant_os.offline_orders import sign_bundle
from restaurant_os.operations import BusinessError
from sqlalchemy.orm import Session
from test_cash_concepts import (
    OWNER_ROLE_ID,
    _seed_cash_concept_scope,
)
from test_cash_ledger import _grant_cash_permissions, _insert_shift
from test_combo_compositions import ACTOR, BRANCH_A, COMBO, ORG_ID
from test_domain_offline_orders import ACCEPTED_AT, _seed_combo_order_scope


def _token(private, claims):
    def encode(value):
        return base64.urlsafe_b64encode(value).decode().rstrip("=")

    header = {"alg": "EdDSA", "typ": "order_grant.v3", "version": 3, "kid": "central"}
    signed = f"{encode(json.dumps(header).encode())}.{encode(json.dumps(claims).encode())}"
    return f"{signed}.{encode(private.sign(signed.encode()))}"


def test_real_combo_acceptance_is_atomic_and_idempotent(tmp_path):
    outbox = OrderOutbox(tmp_path / "orders.db")
    models.metadata.create_all(outbox.engine)
    with Session(outbox.engine) as session:
        _seed_cash_concept_scope(session)
        _grant_cash_permissions(
            session,
            "cash.movement.withdraw",
            "cash.movement.deposit",
            "cash.movement.compensate",
            "cash.movement.read",
            "cash.shift.close",
        )
        _insert_shift(session)
        _seed_combo_order_scope(session)
        for code in ("payments.confirm", "kds.tasks.operate", "orders.fulfill"):
            permission_id = str(uuid4())
            session.execute(
                models.permissions.insert().values(
                    id=permission_id, code=code, description=code, created_at=ACCEPTED_AT
                )
            )
            session.execute(
                models.role_permissions.insert().values(
                    role_id=OWNER_ROLE_ID, permission_id=permission_id
                )
            )
        session.commit()
    issuer, device = Ed25519PrivateKey.generate(), Ed25519PrivateKey.generate()
    issued = int(ACCEPTED_AT.timestamp())
    manifest = {
        "schema_version": "ord-off/v1",
        "organization_id": ORG_ID,
        "branch_id": BRANCH_A,
        "device_id": str(uuid4()),
        "bundle_id": str(uuid4()),
        "lease_epoch": 1,
        "issued_at": issued,
        "expires_at": issued + 7200,
    }
    with Session(outbox.engine) as source:
        bundle = sign_bundle(
            {
                "manifest": manifest,
                "catalog": build_catalog_snapshot(
                    source, organization_id=ORG_ID, branch_id=BRANCH_A
                ),
                "operational_seed": build_operational_seed(
                    source, organization_id=ORG_ID, branch_id=BRANCH_A, actor_ids=[ACTOR]
                ),
            },
            issuer,
            kid="central",
        )
    claims = {
        "schema_version": "ord-off-grant/v3",
        "organization_id": ORG_ID,
        "branch_id": BRANCH_A,
        "device_id": manifest["device_id"],
        "bundle_id": manifest["bundle_id"],
        "bundle_hash": bundle["hash"],
        "actor_id": ACTOR,
        "lease_epoch": 1,
        "capabilities": [
            "orders.create",
            "payments.confirm",
            "kds.tasks.operate",
            "orders.fulfill",
        ],
        "iat": issued,
        "exp": issued + 7200,
    }
    token = _token(issuer, claims)
    outbox.engine.dispose()
    outbox = OrderOutbox(tmp_path / "gateway-orders.db")
    catalog = OrderOutbox(tmp_path / "gateway-catalog.db")
    hydrate_bundle(outbox.engine, bundle, include_operational_seed=True)
    hydrate_bundle(catalog.engine, bundle)
    service = LocalOrderService(
        outbox, catalog.engine, bundle, {"central": issuer.public_key()}, device
    )
    payload = {"lines": [{"product_id": COMBO, "quantity": 1}], "register_id": "CAJA-01"}
    result = service.execute(token, "create", payload, "gateway-real-combo-001", now=ACCEPTED_AT)
    replay = service.execute(token, "create", payload, "gateway-real-combo-001", now=ACCEPTED_AT)
    assert result == replay
    assert result["total_cents"] == 15900
    assert result["_offline"]["status"] == "PENDING_SYNC"
    with Session(outbox.engine) as session:
        assert session.scalar(sa.select(sa.func.count()).select_from(models.orders)) == 1
        assert session.scalar(sa.select(sa.func.count()).select_from(models.production_tasks)) == 2
    assert len(outbox.pending()) == 1
    payment = service.execute(
        token,
        "pay",
        {"amount_cents": 15900, "method": "cash", "register_id": "CAJA-01"},
        "gateway-real-payment-001",
        aggregate_id=result["id"],
        now=ACCEPTED_AT,
    )
    assert payment["_offline"]["status"] == "PENDING_SYNC"
    for task in result["production_tasks"]:
        for status in ("IN_PROGRESS", "COMPLETED"):
            service.execute(
                token,
                "kds_transition",
                {"task_id": task["id"], "status": status},
                f"gateway-task-{task['id']}-{status}",
                aggregate_id=result["id"],
                now=ACCEPTED_AT,
            )
    for command in ("deliver", "close"):
        final = service.execute(
            token,
            "fulfill",
            {"command": command},
            f"gateway-fulfillment-{command}",
            aggregate_id=result["id"],
            now=ACCEPTED_AT,
        )
    assert final["status"] == "CLOSED"
    with Session(outbox.engine) as session:
        assert session.scalar(sa.select(sa.func.count()).select_from(models.payments)) == 1
        session.execute(
            models.users.update().where(models.users.c.id == ACTOR).values(status="inactive")
        )
        session.commit()
    with pytest.raises(BusinessError):
        service.execute(token, "create", payload, "gateway-denied-order-001", now=ACCEPTED_AT)
    with Session(outbox.engine) as session:
        assert session.scalar(sa.select(sa.func.count()).select_from(models.orders)) == 1
        assert (
            session.scalar(
                sa.select(sa.func.count())
                .select_from(models.audit_events)
                .where(models.audit_events.c.action == "authorization.denied")
            )
            == 1
        )
