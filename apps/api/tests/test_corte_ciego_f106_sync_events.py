"""Historical sync transport must not become a human financial export."""

from datetime import datetime, timezone
from typing import Any

import pytest
import sqlalchemy as sa
from corte_ciego_fixtures import BRANCH_A, BRANCH_B, ORG_ID, CashWorld, cash_world, grant_permission
from restaurant_os import models
from restaurant_os import operations as ops
from restaurant_os.auth import create_session_token
from restaurant_os.config import get_settings
from restaurant_os.sync_event_views import SyncEventOperationalV2, human_sync_events
from sqlalchemy.orm import Session

__all__ = ["cash_world"]


def seed_event(session: Session, actor: str, branch: str = BRANCH_A) -> str:
    now = datetime.now(timezone.utc)
    command, event = ops._id(), ops._id()
    session.execute(
        models.sync_commands.insert().values(
            id=command,
            organization_id=ORG_ID,
            branch_id=branch,
            source_device_id=ops._id(),
            actor_user_id=actor,
            command_id=ops._id(),
            idempotency_key=ops._id(),
            command_type="synthetic.historical",
            payload={"amount_cents": 95123},
            status="CONFIRMED",
            checkpoint=1,
            occurred_at=now,
            received_at=now,
            confirmed_at=now,
        )
    )
    session.execute(
        models.sync_events.insert().values(
            id=event,
            organization_id=ORG_ID,
            branch_id=branch,
            sync_command_id=command,
            event_type="PRIVATE-SYNC-95123",
            checkpoint=1,
            payload={"amount_cents": 95123},
            occurred_at=now,
        )
    )
    session.commit()
    return event


def test_human_diagnostic_cannot_read_original_payload(cash_world: CashWorld) -> None:
    world = cash_world
    with world.sessions() as session:
        grant_permission(session, world.roles["cashier"], "sync.events.read")
        seed_event(session, world.actors["cashier"])
    token = create_session_token({"sub": world.actors["cashier"]}, get_settings().secret_key)
    result = world.client.get(
        "/api/v1/sync/events",
        params={"branch_id": BRANCH_A},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert result.status_code == 200, result.text
    assert (
        "95123" not in result.text
        and "payload" not in result.text
        and "event_type" not in result.text
    ), result.text
    assert result.json()[0]["projection"] == "operational"
    assert result.headers["cache-control"] == "no-store"


def test_projection_uses_only_metadata_sql_and_preserves_original(cash_world: CashWorld) -> None:
    world = cash_world
    with world.sessions() as session:
        grant_permission(session, world.roles["cashier"], "sync.events.read")
        seed_event(session, world.actors["cashier"])
        original = dict(session.execute(sa.select(models.sync_events)).mappings().one())
    statements: list[str] = []

    def observe(_conn: Any, _cursor: Any, sql: str, *_args: Any) -> None:
        if sql.lstrip().upper().startswith("SELECT"):
            statements.append(sql)

    sa.event.listen(world.engine, "before_cursor_execute", observe)
    try:
        with world.sessions() as session:
            result = human_sync_events(
                session,
                ORG_ID,
                BRANCH_A,
                0,
                world.actors["cashier"],
                lambda: pytest.fail("Legacy transport"),
            )
            assert len(result) == 1 and set(result[0]) == set(SyncEventOperationalV2.model_fields)
            assert (
                human_sync_events(
                    session,
                    ORG_ID,
                    BRANCH_A,
                    1,
                    world.actors["cashier"],
                    lambda: pytest.fail("Legacy transport"),
                )
                == []
            )
    finally:
        sa.event.remove(world.engine, "before_cursor_execute", observe)
    assert not any(
        field in sql
        for sql in statements
        for field in ("sync_events.payload", "sync_events.event_type", "sync_commands.payload")
    )
    with world.sessions() as session:
        assert dict(session.execute(sa.select(models.sync_events)).mappings().one()) == original


def test_diagnostic_permission_and_scope_are_required_in_service(cash_world: CashWorld) -> None:
    world = cash_world
    with world.sessions() as session, pytest.raises(ops.AuthorizationError):
        human_sync_events(session, ORG_ID, BRANCH_A, 0, world.actors["cashier"], lambda: [])
    with world.sessions() as session:
        grant_permission(session, world.roles["cashier"], "sync.events.read")
        session.commit()
    for actor, branch in [(world.actors["foreign"], BRANCH_A), (world.actors["cashier"], BRANCH_B)]:
        with world.sessions() as session, pytest.raises(ops.AuthorizationError):
            human_sync_events(session, ORG_ID, branch, 0, actor, lambda: [])


@pytest.mark.parametrize("typ", ["agent", "device"])
def test_technical_bearer_does_not_enter_human_diagnostics(cash_world: CashWorld, typ: str) -> None:
    world = cash_world
    token = create_session_token(
        {"sub": world.actors["owner"], "typ": typ}, get_settings().secret_key
    )
    result = world.client.get(
        "/api/v1/sync/events",
        params={"branch_id": BRANCH_A},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert result.status_code == 403


def test_audit_failure_prevents_diagnostic_response(
    cash_world: CashWorld, monkeypatch: pytest.MonkeyPatch
) -> None:
    world = cash_world
    with world.sessions() as session:
        grant_permission(session, world.roles["cashier"], "sync.events.read")
        seed_event(session, world.actors["cashier"])
    audit = ops._audit

    def fail(session: Session, action: str, *args: Any, **kwargs: Any) -> Any:
        if action == "sync.events.read":
            raise sa.exc.SQLAlchemyError("PRIVATE-SYNC-95123")
        return audit(session, action, *args, **kwargs)

    monkeypatch.setattr(ops, "_audit", fail)
    token = create_session_token({"sub": world.actors["cashier"]}, get_settings().secret_key)
    result = world.client.get(
        "/api/v1/sync/events",
        params={"branch_id": BRANCH_A},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert result.status_code == 503 and "95123" not in result.text


def test_revocation_after_commit_blocks_delivery(
    cash_world: CashWorld, monkeypatch: pytest.MonkeyPatch
) -> None:
    world = cash_world
    with world.sessions() as session:
        grant_permission(session, world.roles["cashier"], "sync.events.read")
        seed_event(session, world.actors["cashier"])
    commit = Session.commit
    changed = False

    def change(session: Session) -> None:
        nonlocal changed
        commit(session)
        if not changed:
            changed = True
            with world.sessions() as writer:
                writer.execute(
                    models.users.update()
                    .where(models.users.c.id == world.actors["cashier"])
                    .values(status="inactive")
                )
                commit(writer)

    monkeypatch.setattr(Session, "commit", change)
    with world.sessions() as session, pytest.raises(ops.AuthorizationError):
        human_sync_events(session, ORG_ID, BRANCH_A, 0, world.actors["cashier"], lambda: [])
    assert changed
