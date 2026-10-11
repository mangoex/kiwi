from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

import pytest
import sqlalchemy as sa

ROOT = Path(__file__).resolve().parents[3]
INDEX_REVISION = "0079_agent_inventory_movement_index"
INDEX_NAME = "ix_inventory_movements_org_branch_effective_id"
INDEX_MIGRATION = (
    ROOT
    / "apps"
    / "api"
    / "alembic"
    / "versions"
    / "202610111000_0079_agent_inventory_movement_index.py"
)


def test_grokbot_agent_tools_migration_roundtrip_and_history_guard(tmp_path: Path) -> None:
    database_path = tmp_path / "grokbot-agent-tools.db"
    env = {
        **os.environ,
        "RESTAURANTOS_DATABASE_URL": f"sqlite+pysqlite:///{database_path}",
    }

    def alembic(*arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "alembic", "-c", "alembic.ini", *arguments],
            cwd=ROOT / "apps" / "api",
            env=env,
            capture_output=True,
            text=True,
        )

    upgraded = alembic("upgrade", "0078_grokbot_agent_tools")
    assert upgraded.returncode == 0, upgraded.stdout + upgraded.stderr
    connection = sqlite3.connect(database_path)
    try:
        tables = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
        assert {
            "external_agent_integrations",
            "external_agent_identities",
            "external_agent_identity_branches",
            "external_agent_credentials",
            "external_agent_commands",
            "external_agent_callback_outbox",
        } <= tables
        assert {row[1] for row in connection.execute("PRAGMA table_info(admin_ai_proposals)")} >= {
            "actor_agent_identity_id",
            "origin",
        }
        assert {row[1] for row in connection.execute("PRAGMA table_info(purchase_documents)")} >= {
            "created_by_agent_identity_id",
            "origin",
        }
    finally:
        connection.close()

    downgraded = alembic("downgrade", "0077_pos_branch_selection")
    assert downgraded.returncode == 0, downgraded.stdout + downgraded.stderr
    upgraded_again = alembic("upgrade", "0078_grokbot_agent_tools")
    assert upgraded_again.returncode == 0, upgraded_again.stdout + upgraded_again.stderr

    connection = sqlite3.connect(database_path)
    try:
        organization_id = connection.execute("SELECT id FROM organizations LIMIT 1").fetchone()[0]
        user_id = connection.execute("SELECT id FROM users LIMIT 1").fetchone()[0]
        branch_id = connection.execute("SELECT id FROM branches LIMIT 1").fetchone()[0]
        connection.execute(
            "INSERT INTO external_agent_integrations "
            "(id, organization_id, provider, display_name, is_enabled, state, created_by_user_id, "
            "created_at, updated_at) VALUES (?, ?, 'GROKBOT', 'Administrador Kiwi', 0, "
            "'DISCONNECTED', ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)",
            ("migration-agent-integration", organization_id, user_id),
        )
        connection.execute(
            "INSERT INTO external_agent_identities "
            "(id, organization_id, integration_id, profile, is_enabled, corporate_scope, "
            "authorization_version, capabilities, created_at, updated_at) VALUES "
            "(?, ?, ?, 'inventory', 0, 0, 1, '[]', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)",
            ("migration-agent-identity", organization_id, "migration-agent-integration"),
        )
        connection.execute(
            "INSERT INTO external_agent_commands "
            "(id, organization_id, integration_id, identity_id, branch_id, operation_type, "
            "idempotency_key, request_hash, status, result, created_at, updated_at) VALUES "
            "(?, ?, ?, ?, ?, 'inventory_item_proposal', 'migration-agent-command', ?, "
            "'READY_FOR_REVIEW', '{}', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)",
            (
                "migration-agent-command",
                organization_id,
                "migration-agent-integration",
                "migration-agent-identity",
                branch_id,
                "0" * 64,
            ),
        )
        connection.commit()
    finally:
        connection.close()

    blocked = alembic("downgrade", "0077_pos_branch_selection")
    assert blocked.returncode != 0
    assert "0078 downgrade blocked: external agent command history exists" in (
        blocked.stdout + blocked.stderr
    )


