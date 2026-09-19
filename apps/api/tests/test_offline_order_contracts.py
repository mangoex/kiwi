from __future__ import annotations

from uuid import uuid4

import pytest
from restaurant_os.offline_order_contracts import command_hash, validate_envelope
from restaurant_os.operations import BusinessError


def _envelope() -> dict[str, object]:
    return {
        "schema_version": "ord-off/v1",
        "command_id": str(uuid4()),
        "command_type": "create",
        "idempotency_key": "offline-order-command-001",
        "aggregate_id": str(uuid4()),
        "sequence": 1,
        "previous_hash": None,
        "organization_id": str(uuid4()),
        "branch_id": str(uuid4()),
        "device_id": str(uuid4()),
        "actor_id": str(uuid4()),
        "accepted_at": "2026-09-19T00:00:00+00:00",
        "grant": "synthetic-grant",
        "bundle_id": str(uuid4()),
        "bundle_hash": "a" * 64,
        "lease_epoch": 1,
        "local_sequence": 1,
        "payload": {"lines": [{"product_id": str(uuid4()), "quantity": 1}]},
        "device_signature": "synthetic-signature",
    }


def test_offline_order_envelope_is_strict_and_hash_excludes_signature() -> None:
    envelope = _envelope()
    assert validate_envelope(envelope) == envelope
    first = command_hash(envelope)
    envelope["device_signature"] = "other"
    assert command_hash(envelope) == first
    envelope["payload"] = {"total_cents": 1}
    with pytest.raises(BusinessError, match="Computed"):
        validate_envelope(envelope)


@pytest.mark.parametrize(
    "field,value",
    [("command_type", []), ("sequence", "1"), ("bundle_hash", "short")],
)
def test_malformed_envelope_never_raises_type_or_key_errors(field: str, value: object) -> None:
    envelope = _envelope()
    envelope[field] = value
    with pytest.raises(BusinessError):
        validate_envelope(envelope)
