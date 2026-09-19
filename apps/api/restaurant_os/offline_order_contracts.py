"""Strict ORD-OFF001 envelopes; clients carry intent, never computed facts."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any
from uuid import UUID

from restaurant_os.operations import BusinessError

SCHEMA = "ord-off/v1"
COMMAND_TYPES = {"create", "pay", "kds_transition", "amend", "cancel", "fulfill"}
COMPUTED_FIELDS = {
    "total_cents",
    "price_cents",
    "cost",
    "costs",
    "balance",
    "snapshot",
    "result",
    "organization_id",
    "branch_id",
}


def canonical_envelope(envelope: dict[str, Any], *, include_signature: bool = False) -> bytes:
    value = dict(envelope)
    if not include_signature:
        value.pop("device_signature", None)
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def command_hash(envelope: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_envelope(envelope)).hexdigest()


def intention_hash(envelope: dict[str, Any]) -> str:
    value = dict(envelope)
    value.pop("device_signature", None)
    value.pop("accepted_at", None)
    return hashlib.sha256(canonical_envelope(value)).hexdigest()


def validate_envelope(envelope: dict[str, Any]) -> dict[str, Any]:
    required = {
        "schema_version",
        "command_id",
        "command_type",
        "idempotency_key",
        "aggregate_id",
        "sequence",
        "previous_hash",
        "organization_id",
        "branch_id",
        "device_id",
        "actor_id",
        "accepted_at",
        "grant",
        "bundle_id",
        "bundle_hash",
        "lease_epoch",
        "local_sequence",
        "payload",
        "device_signature",
    }
    if (
        not isinstance(envelope, dict)
        or set(envelope) != required
        or envelope.get("schema_version") != SCHEMA
    ):
        raise BusinessError("offline_order_envelope_invalid", "Offline order envelope is invalid")
    if (
        not isinstance(envelope["command_type"], str)
        or envelope["command_type"] not in COMMAND_TYPES
        or not isinstance(envelope["payload"], dict)
    ):
        raise BusinessError("offline_order_envelope_invalid", "Offline order command is invalid")
    try:
        for field in ("command_id", "aggregate_id", "bundle_id"):
            if (
                not isinstance(envelope[field], str)
                or str(UUID(envelope[field])) != envelope[field]
            ):
                raise ValueError(field)
        accepted = datetime.fromisoformat(str(envelope["accepted_at"]).replace("Z", "+00:00"))
    except ValueError as exc:
        raise BusinessError(
            "offline_order_envelope_invalid", "Offline order identity is invalid"
        ) from exc
    integer_fields = ("sequence", "lease_epoch", "local_sequence")
    if (
        accepted.tzinfo is None
        or any(
            isinstance(envelope[field], bool)
            or not isinstance(envelope[field], int)
            or envelope[field] < 1
            for field in integer_fields
        )
        or not isinstance(envelope["idempotency_key"], str)
        or not 12 <= len(envelope["idempotency_key"]) <= 160
        or not isinstance(envelope["bundle_hash"], str)
        or len(envelope["bundle_hash"]) != 64
        or any(character not in "0123456789abcdef" for character in envelope["bundle_hash"])
        or not isinstance(envelope["previous_hash"], (str, type(None)))
        or (
            isinstance(envelope["previous_hash"], str)
            and (
                len(envelope["previous_hash"]) != 64
                or any(
                    character not in "0123456789abcdef" for character in envelope["previous_hash"]
                )
            )
        )
        or not all(
            isinstance(envelope[field], str) and envelope[field]
            for field in (
                "organization_id",
                "branch_id",
                "device_id",
                "actor_id",
                "grant",
                "device_signature",
            )
        )
    ):
        raise BusinessError("offline_order_envelope_invalid", "Offline order sequence is invalid")
    if _contains_computed_field(envelope["payload"]):
        raise BusinessError("offline_order_payload_invalid", "Computed fields are not accepted")
    return dict(envelope)


def _contains_computed_field(value: Any) -> bool:
    if isinstance(value, dict):
        return any(
            key in COMPUTED_FIELDS or _contains_computed_field(item) for key, item in value.items()
        )
    if isinstance(value, list):
        return any(_contains_computed_field(item) for item in value)
    return False
