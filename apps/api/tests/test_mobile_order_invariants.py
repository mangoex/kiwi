# SEC001-SYNTHETIC-FIXTURE provenance=restaurantos-mobile-invariants-v1
from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest
import sqlalchemy as sa
from restaurant_os import models
from restaurant_os.operations import (
    BusinessError,
    accept_pending_order,
    create_public_online_order,
)
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from test_platform_api import _seed

ADMIN_USER_ID = "018f6f73-2d0a-74f0-8f1c-000000000006"
BRANCH_ID = "018f6f73-2d0a-74f0-8f1c-000000000003"
BURGER_ID = "018f6f73-2d0a-74f0-8f1c-000000000111"
BEEF_ID = "018f6f73-2d0a-74f0-8f1c-000000000311"


@pytest.fixture()
def session() -> Any:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    models.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as database_session:
        _seed(database_session)
        yield database_session


def test_public_order_validates_customer_phone(session: Any) -> None:
    # Invalid phone (< 10 digits)
    with pytest.raises(BusinessError) as exc_info:
        create_public_online_order(
            session=session,
            lines=[{"product_id": BURGER_ID, "quantity": 1}],
            owner_name="Juan Perez",
            customer_phone="12345",
            branch_id=BRANCH_ID,
        )
    assert exc_info.value.code == "invalid_phone"

    # Valid phone (>= 10 digits)
    order = create_public_online_order(
        session=session,
        lines=[{"product_id": BURGER_ID, "quantity": 1}],
        owner_name="Juan Perez",
        customer_phone="5512345678",
        branch_id=BRANCH_ID,
    )
    assert order["status"] == "PENDING"
    assert order["total_cents"] == 9500


def test_public_order_does_not_create_ghost_open_shift(session: Any) -> None:
    # Verify no OPEN shifts exist initially in seeded DB
    initial_open_shifts = session.execute(
        sa.select(models.cash_shifts).where(
            models.cash_shifts.c.branch_id == BRANCH_ID,
            models.cash_shifts.c.status == "OPEN",
        )
    ).all()
    assert len(initial_open_shifts) == 0

    order = create_public_online_order(
        session=session,
        lines=[{"product_id": BURGER_ID, "quantity": 2}],
        owner_name="Cliente Web",
        customer_phone="5588776655",
        branch_id=BRANCH_ID,
    )

    # Verify no new shift with status="OPEN" was created
    open_shifts_after = session.execute(
        sa.select(models.cash_shifts).where(
            models.cash_shifts.c.branch_id == BRANCH_ID,
            models.cash_shifts.c.status == "OPEN",
        )
    ).all()
    assert len(open_shifts_after) == 0
    assert order["total_cents"] == 19000


def test_accept_pending_order_reserves_inventory_and_creates_tasks(session: Any) -> None:
    created = create_public_online_order(
        session=session,
        lines=[{"product_id": BURGER_ID, "quantity": 2}],
        owner_name="Maria Gomez",
        customer_phone="5544332211",
        branch_id=BRANCH_ID,
    )
    order_id = created["id"]

    # Verify no reservations exist prior to acceptance
    pre_reservations = session.execute(
        sa.select(models.inventory_movements).where(
            models.inventory_movements.c.document_id == order_id,
            models.inventory_movements.c.movement_type == "SALE_RESERVATION",
        )
    ).all()
    assert len(pre_reservations) == 0

    # Accept order as authorized admin user
    accepted = accept_pending_order(session=session, order_id=order_id, actor_user_id=ADMIN_USER_ID)
    assert accepted["status"] == "ACCEPTED"

    # Verify production tasks were created
    tasks = session.execute(
        sa.select(models.production_tasks).where(models.production_tasks.c.order_id == order_id)
    ).mappings().all()
    assert len(tasks) == 1
    assert tasks[0]["status"] == "PENDING"
    assert tasks[0]["quantity"] == 2

    # Verify inventory reservation was recorded in inventory_movements
    reservations = session.execute(
        sa.select(models.inventory_movements).where(
            models.inventory_movements.c.document_id == order_id,
            models.inventory_movements.c.movement_type == "SALE_RESERVATION",
        )
    ).mappings().all()
    assert len(reservations) >= 1
    # 2 burgers * 120 grams beef = 240 grams reserved
    assert any(
        res["item_id"] == BEEF_ID
        and Decimal(str(res["quantity_delta"])) == Decimal("-240.000000")
        for res in reservations
    )
