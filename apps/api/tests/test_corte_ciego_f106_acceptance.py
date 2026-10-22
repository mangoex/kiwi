"""Acceptance and delivery assignment return own receipts, not historical money."""

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

import pytest
import sqlalchemy as sa
from corte_ciego_fixtures import ident
from restaurant_os import models
from restaurant_os import operations as ops
from restaurant_os.auth import create_session_token
from restaurant_os.config import get_settings
from sqlalchemy.orm import Session
from test_corte_ciego_f105_intents import activate
from test_corte_ciego_f106_amendments import AmendmentWorld
from test_platform_api import (
    ADMIN_ROLE_ID,
    ADMIN_USER_ID,
    BRANCH_ID,
    _admin_headers,
    _client_with_seeded_database,
    _test_session_factory,
)
from test_public_order_intents import (
    _create_active_driver,
    _enable_public_order_capture,
    _intent_id,
    _payload,
    _post_intent,
)

KEY = "f106-public-acceptance"


@dataclass
class AcceptanceWorld:
    client: Any
    factory: Any
    intent: str
    driver: str

    def accept(self, *, alias: bool = False, driver: bool = False) -> Any:
        body = {"driver_id": self.driver} if driver else {}
        if not alias:
            body["expected_version"] = 1
        return self.client.post(
            f"/api/v1/{'orders' if alias else 'order-intents'}/{self.intent}/accept",
            headers={**_admin_headers(), "Idempotency-Key": KEY},
            json=body,
        )

    def assign(self, order: str) -> Any:
        return self.client.put(
            f"/api/v1/orders/{order}/delivery-assignment",
            headers=_admin_headers(),
            json={"driver_id": self.driver},
        )

    def revoke(self, code: str) -> None:
        AmendmentWorld(self.client, self.factory, "", {}).revoke(code)


def setup_acceptance(client: Any) -> AcceptanceWorld:
    _enable_public_order_capture(client)
    driver = _create_active_driver(client, employee_code="ACP106", name="Synthetic driver")
    created = _post_intent(
        client,
        _payload(
            order_type="delivery",
            delivery_address={"address_text": "Synthetic private address"},
        ),
    )
    assert created.status_code == 201, created.text
    return AcceptanceWorld(
        client,
        _test_session_factory(client),
        _intent_id(client, created.json()["public_reference"]),
        driver["id"],
    )


@pytest.fixture
def acceptance_world() -> Iterator[AcceptanceWorld]:
    client = _client_with_seeded_database()
    try:
        yield setup_acceptance(client)
    finally:
        client.close()


@pytest.mark.parametrize("alias", [False, True])
def test_public_acceptance_and_replay_hide_historical_money(
    acceptance_world: AcceptanceWorld,
    alias: bool,
) -> None:
    world = acceptance_world
    activate(world.factory)
    result = world.accept(alias=alias, driver=True)
    assert result.status_code == (200 if alias else 201), result.text
    assert "total_cents" not in result.json() and "private address" not in result.text, result.text
    assert result.json()["projection"] == "operational"
    assert result.headers["cache-control"] == "no-store"
    world.revoke("orders.create")
    replay = world.accept(alias=alias, driver=True)
    assert replay.status_code == 200 and replay.json() == result.json(), replay.text
    with world.factory() as session:
        assert session.scalar(sa.select(sa.func.count()).select_from(models.orders)) == 1
        assert (
            session.scalar(
                sa.select(models.public_order_intent_commands.c.result).where(
                    models.public_order_intent_commands.c.command_type == "accept",
                )
            )["total_cents"]
            == 9500
        )


def test_assignment_does_not_return_immutable_amount_or_address(
    acceptance_world: AcceptanceWorld,
) -> None:
    world = acceptance_world
    accepted = world.accept()
    assert accepted.status_code == 201
    order = accepted.json()["id"]
    activate(world.factory)
    result = world.assign(order)
    assert result.status_code == 200, result.text
    assert "order_total_cents" not in result.json() and "private address" not in result.text, (
        result.text
    )
    assert result.json()["action"] == "delivery.assign"
    world.revoke("orders.create")
    assert world.assign(order).json() == result.json()


def create_pending(world: AcceptanceWorld) -> str:
    for path, body in (
        (
            "stores",
            {"branch_id": BRANCH_ID, "external_store_id": "f106-pending", "is_active": True},
        ),
        ("config", {"is_enabled": True, "auto_accept": False}),
    ):
        response = world.client.post(
            f"/api/v1/integrations/whatsapp/{path}",
            headers=_admin_headers(),
            json=body,
        )
        assert response.status_code == 200, response.text
    secret = response.json()["webhook_secret"]
    result = world.client.post(
        "/api/v1/integrations/whatsapp/webhook",
        headers={"Authorization": f"Bearer {secret}"},
        json={
            "event_type": "NEW_ORDER",
            "order_id": "f106-pending",
            "display_id": "P106",
            "store_id": "f106-pending",
            "customer": {"name": "Synthetic customer", "phone": "3312345678"},
            "delivery_address": "Synthetic private address",
            "items": [
                {
                    "item_id": "item1",
                    "name": "Synthetic product",
                    "quantity": 1,
                    "unit_price_cents": 9500,
                }
            ],
            "total_cents": 9500,
            "currency": "MXN",
        },
    )
    assert result.status_code == 200, result.text
    return str(result.json()["result"]["order_id"])


