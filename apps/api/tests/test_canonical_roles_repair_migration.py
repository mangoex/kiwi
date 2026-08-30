"""R3 regression coverage for the forward-only 0047 RBAC data repair."""

from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

import pytest
import sqlalchemy as sa
from sqlalchemy import create_engine

ROOT = Path(__file__).resolve().parents[3]
API_DIR = ROOT / "apps" / "api"
POSTGRES_ENV = "RBAC0056_TEST_POSTGRES_URL"
ROLE_IDS = {
    "Cajero": "018f6f73-2d0a-74f0-8f1c-000000001001",
    "Cajero jefe": "018f6f73-2d0a-74f0-8f1c-000000001002",
    "Líder": "018f6f73-2d0a-74f0-8f1c-000000001003",
    "Supervisor": "018f6f73-2d0a-74f0-8f1c-000000001004",
    "Administrador": "018f6f73-2d0a-74f0-8f1c-000000001005",
    "Dueño": "018f6f73-2d0a-74f0-8f1c-000000001006",
}
PROFILE_ADDITIONS = {
    "Cajero": {
        "pos.operate",
        "orders.read",
        "orders.create",
        "payments.read",
        "payments.confirm",
        "cash.concept.read",
        "cash.movement.withdraw",
    },
    "Cajero jefe": {
        "cash.shift.read",
        "cash.shift.open",
        "cash.shift.close",
        "cash.movement.deposit",
        "cash.movement.read",
        "cash.reconciliation.perform",
        "orders.amend",
        "purchases.read",
        "purchases.manage",
        "inventory.waste",
        "orders.reopen.request",
    },
    "Líder": {"cash.user_cut.read", "cash.user_cut.create", "orders.cancel"},
    "Supervisor": {
        "recipes.manage",
        "inventory.read",
        "reports.ingredient_sales.read",
        "reports.waste.read",
    },
    "Administrador": {"reports.sales.read", "reports.expenses.read"},
}


def _expected_profiles() -> dict[str, set[str]]:
    effective: set[str] = set()
    result: dict[str, set[str]] = {}
    for name in ("Cajero", "Cajero jefe", "Líder", "Supervisor", "Administrador"):
        effective |= PROFILE_ADDITIONS[name]
        result[name] = set(effective)
    return result


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


def _postgres_url() -> str:
    url = os.environ.get(POSTGRES_ENV)
    if not url:
        pytest.skip(f"{POSTGRES_ENV} is required for opt-in PostgreSQL tests")
    parsed = urlparse(url)
    database = parsed.path.lstrip("/")
    if (
        not parsed.scheme.startswith("postgres")
        or parsed.hostname not in {"localhost", "127.0.0.1"}
        or not database.startswith("rbac0056_")
    ):
        raise RuntimeError(f"{POSTGRES_ENV} must target a local isolated rbac0056_* database")
    return url


def _postgres_alembic(url: str, *arguments: str) -> subprocess.CompletedProcess[str]:
    environment = dict(os.environ)
    environment.pop("DATABASE_URL", None)
    environment["RESTAURANTOS_DATABASE_URL"] = url
    return subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "alembic.ini", *arguments],
        cwd=API_DIR,
        env=environment,
        capture_output=True,
        text=True,
        timeout=60,
    )


def _permission_codes(connection: sqlite3.Connection, role_id: str) -> set[str]:
    return {
        row[0]
        for row in connection.execute(
            """
            SELECT permissions.code
            FROM role_permissions
            JOIN permissions ON permissions.id = role_permissions.permission_id
            WHERE role_permissions.role_id = ?
            """,
            (role_id,),
        )
    }


def test_0056_repairs_0047_to_exact_cumulative_profiles(tmp_path: Path) -> None:
    database_path = tmp_path / "canonical-rbac-repair.db"
    upgraded = _alembic(database_path, "upgrade", "0056_repair_0047_canonical_roles")
    assert upgraded.returncode == 0, upgraded.stderr

    connection = sqlite3.connect(database_path)
    try:
        for role_name, expected_codes in _expected_profiles().items():
            role = connection.execute(
                "SELECT organization_id, name, scope FROM roles WHERE id = ?",
                (ROLE_IDS[role_name],),
            ).fetchone()
            assert role == (
                "018f6f73-2d0a-74f0-8f1c-000000000001",
                role_name,
                "branch",
            )
            assert _permission_codes(connection, ROLE_IDS[role_name]) == expected_codes

        assert connection.execute(
            "SELECT scope FROM roles WHERE id = ?", (ROLE_IDS["Dueño"],)
        ).fetchone() == ("organization",)
        assert connection.execute(
            "SELECT authority_kind FROM role_authority_grants WHERE role_id = ?",
            (ROLE_IDS["Dueño"],),
        ).fetchone() == ("organization_all_permissions",)
        assert connection.execute(
            "SELECT COUNT(*) FROM user_roles WHERE role_id = ?", (ROLE_IDS["Dueño"],)
        ).fetchone() == (0,)
    finally:
        connection.close()


