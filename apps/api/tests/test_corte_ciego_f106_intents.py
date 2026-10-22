"""Own intent recovery uses present read authority, never historical money snapshots."""

from typing import Any

import pytest
import sqlalchemy as sa
from restaurant_os import models
from restaurant_os import operations as ops
from restaurant_os.auth import create_session_token
from restaurant_os.config import get_settings
from sqlalchemy.orm import Session
from test_branch_workspace_authority import workspace as workspace
from test_corte_ciego_f105_intents import activate
from test_operational_intents import (
    _execute_order,
    _grant_permission,
    _order_body,
    _prepare_command,
)
from test_operational_intents import operational as operational
from test_platform_api import ADMIN_ROLE_ID, ADMIN_USER_ID, BRANCH_ID


@pytest.fixture(autouse=True)
def explicit_operator(operational: Any) -> None:
    # Workspace fixture starts with organizational authority. Remove that alternate
    # grant so deleting one permission actually revokes it for this synthetic actor.
    _, factory, _ = operational
    with factory() as session:
        for code in ("orders.read", "orders.create", "payments.confirm"):
            _grant_permission(session, code)
        session.execute(
            models.role_authority_grants.delete().where(
                models.role_authority_grants.c.role_id == ADMIN_ROLE_ID
            )
        )
        session.commit()


def remove_permission(factory: Any, code: str) -> None:
    with factory() as session:
        permission = session.scalar(
            sa.select(models.permissions.c.id).where(models.permissions.c.code == code)
        )
        session.execute(
            models.role_permissions.delete().where(
                models.role_permissions.c.role_id == ADMIN_ROLE_ID,
                models.role_permissions.c.permission_id == permission,
            )
        )
        session.commit()


def test_historical_intent_recovers_metadata_without_loading_money(operational: Any) -> None:
    client, factory, headers = operational
    intent, _, order = _execute_order(operational)
    activate(factory)
    remove_permission(factory, "orders.create")
    statements: list[str] = []
    with factory() as session:
        engine = session.get_bind()

    def observe(_conn: Any, _cursor: Any, sql: str, *_args: Any) -> None:
        if sql.lstrip().upper().startswith("SELECT"):
            statements.append(sql)

    sa.event.listen(engine, "before_cursor_execute", observe)
    try:
        result = client.post(f"/api/v1/operational-intents/{intent['id']}/resolve", headers=headers)
    finally:
        sa.event.remove(engine, "before_cursor_execute", observe)
    assert result.status_code == 200, result.text
    assert result.json() == {**intent, "state": "acknowledged", "resource_id": order["id"]}
    assert result.headers["cache-control"] == "no-store"
    assert not any("response_snapshot" in sql or "orders.total_cents" in sql for sql in statements)
    with factory() as session:
        assert (
            session.scalar(sa.select(models.order_create_commands.c.response_snapshot))[
                "total_cents"
            ]
            > 0
        )


@pytest.mark.parametrize("route", ["list", "resolve"])
def test_read_revocation_denies_own_intent_without_resolving(operational: Any, route: str) -> None:
    client, factory, headers = operational
    intent, _, _ = _execute_order(operational)
    activate(factory)
    remove_permission(factory, "orders.read")
    result = (
        client.get("/api/v1/operational-intents", headers=headers)
        if route == "list"
        else client.post(f"/api/v1/operational-intents/{intent['id']}/resolve", headers=headers)
    )
    assert result.status_code == 403, result.text
    with factory() as session:
        assert session.scalar(sa.select(models.operational_command_intents.c.state)) == "applied"


def test_active_policy_requires_receipt_read_before_preparation(operational: Any) -> None:
    client, factory, headers = operational
    activate(factory)
    remove_permission(factory, "orders.read")
    result = client.post(
        "/api/v1/operational-intents",
        headers={**headers, "Idempotency-Key": "f106-unreadable-preparation"},
        json={"kind": "order.create", "target_id": None, "payload": _order_body()},
    )
    assert result.status_code == 403, result.text
    with factory() as session:
        assert (
            session.scalar(
                sa.select(sa.func.count()).select_from(models.operational_command_intents)
            )
            == 0
        )


@pytest.mark.parametrize("typ", ["agent", "device"])
def test_intent_human_routes_reject_service_audience(operational: Any, typ: str) -> None:
    client, factory, headers = operational
    intent = _prepare_command(client, headers, "order.create", _order_body(), "f106-token-intent")
    activate(factory)
    token = create_session_token({"sub": ADMIN_USER_ID, "typ": typ}, get_settings().secret_key)
    auth = {**headers, "Authorization": f"Bearer {token}", "Idempotency-Key": "f106-token-prepare"}
    responses = [
        client.get("/api/v1/operational-intents", headers=auth),
        client.post(f"/api/v1/operational-intents/{intent['id']}/resolve", headers=auth),
        client.post(
            "/api/v1/operational-intents",
            headers=auth,
            json={"kind": "order.create", "target_id": None, "payload": _order_body()},
        ),
    ]
    assert [response.status_code for response in responses] == [403, 403, 403]


def test_cash_intent_uses_cash_read_not_order_read(operational: Any) -> None:
    client, factory, headers = operational
    activate(factory)
    remove_permission(factory, "orders.read")
    body = {"branch_id": BRANCH_ID, "register_id": "F106-INTENT", "opening_cash_cents": 100}
    intent = _prepare_command(client, headers, "cash.shift.open", body, "f106-cash-intent")
    result = client.post(f"/api/v1/operational-intents/{intent['id']}/resolve", headers=headers)
    assert result.status_code == 200 and result.json()["state"] == "no_effect"
    remove_permission(factory, "cash.shift.read")
    denied = client.post(f"/api/v1/operational-intents/{intent['id']}/resolve", headers=headers)
    assert denied.status_code == 403, denied.text


def test_recovery_rechecks_read_after_commit(
    operational: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, factory, headers = operational
    intent, _, _ = _execute_order(operational)
    activate(factory)
    commit = Session.commit
    revoked = False

    def revoke_after_commit(session: Session) -> None:
        nonlocal revoked
        commit(session)
        if not revoked:
            revoked = True
            remove_permission(factory, "orders.read")

    monkeypatch.setattr(Session, "commit", revoke_after_commit)
    result = client.post(f"/api/v1/operational-intents/{intent['id']}/resolve", headers=headers)
    assert revoked and result.status_code == 403, result.text
    with factory() as session:
        assert (
            session.scalar(sa.select(models.operational_command_intents.c.state)) == "acknowledged"
        )
        assert (
            session.scalar(sa.select(sa.func.count()).select_from(models.order_create_commands))
            == 1
        )


def test_receipt_failure_keeps_intent_pending_and_private(
    operational: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, factory, headers = operational
    intent, _, _ = _execute_order(operational)
    activate(factory)
    audit = ops._audit

    def fail_audit(session: Session, action: str, *args: Any, **kwargs: Any) -> Any:
        if action == "operational_command.acknowledged":
            raise sa.exc.SQLAlchemyError("PRIVATE-INTENT-SQL")
        return audit(session, action, *args, **kwargs)

    monkeypatch.setattr(ops, "_audit", fail_audit)
    result = client.post(f"/api/v1/operational-intents/{intent['id']}/resolve", headers=headers)
    assert result.status_code == 503 and "PRIVATE-INTENT" not in result.text
    with factory() as session:
        assert session.scalar(sa.select(models.operational_command_intents.c.state)) == "applied"
