"""Amendment acknowledgements cannot reopen a historical delivery money response."""

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
from test_delivery_fee_commands import PRODUCT, quote, setup_delivery
from test_platform_api import (
    ADMIN_ROLE_ID,
    ADMIN_USER_ID,
    _admin_headers,
    _test_session_factory,
)

KEY = "f106-amendment-command"


@dataclass
class AmendmentWorld:
    client: Any
    factory: Any
    order: str
    body: dict[str, Any]

    def post(self, *, recover: bool = False, key: str = KEY) -> Any:
        return self.client.post(
            f"/api/v1/orders/{self.order}/amendments" + ("/recover" if recover else ""),
            headers={**_admin_headers(), "Idempotency-Key": key},
            **({} if recover else {"json": self.body}),
        )

    def revoke(self, code: str) -> None:
        with self.factory() as session:
            permission = session.scalar(
                sa.select(models.permissions.c.id).where(models.permissions.c.code == code)
            )
            session.execute(
                models.role_permissions.delete().where(
                    models.role_permissions.c.role_id == ADMIN_ROLE_ID,
                    models.role_permissions.c.permission_id == permission,
                )
            )
            session.execute(
                models.role_authority_grants.delete().where(
                    models.role_authority_grants.c.role_id == ADMIN_ROLE_ID
                )
            )
            session.commit()


@pytest.fixture
def amendment_world() -> Iterator[AmendmentWorld]:
    client, body, _ = setup_delivery()
    body["delivery_quote_reference"] = quote(client, body)["delivery_quote_reference"]
    created = client.post("/api/v1/orders", headers=_admin_headers(), json=body)
    assert created.status_code == 200, created.text
    order = created.json()["id"]
    body.update(order_id=order, expected_version=1, delivery_selection={"mode": "REMOVED"})
    body.pop("delivery_quote_reference")
    body["delivery_quote_reference"] = quote(client, body)["delivery_quote_reference"]
    try:
        yield AmendmentWorld(client, _test_session_factory(client), order, body)
    finally:
        client.close()


def test_fee_only_receipt_preserves_amount_and_production(amendment_world: AmendmentWorld) -> None:
    world = amendment_world
    with world.factory() as session:
        inventory = list(session.execute(sa.select(models.inventory_movements)).mappings())
        tasks = list(session.execute(sa.select(models.production_tasks)).mappings())
    activate(world.factory)
    result = world.post()
    assert result.status_code == 200, result.text
    value = result.json()
    assert "total_cents" not in value and "delivery_charge" not in value
    assert value["projection"] == "operational" and value["action"] == "order.amend"
    assert value["version"] == 2 and value["id"] == world.order
    assert result.headers["cache-control"] == "no-store"
    assert world.post().json() == value
    with world.factory() as session:
        assert (
            session.scalar(
                sa.select(models.orders.c.total_cents).where(models.orders.c.id == world.order)
            )
            == 9500
        )
        assert list(session.execute(sa.select(models.inventory_movements)).mappings()) == inventory
        assert list(session.execute(sa.select(models.production_tasks)).mappings()) == tasks
        assert session.scalar(sa.select(sa.func.count()).select_from(models.order_amendments)) == 1
    detail = world.client.get(
        f"/api/v2/orders/{world.order}", headers=_admin_headers(), params={"expected_version": 2}
    )
    assert detail.status_code == 200 and detail.json()["total_cents"] == 9500, detail.text


def test_old_delivery_replay_never_loads_money_and_recovers_without_write(
    amendment_world: AmendmentWorld,
) -> None:
    world = amendment_world
    assert world.post().status_code == 200
    with world.factory() as session:
        original = session.scalar(sa.select(models.order_amendments.c.after_snapshot))
    activate(world.factory)
    assert "total_cents" not in world.post().json()
    world.revoke("orders.amend")
    statements: list[str] = []
    projected: list[str] = []

    def observe(
        _conn: Any, _cursor: Any, sql: str, _params: Any, context: Any, *_args: Any
    ) -> None:
        if sql.lstrip().upper().startswith("SELECT"):
            statements.append(sql)
            statement = context.compiled.statement if context.compiled is not None else None
            if isinstance(statement, sa.sql.Select):
                projected.extend(
                    column.name
                    for column in statement.selected_columns
                    if column is models.order_amendments.c.after_snapshot
                    or column is models.order_amendments.c.before_snapshot
                )

    engine = world.factory.kw["bind"]
    sa.event.listen(engine, "before_cursor_execute", observe)
    try:
        response = world.post()
    finally:
        sa.event.remove(engine, "before_cursor_execute", observe)
    assert response.status_code == 200, response.text
    assert not projected
    assert not any("total_cents" in sql or "delivery_response" in sql for sql in statements)
    assert world.post(recover=True).json() == response.json()
    assert world.post(key="f106-new-amendment").status_code == 403
    world.revoke("orders.read")
    assert world.post(recover=True).status_code == 403
    with world.factory() as session:
        assert session.scalar(sa.select(models.order_amendments.c.after_snapshot)) == original


