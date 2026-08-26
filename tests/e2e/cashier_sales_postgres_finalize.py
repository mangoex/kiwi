#!/usr/bin/env python3
"""Exercise negative branch scope and finalize user cash cuts through the local API."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import httpx
import sqlalchemy as sa


def _prepare_test_authority(database_url: str, repo_root: Path, cashier_id: str) -> int:
    parsed = urlparse(database_url)
    if (
        not parsed.scheme.startswith("postgresql")
        or parsed.hostname not in {"127.0.0.1", "localhost"}
        or parsed.port != 55432
        or parsed.path.lstrip("/") != "kiwi_cashier_e2e"
    ):
        raise RuntimeError("Refusing an unguarded cash-cut database target")
    sys.path.insert(0, str(repo_root / "apps/api"))
    from restaurant_os import models

    engine = sa.create_engine(database_url)
    now = datetime.now(timezone.utc)
    with engine.begin() as connection:
        admin_role_id = connection.execute(
            sa.select(models.roles.c.id)
            .select_from(
                models.roles.join(
                    models.user_roles, models.user_roles.c.role_id == models.roles.c.id
                ).join(models.users, models.users.c.id == models.user_roles.c.user_id)
            )
            .where(
                models.users.c.email == "mangoex@gmail.com", models.roles.c.scope == "organization"
            )
        ).scalar_one()
        for permission_id, code in (
            ("qa-cash-user-cut-read", "cash.user_cut.read"),
            ("qa-cash-user-cut-create", "cash.user_cut.create"),
        ):
            persisted_id = connection.execute(
                sa.select(models.permissions.c.id).where(models.permissions.c.code == code)
            ).scalar_one_or_none()
            if persisted_id is None:
                connection.execute(
                    models.permissions.insert().values(
                        id=permission_id,
                        code=code,
                        description=f"Synthetic E2E authority for {code}",
                        created_at=now,
                    )
                )
                persisted_id = permission_id
            assignment = connection.execute(
                sa.select(models.role_permissions.c.role_id).where(
                    models.role_permissions.c.role_id == admin_role_id,
                    models.role_permissions.c.permission_id == persisted_id,
                )
            ).scalar_one_or_none()
            if assignment is None:
                connection.execute(
                    models.role_permissions.insert().values(
                        role_id=admin_role_id, permission_id=persisted_id
                    )
                )

        denial_rows = connection.execute(
            sa.select(models.audit_events.c.payload).where(
                models.audit_events.c.action == "authorization.denied",
                models.audit_events.c.actor_user_id == cashier_id,
            )
        ).scalars()
        expected_denials = sum(
            1
            for payload in denial_rows
            if payload.get("permission") == "orders.create"
            and payload.get("reason") == "no_scoped_role"
        )
    engine.dispose()
    return expected_denials


def _login(client: httpx.Client, email: str, password: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    response.raise_for_status()
    return {"Authorization": f"Bearer {response.json()['token']}"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--result", required=True, type=Path)
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--base-url", default="http://127.0.0.1:8765")
    args = parser.parse_args()
    if args.base_url != "http://127.0.0.1:8765":
        raise RuntimeError("This test only permits the isolated local API")
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    if manifest.get("database_backend") != "postgresql" or not manifest.get("synthetic_only"):
        raise RuntimeError("Refusing non-synthetic or non-PostgreSQL evidence")

    cashiers = manifest["cashiers"]
    first_line = manifest["account_matrix"][0]["lines"][0]
    repo_root = Path(__file__).resolve().parents[2]
    prior_expected_denials = _prepare_test_authority(
        args.database_url, repo_root, cashiers[0]["user_id"]
    )
    with httpx.Client(base_url=args.base_url, timeout=30) as client:
        if prior_expected_denials == 0:
            cashier_headers = _login(client, cashiers[0]["email"], cashiers[0]["password"])
            denied = client.post(
                "/api/v1/orders",
                headers={**cashier_headers, "Idempotency-Key": "pg-e2e-cross-branch-denied-v1"},
                json={
                    "branch_id": cashiers[1]["branch_id"],
                    "lines": [{"product_id": first_line["product_id"], "quantity": 1}],
                },
            )
            if denied.status_code != 403 or denied.json()["detail"]["code"] != "permission_denied":
                raise AssertionError(
                    "Cross-branch command was not denied correctly: "
                    f"{denied.status_code} {denied.text}"
                )
            cross_branch_http_status = denied.status_code
            cross_branch_error_code = denied.json()["detail"]["code"]
        elif prior_expected_denials == 1:
            cross_branch_http_status = 403
            cross_branch_error_code = "permission_denied"
        else:
            raise AssertionError(
                f"Unexpected duplicate cross-branch denials: {prior_expected_denials}"
            )

        admin_headers = _login(client, "mangoex@gmail.com", "superadmin-test-password")
        cuts = []
        for index, cashier in enumerate(cashiers, start=1):
            page = client.get(
                "/api/v1/cash/shifts",
                headers=admin_headers,
                params={
                    "branch_id": cashier["branch_id"],
                    "register_id": cashier["register_id"],
                    "limit": 100,
                },
            )
            page.raise_for_status()
            shifts = page.json()["items"]
            if len(shifts) != 1 or shifts[0]["status"] != "OPERATIVELY_CLOSED":
                raise AssertionError(
                    f"Unexpected closed shift candidates for {cashier['branch_code']}"
                )
            shift_id = shifts[0]["id"]
            detail = client.get(f"/api/v1/cash/shifts/{shift_id}", headers=admin_headers)
            detail.raise_for_status()
            shift_detail = detail.json()
            shift = shift_detail["cash_shift"]
            closure = shift_detail["closure"]
            expected_cash_cents = int(closure["summary_snapshot"]["expected_cash_cents"])

            created = client.post(
                "/api/v1/cash/user-cuts",
                headers={**admin_headers, "Idempotency-Key": f"pg-e2e-cut-create-{index}"},
                json={
                    "branch_id": cashier["branch_id"],
                    "register_id": cashier["register_id"],
                    "cash_shift_id": shift_id,
                    "cashier_user_id": cashier["user_id"],
                    "period_start": shift["opened_at"],
                    "period_end": closure["closed_at"],
                },
            )
            created.raise_for_status()
            draft = created.json()["cash_cut"]
            counted = client.post(
                f"/api/v1/cash/user-cuts/{draft['id']}/counted-cash",
                headers={**admin_headers, "Idempotency-Key": f"pg-e2e-cut-count-{index}"},
                json={"counted_cash_cents": expected_cash_cents, "version": draft["version"]},
            )
            counted.raise_for_status()
            counted_cut = counted.json()["cash_cut"]
            finalized = client.post(
                f"/api/v1/cash/user-cuts/{draft['id']}/finalize",
                headers={**admin_headers, "Idempotency-Key": f"pg-e2e-cut-finalize-{index}"},
                json={"version": counted_cut["version"]},
            )
            finalized.raise_for_status()
            final_cut = finalized.json()["cash_cut"]
            if final_cut["status"] != "FINALIZED" or final_cut["difference_cents"] != 0:
                raise AssertionError(f"Unexpected final cash cut: {final_cut}")
            cuts.append(
                {
                    "branch_code": cashier["branch_code"],
                    "cash_shift_id": shift_id,
                    "cash_cut_id": final_cut["id"],
                    "expected_cash_cents": final_cut["expected_cash_cents"],
                    "counted_cash_cents": final_cut["counted_cash_cents"],
                    "difference_cents": final_cut["difference_cents"],
                    "status": final_cut["status"],
                }
            )

    result = {
        "status": "ok",
        "cross_branch": {
            "actor": cashiers[0]["email"],
            "attempted_branch": cashiers[1]["branch_code"],
            "http_status": cross_branch_http_status,
            "error_code": cross_branch_error_code,
            "reused_persisted_denial": prior_expected_denials == 1,
        },
        "cash_cuts": cuts,
    }
    args.result.parent.mkdir(parents=True, exist_ok=True)
    args.result.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"status": "ok", "cross_branch": 1, "finalized_cash_cuts": len(cuts)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
