from __future__ import annotations

import base64
import hashlib
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import restaurant_os.api as api_module
import sqlalchemy as sa
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient
from restaurant_os import models
from restaurant_os.database import get_session
from restaurant_os.main import create_app
from restaurant_os.offline_orders import verify_bundle
from restaurant_os.order_lifecycle import canonical_handoff_manifest
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from test_cash_concepts import _seed_cash_concept_scope
from test_cash_ledger import _grant_cash_permissions, _insert_shift
from test_combo_compositions import BRANCH_A, ORG_ID
from test_domain_offline_orders import _seed_combo_order_scope


def _signature(key: Ed25519PrivateKey, value: dict[str, object]) -> str:
    return (
        base64.urlsafe_b64encode(key.sign(canonical_handoff_manifest(value))).decode().rstrip("=")
    )


def _credential(session, device_id: str, token: str, now: datetime) -> None:
    session.execute(
        models.device_credentials.insert().values(
            id=device_id,
            organization_id=ORG_ID,
            branch_id=BRANCH_A,
            capability="gateway.sync",
            token_hash=hashlib.sha256(token.encode()).hexdigest(),
            key_version="test",
            expires_at=now + timedelta(hours=1),
            revoked_at=None,
            created_at=now,
        )
    )


def test_http_handoff_replay_renew_and_recovery(monkeypatch) -> None:
    engine = sa.create_engine(
        "sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    models.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    seed = factory()
    now = datetime.now(UTC)
    issuer, first_key, next_key = (
        Ed25519PrivateKey.generate(),
        Ed25519PrivateKey.generate(),
        Ed25519PrivateKey.generate(),
    )
    first_id, next_id = str(uuid4()), str(uuid4())
    first_token, next_token = "lifecycle-first-token", "lifecycle-next-token"
    try:
        _seed_cash_concept_scope(seed)
        _grant_cash_permissions(seed, "cash.movement.withdraw", "cash.movement.deposit")
        _insert_shift(seed)
        _seed_combo_order_scope(seed)
        _credential(seed, first_id, first_token, now)
        _credential(seed, next_id, next_token, now)
        seed.commit()

        def override():
            request = factory()
            try:
                yield request
            finally:
                request.close()

        app = create_app()
        app.dependency_overrides[get_session] = override
        monkeypatch.setattr(api_module, "offline_order_signing_material", lambda: (issuer, "test"))
        client = TestClient(app)

        def pem(key):
            return (
                key.public_key()
                .public_bytes(
                    serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
                )
                .decode()
            )

        first_headers = {"X-Device-Token": first_token}
        assert (
            client.post(
                "/api/v1/offline-orders/lease",
                headers=first_headers,
                json={"public_key": pem(first_key)},
            ).status_code
            == 200
        )
        bootstrap = client.post(
            "/api/v1/offline-orders/bootstrap",
            headers=first_headers,
            json={"lease_epoch": 1, "public_key": pem(first_key)},
        )
        assert bootstrap.status_code == 200, bootstrap.text
        assert (
            verify_bundle(bootstrap.json(), {"test": issuer.public_key()})["manifest"][
                "lease_epoch"
            ]
            == 1
        )
        command_id, aggregate_id = str(uuid4()), str(uuid4())
        with factory() as persisted:
            persisted.execute(
                models.offline_order_inbox.insert().values(
                    command_id=command_id,
                    organization_id=ORG_ID,
                    branch_id=BRANCH_A,
                    device_id=first_id,
                    actor_id="offline-lifecycle-actor",
                    bundle_id=str(uuid4()),
                    lease_epoch=1,
                    checkpoint=1,
                    aggregate_id=aggregate_id,
                    sequence=1,
                    command_hash="a" * 64,
                    intention_hash="b" * 64,
                    envelope={"local_sequence": 1},
                    result={"status": "confirmed"},
                    status="CONFIRMED",
                    created_at=now,
                )
            )
            persisted.commit()
        manifest = {
            "schema_version": "ord-off-handoff/v1",
            "handoff_id": str(uuid4()),
            "organization_id": ORG_ID,
            "branch_id": BRANCH_A,
            "device_id": first_id,
            "lease_epoch": 1,
            "watermark": 1,
            "commands": [
                {
                    "local_sequence": 1,
                    "command_id": command_id,
                    "command_hash": "a" * 64,
                    "aggregate_id": aggregate_id,
                    "sequence": 1,
                }
            ],
        }
        body = {"manifest": manifest, "signature": _signature(first_key, manifest)}
        omitted = {**manifest, "watermark": 0, "commands": []}
        assert (
            client.post(
                "/api/v1/offline-orders/handoff",
                headers=first_headers,
                json={"manifest": omitted, "signature": _signature(first_key, omitted)},
            ).status_code
            == 409
        )
        altered = {
            **manifest,
            "commands": [{**manifest["commands"][0], "command_hash": "c" * 64}],
        }
        assert (
            client.post(
                "/api/v1/offline-orders/handoff",
                headers=first_headers,
                json={"manifest": altered, "signature": _signature(first_key, altered)},
            ).status_code
            == 409
        )
        first = client.post("/api/v1/offline-orders/handoff", headers=first_headers, json=body)
        assert first.status_code == 200, first.text
        assert first.json()["status"] == "released"
        assert (
            client.post("/api/v1/offline-orders/handoff", headers=first_headers, json=body).json()
            == first.json()
        )
        broken = {**body, "signature": "bad"}
        assert (
            client.post(
                "/api/v1/offline-orders/handoff", headers=first_headers, json=broken
            ).status_code
            == 409
        )
        # A released lease cannot renew; recovery transfers only after the persisted handoff.
        assert (
            client.post(
                "/api/v1/offline-orders/catalog-renew",
                headers=first_headers,
                json={"lease_epoch": 1, "public_key": pem(first_key)},
            ).status_code
            == 409
        )
        recovered = client.post(
            "/api/v1/offline-orders/recover-lease",
            headers={"X-Device-Token": next_token},
            json={"handoff_id": manifest["handoff_id"], "public_key": pem(next_key)},
        )
        assert recovered.status_code == 200, recovered.text
        assert recovered.json()["lease_epoch"] == 2
        assert (
            client.post(
                "/api/v1/offline-orders/catalog-renew",
                headers=first_headers,
                json={"lease_epoch": 1, "public_key": pem(first_key)},
            ).status_code
            == 409
        )
        with factory() as persisted:
            persisted.execute(
                models.offline_order_gateway_leases.update()
                .where(models.offline_order_gateway_leases.c.branch_id == BRANCH_A)
                .values(expires_at=now - timedelta(seconds=1))
            )
            persisted.commit()
        renewed = client.post(
            "/api/v1/offline-orders/catalog-renew",
            headers={"X-Device-Token": next_token},
            json={"lease_epoch": 2, "public_key": pem(next_key)},
        )
        assert renewed.status_code == 200, renewed.text
        assert (
            verify_bundle(renewed.json(), {"test": issuer.public_key()})["manifest"]["lease_epoch"]
            == 2
        )
    finally:
        if "app" in locals():
            app.dependency_overrides.clear()
        seed.close()
        engine.dispose()
