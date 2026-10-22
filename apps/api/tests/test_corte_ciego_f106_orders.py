"""TC-450/462: an order identifier or request alone is not monetary authority."""

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

import pytest
import sqlalchemy as sa
from corte_ciego_fixtures import CashWorld, _actor, cash_world, grant_permission, ident
from fastapi.testclient import TestClient
from restaurant_os import models
from restaurant_os import operations as ops
from sqlalchemy.orm import Session, sessionmaker
from test_cash_ledger import NOW
from test_platform_api import (
    BRANCH_ID,
    _admin_headers,
    _client_with_seeded_database,
    _open_shift,
    _test_session_factory,
)

__all__ = ["cash_world"]


@dataclass
class AttendedWorld:
    client: TestClient
    sessions: sessionmaker[Session]
    actor_id: str
    role_id: str
    order_id: str
    shift_id: str

    def read(self, version: int = 1) -> Any:
        return self.client.get(
            f"/api/v2/orders/{self.order_id}",
            params={"expected_version": version},
            headers={"X-Actor-User-Id": self.actor_id},
        )


@pytest.fixture
def attended_world() -> Iterator[AttendedWorld]:
    client = _client_with_seeded_database()
    role = client.post(
        "/api/v1/roles", headers=_admin_headers(), json={"name": "Cajero", "scope": "branch"}
    )
    assert role.status_code == 200, role.text
    role_id = role.json()["id"]
    user = client.post(
        "/api/v1/users",
        headers=_admin_headers(),
        json={
            "email": "attention@fixture.invalid",
            "display_name": "Attention cashier",
            "employee_code": "ATT001",
            "password": ident("synthetic-f106-user").upper() + "Aa1!",
            "role_id": role_id,
            "branch_id": BRANCH_ID,
        },
    )
    assert user.status_code == 200, user.text
    actor = user.json()["id"]
    headers = {"X-Actor-User-Id": actor}
    opened = _open_shift(client, 10000, headers)
    assert opened.status_code == 200, opened.text
    sessions = _test_session_factory(client)
    with sessions() as session:
        shift_id = session.scalar(
            sa.select(models.cash_shifts.c.id).where(
                models.cash_shifts.c.branch_id == BRANCH_ID,
                models.cash_shifts.c.status == "OPEN",
            )
        )
        session.execute(
            models.blind_cash_policy_revisions.insert().values(
                organization_id=ops.ORGANIZATION_ID,
                branch_id=BRANCH_ID,
                revision=1,
                manifest_digest="a" * 64,
                minimum_api_version=2,
                minimum_client_version=2,
                minimum_gateway_version=2,
                event="activated",
                created_at=NOW,
            )
        )
        session.commit()
    created = client.post(
        "/api/v1/orders",
        headers={**headers, "Idempotency-Key": "attended-order-001"},
        json={"lines": [{"product_id": "018f6f73-2d0a-74f0-8f1c-000000000111", "quantity": 1}]},
    )
    assert created.status_code == 200, created.text
    assert created.json()["projection"] == "operational"
    assert "total_cents" not in created.json()
    try:
        yield AttendedWorld(client, sessions, actor, role_id, created.json()["id"], str(shift_id))
    finally:
        client.close()


