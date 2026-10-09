"""AUD-CORE historical inspection; never repairs data or uses the application's URL."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import sqlalchemy as sa
from sqlalchemy.engine import Connection, Engine, make_url
from sqlalchemy.orm import Session

from restaurant_os import models
from restaurant_os.operations import BusinessError, _money, _quantity
from restaurant_os.purchase_confirmation import original_effects


@contextmanager
def readonly_snapshot(engine: Engine) -> Iterator[Connection]:
    """Use a dedicated inspection engine; its SQLite pool remains query-only."""
    if engine.dialect.name not in {"sqlite", "postgresql"}:
        raise ValueError("Unsupported diagnostic database")
    if engine.dialect.name == "sqlite" and engine.url.database in {None, "", ":memory:"}:
        raise ValueError("Diagnostics require an existing SQLite file")
    with engine.connect() as connection:
        if engine.dialect.name == "postgresql":
            connection = connection.execution_options(isolation_level="REPEATABLE READ")
            connection.begin()
            connection.exec_driver_sql("SET TRANSACTION READ ONLY")
            connection.exec_driver_sql("SET LOCAL statement_timeout = '20s'")
            connection.exec_driver_sql("SET LOCAL lock_timeout = '2s'")
        else:
            connection.exec_driver_sql("PRAGMA query_only = ON")
            connection.exec_driver_sql("BEGIN")
        try:
            yield connection
        finally:
            connection.rollback()


def diagnostic_engine(url: str) -> Engine:
    parsed = make_url(url)
    if parsed.get_backend_name() == "sqlite":
        if not parsed.database or parsed.database == ":memory:" or parsed.query:
            raise ValueError("Diagnostics require an existing SQLite file")
        path = Path(parsed.database).resolve(strict=True)
        if not path.is_file():
            raise ValueError("Diagnostics require an existing SQLite file")
        parsed = parsed.set(database=path.as_uri(), query={"mode": "ro", "uri": "true"})
    elif parsed.get_backend_name() != "postgresql":
        raise ValueError("Unsupported diagnostic database")
    return sa.create_engine(parsed, poolclass=sa.pool.NullPool)


def _reversal_checks(
    session: Session, organization_id: str, limit: int
) -> tuple[list[dict[str, str]], bool]:
    findings: list[dict[str, str]] = []
    partial = False
    common = (
        "id",
        "organization_id",
        "branch_id",
        "status",
        "source_type",
        "source_id",
        "movement_type",
        "reversal_of_id",
    )
    for kind, table in (("cash", models.cash_movements), ("inventory", models.inventory_movements)):
        parent = table.alias(f"{kind}_original")
        reference = (
            sa.func.coalesce(table.c.compensates_movement_id, table.c.reversal_of_id)
            if kind == "cash"
            else table.c.reversal_of_id
        )
        fields: tuple[str, ...]
        original_kind: sa.ColumnElement[bool]
        if kind == "cash":
            fields = common + ("cash_shift_id", "amount_cents", "compensates_movement_id")
            original_kind = sa.func.upper(parent.c.source_type).in_(("PURCHASE", "EXPENSE"))
            candidate = sa.or_(
                sa.func.upper(table.c.source_type).in_(
                    ("PURCHASE_CANCELLATION", "EXPENSE_CANCELLATION")
                ),
                original_kind,
            )
        else:
            fields = common + (
                "warehouse_id",
                "item_id",
                "unit_id",
                "quantity_delta",
                "unit_cost",
                "total_cost",
                "document_id",
                "document_type",
            )
            original_kind = parent.c.movement_type == "PURCHASE_RECEIPT"
            candidate = sa.or_(
                sa.func.upper(table.c.source_type) == "PURCHASE_CANCELLATION",
                table.c.movement_type == "PURCHASE_REVERSAL",
            )
        incoming_conflicts: list[str] = list(
            session.execute(
                sa.select(parent.c.id)
                .select_from(parent.join(table, reference == parent.c.id))
                .where(
                    parent.c.organization_id == organization_id,
                    original_kind,
                    sa.or_(
                        table.c.organization_id != organization_id,
                        table.c.branch_id != parent.c.branch_id,
                    ),
                )
                .distinct()
                .order_by(parent.c.id)
                .limit(limit + 1)
            )
            .scalars()
            .all()
        )
        partial = partial or len(incoming_conflicts) > limit
        for identifier in incoming_conflicts[:limit]:
            findings.append(
                {
                    "code": f"document_{kind}_reversal_scope_conflict",
                    "table": table.name,
                    "record_id": identifier,
                }
            )
        duplicates: list[str] = list(
            session.execute(
                sa.select(parent.c.id)
                .select_from(parent.join(table, reference == parent.c.id))
                .where(parent.c.organization_id == organization_id, original_kind)
                .group_by(parent.c.id)
                .having(sa.func.count() > 1)
                .order_by(parent.c.id)
                .limit(limit + 1)
            )
            .scalars()
            .all()
        )
        partial = partial or len(duplicates) > limit
        for identifier in duplicates[:limit]:
            findings.append(
                {
                    "code": f"duplicate_document_{kind}_reversal",
                    "table": table.name,
                    "record_id": identifier,
                }
            )
        rows = (
            session.execute(
                sa.select(
                    *(table.c[name].label("child_" + name) for name in fields),
                    *(parent.c[name].label("parent_" + name) for name in fields),
                )
                .select_from(table.outerjoin(parent, reference == parent.c.id))
                .where(table.c.organization_id == organization_id, candidate)
                .order_by(table.c.id)
                .limit(limit + 1)
            )
            .mappings()
            .all()
        )
        partial = partial or len(rows) > limit
        for row in rows[:limit]:
            valid = (
                row["parent_id"] is not None
                and row["parent_reversal_of_id"] is None
                and row["parent_organization_id"] == organization_id
                and row["parent_branch_id"] == row["child_branch_id"]
                and row["child_status"] == row["parent_status"] == "confirmed"
            )
            source = str(row["child_source_type"] or "").upper()
            if kind == "cash":
                original_source = str(row["parent_source_type"] or "").upper()
                valid = (
                    valid
                    and row["parent_compensates_movement_id"] is None
                    and row["parent_cash_shift_id"] == row["child_cash_shift_id"]
                    and row["parent_amount_cents"] == row["child_amount_cents"]
                    and (row["parent_movement_type"], row["child_movement_type"])
                    in {("withdrawal", "deposit"), ("deposit", "withdrawal")}
                    and (source, original_source)
                    in {
                        ("PURCHASE_CANCELLATION", "PURCHASE"),
                        ("EXPENSE_CANCELLATION", "EXPENSE"),
                        ("COMPENSATION", "PURCHASE"),
                    }
                    and (
                        row["child_reversal_of_id"] is None
                        or row["child_compensates_movement_id"] is None
                        or row["child_reversal_of_id"] == row["child_compensates_movement_id"]
                    )
                    and (
                        source == "COMPENSATION"
                        or row["child_source_id"] == row["parent_source_id"]
                    )
                )
            else:
                valid = (
                    valid
                    and source == "PURCHASE_CANCELLATION"
                    and row["parent_movement_type"] == "PURCHASE_RECEIPT"
                    and row["child_movement_type"] == "PURCHASE_REVERSAL"
                    and all(
                        row["child_" + field] == row["parent_" + field]
                        for field in (
                            "warehouse_id",
                            "item_id",
                            "unit_id",
                            "unit_cost",
                            "source_id",
                            "document_id",
                            "document_type",
                        )
                    )
                )
                if valid:
                    valid = row["child_quantity_delta"] == -_quantity(
                        row["parent_quantity_delta"]
                    ) and row["child_total_cost"] == -_money(row["parent_total_cost"])
            if not valid:
                findings.append(
                    {
                        "code": f"document_{kind}_reversal_integrity_conflict",
                        "table": table.name,
                        "record_id": row["child_id"],
                    }
                )
    return findings, partial


def diagnose(engine: Engine, organization_id: str, limit: int = 100) -> dict[str, Any]:
    if not organization_id.strip() or len(organization_id) > 36 or not 1 <= limit <= 1000:
        raise ValueError("Invalid diagnostic scope or limit")
    with readonly_snapshot(engine) as connection, Session(bind=connection) as session:
        if not session.scalar(
            sa.select(models.organizations.c.id).where(models.organizations.c.id == organization_id)
        ):
            raise ValueError("Diagnostic organization not found")
        purchases = models.purchase_documents
        count = session.scalar(
            sa.select(sa.func.count())
            .select_from(purchases)
            .where(purchases.c.organization_id == organization_id)
        )
        rows = (
            session.execute(
                sa.select(purchases)
                .where(purchases.c.organization_id == organization_id)
                .order_by(purchases.c.id)
                .limit(limit)
            )
            .mappings()
            .all()
        )
        findings: list[dict[str, str]] = []
        periods: set[tuple[str, str]] = set()
        coverage_partial = len(rows) < int(count or 0)

        def record(code: str, table: str, identifier: str) -> None:
            nonlocal coverage_partial
            if len(findings) < limit:
                findings.append({"code": code, "table": table, "record_id": identifier})
            else:
                coverage_partial = True

        branch_zones: dict[str, str] = dict(
            session.execute(
                sa.select(models.branches.c.id, models.branches.c.timezone).where(
                    models.branches.c.organization_id == organization_id
                )
            ).all()
        )
        for row in rows:
            if row["branch_id"] not in branch_zones:
                record("purchase_branch_scope_conflict", purchases.name, row["id"])
                continue
            cash_method = row["payment_method"] == "cash"
            if cash_method != bool(row["paid_from_cash"]):
                record("purchase_cash_flag_conflict", purchases.name, row["id"])
            has_confirmation = (
                row["confirmed_at"] is not None
                or row["status"] == "confirmed"
                or row["cash_movement_id"] is not None
                or row["confirmed_by"] is not None
                or row["confirmation_idempotency_key"] is not None
            )
            if not has_confirmation:
                has_confirmation = bool(
                    session.scalar(
                        sa.select(
                            sa.exists().where(
                                models.inventory_movements.c.movement_type == "PURCHASE_RECEIPT",
                                sa.or_(
                                    models.inventory_movements.c.source_id == row["id"],
                                    models.inventory_movements.c.document_id == row["id"],
                                ),
                            )
                        )
                    )
                ) or bool(
                    session.scalar(
                        sa.select(
                            sa.exists().where(
                                sa.func.upper(models.cash_movements.c.source_type) == "PURCHASE",
                                models.cash_movements.c.source_id == row["id"],
                            )
                        )
                    )
                )
            if has_confirmation:
                if row["confirmed_at"] is None:
                    record("purchase_confirmation_event_missing", purchases.name, row["id"])
                try:
                    original_effects(session, row)
                except (BusinessError, sa.exc.NoResultFound):
                    record("purchase_original_integrity_conflict", purchases.name, row["id"])
            if cash_method or row["paid_from_cash"]:
                for timestamp in (row["confirmed_at"], row["cancelled_at"]):
                    if timestamp is not None:
                        aware = (
                            timestamp
                            if timestamp.tzinfo
                            else timestamp.replace(tzinfo=timezone.utc)
                        )
                        day = aware.astimezone(ZoneInfo(branch_zones[row["branch_id"]])).date()
                        periods.add((row["branch_id"], day.isoformat()))

        # Queries project only opaque identifiers owned by the requested organization.
        for table, parent, parent_column, source_types in (
            (
                models.cash_movements,
                purchases,
                models.cash_movements.c.source_id,
                ("PURCHASE", "PURCHASE_CANCELLATION"),
            ),
            (
                models.inventory_movements,
                purchases,
                models.inventory_movements.c.source_id,
                ("PURCHASE", "PURCHASE_CANCELLATION"),
            ),
            (
                models.cash_movements,
                models.expense_documents,
                models.cash_movements.c.source_id,
                ("EXPENSE", "EXPENSE_CANCELLATION"),
            ),
        ):
            invalid: list[str] = list(
                session.execute(
                    sa.select(table.c.id)
                    .select_from(table.outerjoin(parent, parent_column == parent.c.id))
                    .where(
                        table.c.organization_id == organization_id,
                        sa.func.upper(table.c.source_type).in_(source_types),
                        sa.or_(
                            parent.c.id.is_(None),
                            parent.c.organization_id != organization_id,
                            parent.c.branch_id != table.c.branch_id,
                            parent.c.status == "draft",
                        ),
                    )
                    .order_by(table.c.id)
                    .limit(limit + 1)
                )
                .scalars()
                .all()
            )
            coverage_partial = coverage_partial or len(invalid) > limit
            for identifier in invalid[:limit]:
                code = (
                    "purchase_effect_parent_conflict"
                    if parent is purchases
                    else "expense_effect_parent_conflict"
                )
                record(code, table.name, identifier)

        reversal_findings, reversal_partial = _reversal_checks(session, organization_id, limit)
        coverage_partial = coverage_partial or reversal_partial
        for finding in reversal_findings:
            record(finding["code"], finding["table"], finding["record_id"])

        terms = models.supplier_branch_terms
        supplier = models.suppliers
        branch = models.branches
        inconsistent_terms = (
            session.execute(
                sa.select(
                    terms.c.supplier_id,
                    terms.c.branch_id,
                    supplier.c.organization_id.label("supplier_org"),
                    branch.c.organization_id.label("branch_org"),
                )
                .select_from(
                    terms.outerjoin(supplier, supplier.c.id == terms.c.supplier_id).outerjoin(
                        branch, branch.c.id == terms.c.branch_id
                    )
                )
                .where(
                    sa.or_(
                        supplier.c.organization_id == organization_id,
                        branch.c.organization_id == organization_id,
                    ),
                    sa.or_(
                        supplier.c.id.is_(None),
                        branch.c.id.is_(None),
                        supplier.c.organization_id != branch.c.organization_id,
                    ),
                )
                .order_by(terms.c.supplier_id, terms.c.branch_id)
                .limit(limit + 1)
            )
            .mappings()
            .all()
        )
        coverage_partial = coverage_partial or len(inconsistent_terms) > limit
        for term in inconsistent_terms[:limit]:
            owned_branch = term["branch_org"] == organization_id
            record(
                "supplier_terms_scope_conflict",
                "branches" if owned_branch else "suppliers",
                term["branch_id"] if owned_branch else term["supplier_id"],
            )

        costs = models.inventory_cost_states
        negative_stock: list[str] = list(
            session.execute(
                sa.select(costs.c.branch_id)
                .select_from(costs.join(branch, branch.c.id == costs.c.branch_id))
                .where(branch.c.organization_id == organization_id, costs.c.quantity_on_hand < 0)
                .order_by(costs.c.branch_id, costs.c.warehouse_id, costs.c.item_id)
                .limit(limit + 1)
            )
            .scalars()
            .all()
        )
        coverage_partial = coverage_partial or len(negative_stock) > limit
        for identifier in negative_stock[:limit]:
            record("negative_stock_requires_investigation", "branches", identifier)

        return {
            "organization_id": organization_id,
            "purchase_count": count,
            "purchases_scanned": len(rows),
            "coverage_partial": coverage_partial,
            "findings": findings,
            "periods_requiring_review": [
                {"branch_id": branch_id, "date": day} for branch_id, day in sorted(periods)
            ],
            "historical_report_execution_known": False,
            "stock_causation_confirmed": False,
            "repairs_performed": False,
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--organization-id", required=True)
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args()
    url = os.environ.get("AUDCORE_DIAGNOSTIC_DATABASE_URL")
    if not url:
        print("Diagnostic database URL must be supplied explicitly.", file=sys.stderr)
        return 2
    engine = None
    try:
        engine = diagnostic_engine(url)
        print(json.dumps(diagnose(engine, args.organization_id, args.limit), sort_keys=True))
        return 0
    except Exception:
        print("Diagnostic failed; no successful report was produced.", file=sys.stderr)
        return 2
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
