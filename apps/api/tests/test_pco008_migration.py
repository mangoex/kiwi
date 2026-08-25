"""TDD-TC-178 SQLite migration evidence for PCO-008."""

from __future__ import annotations

import sqlite3

import pytest
from test_cash_ledger_migration import _sqlite_alembic

REVISION_0052 = "0052_pos_handoff_and_idempotency"
REVISION_0053 = "0053_cash_offline_sync"


def test_0052_to_0053_empty_roundtrip_is_reversible(tmp_path) -> None:
    path = tmp_path / "pco008-roundtrip.db"
    assert _sqlite_alembic(path, "upgrade", REVISION_0052).returncode == 0
    assert _sqlite_alembic(path, "upgrade", REVISION_0053).returncode == 0
    assert _sqlite_alembic(path, "downgrade", REVISION_0052).returncode == 0
    assert _sqlite_alembic(path, "upgrade", REVISION_0053).returncode == 0


def test_0053_downgrade_blocks_cash_history(tmp_path) -> None:
    path = tmp_path / "pco008-history.db"
    assert _sqlite_alembic(path, "upgrade", REVISION_0053).returncode == 0
    with sqlite3.connect(path) as connection:
        connection.execute(
            """INSERT INTO sync_commands (
                id, organization_id, branch_id, source_device_id, command_id,
                idempotency_key, command_type, payload, status, checkpoint,
                occurred_at, received_at, confirmed_at
            ) VALUES (
                'cash-history', 'o1', 'b1', 'd1', 'cmd1', 'cash-history-key',
                'cash.movement.create.v1', '{}', 'CONFLICT', 1,
                '2026-08-24T00:00:00+00:00', '2026-08-24T00:00:00+00:00',
                '2026-08-24T00:00:00+00:00'
            )"""
        )
        connection.commit()
    blocked = _sqlite_alembic(path, "downgrade", REVISION_0052)
    assert blocked.returncode != 0
    assert "PCO-008 history blocks downgrade" in blocked.stderr


def test_0053_scopes_idempotency_and_command_ids_by_organization(tmp_path) -> None:
    path = tmp_path / "pco008-tenant-idempotency.db"
    assert _sqlite_alembic(path, "upgrade", REVISION_0053).returncode == 0
    with sqlite3.connect(path) as connection:
        columns = {row[1]: row for row in connection.execute("PRAGMA table_info(sync_commands)")}
        assert columns["actor_user_id"][3] == 0
        assert columns["request_hash"][3] == 0
        statement = """INSERT INTO sync_commands (
            id, organization_id, branch_id, source_device_id, command_id, idempotency_key,
            command_type, payload, status, checkpoint, occurred_at, received_at, confirmed_at
        ) VALUES (?, ?, 'b1', 'd1', ?, ?, 'legacy.command', '{}', 'CONFIRMED', 1,
            '2026-08-24T00:00:00+00:00', '2026-08-24T00:00:00+00:00',
            '2026-08-24T00:00:00+00:00')"""
        connection.execute(statement, ("a", "o1", "cmd", "shared-key"))
        connection.execute(statement, ("b", "o2", "cmd", "shared-key"))
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(statement, ("c", "o1", "other-cmd", "shared-key"))
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(statement, ("d", "o1", "cmd", "other-key"))


def test_0053_preserves_legacy_sync_command_across_roundtrip(tmp_path) -> None:
    path = tmp_path / "pco008-legacy.db"
    assert _sqlite_alembic(path, "upgrade", REVISION_0052).returncode == 0
    legacy = (
        "legacy-id",
        "o1",
        "b1",
        "d1",
        "legacy-command",
        "legacy-idempotency-key",
        "local_order.closed",
        '{"order_id":"legacy-order"}',
        "CONFIRMED",
        7,
        "2026-08-24T00:00:00+00:00",
        "2026-08-24T00:01:00+00:00",
        "2026-08-24T00:02:00+00:00",
    )
    columns = (
        "id, organization_id, branch_id, source_device_id, command_id, idempotency_key, "
        "command_type, payload, status, checkpoint, occurred_at, received_at, confirmed_at"
    )
    placeholders = ", ".join("?" for _ in legacy)
    with sqlite3.connect(path) as connection:
        connection.execute(f"INSERT INTO sync_commands ({columns}) VALUES ({placeholders})", legacy)
        connection.commit()

    assert _sqlite_alembic(path, "upgrade", REVISION_0053).returncode == 0
    with sqlite3.connect(path) as connection:
        assert connection.execute(
            f"SELECT {columns}, actor_user_id, request_hash FROM sync_commands "
            "WHERE id = 'legacy-id'"
        ).fetchone() == (*legacy, None, None)

    assert _sqlite_alembic(path, "downgrade", REVISION_0052).returncode == 0
    with sqlite3.connect(path) as connection:
        assert (
            connection.execute(
                f"SELECT {columns} FROM sync_commands WHERE id = 'legacy-id'"
            ).fetchone()
            == legacy
        )
