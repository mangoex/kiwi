"""TDD-TC-358/360: read-only stock thresholds at the external agent boundary."""

from __future__ import annotations

import os
from collections.abc import Generator
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy as sa
import yaml
from fixture_metadata import create_fixture_tables
from restaurant_os import models
from sqlalchemy.orm import Session, sessionmaker
from test_agent_tools import (
    ADMIN_USER_ID,
    BRANCH_ID,
    FOREIGN_ORGANIZATION_ID,
    ITEM_ID,
    ORGANIZATION_ID,
    SECOND_BRANCH_ID,
    SECOND_WAREHOUSE_ID,
    UNIT_ID,
    WAREHOUSE_ID,
    _client,
    _configure,
    _factory,
    _token,
)
from test_platform_api import _seed

ROOT = Path(__file__).resolve().parents[3]
NOW = datetime(2026, 10, 27, 12, tzinfo=timezone.utc)


@pytest.fixture(params=["sqlite", "postgresql"])
def stock_factory(request: pytest.FixtureRequest) -> Generator[sessionmaker[Session], None, None]:
    if request.param == "sqlite":
        factory = _factory()
        try:
            yield factory
        finally:
            factory.kw["bind"].dispose()
        return
    url = os.environ.get("GROKBOT_TEST_POSTGRES_URL")
    if not url:
        pytest.skip("GROKBOT_TEST_POSTGRES_URL is required for PostgreSQL stock evidence")
    parsed = sa.engine.make_url(url)
    assert parsed.host in {"127.0.0.1", "localhost"}
    assert (parsed.database or "").startswith("grokbot_")
    # A new schema per test preserves other test data in the local CI database.
    schema = f"agent_stock_{uuid4().hex}"
    control = sa.create_engine(url)
    with control.begin() as connection:
        connection.execute(sa.schema.CreateSchema(schema))
    engine = sa.create_engine(url, connect_args={"options": f"-csearch_path={schema}"})
    try:
        create_fixture_tables(engine)
        factory = sessionmaker(bind=engine, expire_on_commit=False)
        with factory() as session:
            _seed(session)
        yield factory
    finally:
        engine.dispose()
        with control.begin() as connection:
            connection.execute(sa.schema.DropSchema(schema, cascade=True))
        control.dispose()


def _threshold(session: Session, **overrides: object) -> None:
    session.execute(
        models.inventory_stock_thresholds.insert().values(
            **{
                "id": str(uuid4()),
                "organization_id": ORGANIZATION_ID,
                "branch_id": BRANCH_ID,
                "warehouse_id": WAREHOUSE_ID,
                "item_id": ITEM_ID,
                "minimum_quantity": Decimal("1.123456"),
                "maximum_quantity": Decimal("25.987654"),
                "version": 1,
                "created_by": ADMIN_USER_ID,
                "updated_by": ADMIN_USER_ID,
                "created_at": NOW,
                "updated_at": NOW,
                **overrides,
            }
        )
    )


def _snapshot(factory: sessionmaker[Session]) -> dict[str, list[dict]]:
    with factory() as session:
        return {
            table.name: [dict(row) for row in session.execute(sa.select(table)).mappings()]
            for table in (
                models.inventory_stock_thresholds,
                models.inventory_cost_states,
                models.inventory_movements,
                models.inventory_items,
            )
        }


