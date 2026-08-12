from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

from alembic.config import Config

ROOT = Path(__file__).resolve().parents[3]


def test_alembic_config_preserves_percent_encoded_database_url() -> None:
    from restaurant_os.alembic_config import set_alembic_database_url

    encoded_url = (
        "postgresql+psycopg://cashier%40kiwi:pa%25ss@localhost/restaurant"
        "?host=%2Fprivate%2Ftmp%2Fpostgres"
    )
    for database_url in (encoded_url, "sqlite+pysqlite:////private/tmp/restaurantos.db"):
        config = Config()
        set_alembic_database_url(config, database_url)
        assert config.get_main_option("sqlalchemy.url") == database_url


def test_category_option_migration_sqlite_roundtrip_preserves_existing_tables(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "category-option-roundtrip.db"
    env = {
        **os.environ,
        "RESTAURANTOS_DATABASE_URL": f"sqlite+pysqlite:///{database_path}",
    }

    def alembic(*arguments: str) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "-c", "alembic.ini", *arguments],
            cwd=ROOT / "apps" / "api", env=env, capture_output=True, text=True,
        )
        assert result.returncode == 0, result.stderr

    alembic("upgrade", "0033_restore_superadmin_role")
    connection = sqlite3.connect(database_path)
    try:
        existing_orders_sql = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'orders'"
        ).fetchone()[0]
    finally:
        connection.close()
    alembic("upgrade", "head")
    connection = sqlite3.connect(database_path)
    try:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        assert {
            "category_option_groups",
            "category_option_values",
            "product_option_value_assignments",
        } <= tables
        group_sql = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'category_option_groups'"
        ).fetchone()[0]
        assert "uq_category_option_groups_organization_category" in group_sql
        assert "organization_id, code" not in group_sql
        assert "ck_category_option_groups_selection_mode" in group_sql
        group_foreign_keys = {
            row[2]
            for row in connection.execute(
                "PRAGMA foreign_key_list(category_option_groups)"
            )
        }
        assert group_foreign_keys == {"organizations", "product_categories"}
        assignment_foreign_keys = {
            row[2]
            for row in connection.execute(
                "PRAGMA foreign_key_list(product_option_value_assignments)"
            )
        }
        assert assignment_foreign_keys == {
            "products",
            "category_option_groups",
            "category_option_values",
        }
        assignment_indexes = connection.execute(
            "PRAGMA index_list(product_option_value_assignments)"
        ).fetchall()
        assert any(
            index[2]
            and [
                column[2]
                for column in connection.execute(f"PRAGMA index_info({index[1]})")
            ]
            == ["product_id", "group_id"]
            for index in assignment_indexes
        )
        assert "ix_category_option_values_group_order" in {
            row[1] for row in connection.execute("PRAGMA index_list(category_option_values)")
        }
    finally:
        connection.close()
    alembic("downgrade", "0033_restore_superadmin_role")
    connection = sqlite3.connect(database_path)
    try:
        assert connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' "
            "AND name = 'category_option_groups'"
        ).fetchone() is None
        assert connection.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'orders'"
        ).fetchone()[0] == existing_orders_sql
    finally:
        connection.close()
    alembic("upgrade", "head")
    connection = sqlite3.connect(database_path)
    try:
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == (
            "0037_cash_movement_ledger",
        )
        assert connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' "
            "AND name = 'category_option_groups'"
        ).fetchone() is not None
    finally:
        connection.close()


def test_audit_seed_payload_column_is_typed_as_json() -> None:
    migration = (
        ROOT
        / "apps"
        / "api"
        / "alembic"
        / "versions"
        / "202607071900_0002_base_operational_schema.py"
    ).read_text(encoding="utf-8")

    assert 'sa.column("payload", sa.JSON())' in migration


def test_business_unit_migration_seeds_hierarchy_and_operational_profiles(tmp_path: Path) -> None:
    database_path = tmp_path / "restaurantos.db"
    env = {
        **os.environ,
        "RESTAURANTOS_DATABASE_URL": f"sqlite+pysqlite:///{database_path}",
    }
    subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "alembic.ini", "upgrade", "head"],
        cwd=ROOT / "apps" / "api",
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )

    connection = sqlite3.connect(database_path)
    try:
        branch = connection.execute(
            "SELECT code, business_unit_id FROM branches WHERE code = 'PILOTO'"
        ).fetchone()
        assert branch == ("PILOTO", "018f6f73-2d0a-74f0-8f1c-000000000015")

        def permissions_for(role_name: str) -> set[str]:
            rows = connection.execute(
                """
                SELECT permissions.code
                FROM roles
                JOIN role_permissions ON role_permissions.role_id = roles.id
                JOIN permissions ON permissions.id = role_permissions.permission_id
                WHERE roles.name = ?
                """,
                (role_name,),
            )
            return {row[0] for row in rows}

        cashier = permissions_for("Cajero")
        cashier_lead = permissions_for("Cajero jefe")
        leader = permissions_for("Líder")
        supervisor_profile = permissions_for("Supervisor")
        administrator_profile = permissions_for("Administrador")
        owner = permissions_for("Dueño")
        supervisor = permissions_for("Supervisor de sucursal")
        receiver = permissions_for("Receptor de traspaso")
        auditor = permissions_for("Auditor")
        assert "purchases.manage" not in cashier
        assert cashier < cashier_lead < leader < supervisor_profile < administrator_profile
        assert administrator_profile <= owner
        assert "access.organization.all_branches" in owner
        assert connection.execute(
            """
            SELECT COUNT(*) FROM role_authority_grants
            WHERE role_id = (SELECT id FROM roles WHERE name = 'Dueño')
              AND authority_kind = 'organization_all_permissions'
            """
        ).fetchone() == (1,)
        assert connection.execute(
            "SELECT scope FROM roles WHERE name = 'Dueño'"
        ).fetchone() == ("organization",)
        assert connection.execute(
            "SELECT COUNT(*) FROM roles WHERE name IN "
            "('Cajero', 'Cajero jefe', 'Líder', 'Supervisor', 'Administrador') "
            "AND scope = 'branch'"
        ).fetchone() == (5,)
        assert {
            "branch.admin.access",
            "branch.staff.read",
            "catalog.branch.manage",
            "purchases.manage",
            "production.manage",
            "inventory.waste",
            "inventory.transfer.send",
            "inventory.count",
        } <= supervisor
        assert not {
            "branch.admin.access",
            "branch.staff.read",
            "catalog.branch.manage",
        } & cashier
        assert receiver == {"inventory.read", "inventory.transfer.receive"}
        assert "audit.read" in auditor
        assert not ({"purchases.manage", "inventory.adjust", "inventory.waste"} & auditor)
        waste_reasons = connection.execute(
            "SELECT code FROM waste_reasons ORDER BY display_order"
        ).fetchall()
        assert len(waste_reasons) == 9
        assert waste_reasons[0] == ("EXPIRATION",)
        assert waste_reasons[-1] == ("OTHER_AUTHORIZED",)
    finally:
        connection.close()


