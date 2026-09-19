"""Initial, signed ORD-OFF001 order bootstrap without live network access."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from edge_gateway.__main__ import main
from edge_gateway.order_runtime import prepare_orders
from edge_gateway.runtime import create_gateway_runtime
from restaurant_os.offline_order_catalog import (
    build_catalog_snapshot,
    build_operational_seed,
)
from restaurant_os.offline_orders import sign_bundle
from test_cash_concepts import ORG_ID
from test_cash_ledger import BRANCH_A
from test_combo_compositions import ACTOR
from test_offline_order_catalog import _bundle_source

DEVICE_ID = "018f6f73-2d0a-74f0-8f1c-00000000ee01"


class _Response:
    def __init__(self, payload: dict[str, Any], status_code: int = 200) -> None:
        self.payload = payload
        self.status_code = status_code

    def json(self) -> dict[str, Any]:
        return self.payload


class _BootstrapClient:
    def __init__(self, responses: dict[str, _Response]) -> None:
        self.responses = responses
        self.options: dict[str, Any] = {}
        self.requests: list[dict[str, Any]] = []
        self.closed = False

    def post(self, path: str, **kwargs: Any) -> _Response:
        self.requests.append({"path": path, **kwargs})
        return self.responses[path]

    def close(self) -> None:
        self.closed = True


class _CashClient:
    def __init__(self, **_options: Any) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


def _config(
    tmp_path: Path,
    *,
    central_key: Ed25519PrivateKey,
    device_key: Ed25519PrivateKey,
) -> tuple[Path, Path]:
    keyring = tmp_path / "keyring.json"
    keyring.write_text(
        json.dumps(
            {
                "keys": {
                    "central": central_key.public_key()
                    .public_bytes(
                        serialization.Encoding.PEM,
                        serialization.PublicFormat.SubjectPublicKeyInfo,
                    )
                    .decode("ascii")
                }
            }
        ),
        encoding="utf-8",
    )
    credential = tmp_path / "gateway.credential"
    credential.write_text("synthetic-bootstrap-token", encoding="utf-8")
    signing_key = tmp_path / "orders-device.pem"
    signing_key.write_bytes(
        device_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    bundle = tmp_path / "orders-bundle.json"
    config = tmp_path / "gateway.json"
    config.write_text(
        json.dumps(
            {
                "organization_id": ORG_ID,
                "branch_id": BRANCH_A,
                "source_device_id": DEVICE_ID,
                "runtime_root": str(tmp_path),
                "central_url": "https://central.example",
                "pos_origin": "http://localhost:5173",
                "sqlite_path": str(tmp_path / "cash.db"),
                "public_keyring_path": str(keyring),
                "credential_path": str(credential),
                "log_path": str(tmp_path / "gateway.log"),
                "orders": {
                    "database": str(tmp_path / "orders.db"),
                    "catalog_database": str(tmp_path / "catalog.db"),
                    "bundle": str(bundle),
                    "signing_key": str(signing_key),
                },
            }
        ),
        encoding="utf-8",
    )
    return config, bundle


def _signed_bundle(
    source: Any, central_key: Ed25519PrivateKey, *, branch_id: str = BRANCH_A
) -> dict[str, Any]:
    now = datetime.now(UTC).replace(microsecond=0)
    return sign_bundle(
        {
            "manifest": {
                "schema_version": "ord-off/v1",
                "organization_id": ORG_ID,
                "branch_id": branch_id,
                "device_id": DEVICE_ID,
                "bundle_id": str(uuid4()),
                "lease_epoch": 1,
                "issued_at": int(now.timestamp()),
                "expires_at": int((now + timedelta(hours=2)).timestamp()),
            },
            "catalog": build_catalog_snapshot(source, organization_id=ORG_ID, branch_id=BRANCH_A),
            "operational_seed": build_operational_seed(
                source, organization_id=ORG_ID, branch_id=BRANCH_A, actor_ids=[ACTOR]
            ),
        },
        central_key,
        kid="central",
    )


def test_prepare_orders_fetches_and_validates_bundle_before_runtime(tmp_path: Path) -> None:
    source_engine, source, _, _ = _bundle_source()
    central_key, device_key = Ed25519PrivateKey.generate(), Ed25519PrivateKey.generate()
    try:
        config, bundle_path = _config(tmp_path, central_key=central_key, device_key=device_key)
        bundle = _signed_bundle(source, central_key)
        client = _BootstrapClient(
            {
                "/api/v1/offline-orders/lease": _Response({"lease_epoch": 1}),
                "/api/v1/offline-orders/bootstrap": _Response(bundle),
            }
        )

        result = prepare_orders(
            config, client_factory=lambda **options: client.options.update(options) or client
        )

        assert result == {"status": "prepared", "bundle_hash": bundle["hash"], "lease_epoch": 1}
        assert bundle_path.is_file()
        assert client.options["verify"] is True
        assert client.options["trust_env"] is False
        assert client.options["follow_redirects"] is False
        assert set(client.options["headers"]) == {"X-Device-Token"}
        assert client.options["headers"]["X-Device-Token"] == "synthetic-bootstrap-token"
        assert [request["path"] for request in client.requests] == [
            "/api/v1/offline-orders/lease",
            "/api/v1/offline-orders/bootstrap",
        ]
        assert client.requests[1]["json"]["lease_epoch"] == 1
        assert client.closed is True

        runtime = create_gateway_runtime(
            config, client_factory=_CashClient, worker_interval_seconds=60
        )
        runtime.shutdown()
    finally:
        source.close()
        source_engine.dispose()


def test_prepare_orders_preserves_existing_operational_orders(tmp_path: Path) -> None:
    central_key, device_key = Ed25519PrivateKey.generate(), Ed25519PrivateKey.generate()
    config, bundle_path = _config(tmp_path, central_key=central_key, device_key=device_key)
    database = tmp_path / "orders.db"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE orders (id TEXT PRIMARY KEY)")
        connection.execute("INSERT INTO orders (id) VALUES ('existing-order')")
        connection.commit()
    client = _BootstrapClient({})

    with pytest.raises(ValueError, match="order_bundle_refresh_requires_protocol"):
        prepare_orders(config, client_factory=lambda **_options: client)

    assert client.requests == []
    assert not bundle_path.exists()
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT id FROM orders").fetchone() == ("existing-order",)


def test_prepare_orders_rejects_altered_or_wrong_scope_bundle_before_writing(
    tmp_path: Path,
) -> None:
    source_engine, source, _, _ = _bundle_source()
    central_key, device_key = Ed25519PrivateKey.generate(), Ed25519PrivateKey.generate()
    try:
        config, bundle_path = _config(tmp_path, central_key=central_key, device_key=device_key)
        altered = _signed_bundle(source, central_key)
        altered["signature"] = "tampered"
        client = _BootstrapClient(
            {
                "/api/v1/offline-orders/lease": _Response({"lease_epoch": 1}),
                "/api/v1/offline-orders/bootstrap": _Response(altered),
            }
        )
        with pytest.raises(ValueError, match="offline_order_bootstrap_bundle_invalid"):
            prepare_orders(config, client_factory=lambda **_options: client)
        assert not bundle_path.exists()

        wrong_scope = _signed_bundle(source, central_key, branch_id="other-branch")
        client = _BootstrapClient(
            {
                "/api/v1/offline-orders/lease": _Response({"lease_epoch": 1}),
                "/api/v1/offline-orders/bootstrap": _Response(wrong_scope),
            }
        )
        with pytest.raises(ValueError, match="offline_order_bootstrap_scope_invalid"):
            prepare_orders(config, client_factory=lambda **_options: client)
        assert not bundle_path.exists()
    finally:
        source.close()
        source_engine.dispose()


def test_prepare_orders_cli_delegates_to_bootstrap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = tmp_path / "gateway.json"
    config.write_text("{}", encoding="utf-8")
    captured: list[Path] = []
    monkeypatch.setattr(
        "edge_gateway.__main__.prepare_orders",
        lambda path: captured.append(Path(path)) or {"status": "prepared"},
    )

    assert main(["prepare-orders", "--config", str(config)]) == 0
    assert captured == [config]