@pytest.mark.parametrize("minimum", ["0", "1.123456"])
def test_tdd_tc_360_stock_thresholds_exact_nullable_scoped_and_read_only(
    stock_factory: sessionmaker[Session], minimum: str
) -> None:
    with stock_factory() as session:
        # Valid referenced rows, but mismatched scope on decoy thresholds: each join key matters.
        branch = dict(session.execute(sa.select(models.branches)).mappings().first())
        session.execute(
            models.branches.insert().values(
                **{**branch, "id": SECOND_BRANCH_ID, "code": "OTHER", "name": "Other branch"}
            )
        )
        warehouse = dict(session.execute(sa.select(models.warehouses)).mappings().first())
        session.execute(
            models.warehouses.insert().values(
                **{**warehouse, "id": SECOND_WAREHOUSE_ID, "branch_id": SECOND_BRANCH_ID}
            )
        )
        organization = dict(session.execute(sa.select(models.organizations)).mappings().first())
        session.execute(
            models.organizations.insert().values(
                **{**organization, "id": FOREIGN_ORGANIZATION_ID, "name": "Other organization"}
            )
        )
        _threshold(session, minimum_quantity=Decimal(minimum))
        for scope in (
            {"branch_id": SECOND_BRANCH_ID},
            {"warehouse_id": SECOND_WAREHOUSE_ID},
            {"organization_id": FOREIGN_ORGANIZATION_ID},
        ):
            _threshold(
                session, **scope, minimum_quantity=Decimal("777"), maximum_quantity=Decimal("999")
            )
        # Only the canonical warehouse's stock may be returned, without duplicate items.
        session.execute(models.inventory_cost_states.delete())
        for warehouse_id, quantity in ((WAREHOUSE_ID, "3.123456"), (SECOND_WAREHOUSE_ID, "777")):
            session.execute(
                models.inventory_cost_states.insert().values(
                    branch_id=BRANCH_ID,
                    warehouse_id=warehouse_id,
                    item_id=ITEM_ID,
                    quantity_on_hand=Decimal(quantity),
                    average_unit_cost=0,
                    last_unit_cost=0,
                    updated_at=NOW,
                )
            )
        session.commit()
        expected_ids = set(session.scalars(sa.select(models.inventory_items.c.id)))
    client = _client(stock_factory)
    credentials = _configure(client, "inventory", ["agent.inventory.read"])
    headers = {"Authorization": f"Bearer {_token(client, *credentials)}"}
    before = _snapshot(stock_factory)
    rows = []
    params = {"branch_id": BRANCH_ID, "limit": "1"}
    for _ in range(len(expected_ids) + 1):
        response = client.get("/api/v1/agent-tools/inventory/stock", params=params, headers=headers)
        assert response.status_code == 200, response.text
        payload = response.json()
        rows.extend(payload["items"])
        if not payload["page"]["has_more"]:
            break
        params["cursor"] = payload["page"]["next_cursor"]
    assert len(rows) == len(expected_ids)
    assert {row["item_id"] for row in rows} == expected_ids
    for row in rows:
        assert set(row) == {
            "item_id",
            "unit_id",
            "available_quantity",
            "as_of",
            "min_quantity",
            "max_quantity",
        }
        if row["item_id"] == ITEM_ID:
            assert row["unit_id"] == UNIT_ID
            assert isinstance(row["min_quantity"], str)
            assert Decimal(row["min_quantity"]) == Decimal(minimum)
            assert Decimal(row["max_quantity"]) == Decimal("25.987654")
            assert Decimal(row["available_quantity"]) == Decimal("3.123456")
        else:
            assert row["min_quantity"] is None and row["max_quantity"] is None
            assert Decimal(row["available_quantity"]) == 0
    assert _snapshot(stock_factory) == before

    # A configured item with no cost state is still returned with thresholds and zero stock.
    with stock_factory() as session:
        session.execute(models.inventory_cost_states.delete())
        session.commit()
    response = client.get(
        "/api/v1/agent-tools/inventory/stock", params={"branch_id": BRANCH_ID}, headers=headers
    )
    assert response.status_code == 200, response.text
    configured = next(row for row in response.json()["items"] if row["item_id"] == ITEM_ID)
    assert Decimal(configured["available_quantity"]) == 0
    assert Decimal(configured["min_quantity"]) == Decimal(minimum)
    assert Decimal(configured["max_quantity"]) == Decimal("25.987654")


def test_tdd_tc_360_stock_requires_capability_and_branch_allowlist() -> None:
    client = _client(_factory())
    credentials = _configure(client, "inventory", ["agent.inventory.read"])
    headers = {"Authorization": f"Bearer {_token(client, *credentials)}"}
    response = client.get(
        "/api/v1/agent-tools/inventory/stock",
        params={"branch_id": SECOND_BRANCH_ID},
        headers=headers,
    )
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "agent_branch_denied"
    credentials = _configure(client, "inventory", ["agent.context.read"])
    response = client.get(
        "/api/v1/agent-tools/inventory/stock",
        params={"branch_id": BRANCH_ID},
        headers={"Authorization": f"Bearer {_token(client, *credentials)}"},
    )
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "agent_capability_denied"


def test_tdd_tc_360_stock_without_active_canonical_warehouse_fails_closed() -> None:
    factory = _factory()
    client = _client(factory)
    credentials = _configure(client, "inventory", ["agent.inventory.read"])
    with factory() as session:
        session.execute(models.warehouses.update().values(status="inactive"))
        session.commit()
    response = client.get(
        "/api/v1/agent-tools/inventory/stock",
        params={"branch_id": BRANCH_ID},
        headers={"Authorization": f"Bearer {_token(client, *credentials)}"},
    )
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "dependency_unavailable"


def test_tdd_tc_358_stock_thresholds_documented_in_shared_and_runtime_openapi() -> None:
    contract = yaml.safe_load(
        (ROOT / "packages/contracts/openapi/kiwi-agent-tools-v1.openapi.yaml").read_text(
            encoding="utf-8"
        )
    )
    runtime = _client(_factory()).get("/openapi.json").json()
    for schema in (contract, runtime):
        response = schema["paths"]["/api/v1/agent-tools/inventory/stock"]["get"]["responses"]["200"]
        page_name = response["content"]["application/json"]["schema"]["$ref"].rsplit("/", 1)[1]
        page = schema["components"]["schemas"][page_name]
        stock_name = page["properties"]["items"]["items"]["$ref"].rsplit("/", 1)[1]
        stock = schema["components"]["schemas"][stock_name]
        for field in ("min_quantity", "max_quantity"):
            assert field in stock["properties"]
            variants = stock["properties"][field]["anyOf"]
            assert {variant["type"] for variant in variants} == {"string", "null"}
        assert stock["additionalProperties"] is False
