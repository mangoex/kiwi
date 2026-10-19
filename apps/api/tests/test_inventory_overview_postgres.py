"""Real PostgreSQL isolation and bounded inventory-query evidence."""

import os
from time import perf_counter
from uuid import uuid4

import pytest
import sqlalchemy as sa
from restaurant_os import inventory_overview as service
from restaurant_os import models
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from test_inventory_overview import ITEM, movement
from test_platform_api import ADMIN_USER_ID, BRANCH_ID, _seed


@pytest.fixture
def overview_engine():
    raw = os.environ.get("INV_VIEW_TEST_POSTGRES_URL")
    if not raw:
        pytest.skip("INV_VIEW_TEST_POSTGRES_URL is required by the PostgreSQL gate")
    url = make_url(raw)
    if (
        url.host not in {"127.0.0.1", "localhost"}
        or not url.drivername.startswith("postgresql")
        or not (url.database or "").startswith("inv_view_")
        or url.query
    ):
        raise RuntimeError("Inventory tests require an isolated local inv_view_* database")
    admin = sa.create_engine(raw)
    schema = "inv_view_" + uuid4().hex
    with admin.begin() as connection:
        connection.execute(sa.text(f'CREATE SCHEMA "{schema}"'))
    engine = sa.create_engine(
        raw,
        connect_args={
            "options": f"-c search_path={schema} -c statement_timeout=15000 -c lock_timeout=3000"
        },
    )
    try:
        models.metadata.create_all(engine)
        with Session(engine) as session:
            _seed(session)
        yield engine
    finally:
        engine.dispose()
        with admin.begin() as connection:
            connection.execute(sa.text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


def read(engine):
    with Session(engine) as session:
        return service.inventory_overview(
            session, ADMIN_USER_ID, scope="branch", branch_id=BRANCH_ID
        )


def test_overview_repeatable_snapshot_without_blocking_writer(overview_engine, monkeypatch):
    engine = overview_engine
    before = next(row for row in read(engine)["items"] if row["item_id"] == ITEM)
    original = service.inventory_query_capabilities
    captured = []

    def capture(_connection, _cursor, statement, _parameters, _context, _many):
        captured.append(statement.lower().strip())

    def concurrent_write(session, actor):
        capabilities = original(session, actor)
        # The read snapshot has been established. A separate writer must still commit.
        with Session(engine) as writer:
            movement(writer, BRANCH_ID, before["warehouse_id"], "SALE_RESERVATION", "-3")
            writer.commit()
        return capabilities

    monkeypatch.setattr(service, "inventory_query_capabilities", concurrent_write)
    sa.event.listen(engine, "before_cursor_execute", capture)
    try:
        during = next(row for row in read(engine)["items"] if row["item_id"] == ITEM)
    finally:
        sa.event.remove(engine, "before_cursor_execute", capture)
        monkeypatch.setattr(service, "inventory_query_capabilities", original)
    assert during["available_quantity"] == before["available_quantity"]
    assert during["reserved_quantity"] == before["reserved_quantity"]
    assert not any("advisory" in statement for statement in captured)
    after = next(row for row in read(engine)["items"] if row["item_id"] == ITEM)
    from decimal import Decimal

    assert Decimal(after["available_quantity"]) == Decimal(before["available_quantity"]) - 3


def test_overview_readonly_and_query_cost(overview_engine, record_property):
    engine = overview_engine
    statements = []

    def capture(_connection, _cursor, statement, parameters, _context, _many):
        statements.append((statement, parameters))

    sa.event.listen(engine, "before_cursor_execute", capture)
    started = perf_counter()
    try:
        result = read(engine)
    finally:
        sa.event.remove(engine, "before_cursor_execute", capture)
    record_property("inventory_read_ms", int((perf_counter() - started) * 1000))
    assert len(statements) < 30
    assert not any(
        statement.lower().lstrip().startswith(("insert ", "update ", "delete "))
        for statement, _ in statements
    )
    assert result["total_rows"] == sum(result["counts"].values())
    page_sql, parameters = next((sql, args) for sql, args in reversed(statements) if "LIMIT" in sql)
    with engine.connect() as connection:
        plan = connection.exec_driver_sql(
            "EXPLAIN (ANALYZE, FORMAT JSON) " + page_sql, parameters
        ).scalar_one()
        record_property("inventory_sql_ms", plan[0]["Execution Time"])
        assert plan[0]["Plan"]["Actual Rows"] == len(result["items"])


def test_invalid_destination_is_denied_with_durable_audit(overview_engine):
    from restaurant_os.operations import AuthorizationError

    with Session(overview_engine) as session:
        with pytest.raises(AuthorizationError, match="Inventory destination"):
            service.inventory_overview(
                session, ADMIN_USER_ID, scope="branch", branch_id=str(uuid4())
            )
    with Session(overview_engine) as session:
        audit = (
            session.execute(
                sa.select(models.audit_events).where(
                    models.audit_events.c.action == "authorization.denied"
                )
            )
            .mappings()
            .all()
        )
        assert len(audit) == 1
        assert audit[0]["branch_id"] is None


def test_overview_seven_branches_thousand_global_items(overview_engine, record_property):
    """Bound query fan-out and latency on 7,000+ pairs, independently of page size."""
    engine = overview_engine
    with Session(engine) as session:
        branch = dict(
            session.execute(
                sa.select(models.branches).where(models.branches.c.id == BRANCH_ID)
            ).mappings().one()
        )
        warehouse = dict(
            session.execute(
                sa.select(models.warehouses).where(models.warehouses.c.branch_id == BRANCH_ID)
            ).mappings().one()
        )
        item = dict(
            session.execute(
                sa.select(models.inventory_items).where(models.inventory_items.c.id == ITEM)
            ).mappings().one()
        )
        branch_ids = [str(uuid4()) for _ in range(6)]
        session.execute(models.branches.insert(), [
            {**branch, "id": branch_id, "name": f"Load branch {index}", "code": f"LOAD{index}"}
            for index, branch_id in enumerate(branch_ids)
        ])
        session.execute(models.warehouses.insert(), [
            {**warehouse, "id": str(uuid4()), "branch_id": branch_id,
             "name": f"Load warehouse {index}"}
            for index, branch_id in enumerate(branch_ids)
        ])
        session.execute(models.inventory_items.insert(), [
            {**item, "id": str(uuid4()), "sku": f"INV-VIEW-LOAD-{index:04}",
             "name": f"Load item {index:04}", "catalog_scope": "organization",
             "source_branch_id": None}
            for index in range(1000)
        ])
        expected_items = session.scalar(
            sa.select(sa.func.count()).select_from(models.inventory_items).where(
                models.inventory_items.c.organization_id == item["organization_id"],
                models.inventory_items.c.status == "active",
                models.inventory_items.c.catalog_scope == "organization",
            )
        )
        session.commit()

    statements = []

    def capture(_connection, _cursor, statement, parameters, _context, _many):
        statements.append((statement, parameters))

    sa.event.listen(engine, "before_cursor_execute", capture)
    started = perf_counter()
    try:
        with Session(engine) as session:
            result = service.inventory_overview(
                session, ADMIN_USER_ID, scope="organization", branch_id=None, limit=50
            )
    finally:
        elapsed_ms = (perf_counter() - started) * 1000
        sa.event.remove(engine, "before_cursor_execute", capture)

    # The two-second local budget and five-second CI ceiling are performance evidence,
    # not inventory/business rules. This fixture deliberately has only the seed ledger.
    budget_ms = 5000 if os.environ.get("CI") else 2000
    for name, value in {
        "inventory_load_read_ms": round(elapsed_ms, 3),
        "inventory_load_local_target_ms": 2000,
        "inventory_load_ci_budget_ms": 5000,
        "inventory_load_enforced_budget_ms": budget_ms,
        "inventory_load_sql_statements": len(statements),
        "inventory_load_total_rows": result["total_rows"],
        "inventory_load_branches": 7,
        "inventory_load_global_items": expected_items,
    }.items():
        record_property(name, value)
    assert result["total_rows"] == expected_items * 7
    assert result["total_rows"] >= 7000
    assert result["total_rows"] == sum(result["counts"].values())
    assert len(result["items"]) == 50
    assert len(statements) < 30, "Inventory projection must not add one query per item"
    assert elapsed_ms < budget_ms, "Seven-branch overview exceeded its performance budget"
    assert not any(
        statement.lower().lstrip().startswith(("insert ", "update ", "delete "))
        or "advisory" in statement.lower()
        for statement, _ in statements
    )
    page_sql, parameters = next((sql, args) for sql, args in reversed(statements) if "LIMIT" in sql)
    with engine.connect() as connection:
        plan = connection.exec_driver_sql(
            "EXPLAIN (ANALYZE, FORMAT JSON) " + page_sql, parameters
        ).scalar_one()
    record_property("inventory_load_page_sql_ms", plan[0]["Execution Time"])
    assert plan[0]["Plan"]["Actual Rows"] == len(result["items"])
    print(
        f"Inventory load: {result['total_rows']} rows, 7 branches, "
        f"{len(statements)} SQL statements, read={elapsed_ms:.3f}ms, "
        f"page SQL={plan[0]['Execution Time']:.3f}ms"
    )
