#!/usr/bin/env python3
"""Deterministically audit PostgreSQL cashier journeys, costing, closes and cuts."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import sqlalchemy as sa

SIX_PLACES = Decimal("0.000001")


def _decimal(value: Any) -> Decimal:
    return Decimal(str(value)).quantize(SIX_PLACES, rounding=ROUND_HALF_UP)


def _rows(
    connection: sa.Connection,
    query: str,
    parameters: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    return [dict(row) for row in connection.execute(sa.text(query), parameters or {}).mappings()]


def _guarded_url(value: str) -> str:
    parsed = urlparse(value)
    if (
        not parsed.scheme.startswith("postgresql")
        or parsed.hostname not in {"127.0.0.1", "localhost"}
        or parsed.port != 55432
        or parsed.path.lstrip("/") != "kiwi_cashier_e2e"
    ):
        raise RuntimeError("Refusing an unguarded PostgreSQL audit target")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--finalize-result", required=True, type=Path)
    parser.add_argument("--cross-branch-result", required=True, type=Path)
    parser.add_argument("--browser-result", required=True, action="append", type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    database_url = _guarded_url(args.database_url)
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    finalize_result = json.loads(args.finalize_result.read_text(encoding="utf-8"))
    cross_branch_result = json.loads(args.cross_branch_result.read_text(encoding="utf-8"))
    expected_branches = int(manifest["branch_count"])
    expected_targets = [int(row["target_cents"]) for row in manifest["account_matrix"]]
    expected_branch_total = int(manifest["expected_branch_total_cents"])
    expected_cashiers = {row["branch_code"]: row for row in manifest["cashiers"]}
    expected_method_totals = {
        method: sum(
            int(row["target_cents"])
            for row in manifest["account_matrix"]
            if row["payment_method"] == method
        )
        for method in ("cash", "debit_card", "transfer")
    }
    if len(args.browser_result) != expected_branches:
        raise AssertionError("One browser result per branch is required")

    browser_rows = []
    seen_branches: set[str] = set()
    for path in args.browser_result:
        evidence = json.loads(path.read_text(encoding="utf-8"))
        if len(evidence.get("branch_results", [])) != 1:
            raise AssertionError(f"Expected one browser branch in {path}")
        branch = evidence["branch_results"][0]
        branch_code = str(branch["branch_code"])
        expected_cashier = expected_cashiers.get(branch_code)
        if expected_cashier is None or branch_code in seen_branches:
            raise AssertionError(f"Duplicate or foreign browser branch: {branch_code}")
        seen_branches.add(branch_code)
        accounts_match = len(branch["accounts"]) == len(manifest["account_matrix"]) and all(
            observed["sequence"] == expected["sequence"]
            and observed["target_cents"] == expected["target_cents"]
            and observed["payment_method"] == expected["payment_method"]
            and observed["displayed_total"]
            == f"${Decimal(expected['target_cents']) / Decimal(100):,.2f}"
            for observed, expected in zip(branch["accounts"], manifest["account_matrix"])
        )
        if (
            evidence["status"] != "ok"
            or branch["branch_id"] != expected_cashier["branch_id"]
            or branch["cashier_email"] != expected_cashier["email"]
            or branch["operational_close_confirmed"] is not True
            or branch["account_count"] != len(expected_targets)
            or len(branch["accounts"]) != len(expected_targets)
            or branch["browser_total_cents"] != expected_branch_total
            or [row["target_cents"] for row in branch["accounts"]] != expected_targets
            or not all(row["success_dialog"] for row in branch["accounts"])
            or not accounts_match
        ):
            raise AssertionError(f"Invalid browser evidence: {path}")
        unexpected_console = [
            line
            for line in evidence["console_errors"].splitlines()
            if line.startswith("[ERROR]") and "fonts.googleapis.com" not in line
        ]
        failed_network = [
            line
            for line in evidence["network_requests"].splitlines()
            if "=> [FAILED]" in line and "fonts.googleapis.com" not in line
        ]
        if unexpected_console or failed_network:
            raise AssertionError(f"Browser errors in {path}: {unexpected_console + failed_network}")
        browser_rows.append(
            {
                "branch": branch["branch_code"],
                "cashier": branch["cashier_email"],
                "accounts": branch["account_count"],
                "total_cents": branch["browser_total_cents"],
                "operational_close_confirmed": True,
            }
        )
    if seen_branches != set(expected_cashiers):
        raise AssertionError(f"Incomplete browser branch set: {seen_branches}")

    cross_actor = expected_cashiers.get(str(cross_branch_result.get("actor_branch")))
    cross_target = expected_cashiers.get(str(cross_branch_result.get("attempted_branch")))
    if (
        finalize_result["status"] != "ok"
        or len(finalize_result["cash_cuts"]) != expected_branches
        or cross_branch_result["status"] != "ok"
        or cross_branch_result["executed"] is not True
        or cross_branch_result["http_status"] != 403
        or cross_branch_result["error_code"] != "permission_denied"
        or not cross_branch_result.get("started_at_utc")
        or not cross_branch_result.get("completed_at_utc")
        or cross_actor is None
        or cross_target is None
        or cross_actor["email"] != cross_branch_result.get("actor")
        or cross_actor["user_id"] != cross_branch_result.get("actor_user_id")
        or cross_target["branch_id"] != cross_branch_result.get("attempted_branch_id")
        or cross_actor["branch_id"] == cross_target["branch_id"]
    ):
        raise AssertionError("Invalid cross-branch or cash-cut evidence")

    engine = sa.create_engine(database_url)
    with engine.connect() as connection:
        revision = connection.execute(
            sa.text("SELECT version_num FROM alembic_version")
        ).scalar_one()
        persisted = _rows(
            connection,
            """
            SELECT b.code AS branch, u.email AS cashier, cs.register_code,
                   COUNT(DISTINCT o.id) AS orders, SUM(o.total_cents) AS order_cents,
                   COUNT(DISTINCT p.id) AS payments, SUM(p.amount_cents) AS paid_cents,
                   SUM(CASE WHEN p.method = 'cash' THEN p.amount_cents ELSE 0 END) AS cash_cents,
                   SUM(CASE WHEN p.method = 'debit_card'
                            THEN p.amount_cents ELSE 0 END) AS debit_cents,
                   SUM(CASE WHEN p.method = 'transfer'
                            THEN p.amount_cents ELSE 0 END) AS transfer_cents,
                   cs.opening_cash_cents, cs.status AS shift_status,
                   MAX(c.summary_snapshot::text) AS closure_summary_text,
                   MAX(uc.status) AS cut_status,
                   MAX(uc.expected_cash_cents) AS expected_cash_cents,
                   MAX(uc.counted_cash_cents) AS counted_cash_cents,
                   MAX(uc.difference_cents) AS difference_cents
              FROM branches b
              JOIN cash_shifts cs ON cs.branch_id = b.id
              JOIN users u ON u.id = cs.cashier_user_id
              JOIN orders o ON o.cash_shift_id = cs.id AND o.branch_id = b.id
              JOIN payments p ON p.order_id = o.id AND p.cash_shift_id = cs.id
              JOIN cash_shift_closures c ON c.cash_shift_id = cs.id
              JOIN user_cash_cuts uc ON uc.cash_shift_id = cs.id
             GROUP BY b.id, b.code, u.email, cs.id, cs.register_code,
                      cs.opening_cash_cents, cs.status
             ORDER BY b.code
            """,
        )
        if len(persisted) != expected_branches:
            raise AssertionError(f"Expected {expected_branches} persisted branches")
        for row in persisted:
            expected_cash = 715_500
            summary = json.loads(str(row.pop("closure_summary_text")))
            row["closure_summary"] = summary
            if (
                row["orders"] != len(expected_targets)
                or int(row["order_cents"]) != expected_branch_total
                or row["payments"] != len(expected_targets)
                or int(row["paid_cents"]) != expected_branch_total
                or int(row["cash_cents"]) != expected_method_totals["cash"]
                or int(row["debit_cents"]) != expected_method_totals["debit_card"]
                or int(row["transfer_cents"]) != expected_method_totals["transfer"]
                or row["shift_status"] != "OPERATIVELY_CLOSED"
                or row["cut_status"] != "FINALIZED"
                or int(row["expected_cash_cents"]) != expected_cash
                or int(row["counted_cash_cents"]) != expected_cash
                or int(row["difference_cents"]) != 0
                or int(summary["expected_cash_cents"]) != expected_cash
                or int(summary["sales_total_cents"]) != expected_branch_total
                or int(summary["payment_total_cents"]) != expected_branch_total
            ):
                raise AssertionError(f"Persisted financial mismatch: {row}")

        totals_by_branch: dict[str, list[int]] = {}
        for row in _rows(
            connection,
            "SELECT b.code AS branch, o.total_cents FROM branches b "
            "JOIN orders o ON o.branch_id = b.id ORDER BY b.code, o.total_cents",
        ):
            totals_by_branch.setdefault(str(row["branch"]), []).append(int(row["total_cents"]))
        for branch, totals in totals_by_branch.items():
            if totals != sorted(expected_targets):
                raise AssertionError(f"Target matrix drift for {branch}: {totals}")

        recipes: dict[str, dict[str, Any]] = {}
        for row in _rows(
            connection,
            """
            SELECT rc.recipe_id, rc.item_id, rc.unit_id, rc.net_quantity,
                   rc.gross_quantity, rc.waste_rate, r.yield_quantity
              FROM recipe_components rc JOIN recipes r ON r.id = rc.recipe_id
            """,
        ):
            recipe = recipes.setdefault(
                str(row["recipe_id"]),
                {"yield_quantity": _decimal(row["yield_quantity"]), "components": {}},
            )
            recipe["components"][str(row["item_id"])] = row
        costs = {
            (str(row["branch_id"]), str(row["item_id"])): _decimal(row["average_unit_cost"])
            for row in _rows(
                connection,
                "SELECT branch_id, item_id, average_unit_cost FROM inventory_cost_states",
            )
        }

        snapshot_mismatches = 0
        total_theoretical_cost = Decimal("0")
        snapshot_rows = _rows(
            connection,
            """
            SELECT s.branch_id, s.recipe_id, s.components, s.total_theoretical_cost,
                   ol.quantity
              FROM order_line_consumption_snapshots s
              JOIN order_lines ol ON ol.id = s.order_line_id
            """,
        )
        for row in snapshot_rows:
            source = recipes[str(row["recipe_id"])]
            observed_components = row["components"]
            if isinstance(observed_components, str):
                observed_components = json.loads(observed_components)
            observed = {str(component["item_id"]): component for component in observed_components}
            expected = source["components"]
            expected_total = Decimal("0")
            if set(observed) != set(expected):
                snapshot_mismatches += 1
                continue
            quantity = Decimal(str(row["quantity"]))
            for item_id, component in expected.items():
                unit_cost = costs[(str(row["branch_id"]), item_id)]
                net = _decimal(
                    Decimal(str(component["net_quantity"])) / source["yield_quantity"] * quantity
                )
                gross = _decimal(
                    Decimal(str(component["gross_quantity"])) / source["yield_quantity"] * quantity
                )
                component_cost = _decimal(gross * unit_cost)
                expected_total += component_cost
                snapshot = observed[item_id]
                if (
                    str(snapshot["unit_id"]) != str(component["unit_id"])
                    or _decimal(snapshot["net_quantity"]) != net
                    or _decimal(snapshot["gross_quantity"]) != gross
                    or _decimal(snapshot["waste_rate"]) != _decimal(component["waste_rate"])
                    or _decimal(snapshot["unit_cost"]) != unit_cost
                    or _decimal(snapshot["total_cost"]) != component_cost
                ):
                    snapshot_mismatches += 1
                    break
            expected_total = _decimal(expected_total)
            if _decimal(row["total_theoretical_cost"]) != expected_total:
                snapshot_mismatches += 1
            total_theoretical_cost += _decimal(row["total_theoretical_cost"])

        integrity = dict(
            connection.execute(
                sa.text(
                    """
                    SELECT
                      (SELECT COUNT(*) FROM orders) AS orders,
                      (SELECT COUNT(*) FROM orders
                        WHERE status = 'ACCEPTED') AS accepted_orders,
                      (SELECT COUNT(*) FROM payments WHERE status = 'CONFIRMED') AS payments,
                      (SELECT COUNT(*) FROM order_lines) AS order_lines,
                      (SELECT COUNT(*) FROM order_line_consumption_snapshots) AS snapshots,
                      (SELECT COUNT(*) FROM order_line_consumption_snapshots
                        WHERE total_theoretical_cost > 0) AS nonzero_cost_snapshots,
                      (SELECT COUNT(*) FROM cash_shifts
                        WHERE status = 'OPERATIVELY_CLOSED') AS operationally_closed_shifts,
                      (SELECT COUNT(*) FROM cash_shift_closures) AS closures,
                      (SELECT COUNT(*) FROM user_cash_cuts
                        WHERE status = 'FINALIZED') AS finalized_cash_cuts,
                      (SELECT COUNT(*) FROM user_cash_cut_operations) AS cut_operations,
                      (SELECT COUNT(*) FROM orders
                        WHERE cash_shift_id IS NULL) AS orders_without_shift
                    """
                )
            )
            .mappings()
            .one()
        )
        expected_orders = expected_branches * len(expected_targets)
        if (
            integrity["orders"] != expected_orders
            or integrity["accepted_orders"] != expected_orders
            or integrity["payments"] != expected_orders
            or integrity["order_lines"] != integrity["snapshots"]
            or integrity["snapshots"] != integrity["nonzero_cost_snapshots"]
            or integrity["operationally_closed_shifts"] != expected_branches
            or integrity["closures"] != expected_branches
            or integrity["finalized_cash_cuts"] != expected_branches
            or integrity["cut_operations"] != expected_branches * 3
            or integrity["orders_without_shift"] != 0
            or snapshot_mismatches != 0
        ):
            raise AssertionError(
                f"PostgreSQL integrity mismatch: {integrity}, snapshots={snapshot_mismatches}"
            )

        denials = _rows(
            connection,
            """
            SELECT u.email AS actor, ae.payload
              FROM audit_events ae LEFT JOIN users u ON u.id = ae.actor_user_id
             WHERE ae.action = 'authorization.denied'
             ORDER BY ae.created_at
            """,
        )
        correlated_denials = _rows(
            connection,
            """
            SELECT ae.id, ae.branch_id, ae.actor_user_id, ae.payload, ae.created_at
              FROM audit_events ae
             WHERE ae.action = 'authorization.denied'
               AND ae.actor_user_id = :actor_user_id
               AND ae.branch_id = :branch_id
               AND ae.created_at >= :started_at
               AND ae.created_at <= :completed_at
             ORDER BY ae.created_at
            """,
            {
                "actor_user_id": cross_branch_result["actor_user_id"],
                "branch_id": cross_branch_result["attempted_branch_id"],
                "started_at": datetime.fromisoformat(cross_branch_result["started_at_utc"]),
                "completed_at": datetime.fromisoformat(cross_branch_result["completed_at_utc"]),
            },
        )
        if len(correlated_denials) != 1 or correlated_denials[0]["payload"] != {
            "permission": "orders.create",
            "reason": "no_scoped_role",
        }:
            raise AssertionError(
                f"Cross-branch denial is not correlated in PostgreSQL: {correlated_denials}"
            )
        cross_window_orders = connection.execute(
            sa.text(
                """
                SELECT COUNT(*) FROM orders
                 WHERE branch_id = :branch_id
                   AND created_at >= :started_at
                   AND created_at <= :completed_at
                """
            ),
            {
                "branch_id": cross_branch_result["attempted_branch_id"],
                "started_at": datetime.fromisoformat(cross_branch_result["started_at_utc"]),
                "completed_at": datetime.fromisoformat(cross_branch_result["completed_at_utc"]),
            },
        ).scalar_one()
        if cross_window_orders != 0:
            raise AssertionError(
                f"Cross-branch request created {cross_window_orders} target-branch orders"
            )
    engine.dispose()

    report = {
        "status": "green_with_declared_limits",
        "backend": "postgresql",
        "alembic_revision": revision,
        "synthetic_only": True,
        "browser": {"branches": browser_rows, "bounded_mcp_runner": True},
        "cross_branch": cross_branch_result,
        "persistence": {
            "branches": persisted,
            "integrity": integrity,
            "snapshot_exact_mismatches": snapshot_mismatches,
            "total_theoretical_cost": format(_decimal(total_theoretical_cost), "f"),
            "global_sales_cents": expected_branches * expected_branch_total,
        },
        "authorization_denials": denials,
        "correlated_cross_branch_denial": correlated_denials[0],
        "cross_branch_target_orders_in_window": cross_window_orders,
        "declared_limits": [
            "Synthetic branches, cashiers, products, recipes and costs; "
            "production data was not used.",
            "The user journeys were sequential; same-register concurrency was not exercised.",
            "Cashiers performed operational close; the administrator finalized user cash cuts "
            "because the Cajero profile intentionally lacks cash.user_cut.create.",
            "One failed administrative cut attempt exposed and then corrected a fixture-only "
            "RBAC seed omission; it created no cut or financial operation.",
            "Canonical migration-seeded RBAC was not validated because fixture truncation removed "
            "it; test-only permission inserts do not prove production readiness.",
            "The direct MCP client proves bounded tool use by this runner, not a fail-closed "
            "approval layer for every exposed server tool.",
        ],
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "status": report["status"],
                "branches": len(persisted),
                "orders": integrity["orders"],
                "global_sales_cents": report["persistence"]["global_sales_cents"],
                "nonzero_cost_snapshots": integrity["nonzero_cost_snapshots"],
                "snapshot_exact_mismatches": snapshot_mismatches,
                "finalized_cash_cuts": integrity["finalized_cash_cuts"],
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
