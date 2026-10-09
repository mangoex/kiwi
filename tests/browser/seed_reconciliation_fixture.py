"""Reproducible report UI fixture cloned from an exclusively synthetic temp DB."""

import argparse
import json
import os
import shutil
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import sqlalchemy as sa
from restaurant_os import models
from restaurant_os.operations import _cash_summary_for_shift
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session


def authorize_reports(session: Session, actor: str, now: datetime) -> None:
    role = session.scalar(
        sa.select(models.user_roles.c.role_id)
        .join(
            models.role_permissions,
            models.role_permissions.c.role_id == models.user_roles.c.role_id,
        )
        .join(
            models.permissions, models.permissions.c.id == models.role_permissions.c.permission_id
        )
        .where(models.user_roles.c.user_id == actor, models.permissions.c.code == "admin.manage")
    )
    if role is None:
        raise RuntimeError("Expected synthetic administrative role")
    for code in ("reports.ingredient_sales.read", "reports.expenses.read", "reports.sales.read"):
        permission = session.scalar(
            sa.select(models.permissions.c.id).where(models.permissions.c.code == code)
        )
        if permission is None:
            permission = str(uuid4())
            session.execute(
                models.permissions.insert().values(
                    id=permission, code=code, description=code, created_at=now
                )
            )
        if not session.scalar(
            sa.select(models.role_permissions.c.role_id).where(
                models.role_permissions.c.role_id == role,
                models.role_permissions.c.permission_id == permission,
            )
        ):
            session.execute(
                models.role_permissions.insert().values(role_id=role, permission_id=permission)
            )


def fixture_manifest_path(manifest_path: Path) -> Path:
    path = manifest_path.resolve()
    roots = [Path(tempfile.gettempdir()).resolve()]
    if runner_temp := os.environ.get("RUNNER_TEMP"):
        roots.append(Path(runner_temp).resolve())
    if not any(path.is_relative_to(root) for root in roots):
        raise RuntimeError("Fixture must be inside a task temporary directory")
    return path


def seed(manifest_path: Path) -> Path:
    manifest_path = fixture_manifest_path(manifest_path)
    manifest = json.loads(manifest_path.read_text())
    if manifest.get("synthetic_only") is not True:
        raise RuntimeError("Synthetic fixture required")
    url = make_url(manifest["database_url"])
    if not url.drivername.startswith("sqlite") or url.query:
        raise RuntimeError("Exclusive SQLite fixture required")
    source = Path(url.database).resolve()
    source.relative_to(manifest_path.parent)
    destination = manifest_path.parent / "reconciliation.sqlite"
    if source == destination or not source.is_file():
        raise RuntimeError("Invalid fixture source")
    shutil.copyfile(source, destination)
    engine = sa.create_engine(sa.engine.URL.create("sqlite+pysqlite", database=str(destination)))
    branch_id = manifest["branch_id"]
    with Session(engine) as session:
        branch = (
            session.execute(sa.select(models.branches).where(models.branches.c.id == branch_id))
            .mappings()
            .one()
        )
        org = branch["organization_id"]
        actor = session.scalar(
            sa.select(models.users.c.id).where(models.users.c.email == manifest["login"]["email"])
        )
        authorize_reports(session, actor, datetime(2026, 1, 1, tzinfo=timezone.utc))
        session.execute(
            models.branches.update().where(models.branches.c.id == branch_id).values(timezone="UTC")
        )
        for day, state, opening, counted in [
            (15, "CLOSED", 200000, 0),
            (17, "OPERATIVELY_CLOSED", 10000, None),
            (18, "CLOSED", 200000, 0),
            (18, "OPEN", 10000, None),
        ]:
            opened = datetime(2026, 1, day, 12, tzinfo=timezone.utc)
            closed = opened + timedelta(days=1)
            sid = str(uuid4())
            shift = dict(
                id=sid,
                organization_id=org,
                branch_id=branch_id,
                register_code="REPORT-" + sid[:8],
                status=state,
                opening_cash_cents=opening,
                opened_at=opened,
                created_at=opened,
                closed_at=None if state == "OPEN" else closed,
            )
            session.execute(models.cash_shifts.insert().values(**shift))
            if day == 15:
                session.execute(
                    models.cash_movements.insert().values(
                        id=str(uuid4()),
                        organization_id=org,
                        branch_id=branch_id,
                        cash_shift_id=sid,
                        movement_type="withdrawal",
                        amount_cents=30000,
                        reason_code="TEST",
                        reason="Retiro sintético",
                        source_type="MANUAL",
                        actor_user_id=actor,
                        idempotency_key="report-" + sid,
                        status="confirmed",
                        concept_snapshot={"name": "Retiro a bóveda"},
                        created_at=opened + timedelta(hours=13),
                    )
                )
            summary = _cash_summary_for_shift(session, shift)
            if state == "CLOSED":
                session.execute(
                    models.cash_shift_cuts.insert().values(
                        id=str(uuid4()),
                        organization_id=org,
                        branch_id=branch_id,
                        cash_shift_id=sid,
                        sales_total_cents=summary["sales_total_cents"],
                        payment_total_cents=summary["payment_total_cents"],
                        cash_payment_total_cents=summary["cash_payment_cents"],
                        opening_cash_cents=opening,
                        expected_cash_cents=summary["expected_cash_cents"],
                        counted_cash_cents=counted,
                        difference_cents=counted - summary["expected_cash_cents"],
                        status="FINAL",
                        created_at=closed,
                    )
                )
            elif state == "OPERATIVELY_CLOSED":
                session.execute(
                    models.cash_shift_closures.insert().values(
                        id=str(uuid4()),
                        organization_id=org,
                        branch_id=branch_id,
                        cash_shift_id=sid,
                        register_code_snapshot=shift["register_code"],
                        closed_by_user_id=actor,
                        summary_snapshot=summary,
                        closed_at=closed,
                        created_at=closed,
                    )
                )
        session.commit()
    engine.dispose()
    manifest.update(
        database_url="sqlite+pysqlite:///" + str(destination),
        reconciliation_dates={
            "zero": "2026-01-15",
            "activity": "2026-01-16",
            "pending": "2026-01-17",
            "mixed": "2026-01-18",
        },
    )
    output = manifest_path.parent / "reconciliation-manifest.json"
    output.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    print(seed(parser.parse_args().manifest))
