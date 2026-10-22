"""Current own-command authority for order correction receipts, without history rewrites."""

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

import pytest
import sqlalchemy as sa
from corte_ciego_fixtures import grant_permission
from restaurant_os import models
from restaurant_os import operations as ops
from restaurant_os.auth import create_session_token
from restaurant_os.config import get_settings
from sqlalchemy.orm import Session
from test_cash_concepts import OWNER_ID, OWNER_ROLE_ID, SECOND_OWNER_ID, _cash_concept_client
from test_cash_ledger import BRANCH_A, _insert_shift
from test_corte_ciego_f106_movements import activate
from test_order_corrections import _approved_simple_request, _plan
from test_order_reopen_workflow import CHIEF_ID, _actors, _order


@dataclass
class ReopenWorld:
    client: Any
    factory: Any
    order: str
    request: str

    def apply(self, actor: str = OWNER_ID, key: str = "f106-reopen-apply") -> Any:
        return self.client.post(
            f"/api/v1/orders/reopen-requests/{self.request}/apply",
            headers=headers(actor, key),
            json=_plan([]),
        )


def headers(
    actor: str = OWNER_ID, key: str = "f106-reopen-command", typ: str | None = None
) -> dict[str, str]:
    payload = {"sub": actor}
    if typ:
        payload["typ"] = typ
    return {
        "Authorization": "Bearer " + create_session_token(payload, get_settings().secret_key),
        "Idempotency-Key": key,
    }


@pytest.fixture
def reopen_world() -> Iterator[ReopenWorld]:
    client = _cash_concept_client()
    factory = client.app.state.test_session_factory
    with factory() as session:
        _insert_shift(session)
        _actors(session)
        order, request = _approved_simple_request(session, "f106-1")
        grant_permission(session, OWNER_ROLE_ID, "orders.read")
        session.commit()
    try:
        yield ReopenWorld(client, factory, order, str(request["id"]))
    finally:
        client.close()


def test_apply_receipt_keeps_refund_and_original_history(reopen_world: ReopenWorld) -> None:
    world = reopen_world
    activate(world.factory)
    result = world.apply()
    assert result.status_code == 200, result.text
    value = result.json()
    assert "settlement_delta_cents" not in value and "payment_adjustment" not in value
    assert value["projection"] == "operational" and value["status"] == "APPLIED"
    assert value["request_id"] == world.request and value["order_id"] == world.order
    assert result.headers["cache-control"] == "no-store"
    assert world.apply().json() == value
    with world.factory() as session:
        stored = session.scalar(
            sa.select(models.order_reopen_commands.c.response_snapshot).where(
                models.order_reopen_commands.c.command_type == "apply",
            )
        )
        assert stored["settlement_delta_cents"] == -500
        assert stored["payment_adjustment"]["amount_cents"] == 500
        assert session.scalar(sa.select(models.payments.c.amount_cents)) == 500
        assert (
            session.scalar(
                sa.select(models.orders.c.total_cents).where(models.orders.c.id == world.order)
            )
            == 500
        )
        assert session.scalar(sa.select(sa.func.count()).select_from(models.order_corrections)) == 1


def test_historical_replay_uses_read_authority_and_no_money_query(
    reopen_world: ReopenWorld,
) -> None:
    world = reopen_world
    assert world.apply().status_code == 200
    with world.factory() as session:
        original = session.scalar(
            sa.select(models.order_reopen_commands.c.response_snapshot).where(
                models.order_reopen_commands.c.command_type == "apply",
            )
        )
    activate(world.factory)
    # Reproduces the leak before separately exercising read-only recovery.
    assert "settlement_delta_cents" not in world.apply().json()
    with world.factory() as session:
        session.execute(
            models.role_authority_grants.delete().where(
                models.role_authority_grants.c.role_id == OWNER_ROLE_ID,
            )
        )
        session.commit()
    statements: list[str] = []

    def observe(_connection: Any, _cursor: Any, sql: str, *_args: Any) -> None:
        if sql.lstrip().upper().startswith("SELECT"):
            statements.append(sql)

    engine = world.factory.kw["bind"]
    sa.event.listen(engine, "before_cursor_execute", observe)
    try:
        recovered = world.apply()
    finally:
        sa.event.remove(engine, "before_cursor_execute", observe)
    assert recovered.status_code == 200, recovered.text
    assert not any(
        any(
            field in sql
            for field in ("response_snapshot", "before_snapshot", "total_cents", "amount_cents")
        )
        for sql in statements
    )
    assert world.apply(key="f106-reopen-new-action").status_code == 403
    with world.factory() as session:
        permission = session.scalar(
            sa.select(models.permissions.c.id).where(models.permissions.c.code == "orders.read")
        )
        session.execute(
            models.role_permissions.delete().where(
                models.role_permissions.c.role_id == OWNER_ROLE_ID,
                models.role_permissions.c.permission_id == permission,
            )
        )
        session.commit()
    assert world.apply().status_code == 403
    with world.factory() as session:
        assert (
            session.scalar(
                sa.select(models.order_reopen_commands.c.response_snapshot).where(
                    models.order_reopen_commands.c.command_type == "apply"
                )
            )
            == original
        )


