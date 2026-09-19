"""CLI lifecycle regressions using signed bundles and a closed fake HTTPS client."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from edge_gateway.order_outbox import digest
from edge_gateway.order_runtime import (
    handoff_orders,
    orders_status,
    recover_orders,
    renew_orders,
)
from edge_gateway.runtime import create_gateway_runtime
from restaurant_os.offline_orders import sign_bundle
from test_offline_order_catalog import _bundle_source
from test_order_prepare import (
    DEVICE_ID,
    _BootstrapClient,
    _CashClient,
    _config,
    _Response,
    _signed_bundle,
)


class _LifecycleClient:
    def __init__(self, responses: dict[str, dict[str, Any]]) -> None:
        self.responses = responses
        self.requests: list[dict[str, Any]] = []
        self.closed = False

    def post(self, path: str, **kwargs: Any) -> _Response:
        self.requests.append({"path": path, **kwargs})
        payload = kwargs["json"]
        if path == "/api/v1/offline-orders/handoff":
            manifest = payload["manifest"]
            return _Response(
                {
                    "status": "released",
                    "handoff_id": manifest["handoff_id"],
                    "branch_id": manifest["branch_id"],
                    "lease_epoch": manifest["lease_epoch"],
                    "watermark": manifest["watermark"],
                    "manifest_hash": digest(manifest),
                }
            )
        return _Response(self.responses[path])

    def close(self) -> None:
        self.closed = True


def _epoch_bundle(source: Any, central_key: Ed25519PrivateKey, *, epoch: int) -> dict[str, Any]:
    current = _signed_bundle(source, central_key)
    return sign_bundle(
        {
            "manifest": {
                **current["manifest"],
                "bundle_id": str(uuid4()),
                "lease_epoch": epoch,
            },
            "catalog": current["catalog"],
            "operational_seed": current["operational_seed"],
        },
        central_key,
        kid="central",
    )


def test_cli_handoff_renew_recover_and_status_keep_authority_durable(tmp_path: Path) -> None:
    source_engine, source, _, _ = _bundle_source()
    central_key, device_key = Ed25519PrivateKey.generate(), Ed25519PrivateKey.generate()
    runtime = None
    try:
        config, _bundle_path = _config(tmp_path, central_key=central_key, device_key=device_key)
        initial = _signed_bundle(source, central_key)
        bootstrap = _BootstrapClient(
            {
                "/api/v1/offline-orders/lease": _Response({"lease_epoch": 1}),
                "/api/v1/offline-orders/bootstrap": _Response(initial),
            }
        )
        from edge_gateway.order_runtime import prepare_orders

        prepare_orders(config, client_factory=lambda **_options: bootstrap)
        runtime = create_gateway_runtime(
            config, client_factory=_CashClient, worker_interval_seconds=60
        )
        runtime.shutdown()
        runtime = None
        assert orders_status(config)["ready"] is True

        renewed_bundle = _epoch_bundle(source, central_key, epoch=1)
        renew_client = _LifecycleClient({"/api/v1/offline-orders/catalog-renew": renewed_bundle})
        renewal = renew_orders(config, client_factory=lambda **_options: renew_client)
        assert renewal["status"] == "renewed"
        assert renew_client.requests[0]["json"]["lease_epoch"] == 1

        handoff_client = _LifecycleClient({})
        handoff = handoff_orders(config, client_factory=lambda **_options: handoff_client)
        assert handoff["status"] == "released"
        assert orders_status(config) == {
            "ready": False,
            "lifecycle": "released",
            "bundle_hash": renewed_bundle["hash"],
            "lease_epoch": 1,
        }

        epoch_two = _epoch_bundle(source, central_key, epoch=2)
        recover_client = _LifecycleClient(
            {
                "/api/v1/offline-orders/recover-lease": {
                    "branch_id": epoch_two["manifest"]["branch_id"],
                    "status": "active",
                    "lease_epoch": 2,
                },
                "/api/v1/offline-orders/bootstrap": epoch_two,
            }
        )
        assert recover_orders(config, client_factory=lambda **_options: recover_client) == {
            "status": "recovered",
            "bundle_hash": epoch_two["hash"],
            "lease_epoch": 2,
        }
        assert orders_status(config)["ready"] is True
        assert [request["path"] for request in recover_client.requests] == [
            "/api/v1/offline-orders/recover-lease",
            "/api/v1/offline-orders/bootstrap",
        ]
    finally:
        if runtime is not None:
            runtime.shutdown()
        source.close()
        source_engine.dispose()


def test_handoff_freezes_before_rejecting_unreconciled_cash(tmp_path: Path) -> None:
    source_engine, source, _, _ = _bundle_source()
    central_key, device_key = Ed25519PrivateKey.generate(), Ed25519PrivateKey.generate()
    runtime = None
    try:
        config, _bundle_path = _config(tmp_path, central_key=central_key, device_key=device_key)
        initial = _signed_bundle(source, central_key)
        bootstrap = _BootstrapClient(
            {
                "/api/v1/offline-orders/lease": _Response({"lease_epoch": 1}),
                "/api/v1/offline-orders/bootstrap": _Response(initial),
            }
        )
        from edge_gateway.order_runtime import prepare_orders

        prepare_orders(config, client_factory=lambda **_options: bootstrap)
        runtime = create_gateway_runtime(
            config, client_factory=_CashClient, worker_interval_seconds=60
        )
        runtime.shutdown()
        runtime = None
        with sqlite3.connect(tmp_path / "cash.db") as cash:
            cash.execute(
                "INSERT INTO local_commands (command_id, idempotency_key, organization_id, "
                "branch_id, source_device_id, command_type, payload_json, status, occurred_at, "
                "created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, 'PENDING_SYNC', ?, ?)",
                (
                    str(uuid4()),
                    "cash-idempotency-key",
                    json.loads(config.read_text())["organization_id"],
                    json.loads(config.read_text())["branch_id"],
                    DEVICE_ID,
                    "cash.movement.create.v1",
                    "{}",
                    "2026-01-01T00:00:00+00:00",
                    "2026-01-01T00:00:00+00:00",
                ),
            )
        with pytest.raises(ValueError, match="offline_handoff_cash_reconciliation_incomplete"):
            handoff_orders(config, client_factory=lambda **_options: _LifecycleClient({}))
        assert orders_status(config)["lifecycle"] == "freezing"
    finally:
        if runtime is not None:
            runtime.shutdown()
        source.close()
        source_engine.dispose()
