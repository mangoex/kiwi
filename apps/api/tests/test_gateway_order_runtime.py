"""Real ORD-OFF001 gateway runtime composition over two SQLite databases."""

from __future__ import annotations

import base64
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
import sqlalchemy as sa
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from edge_gateway.runtime import create_gateway_runtime
from fastapi.testclient import TestClient
from restaurant_os import models
from restaurant_os.offline_order_catalog import build_catalog_snapshot, build_operational_seed
from restaurant_os.offline_orders import sign_bundle
from sqlalchemy import text
from sqlalchemy.orm import Session
from test_cash_concepts import ORG_ID
from test_cash_ledger import BRANCH_A
from test_combo_compositions import ACTOR, COMBO
from test_offline_order_catalog import _bundle_source

DEVICE_ID = "018f6f73-2d0a-74f0-8f1c-00000000ee01"


class _Response:
    status_code = 200

    @staticmethod
    def json() -> dict[str, Any]:
        return {"status": "CONFIRMED", "checkpoint": 1}


class _Client:
    def __init__(self, **_options: Any) -> None:
        self.closed = False

    def post(self, _url: str, **_kwargs: Any) -> _Response:
        return _Response()

    def close(self) -> None:
        self.closed = True


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _order_grant(
    private_key: Ed25519PrivateKey, *, manifest: dict[str, Any], bundle_hash: str, now: datetime
) -> str:
    header = {"alg": "EdDSA", "typ": "order_grant.v3", "version": 3, "kid": "central"}
    claims = {
        "schema_version": "ord-off-grant/v3",
        "organization_id": ORG_ID,
        "branch_id": BRANCH_A,
        "device_id": DEVICE_ID,
        "bundle_id": manifest["bundle_id"],
        "bundle_hash": bundle_hash,
        "actor_id": ACTOR,
        "lease_epoch": 1,
        "capabilities": [
            "orders.create",
            "orders.read",
            "payments.confirm",
            "kds.tasks.operate",
            "orders.amend",
            "orders.cancel",
            "orders.fulfill",
            "pos.operate",
            "cash.shift.read",
        ],
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=30)).timestamp()),
    }
    encoded_header = _b64(json.dumps(header, sort_keys=True).encode())
    encoded_claims = _b64(json.dumps(claims, sort_keys=True).encode())
    signed = f"{encoded_header}.{encoded_claims}"
    return f"{signed}.{_b64(private_key.sign(signed.encode('ascii')))}"


def _runtime_config(
    tmp_path: Path,
    central_key: Ed25519PrivateKey,
    device_key: Ed25519PrivateKey,
    bundle: dict[str, Any],
) -> Path:
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
    credential.write_text("synthetic-gateway-credential", encoding="utf-8")
    signing_key = tmp_path / "orders-device.pem"
    signing_key.write_bytes(
        device_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    bundle_path = tmp_path / "orders-bundle.json"
    bundle_path.write_text(json.dumps(bundle), encoding="utf-8")
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
                    "bundle": str(bundle_path),
                    "signing_key": str(signing_key),
                },
            }
        ),
        encoding="utf-8",
    )
    return config


