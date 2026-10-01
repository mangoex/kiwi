"""Durable creation schema roundtrip and history protection on SQLite."""

import sqlite3

from test_cash_ledger_migration import _sqlite_alembic

REVISION = "0072_purchase_create_commands"
PREVIOUS = "0071_classification_rollout"


def test_purchase_creation_migration_roundtrip_and_history_guard(tmp_path):
    path = tmp_path / "purchase-create.db"
    upgraded = _sqlite_alembic(path, "upgrade", REVISION)
    assert upgraded.returncode == 0, upgraded.stdout + upgraded.stderr
    assert _sqlite_alembic(path, "downgrade", PREVIOUS).returncode == 0
    assert _sqlite_alembic(path, "upgrade", REVISION).returncode == 0
    with sqlite3.connect(path) as connection:
        connection.execute(
            "INSERT INTO purchase_create_commands "
            "(id, organization_id, branch_id, actor_user_id, idempotency_key, "
            "request_hash, purchase_id, result, created_at) VALUES "
            "('command', 'org', 'branch', 'actor', 'key', 'hash', 'purchase', '{}', '2026-09-30')"
        )
    blocked = _sqlite_alembic(path, "downgrade", PREVIOUS)
    assert blocked.returncode != 0
    assert (
        "Cannot downgrade 0072 while purchase creation history exists"
        in blocked.stdout + blocked.stderr
    )