def test_pending_acceptance_and_replay_are_operational(acceptance_world: AcceptanceWorld) -> None:
    world = acceptance_world
    order = create_pending(world)
    activate(world.factory)
    path = f"/api/v1/orders/{order}/accept"
    result = world.client.post(path, headers=_admin_headers())
    assert result.status_code == 200 and "total_cents" not in result.json(), result.text
    assert result.json()["source_kind"] == "pending_order"
    world.revoke("orders.create")
    assert world.client.post(path, headers=_admin_headers()).json() == result.json()
    with world.factory() as session:
        assert (
            session.scalar(
                sa.select(sa.func.count())
                .select_from(models.audit_events)
                .where(
                    models.audit_events.c.action == "order.accepted",
                    models.audit_events.c.entity_id == order,
                )
            )
            == 1
        )


@pytest.mark.parametrize("action", ["public", "pending", "assignment"])
def test_missing_read_prevents_effect(acceptance_world: AcceptanceWorld, action: str) -> None:
    world = acceptance_world
    order = create_pending(world) if action == "pending" else ""
    if action == "assignment":
        order = world.accept().json()["id"]
    activate(world.factory)
    world.revoke("orders.read")
    if action == "public":
        response = world.accept()
    elif action == "pending":
        response = world.client.post(f"/api/v1/orders/{order}/accept", headers=_admin_headers())
    else:
        response = world.assign(order)
    assert response.status_code == 403, response.text
    with world.factory() as session:
        assert (
            session.scalar(sa.select(sa.func.count()).select_from(models.delivery_assignments)) == 0
        )
        if action == "public":
            assert session.scalar(sa.select(sa.func.count()).select_from(models.orders)) == 0
        elif action == "pending":
            assert (
                session.scalar(sa.select(models.orders.c.status).where(models.orders.c.id == order))
                == "PENDING"
            )


