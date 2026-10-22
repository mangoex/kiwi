"""Real PostgreSQL session descriptor follows grant revocation without monetary reads."""

import sqlalchemy as sa
from restaurant_os import models
from restaurant_os.financial_access import FinancialAccessService
from restaurant_os.financial_authority import FinancialAuthority
from restaurant_os.financial_session import session_financial_access
from sqlalchemy.orm import Session
from test_cash_concepts import BRANCH_A, CASHIER_ID, ORG_ID, OWNER_ID
from test_corte_ciego_f105_postgres import pg_cash as pg_cash


def test_descriptor_tracks_persisted_revocation(pg_cash: tuple[sa.Engine, str, str]) -> None:
    engine, _, grant = pg_cash
    with Session(engine) as session:
        version = FinancialAuthority(session, CASHIER_ID, ORG_ID)._begin()
        before = session_financial_access(session, CASHIER_ID, ORG_ID, [BRANCH_A], version)
        assert before["branches"][0]["datasets"] == ["cash.shifts", "sales"]
    with Session(engine) as session:
        FinancialAccessService(session, ORG_ID).revoke(
            OWNER_ID, grant, "revoke-session-test", {"reason": "Revocation regression"}
        )
    with Session(engine) as session:
        version = FinancialAuthority(session, CASHIER_ID, ORG_ID)._begin()
        after = session_financial_access(session, CASHIER_ID, ORG_ID, [BRANCH_A], version)
        assert after["branches"][0]["datasets"] == ["sales"]
        assert session.scalar(sa.select(models.cash_shifts.c.opening_cash_cents)) == 12_345
