"""ORD-OFF001: opt-in real PostgreSQL concurrency and retained pricing."""

from __future__ import annotations

import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
from threading import Barrier
from uuid import uuid4

import pytest
import sqlalchemy as sa
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from restaurant_os import models
from restaurant_os.offline_order_catalog import (
    build_catalog_snapshot,
    build_operational_seed,
    hydrate_bundle,
)
from restaurant_os.offline_orders import (
    acquire_gateway_lease,
    reconcile_order_command,
    retain_bundle,
    sign_bundle,
)
from restaurant_os.operations import BusinessError, _require_order_write_fence
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from test_cash_concepts import _seed_cash_concept_scope
from test_cash_ledger import _insert_shift
from test_combo_compositions import ACTOR, BRANCH_A, COMBO, ORG_ID
from test_domain_offline_orders import ACCEPTED_AT, _seed_combo_order_scope
from test_gateway_order_service import LocalOrderService, OrderOutbox, _token

API = Path(__file__).resolve().parents[1]


def test_first_lease_waits_for_existing_online_writer_on_postgresql():
    engine = _engine()
    device = Ed25519PrivateKey.generate()
    try:
        with Session(engine) as seed:
            _seed_cash_concept_scope(seed)
        with Session(engine) as writer, Session(engine) as gateway:
            # No lease row exists yet: the stable branch lock must still fence
            # acquisition until the current online unit of work is complete.
            _require_order_write_fence(writer, BRANCH_A)
            gateway.execute(sa.text("SET LOCAL lock_timeout = '100ms'"))
            with pytest.raises(sa.exc.OperationalError) as blocked:
                acquire_gateway_lease(
                    gateway,
                    organization_id=ORG_ID,
                    branch_id=BRANCH_A,
                    device_id=str(uuid4()),
                    actor_id=ACTOR,
                    public_key=device.public_key(),
                    now=ACCEPTED_AT,
                )
            assert getattr(blocked.value.orig, "sqlstate", None) == "55P03"
            gateway.rollback()
            writer.rollback()
            lease = acquire_gateway_lease(
                gateway,
                organization_id=ORG_ID,
                branch_id=BRANCH_A,
                device_id=str(uuid4()),
                actor_id=ACTOR,
                public_key=device.public_key(),
                now=ACCEPTED_AT,
            )
            gateway.commit()
            assert lease["lease_epoch"] == 1
            with pytest.raises(BusinessError) as fenced:
                _require_order_write_fence(writer, BRANCH_A)
            assert fenced.value.code == "offline_gateway_fence_active"
    finally:
        engine.dispose()


def _engine():
    url = os.environ.get("OFFLINE_ORDERS_TEST_POSTGRES_URL")
    if not url:
        pytest.skip("OFFLINE_ORDERS_TEST_POSTGRES_URL required")
    target = make_url(url)
    if (
        not target.drivername.startswith("postgresql")
        or target.host not in {"127.0.0.1", "localhost"}
        or not (target.database or "").startswith("offline_orders_test")
        or target.query
    ):
        raise RuntimeError("Offline orders tests require an isolated local database")
    engine = sa.create_engine(url)
    with engine.begin() as connection:
        connection.exec_driver_sql("DROP SCHEMA public CASCADE")
        connection.exec_driver_sql("CREATE SCHEMA public")
    environment = {**os.environ, "RESTAURANTOS_DATABASE_URL": url}
    environment.pop("DATABASE_URL", None)
    migrated = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=API,
        env=environment,
        capture_output=True,
        text=True,
        timeout=90,
    )
    assert migrated.returncode == 0, migrated.stdout + migrated.stderr
    inspector = sa.inspect(engine)
    for table in models.metadata.tables.values():
        if table.name.startswith("offline_order_"):
            actual = {column["name"] for column in inspector.get_columns(table.name)}
            assert actual == set(table.c.keys()), f"Migration/model mismatch: {table.name}"
    with engine.begin() as connection:
        tables = (
            connection.execute(
                sa.text(
                    "SELECT tablename FROM pg_tables WHERE schemaname='public' "
                    "AND tablename <> 'alembic_version'"
                )
            )
            .scalars()
            .all()
        )
        names = ",".join(connection.dialect.identifier_preparer.quote(name) for name in tables)
        connection.exec_driver_sql(f"TRUNCATE TABLE {names} RESTART IDENTITY CASCADE")
    return engine


