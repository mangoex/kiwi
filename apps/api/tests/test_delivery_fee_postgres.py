"""Mandatory, isolated PostgreSQL migration and money-concurrency gate."""

from __future__ import annotations

import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Barrier
from uuid import uuid4

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from restaurant_os import delivery_fee, models
from restaurant_os.database import get_session
from restaurant_os.main import create_app
from restaurant_os.operations import BusinessError, amend_order, pay_order
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker
from test_delivery_fee_commands import quote, setup_delivery
from test_platform_api import ADMIN_ROLE_ID, ADMIN_USER_ID, BRANCH_ID, _admin_headers, _seed


@pytest.fixture
def factory() -> sessionmaker[Session]:
    raw = os.environ.get("DELIVERY_FEE_TEST_POSTGRES_URL", "")
    if not raw:
        raise RuntimeError("DELIVERY_FEE_TEST_POSTGRES_URL is required for this money gate")
    url = make_url(raw)
    if (
        not url.drivername.startswith("postgresql")
        or url.host not in {"127.0.0.1", "localhost"}
        or not (url.database or "").startswith("delivery_fee_")
        or url.query
    ):
        raise RuntimeError("Delivery tests require an isolated local delivery_fee_* database")
    engine = sa.create_engine(
        raw, connect_args={"options": "-clock_timeout=10000 -cstatement_timeout=20000"}
    )
    with engine.begin() as connection:
        connection.execute(sa.text("DROP SCHEMA public CASCADE"))
        connection.execute(sa.text("CREATE SCHEMA public"))
    environment = {**os.environ, "RESTAURANTOS_DATABASE_URL": raw}
    environment.pop("DATABASE_URL", None)
    migrated = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=Path(__file__).resolve().parents[1],
        env=environment,
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert migrated.returncode == 0, migrated.stdout + migrated.stderr
    with engine.begin() as connection:
        names = [
            name for name in sa.inspect(connection).get_table_names() if name != "alembic_version"
        ]
        quoted = ", ".join(connection.dialect.identifier_preparer.quote(name) for name in names)
        connection.execute(sa.text("TRUNCATE TABLE " + quoted + " RESTART IDENTITY CASCADE"))
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as session:
        _seed(session)
        permission_id = session.scalar(
            sa.select(models.permissions.c.id).where(
                models.permissions.c.code == "reports.sales.read"
            )
        )
        if permission_id is None:
            permission_id = str(uuid4())
            session.execute(
                models.permissions.insert().values(
                    id=permission_id,
                    code="reports.sales.read",
                    description="Delivery report fixture",
                    created_at=datetime.now(timezone.utc),
                )
            )
        session.execute(
            models.role_permissions.insert().values(
                role_id=ADMIN_ROLE_ID, permission_id=permission_id
            )
        )
        session.commit()
    yield factory
    engine.dispose()


def client_for(factory: sessionmaker[Session]) -> TestClient:
    app = create_app()

    def dependency():
        with factory() as session:
            yield session

    app.dependency_overrides[get_session] = dependency
    app.state.test_session_factory = factory
    return TestClient(app)


def test_catalog_publication_has_one_winner_and_preserves_history(factory) -> None:
    with factory() as session:
        tariff = delivery_fee.save_tariff(
            session,
            ADMIN_USER_ID,
            "delivery-pg-tariff-001",
            {"code": "STANDARD", "name": "Estándar", "amount_cents": 2800},
        )
    barrier = Barrier(2)

    def publish(index: int) -> str:
        with factory() as session:
            barrier.wait(timeout=10)
            try:
                delivery_fee.save_policy(
                    session,
                    ADMIN_USER_ID,
                    f"delivery-pg-policy-{index}",
                    {
                        "branch_id": BRANCH_ID,
                        "expected_version": 0,
                        "enabled": True,
                        "eligible_tariff_ids": [tariff["id"]],
                        "default_tariff_id": tariff["id"],
                    },
                )
                return "published"
            except BusinessError as error:
                session.rollback()
                return error.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(publish, range(2)))
    assert sorted(outcomes) == ["delivery_policy_version_conflict", "published"]
    with factory() as session:
        assert session.scalar(sa.select(sa.func.count()).select_from(models.delivery_policies)) == 1


