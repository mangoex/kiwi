"""Driver history is a scoped financial read, never an administrative money bypass."""

from typing import Any

import pytest
import sqlalchemy as sa
from corte_ciego_fixtures import BRANCH_A, BRANCH_B, ORG_ID, CashWorld, cash_world, ident
from restaurant_os import models
from restaurant_os import operations as ops
from restaurant_os.auth import create_session_token
from restaurant_os.config import get_settings
from sqlalchemy.orm import Session

__all__ = ["cash_world"]


def seed_history(session: Session, actor: str, orders: list[str]) -> str:
    driver = ops.create_driver(
        session,
        BRANCH_A,
        {
            "employee_code": "HST106",
            "name": "Synthetic history driver",
            "license_number": "LIC-HST106",
            "motorcycle_plate": "HST106",
            "phone": "6691234567",
            "address": "Synthetic address",
            "emergency_contact_name": "Synthetic contact",
        },
        actor,
    )
    for order_id in orders:
        order = (
            session.execute(sa.select(models.orders).where(models.orders.c.id == order_id))
            .mappings()
            .one()
        )
        # Frozen historical assignments in two branches, not edits to existing history.
        session.execute(
            models.delivery_assignments.insert().values(
                id=ops._id(),
                organization_id=ORG_ID,
                branch_id=order["branch_id"],
                order_id=order_id,
                driver_id=driver["id"],
                customer_id=None,
                driver_name_snapshot="Synthetic history driver",
                customer_name_snapshot="Synthetic customer",
                delivery_address_snapshot={"address_text": "Synthetic private history"},
                order_total_cents=order["total_cents"],
                currency="MXN",
                line_count=1,
                item_quantity=1,
                status="ASSIGNED",
                assigned_by=actor,
                assigned_at=order["created_at"],
            )
        )
    session.commit()
    return str(driver["id"])


def history(world: CashWorld, driver: str, actor: str, branch: str | None = None) -> Any:
    return world.client.get(
        f"/api/v1/drivers/{driver}/deliveries",
        headers=world.headers(actor),
        params={} if branch is None else {"branch_id": branch},
    )


def test_admin_permission_does_not_authorize_financial_history(cash_world: CashWorld) -> None:
    world = cash_world
    with world.sessions() as session:
        driver = seed_history(session, world.actors["owner"], [ident("order:1"), ident("order-b")])
    result = history(world, driver, "administrator")
    assert result.status_code == 403 and "order_total_cents" not in result.text, result.text


def test_delegate_has_only_explicit_branch_and_dataset(cash_world: CashWorld) -> None:
    world = cash_world
    with world.sessions() as session:
        driver = seed_history(session, world.actors["owner"], [ident("order:1"), ident("order-b")])
    assert history(world, driver, "delegate").status_code == 403
    assert history(world, driver, "delegate", BRANCH_A).status_code == 403
    allowed = history(world, driver, "delegate", BRANCH_B)
    assert allowed.status_code == 200, allowed.text
    assert len(allowed.json()) == 1 and allowed.json()[0]["branch_id"] == BRANCH_B
    assert allowed.headers["cache-control"] == "no-store"
    world.revoke("delegate", "sales-b")
    assert history(world, driver, "delegate", BRANCH_B).status_code == 403


def test_owner_reads_original_history_without_modification(cash_world: CashWorld) -> None:
    world = cash_world
    with world.sessions() as session:
        driver = seed_history(session, world.actors["owner"], [ident("order:1"), ident("order-b")])
        before = list(session.execute(sa.select(models.delivery_assignments)).mappings())
    result = history(world, driver, "owner")
    assert result.status_code == 200 and len(result.json()) == 2, result.text
    assert {row["branch_id"] for row in result.json()} == {BRANCH_A, BRANCH_B}
    assert all(row["order_total_cents"] == 5000 for row in result.json())
    with world.sessions() as session:
        assert list(session.execute(sa.select(models.delivery_assignments)).mappings()) == before
        audit = (
            session.execute(
                sa.select(models.audit_events).where(
                    models.audit_events.c.action == "driver.deliveries.read",
                )
            )
            .mappings()
            .one()
        )
        assert "5000" not in str(audit["payload"]) and "private history" not in str(
            audit["payload"]
        )
        assert audit["actor_user_id"] == world.actors["owner"]


