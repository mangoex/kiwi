"""AUD-CORE financial events, dates and deterministic report arithmetic."""

from datetime import timedelta
from decimal import Decimal

import pytest
from restaurant_os import models
from restaurant_os.operations import BusinessError, calculate_expected_cash
from restaurant_os.reconciliation_reports import (
    _branch_day_bounds_utc,
    export_reconciliation_workbook,
    get_branch_daily_reconciliation,
    get_multi_branch_consolidated_report,
)
from test_cash_ledger import BRANCH_A, CASHIER_ID, NOW, ORG_ID, SHIFT_ID, _new_session
from test_pco007_recipe_reports import _expense_service


def purchase_row(session, *, confirmed_at=NOW, cancelled_at=None, created_at=NOW):
    session.execute(
        models.suppliers.insert().values(
            id="aud-supplier",
            organization_id=ORG_ID,
            code="AUD",
            commercial_name="Proveedor",
            status="active",
            created_at=NOW,
            updated_at=NOW,
        )
    )
    session.execute(
        models.purchase_documents.insert().values(
            id="aud-purchase",
            organization_id=ORG_ID,
            branch_id=BRANCH_A,
            supplier_id="aud-supplier",
            document_type="note",
            folio="AUD-1",
            document_date=NOW,
            subtotal=300,
            discount_total=0,
            tax_total=0,
            freight_total=0,
            total=300,
            payment_method="cash",
            paid_from_cash=True,
            cash_movement_id="aud-withdrawal",
            status="cancelled" if cancelled_at else "confirmed",
            created_by=CASHIER_ID,
            confirmed_by=CASHIER_ID if confirmed_at else None,
            cancelled_by=None,
            created_at=created_at,
            confirmed_at=confirmed_at,
            cancelled_at=cancelled_at,
        )
    )


def cash_row(session, identifier, kind, source, amount=30000, occurred_at=NOW, linked=None):
    session.execute(
        models.cash_movements.insert().values(
            id=identifier,
            organization_id=ORG_ID,
            branch_id=BRANCH_A,
            cash_shift_id=SHIFT_ID,
            movement_type=kind,
            amount_cents=amount,
            reason_code="SUPPLY_PURCHASE",
            reason="Compra",
            source_type=source,
            source_id="aud-purchase",
            actor_user_id=CASHIER_ID,
            idempotency_key=identifier,
            status="confirmed",
            reversal_of_id=linked,
            created_at=occurred_at,
        )
    )


def prepare(session):
    service = _expense_service(session)
    session.execute(
        models.branches.update().where(models.branches.c.id == BRANCH_A).values(timezone="UTC")
    )
    session.execute(
        models.cash_shifts.update()
        .where(models.cash_shifts.c.id == SHIFT_ID)
        .values(opening_cash_cents=200000)
    )
    return service


def test_cash_purchase_is_one_egress_and_provider_category():
    engine, session = _new_session()
    try:
        prepare(session)
        purchase_row(session)
        cash_row(session, "aud-withdrawal", "withdrawal", "PURCHASE")
        session.commit()
        ledger = calculate_expected_cash(session, SHIFT_ID)
        report = get_branch_daily_reconciliation(session, BRANCH_A, NOW.date().isoformat())
        assert ledger["expected_cash_cents"] == 170000
        assert report["balance"]["expected_cash_in_register"] == Decimal("1700")
        assert report["balance"]["supplier_expenses"] == Decimal("300")
        assert report["balance"]["fixed_expenses"] == 0
        assert len(report["suppliers_breakdown"]) == 1
        consolidated = get_multi_branch_consolidated_report(
            session, NOW.date().isoformat(), NOW.date().isoformat(), BRANCH_A
        )
        assert consolidated["summary"]["total_expected_cash"] == Decimal("1700")
        from openpyxl import load_workbook

        workbook = load_workbook(
            export_reconciliation_workbook(session, BRANCH_A, NOW.month, NOW.year)
        )
        assert workbook["Resumen"]["B11"].value == 1700
    finally:
        session.close()
        engine.dispose()


