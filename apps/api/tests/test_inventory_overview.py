"""INV-VIEW-001: scoped, exact, non-mutating inventory projection."""

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
import sqlalchemy as sa
from restaurant_os import models
from restaurant_os.operations import ORGANIZATION_ID
from test_platform_api import (
    BRANCH_ID,
    _admin_headers,
    _branch_admin_fixture,
    _client_with_seeded_database,
    _login_headers,
    _test_session_factory,
)

ITEM = "018f6f73-2d0a-74f0-8f1c-000000000311"
UNIT = "018f6f73-2d0a-74f0-8f1c-000000000301"


def movement(session, branch: str, warehouse: str, kind: str, quantity: str) -> None:
    session.execute(
        models.inventory_movements.insert().values(
            id=str(uuid4()),
            organization_id=ORGANIZATION_ID,
            branch_id=branch,
            warehouse_id=warehouse,
            item_id=ITEM,
            unit_id=UNIT,
            movement_type=kind,
            quantity_delta=Decimal(quantity),
            reason="INV-VIEW fixture",
            created_at=datetime.now(timezone.utc),
        )
    )


def test_capabilities_and_query_do_not_change_pos_context() -> None:
    client = _client_with_seeded_database()
    branch = _branch_admin_fixture(client)
    before = client.get("/api/v1/auth/session", headers=_admin_headers()).json()
    capability = before["inventory_query_capabilities"]
    assert capability["organization_read"] is True
    assert {row["id"] for row in capability["branches"]} == {BRANCH_ID, branch["branch_id"]}
    response = client.get("/api/v1/inventory/overview?scope=organization", headers=_admin_headers())
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    rows = response.json()["items"]
    assert any(
        row["item_id"] == ITEM
        and row["branch_id"] == branch["branch_id"]
        and Decimal(row["available_quantity"]) == 0
        for row in rows
    )
    after = client.get("/api/v1/auth/session", headers=_admin_headers()).json()
    assert before["active_branch"] == after["active_branch"]
    assert before["scope"] == after["scope"]


def test_exact_reservation_projection_and_read_has_no_dml_or_advisory_lock() -> None:
    client = _client_with_seeded_database()
    branch = _branch_admin_fixture(client)
    factory = _test_session_factory(client)
    with factory() as session:
        movement(session, branch["branch_id"], branch["warehouse_id"], "OPENING_BALANCE", "10")
        movement(session, branch["branch_id"], branch["warehouse_id"], "SALE_RESERVATION", "-3")
        session.commit()
    engine = factory.kw["bind"]
    statements: list[str] = []

    def capture(_connection, _cursor, statement, _parameters, _context, _many):
        statements.append(statement.lower().strip())

    sa.event.listen(engine, "before_cursor_execute", capture)
    try:
        response = client.get(
            f"/api/v1/inventory/overview?scope=branch&branch_id={branch['branch_id']}",
            headers=_admin_headers(),
        )
    finally:
        sa.event.remove(engine, "before_cursor_execute", capture)
    assert response.status_code == 200, response.text
    row = next(row for row in response.json()["items"] if row["item_id"] == ITEM)
    assert [
        Decimal(row[key])
        for key in ("physical_quantity", "reserved_quantity", "available_quantity")
    ] == [10, 3, 7]
    assert isinstance(row["available_quantity"], str)
    assert not any(
        s.startswith(("insert ", "update ", "delete ", "create ", "alter ")) or "advisory" in s
        for s in statements
    )
    with factory() as session:
        movement(session, branch["branch_id"], branch["warehouse_id"], "RESERVATION_RELEASE", "3")
        movement(session, branch["branch_id"], branch["warehouse_id"], "SALE_CONSUMPTION", "-3")
        session.commit()
    data = client.get(
        f"/api/v1/inventory/overview?scope=branch&branch_id={branch['branch_id']}",
        headers=_admin_headers(),
    ).json()
    row = next(row for row in data["items"] if row["item_id"] == ITEM)
    assert [
        Decimal(row[key])
        for key in ("physical_quantity", "reserved_quantity", "available_quantity")
    ] == [7, 0, 7]


def test_local_reader_cannot_escalate_scope() -> None:
    client = _client_with_seeded_database()
    branch = _branch_admin_fixture(client)
    headers = _login_headers(client, "supervisor.norte@kiwi.local", "Temporal123+")
    profile = client.get("/api/v1/auth/session", headers=headers).json()
    assert profile["inventory_query_capabilities"]["organization_read"] is False
    assert [row["id"] for row in profile["inventory_query_capabilities"]["branches"]] == [
        branch["branch_id"]
    ]
    assert (
        client.get("/api/v1/inventory/overview?scope=organization", headers=headers).status_code
        == 403
    )
    assert (
        client.get(
            f"/api/v1/inventory/overview?scope=branch&branch_id={BRANCH_ID}", headers=headers
        ).status_code
        == 403
    )
    assert (
        client.get(
            f"/api/v1/inventory/overview?scope=branch&branch_id={branch['branch_id']}",
            headers=headers,
        ).status_code
        == 200
    )


@pytest.mark.parametrize(
    "query",
    [
        "",
        "scope=branch",
        "scope=other",
        "scope=organization&branch_id=" + BRANCH_ID,
        "scope=organization&limit=101",
        "scope=organization&offset=-1",
        "scope=branch&branch_id=invalid",
        "scope=organization&q=" + "a" * 121,
    ],
)
def test_invalid_contract(query: str) -> None:
    client = _client_with_seeded_database()
    assert (
        client.get("/api/v1/inventory/overview?" + query, headers=_admin_headers()).status_code
        == 422
    )


