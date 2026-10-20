"""0098: additive migration, preservation and guarded rollback on both dialects."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy.engine import make_url
from test_driver_cash_settlement_migration import _migrate


def roundtrip(url: str) -> None:
    _migrate(url, "upgrade", "0097_public_tracking_event_index")
    engine = sa.create_engine(url)
    with engine.begin() as connection:
        organization_id = connection.scalar(sa.text("SELECT id FROM organizations LIMIT 1"))
        connection.execute(
            sa.text(
                "INSERT INTO customers (id, organization_id, name, created_at, updated_at) "
                "VALUES ('mobile-historical-test', :organization, 'Historical', CURRENT_TIMESTAMP, "
                "CURRENT_TIMESTAMP)"
            ),
            {"organization": organization_id},
        )
    with engine.begin() as connection:
        metadata = sa.MetaData()
        keys = sa.Table("public_order_keys", metadata, autoload_with=connection)
        intents = sa.Table("public_order_intents", metadata, autoload_with=connection)
        orders = sa.Table("orders", metadata, autoload_with=connection)
        branch_id = connection.scalar(sa.text("SELECT id FROM branches LIMIT 1"))
        key = (
            connection.execute(sa.select(keys).where(keys.c.branch_id == branch_id))
            .mappings()
            .first()
        )
        if key is None:
            connection.execute(
                keys.insert().values(
                    public_key="mobile-history-key",
                    organization_id=organization_id,
                    branch_id=branch_id,
                    status="active",
                )
            )
            public_key = "mobile-history-key"
        else:
            public_key = key["public_key"]
        timestamp = datetime.now(timezone.utc)
        connection.execute(
            intents.insert().values(
                id="mobile-historical-intent",
                organization_id=organization_id,
                branch_id=branch_id,
                public_key=public_key,
                public_reference="PI-HISTORICAL-MOBILE",
                correlation_id="history-mobile",
                status="ACCEPTED",
                customer_snapshot={"name": "Historical"},
                order_type="takeout",
                total_cents=1000,
                currency="MXN",
                version=2,
                created_at=timestamp,
            )
        )
        connection.execute(
            orders.insert().values(
                id="mobile-historical-order",
                organization_id=organization_id,
                branch_id=branch_id,
                customer_id="mobile-historical-test",
                public_order_intent_id="mobile-historical-intent",
                public_order_intent_status="ACCEPTED",
                customer_snapshot={"name": "Historical"},
                folio="MOBILE-HISTORY-001",
                channel="PUBLIC_INTENT",
                status="ACCEPTED",
                total_cents=1000,
                currency="MXN",
                version=1,
                created_at=timestamp,
            )
        )
        connection.execute(
            intents.update()
            .where(intents.c.id == "mobile-historical-intent")
            .values(accepted_order_id="mobile-historical-order")
        )
    _migrate(url, "upgrade", "0098_mobile_customer_profile")
    with engine.begin() as connection:
        row = connection.execute(
            sa.text(
                "SELECT name, birthday_day, birthday_month, birthday_year FROM customers "
                "WHERE id = 'mobile-historical-test'"
            )
        ).one()
        assert tuple(row) == ("Historical", None, None, None)
        connection.execute(
            sa.text(
                "UPDATE customers SET birthday_day = 29, birthday_month = 2 "
                "WHERE id = 'mobile-historical-test'"
            )
        )
    with pytest.raises(AssertionError, match="Mobile profile data exists"):
        _migrate(url, "downgrade", "0097_public_tracking_event_index")
    with engine.begin() as connection:
        connection.execute(
            sa.text(
                "UPDATE customers SET birthday_day = NULL, birthday_month = NULL "
                "WHERE id = 'mobile-historical-test'"
            )
        )
    _migrate(url, "downgrade", "0097_public_tracking_event_index")
    assert not sa.inspect(engine).has_table("mobile_customer_identities")
    with engine.begin() as connection:
        assert (
            connection.scalar(
                sa.text("SELECT name FROM customers WHERE id = 'mobile-historical-test'")
            )
            == "Historical"
        )
        assert (
            connection.scalar(
                sa.text("SELECT total_cents FROM orders WHERE id = 'mobile-historical-order'")
            )
            == 1000
        )
        assert (
            connection.scalar(
                sa.text(
                    "SELECT accepted_order_id FROM public_order_intents "
                    "WHERE id = 'mobile-historical-intent'"
                )
            )
            == "mobile-historical-order"
        )
        connection.execute(
            sa.text(
                "UPDATE public_order_intents SET accepted_order_id = NULL "
                "WHERE id = 'mobile-historical-intent'"
            )
        )
        connection.execute(sa.text("DELETE FROM orders WHERE id = 'mobile-historical-order'"))
        connection.execute(
            sa.text("DELETE FROM public_order_intents WHERE id = 'mobile-historical-intent'")
        )
        connection.execute(sa.text("DELETE FROM customers WHERE id = 'mobile-historical-test'"))
    engine.dispose()


def test_mobile_customer_migration_sqlite(tmp_path: Path) -> None:
    roundtrip(f"sqlite+pysqlite:///{tmp_path / 'mobile-profile.sqlite'}")


def test_mobile_customer_migration_postgres() -> None:
    raw = os.environ.get("MOBILE_CUSTOMER_TEST_POSTGRES_URL")
    if not raw:
        pytest.skip("MOBILE_CUSTOMER_TEST_POSTGRES_URL required for isolated PostgreSQL")
    url = make_url(raw)
    if (
        not url.drivername.startswith("postgresql")
        or url.host not in {"127.0.0.1", "localhost"}
        or not (url.database or "").startswith("crm_mobile_")
        or url.query
    ):
        raise RuntimeError("Use an isolated local crm_mobile_* PostgreSQL database")
    roundtrip(raw)