def test_cumulative_profiles_seed_fails_closed_and_preserves_foreign_permission(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "cumulative-profile-permission-collision.db"
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

    upgraded = alembic("upgrade", "0034_category_option_selection")
    assert upgraded.returncode == 0, upgraded.stderr
    connection = sqlite3.connect(database_path)
    try:
        connection.execute(
            "INSERT INTO permissions (id, code, description, created_at) VALUES (?, ?, ?, ?)",
            (
                "018f6f73-2d0a-74f0-8f1c-000000009901",
                "cash.movement.withdraw",
                "foreign permission must survive",
                "2026-08-10 03:00:00",
            ),
        )
        connection.commit()
    finally:
        connection.close()

    blocked = alembic("upgrade", "head")
    assert blocked.returncode != 0
    assert "Cumulative profile seed collision" in blocked.stdout + blocked.stderr
    connection = sqlite3.connect(database_path)
    try:
        assert connection.execute(
            "SELECT description FROM permissions WHERE code = 'cash.movement.withdraw'"
        ).fetchone() == ("foreign permission must survive",)
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == (
            "0034_category_option_selection",
        )
    finally:
        connection.close()


def test_cumulative_profiles_seed_fails_closed_on_reserved_role_collision(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "cumulative-profile-role-collision.db"
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

    upgraded = alembic("upgrade", "0034_category_option_selection")
    assert upgraded.returncode == 0, upgraded.stderr
    connection = sqlite3.connect(database_path)
    try:
        connection.execute(
            """
            INSERT INTO roles (id, organization_id, name, scope, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                "018f6f73-2d0a-74f0-8f1c-000000001006",
                "018f6f73-2d0a-74f0-8f1c-000000000001",
                "Foreign owner identity",
                "organization",
                "2026-08-10 03:00:00",
            ),
        )
        connection.commit()
    finally:
        connection.close()

    blocked = alembic("upgrade", "head")
    assert blocked.returncode != 0
    assert "Cumulative profile seed collision" in blocked.stdout + blocked.stderr
    connection = sqlite3.connect(database_path)
    try:
        assert connection.execute(
            "SELECT name FROM roles WHERE id = '018f6f73-2d0a-74f0-8f1c-000000001006'"
        ).fetchone() == ("Foreign owner identity",)
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == (
            "0034_category_option_selection",
        )
    finally:
        connection.close()


def test_cumulative_profiles_downgrade_requires_controlled_reversal(tmp_path: Path) -> None:
    database_path = tmp_path / "cumulative-profiles-roundtrip.db"
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

    upgraded = alembic("upgrade", "head")
    assert upgraded.returncode == 0, upgraded.stderr
    connection = sqlite3.connect(database_path)
    try:
        owner_role_id = "018f6f73-2d0a-74f0-8f1c-000000001006"
        legacy_admin_role_id = connection.execute(
            "SELECT id FROM roles WHERE name = 'Administrador corporativo'"
        ).fetchone()[0]
        user_id = connection.execute(
            "SELECT id FROM users WHERE organization_id = ? ORDER BY id LIMIT 1",
            ("018f6f73-2d0a-74f0-8f1c-000000000001",),
        ).fetchone()[0]
        cash_permission_id = connection.execute(
            "SELECT id FROM permissions WHERE code = 'cash.movement.withdraw'"
        ).fetchone()[0]
        mapping_sql = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' "
            "AND name = 'profile_transition_mappings'"
        ).fetchone()[0]
        assert "uq_profile_transition_mappings_active_state" not in mapping_sql
        mapping_indexes = {
            row[1] for row in connection.execute("PRAGMA index_list(profile_transition_mappings)")
        }
        assert "uq_profile_transition_mappings_open_target" in mapping_indexes
        mapping_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(profile_transition_mappings)")
        }
        assert {
            "target_branch_id",
            "role_snapshot",
            "provenance",
            "create_idempotency_key",
            "apply_idempotency_key",
            "reverse_idempotency_key",
            "applied_at",
        } <= mapping_columns
        assert "uq_profile_transition_mappings_create_key" in mapping_sql
        for mapping_id in (
            "018f6f73-2d0a-74f0-8f1c-000000001208",
            "018f6f73-2d0a-74f0-8f1c-000000001209",
        ):
            connection.execute(
                """
                INSERT INTO profile_transition_mappings
                (id, organization_id, user_id, legacy_role_id, target_role_id, status,
                 mapped_by_user_id, created_at, reversed_at)
                VALUES (?, ?, ?, ?, ?, 'reversed', ?, '2026-08-10 03:00:00', '2026-08-10 04:00:00')
                """,
                (
                    mapping_id,
                    "018f6f73-2d0a-74f0-8f1c-000000000001",
                    user_id,
                    legacy_admin_role_id,
                    owner_role_id,
                    user_id,
                ),
            )
        connection.commit()
        assert connection.execute(
            "SELECT COUNT(*) FROM profile_transition_mappings WHERE status = 'reversed'"
        ).fetchone() == (2,)
        connection.execute(
            """
            INSERT INTO profile_transition_mappings
            (id, organization_id, user_id, legacy_role_id, target_role_id, status,
             mapped_by_user_id, created_at, reversed_at)
            VALUES (?, ?, ?, ?, ?, 'pending', ?, '2026-08-10 05:00:00', NULL)
            """,
            (
                "018f6f73-2d0a-74f0-8f1c-000000001210",
                "018f6f73-2d0a-74f0-8f1c-000000000001",
                user_id,
                legacy_admin_role_id,
                owner_role_id,
                user_id,
            ),
        )
        connection.commit()
        try:
            connection.execute(
                """
                INSERT INTO profile_transition_mappings
                (id, organization_id, user_id, legacy_role_id, target_role_id, status,
                 mapped_by_user_id, created_at, reversed_at)
                VALUES (?, ?, ?, ?, ?, 'mapped', ?, '2026-08-10 06:00:00', NULL)
                """,
                (
                    "018f6f73-2d0a-74f0-8f1c-000000001211",
                    "018f6f73-2d0a-74f0-8f1c-000000000001",
                    user_id,
                    legacy_admin_role_id,
                    owner_role_id,
                    user_id,
                ),
            )
        except sqlite3.IntegrityError:
            pass
        else:
            raise AssertionError("Two active profile mappings must be rejected")
        connection.execute(
            "DELETE FROM profile_transition_mappings WHERE id = ?",
            ("018f6f73-2d0a-74f0-8f1c-000000001210",),
        )
        connection.commit()
        assert connection.execute(
            "SELECT COUNT(*) FROM user_roles WHERE role_id = ?", (owner_role_id,)
        ).fetchone() == (0,)

        connection.execute(
            "INSERT INTO user_roles (user_id, role_id, branch_id) VALUES (?, ?, NULL)",
            (user_id, owner_role_id),
        )
        connection.commit()
        blocked_assignment = alembic("downgrade", "0034_category_option_selection")
        assert blocked_assignment.returncode != 0
        assert "Safe downgrade blocked" in (
            blocked_assignment.stdout + blocked_assignment.stderr
        )
        connection.execute(
            "DELETE FROM user_roles WHERE user_id = ? AND role_id = ?",
            (user_id, owner_role_id),
        )
        connection.commit()

        connection.execute(
            """
            INSERT INTO profile_transition_mappings
            (id, organization_id, user_id, legacy_role_id, target_role_id, status,
             mapped_by_user_id, created_at, reversed_at)
            VALUES (?, ?, ?, ?, ?, 'mapped', ?, '2026-08-10 03:00:00', NULL)
            """,
            (
                "018f6f73-2d0a-74f0-8f1c-000000001207",
                "018f6f73-2d0a-74f0-8f1c-000000000001",
                user_id,
                legacy_admin_role_id,
                owner_role_id,
                user_id,
            ),
        )
        connection.commit()
        blocked_mapping = alembic("downgrade", "0034_category_option_selection")
        assert blocked_mapping.returncode != 0
        assert "Safe downgrade blocked" in blocked_mapping.stdout + blocked_mapping.stderr
        connection.execute("DELETE FROM profile_transition_mappings")
        connection.commit()

        connection.execute(
            "INSERT INTO role_permissions (role_id, permission_id) VALUES (?, ?)",
            (legacy_admin_role_id, cash_permission_id),
        )
        connection.commit()
        blocked_grant = alembic("downgrade", "0034_category_option_selection")
        assert blocked_grant.returncode != 0
        assert "Safe downgrade blocked" in blocked_grant.stdout + blocked_grant.stderr
        connection.execute(
            "DELETE FROM role_permissions WHERE role_id = ? AND permission_id = ?",
            (legacy_admin_role_id, cash_permission_id),
        )
        connection.commit()
    finally:
        connection.close()

    downgraded = alembic("downgrade", "0034_category_option_selection")
    assert downgraded.returncode == 0, downgraded.stderr
    connection = sqlite3.connect(database_path)
    try:
        assert connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' "
            "AND name = 'profile_transition_mappings'"
        ).fetchone() is None
        assert connection.execute(
            "SELECT name FROM roles WHERE id = '018f6f73-2d0a-74f0-8f1c-000000000008'"
        ).fetchone() == ("Cajero",)
    finally:
        connection.close()


def test_branch_admin_permission_migration_roundtrip(tmp_path: Path) -> None:
    database_path = tmp_path / "branch-admin-roundtrip.db"
    env = {
        **os.environ,
        "RESTAURANTOS_DATABASE_URL": f"sqlite+pysqlite:///{database_path}",
    }

    def alembic(*arguments: str) -> None:
        subprocess.run(
            [sys.executable, "-m", "alembic", "-c", "alembic.ini", *arguments],
            cwd=ROOT / "apps" / "api",
            env=env,
            check=True,
            capture_output=True,
            text=True,
        )

    def permission_codes(connection: sqlite3.Connection, role_name: str) -> set[str]:
        rows = connection.execute(
            """
            SELECT permissions.code
            FROM roles
            JOIN role_permissions ON role_permissions.role_id = roles.id
            JOIN permissions ON permissions.id = role_permissions.permission_id
            WHERE roles.name = ?
            """,
            (role_name,),
        )
        return {row[0] for row in rows}

    branch_permissions = {
        "branch.admin.access",
        "branch.staff.read",
        "catalog.branch.manage",
    }
    alembic("upgrade", "head")
    connection = sqlite3.connect(database_path)
    try:
        assert branch_permissions <= permission_codes(
            connection, "Supervisor de sucursal"
        )
        assert branch_permissions <= permission_codes(
            connection, "Administrador corporativo"
        )
        assert not branch_permissions & permission_codes(connection, "Cajero")
    finally:
        connection.close()

    alembic("downgrade", "0023_physical_counts")
    connection = sqlite3.connect(database_path)
    try:
        remaining = {row[0] for row in connection.execute("SELECT code FROM permissions")}
        assert not branch_permissions & remaining
        assert "production.manage" in permission_codes(connection, "Supervisor de sucursal")
    finally:
        connection.close()

    alembic("upgrade", "head")
    connection = sqlite3.connect(database_path)
    try:
        assert branch_permissions <= permission_codes(connection, "Supervisor de sucursal")
    finally:
        connection.close()


def test_ingredient_variation_downgrade_archives_materialized_options_with_data(
    tmp_path: Path,
) -> None:
    """0026 is reversible without making its runtime options visible on 0025."""
    database_path = tmp_path / "ingredient-variation-roundtrip.db"
    env = {
        **os.environ,
        "RESTAURANTOS_DATABASE_URL": f"sqlite+pysqlite:///{database_path}",
    }

    def alembic(*arguments: str) -> None:
        subprocess.run(
            [sys.executable, "-m", "alembic", "-c", "alembic.ini", *arguments],
            cwd=ROOT / "apps" / "api",
            env=env,
            check=True,
            capture_output=True,
            text=True,
        )

    alembic("upgrade", "head")
    connection = sqlite3.connect(database_path)
    try:
        now = "2026-07-13 12:00:00"
        organization_id = "018f6f73-2d0a-74f0-8f1c-000000000001"
        product_id = "018f6f73-2d0a-74f0-8f1c-000000000111"
        item_id = "018f6f73-2d0a-74f0-8f1c-000000000311"
        user_id = "018f6f73-2d0a-74f0-8f1c-000000000006"
        connection.execute(
            "INSERT INTO ingredient_variations "
            "(id, organization_id, inventory_item_id, add_label, remove_label, status, "
            "created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "roundtrip-variation",
                organization_id,
                item_id,
                "Con carne",
                "Sin carne",
                "active",
                now,
                now,
            ),
        )
        connection.execute(
            "INSERT INTO modifier_groups VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "roundtrip-group",
                organization_id,
                product_id,
                "Cambios de ingredientes",
                0,
                0,
                1,
                None,
                999,
                "active",
                now,
                now,
            ),
        )
        connection.execute(
            "INSERT INTO modifier_options VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "roundtrip-option",
                "roundtrip-group",
                "Con carne",
                "add",
                0,
                item_id,
                None,
                0,
                1,
                1,
                "Con carne",
                None,
                0,
                "active",
                now,
                now,
            ),
        )
        connection.execute(
            "INSERT INTO ingredient_variation_products VALUES "
            "(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "roundtrip-assignment",
                "roundtrip-variation",
                product_id,
                1,
                0,
                "1",
                "0",
                0,
                0,
                "roundtrip-option",
                None,
                "active",
                now,
                now,
            ),
        )
        connection.execute(
            "INSERT INTO ingredient_variation_commands VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "roundtrip-command",
                organization_id,
                "roundtrip-variation",
                user_id,
                "roundtrip-key",
                "0" * 64,
                "[]",
                "completed",
                now,
                now,
            ),
        )
        connection.commit()
    finally:
        connection.close()

    alembic("downgrade", "0025_legacy_branch_catalog_import")
    connection = sqlite3.connect(database_path)
    try:
        assert connection.execute(
            "SELECT status FROM modifier_options WHERE id = 'roundtrip-option'"
        ).fetchone() == ("archived",)
        assert connection.execute(
            "SELECT status, maximum_selections FROM modifier_groups WHERE id = 'roundtrip-group'"
        ).fetchone() == ("archived", 0)
        tables = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
        assert "ingredient_variations" not in tables
        assert "ingredient_variation_products" not in tables
        assert "ingredient_variation_commands" not in tables
    finally:
        connection.close()

    alembic("upgrade", "head")
    connection = sqlite3.connect(database_path)
    try:
        assert connection.execute(
            "SELECT status FROM modifier_options WHERE id = 'roundtrip-option'"
        ).fetchone() == ("archived",)
    finally:
        connection.close()


def test_global_comments_extras_upgrade_downgrade_upgrade_preserves_legacy_and_conflicts(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "global-comments-extras-roundtrip.db"
    env = {
        **os.environ,
        "RESTAURANTOS_DATABASE_URL": f"sqlite+pysqlite:///{database_path}",
    }

    def alembic(*arguments: str) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "-c", "alembic.ini", *arguments],
            cwd=ROOT / "apps" / "api",
            env=env,
            capture_output=True,
            text=True,
        )
        if result.returncode:
            raise AssertionError(result.stderr)

    organization_id = "018f6f73-2d0a-74f0-8f1c-000000000001"
    second_organization_id = "018f6f73-2d0a-74f0-8f1c-000000000099"
    burger_id = "018f6f73-2d0a-74f0-8f1c-000000000111"
    fries_id = "018f6f73-2d0a-74f0-8f1c-000000000112"
    beef_item_id = "018f6f73-2d0a-74f0-8f1c-000000000311"
    now = "2026-07-14 12:00:00"

    alembic("upgrade", "0027_catalog_cleanup")
    connection = sqlite3.connect(database_path)
    try:
        connection.execute(
            "INSERT INTO organizations (id, name, status, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (second_organization_id, "Segunda organización", "active", now, now),
        )
        connection.execute(
            "INSERT INTO ingredient_variations "
            "(id, organization_id, inventory_item_id, add_label, remove_label, status, "
            "created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "global-roundtrip-extra",
                organization_id,
                beef_item_id,
                "Con carne",
                "Sin carne",
                "active",
                now,
                now,
            ),
        )
        connection.execute(
            "INSERT INTO modifier_groups VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "global-comment-group",
                organization_id,
                burger_id,
                "Comentarios del pedido",
                0,
                0,
                4,
                None,
                0,
                "active",
                now,
                now,
            ),
        )
        connection.execute(
            "INSERT INTO modifier_options VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "global-comment-option",
                "global-comment-group",
                "Sin cebolla",
                "preset_instruction",
                0,
                None,
                None,
                0,
                0,
                0,
                "Sin cebolla",
                None,
                0,
                "active",
                now,
                now,
            ),
        )
        for group_id, product_id, option_id, station, quantity, price in (
            ("global-extra-group-a", burger_id, "global-extra-option-a", "kitchen", "1", 100),
            ("global-extra-group-b", fries_id, "global-extra-option-b", "drinks", "2", 200),
        ):
            connection.execute(
                "INSERT INTO modifier_groups VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    group_id,
                    organization_id,
                    product_id,
                    "Cambios de ingredientes",
                    0,
                    0,
                    1,
                    station,
                    10,
                    "active",
                    now,
                    now,
                ),
            )
            connection.execute(
                "INSERT INTO modifier_options VALUES "
                "(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    option_id,
                    group_id,
                    "Con carne",
                    "add",
                    price,
                    beef_item_id,
                    None,
                    0,
                    quantity,
                    1,
                    "Con carne",
                    station,
                    10,
                    "active",
                    now,
                    now,
                ),
            )
        connection.execute(
            "INSERT INTO ingredient_variation_products VALUES "
            "(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "global-roundtrip-assignment-a",
                "global-roundtrip-extra",
                burger_id,
                1,
                0,
                "1",
                "0",
                1,
                100,
                "global-extra-option-a",
                None,
                "active",
                now,
                now,
            ),
        )
        connection.execute(
            "INSERT INTO ingredient_variation_products VALUES "
            "(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "global-roundtrip-assignment-b",
                "global-roundtrip-extra",
                fries_id,
                1,
                0,
                "2",
                "0",
                1,
                200,
                "global-extra-option-b",
                None,
                "active",
                now,
                now,
            ),
        )
        connection.execute(
            "INSERT INTO ingredient_variations "
            "(id, organization_id, inventory_item_id, add_label, remove_label, status, "
            "created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "global-roundtrip-second-org-extra",
                second_organization_id,
                beef_item_id,
                "Con carne segunda",
                "Sin carne segunda",
                "archived",
                now,
                now,
            ),
        )
        connection.commit()
    finally:
        connection.close()


    alembic("upgrade", "0028_global_order_comments_extras")
    connection = sqlite3.connect(database_path)
    try:
        assert connection.execute("SELECT text FROM order_comment_presets").fetchone() == (
            "Sin cebolla",
        )
        assert connection.execute("SELECT product_id FROM order_comment_products").fetchone() == (
            burger_id,
        )
        assert connection.execute(
            "SELECT status FROM ingredient_variations WHERE id = 'global-roundtrip-extra'"
        ).fetchone() == ("needs_review",)
        assert connection.execute(
            "SELECT status FROM ingredient_variations "
            "WHERE id = 'global-roundtrip-second-org-extra'"
        ).fetchone() == ("needs_review",)
        assert connection.execute(
            "SELECT COUNT(*) FROM ingredient_variation_products "
            "WHERE variation_id = 'global-roundtrip-extra'"
        ).fetchone() == (2,)
        migration_audits = {
            row[0]: json.loads(row[1])
            for row in connection.execute(
                "SELECT organization_id, payload FROM audit_events "
                "WHERE action = 'catalog.global_comments_extras_migrated'"
            )
        }
        assert set(migration_audits) == {organization_id, second_organization_id}
        assert migration_audits[organization_id] == {
            "comment_presets": 1,
            "ingredient_variations_active": 0,
            "ingredient_variations_needs_review": 1,
        }
        assert migration_audits[second_organization_id] == {
            "comment_presets": 0,
            "ingredient_variations_active": 0,
            "ingredient_variations_needs_review": 1,
        }
    finally:
        connection.close()

    alembic("downgrade", "0027_catalog_cleanup")
    connection = sqlite3.connect(database_path)
    try:
        tables = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
        assert "order_comment_presets" not in tables and "order_comment_products" not in tables
        assert "ingredient_variation_0028_status_backups" not in tables
        columns = {row[1] for row in connection.execute("PRAGMA table_info(ingredient_variations)")}
        assert not {"portion_quantity", "sale_price_cents", "station", "display_order"} & columns
        assert connection.execute(
            "SELECT COUNT(*) FROM ingredient_variation_products "
            "WHERE variation_id = 'global-roundtrip-extra'"
        ).fetchone() == (2,)
        assert connection.execute(
            "SELECT status FROM ingredient_variations WHERE id = 'global-roundtrip-extra'"
        ).fetchone() == ("active",)
        assert connection.execute(
            "SELECT status FROM ingredient_variations "
            "WHERE id = 'global-roundtrip-second-org-extra'"
        ).fetchone() == ("archived",)
    finally:
        connection.close()

    alembic("upgrade", "0028_global_order_comments_extras")
    connection = sqlite3.connect(database_path)
    try:
        assert connection.execute(
            "SELECT status FROM ingredient_variations WHERE id = 'global-roundtrip-extra'"
        ).fetchone() == ("needs_review",)
        assert connection.execute(
            "SELECT status FROM ingredient_variations "
            "WHERE id = 'global-roundtrip-second-org-extra'"
        ).fetchone() == ("needs_review",)
        assert connection.execute("SELECT COUNT(*) FROM order_comment_products").fetchone() == (1,)
    finally:
        connection.close()


def test_order_amendments_deferred_payments_roundtrip(tmp_path: Path) -> None:
    database_path = tmp_path / "order-amendments-deferred-payments.db"
    env = {
        **os.environ,
        "RESTAURANTOS_DATABASE_URL": f"sqlite+pysqlite:///{database_path}",
    }

    def alembic(*arguments: str) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "-c", "alembic.ini", *arguments],
            cwd=ROOT / "apps" / "api",
            env=env,
            capture_output=True,
            text=True,
        )
        if result.returncode:
            raise AssertionError(result.stderr)

    alembic("upgrade", "head")
    connection = sqlite3.connect(database_path)
    try:
        tables = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
        assert "order_amendments" in tables
        order_columns = {row[1] for row in connection.execute("PRAGMA table_info(orders)")}
        line_columns = {row[1] for row in connection.execute("PRAGMA table_info(order_lines)")}
        assert {"payment_method_intent", "version"} <= order_columns
        assert {"status", "revision", "supersedes_line_id", "removed_at"} <= line_columns
        assert connection.execute(
            "SELECT COUNT(*) FROM permissions WHERE code = 'orders.amend'"
        ).fetchone() == (1,)
    finally:
        connection.close()

    alembic("downgrade", "0028_global_order_comments_extras")
    connection = sqlite3.connect(database_path)
    try:
        tables = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
        assert "order_amendments" not in tables
        assert "payment_method_intent" not in {
            row[1] for row in connection.execute("PRAGMA table_info(orders)")
        }
    finally:
        connection.close()

    alembic("upgrade", "head")
    connection = sqlite3.connect(database_path)
    try:
        assert connection.execute(
            "SELECT version_num FROM alembic_version"
        ).fetchone() == ("0037_cash_movement_ledger",)
    finally:
        connection.close()


def test_driver_catalog_roundtrip_and_data_guard(tmp_path: Path) -> None:
    database_path = tmp_path / "driver-catalog.db"
    env = {
        **os.environ,
        "RESTAURANTOS_DATABASE_URL": f"sqlite+pysqlite:///{database_path}",
    }

    def run_alembic(*arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "alembic", "-c", "alembic.ini", *arguments],
            cwd=ROOT / "apps" / "api",
            env=env,
            capture_output=True,
            text=True,
        )

    upgraded = run_alembic("upgrade", "head")
    assert upgraded.returncode == 0, upgraded.stderr
    connection = sqlite3.connect(database_path)
    try:
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(drivers)")
        }
        assert {
            "organization_id",
            "branch_id",
            "name",
            "license_number",
            "motorcycle_plate",
            "phone",
            "address",
            "emergency_contact_name",
            "status",
        } <= columns
    finally:
        connection.close()

    downgraded = run_alembic("downgrade", "0029_order_amendments_deferred")
    assert downgraded.returncode == 0, downgraded.stderr
    connection = sqlite3.connect(database_path)
    try:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        assert "drivers" not in tables
    finally:
        connection.close()

    assert run_alembic("upgrade", "head").returncode == 0
    connection = sqlite3.connect(database_path)
    try:
        organization_id = connection.execute(
            "SELECT id FROM organizations LIMIT 1"
        ).fetchone()[0]
        branch_id = connection.execute("SELECT id FROM branches LIMIT 1").fetchone()[0]
        connection.execute(
            """
            INSERT INTO drivers (
                id, organization_id, branch_id, name, license_number,
                motorcycle_plate, phone, address, emergency_contact_name,
                status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?)
            """,
            (
                "driver-migration-guard",
                organization_id,
                branch_id,
                "Repartidor prueba",
                "LIC-1",
                "PLACA-1",
                "6140000000",
                "Domicilio prueba",
                "Contacto prueba",
                "2026-07-23T01:00:00+00:00",
                "2026-07-23T01:00:00+00:00",
            ),
        )
        connection.commit()
    finally:
        connection.close()

    blocked = run_alembic("downgrade", "0029_order_amendments_deferred")
    assert blocked.returncode != 0
    assert "Cannot downgrade 0030 while driver records exist" in blocked.stderr


def test_delivery_assignments_roundtrip_and_data_guard(tmp_path: Path) -> None:
    database_path = tmp_path / "delivery-assignments.db"
    env = {
        **os.environ,
        "RESTAURANTOS_DATABASE_URL": f"sqlite+pysqlite:///{database_path}",
    }

    def run_alembic(*arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "alembic", "-c", "alembic.ini", *arguments],
            cwd=ROOT / "apps" / "api",
            env=env,
            capture_output=True,
            text=True,
        )

    upgraded = run_alembic("upgrade", "head")
    assert upgraded.returncode == 0, upgraded.stderr
    connection = sqlite3.connect(database_path)
    try:
        columns = {
            row[1]
            for row in connection.execute(
                "PRAGMA table_info(delivery_assignments)"
            )
        }
        assert {
            "order_id",
            "driver_id",
            "customer_id",
            "driver_name_snapshot",
            "customer_name_snapshot",
            "delivery_address_snapshot",
            "order_total_cents",
            "currency",
            "line_count",
            "item_quantity",
            "status",
            "assigned_by",
            "assigned_at",
        } <= columns
    finally:
        connection.close()

    downgraded = run_alembic("downgrade", "0030_driver_catalog")
    assert downgraded.returncode == 0, downgraded.stderr
    connection = sqlite3.connect(database_path)
    try:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        assert "delivery_assignments" not in tables
    finally:
        connection.close()

    assert run_alembic("upgrade", "head").returncode == 0
    connection = sqlite3.connect(database_path)
    try:
        organization_id = connection.execute(
            "SELECT id FROM organizations LIMIT 1"
        ).fetchone()[0]
        branch_id = connection.execute("SELECT id FROM branches LIMIT 1").fetchone()[0]
        user_id = connection.execute("SELECT id FROM users LIMIT 1").fetchone()[0]
        connection.execute(
            """
            INSERT INTO delivery_assignments (
                id, organization_id, branch_id, order_id, driver_id, customer_id,
                driver_name_snapshot, customer_name_snapshot,
                delivery_address_snapshot, order_total_cents, currency,
                line_count, item_quantity, status, assigned_by, assigned_at
            ) VALUES (?, ?, ?, ?, ?, NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "assignment-migration-guard",
                organization_id,
                branch_id,
                "order-migration-guard",
                "driver-migration-guard",
                "Repartidor prueba",
                "Cliente prueba",
                "{}",
                12500,
                "MXN",
                2,
                3,
                "ASSIGNED",
                user_id,
                "2026-07-23T02:30:00+00:00",
            ),
        )
        connection.commit()
    finally:
        connection.close()

    blocked = run_alembic("downgrade", "0030_driver_catalog")
    assert blocked.returncode != 0
    assert "Cannot downgrade 0031 while delivery assignments exist" in blocked.stderr


def test_attendance_clock_roundtrip_and_data_guard(tmp_path: Path) -> None:
    database_path = tmp_path / "attendance-clock.db"
    env = {
        **os.environ,
        "RESTAURANTOS_DATABASE_URL": f"sqlite+pysqlite:///{database_path}",
    }

    def run_alembic(*arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "alembic", "-c", "alembic.ini", *arguments],
            cwd=ROOT / "apps" / "api",
            env=env,
            capture_output=True,
            text=True,
        )

    upgraded = run_alembic("upgrade", "head")
    assert upgraded.returncode == 0, upgraded.stderr
    connection = sqlite3.connect(database_path)
    try:
        user_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(users)")
        }
        driver_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(drivers)")
        }
        attendance_columns = {
            row[1]
            for row in connection.execute("PRAGMA table_info(attendance_checks)")
        }
        assert "employee_code" in user_columns
        assert "employee_code" in driver_columns
        assert connection.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type = 'table' AND name = 'employee_code_registry'"
        ).fetchone() == ("employee_code_registry",)
        assert {
            "subject_type",
            "subject_id",
            "employee_code_snapshot",
            "employee_name_snapshot",
            "local_date",
            "daily_sequence",
            "checked_at",
            "created_by",
        } <= attendance_columns
    finally:
        connection.close()

    downgraded = run_alembic("downgrade", "0031_delivery_assignments")
    assert downgraded.returncode == 0, downgraded.stderr
    connection = sqlite3.connect(database_path)
    try:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        assert "attendance_checks" not in tables
        assert "employee_code_registry" not in tables
        assert "employee_code" not in {
            row[1] for row in connection.execute("PRAGMA table_info(users)")
        }
        assert "employee_code" not in {
            row[1] for row in connection.execute("PRAGMA table_info(drivers)")
        }
    finally:
        connection.close()

    assert run_alembic("upgrade", "head").returncode == 0
    connection = sqlite3.connect(database_path)
    try:
        organization_id = connection.execute(
            "SELECT id FROM organizations LIMIT 1"
        ).fetchone()[0]
        user_id = connection.execute("SELECT id FROM users LIMIT 1").fetchone()[0]
        connection.execute(
            """
            INSERT INTO employee_code_registry (
                organization_id, employee_code, subject_type, subject_id,
                created_at, updated_at
            ) VALUES (?, 'EMP001', 'user', ?, ?, ?)
            """,
            (organization_id, user_id, "2026-08-08T08:00:00+00:00", "2026-08-08T08:00:00+00:00"),
        )
        connection.execute(
            "UPDATE users SET employee_code = 'EMP001' WHERE id = ?", (user_id,)
        )
        connection.commit()
    finally:
        connection.close()

    blocked_code = run_alembic("downgrade", "0031_delivery_assignments")
    assert blocked_code.returncode != 0
    assert "Cannot downgrade 0032" in blocked_code.stderr

    connection = sqlite3.connect(database_path)
    try:
        organization_id = connection.execute(
            "SELECT id FROM organizations LIMIT 1"
        ).fetchone()[0]
        branch_id = connection.execute("SELECT id FROM branches LIMIT 1").fetchone()[0]
        user_id = connection.execute("SELECT id FROM users LIMIT 1").fetchone()[0]
        connection.execute("UPDATE users SET employee_code = NULL WHERE id = ?", (user_id,))
        connection.execute(
            "DELETE FROM employee_code_registry "
            "WHERE organization_id = ? AND employee_code = 'EMP001'",
            (organization_id,),
        )
        connection.execute(
            """
            INSERT INTO attendance_checks (
                id, organization_id, branch_id, subject_type, subject_id,
                employee_code_snapshot, employee_name_snapshot, local_date,
                daily_sequence, checked_at, created_by
            ) VALUES (?, ?, ?, 'user', ?, ?, ?, ?, 1, ?, ?)
            """,
            (
                "attendance-migration-guard",
                organization_id,
                branch_id,
                user_id,
                "HIS001",
                "Persona histórica",
                "2026-08-08",
                "2026-08-08T08:00:00+00:00",
                user_id,
            ),
        )
        connection.commit()
    finally:
        connection.close()

    blocked_history = run_alembic("downgrade", "0031_delivery_assignments")
    assert blocked_history.returncode != 0
    assert "Cannot downgrade 0032" in blocked_history.stderr