def test_known_key_does_not_accept_changed_intention(amendment_world: AmendmentWorld) -> None:
    world = amendment_world
    activate(world.factory)
    assert world.post().status_code == 200
    world.body["delivery_selection"] = {"mode": "AUTO"}
    result = world.post()
    assert (
        result.status_code == 409 and result.json()["detail"]["code"] == "idempotency_key_conflict"
    )


@pytest.mark.parametrize("typ", ["agent", "device"])
def test_amendment_endpoints_are_human_only(amendment_world: AmendmentWorld, typ: str) -> None:
    world = amendment_world
    activate(world.factory)
    token = create_session_token({"sub": ADMIN_USER_ID, "typ": typ}, get_settings().secret_key)
    auth = {"Authorization": f"Bearer {token}", "Idempotency-Key": KEY}
    path = f"/api/v1/orders/{world.order}/amendments"
    assert world.client.post(path, headers=auth, json=world.body).status_code == 403
    assert world.client.post(path + "/recover", headers=auth).status_code == 403


def test_audit_failure_rolls_back_delivery_change(
    amendment_world: AmendmentWorld, monkeypatch: pytest.MonkeyPatch
) -> None:
    world = amendment_world
    activate(world.factory)
    audit = ops._audit

    def fail(session: Session, action: str, *args: Any, **kwargs: Any) -> Any:
        if action == "order.amendment.receipt_read":
            raise sa.exc.SQLAlchemyError("PRIVATE-AMENDMENT-SQL")
        return audit(session, action, *args, **kwargs)

    monkeypatch.setattr(ops, "_audit", fail)
    result = world.post()
    assert result.status_code == 503 and "PRIVATE-AMENDMENT" not in result.text
    with world.factory() as session:
        assert (
            session.scalar(
                sa.select(models.orders.c.total_cents).where(models.orders.c.id == world.order)
            )
            == 12300
        )
        assert (
            session.scalar(
                sa.select(models.orders.c.version).where(models.orders.c.id == world.order)
            )
            == 1
        )
        assert session.scalar(sa.select(sa.func.count()).select_from(models.order_amendments)) == 0


def test_revoked_after_commit_cannot_receive_and_recovery_keeps_one_effect(
    amendment_world: AmendmentWorld, monkeypatch: pytest.MonkeyPatch
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
                    .where(models.users.c.id == ADMIN_USER_ID)
                    .values(status="inactive")
                )
                commit(other)

    monkeypatch.setattr(Session, "commit", revoke)
    result = world.post()
    assert revoked and result.status_code == 403, result.text
    with world.factory() as session:
        assert session.scalar(sa.select(sa.func.count()).select_from(models.order_amendments)) == 1
        session.execute(
            models.users.update().where(models.users.c.id == ADMIN_USER_ID).values(status="active")
        )
        session.commit()
    assert world.post(recover=True).status_code == 200
    with world.factory() as session:
        assert session.scalar(sa.select(sa.func.count()).select_from(models.order_amendments)) == 1


def test_recovery_of_unknown_key_never_executes(amendment_world: AmendmentWorld) -> None:
    world = amendment_world
    activate(world.factory)
    assert world.post(recover=True).status_code == 404
    with world.factory() as session:
        assert session.scalar(sa.select(sa.func.count()).select_from(models.order_amendments)) == 0
        assert (
            session.scalar(
                sa.select(models.orders.c.version).where(models.orders.c.id == world.order)
            )
            == 1
        )


