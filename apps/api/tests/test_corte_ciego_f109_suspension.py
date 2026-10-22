"""Suspension never turns a protected branch back into broad legacy access."""

import pytest
import sqlalchemy as sa
from corte_ciego_fixtures import BRANCH_A, CashWorld, cash_world, grant_permission
from restaurant_os import models
from restaurant_os import operations as ops
from restaurant_os.cash_views import active_revision
from restaurant_os.financial_authority import FinancialAuthority, authorize_capability_assignment
from sqlalchemy.orm import Session

__all__ = ["cash_world"]


def suspend(session: Session, branch: str = BRANCH_A) -> None:
    policy = dict(
        session.execute(
            sa.select(models.blind_cash_policy_revisions)
            .where(models.blind_cash_policy_revisions.c.branch_id == branch)
            .order_by(models.blind_cash_policy_revisions.c.revision.desc())
            .limit(1)
        )
        .mappings()
        .one()
    )
    session.execute(
        models.blind_cash_policy_revisions.insert().values(
            {
                **policy,
                "revision": policy["revision"] + 1,
                "event": "suspended",
                "created_at": ops._now(),
            }
        )
    )
    session.commit()


@pytest.mark.parametrize(
    "route",
    ["/api/v1/cash/shifts", "/api/v2/cash/shifts", "/api/v1/payments", "/api/v1/pos/rappi/orders"],
)
def test_suspended_policy_never_reopens_legacy_money(cash_world: CashWorld, route: str) -> None:
    world = cash_world
    original = world.snapshot()
    with world.sessions() as session:
        suspend(session)
    result = world.client.get(
        route, params={"branch_id": BRANCH_A}, headers=world.headers("cashier")
    )
    assert (
        result.status_code == 409 and result.json()["detail"]["code"] == "cash_policy_suspended"
    ), result.text
    assert "cents" not in result.text
    assert world.snapshot() == original


def test_both_policy_probes_fail_closed(cash_world: CashWorld) -> None:
    world = cash_world
    with world.sessions() as session:
        suspend(session)
        with pytest.raises(ops.BusinessError, match="suspended"):
            active_revision(session, BRANCH_A)
        with pytest.raises(ops.BusinessError, match="suspended"):
            FinancialAuthority(session, world.actors["owner"], ops.ORGANIZATION_ID).policy_revision(
                BRANCH_A
            )


def test_suspension_does_not_restore_admin_assignment_bypass(cash_world: CashWorld) -> None:
    world = cash_world
    with world.sessions() as session:
        grant_permission(session, world.roles["owner"], "inventory.count.review")
        suspend(session)
        permission = session.scalar(
            sa.select(models.permissions.c.id).where(
                models.permissions.c.code == "inventory.count.review"
            )
        )
        with pytest.raises(ops.AuthorizationError):
            authorize_capability_assignment(
                session, world.actors["administrator"], [str(permission)], ops.ORGANIZATION_ID
            )


def test_suspended_financial_denial_precedes_money_sql(cash_world: CashWorld) -> None:
    world = cash_world
    with world.sessions() as session:
        suspend(session)
    statements = []

    def observe(_conn, _cursor, sql, *_args):
        if sql.lstrip().upper().startswith("SELECT"):
            statements.append(sql)

    sa.event.listen(world.engine, "before_cursor_execute", observe)
    try:
        result = world.client.get(
            "/api/v1/payments", params={"branch_id": BRANCH_A}, headers=world.headers("owner")
        )
    finally:
        sa.event.remove(world.engine, "before_cursor_execute", observe)
    assert result.status_code == 409
    assert not any("payments.amount_cents" in sql for sql in statements)


def test_prepared_policy_before_first_activation_preserves_legacy(cash_world: CashWorld) -> None:
    world = cash_world
    with world.sessions() as session:
        original = dict(
            session.execute(sa.select(models.branches).where(models.branches.c.id == BRANCH_A))
            .mappings()
            .one()
        )
        branch = ops._id()
        session.execute(
            models.branches.insert().values({**original, "id": branch, "code": "PREP109"})
        )
        policy = dict(
            session.execute(
                sa.select(models.blind_cash_policy_revisions).where(
                    models.blind_cash_policy_revisions.c.branch_id == BRANCH_A
                )
            )
            .mappings()
            .one()
        )
        session.execute(
            models.blind_cash_policy_revisions.insert().values(
                {**policy, "branch_id": branch, "event": "prepared"}
            )
        )
        session.commit()
        assert active_revision(session, branch) is None
