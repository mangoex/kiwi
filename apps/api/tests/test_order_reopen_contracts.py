"""PCO-005A JSON Schema contracts are strict and resolve local references."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from restaurant_os.operations import (
    create_order_reopen_request,
    decide_order_reopen_request,
    list_order_accounts,
    list_order_reopen_requests,
)
from test_cash_concepts import OWNER_ID
from test_order_reopen_workflow import CHIEF_ID, _actors, _new_session, _order

jsonschema = pytest.importorskip("jsonschema")

SCHEMA_DIR = Path(__file__).resolve().parents[3] / "packages" / "contracts" / "schemas"
NAMES = (
    "order-account-list-v1.schema.json",
    "order-reopen-request-command-v1.schema.json",
    "order-reopen-request-v1.schema.json",
    "order-reopen-request-list-v1.schema.json",
    "order-reopen-decision-command-v1.schema.json",
)


def test_pco005_schemas_are_strict_and_validate_examples():
    schemas = {name: json.loads((SCHEMA_DIR / name).read_text()) for name in NAMES}
    for schema in schemas.values():
        jsonschema.Draft202012Validator.check_schema(schema)
    request = {
        "id": "request-1",
        "organization_id": "org-1",
        "branch_id": "branch-1",
        "order_id": "order-1",
        "status": "REQUESTED",
        "order_version_snapshot": 1,
        "order_status_snapshot": "CLOSED",
        "requested_by_user_id": "user-1",
        "requested_at": "2026-08-13T00:00:00+00:00",
        "reason": "Corrección solicitada por cliente",
        "evidence_refs": ["ticket:1"],
        "decided_by_user_id": None,
        "decided_at": None,
        "decision_reason": None,
        "created_at": "2026-08-13T00:00:00+00:00",
        "updated_at": "2026-08-13T00:00:00+00:00",
    }
    validators = {
        name: jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker())
        for name, schema in schemas.items()
    }
    validators["order-reopen-request-command-v1.schema.json"].validate(
        {"reason": "Corrección solicitada por cliente", "evidence_refs": ["ticket:1"]}
    )
    validators["order-reopen-decision-command-v1.schema.json"].validate(
        {"decision_reason": "Autoriza revisión documentada"}
    )
    validators["order-reopen-request-v1.schema.json"].validate(request)
    validators["order-reopen-request-list-v1.schema.json"].validate(
        {"items": [request], "next_cursor": None}
    )
    validators["order-account-list-v1.schema.json"].validate({"items": [], "next_cursor": None})
    with pytest.raises(jsonschema.ValidationError):
        validators["order-reopen-request-command-v1.schema.json"].validate(
            {
                "reason": "Corrección solicitada por cliente",
                "evidence_refs": ["ticket:1"],
                "actor": "forbidden",
            }
        )


def _json_value(value):
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _json_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_value(item) for item in value]
    return value


def test_pco005_contracts_validate_real_operation_responses():
    engine, session = _new_session()
    try:
        _actors(session)
        order_id = _order(session)
        schemas = {name: json.loads((SCHEMA_DIR / name).read_text()) for name in NAMES}
        validators = {
            name: jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker())
            for name, schema in schemas.items()
        }
        accounts = list_order_accounts(session, {"limit": 1}, CHIEF_ID)
        validators["order-account-list-v1.schema.json"].validate(_json_value(accounts))
        payload = {"reason": "Corrección solicitada por cliente", "evidence_refs": ["ticket:001"]}
        request = create_order_reopen_request(
            session, order_id, payload, "contract-key-001", CHIEF_ID
        )
        validators["order-reopen-request-v1.schema.json"].validate(_json_value(request))
        listing = list_order_reopen_requests(session, {"limit": 1}, OWNER_ID)
        validators["order-reopen-request-list-v1.schema.json"].validate(_json_value(listing))
        decision = decide_order_reopen_request(
            session,
            request["id"],
            "APPROVED",
            {"decision_reason": "Autoriza revisión documentada"},
            "contract-key-002",
            OWNER_ID,
        )
        validators["order-reopen-request-v1.schema.json"].validate(_json_value(decision))
    finally:
        session.close()
        engine.dispose()
