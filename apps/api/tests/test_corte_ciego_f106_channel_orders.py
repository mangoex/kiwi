"""Provider inboxes cannot bypass the operational order projection."""

import json
import re
from pathlib import Path
from typing import Any

import pytest
import sqlalchemy as sa
from corte_ciego_fixtures import BRANCH_A, BRANCH_B, CashWorld, cash_world, ident
from restaurant_os import models
from restaurant_os import operations as ops
from restaurant_os.auth import create_session_token
from restaurant_os.channel_order_views import ChannelOrderOperationalV2
from restaurant_os.config import get_settings
from restaurant_os.integrations.service import ChannelIntegrationService
from sqlalchemy.orm import Session

__all__ = ["cash_world"]
PROVIDERS = ["UBER_EATS", "DIDI_FOOD", "RAPPI", "WHATSAPP"]
PATHS = ["uber-eats", "didi-food", "rappi", "whatsapp"]


def test_legacy_channel_status_cannot_bypass_exact_exception(cash_world: CashWorld):
    world = cash_world
    with world.sessions() as session:
        order = seed_channels(session, ident("order:1"))[0]
    with world.sessions() as session, pytest.raises(ops.BusinessError) as failure:
        ChannelIntegrationService().update_order_status(
            session, order, "CANCELLED", world.actors["cashier"]
        )
    assert failure.value.code == "channel_contract_upgrade_required"
    with world.sessions() as session:
        assert (
            session.scalar(sa.select(models.orders.c.status).where(models.orders.c.id == order))
            == "PENDING"
        )


def seed_channels(session: Session, source_order: str) -> list[str]:
    template = dict(
        session.execute(sa.select(models.orders).where(models.orders.c.id == source_order))
        .mappings()
        .one()
    )
    identifiers = []
    for provider in PROVIDERS:
        identifier = ops._id()
        identifiers.append(identifier)
        session.execute(
            models.orders.insert().values(
                {
                    **template,
                    "id": identifier,
                    "folio": provider + "-106",
                    "channel": provider,
                    "status": "PENDING",
                    "total_cents": 95123,
                    "customer_snapshot": {
                        "name": "Synthetic customer",
                        "private": "PRIVATE-CHANNEL-95123",
                    },
                    "delivery_address_snapshot": {"private": "PRIVATE-CHANNEL-95123"},
                }
            )
        )
        session.execute(
            models.channel_orders_meta.insert().values(
                id=ops._id(),
                order_id=identifier,
                provider=provider,
                external_order_id=identifier,
                display_code="PRIVATE-CHANNEL-95123",
                raw_payload={"total_cents": 95123},
                created_at=template["created_at"],
                updated_at=template["created_at"],
            )
        )
    session.commit()
    return identifiers


@pytest.mark.parametrize("path,provider", zip(PATHS, PROVIDERS, strict=True))
def test_channel_inbox_returns_closed_operational_records(
    cash_world: CashWorld, path: str, provider: str
) -> None:
    world = cash_world
    with world.sessions() as session:
        seed_channels(session, ident("order:1"))
    result = world.client.get(
        f"/api/v1/pos/{path}/orders",
        params={"branch_id": BRANCH_A},
        headers=world.headers("cashier"),
    )
    assert result.status_code == 200, result.text
    assert "total_cents" not in result.text and "PRIVATE-CHANNEL" not in result.text, result.text
    assert len(result.json()) == 1 and result.json()[0]["channel"] == provider
    assert result.json()[0]["projection"] == "operational"
    assert result.headers["cache-control"] == "no-store"


def test_service_requires_current_identity_permission_and_scope(cash_world: CashWorld) -> None:
    world = cash_world
    service = ChannelIntegrationService()
    with world.sessions() as session:
        seed_channels(session, ident("order:1"))
    for actor, branch in [
        (None, BRANCH_A),
        (world.actors["foreign"], BRANCH_A),
        (world.actors["cashier"], BRANCH_B),
    ]:
        with world.sessions() as session, pytest.raises(ops.AuthorizationError):
            service.list_pos_orders(session, branch, actor_user_id=actor)
    with world.sessions() as session:
        permission = session.scalar(
            sa.select(models.permissions.c.id).where(models.permissions.c.code == "orders.read")
        )
        session.execute(
            models.role_permissions.delete().where(
                models.role_permissions.c.role_id == world.roles["cashier"],
                models.role_permissions.c.permission_id == permission,
            )
        )
        session.commit()
    with world.sessions() as session, pytest.raises(ops.AuthorizationError):
        service.list_pos_orders(session, BRANCH_A, actor_user_id=world.actors["cashier"])


