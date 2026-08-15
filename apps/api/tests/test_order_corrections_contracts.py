"""TDD-TC-101: deterministic structural gates for PCO-005B JSON schemas.

The repository's local Python runtime does not include ``jsonschema``.  These
tests intentionally inspect every safety-relevant keyword instead of skipping
the contract gate.  CI environments with jsonschema can additionally validate
the documents using Draft202012Validator without changing their semantics.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SCHEMA_DIR = Path(__file__).resolve().parents[3] / "packages" / "contracts" / "schemas"
COMMAND = "order-reopen-apply-command-v1.schema.json"
RESPONSE = "order-reopen-apply-response-v1.schema.json"
SALES_MONITOR = "sales-monitor-v1.schema.json"
SALES_DRILL_DOWN = "sales-monitor-drill-down-v1.schema.json"


def _schema(name: str) -> dict[str, Any]:
    return json.loads((SCHEMA_DIR / name).read_text(encoding="utf-8"))


def _closed_object(
    schema: dict[str, Any],
    required: set[str],
    properties: set[str],
) -> None:
    assert schema["type"] == "object"
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == required
    assert set(schema["properties"]) == properties


def test_pco005b_command_schema_is_draft_2020_12_closed_and_server_authoritative() -> None:
    command = _schema(COMMAND)
    _closed_object(
        command,
        {
            "expected_order_version",
            "lines",
            "production_dispositions",
            "settlement_method",
            "settlement_evidence_refs",
        },
        {
            "expected_order_version",
            "lines",
            "production_dispositions",
            "settlement_method",
            "settlement_evidence_refs",
            "register_id",
        },
    )
    assert command["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert command["$id"].endswith(COMMAND)
    assert command["properties"]["expected_order_version"] == {
        "type": "integer",
        "minimum": 1,
    }
    assert command["properties"]["settlement_method"]["enum"] == [
        "cash",
        "debit_card",
        "credit_card",
        "transfer",
    ]
    assert {
        "actor_user_id",
        "organization_id",
        "branch_id",
        "currency",
        "cash_shift_id",
        "cash_movement_id",
        "total_cents",
        "settlement_delta_cents",
    }.isdisjoint(command["properties"])


def test_pco005b_command_schema_requires_one_exact_line_variant_and_closed_dispositions() -> None:
    definitions = _schema(COMMAND)["$defs"]
    line_variants = definitions["correction_line"]["oneOf"]
    assert line_variants == [
        {"$ref": "#/$defs/retained_line"},
        {"$ref": "#/$defs/addition_line"},
    ]
    _closed_object(
        definitions["retained_line"],
        {"source_line_id", "quantity"},
        {"source_line_id", "quantity"},
    )
    _closed_object(
        definitions["addition_line"],
        {"product_id", "quantity"},
        {"product_id", "quantity"},
    )
    assert definitions["uuid"] == {"type": "string", "format": "uuid"}
    assert definitions["positive_quantity"] == {"type": "integer", "minimum": 1}
    _closed_object(
        definitions["production_disposition"],
        {"source_line_id", "source_task_id", "quantity", "disposition"},
        {"source_line_id", "source_task_id", "quantity", "disposition"},
    )
    assert definitions["production_disposition"]["properties"]["disposition"] == {
        "enum": ["waste", "recovery"]
    }
    assert definitions["production_disposition"]["properties"]["source_line_id"] == {
        "$ref": "#/$defs/uuid"
    }
    assert definitions["production_disposition"]["properties"]["source_task_id"] == {
        "$ref": "#/$defs/uuid"
    }


def test_pco005b_command_schema_requires_register_only_for_cash_and_keeps_evidence_opaque() -> None:
    command = _schema(COMMAND)
    condition = command["allOf"]
    assert condition == [
        {
            "if": {
                "properties": {"settlement_method": {"const": "cash"}},
                "required": ["settlement_method"],
            },
            "then": {"required": ["register_id"]},
            "else": {"not": {"required": ["register_id"]}},
        }
    ]
    register = command["$defs"]["register_id"]
    assert register["type"] == "string"
    assert register["minLength"] == 1
    assert register["maxLength"] == 80
    assert command["$defs"]["evidence_ref"] == {
        "type": "string",
        "minLength": 1,
        "maxLength": 500,
    }


def test_pco005b_response_schema_is_closed_and_excludes_evidence_and_identity() -> None:
    response = _schema(RESPONSE)
    _closed_object(
        response,
        {
            "status",
            "correction",
            "settlement_delta_cents",
            "payment_adjustment",
            "production_adjustments",
        },
        {
            "status",
            "correction",
            "settlement_delta_cents",
            "payment_adjustment",
            "production_adjustments",
        },
    )
    assert response["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert response["$id"].endswith(RESPONSE)
    assert response["properties"]["status"] == {"const": "APPLIED"}
    definitions = response["$defs"]
    _closed_object(
        definitions["correction"],
        {
            "id",
            "request_id",
            "folio",
            "corrected_total_cents",
            "settlement_delta_cents",
            "currency",
            "applied_at",
        },
        {
            "id",
            "request_id",
            "folio",
            "corrected_total_cents",
            "settlement_delta_cents",
            "currency",
            "applied_at",
        },
    )
    _closed_object(
        definitions["payment_adjustment"],
        {"id", "adjustment_type", "amount_cents", "method", "currency", "cash_movement_id"},
        {"id", "adjustment_type", "amount_cents", "method", "currency", "cash_movement_id"},
    )
    forbidden = {
        "actor_user_id",
        "organization_id",
        "branch_id",
        "cash_shift_id",
        "evidence_refs",
        "before_snapshot",
        "after_snapshot",
        "payload",
    }
    assert forbidden.isdisjoint(definitions["correction"]["properties"])
    assert forbidden.isdisjoint(definitions["payment_adjustment"]["properties"])


def test_pco005b_response_schema_closes_each_production_adjustment_and_nullable_links() -> None:
    adjustment = _schema(RESPONSE)["$defs"]["production_adjustment"]
    _closed_object(
        adjustment,
        {
            "id",
            "adjustment_type",
            "source_line_id",
            "source_task_id",
            "quantity",
            "inventory_movement_id",
            "production_task_id",
        },
        {
            "id",
            "adjustment_type",
            "source_line_id",
            "source_task_id",
            "quantity",
            "inventory_movement_id",
            "production_task_id",
        },
    )
    assert adjustment["properties"]["adjustment_type"] == {
        "enum": ["RELEASE", "WASTE", "RECOVERY", "ADDITION"]
    }
    assert adjustment["properties"]["quantity"]["oneOf"] == [
        {"type": "integer", "minimum": 1},
        {"type": "string", "pattern": "^[0-9]+(?:\\.[0-9]+)?$"},
    ]
    for name in (
        "source_line_id",
        "source_task_id",
        "inventory_movement_id",
        "production_task_id",
    ):
        assert adjustment["properties"][name]["oneOf"] == [
            {"type": "null"},
            {"$ref": "#/$defs/uuid"},
        ]


def test_pco005b_reporting_summary_contract_requires_a_closed_separate_corrections_stream() -> None:
    monitor = _schema(SALES_MONITOR)
    assert monitor["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert monitor["additionalProperties"] is False
    assert "corrections" in monitor["required"]
    assert monitor["properties"]["corrections"] == {"$ref": "#/$defs/correction_summary"}
    _closed_object(
        monitor["$defs"]["correction_summary"],
        {
            "count",
            "charge_cents",
            "refund_cents",
            "net_delta_cents",
            "cash_adjustment_count",
        },
        {
            "count",
            "charge_cents",
            "refund_cents",
            "net_delta_cents",
            "cash_adjustment_count",
        },
    )
    properties = monitor["$defs"]["correction_summary"]["properties"]
    assert properties["count"] == {"type": "integer", "minimum": 0}
    assert properties["charge_cents"] == {"type": "integer", "minimum": 0}
    assert properties["refund_cents"] == {"type": "integer", "minimum": 0}
    assert properties["cash_adjustment_count"] == {"type": "integer", "minimum": 0}
    assert properties["net_delta_cents"] == {"type": "integer"}


def test_pco005b_reporting_drill_contract_requires_closed_redacted_correction_items() -> None:
    drill = _schema(SALES_DRILL_DOWN)
    assert drill["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert drill["additionalProperties"] is False
    assert "corrections" in drill["required"]
    assert drill["properties"]["corrections"] == {
        "type": "array",
        "items": {"$ref": "#/$defs/correction_item"},
    }
    item = drill["$defs"]["correction_item"]
    fields = {
        "correction_id",
        "order_id",
        "folio",
        "branch_id",
        "applied_at",
        "settlement_delta_cents",
        "currency",
        "payment_adjustment_id",
        "adjustment_type",
        "method",
        "amount_cents",
        "cash_shift_id",
        "register_id",
    }
    _closed_object(item, fields, fields)
    properties = item["properties"]
    for name in ("correction_id", "order_id", "branch_id"):
        assert properties[name] == {"type": "string", "format": "uuid"}
    assert properties["applied_at"] == {"type": "string", "format": "date-time"}
    assert properties["currency"] == {"type": "string", "pattern": "^[A-Z]{3}$"}
    assert properties["settlement_delta_cents"] == {"type": "integer"}
    assert drill["$defs"]["nullable_uuid"]["oneOf"] == [
        {"type": "null"},
        {"type": "string", "format": "uuid"},
    ]
    assert properties["payment_adjustment_id"] == {"$ref": "#/$defs/nullable_uuid"}
    assert properties["cash_shift_id"] == {"$ref": "#/$defs/nullable_uuid"}
    assert properties["adjustment_type"]["oneOf"] == [
        {"type": "null"},
        {"enum": ["CHARGE", "REFUND"]},
    ]
    assert properties["method"]["oneOf"] == [
        {"type": "null"},
        {"enum": ["cash", "debit_card", "credit_card", "transfer"]},
    ]
    assert properties["amount_cents"]["oneOf"] == [
        {"type": "null"},
        {"type": "integer", "minimum": 1},
    ]
    assert properties["register_id"] == {"$ref": "#/$defs/nullable_register_id"}
    assert {
        "actor_user_id",
        "organization_id",
        "evidence_refs",
        "before_snapshot",
        "after_snapshot",
        "payload",
    }.isdisjoint(properties)
