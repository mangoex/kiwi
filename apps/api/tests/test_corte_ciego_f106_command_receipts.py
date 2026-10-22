"""TC-450/462: stored order/payment responses are not a financial read capability."""

import json
from pathlib import Path
from typing import Any

import jsonschema
import pytest
import sqlalchemy as sa
from restaurant_os import models
from restaurant_os import operations as ops
from test_corte_ciego_f106_orders import AttendedWorld, attended_world

__all__ = ["attended_world"]


def recover(world: AttendedWorld) -> Any:
    return world.client.post(
        "/api/v1/orders/recover",
        json={},
        headers={
            "X-Actor-User-Id": world.actor_id,
            "Idempotency-Key": "attended-order-001",
        },
    )


def pay(world: AttendedWorld, key: str = "receipt-payment-001") -> Any:
    return world.client.post(
        f"/api/v1/orders/{world.order_id}/payments",
        headers={
            "X-Actor-User-Id": world.actor_id,
            "Idempotency-Key": key,
        },
        json={
            "amount_cents": 9500,
            "register_id": "CAJA-01",
            "method": "cash",
            "received_cash": "100.00",
        },
    )


def remove_permission(world: AttendedWorld, code: str) -> None:
    with world.sessions() as session:
        permission = session.scalar(
            sa.select(models.permissions.c.id).where(models.permissions.c.code == code)
        )
        session.execute(
            models.role_permissions.delete().where(
                models.role_permissions.c.role_id == world.role_id,
                models.role_permissions.c.permission_id == permission,
            )
        )
        session.commit()


def test_create_recovery_is_closed_receipt_without_selecting_snapshot(
    attended_world: AttendedWorld,
) -> None:
    world = attended_world
    statements: list[str] = []
    engine = world.sessions.kw["bind"]

    def observe(_conn: Any, _cursor: Any, sql: str, *_args: Any) -> None:
        if sql.lstrip().upper().startswith("SELECT"):
            statements.append(sql)

    sa.event.listen(engine, "before_cursor_execute", observe)
    try:
        response = recover(world)
    finally:
        sa.event.remove(engine, "before_cursor_execute", observe)
    assert response.status_code == 200, response.text
    assert response.json()["projection"] == "operational"
    schema = json.loads(
        (
            Path(__file__).resolve().parents[3]
            / "packages/contracts/schemas/order-command-receipt-v2.schema.json"
        ).read_text(encoding="utf-8")
    )
    jsonschema.validate(response.json(), schema)
    assert response.json()["id"] == world.order_id
    assert "cents" not in response.text and "snapshot" not in response.text
    assert not any("order_create_commands.response_snapshot" in sql for sql in statements)
    assert response.headers["cache-control"] == "no-store"


def test_own_receipt_survives_write_revocation_but_not_read_revocation(
    attended_world: AttendedWorld,
) -> None:
    world = attended_world
    remove_permission(world, "orders.create")
    response = recover(world)
    assert response.status_code == 200, response.text
    assert "cents" not in response.text
    remove_permission(world, "orders.read")
    assert recover(world).status_code == 403


def test_payment_receipt_replay_does_not_return_money_after_shift_closes(
    attended_world: AttendedWorld,
) -> None:
    world = attended_world
    first = pay(world)
    assert first.status_code == 200, first.text
    assert first.json()["projection"] == "operational"
    assert "cents" not in first.text
    with world.sessions() as session:
        stored = session.scalar(
            sa.select(models.payment_commands.c.response_snapshot).where(
                models.payment_commands.c.order_id == world.order_id
            )
        )
        assert stored["amount_cents"] == 9500
        session.execute(
            models.cash_shifts.update()
            .where(models.cash_shifts.c.id == world.shift_id)
            .values(status="CLOSED")
        )
        session.execute(
            models.orders.update()
            .where(models.orders.c.id == world.order_id)
            .values(status="CLOSED")
        )
        session.commit()
    remove_permission(world, "payments.confirm")
    replay = pay(world)
    assert replay.status_code == 200, replay.text
    assert replay.json() == first.json()
    assert pay(world, "receipt-new-payment-002").status_code == 403
    with world.sessions() as session:
        assert (
            session.scalar(
                sa.select(sa.func.count())
                .select_from(models.payments)
                .where(models.payments.c.order_id == world.order_id)
            )
            == 1
        )
    remove_permission(world, "orders.read")
    assert pay(world).status_code == 403


