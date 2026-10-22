"""PostgreSQL financial history query and audit atomicity with real FKs."""

from typing import Any

import pytest
import sqlalchemy as sa
from corte_ciego_fixtures import ident
from restaurant_os import models
from restaurant_os import operations as ops
from sqlalchemy.orm import Session
from test_cash_concepts import BRANCH_A, OWNER_ID
from test_corte_ciego_f105_postgres import pg_cash as pg_cash
from test_corte_ciego_f106_driver_history import seed_history
from test_corte_ciego_f106_postgres import pg_sales as pg_sales


def test_financial_history_scope_and_originals(pg_sales: tuple[sa.Engine, str]) -> None:
    engine, _grant = pg_sales
    order = ident("f106-order")
    with Session(engine) as session:
        driver = seed_history(session, OWNER_ID, [order])
        original = dict(session.execute(sa.select(models.delivery_assignments)).mappings().one())
        rows = ops.list_driver_deliveries(session, driver, OWNER_ID, branch_id=BRANCH_A)
        assert len(rows) == 1 and rows[0]["order_total_cents"] == 5678
    with Session(engine) as session:
        assert (
            dict(session.execute(sa.select(models.delivery_assignments)).mappings().one())
            == original
        )
        assert (
            session.scalar(
                sa.select(sa.func.count())
                .select_from(models.audit_events)
                .where(
                    models.audit_events.c.action == "driver.deliveries.read",
                )
            )
            == 1
        )


def test_audit_failure_does_not_mutate_history(
    pg_sales: tuple[sa.Engine, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    engine, _grant = pg_sales
    order = ident("f106-order")
    with Session(engine) as session:
        driver = seed_history(session, OWNER_ID, [order])
    audit = ops._audit

    def fail(session: Session, action: str, *args: Any, **kwargs: Any) -> Any:
        if action == "driver.deliveries.read":
            raise sa.exc.SQLAlchemyError("Synthetic failure")
        return audit(session, action, *args, **kwargs)

    monkeypatch.setattr(ops, "_audit", fail)
    with Session(engine) as session, pytest.raises(sa.exc.SQLAlchemyError):
        ops.list_driver_deliveries(session, driver, OWNER_ID, branch_id=BRANCH_A)
    with Session(engine) as session:
        assert session.scalar(sa.select(models.delivery_assignments.c.order_total_cents)) == 5678
        assert (
            session.scalar(
                sa.select(sa.func.count())
                .select_from(models.audit_events)
                .where(
                    models.audit_events.c.action == "driver.deliveries.read",
                )
            )
            == 0
        )
