# SEC001-SYNTHETIC-FIXTURE provenance=restaurantos-grokbot-agent-expense-cash-v1
"""Read-only dashboard projections for the Administrador agent identity."""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime

import pytest
import sqlalchemy as sa
from restaurant_os import models
from restaurant_os.reconciliation_reports import get_branch_daily_reconciliation
from test_agent_tools import (
    BRANCH_ID,
    ORGANIZATION_ID,
    SECOND_BRANCH_ID,
    _admin_headers,
    _client,
    _configure,
    _factory,
    _token,
)
from test_platform_api import ADMIN_USER_ID

MAZATLAN_DAY = "2026-10-11T07:00:00Z"
NEXT_MAZATLAN_DAY = "2026-10-12T07:00:00Z"
OPT_IN = (
    "agent.operating_expenses.read",
    "agent.payment_methods.read",
    "agent.cash_reconciliation.read",
    "agent.cash_personal_data.read",
)


def _headers(client, capabilities: list[str]) -> dict[str, str]:
    client_id, secret = _configure(client, "administrator", capabilities)
    return {"Authorization": f"Bearer {_token(client, client_id, secret)}"}


def _counts(session) -> dict[str, int]:
    tables = (
        models.expense_documents,
        models.payments,
        models.cash_movements,
        models.order_corrections,
        models.purchase_documents,
        models.cash_shifts,
    )
    return {
        table.name: int(session.scalar(sa.select(sa.func.count()).select_from(table)) or 0)
        for table in tables
    }


def _expense(
    session,
    identifier: str,
    concept_id: str,
    name: str,
    when: datetime,
    cents: int,
    *,
    cancelled_at: datetime | None = None,
    branch_id: str = BRANCH_ID,
) -> None:
    session.execute(
        models.expense_documents.insert().values(
            id=identifier,
            organization_id=ORGANIZATION_ID,
            branch_id=branch_id,
            concept_id=concept_id,
            concept_snapshot={"code": name, "name": name},
            folio=f"GAS-{identifier[-4:]}",
            document_date=date(2026, 10, 11),
            total_cents=cents,
            tax_cents=0,
            currency="MXN",
            payment_method="transfer",
            reference="REF",
            notes="nota privada",
            evidence_refs=[],
            status="cancelled" if cancelled_at else "confirmed",
            version=1,
            created_by=ADMIN_USER_ID,
            created_at=when,
            updated_at=when,
            confirmed_at=when,
            cancelled_at=cancelled_at,
        )
    )