def test_gateway_runtime_hydrates_signed_bundle_and_preserves_it_on_restart(tmp_path: Path) -> None:
    source_engine, source, catalog, seed = _bundle_source()
    central_key, device_key = Ed25519PrivateKey.generate(), Ed25519PrivateKey.generate()
    now = datetime.now(UTC).replace(microsecond=0)
    try:
        role_id = source.scalar(
            sa.select(models.user_roles.c.role_id).where(models.user_roles.c.user_id == ACTOR)
        )
        source.execute(
            models.permissions.insert().values(
                id="runtime-kds-operate",
                code="kds.tasks.operate",
                description="kds.tasks.operate",
                created_at=now,
            )
        )
        source.execute(
            models.role_permissions.insert().values(
                role_id=role_id, permission_id="runtime-kds-operate"
            )
        )
        source.commit()
        catalog = build_catalog_snapshot(source, organization_id=ORG_ID, branch_id=BRANCH_A)
        seed = build_operational_seed(
            source, organization_id=ORG_ID, branch_id=BRANCH_A, actor_ids=[ACTOR]
        )
        manifest = {
            "schema_version": "ord-off/v1",
            "organization_id": ORG_ID,
            "branch_id": BRANCH_A,
            "device_id": DEVICE_ID,
            "bundle_id": str(uuid4()),
            "lease_epoch": 1,
            "issued_at": int(now.timestamp()),
            "expires_at": int((now + timedelta(hours=2)).timestamp()),
        }
        bundle = sign_bundle(
            {"manifest": manifest, "catalog": catalog, "operational_seed": seed},
            central_key,
            kid="central",
        )
        config = _runtime_config(tmp_path, central_key, device_key, bundle)
        token = _order_grant(
            central_key,
            manifest=bundle["manifest"],
            bundle_hash=bundle["hash"],
            now=now,
        )
        headers = {
            "Authorization": f"Offline {token}",
            "Idempotency-Key": "runtime-order-create-001",
        }

        runtime = create_gateway_runtime(config, client_factory=_Client, worker_interval_seconds=60)
        with TestClient(runtime.app) as client:
            status = client.get("/api/v1/local/orders/status")
            assert status.status_code == 200
            assert status.json()["ready"] is True
            assert status.json()["bundle_hash"] == bundle["hash"]
            assert (
                client.get("/api/v1/local/order-api/auth/session", headers=headers).status_code
                == 200
            )
            assert (
                client.get("/api/v1/local/order-api/catalog/products", headers=headers).status_code
                == 200
            )
            quote = client.post(
                "/api/v1/local/order-api/orders/quote",
                headers=headers,
                json={"lines": [{"product_id": COMBO, "quantity": 1}]},
            )
            assert quote.status_code == 200
            assert quote.json()["total_cents"] == 15_900
            created = client.post(
                "/api/v1/local/order-api/orders",
                headers=headers,
                json={"lines": [{"product_id": COMBO, "quantity": 1}], "register_id": "CAJA-01"},
            )
            assert created.status_code == 200, created.text
            order_id = created.json()["id"]
            detail = client.get(f"/api/v1/local/order-api/orders/{order_id}", headers=headers)
            assert detail.status_code == 200
            task_id = detail.json()["production_tasks"][0]["id"]
            kds = client.post(
                f"/api/v1/local/order-api/kds/tasks/{task_id}/transition",
                headers={**headers, "Idempotency-Key": "runtime-kds-transition-001"},
                json={"status": "IN_PROGRESS"},
            )
            assert kds.status_code == 200, kds.text
            assert kds.json()["status"] == "IN_PROGRESS"
            with Session(runtime.order_service.catalog_engine) as frozen:
                assert frozen.scalar(text("PRAGMA query_only")) == 1
                assert frozen.scalar(text("SELECT count(*) FROM products")) == 3
                with pytest.raises(sa.exc.OperationalError):
                    frozen.execute(text("UPDATE products SET name = name"))

        restarted = create_gateway_runtime(
            config, client_factory=_Client, worker_interval_seconds=60
        )
        with TestClient(restarted.app) as client:
            command_id = created.json()["_offline"]["command_id"]
            response = client.get(f"/api/v1/local/orders/commands/{command_id}", headers=headers)
            assert response.status_code == 200
            assert response.json()["_offline"]["status"] == "PENDING_SYNC"
            recovered = client.post(
                "/api/v1/local/order-api/orders/recover", headers=headers, json={}
            )
            assert recovered.status_code == 200, recovered.text
            assert recovered.json()["id"] == order_id
            with Session(restarted.order_service.outbox.engine) as persisted:
                assert persisted.scalar(sa.select(sa.func.count()).select_from(models.orders)) == 1
    finally:
        source.close()
        source_engine.dispose()