def test_actual_checkout_authorizes_only_its_order_and_persists_read_audit(
    attended_world: AttendedWorld,
) -> None:
    world = attended_world
    response = world.read()
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    value = response.json()
    import json
    from pathlib import Path

    import jsonschema

    schema = json.loads(
        (
            Path(__file__).resolve().parents[3]
            / "packages/contracts/schemas/attended-order-detail-v2.schema.json"
        ).read_text()
    )
    jsonschema.validate(value, schema)
    assert value["total_cents"] == 9500 and value["lines"][0]["line_total_cents"] == 9500
    assert value["projection"] == "order"
    assert value["read_context"]["source_kind"] == "order_acceptance"
    assert not {
        "events",
        "sales_operation_snapshots",
        "corrections",
        "consumption_snapshots",
        "customer_snapshot",
        "delivery_address_snapshot",
    }.intersection(value)
    with world.sessions() as session:
        read = (
            session.execute(
                sa.select(models.audit_events).where(
                    models.audit_events.c.action == "order.detail_read",
                    models.audit_events.c.entity_id == world.order_id,
                )
            )
            .mappings()
            .one()
        )
        assert read["actor_user_id"] == world.actor_id
        assert read["payload"]["source_id"] == value["read_context"]["source_id"]
        assert read["payload"]["order_version"] == 1
        assert not any("cents" in key for key in read["payload"])
    stale = world.read(2)
    assert stale.status_code == 409, stale.text
    assert stale.json()["detail"]["code"] == "order_version_conflict"
    value["lines"][0]["recipe_cost_cents"] = 1000
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(value, schema)


@pytest.mark.parametrize("change", ["permission", "order_closed", "shift_closed", "actor_inactive"])
def test_attendance_is_revalidated_on_every_read(
    attended_world: AttendedWorld, change: str
) -> None:
    world = attended_world
    assert world.read().status_code == 200
    with world.sessions() as session:
        if change == "permission":
            permission = session.scalar(
                sa.select(models.permissions.c.id).where(
                    models.permissions.c.code == "orders.create",
                )
            )
            session.execute(
                models.role_permissions.delete().where(
                    models.role_permissions.c.role_id == world.role_id,
                    models.role_permissions.c.permission_id == permission,
                )
            )
        elif change == "order_closed":
            session.execute(
                models.orders.update()
                .where(models.orders.c.id == world.order_id)
                .values(status="CLOSED")
            )
        elif change == "shift_closed":
            session.execute(
                models.cash_shifts.update()
                .where(models.cash_shifts.c.id == world.shift_id)
                .values(status="CLOSED", closed_at=NOW)
            )
        else:
            session.execute(
                models.users.update()
                .where(models.users.c.id == world.actor_id)
                .values(status="inactive")
            )
        session.commit()
    response = world.read()
    assert response.status_code == 403, response.text
    assert "9500" not in response.text


def test_known_id_and_query_reason_do_not_create_attention(cash_world: CashWorld) -> None:
    for order_id in (ident("order:1"), ident("order:2"), ident("order-b")):
        response = cash_world.client.get(
            f"/api/v2/orders/{order_id}",
            params={"expected_version": 999, "reason": "seguimiento", "context": "attendance"},
            headers=cash_world.headers("cashier"),
        )
        assert response.status_code == 403, response.text
    owner = cash_world.client.get(
        f"/api/v2/orders/{ident('order:1')}",
        params={"expected_version": 1},
        headers=cash_world.headers("owner"),
    )
    assert owner.status_code == 200, owner.text
    assert owner.json()["total_cents"] == 5000
    assert owner.json()["read_context"]["source_kind"] == "financial"


def test_only_approved_reopen_for_participant_and_current_version_opens_detail(
    cash_world: CashWorld,
) -> None:
    order_id = ident("order:1")
    with cash_world.sessions() as session:
        grant_permission(session, cash_world.roles["cashier"], "orders.reopen.request")
        grant_permission(session, cash_world.roles["leader"], "orders.reopen.authorize")
        session.commit()
        request = ops.create_order_reopen_request(
            session,
            order_id,
            {"reason": "Synthetic order correction", "evidence_refs": ["fixture:ticket"]},
            "f106-approved-read-request",
            cash_world.actors["cashier"],
        )
    route = f"/api/v2/orders/{order_id}"
    denied = cash_world.client.get(
        route, params={"expected_version": 1}, headers=cash_world.headers("cashier")
    )
    assert denied.status_code == 403, denied.text
    with cash_world.sessions() as session:
        ops.decide_order_reopen_request(
            session,
            request["id"],
            "APPROVED",
            {"decision_reason": "Synthetic approval for review"},
            "f106-approved-read-approve",
            cash_world.actors["leader"],
        )
    for actor in ("cashier", "leader"):
        allowed = cash_world.client.get(
            route, params={"expected_version": 1}, headers=cash_world.headers(actor)
        )
        assert allowed.status_code == 200, allowed.text
        assert allowed.json()["read_context"]["source_kind"] == "approved_reopen"
        assert allowed.json()["read_context"]["source_id"] == request["id"]
        assert allowed.json()["total_cents"] == 5000
    unrelated = cash_world.client.get(
        route, params={"expected_version": 1}, headers=cash_world.headers("administrator")
    )
    assert unrelated.status_code == 403, unrelated.text
    with cash_world.sessions() as session:
        session.execute(
            models.orders.update().where(models.orders.c.id == order_id).values(version=2)
        )
        session.commit()
    changed = cash_world.client.get(
        route, params={"expected_version": 2}, headers=cash_world.headers("cashier")
    )
    assert changed.status_code == 403, changed.text


