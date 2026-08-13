"""PCO-004 reporting projection regressions."""

from __future__ import annotations

from datetime import timedelta

import pytest
from restaurant_os import models
from restaurant_os.operations import BusinessError, ReportingProjectionService
from test_cash_ledger import (
    BRANCH_A,
    CASHIER_ID,
    CASHIER_ROLE_ID,
    NOW,
    ORG_ID,
    SHIFT_ID,
    _new_session,
)


def test_monitor_preserves_unknown_values_and_drilldown_hides_pii(
    caplog: pytest.LogCaptureFixture,
) -> None:
    engine, session = _new_session()
    try:
        caplog.set_level("INFO", logger="restaurant_os.operations")
        session.execute(models.permissions.insert().values(
            id="018f6f73-2d0a-74f0-8f1c-000000008001", code="reports.sales.read",
            description="reports", created_at=NOW,
        ))
        session.execute(models.role_permissions.insert().values(
            role_id=CASHIER_ROLE_ID,
            permission_id="018f6f73-2d0a-74f0-8f1c-000000008001",
        ))
        payment_id = "018f6f73-2d0a-74f0-8f1c-000000008002"
        order_id = "018f6f73-2d0a-74f0-8f1c-000000008003"
        session.execute(models.orders.insert().values(
            id=order_id, organization_id=ORG_ID, branch_id=BRANCH_A, cash_shift_id=SHIFT_ID,
            customer_id=None, customer_snapshot={"name": "No exponer"},
            delivery_address_snapshot=None,
            folio="PCO-004", channel="POS", status="CLOSED", total_cents=1000, currency="MXN",
            owner_name=None, order_type="takeout", payment_method_intent=None, version=1,
            created_at=NOW, accepted_at=NOW,
        ))
        session.execute(models.payments.insert().values(
            id=payment_id, organization_id=ORG_ID, branch_id=BRANCH_A, order_id=order_id,
            cash_shift_id=SHIFT_ID, method="cash", status="CONFIRMED", amount_cents=1000,
            currency="MXN", confirmed_at=NOW, created_at=NOW,
        ))
        snapshot_id = "018f6f73-2d0a-74f0-8f1c-000000008004"
        session.execute(models.sales_operation_snapshots.insert().values(
            id=snapshot_id, organization_id=ORG_ID, branch_id=BRANCH_A, payment_id=payment_id,
            order_id=order_id, cash_shift_id=SHIFT_ID, register_code_snapshot="CAJA-01",
            folio_snapshot="PCO-004", service_type_snapshot="takeout", currency="MXN",
            gross_cents=1000, net_cents=1200, discount_cents=0, courtesy_cents=0, tax_cents=None,
            quality_status="incomplete", confirmed_at=NOW, created_at=NOW,
        ))
        session.execute(models.sales_operation_line_snapshots.insert().values(
            id="018f6f73-2d0a-74f0-8f1c-000000008005",
            sales_operation_snapshot_id=snapshot_id, payment_id=payment_id,
            order_line_id="line-unused", product_id="product", product_name_snapshot="Producto",
            family_id_snapshot="family-a", family_name_snapshot="Familia A",
            family_snapshot_source="captured", quantity=2, gross_cents=700,
            net_cents=700, discount_cents=0, courtesy_cents=0, tax_cents=None,
        ))
        session.execute(models.sales_operation_line_snapshots.insert().values(
            id="018f6f73-2d0a-74f0-8f1c-000000008006",
            sales_operation_snapshot_id=snapshot_id, payment_id=payment_id,
            order_line_id="line-second", product_id="product-two", product_name_snapshot="Segundo",
            family_id_snapshot="family-b", family_name_snapshot="Familia B",
            family_snapshot_source="captured", quantity=1, gross_cents=300,
            net_cents=None, discount_cents=0, courtesy_cents=0, tax_cents=None,
        ))
        session.commit()
        service = ReportingProjectionService(session, CASHIER_ID)
        period = {
            "from_utc": NOW - timedelta(seconds=1),
            "to_utc": NOW + timedelta(seconds=1),
            "branch_id": BRANCH_A,
        }
        result = service.summary(period)
        assert result["summary"]["gross"]["known_cents"] == 1000
        assert result["summary"]["net"] == {"known_cents": 1200, "unknown_operation_count": 0}
        assert result["breakdowns"]["services"][0]["net"] == {
            "known_cents": 1200,
            "unknown_operation_count": 0,
        }
        assert result["summary"]["tax"] == {"known_cents": 0, "unknown_operation_count": 1}
        family_gross_cents = sum(
            item["gross"]["known_cents"] for item in result["breakdowns"]["families"]
        )
        assert family_gross_cents == 1000
        assert len(result["facets"]["cash_shifts"]) == 1
        drill = service.drill_down({**period, "metric": "tax"})
        assert "customer" not in drill["items"][0]
        assert drill["items"][0]["item_quantity"] == 3
        assert drill["items"][0]["net"] == {"known_cents": 1200, "unknown_operation_count": 0}

        family_result = service.summary({**period, "family_id": "family-a"})
        assert family_result["summary"]["gross"] == {
            "known_cents": 700,
            "unknown_operation_count": 0,
        }
        assert family_result["summary"]["line_count"] == 1
        assert family_result["summary"]["item_quantity"] == 2
        assert family_result["summary"]["net"] == {
            "known_cents": 700,
            "unknown_operation_count": 0,
        }
        assert [item["id"] for item in family_result["breakdowns"]["families"]] == ["family-a"]
        assert [item["id"] for item in family_result["facets"]["families"]] == ["family-a"]
        family_drill = service.drill_down({**period, "family_id": "family-a", "metric": "gross"})
        assert family_drill["items"][0]["gross"] == {
            "known_cents": 700,
            "unknown_operation_count": 0,
        }
        assert family_drill["items"][0]["line_count"] == 1
        assert family_drill["items"][0]["item_quantity"] == 2
        family_unknown = service.summary({**period, "family_id": "family-b"})
        assert family_unknown["summary"]["net"] == {
            "known_cents": 0,
            "unknown_operation_count": 1,
        }
        with pytest.raises(BusinessError) as invalid_cursor:
            service.drill_down({**period, "metric": "gross", "cursor": "garbage|garbage"})
        assert invalid_cursor.value.code == "sales_monitor_cursor_invalid"
        metrics = [record for record in caplog.records if hasattr(record, "metric")]
        assert any(
            record.metric == "sales_monitor_request_total" and record.result == "success"
            for record in metrics
        )
        assert any(
            record.metric == "sales_monitor_request_total"
            and getattr(record, "error_code", None) == "sales_monitor_cursor_invalid"
            for record in metrics
        )
        assert any(
            record.metric == "sales_monitor_incomplete_operations"
            and getattr(record, "value", None) == 1
            for record in metrics
        )
        assert "No exponer" not in "\n".join(record.getMessage() for record in metrics)
    finally:
        session.close()
        engine.dispose()


