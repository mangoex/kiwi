"""EXP-001: document effects, not purchases disguised as expenses."""

from uuid import uuid4

import pytest
import sqlalchemy as sa
from restaurant_os import models
from restaurant_os.operations import _now
from test_cash_concepts import (
    BRANCH_A,
    BRANCH_B,
    CASHIER_ID,
    CASHIER_ROLE_ID,
    ORG_ID,
    OWNER_ID,
    OWNER_ROLE_ID,
    _cash_concept_client,
)


def setup_expenses():
    client = _cash_concept_client()
    with client.app.state.test_session_factory() as session:
        for code in (
            "expense.concept.read",
            "expense.concept.manage",
            "expenses.read",
            "expenses.manage",
            "expenses.cancel",
            "cash.movement.withdraw",
            "cash.movement.compensate",
            "reports.expenses.read",
        ):
            pid = str(uuid4())
            session.execute(
                models.permissions.insert().values(
                    id=pid, code=code, description=code, created_at=_now()
                )
            )
            session.execute(
                models.role_permissions.insert().values(role_id=OWNER_ROLE_ID, permission_id=pid)
            )
        session.execute(
            models.cash_shifts.insert().values(
                id="expense-shift",
                organization_id=ORG_ID,
                branch_id=BRANCH_A,
                register_code="CAJA-01",
                cashier_user_id=OWNER_ID,
                opened_at=_now(),
                created_at=_now(),
                opening_cash_cents=200000,
                status="OPEN",
            )
        )
        session.commit()
    headers = {"X-Actor-User-Id": OWNER_ID}
    return client, headers


def command(client, headers, path, payload, key=None, method="POST"):
    return client.request(
        method,
        "/api/v1" + path,
        headers={**headers, "Idempotency-Key": key or str(uuid4())},
        json=payload,
    )