def test_superadmin_role_repair_is_idempotent_and_preserves_credentials(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "superadmin-role-repair.db"
    env = {
        **os.environ,
        "RESTAURANTOS_DATABASE_URL": f"sqlite+pysqlite:///{database_path}",
    }

    def run_alembic(*arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "alembic", "-c", "alembic.ini", *arguments],
            cwd=ROOT / "apps" / "api",
            env=env,
            capture_output=True,
            text=True,
        )

    upgraded = run_alembic("upgrade", "0032_attendance_clock")
    assert upgraded.returncode == 0, upgraded.stderr
    connection = sqlite3.connect(database_path)
    try:
        user_id = connection.execute(
            "SELECT id FROM users WHERE lower(email) = 'mangoex@gmail.com'"
        ).fetchone()[0]
        password_before = connection.execute(
            "SELECT password_hash, password_salt, password_algorithm "
            "FROM user_credentials WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        employee_code_before = connection.execute(
            "SELECT employee_code FROM users WHERE id = ?", (user_id,)
        ).fetchone()[0]
        connection.execute("DELETE FROM user_roles WHERE user_id = ?", (user_id,))
        connection.commit()
    finally:
        connection.close()

    repaired = run_alembic("upgrade", "head")
    assert repaired.returncode == 0, repaired.stderr
    connection = sqlite3.connect(database_path)
    try:
        assert connection.execute(
            "SELECT version_num FROM alembic_version"
        ).fetchone() == ("0037_cash_movement_ledger",)
        assert connection.execute(
            "SELECT COUNT(*) FROM user_roles WHERE user_id = ?",
            (user_id,),
        ).fetchone() == (1,)
        assert connection.execute(
            "SELECT password_hash, password_salt, password_algorithm "
            "FROM user_credentials WHERE user_id = ?",
            (user_id,),
        ).fetchone() == password_before
        assert connection.execute(
            "SELECT employee_code FROM users WHERE id = ?", (user_id,)
        ).fetchone()[0] == employee_code_before
        assert connection.execute(
            "SELECT COUNT(*) FROM audit_events "
            "WHERE action = 'platform.superadmin_role_restored'"
        ).fetchone() == (1,)
    finally:
        connection.close()

    downgraded = run_alembic("downgrade", "0032_attendance_clock")
    assert downgraded.returncode == 0, downgraded.stderr
    connection = sqlite3.connect(database_path)
    try:
        assert connection.execute(
            "SELECT COUNT(*) FROM user_roles WHERE user_id = ?", (user_id,)
        ).fetchone() == (1,)
    finally:
        connection.close()

    assert run_alembic("upgrade", "head").returncode == 0


def test_superadmin_role_repair_types_reused_postgresql_parameters() -> None:
    migration = (
        ROOT
        / "apps"
        / "api"
        / "alembic"
        / "versions"
        / "202608090100_0033_restore_superadmin_role.py"
    ).read_text(encoding="utf-8")

    assert "CAST(:user_id AS VARCHAR(36))" in migration
    assert "CAST(:role_id AS VARCHAR(36))" in migration
    assert "CAST(NULL AS VARCHAR(36))" in migration