def test_payment_preview_requires_current_order_context(attended_world: AttendedWorld) -> None:
    world = attended_world
    remove_permission(world, "orders.create")
    with world.sessions() as session, pytest.raises(ops.AuthorizationError):
        ops.preview_order_payment(
            session, world.order_id, "cash", world.actor_id, received_cash="100.00"
        )


def test_authorized_preview_keeps_exact_price_and_change(attended_world: AttendedWorld) -> None:
    with attended_world.sessions() as session:
        value = ops.preview_order_payment(
            session,
            attended_world.order_id,
            "cash",
            attended_world.actor_id,
            received_cash="100.00",
        )
    assert value["total_cents"] == 9500
    assert value["cash_tender"]["change_cents"] == 500


def test_payment_replay_never_selects_monetary_snapshot(attended_world: AttendedWorld) -> None:
    world = attended_world
    first = pay(world)
    assert first.status_code == 200
    statements: list[str] = []
    engine = world.sessions.kw["bind"]

    def observe(_conn: Any, _cursor: Any, sql: str, *_args: Any) -> None:
        if sql.lstrip().upper().startswith("SELECT"):
            statements.append(sql)

    sa.event.listen(engine, "before_cursor_execute", observe)
    try:
        replay = pay(world)
    finally:
        sa.event.remove(engine, "before_cursor_execute", observe)
    assert replay.status_code == 200 and replay.json() == first.json()
    assert not any(
        "payment_commands.response_snapshot" in sql or "orders.total_cents" in sql
        for sql in statements
    )


def test_receipt_audit_failure_does_not_repeat_payment(
    attended_world: AttendedWorld,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    world = attended_world
    original = ops._audit

    def fail(*args: Any, **kwargs: Any) -> Any:
        if len(args) > 1 and args[1] == "operational_command.receipt_read":
            raise sa.exc.SQLAlchemyError("PRIVATE-RECEIPT")
        return original(*args, **kwargs)

    monkeypatch.setattr(ops, "_audit", fail)
    failed = pay(world)
    assert failed.status_code == 503 and "PRIVATE-RECEIPT" not in failed.text
    monkeypatch.setattr(ops, "_audit", original)
    receipt = pay(world)
    assert receipt.status_code == 200 and "cents" not in receipt.text
    with world.sessions() as session:
        assert (
            session.scalar(
                sa.select(sa.func.count())
                .select_from(models.payments)
                .where(models.payments.c.order_id == world.order_id)
            )
            == 1
        )


def test_missing_receipt_permission_denies_before_payment_effect(
    attended_world: AttendedWorld,
) -> None:
    world = attended_world
    remove_permission(world, "orders.read")
    assert pay(world).status_code == 403
    with world.sessions() as session:
        assert (
            session.scalar(
                sa.select(sa.func.count())
                .select_from(models.payments)
                .where(models.payments.c.order_id == world.order_id)
            )
            == 0
        )


def test_preview_http_preserves_change_and_audits_read(attended_world: AttendedWorld) -> None:
    world = attended_world
    response = world.client.post(
        f"/api/v1/orders/{world.order_id}/payment-preview",
        headers={"X-Actor-User-Id": world.actor_id},
        json={"method": "cash", "received_cash": "100.00"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["cash_tender"]["change_cents"] == 500
    assert response.headers["cache-control"] == "no-store"
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


def test_receipt_published_schema_matches_runtime() -> None:
    from restaurant_os.order_command_receipts import OrderCommandReceiptV2

    stored = json.loads(
        (
            Path(__file__).resolve().parents[3]
            / "packages/contracts/schemas/order-command-receipt-v2.schema.json"
        ).read_text(encoding="utf-8")
    )
    assert stored == {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        **OrderCommandReceiptV2.model_json_schema(),
    }