def test_denial_precedes_money_query_in_domain_and_http(cash_world: CashWorld) -> None:
    world = cash_world
    with world.sessions() as session:
        driver = seed_history(session, world.actors["owner"], [ident("order:1")])
    queries: list[str] = []

    def observe(_conn: Any, _cursor: Any, sql: str, *_args: Any) -> None:
        if sql.lstrip().upper().startswith("SELECT"):
            queries.append(sql)

    sa.event.listen(world.engine, "before_cursor_execute", observe)
    try:
        assert history(world, driver, "administrator", BRANCH_A).status_code == 403
        with world.sessions() as session, pytest.raises(ops.AuthorizationError):
            ops.list_driver_deliveries(
                session, driver, world.actors["administrator"], branch_id=BRANCH_A
            )
    finally:
        sa.event.remove(world.engine, "before_cursor_execute", observe)
    assert not any("delivery_assignments.order_total_cents" in query for query in queries)


def test_financial_authority_does_not_replace_administrative_permission(
    cash_world: CashWorld,
) -> None:
    world = cash_world
    with world.sessions() as session:
        driver = seed_history(session, world.actors["owner"], [ident("order-b")])
        permission = session.scalar(
            sa.select(models.permissions.c.id).where(models.permissions.c.code == "admin.manage")
        )
        session.execute(
            models.role_permissions.delete().where(
                models.role_permissions.c.role_id == world.roles["delegate"],
                models.role_permissions.c.permission_id == permission,
            )
        )
        session.commit()
    assert history(world, driver, "delegate", BRANCH_B).status_code == 403


@pytest.mark.parametrize("typ", ["agent", "device"])
def test_history_rejects_technical_identity(cash_world: CashWorld, typ: str) -> None:
    world = cash_world
    with world.sessions() as session:
        driver = seed_history(session, world.actors["owner"], [ident("order:1")])
    token = create_session_token(
        {"sub": world.actors["owner"], "typ": typ}, get_settings().secret_key
    )
    result = world.client.get(
        f"/api/v1/drivers/{driver}/deliveries", headers={"Authorization": f"Bearer {token}"}
    )
    assert result.status_code == 403 and "order_total_cents" not in result.text


def test_history_rejects_foreign_scope_and_identity(cash_world: CashWorld) -> None:
    world = cash_world
    with world.sessions() as session:
        driver = seed_history(session, world.actors["owner"], [ident("order:1")])
    assert history(world, driver, "owner", ident("nonexistent-branch")).status_code == 403
    assert history(world, driver, "foreign", BRANCH_A).status_code == 403


def test_audit_failure_prevents_delivery(
    cash_world: CashWorld, monkeypatch: pytest.MonkeyPatch
) -> None:
    world = cash_world
    with world.sessions() as session:
        driver = seed_history(session, world.actors["owner"], [ident("order:1")])
    audit = ops._audit

    def fail(session: Session, action: str, *args: Any, **kwargs: Any) -> Any:
        if action == "driver.deliveries.read":
            raise sa.exc.SQLAlchemyError("PRIVATE-HISTORY-SQL")
        return audit(session, action, *args, **kwargs)

    monkeypatch.setattr(ops, "_audit", fail)
    result = history(world, driver, "owner", BRANCH_A)
    assert (
        result.status_code == 503
        and "PRIVATE-HISTORY" not in result.text
        and "5000" not in result.text
    )
    with world.sessions() as session:
        assert (
            session.scalar(
                sa.select(sa.func.count())
                .select_from(models.audit_events)
                .where(
                    models.audit_events.c.action == "driver.deliveries.read",
                )
            )
            == 0
        )
        assert session.scalar(sa.select(models.delivery_assignments.c.order_total_cents)) == 5000


def test_revoked_after_read_commit_does_not_deliver(
    cash_world: CashWorld, monkeypatch: pytest.MonkeyPatch
) -> None:
    world = cash_world
    with world.sessions() as session:
        driver = seed_history(session, world.actors["owner"], [ident("order-b")])
    commit = Session.commit
    revoked = False

    def revoke(session: Session) -> None:
        nonlocal revoked
        commit(session)
        if not revoked:
            revoked = True
            world.revoke("delegate", "sales-b")

    monkeypatch.setattr(Session, "commit", revoke)
    result = history(world, driver, "delegate", BRANCH_B)
    assert revoked and result.status_code == 403 and "5000" not in result.text, result.text
