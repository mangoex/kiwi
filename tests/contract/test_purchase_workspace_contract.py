from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator


def test_online_capture_contract_is_separate_from_offline_envelope() -> None:
    root = Path(__file__).resolve().parents[2] / "packages/contracts/schemas"
    http = json.loads((root / "purchase-create-http-v1.schema.json").read_text())
    offline = json.loads((root / "purchase-command.schema.json").read_text())
    assert http["additionalProperties"] is False
    assert "command_id" not in http["properties"]
    assert "command_id" in offline["$defs"]["create"]["required"]
    assert http["properties"]["lines"]["maxItems"] == 200
    assert "unit_price" in http["$defs"]["line"]["required"]
    assert {option["format"] for option in http["properties"]["document_date"]["oneOf"]} == {
        "date",
        "date-time",
    }
    assert http["properties"]["notes"]["maxLength"] == 600
    assert http["properties"]["supplier_catalog_exception"]["type"] == "boolean"
    assert http["properties"]["supplier_catalog_exception_reason"]["maxLength"] == 240
    assert "supplier_catalog_exception" not in http["required"]


@pytest.mark.parametrize(
    "method,paid,valid",
    [
        ("cash", True, True),
        ("card", False, True),
        ("transfer", False, True),
        ("other", False, True),
        ("cash", False, False),
        ("transfer", True, False),
        ("credit", False, False),
        ("unknown", False, False),
    ],
)
def test_capture_schema_closes_payment_methods_and_derives_cash(method, paid, valid):
    root = Path(__file__).resolve().parents[2] / "packages/contracts/schemas"
    schema = json.loads((root / "purchase-create-http-v1.schema.json").read_text())
    payload = {
        "branch_id": "018f6f73-2d0a-74f0-8f1c-000000000003",
        "supplier_id": "018f6f73-2d0a-74f0-8f1c-000000000003",
        "document_type": "note",
        "folio": "Contract",
        "document_date": "2026-10-09",
        "payment_method": method,
        "paid_from_cash": paid,
        "lines": [
            {
                "presentation_id": "018f6f73-2d0a-74f0-8f1c-000000000003",
                "quantity": "1",
                "unit_price": "0",
                "discount": "0",
                "tax": "0",
            }
        ],
    }
    validator = Draft202012Validator(schema, format_checker=Draft202012Validator.FORMAT_CHECKER)
    assert validator.is_valid(payload) is valid


@pytest.mark.parametrize(
    "patch,valid",
    [
        ({}, True),
        (
            {
                "register_id": "CAJA-01",
                "expected_cash_shift_id": "018f6f73-2d0a-74f0-8f1c-000000000003",
            },
            True,
        ),
        ({"register_id": "CAJA-01"}, False),
        ({"expected_cash_shift_id": "018f6f73-2d0a-74f0-8f1c-000000000003"}, False),
        (
            {"register_id": " ", "expected_cash_shift_id": "018f6f73-2d0a-74f0-8f1c-000000000003"},
            False,
        ),
        ({"expected_cash_shift_id": "invalid", "register_id": "CAJA-01"}, False),
        ({"total": 300}, False),
    ],
)
def test_reviewed_confirmation_schema_requires_exact_paired_cash_context(patch, valid):
    root = Path(__file__).resolve().parents[2] / "packages/contracts/schemas"
    schema = json.loads((root / "purchase-confirm-http-v1.schema.json").read_text())
    validator = Draft202012Validator(schema, format_checker=Draft202012Validator.FORMAT_CHECKER)
    assert (
        validator.is_valid({"branch_id": "018f6f73-2d0a-74f0-8f1c-000000000003", **patch}) is valid
    )


def test_purchase_cash_context_contract_is_minimal_and_validates_identity():
    root = Path(__file__).resolve().parents[2] / "packages/contracts/schemas"
    schema = json.loads((root / "purchase-cash-context-v1.schema.json").read_text())
    validator = Draft202012Validator(schema, format_checker=Draft202012Validator.FORMAT_CHECKER)
    payload = {
        "branch_id": "018f6f73-2d0a-74f0-8f1c-000000000003",
        "open_registers": [
            {
                "register_id": "CAJA-01",
                "cash_shift_id": "018f6f73-2d0a-74f0-8f1c-000000000004",
                "opened_at": "2026-10-09T12:00:00Z",
            }
        ],
    }
    assert validator.is_valid(payload)
    assert validator.is_valid({**payload, "open_registers": []})
    assert not validator.is_valid({**payload, "expected_cash_cents": 200000})
    for patch in ({"cash_shift_id": "invalid"}, {"opened_at": "2026-10-09"}, {"balance": 100}):
        assert not validator.is_valid(
            {**payload, "open_registers": [{**payload["open_registers"][0], **patch}]}
        )
