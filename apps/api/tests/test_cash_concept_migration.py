from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
API_DIR = ROOT / "apps" / "api"


def test_cash_concept_migration_is_linear_and_empty_round_trip_is_reversible(  # noqa: E501
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "cash-concepts.db"
    env = {
        **os.environ,
        "RESTAURANTOS_DATABASE_URL": f"sqlite+pysqlite:///{database_path}",
    }

    def alembic(*arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "alembic", "-c", "alembic.ini", *arguments],
            cwd=API_DIR,
            env=env,
            capture_output=True,
            text=True,
        )

    upgraded_0035 = alembic("upgrade", "0035_cumulative_profiles_rbac")
    assert upgraded_0035.returncode == 0, upgraded_0035.stderr
    connection = sqlite3.connect(database_path)
    try:
        legacy_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(cash_movements)")
        }
    finally:
        connection.close()

    upgraded_0036 = alembic("upgrade", "0036_cash_concepts")
    assert upgraded_0036.returncode == 0, upgraded_0036.stderr
    connection = sqlite3.connect(database_path)
    try:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        assert {
            "cash_movement_concepts",
            "cash_movement_concept_versions",
            "cash_concept_commands",
        } <= tables
        assert {
            row[1] for row in connection.execute("PRAGMA table_info(cash_movements)")
        } == legacy_columns
    finally:
        connection.close()

    downgraded = alembic("downgrade", "0035_cumulative_profiles_rbac")
    assert downgraded.returncode == 0, downgraded.stderr
    reupgraded = alembic("upgrade", "0036_cash_concepts")
    assert reupgraded.returncode == 0, reupgraded.stderr


def test_cash_concept_migration_blocks_downgrade_when_history_exists(tmp_path: Path) -> None:
    database_path = tmp_path / "cash-concepts-history.db"
    env = {
        **os.environ,
        "RESTAURANTOS_DATABASE_URL": f"sqlite+pysqlite:///{database_path}",
    }

    def alembic(*arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "alembic", "-c", "alembic.ini", *arguments],
            cwd=API_DIR,
            env=env,
            capture_output=True,
            text=True,
        )

    upgraded = alembic("upgrade", "0036_cash_concepts")
    assert upgraded.returncode == 0, upgraded.stderr
    connection = sqlite3.connect(database_path)
    try:
        organization_id = connection.execute("SELECT id FROM organizations LIMIT 1").fetchone()[0]
        user_id = connection.execute("SELECT id FROM users LIMIT 1").fetchone()[0]
        connection.execute(
            """
            INSERT INTO cash_movement_concepts
                (id, organization_id, code, status, created_by_user_id, created_at, archived_at)
            VALUES (?, ?, ?, 'active', ?, ?, NULL)
            """,
            (
                "018f6f73-2d0a-74f0-8f1c-000000009001",
                organization_id,
                "DOWNGRADE_GUARD",
                user_id,
                "2026-08-11T18:00:00+00:00",
            ),
        )
        connection.commit()
    finally:
        connection.close()

    blocked = alembic("downgrade", "0035_cumulative_profiles_rbac")
    assert blocked.returncode != 0
    assert "Safe downgrade blocked: cash concept history exists" in (
        blocked.stdout + blocked.stderr
    )
