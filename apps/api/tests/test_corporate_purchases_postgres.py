"""PostgreSQL concurrency and rollback evidence for CORP-PUR-001."""

from __future__ import annotations

import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from threading import Barrier

import pytest
import sqlalchemy as sa
from restaurant_os import corporate_purchases, models
from restaurant_os.corporate_purchases import (
    approve_corporate_purchase_order,
    create_corporate_purchase_order,
    receive_corporate_purchase_order,
)
from restaurant_os.operations import (
    ORGANIZATION_ID,
    BusinessError,
    create_purchase_presentation,
    create_supplier,
)
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from test_corporate_purchases import (
    LEGAL_ENTITY_ID,
    SECOND_BRANCH_ID,
    SECOND_WAREHOUSE_ID,
    _order_payload,
)
from test_platform_api import ADMIN_ROLE_ID, ADMIN_USER_ID, BRANCH_ID, _seed
from test_purchase_workspace import _presentation

UTC = timezone.utc
TEST_URL_ENV = "CORP_PUR_TEST_POSTGRES_URL"


@pytest.fixture
def pg_engine():
    url = os.environ.get(TEST_URL_ENV)
    if not url:
        pytest.skip(f"{TEST_URL_ENV} is required; configured in CI")
    parsed = make_url(url)
    if (
        not parsed.drivername.startswith("postgresql")
        or parsed.host not in {"localhost", "127.0.0.1"}
        or not (parsed.database or "").startswith("corp_pur_")
        or parsed.query
    ):
        raise RuntimeError("Corporate purchase tests require an isolated corp_pur_* database")
    engine = sa.create_engine(
        url, connect_args={"options": "-c statement_timeout=15000 -c lock_timeout=10000"}
    )
    with engine.begin() as connection:
        connection.execute(sa.text("DROP SCHEMA public CASCADE"))
        connection.execute(sa.text("CREATE SCHEMA public"))
    env = {**os.environ, "RESTAURANTOS_DATABASE_URL": url}
    env.pop("DATABASE_URL", None)
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "alembic.ini", "upgrade", "head"],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
        timeout=90,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    with engine.begin() as connection:
        # Fixture-only cleanup of the entire schema can exceed 15s on Windows under I/O load.
        # SET LOCAL ends with this transaction; domain statements retain 15s/lock_timeout 10s.
        connection.execute(sa.text("SET LOCAL statement_timeout = 60000"))
        names = [
            name for name in sa.inspect(connection).get_table_names() if name != "alembic_version"
        ]
        quoted = ", ".join(connection.dialect.identifier_preparer.quote(name) for name in names)
        connection.execute(sa.text("TRUNCATE TABLE " + quoted + " RESTART IDENTITY CASCADE"))
    with Session(engine) as session:
        _seed(session)
        now = datetime(2026, 10, 12, tzinfo=UTC)
        for code, permission_id in (
            ("purchases.corporate.read", "018f6f73-2d0a-74f0-8f1c-000000000982"),
            ("purchases.corporate.manage", "018f6f73-2d0a-74f0-8f1c-000000000983"),
        ):
            session.execute(
                models.permissions.insert().values(
                    id=permission_id, code=code, description=code, created_at=now
                )
            )
            session.execute(
                models.role_permissions.insert().values(
                    role_id=ADMIN_ROLE_ID, permission_id=permission_id
                )
            )
        business_unit_id = session.scalar(
            sa.select(models.business_units.c.id).where(
                models.business_units.c.legal_entity_id == LEGAL_ENTITY_ID
            )
        )
        session.execute(
            models.branches.insert().values(
                id=SECOND_BRANCH_ID,
                organization_id=ORGANIZATION_ID,
                legal_entity_id=LEGAL_ENTITY_ID,
                business_unit_id=business_unit_id,
                name="Sucursal Norte",
                code="NORTE-CORP-PG",
                timezone="America/Mazatlan",
                status="active",
                created_at=now,
                updated_at=now,
            )
        )
        session.execute(
            models.warehouses.insert().values(
                id=SECOND_WAREHOUSE_ID,
                organization_id=ORGANIZATION_ID,
                branch_id=SECOND_BRANCH_ID,
                name="Almacén Norte",
                status="active",
                created_at=now,
                updated_at=now,
            )
        )
        session.commit()
    try:
        yield engine
    finally:
        engine.dispose()


