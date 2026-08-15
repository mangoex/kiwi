"""Strict JSON Schema contracts for PCO-006 user cash cuts."""

from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest

SCHEMA_DIR = Path(__file__).resolve().parents[3] / "packages" / "contracts" / "schemas"
NAMES = (
    "user-cash-cut-v1.schema.json",
    "user-cash-cut-create-command-v1.schema.json",
    "user-cash-cut-counted-cash-command-v1.schema.json",
    "user-cash-cut-finalize-command-v1.schema.json",
    "user-cash-cut-reopen-request-command-v1.schema.json",
    "user-cash-cut-response-v1.schema.json",
    "user-cash-cut-list-v1.schema.json",
    "user-cash-cut-detail-v1.schema.json",
    "user-cash-cut-reopen-response-v1.schema.json",
    "user-cash-cut-compensation-response-v1.schema.json",
)


def _schemas() -> dict[str, dict]:
    return {name: json.loads((SCHEMA_DIR / name).read_text()) for name in NAMES}


def test_pco006_schema_structure_is_always_strict() -> None:
    schemas = _schemas()
    assert set(schemas) == set(NAMES)
    for name, schema in schemas.items():
        assert schema["$id"].endswith(name)
        assert schema["additionalProperties"] is False
        assert "idempotency_key" not in schema.get("properties", {})
        assert "request_hash" not in schema.get("properties", {})
        assert "payload" not in schema.get("properties", {})
    assert (
        schemas["user-cash-cut-response-v1.schema.json"]["properties"]["cash_cut"]["$ref"]
        == "user-cash-cut-v1.schema.json"
    )


def test_pco006_draft_validation_requires_declared_dev_dependency() -> None:
    try:
        jsonschema = importlib.import_module("jsonschema")
        referencing = importlib.import_module("referencing")
    except ImportError:
        pytest.fail("jsonschema is declared in apps/api[dev] but unavailable locally")
    schemas = list(_schemas().values())
    registry = referencing.Registry().with_resources(
        (schema["$id"], referencing.Resource.from_contents(schema)) for schema in schemas
    )
    validators = {
        schema["$id"].rsplit("/", 1)[-1]: jsonschema.Draft202012Validator(
            schema, registry=registry, format_checker=jsonschema.FormatChecker()
        )
        for schema in schemas
    }
    validators["user-cash-cut-counted-cash-command-v1.schema.json"].validate(
        {"counted_cash_cents": 1, "version": 1}
    )
    with pytest.raises(jsonschema.ValidationError):
        validators["user-cash-cut-counted-cash-command-v1.schema.json"].validate(
            {"counted_cash_cents": True, "version": 1}
        )
    reopen = validators["user-cash-cut-reopen-request-command-v1.schema.json"]
    with pytest.raises(jsonschema.ValidationError):
        reopen.validate({"counted_cash_cents": 0, "reason": "   ", "evidence_refs": ["x"]})
    with pytest.raises(jsonschema.ValidationError):
        reopen.validate({"counted_cash_cents": 0, "reason": "ok", "evidence_refs": [" "]})
    with pytest.raises(jsonschema.ValidationError):
        reopen.validate({"counted_cash_cents": 0, "reason": "ok", "evidence_refs": ["x"] * 11})