def test_agent_inventory_movement_index_roundtrip_on_sqlite(tmp_path: Path) -> None:
    database_path = tmp_path / "grokbot-movement-index.db"
    env = {
        **os.environ,
        "RESTAURANTOS_DATABASE_URL": f"sqlite+pysqlite:///{database_path}",
    }

    def alembic(*arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "alembic", "-c", "alembic.ini", *arguments],
            cwd=ROOT / "apps" / "api",
            env=env,
            capture_output=True,
            text=True,
        )

    upgraded = alembic("upgrade", INDEX_REVISION)
    assert upgraded.returncode == 0, upgraded.stdout + upgraded.stderr
    with sqlite3.connect(database_path) as connection:
        indexes = {row[1] for row in connection.execute("PRAGMA index_list(inventory_movements)")}
        columns = [row[2] for row in connection.execute(f'PRAGMA index_info("{INDEX_NAME}")')]
    assert INDEX_NAME in indexes
    assert columns == ["organization_id", "branch_id", "effective_at", "id"]

    downgraded = alembic("downgrade", "0078_grokbot_agent_tools")
    assert downgraded.returncode == 0, downgraded.stdout + downgraded.stderr
    with sqlite3.connect(database_path) as connection:
        indexes = {row[1] for row in connection.execute("PRAGMA index_list(inventory_movements)")}
    assert INDEX_NAME not in indexes


def test_agent_inventory_movement_index_keeps_postgres_concurrent_ddl() -> None:
    source = INDEX_MIGRATION.read_text(encoding="utf-8")
    assert source.count("autocommit_block()") == 2
    assert source.count("postgresql_concurrently=True") == 2


def test_agent_inventory_movement_index_roundtrip_on_postgres() -> None:
    url = os.environ.get("GROKBOT_TEST_POSTGRES_URL")
    if not url:
        pytest.skip("GROKBOT_TEST_POSTGRES_URL is required")
    parsed = urlparse(url)
    database = parsed.path.lstrip("/")
    assert parsed.hostname in {"127.0.0.1", "localhost"}
    assert database.startswith("grokbot_")

    engine = sa.create_engine(url)
    try:
        with engine.begin() as connection:
            connection.execute(sa.text("DROP SCHEMA public CASCADE"))
            connection.execute(sa.text("CREATE SCHEMA public"))
    finally:
        engine.dispose()

    env = {**os.environ, "RESTAURANTOS_DATABASE_URL": url}
    env.pop("DATABASE_URL", None)

    def alembic(*arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "alembic", "-c", "alembic.ini", *arguments],
            cwd=ROOT / "apps" / "api",
            env=env,
            capture_output=True,
            text=True,
        )

    upgraded = alembic("upgrade", INDEX_REVISION)
    assert upgraded.returncode == 0, upgraded.stdout + upgraded.stderr
    engine = sa.create_engine(url)
    try:
        with engine.connect() as connection:
            columns = (
                connection.execute(
                    sa.text(
                        "SELECT a.attname FROM pg_class i "
                        "JOIN pg_index x ON x.indexrelid = i.oid "
                        "JOIN pg_class t ON t.oid = x.indrelid "
                        "JOIN unnest(x.indkey) WITH ORDINALITY AS k(attnum, ord) ON TRUE "
                        "JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = k.attnum "
                        "WHERE i.relname = :index_name ORDER BY k.ord"
                    ),
                    {"index_name": INDEX_NAME},
                )
                .scalars()
                .all()
            )
        assert columns == ["organization_id", "branch_id", "effective_at", "id"]
    finally:
        engine.dispose()

    downgraded = alembic("downgrade", "0078_grokbot_agent_tools")
    assert downgraded.returncode == 0, downgraded.stdout + downgraded.stderr
    engine = sa.create_engine(url)
    try:
        with engine.connect() as connection:
            assert (
                connection.scalar(
                    sa.text("SELECT to_regclass(:index_name)"),
                    {"index_name": INDEX_NAME},
                )
                is None
            )
    finally:
        engine.dispose()