def _approved_order(engine):
    with Session(engine) as session:
        supplier = create_supplier(
            session,
            {"code": "CORP-PG", "commercial_name": "Proveedor corporativo PostgreSQL"},
            ADMIN_USER_ID,
        )
        presentation = create_purchase_presentation(
            session,
            {**_presentation(supplier["id"]), "code": "CORP-PG-PRES", "last_net_price": "100"},
            ADMIN_USER_ID,
        )
        warehouse_id = session.scalar(
            sa.select(models.warehouses.c.id).where(models.warehouses.c.branch_id == BRANCH_ID)
        )
        created = create_corporate_purchase_order(
            session,
            _order_payload(supplier["id"], presentation["id"], warehouse_id),
            ADMIN_USER_ID,
            "corp-pg-create",
        )
        approved = approve_corporate_purchase_order(
            session,
            created["id"],
            {"expected_version": created["version"]},
            ADMIN_USER_ID,
            "corp-pg-approve",
        )
        allocation = next(
            row
            for row in approved["lines"][0]["allocations"]
            if row["branch_id"] == SECOND_BRANCH_ID
        )
        return approved, allocation


def _receipt_payload(order, allocation, quantity="2"):
    return {
        "expected_version": order["version"],
        "branch_id": SECOND_BRANCH_ID,
        "warehouse_id": SECOND_WAREHOUSE_ID,
        "received_at": "2026-10-12",
        "lines": [{"allocation_id": allocation["id"], "quantity": quantity}],
    }


def test_concurrent_receipts_have_one_winner_and_no_duplicate_effects(pg_engine):
    order, allocation = _approved_order(pg_engine)
    barrier = Barrier(2)

    def receive(index):
        with Session(pg_engine) as session:
            barrier.wait(timeout=10)
            try:
                result = receive_corporate_purchase_order(
                    session,
                    order["id"],
                    _receipt_payload(order, allocation),
                    ADMIN_USER_ID,
                    f"corp-pg-receive-{index}",
                )
                return result["order"]["status"]
            except BusinessError as error:
                return error.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(receive, range(2)))

    assert outcomes.count("PARTIALLY_RECEIVED") == 1
    assert outcomes.count("corporate_purchase_version_conflict") == 1
    with Session(pg_engine) as session:
        assert session.scalar(
            sa.select(sa.func.count()).select_from(models.corporate_purchase_receipts)
        ) == 1
        assert session.scalar(
            sa.select(sa.func.count()).select_from(models.corporate_purchase_receipt_lines)
        ) == 1
        assert session.scalar(
            sa.select(sa.func.count())
            .select_from(models.inventory_movements)
            .where(models.inventory_movements.c.source_type == "corporate_purchase_receipt")
        ) == 1
        assert session.scalar(
            sa.select(sa.func.count())
            .select_from(models.supplier_price_history)
            .where(models.supplier_price_history.c.source_type == "corporate_purchase_receipt")
        ) == 1


def test_late_failure_rolls_back_receipt_cost_history_and_audit(pg_engine, monkeypatch):
    order, allocation = _approved_order(pg_engine)

    def fail_command(*_args, **_kwargs):
        raise RuntimeError("injected command receipt failure")

    monkeypatch.setattr(corporate_purchases, "_store_command", fail_command)
    with pytest.raises(RuntimeError, match="injected command receipt failure"):
        with Session(pg_engine) as session:
            receive_corporate_purchase_order(
                session,
                order["id"],
                _receipt_payload(order, allocation, "1"),
                ADMIN_USER_ID,
                "corp-pg-rollback",
            )

    with Session(pg_engine) as session:
        assert session.scalar(
            sa.select(sa.func.count()).select_from(models.corporate_purchase_receipts)
        ) == 0
        assert session.scalar(
            sa.select(sa.func.count())
            .select_from(models.inventory_movements)
            .where(models.inventory_movements.c.source_type == "corporate_purchase_receipt")
        ) == 0
        assert session.scalar(
            sa.select(sa.func.count())
            .select_from(models.supplier_price_history)
            .where(models.supplier_price_history.c.source_type == "corporate_purchase_receipt")
        ) == 0
        assert session.scalar(
            sa.select(sa.func.count())
            .select_from(models.audit_events)
            .where(models.audit_events.c.action == "corporate_purchase.received")
        ) == 0
        assert session.scalar(
            sa.select(sa.func.count()).select_from(models.inventory_cost_states)
        ) == 0
