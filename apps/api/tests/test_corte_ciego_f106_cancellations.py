"""Cancellation acknowledges the operation without disclosing financial history."""

from typing import Any

import pytest
import sqlalchemy as sa
from corte_ciego_approval_fixtures import approved
from restaurant_os import models
from restaurant_os import operations as ops
from restaurant_os.auth import create_session_token
from restaurant_os.config import get_settings
from sqlalchemy.orm import Session
from test_corte_ciego_f105_intents import activate
from test_corte_ciego_f106_amendments import AmendmentWorld
from test_corte_ciego_f106_amendments import amendment_world as amendment_world
from test_platform_api import ADMIN_USER_ID, _admin_headers


def cancel(world: AmendmentWorld) -> Any:
    return world.client.post(
        f"/api/v1/orders/{world.order}/cancel",
        headers=_admin_headers(),
        json={
            "reason": "Synthetic cancellation",
            "expected_version": 1,
            "exception_authorization_id": world.cancellation_authorization,
        },
    )


def test_cancel_returns_operational_receipt_and_preserves_history(
    amendment_world: AmendmentWorld,
) -> None:
    world = amendment_world
    activate(world.factory)
    with world.factory() as session:
        before = dict(session.execute(sa.select(models.orders)).mappings().one())
    result = cancel(world)
    assert result.status_code == 200, result.text
    assert "total_cents" not in result.json(), result.text
    assert result.json() == {
        "schema_version": 2,
        "projection": "operational",
        "policy_version": 1,
        "action": "order.cancel",
        "id": world.order,
        "order_id": world.order,
        "branch_id": before["branch_id"],
        "status": "CANCELLED",
        "cancellation_kind": "reservation_release",
        "classification": None,
    }
    assert result.headers["cache-control"] == "no-store"
    with world.factory() as session:
        after = dict(session.execute(sa.select(models.orders)).mappings().one())
        assert after == {**before, "status": "CANCELLED"}
        releases = list(session.execute(sa.select(models.inventory_movements)).mappings())
    assert cancel(world).status_code == 409
    with world.factory() as session:
        assert list(session.execute(sa.select(models.inventory_movements)).mappings()) == releases


def test_read_permission_is_required_before_cancellation(amendment_world: AmendmentWorld) -> None:
    world = amendment_world
    activate(world.factory)
    world.revoke("orders.read")
    result = cancel(world)
    assert result.status_code == 403, result.text
    with world.factory() as session:
        assert session.scalar(sa.select(models.orders.c.status)) == "ACCEPTED"


