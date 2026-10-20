"""R3 controlled races on an explicitly isolated local PostgreSQL database."""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event
from typing import Any

import pytest
import sqlalchemy as sa
from restaurant_os import mobile_customers as service
from restaurant_os import models
from restaurant_os.operations import ORGANIZATION_ID
from sqlalchemy.dialects import sqlite
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from test_mobile_customer_profile import PROFILE, Verifier
from test_platform_api import BRANCH_ID, _seed

KEY = {"organization_id": ORGANIZATION_ID, "branch_id": BRANCH_ID}


def _create_fixture_tables(engine: Any) -> None:
    # Cyclic PostgreSQL FK DDL mutates its MetaData. Keep the canonical model
    # intact for SQLite fixtures executed later in the same pytest process.
    fixture_metadata = sa.MetaData()
    for table in models.metadata.tables.values():
        table.to_metadata(fixture_metadata)
    fixture_metadata.create_all(engine)


def test_fixture_ddl_preserves_shared_sqlite_constraints() -> None:
    before = str(sa.schema.CreateTable(models.orders).compile(dialect=sqlite.dialect()))
    postgres = sa.create_mock_engine("postgresql://", lambda *_args, **_kwargs: None)
    _create_fixture_tables(postgres)
    after = str(sa.schema.CreateTable(models.orders).compile(dialect=sqlite.dialect()))
    assert "fk_orders_public_order_intent_accepted" in before
    assert after == before, "PostgreSQL fixture DDL must preserve shared SQLite constraints"


@pytest.fixture(scope="module")
def pg_engine() -> Any:
    raw = os.environ.get("MOBILE_CUSTOMER_RUNTIME_POSTGRES_URL")
    if not raw:
        pytest.skip("MOBILE_CUSTOMER_RUNTIME_POSTGRES_URL is required")
    parsed = make_url(raw)
    if (
        not parsed.drivername.startswith("postgresql")
        or parsed.host not in {"127.0.0.1", "localhost"}
        or not (parsed.database or "").startswith("crm_mobile_")
        or parsed.query
    ):
        raise RuntimeError("Use only an isolated local crm_mobile_* database")
    engine = sa.create_engine(raw, connect_args={"options": "-c lock_timeout=8000"})
    with engine.begin() as connection:
        connection.execute(sa.text("DROP SCHEMA public CASCADE"))
        connection.execute(sa.text("CREATE SCHEMA public"))
    _create_fixture_tables(engine)
    with Session(engine) as session:
        _seed(session)
    yield engine
    engine.dispose()


def _challenge(engine: Any, phone: str, identity: Any = None) -> str:
    with Session(engine) as session:
        return str(service.start_access(session, KEY, phone, Verifier(), identity)["challenge"])


def _verify(engine: Any, token: str, verifier: Any = None, identity: Any = None) -> Any:
    with Session(engine) as session:
        return service.verify_access(
            session, KEY, token, "123456", verifier or Verifier(), identity
        )


def test_concurrent_verified_logins_create_one_identity(pg_engine: Any) -> None:
    barrier = Barrier(2)

    class SynchronizedVerifier(Verifier):
        def check(self, verification_id: str, code: str) -> bool:
            barrier.wait(timeout=8)
            return True

    tokens = [_challenge(pg_engine, "6691234567") for _ in range(2)]
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(_verify, pg_engine, token, SynchronizedVerifier()) for token in tokens
        ]
        identities = [future.result(timeout=15)[0] for future in futures]
    assert identities[0]["id"] == identities[1]["id"]
    with Session(pg_engine) as session:
        assert (
            session.scalar(
                sa.select(sa.func.count())
                .select_from(models.mobile_customer_identities)
                .where(models.mobile_customer_identities.c.phone == "+526691234567")
            )
            == 1
        )


def test_concurrent_profile_creation_keeps_one_customer_and_default(pg_engine: Any) -> None:
    identity, _ = _verify(pg_engine, _challenge(pg_engine, "6691234568"))
    payload = {
        **PROFILE,
        "address": {
            "creation_key": "pg-stable-address-0001",
            "alias": "Casa",
            "street": "Prueba",
            "exterior_number": "1",
            "neighborhood": "Centro",
            "postal_code": "82000",
            "city": "Mazatlán",
            "municipality": "Mazatlán",
            "state": "Sinaloa",
            "is_default": True,
        },
    }
    barrier = Barrier(2)

    def save() -> Any:
        with Session(pg_engine) as session:
            barrier.wait(timeout=8)
            return service.save_profile(session, identity, KEY, payload)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(save) for _ in range(2)]
        results = [f.result(timeout=15) for f in futures]
    assert results[0]["id"] == results[1]["id"]
    assert results[0]["saved_address_id"] == results[1]["saved_address_id"]
    assert len(results[1]["addresses"]) == 1


def test_overlapping_phone_changes_reject_stale_identity(pg_engine: Any) -> None:
    identity, _ = _verify(pg_engine, _challenge(pg_engine, "6691234569"))
    with Session(pg_engine) as session:
        service.save_profile(session, identity, KEY, PROFILE)
        identity = dict(
            session.execute(
                sa.select(models.mobile_customer_identities).where(
                    models.mobile_customer_identities.c.id == identity["id"]
                )
            )
            .mappings()
            .one()
        )
    tokens = [_challenge(pg_engine, phone, identity) for phone in ("6690000001", "6690000002")]
    waiting, release = Event(), Event()

    class WaitingVerifier(Verifier):
        def check(self, verification_id: str, code: str) -> bool:
            waiting.set()
            assert release.wait(10)
            return True

    with ThreadPoolExecutor(max_workers=1) as pool:
        loser = pool.submit(_verify, pg_engine, tokens[1], WaitingVerifier(), identity)
        assert waiting.wait(8)
        try:
            winner, _ = _verify(pg_engine, tokens[0], identity=identity)
            assert winner["phone"] == "+526690000001"
        finally:
            release.set()
        with pytest.raises(service.MobileError, match="mobile_identity_changed"):
            loser.result(timeout=15)
    with Session(pg_engine) as session:
        active = list(
            session.execute(
                sa.select(models.customer_phones).where(
                    models.customer_phones.c.customer_id == winner["customer_id"],
                    models.customer_phones.c.status == "active",
                )
            ).mappings()
        )
        assert len(active) == 1
        assert active[0]["normalized_number"] == winner["phone"]
        assert active[0]["is_primary"]