def test_request_and_decision_receipts_cannot_transfer_between_actors(
    reopen_world: ReopenWorld,
) -> None:
    world = reopen_world
    activate(world.factory)
    with world.factory() as session:
        order = _order(session, 42)
    body = {"reason": "Review this exact order", "evidence_refs": ["ticket:42"]}
    path = f"/api/v1/orders/{order}/reopen-requests"
    response = world.client.post(path, headers=headers(CHIEF_ID, "f106-reopen-request"), json=body)
    assert response.status_code == 200, response.text
    assert response.json()["projection"] == "operational"
    transferred = world.client.post(
        path, headers=headers(OWNER_ID, "f106-reopen-request"), json=body
    )
    assert transferred.status_code in (403, 409), transferred.text
    request = response.json()["request_id"]
    path = f"/api/v1/orders/reopen-requests/{request}/approve"
    body = {"decision_reason": "Approve this exact request"}
    approved = world.client.post(path, headers=headers(), json=body)
    assert approved.status_code == 200, approved.text
    assert (
        approved.json()["status"] == "APPROVED" and approved.json()["projection"] == "operational"
    )
    transferred = world.client.post(path, headers=headers(SECOND_OWNER_ID), json=body)
    assert transferred.status_code in (403, 409), transferred.text


def test_list_selects_no_before_snapshot_and_revalidates_actor(reopen_world: ReopenWorld) -> None:
    world = reopen_world
    activate(world.factory)
    statements: list[str] = []
    engine = world.factory.kw["bind"]

    def observe(_connection: Any, _cursor: Any, sql: str, *_args: Any) -> None:
        if sql.lstrip().upper().startswith("SELECT"):
            statements.append(sql)

    sa.event.listen(engine, "before_cursor_execute", observe)
    try:
        response = world.client.get(
            "/api/v1/orders/reopen-requests", headers=headers(), params={"branch_id": BRANCH_A}
        )
    finally:
        sa.event.remove(engine, "before_cursor_execute", observe)
    assert response.status_code == 200, response.text
    assert not any("before_snapshot" in sql for sql in statements)
    with world.factory() as session:
        session.execute(
            models.users.update().where(models.users.c.id == OWNER_ID).values(status="inactive")
        )
        session.commit()
    assert (
        world.client.get(
            "/api/v1/orders/reopen-requests", headers=headers(), params={"branch_id": BRANCH_A}
        ).status_code
        == 403
    )


@pytest.mark.parametrize("typ", ["agent", "device"])
def test_human_reopen_endpoints_reject_technical_credentials(
    reopen_world: ReopenWorld, typ: str
) -> None:
    world = reopen_world
    activate(world.factory)
    auth = headers(typ=typ)
    assert (
        world.client.get(
            "/api/v1/orders/reopen-requests", headers=auth, params={"branch_id": BRANCH_A}
        ).status_code
        == 403
    )
    for path, body in (
        (
            f"/api/v1/orders/{world.order}/reopen-requests",
            {"reason": "Technical request", "evidence_refs": ["ticket:x"]},
        ),
        (
            f"/api/v1/orders/reopen-requests/{world.request}/approve",
            {"decision_reason": "Technical approval"},
        ),
        (
            f"/api/v1/orders/reopen-requests/{world.request}/reject",
            {"decision_reason": "Technical rejection"},
        ),
        (f"/api/v1/orders/reopen-requests/{world.request}/apply", _plan([])),
    ):
        assert world.client.post(path, headers=auth, json=body).status_code == 403


def test_receipt_audit_failure_rolls_back_correction(
    reopen_world: ReopenWorld, monkeypatch: pytest.MonkeyPatch
) -> None:
    world = reopen_world
    activate(world.factory)
    audit = ops._audit

    def fail(session: Session, action: str, *args: Any, **kwargs: Any) -> Any:
        if action == "order.reopen.receipt_read":
            raise sa.exc.SQLAlchemyError("PRIVATE-CORRECTION-SQL")
        return audit(session, action, *args, **kwargs)

    monkeypatch.setattr(ops, "_audit", fail)
    response = world.apply()
    assert response.status_code == 503 and "PRIVATE-CORRECTION" not in response.text
    with world.factory() as session:
        for table in (
            models.order_corrections,
            models.order_payment_adjustments,
            models.cash_movements,
        ):
            assert session.scalar(sa.select(sa.func.count()).select_from(table)) == 0
        assert (
            session.scalar(
                sa.select(models.order_reopen_requests.c.status).where(
                    models.order_reopen_requests.c.id == world.request
                )
            )
            == "APPROVED"
        )
        assert session.scalar(sa.select(models.payments.c.amount_cents)) == 500


