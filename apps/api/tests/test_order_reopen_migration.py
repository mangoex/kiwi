"""PCO-005A migration roundtrip on isolated SQLite only."""

import sqlite3
from pathlib import Path

from test_cash_ledger_migration import _sqlite_alembic


def test_sqlite_migrates_0038_to_0039_roundtrip(tmp_path: Path):
    path = tmp_path / "pco005.db"
    assert (
        _sqlite_alembic(path, "upgrade", "0038_cash_shift_closures_sales_monitor").returncode == 0
    )
    assert _sqlite_alembic(path, "upgrade", "0039_order_reopen_requests").returncode == 0
    assert (
        _sqlite_alembic(path, "downgrade", "0038_cash_shift_closures_sales_monitor").returncode == 0
    )
    assert _sqlite_alembic(path, "upgrade", "0039_order_reopen_requests").returncode == 0


def test_sqlite_downgrade_is_blocked_after_pco005_history(tmp_path: Path):
    path = tmp_path / "pco005-history.db"
    assert _sqlite_alembic(path, "upgrade", "0039_order_reopen_requests").returncode == 0
    connection = sqlite3.connect(path)
    try:
        connection.execute(
            """
            INSERT INTO order_reopen_requests (
                id, organization_id, branch_id, order_id, status, order_version_snapshot,
                order_status_snapshot, before_snapshot, reason, evidence_refs,
                requested_by_user_id, requested_at, created_at, updated_at
            ) VALUES (?, ?, ?, ?, 'REQUESTED', 1, 'CLOSED', '{}', 'Motivo válido',
                      '["ticket:1"]', ?, '2026-08-13T00:00:00+00:00',
                      '2026-08-13T00:00:00+00:00', '2026-08-13T00:00:00+00:00')
            """,
            ("request-1", "org-1", "branch-1", "order-1", "user-1"),
        )
        connection.commit()
    finally:
        connection.close()
    blocked = _sqlite_alembic(path, "downgrade", "0038_cash_shift_closures_sales_monitor")
    assert blocked.returncode != 0
    assert "PCO-005A history" in blocked.stderr


def test_sqlite_downgrade_is_blocked_after_pco005_command_history(tmp_path: Path):
    path = tmp_path / "pco005-command-history.db"
    assert _sqlite_alembic(path, "upgrade", "0039_order_reopen_requests").returncode == 0
    connection = sqlite3.connect(path)
    try:
        connection.execute(
            """
            INSERT INTO order_reopen_commands (
                id, organization_id, request_id, order_id, command_type, idempotency_key,
                request_hash, status, response_snapshot, actor_user_id, created_at
            ) VALUES (?, ?, NULL, ?, 'request', 'command-key-001',
                      'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
                      'completed', '{}', ?, '2026-08-13T00:00:00+00:00')
            """,
            ("command-1", "org-1", "order-1", "user-1"),
        )
        connection.commit()
    finally:
        connection.close()
    blocked = _sqlite_alembic(path, "downgrade", "0038_cash_shift_closures_sales_monitor")
    assert blocked.returncode != 0
    assert "PCO-005A history" in blocked.stderr
