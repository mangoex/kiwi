"""Real PostgreSQL channel projections, JSON extraction and historical integrity."""

from typing import Any

import pytest
import sqlalchemy as sa
from corte_ciego_fixtures import grant_permission, ident
from restaurant_os import models
from restaurant_os import operations as ops
from restaurant_os.integrations.service import ChannelIntegrationService
from sqlalchemy.orm import Session
from test_cash_concepts import BRANCH_A, OWNER_ID, OWNER_ROLE_ID
from test_corte_ciego_f105_postgres import pg_cash as pg_cash
from test_corte_ciego_f106_channel_orders import PROVIDERS, seed_channels
from test_corte_ciego_f106_postgres import pg_sales as pg_sales


def test_channel_projection_and_original_payloads(pg_sales: tuple[sa.Engine, str]) -> None:
    engine, _ = pg_sales
    with Session(engine) as session:
        grant_permission(session, OWNER_ROLE_ID, "orders.read")
        seed_channels(session, ident("f106-order"))
        before = list(session.execute(sa.select(models.channel_orders_meta)).mappings())
        for provider in PROVIDERS:
            result = ChannelIntegrationService().list_pos_orders(
                session, BRANCH_A, provider, "PENDING", actor_user_id=OWNER_ID
            )
            assert len(result) == 1 and result[0]["customer_label"] == "Synthetic customer"
            assert result[0]["channel"] == provider and "95123" not in str(result)
            assert "delivery_address_snapshot" not in result[0] and "lines" not in result[0]
        assert list(session.execute(sa.select(models.channel_orders_meta)).mappings()) == before
        assert (
            session.scalar(
                sa.select(sa.func.count())
                .select_from(models.audit_events)
                .where(models.audit_events.c.action == "channel.orders.read")
            )
            == 4
        )


def test_channel_audit_failure_rolls_back(
    pg_sales: tuple[sa.Engine, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    engine, _ = pg_sales
    with Session(engine) as session:
        grant_permission(session, OWNER_ROLE_ID, "orders.read")
        seed_channels(session, ident("f106-order"))
    audit = ops._audit

    def fail(session: Session, action: str, *args: Any, **kwargs: Any) -> Any:
        if action == "channel.orders.read":
            raise sa.exc.SQLAlchemyError("Synthetic audit failure")
        return audit(session, action, *args, **kwargs)

    monkeypatch.setattr(ops, "_audit", fail)
    with Session(engine) as session, pytest.raises(sa.exc.SQLAlchemyError):
        ChannelIntegrationService().list_pos_orders(
            session, BRANCH_A, "RAPPI", actor_user_id=OWNER_ID
        )
    with Session(engine) as session:
        assert (
            session.scalar(
                sa.select(sa.func.count())
                .select_from(models.audit_events)
                .where(models.audit_events.c.action == "channel.orders.read")
            )
            == 0
        )
        assert (
            session.scalar(sa.select(sa.func.count()).select_from(models.channel_orders_meta)) == 4
        )
