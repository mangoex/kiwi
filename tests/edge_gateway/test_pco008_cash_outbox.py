# SEC001-SYNTHETIC-FIXTURE provenance=restaurantos-pco008-edge-outbox-tests-v1
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "apps" / "edge-gateway"))

from edge_gateway import (  # noqa: E402
    CashSyncWorker,
    GatewayOutbox,
    InvalidCommandEnvelope,
    create_local_cash_app,
)
from edge_gateway.transport import HTTPXGatewayTransport  # noqa: E402


def _command() -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "command_id": "018f6f73-2d0a-74f0-8f1c-000000008001",
        "idempotency_key": "pco008-offline-cash-0001",
        "organization_id": "018f6f73-2d0a-74f0-8f1c-000000000001",
        "branch_id": "018f6f73-2d0a-74f0-8f1c-000000000003",
        "source_device_id": "018f6f73-2d0a-74f0-8f1c-000000000401",
        "actor_user_id": "018f6f73-2d0a-74f0-8f1c-000000000006",
        "command_type": "cash.movement.create.v1",
        "occurred_at": "2026-08-24T12:00:00Z",
        "accepted_at": "2026-08-24T12:00:00Z",
        "offline_grant": "synthetic.offline.grant.for-tests",
        "payload": {
            "register_id": "CAJA-01",
            "movement_type": "deposit",
            "concept_id": "018f6f73-2d0a-74f0-8f1c-000000000501",
            "amount_cents": 100,
            "reference": "LOCAL-001",
            "evidence_refs": ["evidence://synthetic/pco008"],
        },
    }


def test_pco008_outbox_is_narrow_idempotent_and_recovers_syncing(tmp_path: Path) -> None:
    outbox = GatewayOutbox(tmp_path / "gateway.db")
    command = _command()

    pending = outbox.enqueue_command(command)
    replay = outbox.enqueue_command(command)

    assert pending["status"] == "PENDING_SYNC"
    assert len(pending["request_hash"]) == 64
    assert replay["id"] == pending["id"]
    claimed = outbox.claim_pending_commands(now="2100-08-24T12:01:00Z")
    assert claimed[0]["status"] == "SYNCING"
    assert outbox.recover_syncing(now="2100-08-24T12:02:00Z") == 1
    assert outbox.list_pending_commands()[0]["id"] == pending["id"]


def test_pco008_outbox_rejects_every_other_command_and_changed_intent(tmp_path: Path) -> None:
    outbox = GatewayOutbox(tmp_path / "gateway.db")
    command = _command()
    outbox.enqueue_command(command)

    with pytest.raises(InvalidCommandEnvelope, match="unsupported_command_type"):
        outbox.enqueue_command({**command, "command_type": "order.create.v1"})
    with pytest.raises(InvalidCommandEnvelope, match="idempotency_conflict"):
        outbox.enqueue_command({**command, "payload": {**command["payload"], "amount_cents": 101}})


def test_pco008_worker_classifies_transport_confirmation_and_conflict(tmp_path: Path) -> None:
    outbox = GatewayOutbox(tmp_path / "gateway.db")
    command = _command()
    outbox.enqueue_command(command)
    transport_failures = CashSyncWorker(outbox, lambda _: (_ for _ in ()).throw(TimeoutError()))
    retried = transport_failures.reconcile_once("2100-08-24T12:01:00Z")
    assert retried[0]["status"] == "PENDING_SYNC"
    assert retried[0]["attempts"] == 1

    confirmed = CashSyncWorker(
        outbox, lambda _: {"status": "CONFIRMED", "checkpoint": 7}
    ).reconcile_once("2200-08-24T12:01:00Z")
    assert confirmed[0]["status"] == "CONFIRMED"
    assert outbox.get_sync_state(command["branch_id"])["last_checkpoint"] == 7

    second = {**_command(), "command_id": "018f6f73-2d0a-74f0-8f1c-000000008002"}
    second["idempotency_key"] = "pco008-offline-cash-0002"
    outbox.enqueue_command(second)
    conflicted = CashSyncWorker(
        outbox, lambda _: {"status": "CONFLICT", "code": "permission_denied"}
    ).reconcile_once("2200-08-24T12:02:00Z")
    assert conflicted[0]["status"] == "CONFLICT"
    assert conflicted[0]["conflict_code"] == "permission_denied"


def test_pco008_worker_sends_only_the_strict_central_envelope(tmp_path: Path) -> None:
    outbox = GatewayOutbox(tmp_path / "gateway.db")
    outbox.enqueue_command(_command())
    sent: list[dict[str, Any]] = []

    def transport(envelope: dict[str, Any]) -> dict[str, Any]:
        sent.append(envelope)
        return {"status": "CONFIRMED", "checkpoint": 1}

    CashSyncWorker(outbox, transport).reconcile_once("2100-08-24T12:01:00Z")

    assert set(sent[0]) == set(_command())
    assert not {"id", "status", "request_hash", "attempts"} & set(sent[0])


def test_pco008_local_api_derives_identity_and_redacts_grant(tmp_path: Path) -> None:
    identity = {
        "organization_id": _command()["organization_id"],
        "branch_id": _command()["branch_id"],
        "source_device_id": _command()["source_device_id"],
    }
    grant = {
        **identity,
        "actor_user_id": _command()["actor_user_id"],
        "kind": "offline_grant.v2",
        "version": 2,
        "capabilities": ["cash.movement.create.v1"],
        "iat": 0,
        "exp": 4_102_444_800,
    }
    app = create_local_cash_app(
        GatewayOutbox(tmp_path / "gateway.db"),
        identity,
        lambda token: grant if token == "synthetic.offline.grant.for-tests" else None,
    )
    client = TestClient(app)
    headers = {
        "Authorization": "Offline synthetic.offline.grant.for-tests",
        "Idempotency-Key": "pco008-local-api-0001",
    }

    created = client.post(
        "/api/v1/local/cash/movements", headers=headers, json=_command()["payload"]
    )
    replay = client.post(
        "/api/v1/local/cash/movements", headers=headers, json=_command()["payload"]
    )

    assert created.status_code == 201
    assert replay.status_code == 200
    assert created.json()["status"] == "PENDING_SYNC"
    assert replay.json()["command_id"] == created.json()["command_id"]
    assert "offline_grant" not in created.text
    assert "reference" not in created.text


def test_pco008_transport_uses_scoped_device_header_and_closed_network_options() -> None:
    class Response:
        def __init__(self, status_code: int = 200) -> None:
            self.status_code = status_code

        @staticmethod
        def json() -> dict[str, Any]:
            return {"status": "CONFIRMED", "checkpoint": 3}

    class Client:
        def __init__(self, **options: Any) -> None:
            self.options = options
            self.request: dict[str, Any] | None = None
            self.response = Response()

        def post(self, url: str, **kwargs: Any) -> Response:
            self.request = {"url": url, **kwargs}
            return self.response

        def close(self) -> None:
            pass

    client = Client()
    transport = HTTPXGatewayTransport(
        "https://central.example",
        "synthetic-device-secret",
        client_factory=lambda **options: setattr(client, "options", options) or client,
    )

    assert transport(_command()) == {"status": "CONFIRMED", "checkpoint": 3}
    assert client.options["verify"] is True
    assert client.options["trust_env"] is False
    assert client.options["follow_redirects"] is False
    assert isinstance(client.options["timeout"], httpx.Timeout)
    assert client.request is not None
    assert client.request["headers"] == {"X-Device-Token": "synthetic-device-secret"}
    client.response = Response(429)
    assert transport(_command()) == {
        "status_code": 503,
        "code": "transport_retryable",
    }
