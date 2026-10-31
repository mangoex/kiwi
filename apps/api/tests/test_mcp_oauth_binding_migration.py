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
REVISION = "0105_mcp_oauth_bindings"
PARENT_REVISION = "0104_purchase_draft_edits"


def test_tdd_tc_495_oauth_binding_migration_roundtrip_and_history_guard(tmp_path: Path) -> None:
    database_path = tmp_path / "mcp-oauth-binding.db"
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

    upgraded = alembic("upgrade", REVISION)
    assert upgraded.returncode == 0, upgraded.stdout + upgraded.stderr
    with sqlite3.connect(database_path) as connection:
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(external_agent_oauth_bindings)")
        }
    assert columns == {
        "identity_id",
        "organization_id",
        "issuer",
        "subject",
        "oauth_client_id",
        "created_by_user_id",
        "created_at",
        "updated_at",
    }

    downgraded = alembic("downgrade", PARENT_REVISION)
    assert downgraded.returncode == 0, downgraded.stdout + downgraded.stderr
    with sqlite3.connect(database_path) as connection:
        tables = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
    assert "external_agent_oauth_bindings" not in tables

    upgraded_again = alembic("upgrade", REVISION)
    assert upgraded_again.returncode == 0, upgraded_again.stdout + upgraded_again.stderr
    with sqlite3.connect(database_path) as connection:
        organization_id = connection.execute("SELECT id FROM organizations LIMIT 1").fetchone()[0]
        user_id = connection.execute("SELECT id FROM users LIMIT 1").fetchone()[0]
        connection.execute(
            "INSERT INTO external_agent_integrations "
            "(id, organization_id, provider, display_name, is_enabled, state, created_by_user_id, "
            "created_at, updated_at) VALUES (?, ?, 'GROKBOT', 'Administrador Kiwi', 0, "
            "'DISCONNECTED', ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)",
            ("migration-workos-integration", organization_id, user_id),
        )
        connection.execute(
            "INSERT INTO external_agent_identities "
            "(id, organization_id, integration_id, profile, is_enabled, corporate_scope, "
            "authorization_version, capabilities, created_at, updated_at) VALUES "
            "(?, ?, ?, 'administrator', 0, 0, 1, '[]', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)",
            ("migration-workos-identity", organization_id, "migration-workos-integration"),
        )
        connection.execute(
            "INSERT INTO external_agent_oauth_bindings "
            "(identity_id, organization_id, issuer, subject, oauth_client_id, created_by_user_id, "
            "created_at, updated_at) VALUES "
            "(?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)",
            (
                "migration-workos-identity",
                organization_id,
                "https://auth.example.com",
                "user_migration_workos",
                "client_migration_workos",
                user_id,
            ),
        )
        connection.commit()

    blocked = alembic("downgrade", PARENT_REVISION)
    assert blocked.returncode != 0
    assert "0105 downgrade blocked: OAuth identity bindings exist" in (
        blocked.stdout + blocked.stderr
    )


def test_tdd_tc_495_oauth_binding_migration_roundtrip_on_postgres() -> None:
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
        env = {**os.environ, "RESTAURANTOS_DATABASE_URL": url}

        def alembic(*arguments: str) -> subprocess.CompletedProcess[str]:
            return subprocess.run(
                [sys.executable, "-m", "alembic", "-c", "alembic.ini", *arguments],
                cwd=ROOT / "apps" / "api",
                env=env,
                capture_output=True,
                text=True,
            )

        upgraded = alembic("upgrade", REVISION)
        assert upgraded.returncode == 0, upgraded.stdout + upgraded.stderr
        assert "external_agent_oauth_bindings" in sa.inspect(engine).get_table_names()
        downgraded = alembic("downgrade", PARENT_REVISION)
        assert downgraded.returncode == 0, downgraded.stdout + downgraded.stderr
        assert "external_agent_oauth_bindings" not in sa.inspect(engine).get_table_names()
    finally:
        engine.dispose()