def test_manual_compensation_of_purchase_nets_supplier_category(monkeypatch):
    from restaurant_os import operations
    from test_cash_ledger import OWNER_ID

    monkeypatch.setattr(operations, "_now", lambda: NOW)
    engine, session = _new_session()
    try:
        prepare(session)
        purchase_row(session)
        cash_row(session, "aud-withdrawal", "withdrawal", "PURCHASE")
        session.commit()
        operations.compensate_cash_movement(
            session,
            "aud-withdrawal",
            {"reason": "Devolución real", "evidence_refs": ["archivo:devolucion"]},
            "aud-manual-return",
            OWNER_ID,
        )
        report = get_branch_daily_reconciliation(session, BRANCH_A, NOW.date().isoformat())
        assert report["balance"]["expected_cash_in_register"] == Decimal("2000")
        assert report["balance"]["supplier_expenses"] == 0
        assert report["balance"]["cash_deposits"] == 0
        assert sorted(row["amount"] for row in report["suppliers_breakdown"]) == [-300, 300]
        assert (
            session.execute(models.purchase_documents.select()).mappings().one()["status"]
            == "confirmed"
        )
    finally:
        session.close()
        engine.dispose()


@pytest.mark.parametrize("fault", ["wrong_original", "missing_reversal", "wrong_amount", "noncash"])
def test_purchase_cash_report_rejects_inconsistent_links(fault):
    engine, session = _new_session()
    try:
        prepare(session)
        purchase_row(session, cancelled_at=NOW if fault != "wrong_original" else None)
        cash_row(session, "aud-withdrawal", "withdrawal", "PURCHASE")
        if fault == "wrong_original":
            cash_row(session, "forged", "withdrawal", "PURCHASE", amount=10000)
        elif fault == "noncash":
            session.execute(
                models.purchase_documents.update().values(
                    payment_method="transfer", paid_from_cash=False
                )
            )
        else:
            cash_row(
                session,
                "aud-return",
                "deposit",
                "PURCHASE_CANCELLATION",
                amount=10000 if fault == "wrong_amount" else 30000,
                linked=None if fault == "missing_reversal" else "aud-withdrawal",
            )
        session.commit()
        with pytest.raises(BusinessError, match="Purchase cash link is inconsistent"):
            get_branch_daily_reconciliation(session, BRANCH_A, NOW.date().isoformat())
    finally:
        session.close()
        engine.dispose()


def test_purchase_report_rejects_duplicate_historical_compensations():
    engine, session = _new_session()
    try:
        prepare(session)
        purchase_row(session, cancelled_at=NOW)
        cash_row(session, "aud-withdrawal", "withdrawal", "PURCHASE")
        for identifier in ("aud-return-1", "aud-return-2"):
            cash_row(
                session, identifier, "deposit", "PURCHASE_CANCELLATION", linked="aud-withdrawal"
            )
        session.commit()
        with pytest.raises(BusinessError, match="Purchase cash link is inconsistent"):
            get_branch_daily_reconciliation(session, BRANCH_A, NOW.date().isoformat())
    finally:
        session.close()
        engine.dispose()


def test_expense_cash_refund_nets_original_concept_without_generic_deposit(monkeypatch):
    from restaurant_os import expenses
    from test_operating_expenses import command, draft, setup_expenses

    monkeypatch.setattr(expenses, "_now", lambda: NOW)
    client, headers = setup_expenses()
    with client.app.state.test_session_factory() as session:
        session.execute(models.branches.update().values(timezone="UTC"))
        session.execute(models.cash_shifts.update().values(opened_at=NOW))
        session.commit()
    doc = draft(client, headers)
    confirmed = command(
        client,
        headers,
        f"/expenses/{doc['id']}/confirm",
        {
            "branch_id": BRANCH_A,
            "version": 1,
            "register_id": "CAJA-01",
            "expected_cash_shift_id": "expense-shift",
        },
    )
    assert confirmed.status_code == 200, confirmed.text
    cancelled = command(
        client,
        headers,
        f"/expenses/{doc['id']}/cancel",
        {
            "branch_id": BRANCH_A,
            "version": 2,
            "reason": "Real refund",
            "cash_returned": True,
            "evidence_refs": ["archivo:reembolso"],
        },
    )
    assert cancelled.status_code == 200, cancelled.text
    with client.app.state.test_session_factory() as session:
        report = get_branch_daily_reconciliation(session, BRANCH_A, NOW.date().isoformat())
        assert report["balance"]["fixed_expenses"] == 0
        assert report["balance"]["cash_deposits"] == 0
        assert report["balance"]["expected_cash_in_register"] == 2000
        assert {row["expense_type"] for row in report["fixed_expenses_breakdown"]} == {"Luz"}
        assert sorted(row["amount"] for row in report["fixed_expenses_breakdown"]) == [-300, 300]


