"""Real payment effects remain atomic/idempotent while replies use closed receipts."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import sqlalchemy as sa
from corte_ciego_fixtures import grant_permission, ident
from restaurant_os import models
from restaurant_os import operations as ops
from sqlalchemy.orm import Session
from test_cash_concepts import CASHIER_ID, CASHIER_ROLE_ID
from test_corte_ciego_f105_postgres import pg_cash
from test_corte_ciego_f106_postgres import pg_sales

__all__ = ["pg_cash", "pg_sales"]


def seed_unpaid(engine: sa.Engine) -> str:
    order_id = ident("pg-receipt-order")
    with Session(engine) as session:
        for code in ("orders.read", "payments.confirm"):
            grant_permission(session, CASHIER_ROLE_ID, code)
        order = dict(
            session.execute(
                sa.select(models.orders).where(models.orders.c.id == ident("f106-order"))
            )
            .mappings()
            .one()
        )
        session.execute(
            models.orders.insert().values(
                **{**order, "id": order_id, "folio": "RECEIPT", "status": "ACCEPTED"}
            )
        )
        line = dict(
            session.execute(
                sa.select(models.order_lines).where(models.order_lines.c.order_id == order["id"])
            )
            .mappings()
            .one()
        )
        session.execute(
            models.order_lines.insert().values(
                **{**line, "id": ident("pg-receipt-line"), "order_id": order_id}
            )
        )
        session.commit()
    return order_id


def test_postgres_duplicate_payment_returns_one_receipt(pg_sales: tuple[sa.Engine, str]) -> None:
    engine, _ = pg_sales
    order = seed_unpaid(engine)
    ready = Barrier(2)

    def pay() -> dict:
        with Session(engine) as session:
            ready.wait(10)
            return ops.pay_order(
                session,
                order,
                5678,
                "cash",
                CASHIER_ID,
                "F105-PG",
                idempotency_key="pg-receipt-duplicate",
            )

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(pay) for _ in range(2)]
        results = [future.result(20) for future in futures]
    assert results[0] == results[1] and results[0]["projection"] == "operational"
    assert "amount_cents" not in results[0]
    with Session(engine) as session:
        assert (
            session.scalar(
                sa.select(sa.func.count())
                .select_from(models.payments)
                .where(models.payments.c.order_id == order)
            )
            == 1
        )
        assert (
            session.scalar(
                sa.select(models.payment_commands.c.response_snapshot).where(
                    models.payment_commands.c.order_id == order
                )
            )["amount_cents"]
            == 5678
        )


def test_outer_transaction_owns_payment_and_receipt_audit(pg_sales: tuple[sa.Engine, str]) -> None:
    engine, _ = pg_sales
    order = seed_unpaid(engine)
    with Session(engine) as session:
        result = ops.pay_order(
            session,
            order,
            5678,
            "cash",
            CASHIER_ID,
            "F105-PG",
            idempotency_key="pg-receipt-rollback",
            commit=False,
        )
        assert result["projection"] == "operational"
        session.rollback()
    with Session(engine) as session:
        assert (
            session.scalar(
                sa.select(sa.func.count())
                .select_from(models.payments)
                .where(models.payments.c.order_id == order)
            )
            == 0
        )
        assert (
            session.scalar(
                sa.select(sa.func.count())
                .select_from(models.audit_events)
                .where(models.audit_events.c.action == "operational_command.receipt_read")
            )
            == 0
        )
