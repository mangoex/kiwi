from concurrent.futures import ThreadPoolExecutor

import pytest
import sqlalchemy as sa
from edge_gateway.order_outbox import OrderOutbox


def test_two_registers_serialize_acceptance_and_duplicate_replay(tmp_path):
    outbox = OrderOutbox(tmp_path / "orders.db")
    with outbox.engine.begin() as conn:
        conn.exec_driver_sql("CREATE TABLE effects (id INTEGER PRIMARY KEY)")

    def accept(index):
        key = f"register-command-{index % 2}"

        def execute(session, local, previous):
            session.execute(sa.text("INSERT INTO effects VALUES (:id)"), {"id": local})
            return {
                "command_id": key,
                "aggregate_id": key,
                "sequence": 1,
                "previous_hash": previous,
            }, {"id": key}

        return outbox.accept("actor", key, {"key": key}, execute)

    with ThreadPoolExecutor(max_workers=4) as pool:
        rows = list(pool.map(accept, range(8)))
    assert sorted({row["local_sequence"] for row in rows}) == [1, 2]
    with outbox.engine.connect() as conn:
        assert conn.scalar(sa.text("SELECT count(*) FROM effects")) == 2


def test_domain_and_outbox_rollback_together_and_replay_survives_restart(tmp_path):
    path = tmp_path / "orders.db"
    outbox = OrderOutbox(path)
    with outbox.engine.begin() as conn:
        conn.exec_driver_sql("CREATE TABLE effects (id INTEGER PRIMARY KEY)")

    def fail(session, sequence, previous):
        session.execute(sa.text("INSERT INTO effects VALUES (1)"))
        raise ValueError("domain failed")

    with pytest.raises(ValueError, match="domain failed"):
        outbox.accept("actor", "key-123456789", {"quantity": 1}, fail)
    with outbox.engine.connect() as conn:
        assert conn.scalar(sa.text("SELECT count(*) FROM effects")) == 0
    assert outbox.pending() == []

    def succeed(session, sequence, previous):
        session.execute(sa.text("INSERT INTO effects VALUES (1)"))
        assert sequence == 1
        return {
            "command_id": "cmd1",
            "aggregate_id": "order1",
            "sequence": 1,
            "previous_hash": previous,
        }, {"id": "order1"}

    first = outbox.accept("actor", "key-123456789", {"quantity": 1}, succeed)
    reopened = OrderOutbox(path)
    replay = reopened.accept("actor", "key-123456789", {"quantity": 1}, fail)
    assert replay == first
    with pytest.raises(ValueError, match="idempotency_conflict"):
        reopened.accept("actor", "key-123456789", {"quantity": 2}, fail)


def test_conflict_blocks_only_descendants_and_confirmation_is_durable(tmp_path):
    outbox = OrderOutbox(tmp_path / "orders.db")

    def accept(command, aggregate, sequence):
        return outbox.accept(
            "actor",
            command,
            {"command": command},
            lambda session, local, previous: (
                {
                    "command_id": command,
                    "aggregate_id": aggregate,
                    "sequence": sequence,
                    "previous_hash": previous,
                },
                {"id": aggregate},
            ),
            aggregate_id=aggregate,
        )

    accept("command-00001", "one", 1)
    accept("command-00002", "one", 2)
    accept("command-00003", "two", 1)
    assert [x["command_id"] for x in outbox.pending()] == ["command-00001", "command-00003"]
    outbox.resolve("command-00001", status="CONFLICT", detail="turn_closed")
    with pytest.raises(ValueError, match="offline_order_stream_conflict"):
        accept("command-00004", "one", 3)
    assert [x["command_id"] for x in outbox.pending()] == ["command-00003"]
    outbox.resolve("command-00003", status="CONFIRMED", checkpoint=7)
    assert outbox.pending() == []
    assert outbox.get("command-00003")["checkpoint"] == 7
    with pytest.raises(ValueError, match="terminal"):
        outbox.resolve("command-00003", status="CONFLICT", detail="late")
