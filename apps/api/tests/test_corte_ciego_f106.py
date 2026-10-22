"""TC-462: real operational report and indirect financial boundaries."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import jsonschema
import pytest
import sqlalchemy as sa
from corte_ciego_contracts import REPORT_SCHEMA
from corte_ciego_fixtures import (
    BRANCH_A,
    BRANCH_B,
    ORG_ID,
    CashWorld,
    cash_world,
    grant_permission,
    ident,
)
from restaurant_os import models

__all__ = ["cash_world"]


def report(world: CashWorld, actor: str = "leader", **overrides: Any) -> Any:
    return world.client.get(
        "/api/v2/reports/operations",
        params={"branch_id": BRANCH_A, "period": "month", "anchor_date": "2026-08-15", **overrides},
        headers=world.headers(actor),
    )


@pytest.mark.parametrize("actor", ["leader", "owner"])
def test_report_is_a_closed_operational_contract(cash_world: CashWorld, actor: str) -> None:
    response = report(cash_world, actor)
    assert response.status_code == 200, response.text
    jsonschema.validate(response.json(), REPORT_SCHEMA)
    assert response.json()["ticket_count"] == 1
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.parametrize("actor", ["cashier", "chief_cashier", "administrator", "supervisor"])
def test_report_does_not_infer_manager_from_legacy_roles(cash_world: CashWorld, actor: str) -> None:
    response = report(cash_world, actor)
    assert response.status_code == 403, response.text


def test_report_sales_delegate_exact_branch_and_revocation(cash_world: CashWorld) -> None:
    assert report(cash_world, "delegate").status_code == 403
    assert report(cash_world, "delegate", branch_id=BRANCH_B).status_code == 200
    cash_world.revoke("delegate", "sales-b")
    assert report(cash_world, "delegate", branch_id=BRANCH_B).status_code == 403


@pytest.mark.parametrize(
    "period,anchor,start,end",
    [
        ("day", "2026-08-15", "2026-08-15T06:00:00Z", "2026-08-16T06:00:00Z"),
        ("week", "2027-01-01", "2026-12-28T06:00:00Z", "2027-01-04T06:00:00Z"),
        ("month", "2028-02-20", "2028-02-01T06:00:00Z", "2028-03-01T06:00:00Z"),
        ("month", "2026-12-31", "2026-12-01T06:00:00Z", "2027-01-01T06:00:00Z"),
    ],
)
def test_report_uses_branch_calendar(
    cash_world: CashWorld,
    period: str,
    anchor: str,
    start: str,
    end: str,
) -> None:
    with cash_world.sessions() as session:
        session.execute(
            models.branches.update()
            .where(models.branches.c.id == BRANCH_A)
            .values(
                timezone="America/Mexico_City",
            )
        )
        session.commit()
    response = report(cash_world, period=period, anchor_date=anchor)
    assert response.status_code == 200, response.text
    assert response.json()["start"] == start
    assert response.json()["end"] == end


@pytest.mark.parametrize(
    "instant,expected",
    [
        ("2026-08-15T05:59:59+00:00", 0),
        ("2026-08-15T06:00:00+00:00", 1),
        ("2026-08-16T05:59:59+00:00", 1),
        ("2026-08-16T06:00:00+00:00", 0),
    ],
)
def test_report_semiopen_period(cash_world: CashWorld, instant: str, expected: int) -> None:
    with cash_world.sessions() as session:
        session.execute(
            models.branches.update()
            .where(models.branches.c.id == BRANCH_A)
            .values(
                timezone="America/Mexico_City",
            )
        )
        session.execute(
            models.sales_operation_snapshots.update()
            .where(
                models.sales_operation_snapshots.c.id == ident("sale"),
            )
            .values(confirmed_at=datetime.fromisoformat(instant).astimezone(timezone.utc))
        )
        session.commit()
    response = report(cash_world, period="day")
    assert response.status_code == 200, response.text
    assert response.json()["ticket_count"] == expected


def test_report_never_selects_money_columns(cash_world: CashWorld) -> None:
    statements: list[str] = []

    def observe(conn: Any, cursor: Any, statement: str, *args: Any) -> None:
        if statement.lstrip().upper().startswith("SELECT"):
            statements.append(statement)

    sa.event.listen(cash_world.engine, "before_cursor_execute", observe)
    try:
        response = report(cash_world)
    finally:
        sa.event.remove(cash_world.engine, "before_cursor_execute", observe)
    assert response.status_code == 200, response.text
    assert not any("_cents" in statement for statement in statements)


def test_ai_does_not_hold_a_transaction_across_provider(
    cash_world: CashWorld, monkeypatch: Any
) -> None:
    from restaurant_os import executive_ai

    with cash_world.sessions() as session:

        def provider(*args: Any, **kwargs: Any) -> dict[str, Any]:
            assert not session.in_transaction(), "DB locks retained across external I/O"
            return {"answer": "Synthetic provider"}

        monkeypatch.setattr(executive_ai, "_call_external_provider", provider)
        result = executive_ai.generate_executive_insights(
            session,
            "synthetic",
            branch_id=BRANCH_A,
            actor_user_id=cash_world.actors["owner"],
            provider_options=executive_ai.ExecutiveAiProviderOptions(
                "synthetic", "test", "invalid"
            ),
        )
    assert result["answer"] == "Synthetic provider"


def test_ai_revalidates_after_provider_revokes_scope(
    cash_world: CashWorld, monkeypatch: Any
) -> None:
    from restaurant_os import executive_ai
    from restaurant_os.financial_access import FinancialAccessService
    from restaurant_os.operations import AuthorizationError

    with cash_world.sessions() as session:
        grant_permission(session, cash_world.roles["delegate"], "inventory.costs.read")
        session.commit()
        FinancialAccessService(session, ORG_ID).issue(
            cash_world.actors["owner"],
            "f106-sales-a",
            {
                "subject_user_id": cash_world.actors["delegate"],
                "reason": "Synthetic scope",
                "scopes": [{"branch_id": BRANCH_A, "dataset": "sales"}],
            },
        )

    def provider(*args: Any, **kwargs: Any) -> dict[str, Any]:
        cash_world.revoke("delegate", "sales-b")
        return {"answer": "Must not be returned after revocation"}

    monkeypatch.setattr(executive_ai, "_call_external_provider", provider)
    with cash_world.sessions() as session, pytest.raises(AuthorizationError):
        executive_ai.generate_executive_insights(
            session,
            "synthetic",
            actor_user_id=cash_world.actors["delegate"],
            provider_options=executive_ai.ExecutiveAiProviderOptions(
                "synthetic", "test", "invalid"
            ),
        )


@pytest.mark.parametrize("path", ["payments", "cash/movements"])
def test_financial_lists_require_current_dataset_even_on_empty_page(
    cash_world: CashWorld,
    path: str,
) -> None:
    response = cash_world.client.get(
        f"/api/v2/financial/{path}",
        params={"branch_id": BRANCH_A, "cursor": "zzzz"},
        headers=cash_world.headers("leader"),
    )
    assert response.status_code == 403, response.text


def test_payments_financial_page_is_scoped_and_revalidates(cash_world: CashWorld) -> None:
    path = "/api/v2/financial/payments"
    response = cash_world.client.get(
        path, params={"branch_id": BRANCH_B, "limit": 1}, headers=cash_world.headers("delegate")
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["items"][0]["amount_cents"] == 5000
    assert body["items"][0]["branch_id"] == BRANCH_B
    assert body["items"][0]["projection"] == "financial"
    cash_world.revoke("delegate", "sales-b")
    assert (
        cash_world.client.get(
            path, params={"branch_id": BRANCH_B}, headers=cash_world.headers("delegate")
        ).status_code
        == 403
    )


def test_dashboard_notifications_never_smuggle_cash_payloads(cash_world: CashWorld) -> None:
    from test_cash_ledger import NOW

    with cash_world.sessions() as session:
        session.execute(
            models.audit_events.insert().values(
                id=ident("cash-notification"),
                organization_id=ORG_ID,
                branch_id=BRANCH_B,
                actor_user_id=cash_world.actors["owner"],
                action="cash_shift.closed",
                entity_type="cash_shift",
                entity_id=ident(f"shift:{BRANCH_B}"),
                payload={"difference_cents": 987654, "expected_cash_cents": 123456},
                created_at=NOW,
            )
        )
        session.commit()
    response = cash_world.client.get(
        "/api/v1/dashboard/overview",
        params={"branch_id": BRANCH_B, "month": "2026-08"},
        headers=cash_world.headers("delegate"),
    )
    assert response.status_code == 200, response.text
    assert "987654" not in response.text and "expected_cash_cents" not in response.text


@pytest.mark.parametrize(
    "surface", ["payments", "movements", "sales", "expenses", "reconciliation", "delivery"]
)
def test_domain_readers_cannot_bypass_http_guard(cash_world: CashWorld, surface: str) -> None:
    from restaurant_os import operations as ops
    from restaurant_os.reconciliation_reports import get_branch_daily_reconciliation

    with cash_world.sessions() as session:
        grant_permission(session, cash_world.roles["leader"], "reports.expenses.read")
        session.commit()
    with cash_world.sessions() as session, pytest.raises(ops.AuthorizationError) as error:
        user = cash_world.actors["leader"]
        if surface == "payments":
            ops.list_payments(session, BRANCH_A)
        elif surface == "movements":
            ops.list_cash_movements(session, BRANCH_A)
        elif surface == "reconciliation":
            get_branch_daily_reconciliation(session, BRANCH_A, "2026-08-15", user)
        elif surface == "delivery":
            from restaurant_os.delivery_fee_report import report as delivery_report

            delivery_report(
                session,
                user,
                BRANCH_A,
                datetime(2026, 8, 1, tzinfo=timezone.utc),
                datetime(2026, 9, 1, tzinfo=timezone.utc),
            )
        else:
            service = ops.ReportingProjectionService(session, user)
            filters = {
                "branch_id": BRANCH_A,
                "from_utc": datetime(2026, 8, 1, tzinfo=timezone.utc),
                "to_utc": datetime(2026, 9, 1, tzinfo=timezone.utc),
            }
            if surface == "expenses":
                service.expenses(filters)
            else:
                service.summary(filters)
    assert error.value.code == "financial_access_denied"


def test_report_top_ten_uses_quantity_then_stable_id_and_snapshot_names(
    cash_world: CashWorld,
) -> None:
    from test_cash_ledger import NOW

    names = [f"Snapshot product {index:02}" for index in range(12)]
    with cash_world.sessions() as session:
        category = ident("f106-category")
        session.execute(
            models.product_categories.insert().values(
                id=category,
                organization_id=ORG_ID,
                name="Synthetic",
                created_at=NOW,
                updated_at=NOW,
            )
        )
        for index, name in enumerate(names):
            product = f"00000000-0000-4000-8000-{index:012}"
            line = ident(f"f106-line-{index}")
            session.execute(
                models.products.insert().values(
                    id=product,
                    organization_id=ORG_ID,
                    category_id=category,
                    name="Changed catalog name",
                    sku=f"F106-{index}",
                    station="kitchen",
                    created_at=NOW,
                    updated_at=NOW,
                )
            )
            session.execute(
                models.order_lines.insert().values(
                    id=line,
                    order_id=ident("order:1"),
                    product_id=product,
                    product_name=name,
                    quantity=2 if index == 11 else 1,
                    unit_price_cents=100,
                    line_total_cents=200,
                    station="kitchen",
                    family_id_snapshot=category,
                    family_name_snapshot="Synthetic",
                    family_snapshot_source="captured",
                    created_at=NOW,
                )
            )
            session.execute(
                models.sales_operation_line_snapshots.insert().values(
                    id=ident(f"f106-line-snapshot-{index}"),
                    sales_operation_snapshot_id=ident("sale"),
                    payment_id=ident("payment"),
                    order_line_id=line,
                    product_id=product,
                    product_name_snapshot=name,
                    family_id_snapshot=category,
                    family_name_snapshot="Synthetic",
                    family_snapshot_source="captured",
                    quantity=2 if index == 11 else 1,
                    gross_cents=200,
                    net_cents=200,
                )
            )
        session.commit()
    response = report(cash_world)
    assert response.status_code == 200, response.text
    jsonschema.validate(response.json(), REPORT_SCHEMA)
    assert response.json()["top_products"] == [
        {"position": position, "name": names[index]}
        for position, index in enumerate([11, *range(9)], 1)
    ]
    assert response.json()["ticket_count"] == 1


@pytest.mark.parametrize("anchor,hours", [("2026-03-08", 23), ("2026-11-01", 25)])
def test_report_day_obeys_daylight_saving(cash_world: CashWorld, anchor: str, hours: int) -> None:
    with cash_world.sessions() as session:
        session.execute(
            models.branches.update()
            .where(models.branches.c.id == BRANCH_A)
            .values(
                timezone="America/New_York",
            )
        )
        session.commit()
    response = report(cash_world, period="day", anchor_date=anchor)
    assert response.status_code == 200, response.text
    start, end = (
        datetime.fromisoformat(response.json()[key].replace("Z", "+00:00"))
        for key in ("start", "end")
    )
    assert (end - start).total_seconds() == hours * 3600


def test_crm_origin_branch_is_not_the_scope_of_customer_spend(cash_world: CashWorld) -> None:
    response = cash_world.client.get(
        "/api/v1/admin-ai/customer-crm-segments",
        params={"branch_id": BRANCH_B},
        headers=cash_world.headers("delegate"),
    )
    assert response.status_code == 403, response.text


def test_crm_owner_can_read_with_sqlite_utc_dates(cash_world: CashWorld) -> None:
    response = cash_world.client.get(
        "/api/v1/admin-ai/customer-crm-segments",
        params={"branch_id": BRANCH_A},
        headers=cash_world.headers("owner"),
    )
    assert response.status_code == 200, response.text


@pytest.mark.parametrize(
    "name",
    [
        "operational-report-v2",
        "financial-payments-page-v2",
        "financial-movements-page-v2",
        "operational-customers-page-v2",
        "operational-order-accounts-page-v2",
        "attended-order-detail-v2",
    ],
)
def test_published_v2_schemas_match_runtime(name: str) -> None:
    from restaurant_os.cash_views import CashPageV2
    from restaurant_os.customer_operational_views import CustomerOperationalPageV2
    from restaurant_os.financial_lists import MovementFinancialV2, PaymentFinancialV2
    from restaurant_os.operational_reports import OperationalReportV2
    from restaurant_os.order_detail_views import OrderDetailV2
    from restaurant_os.order_operational_views import OrderAccountOperationalV2

    models_by_name = {
        "operational-report-v2": OperationalReportV2,
        "financial-payments-page-v2": CashPageV2[PaymentFinancialV2],
        "financial-movements-page-v2": CashPageV2[MovementFinancialV2],
        "operational-customers-page-v2": CustomerOperationalPageV2,
        "operational-order-accounts-page-v2": CashPageV2[OrderAccountOperationalV2],
        "attended-order-detail-v2": OrderDetailV2,
    }
    path = (
        Path(__file__).resolve().parents[3] / "packages/contracts/schemas" / f"{name}.schema.json"
    )
    published = json.loads(path.read_text(encoding="utf-8"))
    assert published.pop("$schema") == "https://json-schema.org/draft/2020-12/schema"
    assert published == models_by_name[name].model_json_schema()
