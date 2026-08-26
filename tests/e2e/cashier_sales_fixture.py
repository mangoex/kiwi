#!/usr/bin/env python3
"""Create a disposable seven-branch cashier fixture for browser user journeys.

This script is intentionally test-only. It creates a new SQLite database and
refuses to overwrite an existing file. All monetary values are integer cents;
the order matrix is solved deterministically from the server-side seed prices.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from pathlib import Path
from typing import Any

ACCOUNT_TARGETS_CENTS = (3000, 9500, 25000, 62500, 100000, 200000, 600000, 1000000)
EXPECTED_BRANCH_TOTAL_CENTS = 2_000_000
PASSWORD = "QA-Cashier-2026!"


def _load_seed(repo_root: Path) -> Any:
    module_path = repo_root / "apps/api/tests/test_platform_api.py"
    spec = importlib.util.spec_from_file_location("restaurantos_platform_test_seed", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load fixture seed from {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module._seed


def _exact_basket(target_cents: int, catalog: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return the fewest-item exact basket, with stable SKU tie-breaking."""
    priced = sorted(
        (
            (
                int(product["price_cents"]),
                str(product["sku"]),
                str(product["id"]),
                str(product["name"]),
            )
            for product in catalog
            if isinstance(product.get("price_cents"), int) and int(product["price_cents"]) > 0
        ),
        key=lambda row: (-row[0], row[1]),
    )
    best: list[tuple[int, int] | None] = [None] * (target_cents + 1)
    best[0] = (0, -1)
    for amount in range(1, target_cents + 1):
        winner: tuple[int, int] | None = None
        for index, (price, _sku, _product_id, _name) in enumerate(priced):
            if price > amount or best[amount - price] is None:
                continue
            candidate = (best[amount - price][0] + 1, index)
            if winner is None or candidate < winner:
                winner = candidate
        best[amount] = winner
    if best[target_cents] is None:
        raise RuntimeError(f"No exact catalog basket for {target_cents} cents")

    quantities: dict[int, int] = {}
    remaining = target_cents
    while remaining:
        step = best[remaining]
        if step is None:
            raise RuntimeError(f"Broken deterministic basket at {remaining} cents")
        index = step[1]
        quantities[index] = quantities.get(index, 0) + 1
        remaining -= priced[index][0]

    return [
        {
            "product_id": priced[index][2],
            "sku": priced[index][1],
            "name": priced[index][3],
            "unit_price_cents": priced[index][0],
            "quantity": quantity,
            "line_total_cents": priced[index][0] * quantity,
        }
        for index, quantity in sorted(quantities.items())
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    args = parser.parse_args()

    database_path = args.database.resolve()
    manifest_path = args.manifest.resolve()
    if database_path.exists():
        raise SystemExit(f"Refusing to overwrite existing database: {database_path}")
    database_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    repo_root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(repo_root / "apps/api"))
    os.environ["RESTAURANTOS_ENVIRONMENT"] = "test"
    os.environ["RESTAURANTOS_DATABASE_URL"] = f"sqlite+pysqlite:///{database_path}"
    os.environ["RESTAURANTOS_SECRET_KEY"] = "qa-local-only-secret-key-2026-not-production"

    import sqlalchemy as sa
    from fastapi.testclient import TestClient
    from restaurant_os import models
    from restaurant_os.main import create_app
    from sqlalchemy.orm import Session

    engine = sa.create_engine(os.environ["RESTAURANTOS_DATABASE_URL"])
    models.metadata.create_all(engine)
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
        required_permissions = {
            "cash.shift.read",
            "cash.shift.open",
            "cash.shift.close",
            "orders.read",
            "orders.create",
            "orders.amend",
            "payments.confirm",
            "pos.operate",
        }
        if not required_permissions.issubset(set(role["permissions"])):
            missing_permissions = required_permissions - set(role["permissions"])
            raise RuntimeError(f"Cashier role lacks permissions: {sorted(missing_permissions)}")

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
            if not response.is_success:
                raise RuntimeError(
                    f"Cashier creation failed for {email}: {response.status_code} {response.text}"
                )
            cashiers.append(
                {
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
        catalog = catalog_response.json()
        account_matrix = []
        for index, target_cents in enumerate(ACCOUNT_TARGETS_CENTS, start=1):
            basket = _exact_basket(target_cents, catalog)
            if sum(line["line_total_cents"] for line in basket) != target_cents:
                raise RuntimeError("Deterministic basket total mismatch")
            account_matrix.append(
                {
                    "sequence": index,
                    "target_cents": target_cents,
                    "payment_method": ("cash", "debit_card", "transfer")[((index - 1) % 3)],
                    "lines": basket,
                }
            )

    if sum(account["target_cents"] for account in account_matrix) != EXPECTED_BRANCH_TOTAL_CENTS:
        raise RuntimeError("Branch account matrix does not total exactly MXN 20,000")

    manifest = {
        "schema_version": 1,
        "database_url": os.environ["RESTAURANTOS_DATABASE_URL"],
        "synthetic_only": True,
        "branch_count": len(cashiers),
        "accounts_per_branch": len(account_matrix),
        "expected_branch_total_cents": EXPECTED_BRANCH_TOTAL_CENTS,
        "cashiers": cashiers,
        "account_matrix": account_matrix,
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "status": "ok",
                "database": str(database_path),
                "manifest": str(manifest_path),
                "branches": len(cashiers),
                "accounts_per_branch": len(account_matrix),
                "expected_branch_total_cents": EXPECTED_BRANCH_TOTAL_CENTS,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
