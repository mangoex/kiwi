"""Validate real HTTP category responses and administrative authorization boundary."""

import json
from pathlib import Path

import jsonschema
from restaurant_os import models
from restaurant_os.database import get_session
from test_admin_catalog import _client
from test_cash_concepts import BRANCH_A, CASHIER_ID, OWNER_ID
from test_cash_ledger import NOW

SCHEMA = json.loads(
    (
        Path(__file__).resolve().parents[2]
        / "packages/contracts/schemas/catalog-category.schema.json"
    ).read_text()
)


def test_http_admin_category_contract_replay_conflict_and_branch_boundary():
    client = _client()
    sessions = client.app.dependency_overrides[get_session]()
    session = next(sessions)
    session.execute(
        models.permissions.insert().values(
            id="classification-pos", code="pos.operate", description="Operate POS", created_at=NOW
        )
    )
    session.commit()
    sessions.close()
    owner = {"X-Actor-User-Id": OWNER_ID, "Idempotency-Key": "contract-create"}
    branch = {"X-Actor-User-Id": CASHIER_ID}
    payload = {"name": "ARTESANALES", "classification_code": "drinks", "expected_version": 0}
    assert client.get("/api/v1/categories", headers=branch).status_code == 403
    assert client.post("/api/v1/categories", headers=branch, json=payload).status_code == 403
    assert client.get("/api/v1/categories").status_code in (401, 403)
    created = client.post("/api/v1/categories", headers=owner, json=payload)
    assert created.status_code == 200, created.text
    jsonschema.validate(created.json(), SCHEMA)
    replay = client.post("/api/v1/categories", headers=owner, json=payload)
    assert replay.json() == created.json()
    assert (
        client.post(
            "/api/v1/categories", headers=owner, json={**payload, "name": "DIFFERENT"}
        ).status_code
        == 409
    )
    administrative = client.get("/api/v1/categories", headers=owner)
    assert administrative.status_code == 200
    for row in administrative.json():
        jsonschema.validate(row, SCHEMA)
    operational = client.get(f"/api/v1/categories?branch_id={BRANCH_A}", headers=owner)
    assert operational.status_code == 200, operational.text
    assert operational.json()
    for row in operational.json():
        assert "classification_code" in row
        assert "configuration_version" not in row
        assert "catalog_generation" in row
        assert "catalog_hash" in row
    assert client.get("/api/v1/categories?branch_id=foreign", headers=branch).status_code == 403
