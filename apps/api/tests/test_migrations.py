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
            "purchases.manage",
            "production.manage",
            "inventory.waste",
            "inventory.transfer.send",
            "inventory.count",
        } <= supervisor
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