def test_operating_expenses_require_opt_in_and_respect_mazatlan_cents(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger="restaurant_os.main")
    factory = _factory()
    inside = datetime(2026, 10, 11, 7, 0, tzinfo=UTC)
    with factory() as session:
        before = _counts(session)
        pilot = (
            session.execute(sa.select(models.branches).where(models.branches.c.id == BRANCH_ID))
            .mappings()
            .one()
        )
        session.execute(
            models.branches.insert().values(
                id=SECOND_BRANCH_ID,
                organization_id=pilot["organization_id"],
                legal_entity_id=pilot["legal_entity_id"],
                business_unit_id=pilot["business_unit_id"],
                name="Sucursal Ajena Gasto",
                code="AJENA-GAS",
                timezone="America/Mazatlan",
                status="active",
                created_at=inside,
                updated_at=inside,
            )
        )
        for concept_id, code, name in (
            ("018f6f73-2d0a-74f0-8f1c-00000000e001", "RENTA", "Renta"),
            ("018f6f73-2d0a-74f0-8f1c-00000000e002", "CONTADOR", "Contador"),
        ):
            session.execute(
                models.expense_concepts.insert().values(
                    id=concept_id,
                    organization_id=ORGANIZATION_ID,
                    code=code,
                    name=name,
                    description="Concepto sintético",
                    status="active",
                    version=1,
                    created_by=ADMIN_USER_ID,
                    created_at=inside,
                    updated_at=inside,
                )
            )
        _expense(
            session,
            "018f6f73-2d0a-74f0-8f1c-00000000e011",
            "018f6f73-2d0a-74f0-8f1c-00000000e001",
            "Renta",
            datetime(2026, 10, 11, 6, 59, tzinfo=UTC),
            1000,
        )
        _expense(
            session,
            "018f6f73-2d0a-74f0-8f1c-00000000e012",
            "018f6f73-2d0a-74f0-8f1c-00000000e001",
            "Renta",
            inside,
            2500,
        )
        _expense(
            session,
            "018f6f73-2d0a-74f0-8f1c-00000000e013",
            "018f6f73-2d0a-74f0-8f1c-00000000e002",
            "Contador",
            datetime(2026, 10, 11, 20, 0, tzinfo=UTC),
            4000,
            cancelled_at=datetime(2026, 10, 11, 21, 0, tzinfo=UTC),
        )
        _expense(
            session,
            "018f6f73-2d0a-74f0-8f1c-00000000e014",
            "018f6f73-2d0a-74f0-8f1c-00000000e001",
            "Renta",
            datetime(2026, 10, 12, 7, 0, tzinfo=UTC),
            9000,
        )
        _expense(
            session,
            "018f6f73-2d0a-74f0-8f1c-00000000e015",
            "018f6f73-2d0a-74f0-8f1c-00000000e001",
            "Renta",
            inside,
            99999,
            branch_id=SECOND_BRANCH_ID,
        )
        session.commit()

    client = _client(factory)
    denied = client.get(
        "/api/v1/agent-tools/expenses/summary",
        params={"branch_id": BRANCH_ID, "from_utc": MAZATLAN_DAY, "to_utc": NEXT_MAZATLAN_DAY},
        headers=_headers(client, ["agent.context.read", "agent.sales.read"]),
    )
    assert denied.status_code == 403
    assert denied.json()["detail"]["code"] == "agent_capability_denied"

    response = client.get(
        "/api/v1/agent-tools/expenses/summary",
        params={"branch_id": BRANCH_ID, "from_utc": MAZATLAN_DAY, "to_utc": NEXT_MAZATLAN_DAY},
        headers=_headers(client, ["agent.context.read", "agent.operating_expenses.read"]),
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["grouping"] == "concept"
    assert payload["currency"] == "MXN"
    assert "classification" not in payload
    assert payload["totals"] == {"confirmed_cents": 6500, "reversed_cents": 4000, "net_cents": 2500}
    assert payload["concepts"] == [
        {
            "concept_id": "018f6f73-2d0a-74f0-8f1c-00000000e002",
            "concept_code": "CONTADOR",
            "concept_code_source": "current_catalog",
            "concept_name": "Contador",
            "concept_name_source": "document_snapshot",
            "net_cents": 0,
            "confirmed_cents": 4000,
            "reversed_cents": 4000,
        },
        {
            "concept_id": "018f6f73-2d0a-74f0-8f1c-00000000e001",
            "concept_code": "RENTA",
            "concept_code_source": "current_catalog",
            "concept_name": "Renta",
            "concept_name_source": "document_snapshot",
            "net_cents": 2500,
            "confirmed_cents": 2500,
            "reversed_cents": 0,
        },
    ]
    assert all(isinstance(item["net_cents"], int) for item in payload["concepts"])
    assert "nota privada" not in response.text
    assert "99999" not in response.text
    assert any(
        record.message == "agent.request.accepted"
        and getattr(record, "operation", None) == "GET /api/v1/agent-tools/expenses/summary"
        for record in caplog.records
    )
    too_long = client.get(
        "/api/v1/agent-tools/expenses/summary",
        params={
            "branch_id": BRANCH_ID,
            "from_utc": MAZATLAN_DAY,
            "to_utc": "2026-11-11T07:00:01Z",
        },
        headers=_headers(client, ["agent.operating_expenses.read"]),
    )
    assert too_long.status_code == 400
    assert too_long.json()["detail"]["code"] == "agent_schema_invalid"
    naive = client.get(
        "/api/v1/agent-tools/expenses/summary",
        params={
            "branch_id": BRANCH_ID,
            "from_utc": "2026-10-11T07:00:00",
            "to_utc": NEXT_MAZATLAN_DAY,
        },
        headers=_headers(client, ["agent.operating_expenses.read"]),
    )
    assert naive.status_code == 400
    other_branch = client.get(
        "/api/v1/agent-tools/expenses/summary",
        params={
            "branch_id": SECOND_BRANCH_ID,
            "from_utc": MAZATLAN_DAY,
            "to_utc": NEXT_MAZATLAN_DAY,
        },
        headers=_headers(client, ["agent.operating_expenses.read"]),
    )
    assert other_branch.status_code == 403
    assert other_branch.json()["detail"]["code"] == "agent_branch_denied"
    kitchen_id, kitchen_secret = _configure(
        client, "kitchen", ["agent.context.read", "agent.catalog.read"]
    )
    kitchen = client.get(
        "/api/v1/agent-tools/expenses/summary",
        params={"branch_id": BRANCH_ID, "from_utc": MAZATLAN_DAY, "to_utc": NEXT_MAZATLAN_DAY},
        headers={"Authorization": f"Bearer {_token(client, kitchen_id, kitchen_secret)}"},
    )
    assert kitchen.status_code == 403
    with factory() as session:
        assert _counts(session)["expense_documents"] == before["expense_documents"] + 5


def _sale(
    session,
    suffix: str,
    when: datetime,
    method: str,
    net: int,
    *,
    channel: str = "POS",
    service: str = "takeout",
) -> str:
    order_id = f"018f6f73-2d0a-74f0-8f1c-00000000f{suffix}"
    payment_id = f"018f6f73-2d0a-74f0-8f1c-00000000a{suffix}"
    snapshot_id = f"018f6f73-2d0a-74f0-8f1c-00000000b{suffix}"
    session.execute(
        models.orders.insert().values(
            id=order_id,
            organization_id=ORGANIZATION_ID,
            branch_id=BRANCH_ID,
            cash_shift_id="018f6f73-2d0a-74f0-8f1c-00000000f000",
            folio=f"VENTA-{suffix}",
            channel=channel,
            status="CLOSED",
            total_cents=net,
            currency="MXN",
            customer_snapshot={"name": "Cliente Privado", "phone": "6671999999"},
            created_at=when,
        )
    )
    session.execute(
        models.payments.insert().values(
            id=payment_id,
            organization_id=ORGANIZATION_ID,
            branch_id=BRANCH_ID,
            order_id=order_id,
            cash_shift_id="018f6f73-2d0a-74f0-8f1c-00000000f000",
            method=method,
            status="CONFIRMED",
            amount_cents=net,
            currency="MXN",
            confirmed_at=when,
            created_at=when,
        )
    )
    session.execute(
        models.sales_operation_snapshots.insert().values(
            id=snapshot_id,
            organization_id=ORGANIZATION_ID,
            branch_id=BRANCH_ID,
            payment_id=payment_id,
            order_id=order_id,
            cash_shift_id="018f6f73-2d0a-74f0-8f1c-00000000f000",
            register_code_snapshot="CAJA-1",
            folio_snapshot=f"FOLIO-PRIVADO-{suffix}",
            service_type_snapshot=service,
            currency="MXN",
            gross_cents=net,
            net_cents=net,
            discount_cents=0,
            courtesy_cents=0,
            tax_cents=0,
            quality_status="captured",
            confirmed_at=when,
            created_at=when,
        )
    )
    return order_id


def test_payment_methods_follow_sales_net_and_mazatlan_day() -> None:
    factory = _factory()
    inside = datetime(2026, 10, 11, 12, 0, tzinfo=UTC)
    with factory() as session:
        before = _counts(session)
        session.execute(
            models.cash_shifts.insert().values(
                id="018f6f73-2d0a-74f0-8f1c-00000000f000",
                organization_id=ORGANIZATION_ID,
                branch_id=BRANCH_ID,
                register_code="DASH-PAY",
                status="OPEN",
                opening_cash_cents=0,
                opened_at=inside,
                created_at=inside,
            )
        )
        _sale(session, "101", datetime(2026, 10, 11, 6, 59, tzinfo=UTC), "debit_card", 2000)
        _sale(session, "102", inside, "cash", 2000)
        delivery = _sale(session, "103", inside, "cash", 11600, service="delivery")
        _sale(session, "104", inside, "transfer", 5000, channel="RAPPI")
        _sale(session, "105", datetime(2026, 10, 12, 7, 0, tzinfo=UTC), "cash", 9000)
        session.execute(
            models.order_reopen_requests.insert().values(
                id="018f6f73-2d0a-74f0-8f1c-00000000f201",
                organization_id=ORGANIZATION_ID,
                branch_id=BRANCH_ID,
                order_id=delivery,
                status="APPLIED",
                order_version_snapshot=1,
                order_status_snapshot="CLOSED",
                before_snapshot={},
                reason="Garantia sintetica",
                evidence_refs=["TDD-TC-479"],
                requested_by_user_id=ADMIN_USER_ID,
                requested_at=inside,
                decided_by_user_id=ADMIN_USER_ID,
                decided_at=inside,
                decision_reason="Aprobada",
                applied_by_user_id=ADMIN_USER_ID,
                applied_at=inside,
                created_at=inside,
                updated_at=inside,
            )
        )
        session.execute(
            models.order_corrections.insert().values(
                id="018f6f73-2d0a-74f0-8f1c-00000000f202",
                organization_id=ORGANIZATION_ID,
                branch_id=BRANCH_ID,
                order_id=delivery,
                request_id="018f6f73-2d0a-74f0-8f1c-00000000f201",
                folio="CORRECCION-PRIVADA",
                captured_order_version=1,
                resulting_order_version=2,
                before_snapshot={},
                after_snapshot={},
                currency="MXN",
                corrected_total_cents=11200,
                settlement_delta_cents=-400,
                status="APPLIED",
                actor_user_id=ADMIN_USER_ID,
                applied_at=inside,
            )
        )
        session.commit()

    client = _client(factory)
    denied = client.get(
        "/api/v1/agent-tools/payments/by-method",
        params={"branch_id": BRANCH_ID, "from_utc": MAZATLAN_DAY, "to_utc": NEXT_MAZATLAN_DAY},
        headers=_headers(client, ["agent.sales.read"]),
    )
    assert denied.status_code == 403
    assert denied.json()["detail"]["code"] == "agent_capability_denied"
    headers = _headers(client, ["agent.sales.read", "agent.payment_methods.read"])
    params = {"branch_id": BRANCH_ID, "from_utc": MAZATLAN_DAY, "to_utc": NEXT_MAZATLAN_DAY}
    response = client.get("/api/v1/agent-tools/payments/by-method", params=params, headers=headers)
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["external_orders_included"] is True
    assert payload["net_includes_tax_and_delivery"] is True
    assert payload["order_count"] == 3
    assert payload["external_order_count"] == 1
    assert payload["methods"] == [
        {
            "currency": "MXN",
            "method": "cash",
            "operation_count": 2,
            "net_cents": 13600,
            "external_operation_count": 0,
            "delivery_operation_count": 1,
        },
        {
            "currency": "MXN",
            "method": "transfer",
            "operation_count": 1,
            "net_cents": 5000,
            "external_operation_count": 1,
            "delivery_operation_count": 0,
        },
    ]
    assert payload["totals_by_currency"] == [
        {"currency": "MXN", "net_cents": 18600, "operation_count": 3}
    ]
    assert payload["corrections_by_currency"] == [
        {"currency": "MXN", "correction_count": 1, "net_delta_cents": -400}
    ]
    sales = client.get("/api/v1/agent-tools/sales/summary", params=params, headers=headers)
    assert sales.status_code == 200, sales.text
    assert sales.json()["totals_by_currency"][0]["net_cents"] == 18600
    assert "Cliente Privado" not in response.text
    assert "6671999999" not in response.text
    assert "FOLIO-PRIVADO" not in response.text
    too_long = client.get(
        "/api/v1/agent-tools/payments/by-method",
        params={
            "branch_id": BRANCH_ID,
            "from_utc": "2026-10-01T00:00:00Z",
            "to_utc": "2026-11-01T00:00:01Z",
        },
        headers=headers,
    )
    assert too_long.status_code == 400
    with factory() as session:
        assert _counts(session)["payments"] == before["payments"] + 5


def _movement(
    session,
    identifier: str,
    kind: str,
    source: str,
    amount: int,
    when: datetime,
    *,
    source_id: str | None = None,
    name: str | None = None,
    reference: str | None = None,
) -> None:
    session.execute(
        models.cash_movements.insert().values(
            id=identifier,
            organization_id=ORGANIZATION_ID,
            branch_id=BRANCH_ID,
            cash_shift_id="018f6f73-2d0a-74f0-8f1c-00000000d010",
            movement_type=kind,
            amount_cents=amount,
            reason_code="DASHBOARD",
            reason="Movimiento sintetico",
            source_type=source,
            source_id=source_id,
            reference=reference,
            concept_snapshot={"name": name} if name else None,
            actor_user_id=ADMIN_USER_ID,
            idempotency_key=identifier,
            status="confirmed",
            created_at=when,
        )
    )


def _recon_order(
    session,
    suffix: str,
    when: datetime,
    method: str,
    cents: int,
    *,
    name: str,
    phone: str,
    status: str = "CLOSED",
) -> str:
    order_id = f"018f6f73-2d0a-74f0-8f1c-00000000d1{suffix}"
    session.execute(
        models.orders.insert().values(
            id=order_id,
            organization_id=ORGANIZATION_ID,
            branch_id=BRANCH_ID,
            cash_shift_id="018f6f73-2d0a-74f0-8f1c-00000000d010",
            folio=f"TICKET-{suffix}",
            channel="POS",
            status=status,
            total_cents=cents,
            currency="MXN",
            owner_name=name,
            customer_snapshot={"name": name, "phone": phone},
            created_at=when,
        )
    )
    if status != "CANCELLED":
        session.execute(
            models.payments.insert().values(
                id=f"018f6f73-2d0a-74f0-8f1c-00000000d2{suffix}",
                organization_id=ORGANIZATION_ID,
                branch_id=BRANCH_ID,
                order_id=order_id,
                cash_shift_id="018f6f73-2d0a-74f0-8f1c-00000000d010",
                method=method,
                status="CONFIRMED",
                amount_cents=cents,
                currency="MXN",
                confirmed_at=when,
                created_at=when,
            )
        )
    return order_id


def test_daily_reconciliation_hides_personal_data_until_explicit_flag() -> None:
    factory = _factory()
    local_evening = datetime(2026, 10, 10, 18, 0, tzinfo=UTC)
    before_midnight = datetime(2026, 10, 11, 6, 30, tzinfo=UTC)
    after_midnight = datetime(2026, 10, 11, 7, 30, tzinfo=UTC)
    closed_at = datetime(2026, 10, 11, 8, 0, tzinfo=UTC)
    with factory() as session:
        before = _counts(session)
        session.execute(
            models.branches.update()
            .where(models.branches.c.id == BRANCH_ID)
            .values(timezone="America/Mazatlan")
        )
        session.execute(
            models.cash_shifts.insert().values(
                id="018f6f73-2d0a-74f0-8f1c-00000000d010",
                organization_id=ORGANIZATION_ID,
                branch_id=BRANCH_ID,
                register_code="DASH-CAJA",
                status="OPEN",
                opening_cash_cents=50000,
                cashier_user_id=ADMIN_USER_ID,
                opened_at=datetime(2026, 10, 10, 15, 0, tzinfo=UTC),
                created_at=datetime(2026, 10, 10, 15, 0, tzinfo=UTC),
            )
        )
        _recon_order(
            session, "11", before_midnight, "debit_card", 5000, name="Tarjeta A", phone="6671000011"
        )
        _recon_order(
            session, "12", after_midnight, "debit_card", 7000, name="Tarjeta B", phone="6671000012"
        )
        transfer = _recon_order(
            session,
            "13",
            local_evening,
            "transfer",
            3000,
            name="Cliente Transferencia",
            phone="6671000003",
        )
        _recon_order(
            session,
            "14",
            local_evening,
            "credit",
            2500,
            name="Cliente Credito Privado",
            phone="6671000000",
        )
        _movement(
            session,
            "018f6f73-2d0a-74f0-8f1c-00000000d020",
            "deposit",
            "MANUAL",
            4000,
            local_evening,
        )
        _movement(
            session,
            "018f6f73-2d0a-74f0-8f1c-00000000d021",
            "withdrawal",
            "PURCHASE",
            15000,
            local_evening,
            source_id="018f6f73-2d0a-74f0-8f1c-00000000d025",
        )
        session.execute(
            models.suppliers.insert().values(
                id="018f6f73-2d0a-74f0-8f1c-00000000d024",
                organization_id=ORGANIZATION_ID,
                code="SIGMA-DASH",
                commercial_name="Sigma Alimentos",
                status="active",
                created_at=local_evening,
                updated_at=local_evening,
            )
        )
        session.execute(
            models.purchase_documents.insert().values(
                id="018f6f73-2d0a-74f0-8f1c-00000000d025",
                organization_id=ORGANIZATION_ID,
                branch_id=BRANCH_ID,
                supplier_id="018f6f73-2d0a-74f0-8f1c-00000000d024",
                document_type="note",
                folio="COMPRA-PRIVADA",
                document_date=local_evening,
                subtotal=150,
                discount_total=0,
                tax_total=0,
                freight_total=0,
                total=150,
                payment_method="cash",
                paid_from_cash=True,
                cash_movement_id="018f6f73-2d0a-74f0-8f1c-00000000d021",
                status="confirmed",
                created_by=ADMIN_USER_ID,
                confirmed_by=ADMIN_USER_ID,
                created_at=local_evening,
                confirmed_at=local_evening,
            )
        )
        _movement(
            session,
            "018f6f73-2d0a-74f0-8f1c-00000000d022",
            "withdrawal",
            "MANUAL",
            12000,
            local_evening,
            name="Luz",
        )
        _movement(
            session,
            "018f6f73-2d0a-74f0-8f1c-00000000d023",
            "withdrawal",
            "MANUAL",
            8000,
            local_evening,
            name="RETIRO A BOVEDA",
            reference="Ana Recepcion",
        )
        cancelled = _recon_order(
            session,
            "15",
            local_evening,
            "cash",
            900,
            name="Cliente Cancelado",
            phone="6671000002",
            status="CANCELLED",
        )
        session.execute(
            models.order_events.insert().values(
                id="018f6f73-2d0a-74f0-8f1c-00000000d029",
                order_id=cancelled,
                event_type="ORDER_CANCELLED",
                payload={"reason": "garantia"},
                created_at=local_evening,
            )
        )
        session.execute(
            models.order_reopen_requests.insert().values(
                id="018f6f73-2d0a-74f0-8f1c-00000000d026",
                organization_id=ORGANIZATION_ID,
                branch_id=BRANCH_ID,
                order_id=transfer,
                status="APPLIED",
                order_version_snapshot=1,
                order_status_snapshot="CLOSED",
                before_snapshot={},
                reason="Devolucion garantia",
                evidence_refs=["TDD-TC-480"],
                requested_by_user_id=ADMIN_USER_ID,
                requested_at=local_evening,
                decided_by_user_id=ADMIN_USER_ID,
                decided_at=local_evening,
                decision_reason="Aprobada",
                applied_by_user_id=ADMIN_USER_ID,
                applied_at=local_evening,
                created_at=local_evening,
                updated_at=local_evening,
            )
        )
        session.execute(
            models.order_corrections.insert().values(
                id="018f6f73-2d0a-74f0-8f1c-00000000d027",
                organization_id=ORGANIZATION_ID,
                branch_id=BRANCH_ID,
                order_id=transfer,
                request_id="018f6f73-2d0a-74f0-8f1c-00000000d026",
                folio="CORR-PRIVADA",
                captured_order_version=1,
                resulting_order_version=2,
                before_snapshot={},
                after_snapshot={},
                currency="MXN",
                corrected_total_cents=2500,
                settlement_delta_cents=-500,
                status="APPLIED",
                actor_user_id=ADMIN_USER_ID,
                applied_at=local_evening,
            )
        )
        session.execute(
            models.order_payment_adjustments.insert().values(
                id="018f6f73-2d0a-74f0-8f1c-00000000d028",
                correction_id="018f6f73-2d0a-74f0-8f1c-00000000d027",
                original_payment_id="018f6f73-2d0a-74f0-8f1c-00000000d213",
                adjustment_type="REFUND",
                amount_cents=500,
                method="transfer",
                currency="MXN",
                status="CONFIRMED",
                evidence_refs=["TDD-TC-480"],
                created_at=local_evening,
            )
        )
        session.commit()
        opened = get_branch_daily_reconciliation(session, BRANCH_ID, "2026-10-10", None)
        expected = int(opened["balance"]["expected_cash_in_register"] * 100)
        sales = int(opened["balance"]["total_sales_with_tax"] * 100)
        cash = int(opened["balance"]["cash_sales"] * 100)
        session.rollback()
        session.execute(
            models.cash_shifts.update()
            .where(models.cash_shifts.c.id == "018f6f73-2d0a-74f0-8f1c-00000000d010")
            .values(status="CLOSED", closed_at=closed_at)
        )
        session.execute(
            models.cash_shift_cuts.insert().values(
                id="018f6f73-2d0a-74f0-8f1c-00000000d030",
                organization_id=ORGANIZATION_ID,
                branch_id=BRANCH_ID,
                cash_shift_id="018f6f73-2d0a-74f0-8f1c-00000000d010",
                sales_total_cents=sales,
                payment_total_cents=sales,
                cash_payment_total_cents=cash,
                opening_cash_cents=50000,
                expected_cash_cents=expected,
                counted_cash_cents=expected + 150,
                difference_cents=150,
                status="FINAL",
                created_at=closed_at,
            )
        )
        session.commit()

    client = _client(factory)
    params = {"branch_id": BRANCH_ID, "from_date": "2026-10-10", "to_date": "2026-10-11"}
    denied = client.get(
        "/api/v1/agent-tools/cash/daily-reconciliation",
        params=params,
        headers=_headers(client, ["agent.cash_personal_data.read"]),
    )
    assert denied.status_code == 403
    assert denied.json()["detail"]["code"] == "agent_capability_denied"
    client_id, secret = _configure(client, "administrator", ["agent.cash_reconciliation.read"])
    headers = {"Authorization": f"Bearer {_token(client, client_id, secret)}"}
    response = client.get(
        "/api/v1/agent-tools/cash/daily-reconciliation", params=params, headers=headers
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["timezone"] == "America/Mazatlan"
    assert payload["personal_data_included"] is False
    assert payload["contract_version"] == 2
    first, second = payload["days"]
    assert first["from_utc"].startswith("2026-10-10T07:00:00")
    assert second["from_utc"].startswith("2026-10-11T07:00:00")
    opened_shift = first["shifts_opened"]
    assert opened_shift["card_cents"] == 12000
    assert opened_shift["transfer_cents"] == 3000
    assert opened_shift["deposit_cents"] == 4000
    assert opened_shift["supplier_payments"] == [
        {"supplier_name": "Sigma Alimentos", "amount_cents": 15000}
    ]
    assert opened_shift["fixed_expenses"] == [{"expense_type": "Luz", "amount_cents": 12000}]
    assert opened_shift["cash_withdrawals_cents"] == 8000
    assert opened_shift["cash_withdrawals_count"] == 1
    assert opened_shift["credit_clients_cents"] == 2500
    assert opened_shift["credit_clients_count"] == 1
    assert opened_shift["surplus_shortage_cents"] == 150
    assert opened_shift["physical_count_status"] == "COUNTED"
    assert "cash_withdrawals" not in opened_shift
    assert "credit_clients" not in opened_shift
    assert "transfers" not in opened_shift
    assert first["calendar_activity"]["card_cents"] == 5000
    assert second["shifts_opened"]["card_cents"] == 0
    assert second["shifts_opened"]["surplus_shortage_cents"] is None
    assert second["calendar_activity"]["card_cents"] == 7000
    assert first["refunds"]["correction_refunds_cents"] == 500
    assert first["refunds"]["correction_refund_count"] == 1
    assert first["refunds"]["cancelled_orders_cents"] == 900
    assert first["refunds"]["cancelled_order_count"] == 1
    assert "lines" not in first["refunds"]
    assert second["refunds"]["correction_refunds_cents"] == 0
    assert second["refunds"]["cancelled_orders_cents"] == 0
    assert first["production_bakery"] == {
        "recorded": False,
        "amount_cents": None,
        "reason": "not_recorded",
    }
    hidden = response.text
    for private_value in (
        "Cliente Credito Privado",
        "6671000000",
        "Ana Recepcion",
        "Cliente Transferencia",
        "6671000003",
        "Cliente Cancelado",
        "6671000002",
        "COMPRA-PRIVADA",
        "CORR-PRIVADA",
    ):
        assert private_value not in hidden
    too_long = client.get(
        "/api/v1/agent-tools/cash/daily-reconciliation",
        params={"branch_id": BRANCH_ID, "from_date": "2026-10-01", "to_date": "2026-11-01"},
        headers=headers,
    )
    assert too_long.status_code == 400
    invalid_day = client.get(
        "/api/v1/agent-tools/cash/daily-reconciliation",
        params={"branch_id": BRANCH_ID, "from_date": "2026-02-31", "to_date": "2026-03-01"},
        headers=headers,
    )
    assert invalid_day.status_code == 400
    stored = client.get("/api/v1/integrations/grokbot/config", headers=_admin_headers()).json()
    administrator = next(row for row in stored["identities"] if row["profile"] == "administrator")
    revealed = client.put(
        "/api/v1/integrations/grokbot/identities/administrator",
        headers=_admin_headers(),
        json={
            "is_enabled": True,
            "capabilities": ["agent.cash_reconciliation.read", "agent.cash_personal_data.read"],
            "branch_ids": [BRANCH_ID],
            "corporate_scope": False,
            "expected_authorization_version": administrator["authorization_version"],
        },
    )
    assert revealed.status_code == 200, revealed.text
    personal = client.get(
        "/api/v1/agent-tools/cash/daily-reconciliation",
        params=params,
        headers={"Authorization": f"Bearer {_token(client, client_id, secret)}"},
    )
    assert personal.status_code == 200, personal.text
    revealed_payload = personal.json()
    assert revealed_payload["personal_data_included"] is True
    revealed_shift = revealed_payload["days"][0]["shifts_opened"]
    assert revealed_shift["cash_withdrawals"] == [
        {"folio": "RET-018F6F", "amount_cents": 8000, "received_by": "Ana Recepcion"}
    ]
    assert revealed_shift["credit_clients"][0]["name"] == "Cliente Credito Privado"
    assert revealed_shift["credit_clients"][0]["phone"] == "6671000000"
    assert revealed_shift["credit_clients"][0]["amount_cents"] == 2500
    refund_lines = revealed_payload["days"][0]["refunds"]["lines"]
    assert refund_lines[0]["kind"] == "correction_refund"
    assert refund_lines[0]["ticket"] == "TICKET-13"
    assert refund_lines[0]["amount_cents"] == 500
    assert refund_lines[0]["name"] == "Cliente Transferencia"
    assert refund_lines[0]["phone"] == "6671000003"
    assert any(
        line["kind"] == "cancellation" and line["phone"] == "6671000002" for line in refund_lines
    )
    with factory() as session:
        assert _counts(session)["cash_movements"] == before["cash_movements"] + 4
        assert _counts(session)["purchase_documents"] == before["purchase_documents"] + 1


def test_new_flags_stay_off_and_purchase_history_stays_with_purchasing() -> None:
    client = _client(_factory())
    saved = client.put(
        "/api/v1/integrations/grokbot/config",
        headers=_admin_headers(),
        json={"display_name": "Administrador Kiwi", "is_enabled": True},
    )
    assert saved.status_code == 200, saved.text
    administrator = next(
        row for row in saved.json()["identities"] if row["profile"] == "administrator"
    )
    for capability in OPT_IN:
        assert capability not in administrator["capabilities"]
    expanded = client.put(
        "/api/v1/integrations/grokbot/identities/administrator",
        headers=_admin_headers(),
        json={
            "is_enabled": False,
            "capabilities": [*administrator["capabilities"], "agent.purchases.read"],
            "branch_ids": [],
            "corporate_scope": False,
            "expected_authorization_version": administrator["authorization_version"],
        },
    )
    assert expanded.status_code == 400
    assert expanded.json()["detail"]["code"] == "agent_capability_denied"


def test_dashboard_reads_fail_closed_without_a_human_financial_audience() -> None:
    factory = _factory()
    with factory() as session:
        session.execute(
            models.blind_cash_policy_revisions.insert().values(
                organization_id=ORGANIZATION_ID,
                branch_id=BRANCH_ID,
                revision=1,
                manifest_digest="a" * 64,
                minimum_api_version=2,
                minimum_client_version=2,
                minimum_gateway_version=2,
                event="activated",
                created_at=datetime(2026, 10, 11, tzinfo=UTC),
            )
        )
        session.commit()
    client = _client(factory)
    headers = _headers(
        client,
        [
            "agent.operating_expenses.read",
            "agent.payment_methods.read",
            "agent.cash_reconciliation.read",
        ],
    )
    period = {"branch_id": BRANCH_ID, "from_utc": MAZATLAN_DAY, "to_utc": NEXT_MAZATLAN_DAY}
    for path in ("expenses/summary", "payments/by-method"):
        response = client.get(f"/api/v1/agent-tools/{path}", params=period, headers=headers)
        assert response.status_code == 403, response.text
        assert response.json()["detail"]["code"] == "financial_access_denied"
    daily = client.get(
        "/api/v1/agent-tools/cash/daily-reconciliation",
        params={"branch_id": BRANCH_ID, "from_date": "2026-10-11", "to_date": "2026-10-11"},
        headers=headers,
    )
    assert daily.status_code == 403, daily.text
    assert daily.json()["detail"]["code"] == "financial_access_denied"
