#!/usr/bin/env python3
"""Seed the cashier journey in a guarded, disposable local PostgreSQL database."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from cashier_sales_fixture import (
    ACCOUNT_TARGETS_CENTS,
    EXPECTED_BRANCH_TOTAL_CENTS,
    PASSWORD,
    _exact_basket,
    _load_seed,
)

ITEM_COSTS = {
    "018f6f73-2d0a-74f0-8f1c-000000000311": Decimal("0.250000"),
    "018f6f73-2d0a-74f0-8f1c-000000000312": Decimal("4.000000"),
    "018f6f73-2d0a-74f0-8f1c-000000000313": Decimal("0.050000"),
    "018f6f73-2d0a-74f0-8f1c-000000000314": Decimal("0.020000"),
}


def _guarded_url(value: str) -> str:
    parsed = urlparse(value)
    database_name = parsed.path.lstrip("/")
    if not parsed.scheme.startswith("postgresql"):
        raise RuntimeError("The cashier E2E fixture requires PostgreSQL")
    if parsed.hostname not in {"127.0.0.1", "localhost"} or parsed.port != 55432:
        raise RuntimeError("The cashier E2E fixture requires local port 55432")
    if database_name != "kiwi_cashier_e2e":
        raise RuntimeError("The cashier E2E database name must equal kiwi_cashier_e2e")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--manifest", required=True, type=Path)
    args = parser.parse_args()
    database_url = _guarded_url(args.database_url)
    manifest_path = args.manifest.resolve()
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    repo_root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(repo_root / "apps/api"))
    os.environ.pop("DATABASE_URL", None)
    os.environ["RESTAURANTOS_ENVIRONMENT"] = "test"
    os.environ["RESTAURANTOS_DATABASE_URL"] = database_url
    os.environ["RESTAURANTOS_SECRET_KEY"] = "qa-local-only-secret-key-2026-not-production"

    import sqlalchemy as sa
    from fastapi.testclient import TestClient
    from restaurant_os import models
    from restaurant_os.main import create_app
    from sqlalchemy.orm import Session

    engine = sa.create_engine(database_url)
    with engine.begin() as connection:
        revision = connection.execute(
            sa.text("SELECT version_num FROM alembic_version")
        ).scalar_one()
        tables = connection.execute(
            sa.text(
                "SELECT tablename FROM pg_tables WHERE schemaname = 'public' "
                "AND tablename <> 'alembic_version'"
            )
        ).scalars()
        quoted = ", ".join(connection.dialect.identifier_preparer.quote(name) for name in tables)
        if quoted:
            connection.execute(sa.text(f"TRUNCATE TABLE {quoted} RESTART IDENTITY CASCADE"))

    with Session(engine) as session:
        _load_seed(repo_root)(session)

    app = create_app()
    with TestClient(app) as client:
        login = client.post(
            "/api/v1/auth/login",
            json={"email": "mangoex@gmail.com", "password": "superadmin-test-password"},
        )
        login.raise_for_status()
        headers = {"Authorization": f"Bearer {login.json()['token']}"}

        existing_branches = client.get("/api/v1/branches", headers=headers)
        existing_branches.raise_for_status()
        branches = [existing_branches.json()[0]]
        for number in range(2, 8):
            response = client.post(
                "/api/v1/branches",
                headers=headers,
                json={"name": f"Sucursal QA {number:02d}", "code": f"QA{number:02d}"},
            )
            response.raise_for_status()
            branches.append(response.json())

        role_response = client.post(
            "/api/v1/roles", headers=headers, json={"name": "Cajero", "scope": "branch"}
        )
        role_response.raise_for_status()
        role = role_response.json()

        cashiers: list[dict[str, Any]] = []
        for number, branch in enumerate(branches, start=1):
            email = f"cajero.qa{number:02d}@kiwi.local"
            response = client.post(
                "/api/v1/users",
                headers=headers,
                json={
                    "email": email,
                    "display_name": f"Cajero QA {number:02d}",
                    "employee_code": f"QA{number:04d}",
                    "password": PASSWORD,
                    "role_id": role["id"],
                    "branch_id": branch["id"],
                },
            )
            response.raise_for_status()
            cashiers.append(
                {
                    "user_id": response.json()["id"],
                    "branch_id": branch["id"],
                    "branch_name": branch["name"],
                    "branch_code": branch["code"],
                    "email": email,
                    "password": PASSWORD,
                    "register_id": f"Caja QA {number:02d}",
                }
            )

        catalog_response = client.get(
            f"/api/v1/catalog/products?branch_id={branches[0]['id']}", headers=headers
        )
        catalog_response.raise_for_status()
        account_matrix = [
            {
                "sequence": index,
                "target_cents": target_cents,
                "payment_method": ("cash", "debit_card", "transfer")[(index - 1) % 3],
                "lines": _exact_basket(target_cents, catalog_response.json()),
            }
            for index, target_cents in enumerate(ACCOUNT_TARGETS_CENTS, start=1)
        ]

    now = datetime.now(timezone.utc)
    with Session(engine) as session:
        warehouse_rows = session.execute(
            sa.select(models.warehouses.c.branch_id, models.warehouses.c.id).where(
                models.warehouses.c.branch_id.in_([branch["id"] for branch in branches])
            )
        ).all()
        warehouses = {str(row[0]): str(row[1]) for row in warehouse_rows}
        session.execute(
            models.inventory_cost_states.insert(),
            [
                {
                    "branch_id": branch["id"],
                    "warehouse_id": warehouses[branch["id"]],
                    "item_id": item_id,
                    "quantity_on_hand": Decimal("10000000.000000"),
                    "average_unit_cost": unit_cost,
                    "last_unit_cost": unit_cost,
                    "last_supplier_id": None,
                    "last_cost_at": now,
                    "updated_at": now,
                }
                for branch in branches
                for item_id, unit_cost in ITEM_COSTS.items()
            ],
        )
        session.commit()

    if sum(account["target_cents"] for account in account_matrix) != EXPECTED_BRANCH_TOTAL_CENTS:
        raise RuntimeError("Branch account matrix does not total exactly MXN 20,000")
    manifest = {
        "schema_version": 2,
        "database_backend": "postgresql",
        "database_name": urlparse(database_url).path.lstrip("/"),
        "alembic_revision": revision,
        "synthetic_only": True,
        "branch_count": len(cashiers),
        "accounts_per_branch": len(account_matrix),
        "expected_branch_total_cents": EXPECTED_BRANCH_TOTAL_CENTS,
        "cashiers": cashiers,
        "account_matrix": account_matrix,
        "item_costs_per_base_unit": {
            item_id: format(value, "f") for item_id, value in ITEM_COSTS.items()
        },
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "status": "ok",
                "backend": "postgresql",
                "alembic_revision": revision,
                "branches": len(cashiers),
                "accounts_per_branch": len(account_matrix),
                "cost_states": len(branches) * len(ITEM_COSTS),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