def test_attended_detail_never_queries_history_and_failed_audit_returns_no_money(
    attended_world: AttendedWorld,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from sqlalchemy.exc import SQLAlchemyError

    world = attended_world
    with world.sessions() as session:
        engine = session.get_bind()
    history_queries: list[str] = []

    def observe(conn: Any, cursor: Any, statement: str, *args: Any) -> None:
        if statement.lstrip().upper().startswith("SELECT") and any(
            name in statement
            for name in (
                "sales_operation_snapshots",
                "order_corrections",
                "order_events",
                "audit_events.payload",
            )
        ):
            history_queries.append(statement)

    sa.event.listen(engine, "before_cursor_execute", observe)
    try:
        response = world.read()
        assert response.status_code == 200, response.text
    finally:
        sa.event.remove(engine, "before_cursor_execute", observe)
    assert history_queries == []

    def broken_audit(*args: Any, **kwargs: Any) -> None:
        raise SQLAlchemyError("Synthetic audit failure")

    monkeypatch.setattr(ops, "_audit", broken_audit)
    failed = world.read()
    assert failed.status_code == 503, failed.text
    assert "9500" not in failed.text and "Synthetic audit failure" not in failed.text


@pytest.mark.parametrize("action", ["amendment", "delivery"])
def test_executed_scoped_action_gives_context_only_to_its_actor(
    attended_world: AttendedWorld,
    action: str,
) -> None:
    world = attended_world
    with world.sessions() as session:
        actor_id, role_id = _actor(session, "order-action-participant")
        for permission in ("orders.read", "orders.amend", "orders.create"):
            grant_permission(session, role_id, permission)
        session.commit()
    headers = {"X-Actor-User-Id": actor_id}
    route = f"/api/v2/orders/{world.order_id}"
    before = world.client.get(route, params={"expected_version": 1}, headers=headers)
    assert before.status_code == 403, before.text
    with world.sessions() as session:
        if action == "amendment":
            from corte_ciego_approval_fixtures import approved

            lines = [{"product_id": "018f6f73-2d0a-74f0-8f1c-000000000111", "quantity": 2}]
            auth_id = approved(
                world.sessions,
                world.order_id,
                "amend",
                1,
                "scoped-action-amendment",
                {
                    "lines": lines,
                    "delivery_selection": None,
                    "delivery_quote_reference": None,
                },
                actor_user_id=actor_id,
            )
            ops.amend_order(
                session,
                world.order_id,
                [{"product_id": "018f6f73-2d0a-74f0-8f1c-000000000111", "quantity": 2}],
                1,
                "scoped-action-amendment",
                actor_id,
                exception_authorization_id=auth_id,
                exception_reason="scoped-action-amendment",
            )
        else:
            # Reuse the real order/lines as delivery fixture inputs, then execute
            # the actual immutable driver-assignment command as the second actor.
            session.execute(
                models.orders.update()
                .where(models.orders.c.id == world.order_id)
                .values(order_type="delivery", payment_method_intent="cash")
            )
            session.execute(
                models.drivers.insert().values(
                    id=ident("attention-driver"),
                    organization_id=ops.ORGANIZATION_ID,
                    branch_id=BRANCH_ID,
                    name="Synthetic driver",
                    license_number="fixture",
                    motorcycle_plate="fixture",
                    phone="5551234567",
                    address="Fixture",
                    emergency_contact_name="Fixture",
                    created_at=NOW,
                    updated_at=NOW,
                )
            )
            session.commit()
            ops.assign_delivery_driver(session, world.order_id, ident("attention-driver"), actor_id)
    version = 2 if action == "amendment" else 1
    allowed = world.client.get(route, params={"expected_version": version}, headers=headers)
    assert allowed.status_code == 200, allowed.text
    assert allowed.json()["read_context"]["source_kind"] == (
        "order_amendment" if action == "amendment" else "delivery_assignment"
    )
    assert allowed.json()["total_cents"] == (19000 if action == "amendment" else 9500)


def test_quote_of_attended_order_preserves_amount_and_persists_read_audit(
    attended_world: AttendedWorld,
) -> None:
    world = attended_world
    with world.sessions() as session:
        grant_permission(session, world.role_id, "orders.amend")
        session.commit()
    response = world.client.post(
        "/api/v1/orders/quote",
        headers={"X-Actor-User-Id": world.actor_id},
        json={
            "branch_id": BRANCH_ID,
            "order_id": world.order_id,
            "lines": [{"product_id": "018f6f73-2d0a-74f0-8f1c-000000000111", "quantity": 1}],
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["total_cents"] == 9500
    with world.sessions() as session:
        assert (
            session.scalar(
                sa.select(sa.func.count())
                .select_from(models.audit_events)
                .where(
                    models.audit_events.c.action == "order.detail_read",
                    models.audit_events.c.entity_id == world.order_id,
                )
            )
            == 1
        )


def test_pending_web_intent_keeps_financial_gate_when_resolving_legacy_id(
    cash_world: CashWorld,
) -> None:
    from test_corte_ciego_f106_operational import seed_pending_web

    with cash_world.sessions() as session:
        intent = seed_pending_web(session)
        session.commit()
    for prefix in ("/api/v1/orders/", "/api/v2/orders/"):
        for actor, expected in (("cashier", 403), ("owner", 200)):
            response = cash_world.client.get(
                prefix + intent, params={"expected_version": 1}, headers=cash_world.headers(actor)
            )
            assert response.status_code == expected, response.text


def test_invalid_captured_modifier_fails_without_echoing_private_payload(
    attended_world: AttendedWorld,
) -> None:
    world = attended_world
    with world.sessions() as session:
        session.execute(
            models.order_lines.update()
            .where(models.order_lines.c.order_id == world.order_id)
            .values(selected_modifiers=[{"option_name": "PRIVATE-MARKER", "cost_cents": 999999}])
        )
        session.commit()
    response = world.read()
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["code"] == "order_projection_unavailable"
    assert "PRIVATE-MARKER" not in response.text and "999999" not in response.text


@pytest.mark.parametrize("actor", ["cashier", "leader", "administrator", "revoked"])
def test_direct_order_detail_does_not_bypass_financial_authority(
    cash_world: CashWorld,
    actor: str,
) -> None:
    money_queries: list[str] = []

    def observe(conn: Any, cursor: Any, statement: str, *args: Any) -> None:
        if statement.lstrip().upper().startswith("SELECT") and "_cents" in statement:
            money_queries.append(statement)

    sa.event.listen(cash_world.engine, "before_cursor_execute", observe)
    try:
        with cash_world.sessions() as session:
            with pytest.raises(ops.AuthorizationError):
                ops.get_order_detail(session, ident("order:1"), cash_world.actors[actor])
    finally:
        sa.event.remove(cash_world.engine, "before_cursor_execute", observe)
    assert money_queries == []
