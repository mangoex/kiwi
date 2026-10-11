from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


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
