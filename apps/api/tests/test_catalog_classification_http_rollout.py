"""HTTP issuer -> signed SQLite install -> authenticated central ack -> POS projection."""

import hashlib
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import sqlalchemy as sa
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from restaurant_os import api, models
from restaurant_os.database import get_session
from restaurant_os.offline_order_catalog import hydrate_bundle, refresh_catalog_snapshot
from restaurant_os.offline_orders import verify_bundle
from test_admin_catalog import _client
from test_cash_concepts import ORG_ID, OWNER_ID, OWNER_ROLE_ID
from test_cash_ledger import BRANCH_A


def test_http_classification_rollout_signed_install_and_scope(tmp_path, monkeypatch):
    client = _client()
    issuer, private = Ed25519PrivateKey.generate(), Ed25519PrivateKey.generate()
    monkeypatch.setattr(api, "offline_order_signing_material", lambda: (issuer, "test"))
    now = datetime.now(UTC)
    token, device = "synthetic-device-token", str(uuid4())
    override = client.app.dependency_overrides[get_session]
    iterator = override()
    session = next(iterator)
    try:
        session.execute(
            models.branches.update()
            .where(models.branches.c.id != BRANCH_A)
            .values(status="inactive")
        )
        session.execute(
            models.device_credentials.insert().values(
                id=device,
                organization_id=ORG_ID,
                branch_id=BRANCH_A,
                capability="gateway.sync",
                token_hash=hashlib.sha256(token.encode()).hexdigest(),
                key_version="test",
                expires_at=now + timedelta(hours=1),
                created_at=now,
            )
        )
        permission = session.scalar(
            sa.select(models.permissions.c.id).where(models.permissions.c.code == "pos.operate")
        )
        if not permission:
            permission = str(uuid4())
            session.execute(
                models.permissions.insert().values(
                    id=permission, code="pos.operate", description="POS test", created_at=now
                )
            )
        session.execute(
            models.role_permissions.insert().values(role_id=OWNER_ROLE_ID, permission_id=permission)
        )
        session.commit()
    finally:
        iterator.close()
    admin = {"X-Actor-User-Id": OWNER_ID}
    headers = {"X-Device-Token": token}
    for row in client.get("/api/v1/categories", headers=admin).json():
        response = client.put(
            "/api/v1/categories/" + row["id"],
            headers={**admin, "Idempotency-Key": "map-" + row["id"]},
            json={
                "name": row["name"].upper(),
                "classification_code": "food",
                "expected_version": row["configuration_version"],
            },
        )
        assert response.status_code == 200, response.text
    public = (
        private.public_key()
        .public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
        .decode()
    )
    lease = client.post(
        "/api/v1/offline-orders/lease", headers=headers, json={"public_key": public}
    )
    assert lease.status_code == 200, lease.text
    payload = {
        "public_key": public,
        "lease_epoch": lease.json()["lease_epoch"],
        "catalog_schema": "ord-off-catalog/v3",
    }
    first = client.post("/api/v1/offline-orders/bootstrap", headers=headers, json=payload)
    assert first.status_code == 200, first.text
    bundle = verify_bundle(first.json(), {"test": issuer.public_key()})
    engine = sa.create_engine("sqlite:///" + str(tmp_path / "operational.sqlite"))
    try:
        hydrate_bundle(engine, bundle, include_operational_seed=True)
        ack = {
            key: bundle["manifest"][key]
            for key in (
                "catalog_generation",
                "catalog_classification_mode",
                "bundle_hash",
                "lease_epoch",
            )
        }
        assert client.post("/api/v1/offline-orders/catalog-ack", json=ack).status_code in (401, 403)
        assert (
            client.post("/api/v1/offline-orders/catalog-ack", headers=headers, json=ack).status_code
            == 200
        )
        prepared = client.post(
            "/api/v1/catalog/classification-rollout",
            headers={**admin, "Idempotency-Key": "prepare"},
            json={
                "action": "prepare",
                "expected_version": 0,
                "online_readiness": {BRANCH_A: "cat-class/v1"},
            },
        )
        assert prepared.status_code == 200, prepared.text
        published = client.post(
            "/api/v1/catalog/classification-rollout",
            headers={**admin, "Idempotency-Key": "publish"},
            json={"action": "publish", "expected_version": prepared.json()["version"]},
        )
        assert published.status_code == 200, published.text
        next_response = client.post(
            "/api/v1/offline-orders/catalog-renew", headers=headers, json=payload
        )
        assert next_response.status_code == 200, next_response.text
        next_bundle = verify_bundle(next_response.json(), {"test": issuer.public_key()})
        assert next_bundle["manifest"]["catalog_classification_mode"] == "explicit"
        assert (
            next_bundle["manifest"]["catalog_generation"] > bundle["manifest"]["catalog_generation"]
        )
        refresh_catalog_snapshot(
            engine,
            manifest=next_bundle["manifest"],
            catalog=next_bundle["catalog"],
            operational_seed=next_bundle["operational_seed"],
        )
        ack = {key: next_bundle["manifest"][key] for key in ack}
        assert (
            client.post("/api/v1/offline-orders/catalog-ack", headers=headers, json=ack).status_code
            == 200
        )
        assert (
            client.get("/api/v1/catalog/classification-rollout", headers=admin).json()["state"]
            == "explicit"
        )
        projection = client.get("/api/v1/categories?branch_id=" + BRANCH_A, headers=admin)
        assert projection.status_code == 200, projection.text
        rows = projection.json()
        assert rows and all(row["catalog_classification_mode"] == "explicit" for row in rows)
        assert all("configuration_version" not in row for row in rows)
    finally:
        engine.dispose()
        client.close()