def draft(client, headers, method="cash"):
    concept = command(
        client,
        headers,
        "/expense-concepts",
        {"code": "LUZ", "name": "Luz", "description": "Servicio"},
    )
    assert concept.status_code == 200, concept.text
    response = command(
        client,
        headers,
        "/expenses",
        {
            "branch_id": BRANCH_A,
            "concept_id": concept.json()["id"],
            "document_date": "2026-10-08",
            "total_cents": 30000,
            "tax_cents": None,
            "payment_method": method,
            "reference": "RECIBO-1",
            "notes": "",
            "evidence_refs": ["archivo:recibo-1"],
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def grant_cashier(client, *codes):
    with client.app.state.test_session_factory() as session:
        for code in codes:
            pid = session.scalar(
                sa.select(models.permissions.c.id).where(models.permissions.c.code == code)
            )
            session.execute(
                models.role_permissions.insert().values(role_id=CASHIER_ROLE_ID, permission_id=pid)
            )
        session.commit()


def test_scoped_writer_without_cash_permissions_can_only_confirm_noncash():
    client, owner = setup_expenses()
    doc = draft(client, owner, "transfer")
    grant_cashier(client, "expenses.read", "expenses.manage", "expense.concept.read")
    cashier = {"X-Actor-User-Id": CASHIER_ID}
    assert client.get(f"/api/v1/expenses?branch_id={BRANCH_B}", headers=cashier).status_code == 403
    assert (
        client.get(
            f"/api/v1/expenses/cash-context?branch_id={BRANCH_A}", headers=cashier
        ).status_code
        == 403
    )
    confirmed = command(
        client, cashier, f"/expenses/{doc['id']}/confirm", {"branch_id": BRANCH_A, "version": 1}
    )
    assert confirmed.status_code == 200, confirmed.text
    assert (
        command(
            client,
            cashier,
            f"/expenses/{doc['id']}/cancel",
            {"branch_id": BRANCH_A, "version": 2, "reason": "Sin permiso"},
        ).status_code
        == 403
    )
    with client.app.state.test_session_factory() as session:
        assert session.scalar(sa.select(sa.func.count()).select_from(models.cash_movements)) == 0


def test_snapshot_and_cursor_keep_history_after_catalog_change():
    client, headers = setup_expenses()
    doc = draft(client, headers)
    renamed = command(
        client,
        headers,
        f"/expense-concepts/{doc['concept_id']}",
        {"version": 1, "name": "Electricidad", "description": "Servicio"},
        method="PATCH",
    )
    assert renamed.status_code == 200
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
    command(
        client,
        headers,
        f"/expense-concepts/{doc['concept_id']}",
        {"version": 2, "name": "Servicio eléctrico", "description": ""},
        method="PATCH",
    )
    assert (
        client.get(f"/api/v1/expenses/{doc['id']}", headers=headers).json()["concept_snapshot"][
            "name"
        ]
        == "Electricidad"
    )
    with client.app.state.test_session_factory() as session:
        assert (
            session.scalar(sa.select(models.cash_movements.c.concept_snapshot))["name"]
            == "Electricidad"
        )
    body = {
        k: doc[k]
        for k in (
            "branch_id",
            "concept_id",
            "document_date",
            "total_cents",
            "tax_cents",
            "payment_method",
            "reference",
            "notes",
            "evidence_refs",
        )
    }
    for _ in range(3):
        assert command(client, headers, "/expenses", body).status_code == 200
    first = client.get(f"/api/v1/expenses?branch_id={BRANCH_A}&limit=2", headers=headers).json()
    assert len(first["items"]) == 2 and first["next_cursor"]
    second = client.get(
        "/api/v1/expenses",
        params={"branch_id": BRANCH_A, "limit": 2, "cursor": first["next_cursor"]},
        headers=headers,
    ).json()
    assert len(second["items"]) == 2 and not second["next_cursor"]
    assert not {d["id"] for d in first["items"]} & {d["id"] for d in second["items"]}
    assert (
        client.get(
            "/api/v1/expenses",
            params={
                "branch_id": BRANCH_A,
                "limit": 2,
                "status": "draft",
                "cursor": first["next_cursor"],
            },
            headers=headers,
        ).status_code
        == 409
    )


def test_cash_cancel_requires_refund_and_original_open_shift():
    client, headers = setup_expenses()
    doc = draft(client, headers)
    assert (
        command(
            client,
            headers,
            f"/expenses/{doc['id']}/confirm",
            {
                "branch_id": BRANCH_A,
                "version": 1,
                "register_id": "CAJA-01",
                "expected_cash_shift_id": "expense-shift",
            },
        ).status_code
        == 200
    )
    body = {"branch_id": BRANCH_A, "version": 2, "reason": "Corrección"}
    assert command(client, headers, f"/expenses/{doc['id']}/cancel", body).status_code == 409
    with client.app.state.test_session_factory() as session:
        session.execute(models.cash_shifts.update().values(status="CLOSED", closed_at=_now()))
        session.commit()
    body.update(cash_returned=True, evidence_refs=["archivo:reembolso"])
    assert command(client, headers, f"/expenses/{doc['id']}/cancel", body).status_code == 409
    with client.app.state.test_session_factory() as session:
        assert session.scalar(sa.select(sa.func.count()).select_from(models.cash_movements)) == 1
        assert session.scalar(sa.select(models.expense_documents.c.status)) == "confirmed"


def test_summary_uses_local_boundaries_and_cancellation_event_period():
    from datetime import datetime, timezone

    client, headers = setup_expenses()
    doc = draft(client, headers, "card")
    assert (
        command(
            client, headers, f"/expenses/{doc['id']}/confirm", {"branch_id": BRANCH_A, "version": 1}
        ).status_code
        == 200
    )
    assert (
        command(
            client,
            headers,
            f"/expenses/{doc['id']}/cancel",
            {"branch_id": BRANCH_A, "version": 2, "reason": "Corrección documental"},
        ).status_code
        == 200
    )
    # Controlled fixture timestamps: confirmation is Oct 7 local, cancellation Oct 8 local.
    with client.app.state.test_session_factory() as session:
        session.execute(
            models.expense_documents.update().values(
                confirmed_at=datetime(2026, 10, 8, 5, tzinfo=timezone.utc),
                cancelled_at=datetime(2026, 10, 8, 15, tzinfo=timezone.utc),
            )
        )
        session.commit()
    for day, expected in (("2026-10-07", 30000), ("2026-10-08", -30000)):
        result = client.get(
            "/api/v1/expenses/summary",
            headers=headers,
            params={"branch_id": BRANCH_A, "from_date": day, "to_date": day},
        )
        assert result.status_code == 200, result.text
        assert result.json()["net_cents"] == expected


def test_reconciliation_uses_expense_identity_not_concept_words():
    from decimal import Decimal
    from zoneinfo import ZoneInfo

    from restaurant_os.operations import calculate_expected_cash
    from restaurant_os.reconciliation_reports import get_branch_daily_reconciliation

    client, headers = setup_expenses()
    doc = draft(client, headers)
    assert (
        command(
            client,
            headers,
            f"/expense-concepts/{doc['concept_id']}",
            {"version": 1, "name": "Retiro de basura", "description": ""},
            method="PATCH",
        ).status_code
        == 200
    )
    assert (
        command(
            client,
            headers,
            f"/expenses/{doc['id']}/confirm",
            {
                "branch_id": BRANCH_A,
                "version": 1,
                "register_id": "CAJA-01",
                "expected_cash_shift_id": "expense-shift",
            },
        ).status_code
        == 200
    )
    day = _now().astimezone(ZoneInfo("America/Mazatlan")).date().isoformat()
    with client.app.state.test_session_factory() as session:
        report = get_branch_daily_reconciliation(session, BRANCH_A, day)
        assert report["balance"]["fixed_expenses"] == Decimal("300")
        assert report["balance"]["cash_withdrawals"] == 0
        assert report["balance"]["expected_cash_in_register"] == Decimal("1700")
        assert calculate_expected_cash(session, "expense-shift")["expected_cash_cents"] == 170000
    assert (
        command(
            client,
            headers,
            f"/expenses/{doc['id']}/cancel",
            {
                "branch_id": BRANCH_A,
                "version": 2,
                "reason": "Devolución",
                "cash_returned": True,
                "evidence_refs": ["archivo:devolucion"],
            },
        ).status_code
        == 200
    )
    with client.app.state.test_session_factory() as session:
        assert calculate_expected_cash(session, "expense-shift")["expected_cash_cents"] == 200000


def test_cash_expense_is_atomic_and_replay_does_not_touch_inventory():
    client, headers = setup_expenses()
    doc = draft(client, headers)
    body = {
        "branch_id": BRANCH_A,
        "version": doc["version"],
        "register_id": "CAJA-01",
        "expected_cash_shift_id": "expense-shift",
    }
    path = f"/expenses/{doc['id']}/confirm"
    result = command(client, headers, path, body, "confirm-expense-1")
    assert result.status_code == 200, result.text
    assert result.json()["status"] == "confirmed"
    assert command(client, headers, path, body, "confirm-expense-1").json() == result.json()
    assert command(client, headers, path, body, "different-expense-key").status_code == 409
    with client.app.state.test_session_factory() as session:
        assert session.scalar(sa.select(sa.func.count()).select_from(models.cash_movements)) == 1
        assert session.scalar(sa.select(sa.func.sum(models.cash_movements.c.amount_cents))) == 30000
        for table in (
            models.inventory_movements,
            models.inventory_cost_states,
            models.suppliers,
            models.purchase_documents,
        ):
            assert session.scalar(sa.select(sa.func.count()).select_from(table)) == 0
    cancelled = command(
        client,
        headers,
        f"/expenses/{doc['id']}/cancel",
        {
            "branch_id": BRANCH_A,
            "version": result.json()["version"],
            "reason": "Devolución",
            "cash_returned": True,
            "evidence_refs": ["archivo:devolucion"],
        },
        "cancel-expense-1",
    )
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["status"] == "cancelled"
    with client.app.state.test_session_factory() as session:
        assert session.scalar(sa.select(sa.func.count()).select_from(models.cash_movements)) == 2


@pytest.mark.parametrize("method", ["transfer", "card", "other"])
def test_non_cash_expense_needs_no_shift_and_has_no_stock_effects(method):
    client, headers = setup_expenses()
    with client.app.state.test_session_factory() as session:
        session.execute(models.cash_shifts.delete())
        session.commit()
    doc = draft(client, headers, method)
    result = command(
        client, headers, f"/expenses/{doc['id']}/confirm", {"branch_id": BRANCH_A, "version": 1}
    )
    assert result.status_code == 200, result.text
    with client.app.state.test_session_factory() as session:
        for table in (
            models.cash_movements,
            models.inventory_movements,
            models.inventory_cost_states,
            models.suppliers,
        ):
            assert session.scalar(sa.select(sa.func.count()).select_from(table)) == 0


def test_expense_access_fails_closed():
    client, _ = setup_expenses()
    result = client.get(
        f"/api/v1/expenses?branch_id={BRANCH_A}", headers={"X-Actor-User-Id": CASHIER_ID}
    )
    assert result.status_code == 403


@pytest.mark.parametrize(
    "field,value",
    [
        ("supplier_id", "supplier"),
        ("item_id", "item"),
        ("presentation_id", "presentation"),
        ("warehouse_id", "warehouse"),
        ("total_cents", 1.1),
        ("total_cents", True),
        ("total_cents", 0),
        ("total_cents", 2147483648),
        ("payment_method", "credit"),
        ("tax_cents", 999999),
        ("document_date", ""),
        ("document_date", "20261008"),
        ("version", 1),
    ],
)
def test_invalid_expense_fields_have_no_effect(field, value):
    client, headers = setup_expenses()
    doc = draft(client, headers, "transfer")
    payload = {
        k: doc[k]
        for k in (
            "branch_id",
            "concept_id",
            "document_date",
            "total_cents",
            "tax_cents",
            "payment_method",
            "reference",
            "notes",
            "evidence_refs",
        )
    }
    payload[field] = value
    response = command(client, headers, "/expenses", payload)
    assert response.status_code == 409, response.text
    with client.app.state.test_session_factory() as session:
        assert session.scalar(sa.select(sa.func.count()).select_from(models.expense_documents)) == 1
        assert session.scalar(sa.select(sa.func.count()).select_from(models.cash_movements)) == 0


def test_archived_concept_stale_version_and_turnover_block_confirmation():
    client, headers = setup_expenses()
    doc = draft(client, headers)
    wrong = {
        "branch_id": BRANCH_A,
        "version": 1,
        "register_id": "CAJA-01",
        "expected_cash_shift_id": "old-shift",
    }
    response = command(client, headers, f"/expenses/{doc['id']}/confirm", wrong)
    assert response.json()["detail"]["code"] == "expense_cash_context_changed"
    assert (
        command(
            client, headers, f"/expense-concepts/{doc['concept_id']}/archive", {"version": 1}
        ).status_code
        == 200
    )
    wrong["expected_cash_shift_id"] = "expense-shift"
    assert (
        command(client, headers, f"/expenses/{doc['id']}/confirm", wrong).json()["detail"]["code"]
        == "expense_concept_archived"
    )
    with client.app.state.test_session_factory() as session:
        assert session.scalar(sa.select(sa.func.count()).select_from(models.cash_movements)) == 0


def test_failure_after_cash_write_rolls_back_document_and_receipt(monkeypatch):
    from restaurant_os import expenses
    from sqlalchemy.exc import SQLAlchemyError

    client, headers = setup_expenses()
    doc = draft(client, headers)

    def fail(*args, **kwargs):
        raise SQLAlchemyError("Synthetic unavailable storage")

    monkeypatch.setattr(expenses, "_audit", fail)
    response = command(
        client,
        headers,
        f"/expenses/{doc['id']}/confirm",
        {
            "branch_id": BRANCH_A,
            "version": 1,
            "register_id": "CAJA-01",
            "expected_cash_shift_id": "expense-shift",
        },
        "failed-expense-commit",
    )
    assert response.status_code == 503
    with client.app.state.test_session_factory() as session:
        assert session.scalar(sa.select(sa.func.count()).select_from(models.cash_movements)) == 0
        assert session.scalar(sa.select(models.expense_documents.c.status)) == "draft"
        assert (
            session.scalar(
                sa.select(sa.func.count())
                .select_from(models.expense_commands)
                .where(models.expense_commands.c.idempotency_key == "failed-expense-commit")
            )
            == 0
        )


def test_report_counts_document_once_and_manual_compensation_is_blocked():
    from datetime import datetime, timezone

    from restaurant_os.operations import (
        BusinessError,
        ReportingProjectionService,
        compensate_cash_movement,
    )

    client, headers = setup_expenses()
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
    ).json()
    with client.app.state.test_session_factory() as session:
        report = ReportingProjectionService(session, OWNER_ID).expenses(
            {
                "branch_id": BRANCH_A,
                "from_utc": datetime(2020, 1, 1, tzinfo=timezone.utc),
                "to_utc": datetime(2100, 1, 1, tzinfo=timezone.utc),
            }
        )
        assert [(e["source"], e["total_cents"]) for e in report["items"]] == [("expense", 30000)]
        with pytest.raises(BusinessError, match="Anula desde Gastos"):
            compensate_cash_movement(
                session,
                confirmed["cash_movement_id"],
                {"reason": "Wrong path", "evidence_refs": ["evidence"]},
                "wrong-path-expense",
                OWNER_ID,
            )
    cancelled = command(
        client,
        headers,
        f"/expenses/{doc['id']}/cancel",
        {
            "branch_id": BRANCH_A,
            "version": 2,
            "reason": "Real refund",
            "cash_returned": True,
            "evidence_refs": ["refund"],
        },
    ).json()
    with client.app.state.test_session_factory() as session:
        with pytest.raises(BusinessError, match="Anula desde Gastos"):
            compensate_cash_movement(
                session,
                cancelled["compensation_movement_id"],
                {"reason": "Wrong path", "evidence_refs": ["evidence"]},
                "wrong-path-refund",
                OWNER_ID,
            )
    summary = client.get(
        f"/api/v1/expenses/summary?branch_id={BRANCH_A}&from_date=2020-01-01&to_date=2099-12-31",
        headers=headers,
    )
    assert summary.status_code == 200, summary.text
    assert summary.json()["net_cents"] == 0
    assert summary.json()["confirmed_cents"] == summary.json()["reversed_cents"] == 30000


def test_resolve_missing_command_fences_late_request_and_recovers_existing_result():
    client, headers = setup_expenses()
    doc = draft(client, headers, "transfer")
    key = "lost-request-expense"
    resolved = client.post(
        f"/api/v1/expense-commands/{key}/resolve",
        headers=headers,
        json={"kind": "document.confirm", "target_id": doc["id"], "branch_id": BRANCH_A},
    )
    assert resolved.json() == {"abandoned": True}
    body = {"branch_id": BRANCH_A, "version": 1}
    assert command(client, headers, f"/expenses/{doc['id']}/confirm", body, key).status_code == 409
    result = command(
        client, headers, f"/expenses/{doc['id']}/confirm", body, "confirmed-request-expense"
    )
    assert result.status_code == 200
    recovered = client.get("/api/v1/expense-commands/confirmed-request-expense", headers=headers)
    assert recovered.json() == result.json()
    assert (
        client.get(
            "/api/v1/expense-commands/confirmed-request-expense",
            headers={"X-Actor-User-Id": CASHIER_ID},
        ).status_code
        == 409
    )


def test_malformed_cursors_return_business_error_not_server_error():
    client, headers = setup_expenses()
    for cursor in ("a", "***", "bnVsbA==", "e30=", "5pel5pys6Kqe", "x" * 1025):
        response = client.get(
            "/api/v1/expenses", headers=headers, params={"branch_id": BRANCH_A, "cursor": cursor}
        )
        assert response.status_code == 409, response.text
        assert response.json()["detail"]["code"] == "expense_cursor_invalid"