def test_drill_down_orders_and_paginates_by_normalized_utc_datetimes() -> None:
    engine, session = _new_session()
    try:
        session.execute(models.permissions.insert().values(
            id="018f6f73-2d0a-74f0-8f1c-000000008011", code="reports.sales.read",
            description="reports", created_at=NOW,
        ))
        session.execute(models.role_permissions.insert().values(
            role_id=CASHIER_ROLE_ID,
            permission_id="018f6f73-2d0a-74f0-8f1c-000000008011",
        ))
        early_payment = "018f6f73-2d0a-74f0-8f1c-000000008012"
        late_payment = "018f6f73-2d0a-74f0-8f1c-000000008013"
        for index, (payment_id, confirmed_at) in enumerate((
            (early_payment, NOW),
            (late_payment, NOW + timedelta(microseconds=500_000)),
        ), start=1):
            order_id = f"018f6f73-2d0a-74f0-8f1c-00000000801{3 + index}"
            snapshot_id = f"018f6f73-2d0a-74f0-8f1c-00000000801{5 + index}"
            session.execute(models.orders.insert().values(
                id=order_id, organization_id=ORG_ID, branch_id=BRANCH_A, cash_shift_id=SHIFT_ID,
                customer_id=None, customer_snapshot=None, delivery_address_snapshot=None,
                folio=f"PCO-TIME-{index}", channel="POS", status="CLOSED", total_cents=100,
                currency="MXN", owner_name=None, order_type="takeout", payment_method_intent=None,
                version=1, created_at=confirmed_at, accepted_at=confirmed_at,
            ))
            session.execute(models.payments.insert().values(
                id=payment_id, organization_id=ORG_ID, branch_id=BRANCH_A, order_id=order_id,
                cash_shift_id=SHIFT_ID, method="cash", status="CONFIRMED", amount_cents=100,
                currency="MXN", confirmed_at=confirmed_at, created_at=confirmed_at,
            ))
            session.execute(models.sales_operation_snapshots.insert().values(
                id=snapshot_id, organization_id=ORG_ID, branch_id=BRANCH_A, payment_id=payment_id,
                order_id=order_id, cash_shift_id=SHIFT_ID, register_code_snapshot="CAJA-01",
                folio_snapshot=f"PCO-TIME-{index}", service_type_snapshot="takeout", currency="MXN",
                gross_cents=100, net_cents=100, discount_cents=0, courtesy_cents=0, tax_cents=0,
                quality_status="captured", confirmed_at=confirmed_at, created_at=confirmed_at,
            ))
            session.execute(models.sales_operation_line_snapshots.insert().values(
                id=f"018f6f73-2d0a-74f0-8f1c-00000000802{index}",
                sales_operation_snapshot_id=snapshot_id, payment_id=payment_id,
                order_line_id=f"time-line-{index}", product_id=f"time-product-{index}",
                product_name_snapshot="Temporal", family_id_snapshot="family-time",
                family_name_snapshot="Temporal", family_snapshot_source="captured", quantity=1,
                gross_cents=100, net_cents=100, discount_cents=0, courtesy_cents=0, tax_cents=0,
            ))
        session.commit()
        service = ReportingProjectionService(session, CASHIER_ID)
        raw = {
            "from_utc": NOW - timedelta(seconds=1),
            "to_utc": NOW + timedelta(seconds=1),
            "branch_id": BRANCH_A,
            "metric": "gross",
            "limit": 1,
        }
        first = service.drill_down(raw)
        assert [item["payment_id"] for item in first["items"]] == [late_payment]
        assert first["next_cursor"] is not None
        equivalent_rfc3339_cursor = first["next_cursor"].replace("Z", "+00:00")
        second = service.drill_down({**raw, "cursor": equivalent_rfc3339_cursor})
        assert [item["payment_id"] for item in second["items"]] == [early_payment]
        assert first["items"][0]["payment_id"] != second["items"][0]["payment_id"]
    finally:
        session.close()
        engine.dispose()


def test_monitor_error_paths_emit_one_safe_primary_metric(
    caplog: pytest.LogCaptureFixture,
) -> None:
    engine, session = _new_session()
    try:
        caplog.set_level("INFO", logger="restaurant_os.operations")
        service = ReportingProjectionService(session, CASHIER_ID)
        invalid_period = {"from_utc": NOW, "to_utc": NOW, "branch_id": BRANCH_A}
        with pytest.raises(BusinessError):
            service.summary(invalid_period)
        with pytest.raises(BusinessError):
            service.drill_down({**invalid_period, "metric": "gross", "limit": 101})
        errors = [
            record for record in caplog.records
            if getattr(record, "metric", None) == "sales_monitor_request_total"
            and getattr(record, "result", None) == "error"
        ]
        assert [record.error_code for record in errors] == [
            "sales_monitor_period_invalid", "sales_monitor_filter_invalid"
        ]
    finally:
        session.close()
        engine.dispose()