def test_repair_fails_closed_when_a_required_permission_is_missing(tmp_path: Path) -> None:
    database_path = tmp_path / "canonical-rbac-missing-permission.db"
    prepared = _alembic(database_path, "upgrade", "0055_admin_ai_proposals")
    assert prepared.returncode == 0, prepared.stderr
    connection = sqlite3.connect(database_path)
    try:
        permission_id = connection.execute(
            "SELECT id FROM permissions WHERE code = 'cash.user_cut.create'"
        ).fetchone()[0]
        connection.execute(
            "DELETE FROM role_permissions WHERE permission_id = ?", (permission_id,)
        )
        connection.execute("DELETE FROM permissions WHERE id = ?", (permission_id,))
        connection.commit()
    finally:
        connection.close()

    rejected = _alembic(database_path, "upgrade", "head")
    assert rejected.returncode != 0
    assert "required permission is missing" in rejected.stderr
    current = _alembic(database_path, "current")
    assert "0055_admin_ai_proposals" in current.stdout


def test_repair_fails_closed_for_cross_organization_homonym(tmp_path: Path) -> None:
    database_path = tmp_path / "canonical-rbac-cross-org.db"
    prepared = _alembic(database_path, "upgrade", "0055_admin_ai_proposals")
    assert prepared.returncode == 0, prepared.stderr
    connection = sqlite3.connect(database_path)
    try:
        connection.execute(
            """
            INSERT INTO organizations (id, name, status, created_at, updated_at)
            VALUES (?, 'Otra organización', 'active', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            ("018f6f73-2d0a-74f0-8f1c-000000009001",),
        )
        connection.execute(
            """
            INSERT INTO roles (id, organization_id, name, scope, created_at)
            VALUES (?, ?, 'Cajero', 'branch', CURRENT_TIMESTAMP)
            """,
            (
                "018f6f73-2d0a-74f0-8f1c-000000009002",
                "018f6f73-2d0a-74f0-8f1c-000000009001",
            ),
        )
        connection.commit()
    finally:
        connection.close()

    rejected = _alembic(database_path, "upgrade", "head")
    assert rejected.returncode != 0
    assert "cross-organization role requires audit" in rejected.stderr
    current = _alembic(database_path, "current")
    assert "0055_admin_ai_proposals" in current.stdout


def test_postgres_repair_reaches_exact_profiles_and_blocks_downgrade() -> None:
    url = _postgres_url()
    engine = create_engine(url, future=True)
    try:
        with engine.begin() as connection:
            connection.execute(sa.text("DROP SCHEMA public CASCADE"))
            connection.execute(sa.text("CREATE SCHEMA public"))
    finally:
        engine.dispose()

    upgraded = _postgres_alembic(url, "upgrade", "0056_repair_0047_canonical_roles")
    assert upgraded.returncode == 0, upgraded.stdout + upgraded.stderr
    engine = create_engine(url, future=True)
    try:
        with engine.connect() as connection:
            for role_name, expected_codes in _expected_profiles().items():
                actual_codes = set(
                    connection.execute(
                        sa.text(
                            """
                            SELECT permissions.code
                            FROM role_permissions
                            JOIN permissions
                              ON permissions.id = role_permissions.permission_id
                            WHERE role_permissions.role_id = :role_id
                            """
                        ),
                        {"role_id": ROLE_IDS[role_name]},
                    ).scalars()
                )
                assert actual_codes == expected_codes
    finally:
        engine.dispose()

    downgrade = _postgres_alembic(url, "downgrade", "0055_admin_ai_proposals")
    assert downgrade.returncode != 0
    assert "forward-only" in downgrade.stderr
