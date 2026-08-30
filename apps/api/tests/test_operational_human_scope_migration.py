"""SQLite migration evidence for TDD-TC-213 granular human operations."""

from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ROLE_IDS = {
    "Cajero": "018f6f73-2d0a-74f0-8f1c-000000001001",
    "Cajero jefe": "018f6f73-2d0a-74f0-8f1c-000000001002",
    "Líder": "018f6f73-2d0a-74f0-8f1c-000000001003",
    "Supervisor": "018f6f73-2d0a-74f0-8f1c-000000001004",
    "Administrador": "018f6f73-2d0a-74f0-8f1c-000000001005",
    "Dueño": "018f6f73-2d0a-74f0-8f1c-000000001006",
}
GRANTS = {"kds.tasks.operate", "print.jobs.read", "print.jobs.retry", "sync.events.read"}


def _alembic(database_path: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "alembic.ini", *arguments],
        cwd=ROOT / "apps" / "api",
        env={
            **os.environ,
            "RESTAURANTOS_DATABASE_URL": f"sqlite+pysqlite:///{database_path}",
        },
        capture_output=True,
        text=True,
    )


def _grants(connection: sqlite3.Connection, role_id: str) -> set[str]:
    return {
        row[0]
        for row in connection.execute(
            """
            SELECT permissions.code FROM role_permissions
            JOIN permissions ON permissions.id = role_permissions.permission_id
            WHERE role_permissions.role_id = ? AND permissions.code IN (?, ?, ?, ?)
            """,
            (role_id, *sorted(GRANTS)),
        )
    }


def test_0057_grants_only_upper_profiles_and_roundtrips(tmp_path: Path) -> None:
    database_path = tmp_path / "operational-human-scope.db"
    prepared = _alembic(database_path, "upgrade", "0056_repair_0047_canonical_roles")
    assert prepared.returncode == 0, prepared.stderr
    upgraded = _alembic(
        database_path, "upgrade", "0057_operational_human_scope_permissions"
    )
    assert upgraded.returncode == 0, upgraded.stderr

    connection = sqlite3.connect(database_path)
    try:
        for name in ("Supervisor", "Administrador", "Dueño"):
            assert _grants(connection, ROLE_IDS[name]) == GRANTS
        for name in ("Cajero", "Cajero jefe", "Líder"):
            assert _grants(connection, ROLE_IDS[name]) == set()
    finally:
        connection.close()

    downgraded = _alembic(database_path, "downgrade", "0056_repair_0047_canonical_roles")
    assert downgraded.returncode == 0, downgraded.stderr
    connection = sqlite3.connect(database_path)
    try:
        assert connection.execute(
            "SELECT 1 FROM permissions WHERE code = 'sync.events.read'"
        ).fetchone() is None
        assert _grants(connection, ROLE_IDS["Supervisor"]) == set()
        assert _grants(connection, ROLE_IDS["Administrador"]) == set()
        assert _grants(connection, ROLE_IDS["Dueño"]) == {
            "print.jobs.read",
            "print.jobs.retry",
        }
    finally:
        connection.close()


def test_0057_downgrade_blocks_external_sync_grant(tmp_path: Path) -> None:
    database_path = tmp_path / "operational-human-scope-external.db"
    upgraded = _alembic(
        database_path, "upgrade", "0057_operational_human_scope_permissions"
    )
    assert upgraded.returncode == 0, upgraded.stderr
    connection = sqlite3.connect(database_path)
    try:
        sync_id = connection.execute(
            "SELECT id FROM permissions WHERE code = 'sync.events.read'"
        ).fetchone()[0]
        connection.execute(
            "INSERT INTO role_permissions (role_id, permission_id) VALUES (?, ?)",
            (ROLE_IDS["Cajero"], sync_id),
        )
        connection.commit()
    finally:
        connection.close()

    rejected = _alembic(database_path, "downgrade", "0056_repair_0047_canonical_roles")
    assert rejected.returncode != 0
    assert "external grants" in rejected.stderr
