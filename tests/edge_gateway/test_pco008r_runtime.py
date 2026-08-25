"""PCO-008R executable runtime and central grant compatibility."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("cryptography")

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from restaurant_os.offline_grants import (  # noqa: E402
    create_offline_grant_v2,
    public_key_pem,
)

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "apps" / "edge-gateway"))

from edge_gateway.grants import verify_offline_grant_v2  # noqa: E402
from edge_gateway.runtime import create_gateway_runtime  # noqa: E402
from edge_gateway.runtime_logging import (  # noqa: E402
    close_runtime_logging,
    configure_runtime_logging,
)

UTC = timezone.utc
IDENTITY = {
    "organization_id": "018f6f73-2d0a-74f0-8f1c-000000000001",
    "branch_id": "018f6f73-2d0a-74f0-8f1c-000000000003",
    "source_device_id": "018f6f73-2d0a-74f0-8f1c-000000000401",
}


class _Response:
    status_code = 200

    @staticmethod
    def json() -> dict[str, Any]:
        return {"status": "CONFIRMED", "checkpoint": 1}


class _Client:
    def __init__(self, **options: Any) -> None:
        self.options = options
        self.closed = False

    def post(self, _url: str, **_kwargs: Any) -> _Response:
        return _Response()

    def close(self) -> None:
        self.closed = True


def _runtime_config(tmp_path: Path, private_key: Ed25519PrivateKey) -> Path:
    keyring = tmp_path / "keyring.json"
    keyring.write_text(
        json.dumps({"keys": {"active": public_key_pem(private_key).decode()}}),
        encoding="utf-8",
    )
    credential = tmp_path / "gateway.credential"
    credential.write_text("synthetic-device-secret", encoding="utf-8")
    credential.chmod(0o600)
    config = tmp_path / "gateway.json"
    config.write_text(
        json.dumps(
            {
                **IDENTITY,
                "runtime_root": str(tmp_path),
                "central_url": "https://central.example",
                "pos_origin": "http://localhost:5173",
                "sqlite_path": str(tmp_path / "gateway.db"),
                "public_keyring_path": str(keyring),
                "credential_path": str(credential),
                "log_path": str(tmp_path / "gateway.log"),
            }
        ),
        encoding="utf-8",
    )
    return config


def test_edge_verifies_the_central_canonical_vector() -> None:
    private_key = Ed25519PrivateKey.generate()
    payload = {
        **IDENTITY,
        "actor_user_id": "018f6f73-2d0a-74f0-8f1c-000000000006",
        "capabilities": ["cash.movement.create.v1"],
    }
    token = create_offline_grant_v2(payload, private_key, kid="active", now=100)

    assert verify_offline_grant_v2(token, {"active": private_key.public_key()}, now=101) == {
        **payload,
        "kind": "offline_grant.v2",
        "version": 2,
        "iat": 100,
        "exp": 7_300,
    }


def test_runtime_is_ready_loopback_composed_and_cors_exact(tmp_path: Path) -> None:
    private_key = Ed25519PrivateKey.generate()
    client = _Client()
    runtime = create_gateway_runtime(
        _runtime_config(tmp_path, private_key),
        now=lambda: datetime(2026, 8, 24, tzinfo=UTC),
        client_factory=lambda **options: setattr(client, "options", options) or client,
        worker_interval_seconds=60,
    )

    with TestClient(runtime.app) as app:
        assert app.get("/health/live").json() == {"status": "live"}
        assert app.get("/health/ready").json() == {"status": "ready"}
        assert app.get("/version").json()["service"] == "restaurantos-edge"
        allowed = app.options(
            "/api/v1/local/cash/movements",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "POST",
            },
        )
        denied = app.options(
            "/api/v1/local/cash/movements",
            headers={
                "Origin": "https://other.example",
                "Access-Control-Request-Method": "POST",
            },
        )
        assert allowed.headers["access-control-allow-origin"] == "http://localhost:5173"
        assert "access-control-allow-origin" not in denied.headers
    assert runtime.ready is False
    assert client.closed is True
    runtime_log = (tmp_path / "gateway.log").read_text(encoding="utf-8")
    assert "pco008.runtime_ready" in runtime_log
    assert "pco008.runtime_stopped" in runtime_log
    assert "synthetic-device-secret" not in runtime_log


def test_shutdown_fails_closed_and_releases_resources_when_recovery_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    private_key = Ed25519PrivateKey.generate()
    client = _Client()
    runtime = create_gateway_runtime(
        _runtime_config(tmp_path, private_key),
        now=lambda: datetime(2026, 8, 24, tzinfo=UTC),
        client_factory=lambda **options: setattr(client, "options", options) or client,
        worker_interval_seconds=60,
    )

    def fail_recovery(*, now: str) -> int:
        del now
        raise RuntimeError("synthetic_recovery_failure")

    monkeypatch.setattr(runtime.outbox, "recover_syncing", fail_recovery)
    with pytest.raises(RuntimeError, match="synthetic_recovery_failure"):
        runtime.shutdown()

    assert runtime.ready is False
    assert runtime.app.state.gateway_ready is False
    assert runtime.log_handle is None
    assert client.closed is True

    replacement_root = tmp_path / "replacement"
    replacement_root.mkdir()
    replacement_root.chmod(0o700)
    replacement = create_gateway_runtime(
        _runtime_config(replacement_root, private_key),
        now=lambda: datetime(2026, 8, 24, tzinfo=UTC),
        client_factory=_Client,
        worker_interval_seconds=60,
    )
    replacement.shutdown()


def test_failed_runtime_composition_closes_the_created_transport(tmp_path: Path) -> None:
    private_key = Ed25519PrivateKey.generate()
    client = _Client()
    active_log = configure_runtime_logging(tmp_path / "already-active.log")
    try:
        with pytest.raises(ValueError, match="gateway runtime logging is already configured"):
            create_gateway_runtime(
                _runtime_config(tmp_path, private_key),
                now=lambda: datetime(2026, 8, 24, tzinfo=UTC),
                client_factory=lambda **options: setattr(client, "options", options) or client,
                worker_interval_seconds=60,
            )
    finally:
        close_runtime_logging(active_log)

    assert client.closed is True
