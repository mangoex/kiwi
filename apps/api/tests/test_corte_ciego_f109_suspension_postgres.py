"""Suspension privacy floor on the real append-only PostgreSQL schema."""

import pytest
import sqlalchemy as sa
from restaurant_os import operations as ops
from restaurant_os.cash_views import active_revision
from restaurant_os.financial_authority import FinancialAuthority
from sqlalchemy.orm import Session
from test_cash_concepts import BRANCH_A, ORG_ID, OWNER_ID
from test_corte_ciego_f105_postgres import pg_cash as pg_cash
from test_corte_ciego_f109_suspension import suspend


def test_suspended_revision_does_not_reopen_legacy(pg_cash: tuple[sa.Engine, str, str]) -> None:
    engine, _, _ = pg_cash
    with Session(engine) as session:
        suspend(session)
        with pytest.raises(ops.BusinessError) as exc:
            active_revision(session, BRANCH_A)
        assert exc.value.code == "cash_policy_suspended"
        with pytest.raises(ops.BusinessError) as exc:
            FinancialAuthority(session, OWNER_ID, ORG_ID).policy_revision(BRANCH_A)
        assert exc.value.code == "cash_policy_suspended"
