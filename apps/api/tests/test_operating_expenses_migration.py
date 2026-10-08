"""Migration is exercised only in isolated local databases."""

import os
import sqlite3

import pytest
import sqlalchemy as sa
from test_cash_ledger_migration import _postgres_alembic, _sqlite_alembic

REVISION = "0075_operating_expenses"
PREVIOUS = "0074_dual_physical_counts"


def test_expense_migration_roundtrip_and_catalog_only_history_guard(tmp_path):
    path = tmp_path / "expenses.db"
    initial = _sqlite_alembic(path, "upgrade", PREVIOUS)
    assert initial.returncode == 0, initial.stdout + initial.stderr
    with sqlite3.connect(path) as connection:
        connection.execute(
            "UPDATE roles SET scope='branch' WHERE id=?", ("018f6f73-2d0a-74f0-8f1c-000000001006",)
        )
    refused = _sqlite_alembic(path, "upgrade", REVISION)
    assert refused.returncode != 0 and "canonical expense role differs" in refused.stderr
    with sqlite3.connect(path) as connection:
        assert not connection.execute(
            "SELECT 1 FROM sqlite_master WHERE name='expense_documents'"
        ).fetchone()
        connection.execute(
            "UPDATE roles SET scope='organization' WHERE id=?",
            ("018f6f73-2d0a-74f0-8f1c-000000001006",),
        )
        connection.execute(
            "INSERT INTO organizations (id,name,status,created_at,updated_at) "
            "VALUES ('other-org','Other','active','2026-10-08','2026-10-08')"
        )
        connection.execute(
            "INSERT INTO roles (id,organization_id,name,scope,created_at) "
            "VALUES ('custom-owner','other-org',"
            "'Dueño','organization','2026-10-08')"
        )
    for action, revision in (("upgrade", REVISION), ("downgrade", PREVIOUS), ("upgrade", REVISION)):
        result = _sqlite_alembic(path, action, revision)
        assert result.returncode == 0, result.stdout + result.stderr
    with sqlite3.connect(path) as connection:
        roles = connection.execute(
            "SELECT r.name, p.code FROM role_permissions rp JOIN roles r ON r.id=rp.role_id "
            "JOIN permissions p ON p.id=rp.permission_id WHERE p.code LIKE 'expense%'"
        ).fetchall()
        assert ("Supervisor", "expenses.manage") in roles
        assert ("Dueño", "expense.concept.manage") in roles
        assert not any(name in {"Cajero", "Administrador corporativo"} for name, _ in roles)
        assert not connection.execute(
            "SELECT 1 FROM role_permissions WHERE role_id='custom-owner'"
        ).fetchone()
        connection.execute(
            "INSERT INTO role_permissions SELECT 'custom-owner',id "
            "FROM permissions WHERE code='expenses.read'"
        )
    blocked = _sqlite_alembic(path, "downgrade", PREVIOUS)
    assert blocked.returncode != 0 and "external grants" in blocked.stderr
    with sqlite3.connect(path) as connection:
        connection.execute("DELETE FROM role_permissions WHERE role_id='custom-owner'")
        connection.execute(
            "INSERT INTO expense_concepts (id,organization_id,code,name,description,status,"
            "version,created_by,created_at,updated_at) VALUES "
            "('concept','org','LUZ','Luz','','active',1,'actor','2026-10-08','2026-10-08')"
        )
    blocked = _sqlite_alembic(path, "downgrade", PREVIOUS)
    assert blocked.returncode != 0
    assert "Expense history exists" in blocked.stdout + blocked.stderr


def test_postgres_expense_migration_roundtrip():
    url = os.environ.get("EXP001_TEST_POSTGRES_MIGRATION_URL")
    if not url:
        pytest.skip("EXP001_TEST_POSTGRES_MIGRATION_URL is required")
    parsed = sa.engine.make_url(url)
    assert parsed.host in {"localhost", "127.0.0.1"} and parsed.database.startswith("exp001_")
    for action, revision in (("upgrade", REVISION), ("downgrade", PREVIOUS), ("upgrade", REVISION)):
        result = _postgres_alembic(url, action, revision)
        assert result.returncode == 0, result.stdout + result.stderr
    engine = sa.create_engine(url)
    try:
        with engine.connect() as connection:
            assert connection.scalar(sa.text("SELECT version_num FROM alembic_version")) == REVISION
            assert connection.scalar(sa.text("SELECT COUNT(*) FROM expense_documents")) == 0
    finally:
        engine.dispose()