def test_receipt_audit_failure_rolls_back_every_effect(
    amendment_world: AmendmentWorld,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    world = amendment_world
    activate(world.factory)
    with world.factory() as session:
        before = list(session.execute(sa.select(models.inventory_movements)).mappings())
    audit = ops._audit

    def fail(session: Session, action: str, *args: Any, **kwargs: Any) -> Any:
        if action == "order.cancellation.receipt_read":
            raise sa.exc.SQLAlchemyError("PRIVATE-CANCEL-SQL")
        return audit(session, action, *args, **kwargs)

    monkeypatch.setattr(ops, "_audit", fail)
    result = cancel(world)
    assert result.status_code == 503 and "PRIVATE-CANCEL" not in result.text
    with world.factory() as session:
        assert session.scalar(sa.select(models.orders.c.status)) == "ACCEPTED"
        assert list(session.execute(sa.select(models.inventory_movements)).mappings()) == before
        assert (
            session.scalar(
                sa.select(sa.func.count())
                .select_from(models.order_events)
                .where(
                    models.order_events.c.event_type == "ORDER_CANCELLED",
                )
            )
            == 0
        )


def test_commit_false_is_owned_by_caller(amendment_world: AmendmentWorld) -> None:
    world = amendment_world
    activate(world.factory)
    with world.factory() as session:
        result = ops.cancel_order(
            session,
            world.order,
            reason="Synthetic cancellation",
            actor_user_id=ADMIN_USER_ID,
            commit=False,
            expected_version=1,
            exception_authorization_id=world.cancellation_authorization,
        )
        assert result["projection"] == "operational"
        assert session.scalar(sa.select(models.orders.c.status)) == "CANCELLED"
        session.rollback()
    with world.factory() as session:
        assert session.scalar(sa.select(models.orders.c.status)) == "ACCEPTED"


@pytest.mark.parametrize("typ", ["agent", "device"])
def test_cancellation_requires_human_identity(amendment_world: AmendmentWorld, typ: str) -> None:
    world = amendment_world
    activate(world.factory)
    token = create_session_token({"sub": ADMIN_USER_ID, "typ": typ}, get_settings().secret_key)
    result = world.client.post(
        f"/api/v1/orders/{world.order}/cancel",
        headers={"Authorization": f"Bearer {token}"},
        json={},
    )
    assert result.status_code == 403
    with world.factory() as session:
        assert session.scalar(sa.select(models.orders.c.status)) == "ACCEPTED"


def test_revoked_after_commit_does_not_deliver_receipt(
    amendment_world: AmendmentWorld,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    world = amendment_world
    activate(world.factory)
    commit = Session.commit
    revoked = False

    def revoke(session: Session) -> None:
        nonlocal revoked
        commit(session)
        if not revoked:
            revoked = True
            with world.factory() as other:
                other.execute(
                    models.users.update()
                    .where(
                        models.users.c.id == ADMIN_USER_ID,
                    )
                    .values(status="inactive")
                )
                commit(other)

    monkeypatch.setattr(Session, "commit", revoke)
    result = cancel(world)
    assert revoked and result.status_code == 403, result.text
    with world.factory() as session:
        assert session.scalar(sa.select(models.orders.c.status)) == "CANCELLED"
        assert (
            session.scalar(
                sa.select(sa.func.count())
                .select_from(models.order_events)
                .where(
                    models.order_events.c.event_type == "ORDER_CANCELLED",
                )
            )
            == 1
        )


def test_policy_activated_after_legacy_commit_blocks_original_response(
    amendment_world: AmendmentWorld,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    world = amendment_world
    commit = Session.commit
    activated = False

    def change_policy(session: Session) -> None:
        nonlocal activated
        commit(session)
        if not activated:
            activated = True
            activate(world.factory)

    monkeypatch.setattr(Session, "commit", change_policy)
    result = cancel(world)
    assert activated and result.status_code == 409 and "12300" not in result.text, result.text
    with world.factory() as session:
        assert session.scalar(sa.select(models.orders.c.status)) == "CANCELLED"


def test_cancel_permission_is_not_implied_by_read(amendment_world: AmendmentWorld) -> None:
    world = amendment_world
    activate(world.factory)
    world.revoke("orders.cancel")
    assert cancel(world).status_code == 403
    with world.factory() as session:
        assert session.scalar(sa.select(models.orders.c.status)) == "ACCEPTED"


@pytest.mark.parametrize("classification", ["waste", "recovery"])
def test_produced_order_keeps_classification_and_inventory_effect(
    amendment_world: AmendmentWorld,
    classification: str,
) -> None:
    world = amendment_world
    with world.factory() as session:
        task = session.scalar(sa.select(models.production_tasks.c.id))
    for status in ("IN_PROGRESS", "COMPLETED"):
        result = world.client.post(
            f"/api/v1/kds/tasks/{task}/transition",
            headers=_admin_headers(),
            json={"status": status},
        )
        assert result.status_code == 200, result.text
    activate(world.factory)
    assert cancel(world).status_code == 409
    with world.factory() as session:
        version = session.scalar(
            sa.select(models.orders.c.version).where(models.orders.c.id == world.order)
        )
    approval = approved(
        world.factory,
        world.order,
        "cancel",
        version,
        "Synthetic produced cancellation",
        {"classification": classification},
    )
    result = world.client.post(
        f"/api/v1/orders/{world.order}/cancel",
        headers=_admin_headers(),
        json={
            "reason": "Synthetic produced cancellation",
            "classification": classification,
            "expected_version": version,
            "exception_authorization_id": approval,
        },
    )
    assert result.status_code == 200 and "total_cents" not in result.json(), result.text
    assert result.json()["cancellation_kind"] == classification
    with world.factory() as session:
        amounts = list(
            session.scalars(
                sa.select(models.inventory_movements.c.quantity_delta).where(
                    models.inventory_movements.c.movement_type == classification.upper(),
                )
            )
        )
        assert amounts and all(
            value == 0 if classification == "waste" else value > 0 for value in amounts
        )


def test_cancellation_schema_matches_published_contract() -> None:
    import json
    from pathlib import Path

    from restaurant_os.order_cancellation_views import OrderCancellationReceiptV2

    schema = json.loads(
        (
            Path(__file__).resolve().parents[3]
            / "packages/contracts/schemas/order-cancellation-receipt-v2.schema.json"
        ).read_text()
    )
    assert schema == OrderCancellationReceiptV2.model_json_schema()
    assert schema["additionalProperties"] is False
