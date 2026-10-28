"""Disposable databases with the real 0101 migration and foreign keys enabled."""

from __future__ import annotations

import os
import runpy
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from uuid import uuid4

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from corte_ciego_fixtures import grant_permission
from fixture_metadata import create_fixture_tables
from restaurant_os import models
from restaurant_os.financial_access import FinancialAccessService
from restaurant_os.financial_access_schema import tables
from sqlalchemy.orm import Session
from test_cash_concepts import (
    BRANCH_A,
    CASHIER_ID,
    CASHIER_ROLE_ID,
    ORG_ID,
    OWNER_ID,
    _seed_cash_concept_scope,
)
from test_cash_ledger import NOW

MIGRATION = Path(__file__).parents[1] / "alembic/versions/202610210300_0101_financial_authority.py"


def migrate(connection: sa.Connection, direction: str) -> None:
    module = runpy.run_path(str(MIGRATION))
    with Operations.context(MigrationContext.configure(connection)):
        module[direction]()


def isolated_database(dialect: str) -> Iterator[sa.Engine]:
    control: sa.Engine | None = None
    schema = "cc_f104_" + uuid4().hex
    if dialect == "postgresql":
        # Mandatory gate: absent configuration FAILS instead of adding a skip/exclusion.
        raw = os.environ["CORTE_CIEGO_TEST_POSTGRES_URL"]
        url = sa.engine.make_url(raw)
        if (
            not url.drivername.startswith("postgresql")
            or url.host not in {"127.0.0.1", "localhost"}
            or not (url.database or "").startswith("corte_ciego_")
            or url.query
        ):
            raise RuntimeError("An isolated local corte_ciego_* database is required")
        control = sa.create_engine(url)
        with control.begin() as connection:
            connection.execute(sa.text(f"CREATE SCHEMA {schema}"))
        engine = sa.create_engine(
            url,
            connect_args={
                "options": f"-c search_path={schema} "
                "-c statement_timeout=15000 -c lock_timeout=10000",
            },
        )
    else:
        engine = sa.create_engine("sqlite+pysqlite://")

        @sa.event.listens_for(engine, "connect")
        def foreign_keys(connection: Any, record: Any) -> None:
            connection.execute("PRAGMA foreign_keys=ON")

    try:
        # Only baseline tables required by this authority slice, with their real constraints.
        names = (
            "organizations",
            "legal_entities",
            "business_units",
            "branches",
            "employee_code_registry",
            "users",
            "roles",
            "permissions",
            "user_roles",
            "role_permissions",
            "role_authority_grants",
            "audit_events",
        )
        required = {models.metadata.tables[name] for name in names}
        pending = list(required)
        while pending:
            for foreign_key in pending.pop().foreign_keys:
                target = foreign_key.column.table
                if target not in required:
                    required.add(target)
                    pending.append(target)
        create_fixture_tables(engine, tables=list(required))
        with engine.begin() as connection:
            migrate(connection, "upgrade")
        yield engine
    finally:
        engine.dispose()
        if control is not None:
            # Drop only the UUID schema created by this fixture; never public or another database.
            with control.begin() as connection:
                connection.execute(sa.text(f"DROP SCHEMA {schema} CASCADE"))
            control.dispose()


def seed_authority(engine: sa.Engine) -> str:
    with Session(engine) as session:
        _seed_cash_concept_scope(session)
        grant_permission(session, CASHIER_ROLE_ID, "financial.data.read")
        session.execute(
            models.financial_owner_reviews.insert().values(
                organization_id=ORG_ID,
                user_id=OWNER_ID,
                authorization_version=1,
                manifest_digest="a" * 64,
                approval_reference="Synthetic reviewed Owner",
                reviewed_at=NOW,
            )
        )
        session.commit()
        result = FinancialAccessService(session, ORG_ID).issue(
            OWNER_ID,
            "seed",
            {
                "subject_user_id": CASHIER_ID,
                "reason": "Synthetic scoped read",
                "scopes": [{"branch_id": BRANCH_A, "dataset": "sales"}],
            },
        )
        return str(result["grant_id"])


def relation_names() -> list[str]:
    return [table.name for table in tables(sa.MetaData())]
