from __future__ import annotations

import base64
import hashlib
import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import restaurant_os.api as api_module
import sqlalchemy as sa
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient
from restaurant_os import models
from restaurant_os.auth import create_session_token
from restaurant_os.database import get_session
from restaurant_os.main import create_app
from restaurant_os.offline_order_contracts import canonical_envelope
from restaurant_os.order_execution import ExecutionContext, next_id, order_execution_context
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from test_cash_concepts import OWNER_ROLE_ID, _seed_cash_concept_scope
from test_cash_ledger import _grant_cash_permissions, _insert_shift
from test_combo_compositions import ACTOR, BRANCH_A, COMBO, ORG_ID
from test_domain_offline_orders import _seed_combo_order_scope


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _claims(token: str) -> dict[str, object]:
    payload = token.split(".")[1]
    return json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))


def test_http_bootstrap_grant_minimum_and_reconcile_receipt(monkeypatch) -> None:
    engine = sa.create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    models.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    session = factory()
    now = datetime.now(UTC)
    device_token = "offline-order-http-device-token"
    device_id = str(uuid4())
    issuer = Ed25519PrivateKey.generate()
    device_key = Ed25519PrivateKey.generate()
    try:
        _seed_cash_concept_scope(session)
        _grant_cash_permissions(session, "cash.movement.withdraw", "cash.movement.deposit")
        _insert_shift(session)
        _seed_combo_order_scope(session)
        for code in ("payments.confirm", "kds.tasks.operate", "orders.fulfill"):
            permission_id = str(uuid4())
            session.execute(
                models.permissions.insert().values(
                    id=permission_id, code=code, description=code, created_at=now
                )
            )
            session.execute(
                models.role_permissions.insert().values(
                    role_id=OWNER_ROLE_ID, permission_id=permission_id
                )
            )
        session.execute(
            models.device_credentials.insert().values(
                id=device_id,
                organization_id=ORG_ID,
                branch_id=BRANCH_A,
                capability="gateway.sync",
                token_hash=hashlib.sha256(device_token.encode()).hexdigest(),
                key_version="test",
                expires_at=now + timedelta(hours=1),
                revoked_at=None,
                created_at=now,
            )
        )
        session.commit()

        def override():
            request_session = factory()
            try:
                yield request_session
            finally:
                request_session.close()

        app = create_app()
        app.dependency_overrides[get_session] = override
        monkeypatch.setattr(api_module, "offline_order_signing_material", lambda: (issuer, "test"))
        client = TestClient(app)
        public_pem = (
            device_key.public_key()
            .public_bytes(
                serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
            )
            .decode()
        )
        gateway_headers = {"X-Device-Token": device_token}
        lease = client.post(
            "/api/v1/offline-orders/lease", headers=gateway_headers, json={"public_key": public_pem}
        )
        assert lease.status_code == 200, lease.text
        bootstrap = client.post(
            "/api/v1/offline-orders/bootstrap",
            headers=gateway_headers,
            json={"lease_epoch": 1, "public_key": public_pem},
        )
        assert bootstrap.status_code == 200, bootstrap.text
        bundle = bootstrap.json()
        with factory() as persisted:
            assert (
                persisted.scalar(
                    sa.select(sa.func.count()).select_from(models.offline_order_bundles)
                )
                == 1
            )
        bearer = create_session_token({"sub": ACTOR}, api_module.get_settings().secret_key)
        grant_response = client.post(
            "/api/v1/offline-orders/grants",
            headers={"Authorization": f"Bearer {bearer}"},
            json={
                "branch_id": BRANCH_A,
                "source_device_id": device_id,
                "bundle_id": bundle["manifest"]["bundle_id"],
                "lease_epoch": 1,
            },
        )
        assert grant_response.status_code == 200, grant_response.text
        grant = grant_response.json()["grant"]
        with factory() as persisted:
            assert (
                persisted.scalar(
                    sa.select(sa.func.count()).select_from(models.offline_order_grants)
                )
                == 1
            )
        claims = _claims(grant)
        assert "orders.create" in claims["capabilities"]
        command_id = str(uuid4())
        accepted_at = datetime.now(UTC)
        with order_execution_context(
            ExecutionContext(
                command_id=command_id,
                accepted_at=accepted_at,
                folio="B-CAJA-1",
                gateway_epoch=1,
                execution_mode="offline_reconcile",
            )
        ):
            aggregate_id = next_id()
        envelope = {
            "schema_version": "ord-off/v1",
            "command_id": command_id,
            "command_type": "create",
            "idempotency_key": "offline-http-create-001",
            "aggregate_id": aggregate_id,
            "sequence": 1,
            "previous_hash": None,
            "organization_id": ORG_ID,
            "branch_id": BRANCH_A,
            "device_id": device_id,
            "actor_id": ACTOR,
            "accepted_at": accepted_at.isoformat(),
            "grant": grant,
            "bundle_id": bundle["manifest"]["bundle_id"],
            "bundle_hash": bundle["hash"],
            "lease_epoch": 1,
            "local_sequence": 1,
            "payload": {"lines": [{"product_id": COMBO, "quantity": 1}], "register_id": "CAJA-01"},
            "device_signature": "",
        }
        envelope["device_signature"] = _b64(device_key.sign(canonical_envelope(envelope)))
        first = client.post(
            "/api/v1/offline-orders/reconcile", headers=gateway_headers, json=envelope
        )
        assert first.status_code == 200, first.text
        receipt = first.json()
        assert receipt["status"] == "confirmed" and receipt["checkpoint"] > 0
        replay = client.post(
            "/api/v1/offline-orders/reconcile", headers=gateway_headers, json=envelope
        )
        assert replay.status_code == 200, replay.text
        assert replay.json() == receipt
    finally:
        if "app" in locals():
            app.dependency_overrides.clear()
        session.close()
        engine.dispose()
