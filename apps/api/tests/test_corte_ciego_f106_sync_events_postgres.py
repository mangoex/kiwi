"""PostgreSQL sync metadata keeps historical transport intact."""

import sqlalchemy as sa
from corte_ciego_fixtures import grant_permission
from restaurant_os import models
from restaurant_os.sync_event_views import human_sync_events
from sqlalchemy.orm import Session
from test_cash_concepts import BRANCH_A, ORG_ID, OWNER_ID, OWNER_ROLE_ID
from test_corte_ciego_f105_postgres import pg_cash as pg_cash
from test_corte_ciego_f106_sync_events import seed_event


def test_sync_metadata_and_original_transport(pg_cash: tuple[sa.Engine, str, str]) -> None:
    engine, _, _ = pg_cash
    with Session(engine) as session:
        grant_permission(session, OWNER_ROLE_ID, "sync.events.read")
        event = seed_event(session, OWNER_ID)
        original = dict(session.execute(sa.select(models.sync_events)).mappings().one())
        result = human_sync_events(session, ORG_ID, BRANCH_A, 0, OWNER_ID, lambda: [])
        assert len(result) == 1 and result[0]["id"] == event
        assert "95123" not in str(result) and "payload" not in result[0]
        assert dict(session.execute(sa.select(models.sync_events)).mappings().one()) == original