def test_postgres_duplicate_replay_uses_retained_catalog_and_one_effect(tmp_path):
    engine = _engine()
    issuer, device = Ed25519PrivateKey.generate(), Ed25519PrivateKey.generate()
    device_id = str(uuid4())
    issued = int(ACCEPTED_AT.timestamp())
    with Session(engine) as session:
        _seed_cash_concept_scope(session)
        _insert_shift(session)
        _seed_combo_order_scope(session)
        bundle = sign_bundle(
            {
                "manifest": {
                    "schema_version": "ord-off/v1",
                    "organization_id": ORG_ID,
                    "branch_id": BRANCH_A,
                    "device_id": device_id,
                    "bundle_id": str(uuid4()),
                    "lease_epoch": 1,
                    "issued_at": issued,
                    "expires_at": issued + 7200,
                },
                "catalog": build_catalog_snapshot(
                    session, organization_id=ORG_ID, branch_id=BRANCH_A
                ),
                "operational_seed": build_operational_seed(
                    session, organization_id=ORG_ID, branch_id=BRANCH_A, actor_ids=[ACTOR]
                ),
            },
            issuer,
            kid="central",
        )
        acquire_gateway_lease(
            session,
            organization_id=ORG_ID,
            branch_id=BRANCH_A,
            device_id=device_id,
            actor_id=ACTOR,
            public_key=device.public_key(),
            now=ACCEPTED_AT,
        )
        retain_bundle(session, bundle, {"central": issuer.public_key()}, now=ACCEPTED_AT)
        session.commit()
    claims = {
        "schema_version": "ord-off-grant/v3",
        "organization_id": ORG_ID,
        "branch_id": BRANCH_A,
        "device_id": device_id,
        "bundle_id": bundle["manifest"]["bundle_id"],
        "bundle_hash": bundle["hash"],
        "actor_id": ACTOR,
        "lease_epoch": 1,
        "capabilities": ["orders.create"],
        "iat": issued,
        "exp": issued + 7200,
    }
    outbox, catalog = OrderOutbox(tmp_path / "local.db"), OrderOutbox(tmp_path / "catalog.db")
    hydrate_bundle(outbox.engine, bundle, include_operational_seed=True)
    hydrate_bundle(catalog.engine, bundle)
    local = LocalOrderService(
        outbox, catalog.engine, bundle, {"central": issuer.public_key()}, device
    )
    order = local.execute(
        _token(issuer, claims),
        "create",
        {"lines": [{"product_id": COMBO, "quantity": 1}], "register_id": "CAJA-01"},
        "offline-pg-replay-001",
        now=ACCEPTED_AT,
    )
    envelope = outbox.pending()[0]["envelope"]
    with engine.begin() as connection:
        connection.execute(
            models.price_versions.update()
            .where(models.price_versions.c.product_id == COMBO)
            .values(price_cents=999)
        )
    barrier = Barrier(2)

    def replay():
        with Session(engine) as session:
            barrier.wait(timeout=10)
            return reconcile_order_command(
                session,
                envelope,
                keyring={"central": issuer.public_key()},
                now=ACCEPTED_AT + timedelta(hours=3),
                commit=True,
            )

    with ThreadPoolExecutor(max_workers=2) as workers:
        results = list(workers.map(lambda _: replay(), range(2)))
    assert results[0] == results[1]
    assert results[0]["status"] == "confirmed"
    assert results[0]["checkpoint"] > 0
    for invalid in ({"checkpoint": 0}, {"sequence": 0}, {"lease_epoch": 0}, {"status": "INVALID"}):
        with engine.begin() as connection:
            with pytest.raises(sa.exc.IntegrityError), connection.begin_nested():
                connection.execute(models.offline_order_inbox.update().values(**invalid))
    with Session(engine) as session:
        assert (
            session.scalar(sa.select(sa.func.count()).select_from(models.offline_order_inbox)) == 1
        )
        assert session.scalar(sa.select(sa.func.count()).select_from(models.orders)) == 1
        assert (
            session.scalar(
                sa.select(models.orders.c.total_cents).where(models.orders.c.id == order["id"])
            )
            == 15900
        )
        assert session.scalar(sa.select(sa.func.count()).select_from(models.production_tasks)) == 2
    with engine.begin() as connection:
        connection.execute(
            models.users.update().where(models.users.c.id == ACTOR).values(status="inactive")
        )
    with Session(engine) as session:
        with pytest.raises(BusinessError):
            reconcile_order_command(
                session,
                envelope,
                keyring={"central": issuer.public_key()},
                now=ACCEPTED_AT + timedelta(hours=3),
                commit=True,
            )
    engine.dispose()
    environment = {**os.environ, "RESTAURANTOS_DATABASE_URL": str(engine.url)}
    environment["RESTAURANTOS_DATABASE_URL"] = engine.url.render_as_string(hide_password=False)
    environment.pop("DATABASE_URL", None)
    downgrade = subprocess.run(
        [sys.executable, "-m", "alembic", "downgrade", "0066_combo_compositions"],
        cwd=API,
        env=environment,
        capture_output=True,
        text=True,
        timeout=90,
    )
    assert downgrade.returncode != 0
    assert "Cannot downgrade 0067 while offline order history exists" in downgrade.stderr
    with engine.connect() as connection:
        assert (
            connection.scalar(sa.select(sa.func.count()).select_from(models.offline_order_inbox))
            == 1
        )
        assert (
            connection.exec_driver_sql("SELECT version_num FROM alembic_version").scalar_one()
            == "0067_offline_orders"
        )
    engine.dispose()
