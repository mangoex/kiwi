from edge_gateway.order_outbox import OrderOutbox
from edge_gateway.order_sync import OrderSyncWorker


def test_lost_ack_retries_identical_envelope_after_restart(tmp_path):
    outbox = OrderOutbox(tmp_path / "orders.db")
    outbox.accept(
        "actor",
        "command-key-001",
        {"quantity": 1},
        lambda session, local, previous: (
            {
                "command_id": "command1",
                "aggregate_id": "order1",
                "sequence": 1,
                "previous_hash": None,
                "device_signature": "signature",
            },
            {"id": "order1"},
        ),
    )
    received = []

    def send(envelope):
        received.append(envelope)
        if len(received) == 1:
            raise ConnectionError("response lost")
        return {"command_id": "command1", "status": "confirmed", "checkpoint": 8}

    worker = OrderSyncWorker(outbox, send)
    assert worker.reconcile_once(now="2026-09-19T12:00:00+00:00") == []
    assert outbox.get("command1")["status"] == "PENDING_SYNC"
    restarted = OrderSyncWorker(OrderOutbox(tmp_path / "orders.db"), send)
    assert restarted.reconcile_once(now="2026-09-19T12:00:04+00:00") == []
    assert restarted.reconcile_once(now="2026-09-19T12:00:06+00:00")[0]["status"] == "CONFIRMED"
    assert received[0] == received[1]


def test_wrong_ack_never_confirms(tmp_path):
    outbox = OrderOutbox(tmp_path / "orders.db")
    outbox.accept(
        "actor",
        "command-key-001",
        {},
        lambda session, local, previous: (
            {
                "command_id": "command1",
                "aggregate_id": "order1",
                "sequence": 1,
                "previous_hash": None,
            },
            {},
        ),
    )
    worker = OrderSyncWorker(
        outbox, lambda envelope: {"command_id": "other", "status": "confirmed", "checkpoint": 1}
    )
    assert worker.reconcile_once() == []
    assert outbox.get("command1")["status"] == "PENDING_SYNC"