def test_pagination_local_items_and_missing_warehouse() -> None:
    client = _client_with_seeded_database()
    branch = _branch_admin_fixture(client)
    with _test_session_factory(client)() as session:
        item = dict(
            session.execute(
                sa.select(models.inventory_items).where(models.inventory_items.c.id == ITEM)
            )
            .mappings()
            .one()
        )
        session.execute(
            models.inventory_items.insert().values(
                **{
                    **item,
                    "id": str(uuid4()),
                    "sku": "LOCAL-INV",
                    "name": "Only North",
                    "catalog_scope": "branch",
                    "source_branch_id": branch["branch_id"],
                }
            )
        )
        session.commit()
    response = client.get(
        "/api/v1/inventory/overview?scope=organization&q=LOCAL-INV&limit=1",
        headers=_admin_headers(),
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["total_rows"] == 1
    assert data["items"][0]["branch_id"] == branch["branch_id"]
    assert sum(data["counts"].values()) == 1
    with _test_session_factory(client)() as session:
        session.execute(
            models.warehouses.update()
            .where(models.warehouses.c.id == branch["warehouse_id"])
            .values(status="inactive")
        )
        session.commit()
    response = client.get("/api/v1/inventory/overview?scope=organization", headers=_admin_headers())
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "inventory_warehouse_invalid"


def test_literal_search_and_exact_availability() -> None:
    client = _client_with_seeded_database()
    branch = _branch_admin_fixture(client)
    with _test_session_factory(client)() as session:
        movement(
            session, branch["branch_id"], branch["warehouse_id"], "OPENING_BALANCE", "0.004000"
        )
        session.commit()
    for literal in ["%", "_"]:
        result = client.get(
            "/api/v1/inventory/overview",
            params={"scope": "organization", "q": literal},
            headers=_admin_headers(),
        )
        assert result.status_code == 200
        assert result.json()["total_rows"] == 0
    result = client.get(
        "/api/v1/inventory/overview",
        params={
            "scope": "branch",
            "branch_id": branch["branch_id"],
            "availability": "positive",
            "limit": 1,
        },
        headers=_admin_headers(),
    ).json()
    assert result["counts"] == {"positive": 1, "zero": 0, "negative": 0}
    assert result["items"][0]["available_quantity"] == "0.004000"
    assert result["items"][0]["last_movement_at"].endswith("Z")


def test_database_failure_is_sanitized(monkeypatch, caplog) -> None:
    from restaurant_os import inventory_overview as service

    client = _client_with_seeded_database()

    def fail(*_args, **_kwargs):
        raise sa.exc.OperationalError(
            "SELECT private-driver-value",
            {"actor": "private-driver-value"},
            Exception("private-driver-value"),
        )

    monkeypatch.setattr(service, "inventory_overview", fail)
    response = client.get("/api/v1/inventory/overview?scope=organization", headers=_admin_headers())
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "inventory_overview_unavailable"
    assert "private-driver-value" not in response.text + caplog.text


def test_global_denial_is_audited_and_unrelated_org_role_does_not_escalate() -> None:
    client = _client_with_seeded_database()
    branch = _branch_admin_fixture(client)
    with _test_session_factory(client)() as session:
        role = str(uuid4())
        session.execute(
            models.roles.insert().values(
                id=role,
                organization_id=ORGANIZATION_ID,
                name="Organization unrelated",
                scope="organization",
                created_at=datetime.now(timezone.utc),
            )
        )
        session.execute(
            models.user_roles.insert().values(
                user_id=branch["supervisor_id"], role_id=role, branch_id=None
            )
        )
        session.commit()
        before = session.scalar(
            sa.select(sa.func.count())
            .select_from(models.audit_events)
            .where(models.audit_events.c.action == "authorization.denied")
        )
    headers = _login_headers(client, "supervisor.norte@kiwi.local", "Temporal123+")
    assert (
        client.get("/api/v1/inventory/overview?scope=organization", headers=headers).status_code
        == 403
    )
    with _test_session_factory(client)() as session:
        after = session.scalar(
            sa.select(sa.func.count())
            .select_from(models.audit_events)
            .where(models.audit_events.c.action == "authorization.denied")
        )
    assert after == before + 1


def test_foreign_organization_items_and_ledger_are_excluded() -> None:
    client = _client_with_seeded_database()
    with _test_session_factory(client)() as session:
        foreign_org = str(uuid4())
        session.execute(
            models.organizations.insert().values(
                id=foreign_org,
                name="Foreign",
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
        )
        item = dict(
            session.execute(
                sa.select(models.inventory_items).where(models.inventory_items.c.id == ITEM)
            )
            .mappings()
            .one()
        )
        foreign_item = str(uuid4())
        session.execute(
            models.inventory_items.insert().values(
                **{
                    **item,
                    "id": foreign_item,
                    "organization_id": foreign_org,
                    "sku": "FOREIGN",
                    "name": "Foreign item",
                }
            )
        )
        base_warehouse = session.scalar(
            sa.select(models.warehouses.c.id).where(models.warehouses.c.branch_id == BRANCH_ID)
        )
        movement(session, BRANCH_ID, base_warehouse, "OPENING_BALANCE", "999")
        session.execute(
            models.inventory_movements.update()
            .where(models.inventory_movements.c.quantity_delta == 999)
            .values(organization_id=foreign_org)
        )
        session.commit()
    data = client.get(
        "/api/v1/inventory/overview?scope=organization", headers=_admin_headers()
    ).json()
    assert foreign_item not in {row["item_id"] for row in data["items"]}
    assert all(row["available_quantity"] != "999.000000" for row in data["items"])
