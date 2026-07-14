from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


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
        supervisor = permissions_for("Supervisor de sucursal")
        receiver = permissions_for("Receptor de traspaso")
        auditor = permissions_for("Auditor")
        assert "purchases.manage" not in cashier
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
            "INSERT INTO ingredient_variations VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
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