def test_owner_receives_same_closed_schema_and_no_monetary_sql(cash_world: CashWorld) -> None:
    world = cash_world
    with world.sessions() as session:
        seed_channels(session, ident("order:1"))
        original = list(session.execute(sa.select(models.channel_orders_meta)).mappings())
    queries: list[str] = []

    def observe(_conn: Any, _cursor: Any, sql: str, *_args: Any) -> None:
        if sql.lstrip().upper().startswith("SELECT"):
            queries.append(sql)

    sa.event.listen(world.engine, "before_cursor_execute", observe)
    try:
        result = world.client.get(
            "/api/v1/pos/rappi/orders",
            params={"branch_id": BRANCH_A},
            headers=world.headers("owner"),
        )
    finally:
        sa.event.remove(world.engine, "before_cursor_execute", observe)
    assert result.status_code == 200, result.text
    record = result.json()[0]
    assert set(record) == set(ChannelOrderOperationalV2.model_fields)
    assert not any(
        marker in sql
        for sql in queries
        for marker in [
            "orders.total_cents",
            "order_lines.unit_price_cents",
            "channel_orders_meta.raw_payload",
            "orders.delivery_address_snapshot",
            "channel_orders_meta.display_code",
        ]
    )
    assert not any(
        re.search(r"(?:SELECT |, )orders\.customer_snapshot(?:,| \n)", sql) for sql in queries
    )
    with world.sessions() as session:
        assert list(session.execute(sa.select(models.channel_orders_meta)).mappings()) == original
    schema = Path("packages/contracts/schemas/channel-order-operational-v2.schema.json")
    assert (
        json.loads(schema.read_text(encoding="utf-8"))
        == ChannelOrderOperationalV2.model_json_schema()
    )


def test_status_filter_and_branch_are_applied_before_limit(cash_world: CashWorld) -> None:
    world = cash_world
    with world.sessions() as session:
        identifiers = seed_channels(session, ident("order:1"))
        template = dict(
            session.execute(sa.select(models.orders).where(models.orders.c.id == identifiers[0]))
            .mappings()
            .one()
        )
        for index in range(103):
            identifier = ops._id()
            session.execute(
                models.orders.insert().values(
                    {**template, "id": identifier, "folio": f"LIMIT-{index}", "status": "ACCEPTED"}
                )
            )
            session.execute(
                models.channel_orders_meta.insert().values(
                    id=ops._id(),
                    order_id=identifier,
                    provider="UBER_EATS",
                    external_order_id=identifier,
                    display_code="Synthetic limit",
                    raw_payload={},
                    created_at=template["created_at"],
                    updated_at=template["created_at"],
                )
            )
        session.commit()
        service = ChannelIntegrationService()
        result = service.list_pos_orders(
            session, BRANCH_A, status_filter="PENDING", actor_user_id=world.actors["cashier"]
        )
        assert len(result) == 1 and result[0]["id"] == identifiers[0]
        result = service.list_pos_orders(
            session, BRANCH_A, status_filter="ACCEPTED", actor_user_id=world.actors["cashier"]
        )
        assert len(result) == 100 and all(row["status"] == "ACCEPTED" for row in result)


@pytest.mark.parametrize("typ", ["agent", "device"])
def test_technical_identity_cannot_use_human_inbox(cash_world: CashWorld, typ: str) -> None:
    world = cash_world
    token = create_session_token(
        {"sub": world.actors["owner"], "typ": typ}, get_settings().secret_key
    )
    result = world.client.get(
        "/api/v1/pos/rappi/orders",
        params={"branch_id": BRANCH_A},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert result.status_code == 403


def test_audit_failure_does_not_deliver_records(
    cash_world: CashWorld, monkeypatch: pytest.MonkeyPatch
) -> None:
    world = cash_world
    with world.sessions() as session:
        seed_channels(session, ident("order:1"))
    audit = ops._audit

    def fail(session: Session, action: str, *args: Any, **kwargs: Any) -> Any:
        if action == "channel.orders.read":
            raise sa.exc.SQLAlchemyError("PRIVATE-CHANNEL-SQL")
        return audit(session, action, *args, **kwargs)

    monkeypatch.setattr(ops, "_audit", fail)
    result = world.client.get(
        "/api/v1/pos/rappi/orders", params={"branch_id": BRANCH_A}, headers=world.headers("cashier")
    )
    assert result.status_code == 503 and "PRIVATE-CHANNEL" not in result.text
    with world.sessions() as session:
        assert (
            session.scalar(
                sa.select(sa.func.count())
                .select_from(models.audit_events)
                .where(models.audit_events.c.action == "channel.orders.read")
            )
            == 0
        )


def test_authorization_changed_after_commit_denies_response(
    cash_world: CashWorld, monkeypatch: pytest.MonkeyPatch
) -> None:
    world = cash_world
    with world.sessions() as session:
        seed_channels(session, ident("order:1"))
    commit = Session.commit
    changed = False

    def change(session: Session) -> None:
        nonlocal changed
        commit(session)
        if not changed:
            changed = True
            with world.sessions() as other:
                other.execute(
                    models.users.update()
                    .where(models.users.c.id == world.actors["cashier"])
                    .values(authorization_version=models.users.c.authorization_version + 1)
                )
                commit(other)

    monkeypatch.setattr(Session, "commit", change)
    result = world.client.get(
        "/api/v1/pos/rappi/orders", params={"branch_id": BRANCH_A}, headers=world.headers("cashier")
    )
    assert changed and result.status_code == 409 and "folio" not in result.text, result.text
