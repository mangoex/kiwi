"""Strict JSON Schema contracts for PCO-004 cash shifts and sales reporting."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

jsonschema = pytest.importorskip("jsonschema")
referencing = pytest.importorskip("referencing")

SCHEMA_DIR = Path(__file__).resolve().parents[3] / "packages" / "contracts" / "schemas"
PCO004_SCHEMAS = (
    "business-error-v1.schema.json",
    "cash-shift-open-command-v1.schema.json",
    "cash-shift-close-command-v1.schema.json",
    "cash-shift-v1.schema.json",
    "cash-shift-current-v1.schema.json",
    "cash-shift-operational-close-response-v1.schema.json",
    "cash-shift-list-v1.schema.json",
    "cash-shift-detail-v1.schema.json",
    "sales-monitor-v1.schema.json",
    "sales-monitor-drill-down-v1.schema.json",
)
AT = "2026-08-12T05:00:00+00:00"


def _schemas() -> dict[str, dict[str, Any]]:
    return {
        name: json.loads((SCHEMA_DIR / name).read_text(encoding="utf-8"))
        for name in PCO004_SCHEMAS
    }


def _validators() -> dict[str, Any]:
    schemas = _schemas()
    registry = referencing.Registry().with_resources(
        (schema["$id"], referencing.Resource.from_contents(schema))
        for schema in schemas.values()
    )
    return {
        name: jsonschema.Draft202012Validator(
            schema,
            registry=registry,
            format_checker=jsonschema.FormatChecker(),
        )
        for name, schema in schemas.items()
    }


def _shift(status: str = "OPEN") -> dict[str, Any]:
    return {
        "id": "shift-1",
        "organization_id": "org-1",
        "branch_id": "branch-1",
        "register_code": "CAJA-04",
        "status": status,
        "opening_cash_cents": 10_000,
        "opened_at": AT,
        "closed_at": None if status == "OPEN" else "2026-08-12T13:00:00+00:00",
        "created_at": AT,
    }


def _summary() -> dict[str, int]:
    return {
        "sales_total_cents": 5_000,
        "payment_total_cents": 5_000,
        "cash_payment_cents": 3_000,
        "opening_cash_cents": 10_000,
        "deposit_cents": 1_000,
        "withdrawal_cents": 2_000,
        "excluded_movement_count": 0,
        "expected_cash_cents": 12_000,
        "confirmed_payment_count": 2,
        "closed_order_count": 2,
    }


def _closure() -> dict[str, Any]:
    return {
        "id": "closure-1",
        "organization_id": "org-1",
        "branch_id": "branch-1",
        "cash_shift_id": "shift-1",
        "register_code_snapshot": "CAJA-04",
        "closed_by_user_id": "user-1",
        "summary_snapshot": _summary(),
        "closed_at": "2026-08-12T13:00:00+00:00",
        "created_at": "2026-08-12T13:00:00+00:00",
    }


def _indicator(known_cents: int = 0, unknown: int = 0) -> dict[str, int]:
    return {"known_cents": known_cents, "unknown_operation_count": unknown}


def _filters() -> dict[str, Any]:
    return {
        "from_utc": "2026-08-12T00:00:00+00:00",
        "to_utc": "2026-08-13T00:00:00+00:00",
        "branch_id": "branch-1",
        "register_id": None,
        "cash_shift_id": None,
        "family_id": None,
        "service_type": None,
    }


def _metrics() -> dict[str, Any]:
    return {
        "gross": _indicator(1_500),
        "net": _indicator(1_200),
        "tax": _indicator(0, 1),
        "discount": _indicator(0, 1),
        "courtesy": _indicator(0, 1),
    }


def _monitor() -> dict[str, Any]:
    breakdown = {
        "id": "family-1",
        "label": "Comida",
        **_metrics(),
        "order_count": 1,
        "line_count": 1,
        "item_quantity": 2,
    }
    return {
        "applied_filters": _filters(),
        "summary": {
            **_metrics(),
            "order_count": 1,
            "line_count": 1,
            "item_quantity": 2,
            "legacy_backfilled_line_count": 1,
        },
        "corrections": {
            "count": 0,
            "charge_cents": 0,
            "refund_cents": 0,
            "net_delta_cents": 0,
            "cash_adjustment_count": 0,
        },
        "breakdowns": {
            "families": [breakdown],
            "services": [{**breakdown, "id": "takeout", "label": "Para llevar"}],
        },
        "facets": {
            "cash_shifts": [{"id": "shift-1", "label": "CAJA-04"}],
            "families": [{"id": "family-1", "label": "Comida"}],
            "service_types": [{"id": "takeout", "label": "Para llevar"}],
        },
        "data_quality": {"incomplete_operation_count": 1},
    }


def _correction_item() -> dict[str, Any]:
    return {
        "correction_id": "018f6f73-2d0a-74f0-8f1c-000000008001",
        "order_id": "018f6f73-2d0a-74f0-8f1c-000000008002",
        "folio": "COR-0001",
        "branch_id": "018f6f73-2d0a-74f0-8f1c-000000008003",
        "applied_at": AT,
        "settlement_delta_cents": -500,
        "currency": "MXN",
        "payment_adjustment_id": "018f6f73-2d0a-74f0-8f1c-000000008004",
        "adjustment_type": "REFUND",
        "method": "cash",
        "amount_cents": 500,
        "cash_shift_id": "018f6f73-2d0a-74f0-8f1c-000000008005",
        "register_id": "CAJA-04",
    }


def test_every_pco004_schema_is_draft_2020_12_valid() -> None:
    schemas = _schemas()
    assert set(schemas) == set(PCO004_SCHEMAS)
    for schema in schemas.values():
        jsonschema.Draft202012Validator.check_schema(schema)


def test_cash_shift_commands_are_exact_and_forbid_counted_cash() -> None:
    validators = _validators()
    open_validator = validators["cash-shift-open-command-v1.schema.json"]
    open_validator.validate(
        {"branch_id": "branch-1", "register_id": "CAJA-04", "opening_cash_cents": 0}
    )
    with pytest.raises(jsonschema.ValidationError):
        open_validator.validate(
            {
                "branch_id": "branch-1",
                "register_id": "CAJA-04",
                "opening_cash_cents": 0,
                "actor_user_id": "forbidden",
            }
        )
    close_validator = validators["cash-shift-close-command-v1.schema.json"]
    close_validator.validate({})
    for forbidden in (
        "counted_cash_cents",
        "expected_cash_cents",
        "difference_cents",
        "branch_id",
        "register_id",
    ):
        with pytest.raises(jsonschema.ValidationError):
            close_validator.validate({forbidden: 0})


def test_cash_shift_response_list_detail_current_and_error_are_strict() -> None:
    validators = _validators()
    open_shift = _shift()
    closed_shift = _shift("OPERATIVELY_CLOSED")
    closure = _closure()
    validators["cash-shift-v1.schema.json"].validate(open_shift)
    validators["cash-shift-operational-close-response-v1.schema.json"].validate(
        {"cash_shift": closed_shift, "closure": closure}
    )
    validators["cash-shift-list-v1.schema.json"].validate(
        {"items": [open_shift, closed_shift], "next_cursor": None}
    )
    validators["cash-shift-detail-v1.schema.json"].validate(
        {"cash_shift": closed_shift, "closure": closure}
    )
    validators["cash-shift-current-v1.schema.json"].validate(
        {"cash_shift": None, "closure": closure}
    )
    validators["business-error-v1.schema.json"].validate(
        {"detail": {"code": "cash_shift_not_open", "message": "Shift is not OPEN"}}
    )
    invalid = {"cash_shift": closed_shift, "closure": {**closure, "idempotency_key": "secret"}}
    with pytest.raises(jsonschema.ValidationError):
        validators["cash-shift-detail-v1.schema.json"].validate(invalid)


def test_sales_monitor_contract_preserves_unknown_indicators_and_rejects_extensions() -> None:
    validator = _validators()["sales-monitor-v1.schema.json"]
    monitor = _monitor()
    validator.validate(monitor)
    assert monitor["summary"]["tax"] == {
        "known_cents": 0,
        "unknown_operation_count": 1,
    }
    assert monitor["corrections"] == {
        "count": 0,
        "charge_cents": 0,
        "refund_cents": 0,
        "net_delta_cents": 0,
        "cash_adjustment_count": 0,
    }
    top_level_extra = {**monitor, "total_tax_cents": 0}
    with pytest.raises(jsonschema.ValidationError):
        validator.validate(top_level_extra)
    nested_extra = deepcopy(monitor)
    nested_extra["breakdowns"]["families"][0]["customer_name"] = "PII"
    with pytest.raises(jsonschema.ValidationError):
        validator.validate(nested_extra)


def test_sales_monitor_drill_down_is_strict_and_contains_no_pii_or_payloads() -> None:
    validator = _validators()["sales-monitor-drill-down-v1.schema.json"]
    item = {
        "payment_id": "payment-1",
        "order_id": "order-1",
        "folio": "F-0001",
        "branch_id": "branch-1",
        "cash_shift_id": "shift-1",
        "register_id": "CAJA-04",
        "service_type": "takeout",
        "confirmed_at": AT,
        **_metrics(),
        "order_count": 1,
        "line_count": 1,
        "item_quantity": 2,
        "quality_status": "incomplete",
    }
    response = {
        "applied_filters": _filters(),
        "metric": "tax",
        "items": [item],
        "next_cursor": "opaque-cursor",
        "corrections": [_correction_item()],
    }
    validator.validate(response)
    for forbidden in ("customer_name", "idempotency_key", "payload", "evidence_refs"):
        invalid = deepcopy(response)
        invalid["items"][0][forbidden] = "forbidden"
        with pytest.raises(jsonschema.ValidationError):
            validator.validate(invalid)
    for forbidden in ("evidence_refs", "actor_user_id", "before_snapshot", "payload"):
        invalid = deepcopy(response)
        invalid["corrections"][0][forbidden] = "forbidden"
        with pytest.raises(jsonschema.ValidationError):
            validator.validate(invalid)
    invalid_correction = deepcopy(response)
    invalid_correction["corrections"][0]["currency"] = "mxn"
    with pytest.raises(jsonschema.ValidationError):
        validator.validate(invalid_correction)
