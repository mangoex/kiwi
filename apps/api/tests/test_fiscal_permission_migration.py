"""FISCAL-001 permission registry expansion preserves effective authority history."""

import shutil
import sqlite3
from uuid import NAMESPACE_URL, uuid5

import pytest
from test_cash_ledger_migration import _sqlite_alembic

PREVIOUS = "0084_branch_workspaces"
REVISION = "0085_fiscal_permissions"
CODES = (
    "invoicing.read",
    "invoicing.issue",
    "invoicing.cancel",
    "invoicing.receipt.create",
    "invoicing.config.manage",
)
OWNER = "fiscal-migration-owner"
READER = "fiscal-migration-reader"


@pytest.fixture(scope="module")
def baseline(tmp_path_factory):
    path = tmp_path_factory.mktemp("fiscal-migration") / "baseline.db"
    result = _sqlite_alembic(path, "upgrade", PREVIOUS)
    assert result.returncode == 0, result.stdout + result.stderr
    with sqlite3.connect(path) as connection:
        org = connection.execute("SELECT id FROM organizations LIMIT 1").fetchone()[0]
        owner_role = connection.execute(
            "SELECT role_id FROM role_authority_grants "
            "WHERE authority_kind='organization_all_permissions' LIMIT 1"
        ).fetchone()[0]
        for identifier, version in [(OWNER, 7), (READER, 3)]:
            connection.execute(
                "INSERT INTO users (id, organization_id, email, display_name, status, "
                "authorization_version, created_at, updated_at) VALUES (?, ?, ?, ?, "
                "'active', ?, '2026-10-13', '2026-10-13')",
                (identifier, org, identifier + "@example.invalid", identifier, version),
            )
        connection.execute(
            "INSERT INTO roles (id, organization_id, name, scope, created_at) "
            "VALUES ('fiscal-second-owner-role', ?, 'Second authority', "
            "'organization', '2026-10-13')",
            (org,),
        )
        connection.execute(
            "INSERT INTO role_authority_grants (role_id, authority_kind, created_at) "
            "VALUES ('fiscal-second-owner-role', 'organization_all_permissions', '2026-10-13')"
        )
        for role in (owner_role, "fiscal-second-owner-role"):
            connection.execute(
                "INSERT INTO user_roles (user_id, role_id) VALUES (?, ?)", (OWNER, role)
            )
    return path


@pytest.fixture
def database(baseline, tmp_path):
    path = tmp_path / "fiscal.db"
    shutil.copyfile(baseline, path)
    return path


def _upgrade(path):
    result = _sqlite_alembic(path, "upgrade", REVISION)
    assert result.returncode == 0, result.stdout + result.stderr


def test_registry_adds_five_capabilities_without_grants_and_bumps_owner_once(database):
    _upgrade(database)
    with sqlite3.connect(database) as connection:
        actual = dict(
            connection.execute("SELECT code, id FROM permissions WHERE code LIKE 'invoicing.%'")
        )
        assert actual == {
            code: str(uuid5(NAMESPACE_URL, "restaurantos:permission:" + code)) for code in CODES
        }
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM role_permissions rp "
                "JOIN permissions p ON rp.permission_id=p.id "
                "WHERE p.code LIKE 'invoicing.%'"
            ).fetchone()[0]
            == 0
        )
        versions = dict(
            connection.execute(
                "SELECT id, authorization_version FROM users WHERE id IN (?, ?)", (OWNER, READER)
            )
        )
        assert versions == {OWNER: 8, READER: 3}
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM audit_events WHERE action='rbac.fiscal_permissions_added'"
            ).fetchone()[0]
            >= 1
        )
    _upgrade(database)
    with sqlite3.connect(database) as connection:
        assert (
            connection.execute(
                "SELECT authorization_version FROM users WHERE id=?", (OWNER,)
            ).fetchone()[0]
            == 8
        )


