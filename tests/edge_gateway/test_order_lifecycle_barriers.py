"""Durable authority barriers must work across separately opened gateways."""

from uuid import uuid4

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from edge_gateway.order_lifecycle import handoff_gateway
from edge_gateway.order_outbox import OrderOutbox, digest

SCOPE = dict(organization_id="org", branch_id="branch", device_id="device", lease_epoch=1)


def accept(outbox, key="barrier-order-001", epoch=1):
    command_id = str(uuid4())
    return outbox.accept(
        "actor",
        key,
        {"key": key},
        lambda session, local, previous: (
            {
                "command_id": command_id,
                "aggregate_id": command_id,
                "sequence": 1,
                "previous_hash": previous,
                "local_sequence": local,
                "bundle_hash": "a" * 64,
                **{**SCOPE, "lease_epoch": epoch},
            },
            {"id": command_id},
        ),
    )


def test_freeze_with_pending_commands_stops_another_open_writer_and_can_drain(tmp_path):
    path = tmp_path / "orders.db"
    outbox, second = OrderOutbox(path), OrderOutbox(path)
    outbox.ensure_active_bundle("a" * 64, 1)
    first = accept(outbox)
    handoff_id = str(uuid4())
    with pytest.raises(ValueError, match="reconciliation_incomplete"):
        outbox.freeze_for_handoff(handoff_id=handoff_id, **SCOPE)
    assert second.lifecycle_status() == "FREEZING"
    with pytest.raises(ValueError, match="frozen"):
        accept(second, "barrier-order-002")
    assert len(second.pending()) == 1
    second.resolve(first["command_id"], status="CONFIRMED", checkpoint=1)
    manifest = outbox.freeze_for_handoff(handoff_id=handoff_id, **SCOPE)
    assert manifest["watermark"] == 1
    assert manifest["commands"][0]["command_id"] == first["command_id"]


def test_crash_before_signature_resumes_same_frozen_handoff(tmp_path):
    path = tmp_path / "orders.db"
    outbox = OrderOutbox(path)
    outbox.ensure_active_bundle("a" * 64, 1)
    handoff_id = str(uuid4())
    manifest = outbox.freeze_for_handoff(handoff_id=handoff_id, **SCOPE)
    reopened = OrderOutbox(path)

    def send(payload):
        assert payload["manifest"] == manifest
        return {
            "handoff_id": handoff_id,
            "status": "released",
            "branch_id": "branch",
            "lease_epoch": 1,
            "watermark": 0,
            "manifest_hash": digest(manifest),
        }

    receipt = handoff_gateway(
        reopened, **SCOPE, private_key=Ed25519PrivateKey.generate(), send=send
    )
    assert receipt["handoff_id"] == handoff_id
    assert reopened.lifecycle_status() == "RELEASED"


def test_recovery_preserves_history_but_starts_a_new_epoch_manifest(tmp_path):
    outbox = OrderOutbox(tmp_path / "orders.db")
    outbox.ensure_active_bundle("a" * 64, 1)
    first = accept(outbox)
    outbox.resolve(first["command_id"], status="CONFIRMED", checkpoint=1)
    handoff_id = str(uuid4())
    manifest = outbox.freeze_for_handoff(handoff_id=handoff_id, **SCOPE)
    outbox.acknowledge_handoff(
        {
            "handoff_id": handoff_id,
            "status": "released",
            "branch_id": "branch",
            "lease_epoch": 1,
            "watermark": 1,
            "manifest_hash": digest(manifest),
        }
    )
    bundle = {"hash": "a" * 64, "manifest": {**SCOPE, "lease_epoch": 2}}
    outbox.begin_recovery_refresh(bundle, handoff_id=handoff_id, expected_previous_epoch=1)
    outbox.complete_catalog_refresh()
    second = accept(outbox, "barrier-next-epoch", epoch=2)
    assert second["local_sequence"] == 2
    assert second["envelope"]["local_sequence"] == 1
    outbox.resolve(second["command_id"], status="CONFIRMED", checkpoint=2)
    next_manifest = outbox.freeze_for_handoff(
        handoff_id=str(uuid4()),
        **{**SCOPE, "lease_epoch": 2},
    )
    assert next_manifest["watermark"] == 1
    assert next_manifest["commands"][0]["command_id"] == second["command_id"]
    assert outbox.get(first["command_id"]) == first | {"status": "CONFIRMED", "checkpoint": 1}


def test_cash_api_stops_acceptance_at_the_same_durable_barrier(tmp_path):
    from edge_gateway.local_api import create_local_cash_app
    from edge_gateway.outbox import GatewayOutbox
    from fastapi.testclient import TestClient
    from test_pco008_cash_outbox import _command

    template = _command()
    identity = {key: template[key] for key in ("organization_id", "branch_id", "source_device_id")}
    grant = {
        **identity,
        "actor_user_id": template["actor_user_id"],
        "kind": "offline_grant.v2",
        "version": 2,
        "capabilities": ["cash.movement.create.v1"],
        "iat": 0,
        "exp": 4102444800,
    }
    cash = GatewayOutbox(tmp_path / "cash.db")
    orders = OrderOutbox(tmp_path / "orders.db")
    app = create_local_cash_app(cash, identity, lambda _: grant)
    app.state.order_cash_write_barrier = orders.cash_write_barrier
    headers = {
        "Authorization": f"Offline {template['offline_grant']}",
        "Idempotency-Key": "cash-barrier-test-001",
    }
    with TestClient(app) as client:
        assert (
            client.post(
                "/api/v1/local/cash/movements", headers=headers, json=template["payload"]
            ).status_code
            == 201
        )
        orders.begin_freeze(handoff_id=str(uuid4()), **SCOPE)
        response = client.post(
            "/api/v1/local/cash/movements",
            headers={**headers, "Idempotency-Key": "cash-barrier-test-002"},
            json=template["payload"],
        )
        assert response.status_code == 409
        assert response.json()["detail"]["code"] == "gateway_orders_frozen"
    assert len(cash.list_local_status(identity)) == 1
