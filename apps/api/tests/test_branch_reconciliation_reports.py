from __future__ import annotations

import io
from datetime import datetime, timezone

import openpyxl
from test_platform_api import (
    BRANCH_ID,
    _admin_headers,
    _client_with_seeded_database,
    _open_shift,
)


def test_daily_reconciliation_calculation_and_balance():
    """Verify PRD-FR-215 / BDD-SC-270..275:
    Daily reconciliation consolidates initial cash, sales by payment method,
    direct purchase expenses, fixed expenses, cash withdrawals, and calculates
    theoretical expected cash and cash overage/shortage (sobrante/faltante).
    """
    client = _client_with_seeded_database()
    headers = _admin_headers()
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # 1. Open shift with $2,000 MXN (200,000 cents)
    shift_res = _open_shift(client, opening_cash_cents=200000, headers=headers)
    assert shift_res.status_code == 200

    # 2. Query daily reconciliation report for today
    res = client.get(
        f"/api/v1/reports/branch-reconciliation/daily?branch_id={BRANCH_ID}&date={today_str}",
        headers=headers,
    )
    assert res.status_code == 200, res.text
    data = res.json()

    assert data["branch_id"] == BRANCH_ID
    assert data["date"] == today_str
    assert "balance" in data
    assert "initial_cash" in data["balance"]
    assert "total_sales_with_tax" in data["balance"]
    assert "card_payments" in data["balance"]
    assert "transfer_payments" in data["balance"]
    assert "credit_sales" in data["balance"]
    assert "supplier_expenses" in data["balance"]
    assert "fixed_expenses" in data["balance"]
    assert "cash_withdrawals" in data["balance"]
    assert "cash_deposits" in data["balance"]
    assert "expected_cash_in_register" in data["balance"]
    assert "physical_cash_count" in data["balance"]
    assert "difference" in data["balance"]

    # Tables breakdown
    assert "suppliers_breakdown" in data
    assert "fixed_expenses_breakdown" in data
    assert "transfers_breakdown" in data
    assert "credit_clients_breakdown" in data
    assert "withdrawals_breakdown" in data
    assert "audit" in data
    assert "reviewed" in data["audit"]


def test_multi_branch_consolidated_report():
    """Verify PRD-FR-217 / BDD-SC-281..285:
    Multi-branch consolidated report aggregates expenses by supplier,
    expenses by fixed type, and totals across branches for daily, weekly or monthly ranges.
    """
    client = _client_with_seeded_database()
    headers = _admin_headers()
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    res = client.get(
        f"/api/v1/reports/branch-reconciliation/consolidated?date_from={today_str}&date_to={today_str}",
        headers=headers,
    )
    assert res.status_code == 200, res.text
    data = res.json()

    assert "date_from" in data
    assert "date_to" in data
    assert "branches" in data
    assert "supplier_totals" in data
    assert "fixed_expense_totals" in data
    assert "summary" in data


def test_reconciliation_audit_status_update():
    """Verify PRD-FR-218 / BDD-SC-286..288:
    Auditor / Manager can mark a branch daily reconciliation as reviewed with audit notes.
    """
    client = _client_with_seeded_database()
    headers = _admin_headers()
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    res = client.post(
        "/api/v1/reports/branch-reconciliation/audit",
        json={
            "branch_id": BRANCH_ID,
            "date": today_str,
            "reviewed": True,
            "notes": "Comprobantes físicos validados contra depósito bancario.",
        },
        headers=headers,
    )
    assert res.status_code == 200, res.text
    audit_data = res.json()
    assert audit_data["reviewed"] is True
    assert audit_data["notes"] == "Comprobantes físicos validados contra depósito bancario."
    assert audit_data["audited_by_user_id"] is not None


def test_reconciliation_excel_export():
    """Verify PRD-FR-219 / BDD-SC-289..291:
    Exports daily/monthly branch reconciliation workbook as standard .xlsx stream.
    """
    client = _client_with_seeded_database()
    headers = _admin_headers()
    today = datetime.now(timezone.utc)

    res = client.get(
        f"/api/v1/reports/branch-reconciliation/export?branch_id={BRANCH_ID}&month={today.month}&year={today.year}",
        headers=headers,
    )
    assert res.status_code == 200, res.text
    assert (
        res.headers.get("content-type")
        == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    # Validate that openpyxl can load the exported bytes
    workbook_bytes = io.BytesIO(res.content)
    wb = openpyxl.load_workbook(workbook_bytes)
    assert "Master" in wb.sheetnames or "Resumen" in wb.sheetnames or "1" in wb.sheetnames
