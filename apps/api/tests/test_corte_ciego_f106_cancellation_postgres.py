"""PostgreSQL cancellation serialization and atomic receipt audit."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from typing import Any

import pytest
import sqlalchemy as sa
from restaurant_os import models
from restaurant_os import operations as ops
from sqlalchemy.orm import Session
from test_corte_ciego_f106_amendment_postgres import amendment_pg as amendment_pg
from test_corte_ciego_f106_amendments import AmendmentWorld
from test_platform_api import ADMIN_USER_ID


def test_concurrent_cancellation_has_one_effect(amendment_pg: AmendmentWorld) -> None:
    world = amendment_pg
    barrier = Barrier(2)

    def apply() -> tuple[str, Any]:
        with world.factory() as session:
            barrier.wait(10)
            try:
                return "ok", ops.cancel_order(
                    session,
                    world.order,
                    actor_user_id=ADMIN_USER_ID,
                    reason="Synthetic cancellation",
                    expected_version=1,
                    exception_authorization_id=world.cancellation_authorization,
                )
            except ops.BusinessError as exc:
                session.rollback()
                return "denied", exc.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(apply) for _ in range(2)]
        results = [future.result(30) for future in futures]
    assert ("denied", "order_exception_consumed") in results, results
    receipts = [value for status, value in results if status == "ok"]
    assert len(receipts) == 1 and receipts[0]["projection"] == "operational"
    with world.factory() as session:
        assert (
            session.scalar(
                sa.select(sa.func.count())
                .select_from(models.order_events)
                .where(
                    models.order_events.c.event_type == "ORDER_CANCELLED",
                )
            )
            == 1
        )
        reservations = list(
            session.scalars(
                sa.select(models.inventory_movements.c.quantity_delta).where(
                    models.inventory_movements.c.movement_type == "SALE_RESERVATION",
                )
            )
        )
        releases = list(
            session.scalars(
                sa.select(models.inventory_movements.c.quantity_delta).where(
                    models.inventory_movements.c.movement_type == "RESERVATION_RELEASE",
                )
            )
        )
        assert releases and sorted(releases) == sorted(-quantity for quantity in reservations)
        assert session.scalar(sa.select(models.orders.c.total_cents)) == 12300
        assert (
            session.scalar(
                sa.select(sa.func.count()).select_from(models.order_exception_consumptions)
            )
            == 1
        )


def test_receipt_audit_failure_is_atomic(
    amendment_pg: AmendmentWorld,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    world = amendment_pg
    audit = ops._audit

    def fail(session: Session, action: str, *args: Any, **kwargs: Any) -> Any:
        if action == "order.cancellation.receipt_read":
            raise sa.exc.SQLAlchemyError("Synthetic failure")
        return audit(session, action, *args, **kwargs)

    monkeypatch.setattr(ops, "_audit", fail)
    with world.factory() as session, pytest.raises(sa.exc.SQLAlchemyError):
        ops.cancel_order(
            session,
            world.order,
            actor_user_id=ADMIN_USER_ID,
            reason="Synthetic cancellation",
            expected_version=1,
            exception_authorization_id=world.cancellation_authorization,
        )
    with world.factory() as session:
        assert session.scalar(sa.select(models.orders.c.status)) == "ACCEPTED"
        assert (
            session.scalar(
                sa.select(sa.func.count()).select_from(models.order_exception_consumptions)
            )
            == 0
        )
        assert (
            session.scalar(
                sa.select(sa.func.count())
                .select_from(models.inventory_movements)
                .where(
                    models.inventory_movements.c.movement_type == "RESERVATION_RELEASE",
                )
            )
            == 0
        )