def test_revocation_after_commit_blocks_delivery_but_recovery_does_not_repeat(
    reopen_world: ReopenWorld, monkeypatch: pytest.MonkeyPatch
) -> None:
    world = reopen_world
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
                    .where(models.users.c.id == OWNER_ID)
                    .values(status="inactive")
                )
                commit(other)

    monkeypatch.setattr(Session, "commit", revoke)
    response = world.apply()
    assert revoked and response.status_code == 403, response.text
    with world.factory() as session:
        assert session.scalar(sa.select(sa.func.count()).select_from(models.order_corrections)) == 1
        session.execute(
            models.users.update().where(models.users.c.id == OWNER_ID).values(status="active")
        )
        session.commit()
    recovered = world.apply()
    assert recovered.status_code == 200 and recovered.json()["projection"] == "operational", (
        recovered.text
    )
    with world.factory() as session:
        assert session.scalar(sa.select(sa.func.count()).select_from(models.order_corrections)) == 1


def test_financial_order_history_stays_available_only_to_authorized_reader(
    reopen_world: ReopenWorld,
) -> None:
    from test_cash_ledger import NOW, ORG_ID

    world = reopen_world
    activate(world.factory)
    assert world.apply().status_code == 200
    path = f"/api/v1/orders/{world.order}"
    denied = world.client.get(path, headers=headers(CHIEF_ID))
    assert denied.status_code == 403, denied.text
    with world.factory() as session:
        session.execute(
            models.financial_owner_reviews.insert().values(
                organization_id=ORG_ID,
                user_id=OWNER_ID,
                authorization_version=1,
                manifest_digest="d" * 64,
                approval_reference="synthetic reviewed Owner",
                reviewed_at=NOW,
            )
        )
        session.commit()
    response = world.client.get(path, headers=headers())
    assert response.status_code == 200, response.text
    assert response.json()["corrections"][0]["settlement_delta_cents"] == -500
    assert response.json()["total_cents"] == 500


def test_receipt_matches_published_closed_schema() -> None:
    import json
    from pathlib import Path

    from restaurant_os.order_reopen_views import OrderReopenReceiptV2

    schema = json.loads(
        (
            Path(__file__).resolve().parents[3]
            / "packages/contracts/schemas/order-reopen-receipt-v2.schema.json"
        ).read_text()
    )
    assert schema == OrderReopenReceiptV2.model_json_schema()
    assert schema["additionalProperties"] is False


def test_empty_all_branch_list_still_requires_current_actor(reopen_world: ReopenWorld) -> None:
    world = reopen_world
    activate(world.factory)
    with world.factory() as session:
        session.execute(
            models.users.update().where(models.users.c.id == OWNER_ID).values(status="inactive")
        )
        session.commit()
    result = world.client.get(
        "/api/v1/orders/reopen-requests", headers=headers(), params={"status": "REJECTED"}
    )
    assert result.status_code == 403, result.text


@pytest.mark.parametrize("action", ["request", "approve"])
def test_request_and_decision_share_receipt_audit_transaction(
    reopen_world: ReopenWorld,
    monkeypatch: pytest.MonkeyPatch,
    action: str,
) -> None:
    world = reopen_world
    with world.factory() as session:
        order = _order(session, 43)
        request = None
        if action == "approve":
            request = ops.create_order_reopen_request(
                session,
                order,
                {"reason": "Synthetic transaction setup", "evidence_refs": ["ticket:43"]},
                "f106-reopen-audit-setup",
                CHIEF_ID,
            )["id"]
    activate(world.factory)
    audit = ops._audit

    def fail(session: Session, action: str, *args: Any, **kwargs: Any) -> Any:
        if action == "order.reopen.receipt_read":
            raise sa.exc.SQLAlchemyError("synthetic receipt failure")
        return audit(session, action, *args, **kwargs)

    monkeypatch.setattr(ops, "_audit", fail)
    if action == "request":
        path = f"/api/v1/orders/{order}/reopen-requests"
        body = {"reason": "Synthetic audit failure", "evidence_refs": ["ticket:43"]}
        actor = CHIEF_ID
    else:
        path = f"/api/v1/orders/reopen-requests/{request}/approve"
        body = {"decision_reason": "Synthetic audit failure"}
        actor = OWNER_ID
    result = world.client.post(path, headers=headers(actor, "f106-reopen-audit-failed"), json=body)
    assert result.status_code == 503, result.text
    with world.factory() as session:
        assert (
            session.scalar(
                sa.select(models.order_reopen_commands.c.id).where(
                    models.order_reopen_commands.c.idempotency_key == "f106-reopen-audit-failed",
                )
            )
            is None
        )
        status = session.scalar(
            sa.select(models.order_reopen_requests.c.status).where(
                models.order_reopen_requests.c.order_id == order
            )
        )
        assert status == (None if action == "request" else "REQUESTED")
