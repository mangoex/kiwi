"""PostgreSQL diagnostics projection and receipt audit use real schemas and actors."""

from collections.abc import Iterator
from typing import Any

import pytest
import sqlalchemy as sa
from corte_ciego_storage import isolated_database
from fixture_metadata import create_fixture_tables
from restaurant_os import models
from restaurant_os import operations as ops
from restaurant_os.integrations.service import ChannelIntegrationService
from sqlalchemy.orm import Session, sessionmaker
from test_corte_ciego_f105_intents import activate
from test_platform_api import ADMIN_USER_ID, _seed


@pytest.fixture
def log_pg() -> Iterator[sessionmaker[Session]]:
    for engine in isolated_database("postgresql"):
        create_fixture_tables(engine)
        factory = sessionmaker(bind=engine, expire_on_commit=False)
        with factory() as session:
            _seed(session)
            ChannelIntegrationService().log_webhook(
                session,
                ops.ORGANIZATION_ID,
                "RAPPI",
                "private-event",
                "private-event-id",
                "private-signature",
                {"amount_cents": 950123},
                "private-status",
                "private-error",
            )
        activate(factory)
        yield factory


def test_metadata_projection_preserves_original(log_pg: sessionmaker[Session]) -> None:
    service = ChannelIntegrationService()
    with log_pg() as session:
        result = service.list_webhook_logs(
            session, ops.ORGANIZATION_ID, "RAPPI", actor_user_id=ADMIN_USER_ID
        )
        assert len(result) == 1 and result[0]["status"] == "unknown"
        assert "private" not in str(result) and "amount_cents" not in str(result)
        original = session.execute(sa.select(models.integration_webhook_logs)).mappings().one()
        assert original["payload_raw"] == {"amount_cents": 950123}
        assert (
            original["signature"] == "private-signature" and original["status"] == "private-status"
        )
        audit = session.execute(
            sa.select(models.audit_events.c.payload).where(
                models.audit_events.c.action == "integration.logs.read"
            )
        ).scalar_one()
        assert audit == {"provider": "RAPPI"}


def test_audit_failure_returns_no_result(
    log_pg: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch
) -> None:
    audit = ops._audit

    def fail(session: Session, action: str, *args: Any, **kwargs: Any) -> Any:
        if action == "integration.logs.read":
            raise sa.exc.SQLAlchemyError("synthetic audit failure")
        return audit(session, action, *args, **kwargs)

    monkeypatch.setattr(ops, "_audit", fail)
    with log_pg() as session, pytest.raises(sa.exc.SQLAlchemyError):
        ChannelIntegrationService().list_webhook_logs(
            session, ops.ORGANIZATION_ID, "RAPPI", actor_user_id=ADMIN_USER_ID
        )
    with log_pg() as session:
        assert (
            session.scalar(sa.select(sa.func.count()).select_from(models.integration_webhook_logs))
            == 1
        )
        assert (
            session.scalar(
                sa.select(sa.func.count())
                .select_from(models.audit_events)
                .where(models.audit_events.c.action == "integration.logs.read")
            )
            == 0
        )
