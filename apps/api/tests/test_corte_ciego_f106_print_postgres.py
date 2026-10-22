"""PostgreSQL executes protected print metadata and the actual retry transaction."""

import pytest
import sqlalchemy as sa
from corte_ciego_fixtures import grant_permission, ident
from restaurant_os import models
from restaurant_os import operations as ops
from restaurant_os.financial_access import FinancialAccessService
from sqlalchemy.orm import Session
from test_cash_concepts import BRANCH_A, CASHIER_ID, CASHIER_ROLE_ID, OWNER_ID
from test_corte_ciego_f105_postgres import pg_cash
from test_corte_ciego_f106_postgres import pg_sales

__all__ = ["pg_cash", "pg_sales"]


def test_protected_print_retry_preserves_payload_and_revalidates(
    pg_sales: tuple[sa.Engine, str],
) -> None:
    engine, grant = pg_sales
    job, order = ident("pg-print"), ident("f106-order")
    with Session(engine) as session:
        FinancialAccessService(session, ops.ORGANIZATION_ID).revoke(
            OWNER_ID,
            grant,
            "print-no-financial-fallback",
            {"reason": "Test only attendance"},
        )
        for permission in ("orders.read", "orders.create", "print.jobs.read", "print.jobs.retry"):
            grant_permission(session, CASHIER_ROLE_ID, permission)
        session.execute(
            models.orders.update().where(models.orders.c.id == order).values(status="ACCEPTED")
        )
        ops._audit(
            session,
            "order.accepted",
            "order",
            order,
            {},
            branch_id=BRANCH_A,
            actor_user_id=CASHIER_ID,
        )
        session.execute(
            models.print_jobs.insert().values(
                id=job,
                organization_id=ops.ORGANIZATION_ID,
                branch_id=BRANCH_A,
                order_id=order,
                job_type="ticket",
                target="POS-CAJA-01",
                status="FAILED",
                attempts=1,
                payload={"total_cents": 5678},
                last_error="PRIVATE-ERROR",
                created_at=ops._now(),
                printed_at=None,
            )
        )
        session.commit()
        rows = ops.list_print_jobs(session, BRANCH_A, actor_user_id=CASHIER_ID)
        assert rows[0]["id"] == job and "payload" not in rows[0]
        receipt = ops.retry_print_job(
            session, job, "pg-retry-1", BRANCH_A, actor_user_id=CASHIER_ID
        )
        assert "payload" not in receipt["job"] and receipt["replayed"] is False
        again = ops.retry_print_job(session, job, "pg-retry-1", BRANCH_A, actor_user_id=CASHIER_ID)
        assert again["attempt"]["id"] == receipt["attempt"]["id"] and again["replayed"]
        assert session.scalar(
            sa.select(models.print_jobs.c.payload).where(models.print_jobs.c.id == job)
        ) == {"total_cents": 5678}
        session.execute(
            models.orders.update().where(models.orders.c.id == order).values(status="CLOSED")
        )
        session.commit()
        with pytest.raises(ops.AuthorizationError):
            ops.retry_print_job(session, job, "pg-retry-1", BRANCH_A, actor_user_id=CASHIER_ID)
        assert (
            session.scalar(
                sa.select(sa.func.count())
                .select_from(models.print_attempts)
                .where(models.print_attempts.c.print_job_id == job)
            )
            == 1
        )
