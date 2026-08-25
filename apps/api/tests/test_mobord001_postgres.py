"""Optional PostgreSQL contract for MOB-ORD-001; never reads DATABASE_URL."""
# ruff: noqa: E501

from __future__ import annotations

import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from threading import Barrier

import pytest
import sqlalchemy as sa
from sqlalchemy.engine import make_url

TEST_URL_ENV = "MOBORD001_TEST_POSTGRES_URL"
API_DIR = Path(__file__).resolve().parents[1]
REVISION_0050 = "0050_promote_recipes_to_global_scope"


def _mobord001_postgres_url() -> str:
    url = os.environ.get(TEST_URL_ENV)
    if not url:
        pytest.skip(f"{TEST_URL_ENV} is not configured")
    parsed = make_url(url)
    database = parsed.database or ""
    if (
        not parsed.drivername.startswith("postgresql")
        or parsed.host not in {"127.0.0.1", "localhost"}
        or not database.startswith("mobord001_")
    ):
        raise RuntimeError(
            f"{TEST_URL_ENV} must be local PostgreSQL with database mobord001_*"
        )
    return url


def test_mobord001_postgres_url_is_opt_in_and_isolated() -> None:
    assert _mobord001_postgres_url().startswith("postgresql")


def _alembic_environment(url: str) -> dict[str, str]:
    """Pass only the validated isolated URL; generic DATABASE_URL is excluded."""
    environment = dict(os.environ)
    environment.pop("DATABASE_URL", None)
    environment["RESTAURANTOS_DATABASE_URL"] = url
    return environment


def _run_alembic(url: str, *arguments: str) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "alembic.ini", *arguments],
        cwd=API_DIR,
        env=_alembic_environment(url),
        capture_output=True,
        text=True,
        timeout=60,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stdout + result.stderr)


def test_mobord001_postgres_forward_migration_requires_preprovisioned_0050() -> None:
    """Forward-only gate; reprovision the isolated DB at 0050 before rerunning."""
    url = _mobord001_postgres_url()
    engine = sa.create_engine(url)
    try:
        with engine.connect() as connection:
            revision = connection.scalar(sa.text("SELECT version_num FROM alembic_version"))
        if revision != REVISION_0050:
            raise RuntimeError(
                f"{TEST_URL_ENV} must be reprovisioned at {REVISION_0050}; found {revision!r}"
            )
    finally:
        engine.dispose()


def test_mobord001_postgres_terminal_transition_is_compare_and_swap() -> None:
    """Two database sessions cannot both resolve the same pending version."""
    url = _mobord001_postgres_url()
    _run_alembic(url, "upgrade", "0051_public_order_intents")
    engine = sa.create_engine(url)
    now = datetime.now(timezone.utc)
    organization_id = "mobord001-pg-org"
    legal_entity_id = "mobord001-pg-legal"
    business_unit_id = "mobord001-pg-unit"
    branch_id = "mobord001-pg-branch"
    intent_id = "mobord001-pg-intent"
    with engine.begin() as connection:
        connection.execute(sa.text("DELETE FROM public_order_intents WHERE id = :id"), {"id": intent_id})
        connection.execute(sa.text("DELETE FROM public_order_keys WHERE public_key = 'mobord001-pg-key'"))
        connection.execute(sa.text("DELETE FROM branches WHERE id = :id"), {"id": branch_id})
        connection.execute(sa.text("DELETE FROM business_units WHERE id = :id"), {"id": business_unit_id})
        connection.execute(sa.text("DELETE FROM legal_entities WHERE id = :id"), {"id": legal_entity_id})
        connection.execute(sa.text("DELETE FROM organizations WHERE id = :id"), {"id": organization_id})
        connection.execute(sa.text(
            "INSERT INTO organizations (id, name, status, created_at, updated_at) "
            "VALUES (:id, 'MOB PG', 'active', :now, :now)"
        ), {"id": organization_id, "now": now})
        connection.execute(sa.text(
            "INSERT INTO legal_entities (id, organization_id, name, status, created_at, updated_at) "
            "VALUES (:id, :org, 'MOB PG', 'active', :now, :now)"
        ), {"id": legal_entity_id, "org": organization_id, "now": now})
        connection.execute(sa.text(
            "INSERT INTO business_units (id, organization_id, legal_entity_id, name, code, unit_type, status, created_at, updated_at) "
            "VALUES (:id, :org, :legal, 'MOB PG', 'MOBPG', 'restaurant', 'active', :now, :now)"
        ), {"id": business_unit_id, "org": organization_id, "legal": legal_entity_id, "now": now})
        connection.execute(sa.text(
            "INSERT INTO branches (id, organization_id, legal_entity_id, business_unit_id, name, code, timezone, status, created_at, updated_at) "
            "VALUES (:id, :org, :legal, :unit, 'MOB PG', 'MOBPG', 'America/Mazatlan', 'active', :now, :now)"
        ), {"id": branch_id, "org": organization_id, "legal": legal_entity_id, "unit": business_unit_id, "now": now})
        connection.execute(sa.text(
            "INSERT INTO public_order_keys (public_key, organization_id, branch_id, status, created_at) "
            "VALUES ('mobord001-pg-key', :org, :branch, 'active', :now)"
        ), {"org": organization_id, "branch": branch_id, "now": now})
        connection.execute(sa.text(
            "INSERT INTO public_order_intents "
            "(id, organization_id, branch_id, public_key, public_reference, correlation_id, status, customer_snapshot, order_type, total_cents, currency, version, created_at) "
            "VALUES (:id, :org, :branch, 'mobord001-pg-key', 'PI-PG-CAS', 'mobord001-pg-correlation', 'PENDING_REVIEW', '{}', 'takeout', 0, 'MXN', 1, :now)"
        ), {"id": intent_id, "org": organization_id, "branch": branch_id, "now": now})

    barrier = Barrier(2)

    def resolve(status: str) -> int:
        with engine.begin() as connection:
            barrier.wait(timeout=10)
            result = connection.execute(sa.text(
                "UPDATE public_order_intents SET status = :status, version = 2, decided_at = :now "
                "WHERE id = :id AND status = 'PENDING_REVIEW' AND version = 1"
            ), {"status": status, "now": now, "id": intent_id})
            return int(result.rowcount)

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            rowcounts = list(pool.map(resolve, ("ACCEPTED", "REJECTED")))
        assert sorted(rowcounts) == [0, 1]
        with engine.connect() as connection:
            status, version = connection.execute(sa.text(
                "SELECT status, version FROM public_order_intents WHERE id = :id"
            ), {"id": intent_id}).one()
        assert status in {"ACCEPTED", "REJECTED"}
        assert version == 2
    finally:
        engine.dispose()
    engine = sa.create_engine(url)
    try:
        with engine.connect() as connection:
            constraints = dict(connection.execute(sa.text(
                "SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint "
                "WHERE conrelid = 'orders'::regclass"
            )).all())
            indexes = set(connection.execute(sa.text(
                "SELECT indexname FROM pg_indexes WHERE tablename = 'orders'"
            )).scalars())
        check = constraints["ck_orders_cash_shift_required_except_public_intent"]
        assert "cash_shift_id IS NOT NULL" in check
        assert "public_order_intent_status" in check and "ACCEPTED" in check
        assert "fk_orders_public_order_intent_accepted" in constraints
        assert "uq_orders_public_order_intent_id" in indexes
    finally:
        engine.dispose()