@pytest.mark.parametrize("collision", ["code", "id"])
def test_collision_rejects_without_partial_registry_or_authority_change(database, collision):
    with sqlite3.connect(database) as connection:
        code = CODES[0] if collision == "code" else "custom.other"
        identifier = (
            str(uuid5(NAMESPACE_URL, "restaurantos:permission:" + CODES[0]))
            if collision == "id"
            else "custom-fiscal-id"
        )
        connection.execute(
            "INSERT INTO permissions (id, code, description, created_at) "
            "VALUES (?, ?, 'custom', '2026-10-13')",
            (identifier, code),
        )
    result = _sqlite_alembic(database, "upgrade", REVISION)
    assert result.returncode != 0
    assert "0085 preflight failed: fiscal permission identity exists" in result.stderr
    with sqlite3.connect(database) as connection:
        assert (
            connection.execute(
                "SELECT authorization_version FROM users WHERE id=?", (OWNER,)
            ).fetchone()[0]
            == 7
        )
        assert connection.execute(
            "SELECT COUNT(*) FROM permissions WHERE code LIKE 'invoicing.%'"
        ).fetchone()[0] == (1 if collision == "code" else 0)


def test_authority_overflow_blocks_registry_before_any_write(database):
    with sqlite3.connect(database) as connection:
        connection.execute("UPDATE users SET authorization_version=2147483647 WHERE id=?", (OWNER,))
    result = _sqlite_alembic(database, "upgrade", REVISION)
    assert result.returncode != 0
    assert "0085 preflight failed: authorization version exhausted" in result.stderr
    with sqlite3.connect(database) as connection:
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM permissions WHERE code LIKE 'invoicing.%'"
            ).fetchone()[0]
            == 0
        )


def test_empty_downgrade_preserves_audit_and_bumps_effective_revocation(database):
    _upgrade(database)
    result = _sqlite_alembic(database, "downgrade", PREVIOUS)
    assert result.returncode == 0, result.stdout + result.stderr
    with sqlite3.connect(database) as connection:
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM permissions WHERE code LIKE 'invoicing.%'"
            ).fetchone()[0]
            == 0
        )
        assert (
            connection.execute(
                "SELECT authorization_version FROM users WHERE id=?", (OWNER,)
            ).fetchone()[0]
            == 9
        )
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM audit_events WHERE action='rbac.fiscal_permissions_added'"
            ).fetchone()[0]
            >= 1
        )
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM audit_events WHERE action='rbac.fiscal_permissions_removed'"
            ).fetchone()[0]
            >= 1
        )


@pytest.mark.parametrize("blocker", ["grant", "config"])
def test_downgrade_refuses_existing_assignment_or_fiscal_configuration(database, blocker):
    _upgrade(database)
    with sqlite3.connect(database) as connection:
        if blocker == "grant":
            connection.execute(
                "INSERT INTO role_permissions (role_id, permission_id) "
                "SELECT 'fiscal-second-owner-role', id FROM permissions WHERE code='invoicing.read'"
            )
        else:
            org = connection.execute("SELECT id FROM organizations LIMIT 1").fetchone()[0]
            connection.execute(
                "INSERT INTO facturapi_config (id, organization_id, organization_legal_name, "
                "organization_rfc, organization_tax_system, organization_zip, "
                "created_at, updated_at) "
                "VALUES ('fiscal-test-config', ?, 'Fixture', 'XAXX010101000', '616', "
                "'80000', '2026-10-13', '2026-10-13')",
                (org,),
            )
    result = _sqlite_alembic(database, "downgrade", PREVIOUS)
    assert result.returncode != 0
    assert "0085 downgrade blocked: fiscal authority or history exists" in result.stderr
    with sqlite3.connect(database) as connection:
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM permissions WHERE code LIKE 'invoicing.%'"
            ).fetchone()[0]
            == 5
        )
        assert (
            connection.execute(
                "SELECT authorization_version FROM users WHERE id=?", (OWNER,)
            ).fetchone()[0]
            == 8
        )
