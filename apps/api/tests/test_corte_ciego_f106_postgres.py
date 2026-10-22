"""Real SQL report execution and financial page/revocation ordering."""

from concurrent.futures import ThreadPoolExecutor
from datetime import date
from threading import Event
from typing import Any

import pytest
import sqlalchemy as sa
from corte_ciego_fixtures import grant_permission, ident
from restaurant_os import models, operations
from restaurant_os.financial_access import FinancialAccessService
from restaurant_os.financial_lists import financial_page
from restaurant_os.operational_reports import operational_report
from sqlalchemy.orm import Session
from test_cash_concepts import BRANCH_A, CASHIER_ID, ORG_ID, OWNER_ID, OWNER_ROLE_ID
from test_cash_ledger import NOW
from test_corte_ciego_f104_postgres import wait_until_blocked
from test_corte_ciego_f105_postgres import pg_cash
from test_corte_ciego_f106_operational import seed_contact_details, seed_pending_web

__all__ = ["pg_cash"]


def test_operational_contacts_and_mixed_feed_use_postgres_json_and_cursor(
    pg_sales: tuple[sa.Engine, str],
) -> None:
    engine, _ = pg_sales
    with Session(engine) as session:
        grant_permission(session, OWNER_ROLE_ID, "orders.read")
        contact = seed_contact_details(session, OWNER_ID)
        intent = seed_pending_web(session)
        session.commit()
        customer_page = operations.list_customers_page(
            session,
            BRANCH_A,
            "Contact detail",
            actor_id=OWNER_ID,
            operational=True,
        )
        customer = customer_page["items"][0]
        assert customer["id"] == contact
        assert customer["legacy_address_reference"] == "Referencia"
        assert customer["addresses"][0]["latitude"] == "23.2494149"
        assert "order_summary" not in customer and "customer_segment" not in customer
        seen = []
        cursor = None
        for _ in range(3):
            page = operations.list_order_accounts(
                session,
                {"branch_id": BRANCH_A, "limit": 1, "cursor": cursor},
                OWNER_ID,
                operational=True,
            )
            seen.extend(page["items"])
            cursor = page["next_cursor"]
            if not cursor:
                break
        assert len(seen) == 2
        assert {row["id"] for row in seen} == {ident("f106-order"), intent}
        assert all("total_cents" not in row for row in seen)
        assert next(row for row in seen if row["id"] == intent)["customer_label"] == "F103 Web"


@pytest.fixture
def pg_sales(pg_cash: tuple[sa.Engine, str, str]) -> tuple[sa.Engine, str]:
    engine, shift, _ = pg_cash
    with Session(engine) as session:
        order, payment, snapshot = (ident(name) for name in ("f106-order", "f106-pay", "f106-sale"))
        session.execute(
            models.orders.insert().values(
                id=order,
                organization_id=ORG_ID,
                branch_id=BRANCH_A,
                cash_shift_id=shift,
                folio="F106",
                channel="POS",
                status="PAID",
                total_cents=5678,
                created_at=NOW,
            )
        )
        session.execute(
            models.payments.insert().values(
                id=payment,
                organization_id=ORG_ID,
                branch_id=BRANCH_A,
                order_id=order,
                cash_shift_id=shift,
                method="cash",
                status="CONFIRMED",
                amount_cents=5678,
                confirmed_at=NOW,
                created_at=NOW,
            )
        )
        session.execute(
            models.sales_operation_snapshots.insert().values(
                id=snapshot,
                organization_id=ORG_ID,
                branch_id=BRANCH_A,
                payment_id=payment,
                order_id=order,
                cash_shift_id=shift,
                register_code_snapshot="F105-PG",
                folio_snapshot="F106",
                service_type_snapshot="takeout",
                currency="MXN",
                gross_cents=5678,
                net_cents=5678,
                quality_status="captured",
                confirmed_at=NOW,
                created_at=NOW,
            )
        )
        category, product, line = (
            ident(name) for name in ("f106-cat", "f106-product", "f106-line")
        )
        session.execute(
            models.product_categories.insert().values(
                id=category,
                organization_id=ORG_ID,
                name="Synthetic",
                created_at=NOW,
                updated_at=NOW,
            )
        )
        session.execute(
            models.products.insert().values(
                id=product,
                organization_id=ORG_ID,
                category_id=category,
                name="Current catalog",
                sku="F106",
                station="kitchen",
                created_at=NOW,
                updated_at=NOW,
            )
        )
        session.execute(
            models.order_lines.insert().values(
                id=line,
                order_id=order,
                product_id=product,
                product_name="Historical product",
                quantity=2,
                unit_price_cents=2839,
                line_total_cents=5678,
                station="kitchen",
                family_id_snapshot=category,
                family_name_snapshot="Synthetic",
                family_snapshot_source="captured",
                created_at=NOW,
            )
        )
        session.execute(
            models.sales_operation_line_snapshots.insert().values(
                id=ident("f106-sales-line"),
                sales_operation_snapshot_id=snapshot,
                payment_id=payment,
                order_line_id=line,
                product_id=product,
                product_name_snapshot="Historical product",
                family_id_snapshot=category,
                family_name_snapshot="Synthetic",
                family_snapshot_source="captured",
                quantity=2,
                gross_cents=5678,
                net_cents=5678,
            )
        )
        scopes = models.financial_access_grant_scopes
        grant = str(
            session.scalar(
                sa.select(scopes.c.grant_id).where(
                    scopes.c.branch_id == BRANCH_A,
                    scopes.c.dataset == "sales",
                )
            )
        )
        session.commit()
    return engine, grant