@pytest.mark.parametrize("historical_actor", [ADMIN_USER_ID, None, "another-actor"])
def test_hashless_history_requires_explicit_recovery_and_own_identity(
    amendment_world: AmendmentWorld, historical_actor: str | None
) -> None:
    world = amendment_world
    # Frozen old-format fixture, not an update/backfill of a persisted command.
    with world.factory() as session:
        if historical_actor == "another-actor":
            original_actor = dict(
                session.execute(sa.select(models.users).where(models.users.c.id == ADMIN_USER_ID))
                .mappings()
                .one()
            )
            session.execute(
                models.users.insert().values(
                    {
                        **original_actor,
                        "id": historical_actor,
                        "email": "historical-amendment@fixture.invalid",
                        "employee_code": None,
                    }
                )
            )
        session.execute(
            models.order_amendments.insert().values(
                id=ops._id(),
                order_id=world.order,
                sequence=1,
                expected_version=1,
                resulting_version=2,
                before_snapshot={"total_cents": 12300},
                after_snapshot={"total_cents": 9500},
                actor_user_id=historical_actor,
                idempotency_key=KEY,
                created_at=ops._now(),
            )
        )
        session.commit()
    activate(world.factory)
    result = world.post()
    if historical_actor == ADMIN_USER_ID:
        assert (
            result.status_code == 409
            and result.json()["detail"]["code"] == "order_amendment_recovery_required"
        )
        recovered = world.post(recover=True)
        assert recovered.status_code == 200 and "total_cents" not in recovered.json()
        assert recovered.json()["version"] == 2
    else:
        assert result.status_code == 403
        assert world.post(recover=True).status_code == 403
    with world.factory() as session:
        assert session.scalar(sa.select(models.order_amendments.c.after_snapshot)) == {
            "total_cents": 9500
        }


def test_receipt_schema_matches_published_contract() -> None:
    import json
    from pathlib import Path

    from restaurant_os.order_amendment_views import OrderAmendmentReceiptV2

    schema = json.loads(
        (
            Path(__file__).resolve().parents[3]
            / "packages/contracts/schemas/order-amendment-receipt-v2.schema.json"
        ).read_text()
    )
    assert schema == OrderAmendmentReceiptV2.model_json_schema()
    assert schema["additionalProperties"] is False


def test_missing_read_prevents_new_write(amendment_world: AmendmentWorld) -> None:
    world = amendment_world
    activate(world.factory)
    world.revoke("orders.read")
    assert world.post().status_code == 403
    with world.factory() as session:
        assert session.scalar(sa.select(sa.func.count()).select_from(models.order_amendments)) == 0
        assert (
            session.scalar(
                sa.select(models.orders.c.version).where(models.orders.c.id == world.order)
            )
            == 1
        )


def test_other_current_actor_cannot_recover_owning_users_command(
    amendment_world: AmendmentWorld,
) -> None:
    world = amendment_world
    created = world.client.post(
        "/api/v1/users",
        headers=_admin_headers(),
        json={
            "email": "another-amender@fixture.invalid",
            "display_name": "Other amender",
            "employee_code": "AMD002",
            "password": ident("synthetic-f106-user").upper() + "Aa1!",
            "role_id": ADMIN_ROLE_ID,
        },
    )
    assert created.status_code == 200, created.text
    other_actor = created.json()["id"]
    activate(world.factory)
    assert world.post().status_code == 200
    from restaurant_os.order_amendment_views import recover_amendment

    with world.factory() as session, pytest.raises(ops.BusinessError) as error:
        recover_amendment(session, world.order, KEY, other_actor)
    assert error.value.code == "financial_access_denied"


def test_cart_amendment_keeps_outer_transaction_and_body_identity(
    amendment_world: AmendmentWorld,
) -> None:
    world = amendment_world
    # A non-delivery order exercises the formerly missing general command hash.
    result = world.client.post(
        "/api/v1/orders",
        headers={**_admin_headers(), "Idempotency-Key": "f106-amend-cart"},
        json={"lines": [{"product_id": PRODUCT, "quantity": 1}]},
    )
    assert result.status_code == 200, result.text
    order = result.json()["id"]
    activate(world.factory)
    lines = [{"product_id": PRODUCT, "quantity": 2}]
    with world.factory() as session:
        receipt = ops.amend_order(session, order, lines, 1, KEY, ADMIN_USER_ID, commit=False)
        assert receipt["version"] == 2 and "total_cents" not in receipt
        assert (
            session.scalar(
                sa.select(models.orders.c.total_cents).where(models.orders.c.id == order)
            )
            == 19000
        )
        session.rollback()
    with world.factory() as session:
        assert (
            session.scalar(sa.select(models.orders.c.version).where(models.orders.c.id == order))
            == 1
        )
        assert session.scalar(sa.select(sa.func.count()).select_from(models.order_amendments)) == 0
        receipt = ops.amend_order(session, order, lines, 1, KEY, ADMIN_USER_ID)
        assert ops.amend_order(session, order, lines, 1, KEY, ADMIN_USER_ID) == receipt
        with pytest.raises(ops.BusinessError, match="intention changed"):
            ops.amend_order(
                session, order, [{"product_id": PRODUCT, "quantity": 3}], 1, KEY, ADMIN_USER_ID
            )
