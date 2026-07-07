import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "apps" / "edge-gateway"))

from edge_gateway import GatewayOutbox, InvalidCommandEnvelope  # noqa: E402


def test_gateway_outbox_uses_sqlite_wal(tmp_path: Path) -> None:
    outbox = GatewayOutbox(tmp_path / "gateway.db")

    assert outbox.journal_mode() == "wal"


def test_gateway_outbox_persists_pending_command_idempotently(tmp_path: Path) -> None:
    outbox = GatewayOutbox(tmp_path / "gateway.db")
    command = _command()

    first = outbox.enqueue_command(command)
    second = outbox.enqueue_command(command)

    assert first["id"] == second["id"]
    assert first["status"] == "PENDING"
    assert first["payload"] == {"folio": "PILOTO-LOCAL-000001", "total_cents": 9500}
    assert len(outbox.list_pending_commands()) == 1


def test_gateway_outbox_marks_command_confirmed_with_checkpoint(tmp_path: Path) -> None:
    outbox = GatewayOutbox(tmp_path / "gateway.db")
    command = _command()
    outbox.enqueue_command(command)

    confirmed = outbox.mark_confirmed(command["idempotency_key"], checkpoint=7)

    assert confirmed["status"] == "CONFIRMED"
    assert confirmed["confirmed_checkpoint"] == 7
    assert outbox.list_pending_commands() == []
    assert outbox.get_sync_state(command["branch_id"])["last_checkpoint"] == 7


def test_gateway_outbox_rejects_invalid_command(tmp_path: Path) -> None:
    outbox = GatewayOutbox(tmp_path / "gateway.db")

    with pytest.raises(InvalidCommandEnvelope):
        outbox.enqueue_command({"schema_version": "1.0", "payload": {}})


def _command() -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "command_id": "018f6f73-2d0a-74f0-8f1c-000000001201",
        "idempotency_key": "PILOTO-CAJA-01-LOCAL-000001",
        "organization_id": "018f6f73-2d0a-74f0-8f1c-000000000001",
        "branch_id": "018f6f73-2d0a-74f0-8f1c-000000000003",
        "source_device_id": "018f6f73-2d0a-74f0-8f1c-000000000401",
        "command_type": "local_order.closed",
        "occurred_at": "2026-07-07T18:00:00Z",
        "payload": {"folio": "PILOTO-LOCAL-000001", "total_cents": 9500},
    }