def test_report_and_financial_page_execute_with_real_foreign_keys(
    pg_sales: tuple[sa.Engine, str],
) -> None:
    engine, _ = pg_sales
    with Session(engine) as session:
        report = operational_report(session, CASHIER_ID, BRANCH_A, "month", date(2026, 8, 15))
        assert report.ticket_count == 1
        assert report.top_products[0].model_dump() == {"position": 1, "name": "Historical product"}
        page = financial_page(session, CASHIER_ID, BRANCH_A, "payments")
        assert page["items"][0]["amount_cents"] == 5678


@pytest.mark.parametrize("reader_first", [True, False])
def test_payment_page_serializes_with_grant_revocation(
    pg_sales: tuple[sa.Engine, str],
    monkeypatch: Any,
    reader_first: bool,
) -> None:
    engine, grant = pg_sales
    arrived, release, contender = Event(), Event(), Event()
    pids: list[int] = []
    original_audit = operations._audit

    def before_query(conn: Any, cursor: Any, statement: str, *args: Any) -> None:
        if reader_first and statement.lstrip().startswith("SELECT payments.id"):
            arrived.set()
            assert release.wait(10)

    def audit(*args: Any, **kwargs: Any) -> None:
        original_audit(*args, **kwargs)
        if not reader_first:
            arrived.set()
            assert release.wait(10)

    def reader() -> bool:
        with Session(engine) as session:
            if not reader_first:
                pids.append(int(session.scalar(sa.text("SELECT pg_backend_pid()"))))
                contender.set()
            try:
                page = financial_page(session, CASHIER_ID, BRANCH_A, "payments")
                assert page["items"][0]["amount_cents"] == 5678
                session.commit()
                return True
            except operations.AuthorizationError:
                return False

    def writer() -> None:
        with Session(engine) as session:
            if reader_first:
                pids.append(int(session.scalar(sa.text("SELECT pg_backend_pid()"))))
                contender.set()
            FinancialAccessService(session, ORG_ID).revoke(
                OWNER_ID,
                grant,
                "f106-revoke",
                {"reason": "Synthetic concurrent revocation"},
            )

    monkeypatch.setattr(operations, "_audit", audit)
    sa.event.listen(engine, "before_cursor_execute", before_query)
    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            first = executor.submit(reader if reader_first else writer)
            second = None
            try:
                assert arrived.wait(10)
                second = executor.submit(writer if reader_first else reader)
                assert contender.wait(5)
                wait_until_blocked(engine, pids[0])
            finally:
                release.set()
            assert second is not None
            first_result, second_result = first.result(15), second.result(15)
            assert (first_result if reader_first else second_result) is reader_first
    finally:
        sa.event.remove(engine, "before_cursor_execute", before_query)