@pytest.mark.parametrize("action", ["public", "pending", "assignment"])
def test_receipt_audit_failure_is_atomic(
    acceptance_world: AcceptanceWorld,
    action: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    world = acceptance_world
    order = create_pending(world) if action == "pending" else ""
    if action == "assignment":
        order = world.accept().json()["id"]
    activate(world.factory)
    audit = ops._audit
    with world.factory() as session:
        before = list(session.execute(sa.select(models.inventory_movements)).mappings())

    def fail(session: Session, action: str, *args: Any, **kwargs: Any) -> Any:
        if action == "order.acceptance.receipt_read":
            raise sa.exc.SQLAlchemyError("PRIVATE-ACCEPTANCE-SQL")
        return audit(session, action, *args, **kwargs)

    monkeypatch.setattr(ops, "_audit", fail)
    response = (
        world.accept()
        if action == "public"
        else (
            world.assign(order)
            if action == "assignment"
            else world.client.post(f"/api/v1/orders/{order}/accept", headers=_admin_headers())
        )
    )
    assert response.status_code == 503 and "PRIVATE-ACCEPTANCE" not in response.text, response.text
    with world.factory() as session:
        assert list(session.execute(sa.select(models.inventory_movements)).mappings()) == before
        assert (
            session.scalar(sa.select(sa.func.count()).select_from(models.delivery_assignments)) == 0
        )
        if action == "public":
            assert session.scalar(sa.select(sa.func.count()).select_from(models.orders)) == 0
        elif action == "pending":
            assert (
                session.scalar(sa.select(models.orders.c.status).where(models.orders.c.id == order))
                == "PENDING"
            )


@pytest.mark.parametrize("typ", ["agent", "device"])
def test_all_three_boundaries_require_human_identity(
    acceptance_world: AcceptanceWorld, typ: str
) -> None:
    world = acceptance_world
    token = create_session_token({"sub": ADMIN_USER_ID, "typ": typ}, get_settings().secret_key)
    headers = {"Authorization": f"Bearer {token}", "Idempotency-Key": KEY}
    for path, body in (
        (f"/order-intents/{world.intent}/accept", {"expected_version": 1}),
        (f"/orders/{world.intent}/accept", {}),
    ):
        assert world.client.post("/api/v1" + path, headers=headers, json=body).status_code == 403
    assert (
        world.client.put(
            f"/api/v1/orders/{world.intent}/delivery-assignment",
            headers=headers,
            json={"driver_id": world.driver},
        ).status_code
        == 403
    )


def test_replay_selects_only_command_metadata(acceptance_world: AcceptanceWorld) -> None:
    world = acceptance_world
    assert world.accept(driver=True).status_code == 201
    activate(world.factory)
    projections: list[str] = []

    def observe(
        _conn: Any, _cursor: Any, _sql: str, _params: Any, context: Any, *_args: Any
    ) -> None:
        statement = context.compiled.statement if context.compiled else None
        if isinstance(statement, sa.sql.Select):
            projections.extend(str(column) for column in statement.selected_columns)

    engine = world.factory.kw["bind"]
    sa.event.listen(engine, "before_cursor_execute", observe)
    try:
        result = world.accept(driver=True)
    finally:
        sa.event.remove(engine, "before_cursor_execute", observe)
    assert result.status_code == 200 and "total_cents" not in result.json()
    assert "public_order_intent_commands.result" not in projections
    assert not any("_cents" in column or "snapshot" in column for column in projections)


@pytest.mark.parametrize("action", ["public", "assignment"])
def test_other_actor_cannot_recover_original_receipt(
    acceptance_world: AcceptanceWorld, action: str
) -> None:
    world = acceptance_world
    order = world.accept().json()["id"]
    if action == "assignment":
        assert world.assign(order).status_code == 200
    created = world.client.post(
        "/api/v1/users",
        headers=_admin_headers(),
        json={
            "email": "acceptance-other@fixture.invalid",
            "display_name": "Other operator",
            "employee_code": "ACP107",
            "password": ident("synthetic-f106-user").upper() + "Aa1!",
            "role_id": ADMIN_ROLE_ID,
        },
    )
    assert created.status_code == 200, created.text
    activate(world.factory)
    headers = {"X-Actor-User-Id": created.json()["id"], "Idempotency-Key": KEY}
    result = (
        world.client.post(
            f"/api/v1/order-intents/{world.intent}/accept",
            headers=headers,
            json={"expected_version": 1},
        )
        if action == "public"
        else world.client.put(
            f"/api/v1/orders/{order}/delivery-assignment",
            headers=headers,
            json={"driver_id": world.driver},
        )
    )
    assert result.status_code == 403, result.text


@pytest.mark.parametrize("action", ["public", "assignment"])
def test_read_only_replay_does_not_require_writer_fence(
    acceptance_world: AcceptanceWorld,
    action: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    world = acceptance_world
    order = world.accept().json()["id"]
    if action == "assignment":
        assert world.assign(order).status_code == 200
    activate(world.factory)

    def writer_unavailable(*args: Any, **kwargs: Any) -> None:
        raise ops.BusinessError("offline_gateway_branch_fenced", "Central writes are fenced")

    monkeypatch.setattr(ops, "_require_order_write_fence", writer_unavailable)
    result = world.accept() if action == "public" else world.assign(order)
    assert result.status_code == 200 and result.json()["projection"] == "operational", result.text


@pytest.mark.parametrize("action", ["public", "pending", "assignment"])
def test_revocation_after_commit_prevents_receipt_delivery(
    acceptance_world: AcceptanceWorld,
    action: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    world = acceptance_world
    order = create_pending(world) if action == "pending" else ""
    if action == "assignment":
        order = world.accept().json()["id"]
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
    result = (
        world.accept()
        if action == "public"
        else (
            world.assign(order)
            if action == "assignment"
            else world.client.post(f"/api/v1/orders/{order}/accept", headers=_admin_headers())
        )
    )
    assert revoked and result.status_code == 403, result.text
    with world.factory() as session:
        assert session.scalar(sa.select(models.orders.c.status)) == "ACCEPTED"
        if action == "assignment":
            assert (
                session.scalar(sa.select(sa.func.count()).select_from(models.delivery_assignments))
                == 1
            )


def test_public_replay_rejects_changed_driver(acceptance_world: AcceptanceWorld) -> None:
    world = acceptance_world
    activate(world.factory)
    assert world.accept().status_code == 201
    result = world.accept(driver=True)
    assert result.status_code == 409 and result.json()["detail"]["code"] == "idempotency_conflict"
    with world.factory() as session:
        assert (
            session.scalar(sa.select(sa.func.count()).select_from(models.delivery_assignments)) == 0
        )


def test_pending_receipt_requires_actual_pending_acceptance_fact(
    acceptance_world: AcceptanceWorld,
) -> None:
    world = acceptance_world
    order = world.accept().json()["id"]
    activate(world.factory)
    # Public acceptance has its own command proof, not a fabricated pending transition.
    result = world.client.post(f"/api/v1/orders/{order}/accept", headers=_admin_headers())
    assert result.status_code == 403, result.text
    assert world.accept().status_code == 200


def test_acceptance_schema_matches_published_contract() -> None:
    import json
    from pathlib import Path

    from restaurant_os.order_acceptance_views import OrderAcceptanceReceiptV2

    schema = json.loads(
        (
            Path(__file__).resolve().parents[3]
            / "packages/contracts/schemas/order-acceptance-receipt-v2.schema.json"
        ).read_text()
    )
    assert schema == OrderAcceptanceReceiptV2.model_json_schema()
    assert schema["additionalProperties"] is False
