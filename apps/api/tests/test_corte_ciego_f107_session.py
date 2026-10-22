"""Session navigation metadata must mirror effective, current authority."""

import pytest
import sqlalchemy as sa
from corte_ciego_fixtures import BRANCH_A, BRANCH_B, CashWorld, cash_world
from restaurant_os import operations as ops
from restaurant_os.auth import create_session_token
from restaurant_os.config import get_settings
from restaurant_os.financial_access_schema import DATASETS
from test_corte_ciego_f109_suspension import suspend

__all__ = ["cash_world"]


def test_session_exposes_scoped_financial_authority(cash_world: CashWorld) -> None:
    world = cash_world
    with world.sessions() as session:
        profile = ops.build_session_profile(session, world.actors["delegate"])
    access = profile.get("financial_access")
    assert access is not None, "Session lacks effective financial access"
    assert access["schema_version"] == 2
    branches = {row["branch_id"]: row for row in access["branches"]}
    assert branches[BRANCH_A]["datasets"] == ["cash.cuts"]
    assert branches[BRANCH_B]["datasets"] == ["sales"]
    assert not branches[BRANCH_A]["capabilities"]["cash.user_cut.finalize"]


def test_owner_and_cashier_receive_distinct_actions_without_totals(cash_world: CashWorld) -> None:
    world = cash_world
    world.revoke("cashier", "cashier-prior-cuts-a")
    with world.sessions() as session:
        owner = ops.build_session_profile(session, world.actors["owner"])["financial_access"]
        cashier = ops.build_session_profile(session, world.actors["cashier"])["financial_access"]
    for branch in owner["branches"]:
        assert set(branch["datasets"]) == set(DATASETS)
        assert branch["capabilities"]["cash.user_cut.finalize"]
        assert branch["capabilities"]["financial.delegations.manage"]
    for branch in cashier["branches"]:
        assert branch["datasets"] == []
        assert branch["capabilities"]["cash.user_cut.capture"]
        assert not branch["capabilities"]["cash.user_cut.finalize"]
    assert "cents" not in str(owner) and "grant_id" not in str(owner)


def test_revoked_scope_disappears_from_next_session(cash_world: CashWorld) -> None:
    world = cash_world
    world.revoke("delegate", "sales-b")
    with world.sessions() as session:
        access = ops.build_session_profile(session, world.actors["delegate"])["financial_access"]
    assert all("sales" not in row["datasets"] for row in access["branches"])


def test_suspended_policy_keeps_only_session_metadata(cash_world: CashWorld) -> None:
    world = cash_world
    with world.sessions() as session:
        suspend(session)
        access = ops.build_session_profile(session, world.actors["owner"])["financial_access"]
    branch = next(row for row in access["branches"] if row["branch_id"] == BRANCH_A)
    assert branch == {
        "branch_id": BRANCH_A,
        "policy_version": 2,
        "state": "suspended",
        "capabilities": {},
        "datasets": [],
    }


@pytest.mark.parametrize("typ", ["agent", "device"])
def test_session_financial_metadata_is_for_humans(cash_world: CashWorld, typ: str) -> None:
    world = cash_world
    token = create_session_token(
        {"sub": world.actors["owner"], "typ": typ}, get_settings().secret_key
    )
    response = world.client.get(
        "/api/v1/auth/session", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 403 and "financial_access" not in response.json()


def test_session_response_is_not_cacheable(cash_world: CashWorld) -> None:
    world = cash_world
    token = create_session_token({"sub": world.actors["cashier"]}, get_settings().secret_key)
    response = world.client.get(
        "/api/v1/auth/session", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200 and response.headers.get("cache-control") == "no-store"
    assert {row["branch_id"] for row in response.json()["financial_access"]["branches"]}.issubset(
        response.json()["scope"]["allowed_branch_ids"]
    )


def test_session_descriptor_has_bounded_query_count(cash_world: CashWorld) -> None:
    from restaurant_os.financial_session import session_financial_access

    world = cash_world
    queries = []

    def observe(_conn, _cursor, sql, *_args):
        if sql.lstrip().upper().startswith("SELECT"):
            queries.append(sql)

    sa.event.listen(world.engine, "before_cursor_execute", observe)
    try:
        with world.sessions() as session:
            access = session_financial_access(
                session, world.actors["owner"], ops.ORGANIZATION_ID, [BRANCH_A, BRANCH_B], 1
            )
            assert len(access["branches"]) == 2
    finally:
        sa.event.remove(world.engine, "before_cursor_execute", observe)
    assert len(queries) <= 30, f"Descriptor performs {len(queries)} SELECTs for two branches"
