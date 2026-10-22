"""Test-local allowlists from SDD F1-02, not runtime schemas or serializers."""

from __future__ import annotations

from typing import Any

RECEIPT_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "additionalProperties": False,
    "required": ["command_id", "resource_id", "action", "status", "version", "accepted_at",
                 "replay", "correlation_id", "schema_version", "policy_version", "projection"],
    "properties": {
        "command_id": {"type": "string", "minLength": 1},
        "resource_id": {"type": "string", "minLength": 1},
        "action": {"type": "string", "minLength": 1},
        "status": {"type": "string", "enum": ["DRAFT", "COUNTED", "FINALIZED"]},
        "version": {"type": "integer", "minimum": 1},
        "accepted_at": {"type": "string", "format": "date-time"},
        "replay": {"type": "boolean"},
        "correlation_id": {"type": "string", "minLength": 1},
        "code": {"type": "string"},
        "projection": {"const": "operational"},
        "schema_version": {"const": 2},
        "policy_version": {"type": "integer", "minimum": 1},
    },
}

REPORT_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object", "additionalProperties": False,
    "required": ["branch_id", "period", "start", "end", "timezone", "ticket_count",
                 "top_products", "schema_version", "policy_version", "projection"],
    "properties": {
        "branch_id": {"type": "string", "minLength": 1},
        "period": {"enum": ["day", "week", "month"]},
        "start": {"type": "string", "format": "date-time"},
        "end": {"type": "string", "format": "date-time"},
        "timezone": {"type": "string", "minLength": 1},
        "ticket_count": {"type": "integer", "minimum": 0},
        "projection": {"const": "operational"},
        "schema_version": {"const": 2},
        "policy_version": {"type": "integer", "minimum": 1},
        "top_products": {
            "type": "array", "maxItems": 10,
            "items": {
                "type": "object", "additionalProperties": False,
                "required": ["position", "name"],
                "properties": {
                    "position": {"type": "integer", "minimum": 1, "maximum": 10},
                    "name": {"type": "string", "minLength": 1},
                },
            },
        },
    },
}
