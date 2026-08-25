"""HTTP boundary regressions for the recipe-only PCO-007 workspace."""

from __future__ import annotations

from collections.abc import Generator

from fastapi.testclient import TestClient
from restaurant_os import models
from restaurant_os.database import get_session
from restaurant_os.main import create_app
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from test_cash_concepts import (
    BRANCH_A,
    BRANCH_B,
    CASHIER_ID,
    OWNER_ID,
    OWNER_ROLE_ID,
)
from test_pco007_recipe_reports import ITEM_ID, PRODUCT_ID, UNIT_ID, _seed_recipe_scope


def _client() -> TestClient:
    engine = create_engine(
        "sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    models.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as session:
        # Shared seed gives actual branch/user/role FKs; recipe permission is intentionally scoped.
        from test_cash_concepts import _seed_cash_concept_scope

        _seed_cash_concept_scope(session)
        _seed_recipe_scope(session)
        recipe_permission = (
            session.execute(
                models.permissions.select().where(models.permissions.c.code == "recipes.manage")
            )
            .mappings()
            .one()
        )
        session.execute(
            models.role_permissions.insert().values(
                role_id=OWNER_ROLE_ID, permission_id=recipe_permission["id"]
            )
        )
        session.commit()
    app = create_app()

    def override() -> Generator[Session, None, None]:
        with factory() as session:
            yield session

    app.dependency_overrides[get_session] = override
    return TestClient(app)


def test_workspace_is_recipe_authorized_and_scope_is_explicit() -> None:
    client = _client()
    scoped = client.get("/api/v1/recipes/workspace", headers={"X-Actor-User-Id": CASHIER_ID})
    assert scoped.status_code == 403 and scoped.json()["detail"]["code"] == "recipe_branch_required"
    headers = {"X-Actor-User-Id": CASHIER_ID}
    allowed = client.get(f"/api/v1/recipes/workspace?branch_id={BRANCH_A}", headers=headers)
    assert allowed.status_code == 200
    assert allowed.json()["products"] == [
        {"id": PRODUCT_ID, "name": "Producto PCO007", "sku": "PCO007-P", "has_recipe": False}
    ]
    foreign = client.get(f"/api/v1/recipes/workspace?branch_id={BRANCH_B}", headers=headers)
    assert foreign.status_code == 403
    owner = client.get("/api/v1/recipes/workspace", headers={"X-Actor-User-Id": OWNER_ID})
    assert owner.status_code == 200 and owner.json()["corporate_allowed"] is True


def test_recipe_http_requires_actor_key_and_strict_json() -> None:
    client = _client()
    base = {
        "branch_id": BRANCH_A,
        "expected_active_recipe_id": None,
        "yield_quantity": 1,
        "yield_unit_id": UNIT_ID,
        "components": [
            {"item_id": ITEM_ID, "unit_id": UNIT_ID, "net_quantity": 1, "waste_rate": 0}
        ],
    }
    path = f"/api/v1/products/{PRODUCT_ID}/recipe"
    actor_headers = {"X-Actor-User-Id": CASHIER_ID}
    missing_actor = client.put(path, json=base, headers={"Idempotency-Key": "http-key"})
    assert missing_actor.status_code == 401
    missing_key = client.put(path, json=base, headers=actor_headers)
    assert missing_key.status_code == 409
    assert missing_key.json()["detail"]["code"] == "idempotency_key_required"
    extra = client.put(
        path,
        json={**base, "unexpected": True},
        headers={**actor_headers, "Idempotency-Key": "http-extra"},
    )
    assert extra.status_code == 422
    invalid_uuid = client.put(
        "/api/v1/products/not-a-uuid/recipe",
        json=base,
        headers={**actor_headers, "Idempotency-Key": "http-invalid"},
    )
    assert invalid_uuid.status_code == 422
    created = client.put(
        path, json=base, headers={**actor_headers, "Idempotency-Key": "http-create"}
    )
    assert created.status_code == 200
    replay = client.put(
        path, json=base, headers={**actor_headers, "Idempotency-Key": "http-create"}
    )
    assert replay.status_code == 200 and replay.json()["id"] == created.json()["id"]
    manager_payload = {
        **base,
        "expected_active_recipe_id": created.json()["id"],
        "yield_quantity": "1",
        "components": [{
            "item_id": ITEM_ID, "unit_id": UNIT_ID, "net_quantity": "1", "waste_rate": "0",
        }],
    }
    manager_compatible = client.put(
        path, json=manager_payload,
        headers={**actor_headers, "Idempotency-Key": "recipe-manager-string-payload"},
    )
    assert manager_compatible.status_code == 200
    changed_key = client.put(
        path,
        json={**base, "expected_active_recipe_id": created.json()["id"]},
        headers={**actor_headers, "Idempotency-Key": "http-create"},
    )
    assert changed_key.status_code == 409
    assert changed_key.json()["detail"]["code"] == "idempotency_conflict"
    stale = client.put(path, json=base, headers={**actor_headers, "Idempotency-Key": "http-stale"})
    assert stale.status_code == 409
    assert stale.json()["detail"]["code"] == "recipe_version_conflict"
