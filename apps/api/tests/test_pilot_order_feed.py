"""Pilot regression: POS orders and web intents share a bounded, filtered feed."""

from datetime import timedelta
from uuid import uuid4

import sqlalchemy as sa
from restaurant_os import models
from restaurant_os.operations import list_order_accounts
from test_cash_ledger import BRANCH_A, CASHIER_ID, NOW, ORG_ID, _new_session
from test_order_reopen_workflow import _actors, _order


def _intent(session, *, minutes: int, name: str = "Cliente Web", service: str = "takeout"):
    key = session.scalar(sa.select(models.public_order_keys.c.public_key))
    if not key:
        key = "pilot-synthetic-public-key"
        session.execute(
            models.public_order_keys.insert().values(
                public_key=key,
                organization_id=ORG_ID,
                branch_id=BRANCH_A,
                status="active",
            )
        )
    identity = str(uuid4())
    session.execute(
        models.public_order_intents.insert().values(
            id=identity,
            organization_id=ORG_ID,
            branch_id=BRANCH_A,
            public_key=key,
            public_reference=identity,
            correlation_id=identity,
            status="PENDING_REVIEW",
            customer_snapshot={"name": name},
            order_type=service,
            total_cents=500,
            currency="MXN",
            version=1,
            created_at=NOW + timedelta(minutes=minutes),
        )
    )
    session.commit()
    return identity


def test_pos_order_is_not_hidden_behind_unbounded_web_intents():
    engine, session = _new_session()
    try:
        _actors(session)
        pos_id = _order(session)
        web_ids = {_intent(session, minutes=-i - 1) for i in range(28)}
        first = list_order_accounts(session, {"branch_id": BRANCH_A, "limit": 5}, CASHIER_ID)
        assert len(first["items"]) == 5
        assert first["items"][0]["id"] == pos_id
        seen = [item["id"] for item in first["items"]]
        cursor = first["next_cursor"]
        while cursor:
            page = list_order_accounts(
                session,
                {
                    "branch_id": BRANCH_A,
                    "limit": 5,
                    "cursor": cursor,
                },
                CASHIER_ID,
            )
            assert len(page["items"]) <= 5
            seen.extend(item["id"] for item in page["items"])
            cursor = page["next_cursor"]
        assert len(seen) == len(set(seen)) == 29
        assert set(seen) == web_ids | {pos_id}
    finally:
        session.close()
        engine.dispose()


def test_web_intents_obey_search_service_and_date_filters():
    engine, session = _new_session()
    try:
        _actors(session)
        _order(session)
        expected = _intent(session, minutes=1, name="CLIENTE AGUA", service="delivery")
        _intent(session, minutes=2, name="OTRO CLIENTE", service="delivery")
        _intent(session, minutes=3, name="CLIENTE AGUA", service="takeout")
        _intent(session, minutes=1440, name="CLIENTE AGUA", service="delivery")
        page = list_order_accounts(
            session,
            {
                "branch_id": BRANCH_A,
                "limit": 5,
                "q": "agua",
                "service_type": "delivery",
                "from_utc": NOW.isoformat(),
                "to_utc": (NOW + timedelta(hours=1)).isoformat(),
            },
            CASHIER_ID,
        )
        assert [item["id"] for item in page["items"]] == [expected]
    finally:
        session.close()
        engine.dispose()


def test_web_intent_folio_search_matches_the_displayed_folio():
    engine, session = _new_session()
    try:
        _actors(session)
        wanted = _intent(session, minutes=0)
        _intent(session, minutes=1)
        page = list_order_accounts(
            session,
            {
                "branch_id": BRANCH_A,
                "q": f"WEB-{wanted[-6:]}",
                "limit": 1,
            },
            CASHIER_ID,
        )
        assert [item["id"] for item in page["items"]] == [wanted]
        assert page["next_cursor"] is None
    finally:
        session.close()
        engine.dispose()