def test_payment_racing_removal_cannot_confirm_different_amounts(factory) -> None:
    client, payload, _ = setup_delivery(client_for(factory))
    priced = quote(client, payload)
    payload["delivery_quote_reference"] = priced["delivery_quote_reference"]
    created = client.post("/api/v1/orders", headers=_admin_headers(), json=payload)
    assert created.status_code == 200, created.text
    order = created.json()
    edit = {**payload, "order_id": order["id"], "delivery_selection": {"mode": "REMOVED"}}
    edit.pop("delivery_quote_reference")
    reference = quote(client, edit)["delivery_quote_reference"]
    barrier = Barrier(2)

    def change(action: str) -> str:
        with factory() as session:
            barrier.wait(timeout=10)
            try:
                if action == "pay":
                    pay_order(
                        session,
                        order["id"],
                        12300,
                        "cash",
                        ADMIN_USER_ID,
                        "CAJA-01",
                        idempotency_key="delivery-pg-payment-001",
                    )
                else:
                    amend_order(
                        session,
                        order["id"],
                        payload["lines"],
                        1,
                        "delivery-pg-removal-001",
                        ADMIN_USER_ID,
                        delivery_selection={"mode": "REMOVED"},
                        delivery_quote_reference=reference,
                    )
                return action
            except BusinessError as error:
                session.rollback()
                return error.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(change, ["pay", "remove"]))
    assert sorted(outcomes) in [
        sorted(["pay", "order_has_payment"]),
        sorted(["payment_total_mismatch", "remove"]),
    ]
    with factory() as session:
        current = session.scalar(
            sa.select(models.orders.c.total_cents).where(models.orders.c.id == order["id"])
        )
        paid = session.scalar(
            sa.select(models.payments.c.amount_cents).where(
                models.payments.c.order_id == order["id"]
            )
        )
        assert paid is None or paid == current


def test_delivery_report_uses_integer_snapshot_amounts_on_postgres(factory) -> None:
    client, payload, _ = setup_delivery(client_for(factory))
    payload["delivery_quote_reference"] = quote(client, payload)["delivery_quote_reference"]
    order = client.post("/api/v1/orders", headers=_admin_headers(), json=payload).json()
    paid = client.post(
        f"/api/v1/orders/{order['id']}/payments",
        headers=_admin_headers(),
        json={"amount_cents": 12300, "method": "cash", "register_id": "CAJA-01"},
    )
    assert paid.status_code == 200, paid.text
    now = datetime.now(timezone.utc)
    result = client.get(
        "/api/v1/reports/delivery-fees",
        headers=_admin_headers(),
        params={
            "branch_id": BRANCH_ID,
            "start": (now - timedelta(days=1)).isoformat(),
            "end": (now + timedelta(days=1)).isoformat(),
        },
    )
    assert result.status_code == 200, result.text
    assert result.json()["summary"] == {
        "entry_count": 1,
        "gross_cents": 2800,
        "net_cents": 2414,
        "tax_cents": 386,
    }


def test_empty_downgrade_reverses_and_history_blocks_destructive_downgrade(factory) -> None:
    raw = os.environ["DELIVERY_FEE_TEST_POSTGRES_URL"]
    environment = {**os.environ, "RESTAURANTOS_DATABASE_URL": raw}
    environment.pop("DATABASE_URL", None)

    def migrate(*arguments):
        return subprocess.run(
            [sys.executable, "-m", "alembic", *arguments],
            cwd=Path(__file__).resolve().parents[1],
            env=environment,
            capture_output=True,
            text=True,
            timeout=180,
        )

    result = migrate("downgrade", "0099_mobile_password_access")
    assert result.returncode == 0, result.stderr
    assert migrate("upgrade", "head").returncode == 0
    with factory() as session:
        created = delivery_fee.save_tariff(
            session,
            ADMIN_USER_ID,
            "migration-history-001",
            {"code": "HISTORY", "name": "Historical tariff", "amount_cents": 2800},
        )
    result = migrate("downgrade", "0099_mobile_password_access")
    assert result.returncode != 0
    assert "Delivery history exists" in result.stderr
    with factory() as session:
        assert (
            session.scalar(
                sa.select(models.delivery_tariffs.c.id).where(
                    models.delivery_tariffs.c.id == created["id"]
                )
            )
            == created["id"]
        )
        assert (
            session.scalar(sa.text("SELECT version_num FROM alembic_version"))
            == "0104_purchase_draft_edits"
        )