def test_confirmed_sales_use_canonical_state_and_explicit_payment_methods():
    engine, session = _new_session()
    try:
        prepare(session)
        for index, (method, status) in enumerate(
            [
                ("cash", "CONFIRMED"),
                ("card", "CONFIRMED"),
                ("transfer", "CONFIRMED"),
                ("cash", "REVERSED"),
                ("cash", "confirmed"),
            ]
        ):
            session.execute(
                models.orders.insert().values(
                    id=f"aud-order-{index}",
                    organization_id=ORG_ID,
                    branch_id=BRANCH_A,
                    cash_shift_id=SHIFT_ID,
                    folio=f"AUD-{index}",
                    channel="POS",
                    status="CLOSED",
                    total_cents=10000,
                    currency="MXN",
                    created_at=NOW,
                )
            )
            session.execute(
                models.payments.insert().values(
                    id=f"aud-pay-{index}",
                    organization_id=ORG_ID,
                    branch_id=BRANCH_A,
                    order_id=f"aud-order-{index}",
                    cash_shift_id=SHIFT_ID,
                    method=method,
                    status=status,
                    amount_cents=10000,
                    currency="MXN",
                    confirmed_at=NOW,
                    created_at=NOW,
                )
            )
        session.commit()
        report = get_branch_daily_reconciliation(session, BRANCH_A, NOW.date().isoformat())
        assert report["balance"]["cash_sales"] == 100
        assert report["balance"]["card_payments"] == 100
        assert report["balance"]["transfer_payments"] == 100
        assert report["balance"]["total_sales_with_tax"] == 300
        assert (
            report["balance"]["expected_cash_in_register"] * 100
            == (calculate_expected_cash(session, SHIFT_ID)["expected_cash_cents"])
        )
    finally:
        session.close()
        engine.dispose()


def test_cancelled_draft_has_no_financial_reversal():
    engine, session = _new_session()
    try:
        service = prepare(session)
        purchase_row(session, confirmed_at=None, cancelled_at=NOW)
        session.commit()
        assert (
            service.expenses(
                {
                    "branch_id": BRANCH_A,
                    "from_utc": NOW - timedelta(seconds=1),
                    "to_utc": NOW + timedelta(seconds=1),
                }
            )["items"]
            == []
        )
    finally:
        session.close()
        engine.dispose()


def test_purchase_dates_keep_positive_history_and_link_cash_reversal_to_its_day():
    engine, session = _new_session()
    try:
        service = prepare(session)
        tomorrow = NOW + timedelta(days=1)
        purchase_row(session, cancelled_at=tomorrow, created_at=NOW - timedelta(days=1))
        cash_row(session, "aud-withdrawal", "withdrawal", "PURCHASE")
        cash_row(
            session,
            "aud-return",
            "deposit",
            "PURCHASE_CANCELLATION",
            occurred_at=tomorrow,
            linked="aud-withdrawal",
        )
        session.commit()
        positive = service.expenses(
            {
                "branch_id": BRANCH_A,
                "from_utc": NOW - timedelta(seconds=1),
                "to_utc": NOW + timedelta(seconds=1),
            }
        )
        negative = service.expenses(
            {
                "branch_id": BRANCH_A,
                "from_utc": tomorrow - timedelta(seconds=1),
                "to_utc": tomorrow + timedelta(seconds=1),
            }
        )
        assert [event["total_cents"] for event in positive["items"]] == [30000]
        assert [event["total_cents"] for event in negative["items"]] == [-30000]
        original = get_branch_daily_reconciliation(session, BRANCH_A, NOW.date().isoformat())
        assert original["activity"]["totals"]["supplier_expenses"] == 300
        reversed_day = get_branch_daily_reconciliation(
            session, BRANCH_A, tomorrow.date().isoformat()
        )
        assert reversed_day["activity"]["totals"]["supplier_expenses"] == -300
    finally:
        session.close()
        engine.dispose()


@pytest.mark.parametrize("day,hours", [("2026-03-08", 23), ("2026-11-01", 25)])
def test_local_day_is_half_open_and_follows_dst(day, hours):
    engine, session = _new_session()
    try:
        session.execute(
            models.branches.update()
            .where(models.branches.c.id == BRANCH_A)
            .values(timezone="America/New_York")
        )
        session.commit()
        start, end = _branch_day_bounds_utc(session, BRANCH_A, day)
        assert end - start == timedelta(hours=hours)
        assert end.microsecond == 0
    finally:
        session.close()
        engine.dispose()
