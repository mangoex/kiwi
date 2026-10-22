"""Driver collection stays atomic while human lists/receipts remain operational."""

import logging
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

import pytest
import sqlalchemy as sa
from corte_ciego_fixtures import ident
from fastapi.testclient import TestClient
from restaurant_os import models
from restaurant_os import operations as ops
from restaurant_os.auth import create_session_token
from restaurant_os.config import get_settings
from sqlalchemy.orm import Session, sessionmaker
from test_corte_ciego_f1_red import assert_blind
from test_corte_ciego_f105_intents import activate
from test_platform_api import (
    ADMIN_ROLE_ID,
    ADMIN_USER_ID,
    BRANCH_ID,
    _admin_headers,
    _client_with_seeded_database,
    _open_shift,
    _test_session_factory,
)

PATH = "/api/v1/driver-cash-settlements"
KEY = "f106-settlement-command"


@dataclass
class SettlementWorld:
    client: TestClient
    factory: sessionmaker[Session]
    body: dict[str, Any]

    def post(self, *, recover: bool = False, key: str = KEY) -> Any:
        return self.client.post(
            PATH + ("/recover" if recover else ""),
            headers={**_admin_headers(), "Idempotency-Key": key},
            json=self.body,
        )

    def remove_permission(self, code: str) -> None:
        with self.factory() as session:
            permission = session.scalar(
                sa.select(models.permissions.c.id).where(
                    models.permissions.c.code == code,
                )
            )
            session.execute(
                models.role_permissions.delete().where(
                    models.role_permissions.c.role_id == ADMIN_ROLE_ID,
                    models.role_permissions.c.permission_id == permission,
                )
            )
            session.execute(
                models.role_authority_grants.delete().where(
                    models.role_authority_grants.c.role_id == ADMIN_ROLE_ID,
                )
            )
            session.commit()


def seed_deliveries(client: TestClient) -> dict[str, Any]:
    def post(path: str, body: dict[str, Any]) -> dict[str, Any]:
        response = client.post(path, headers=_admin_headers(), json=body)
        assert response.status_code == 200, response.text
        return response.json()

    driver = post(
        "/api/v1/drivers",
        {
            "employee_code": "F106DR",
            "name": "Driver",
            "license_number": "F106-LIC",
            "motorcycle_plate": "F106",
            "branch_id": BRANCH_ID,
            "phone": "6691000091",
            "address": "Base",
            "emergency_contact_name": "Contact",
        },
    )
    customer = post(
        "/api/v1/customers",
        {
            "branch_id": BRANCH_ID,
            "name": "Delivery customer",
            "phones": [{"number": "6691000092", "is_primary": True}],
        },
    )
    address = post(
        f"/api/v1/customers/{customer['id']}/addresses",
        {
            "branch_id": BRANCH_ID,
            "alias": "Home",
            "street": "Centro",
            "exterior_number": "10",
            "neighborhood": "Centro",
            "postal_code": "82000",
            "city": "Mazatlán",
            "municipality": "Mazatlán",
            "state": "Sinaloa",
            "is_default": True,
        },
    )
    opened = _open_shift(client, 50000)
    assert opened.status_code == 200, opened.text
    order_ids = []
    for quantity in (1, 2):
        order = post(
            "/api/v1/orders",
            {
                "branch_id": BRANCH_ID,
                "order_type": "delivery",
                "payment_method_intent": "cash",
                "customer_id": customer["id"],
                "delivery_address_id": address["id"],
                "driver_id": driver["id"],
                "lines": [
                    {"product_id": "018f6f73-2d0a-74f0-8f1c-000000000111", "quantity": quantity}
                ],
            },
        )
        order_ids.append(order["id"])
    return {
        "branch_id": BRANCH_ID,
        "driver_id": driver["id"],
        "register_id": "CAJA-01",
        "order_ids": order_ids,
    }


@pytest.fixture
def settlement_world() -> Iterator[SettlementWorld]:
    client = _client_with_seeded_database()
    try:
        yield SettlementWorld(client, _test_session_factory(client), seed_deliveries(client))
    finally:
        client.close()


def test_candidates_omit_money_and_preserve_pending_inactive_driver(
    settlement_world: SettlementWorld,
) -> None:
    world = settlement_world
    activate(world.factory)
    moved = world.client.post(
        "/api/v1/branches",
        headers=_admin_headers(),
        json={"name": "Moved driver branch", "code": "F106-MOVED"},
    )
    assert moved.status_code == 200, moved.text
    with world.factory() as session:
        session.execute(
            models.drivers.update()
            .where(
                models.drivers.c.id == world.body["driver_id"],
            )
            .values(status="inactive", branch_id=moved.json()["id"])
        )
        session.commit()
    response = world.client.get(
        PATH + "/drivers", headers=_admin_headers(), params={"branch_id": BRANCH_ID}
    )
    assert response.status_code == 200, response.text
    row = next(row for row in response.json() if row["id"] == world.body["driver_id"])
    assert "eligible_total_cents" not in row
    assert response.headers["cache-control"] == "no-store"
    assert set(row) == {
        "schema_version",
        "projection",
        "policy_version",
        "id",
        "name",
        "status",
        "eligible_order_count",
    }
    assert row["eligible_order_count"] == 2 and row["status"] == "inactive"
    assert_blind(row)


def test_confirmed_receipt_preserves_history_without_money_in_metrics(
    settlement_world: SettlementWorld, caplog: pytest.LogCaptureFixture
) -> None:
    world = settlement_world
    activate(world.factory)
    caplog.set_level(logging.INFO, logger="restaurant_os.operations")
    response = world.post()
    assert response.status_code == 200, response.text
    value = response.json()
    assert "total_cents" not in value
    assert_blind(value)
    assert (
        value["projection"] == "operational" and value["action"] == "driver.cash_settlement.confirm"
    )
    assert value["order_count"] == 2 and "items" not in value
    assert response.headers["cache-control"] == "no-store"
    assert world.post().json() == value
    with world.factory() as session:
        stored = session.scalar(
            sa.select(models.driver_cash_settlement_commands.c.response_snapshot)
        )
        assert stored["total_cents"] == 28500 and len(stored["items"]) == 2
        assert session.scalar(sa.select(sa.func.count()).select_from(models.payments)) == 2
    metrics = [
        r for r in caplog.records if getattr(r, "metric", None) == "driver_cash_settlement_total"
    ]
    assert metrics and all(not hasattr(r, "total_cents") for r in metrics)


def test_old_receipt_recovery_requires_read_not_write_and_no_money_queries(
    settlement_world: SettlementWorld,
) -> None:
    world = settlement_world
    before = world.post()
    assert before.status_code == 200, before.text
    with world.factory() as session:
        original_snapshot = session.scalar(
            sa.select(models.driver_cash_settlement_commands.c.response_snapshot)
        )
    activate(world.factory)
    replay = world.post()
    assert replay.status_code == 200, replay.text
    assert "total_cents" not in replay.json()
    world.remove_permission("payments.confirm")
    statements: list[str] = []
    engine = world.factory.kw["bind"]

    def observe(_conn: Any, _cursor: Any, sql: str, *_args: Any) -> None:
        if sql.lstrip().upper().startswith("SELECT"):
            statements.append(sql)

    sa.event.listen(engine, "before_cursor_execute", observe)
    try:
        result = world.post(recover=True)
    finally:
        sa.event.remove(engine, "before_cursor_execute", observe)
    assert result.status_code == 200, result.text
    assert_blind(result.json())
    assert result.json()["id"] == before.json()["id"]
    assert not any(
        "response_snapshot" in sql or "total_cents" in sql or "amount_cents" in sql
        for sql in statements
    )
    assert world.post(recover=True, key="f106-unknown-settlement").status_code == 409
    assert world.post(key="f106-new-settlement-key").status_code == 403
    world.remove_permission("orders.read")
    assert world.post(recover=True).status_code == 403
    with world.factory() as session:
        assert (
            session.scalar(sa.select(models.driver_cash_settlement_commands.c.response_snapshot))
            == original_snapshot
        )


def test_missing_read_denies_before_payment(settlement_world: SettlementWorld) -> None:
    world = settlement_world
    activate(world.factory)
    world.remove_permission("orders.read")
    assert world.post().status_code == 403
    with world.factory() as session:
        assert session.scalar(sa.select(sa.func.count()).select_from(models.payments)) == 0


@pytest.mark.parametrize("kind", ["agent", "device"])
def test_technical_credentials_cannot_collect_or_read_candidates(
    settlement_world: SettlementWorld, kind: str
) -> None:
    world = settlement_world
    activate(world.factory)
    token = create_session_token({"sub": ADMIN_USER_ID, "typ": kind}, get_settings().secret_key)
    headers = {"Authorization": f"Bearer {token}", "Idempotency-Key": KEY}
    assert (
        world.client.get(
            PATH + "/drivers", headers=headers, params={"branch_id": BRANCH_ID}
        ).status_code
        == 403
    )
    assert world.client.post(PATH, headers=headers, json=world.body).status_code == 403
    assert world.client.post(PATH + "/recover", headers=headers, json=world.body).status_code == 403


def test_receipt_audit_failure_rolls_back_entire_batch(
    settlement_world: SettlementWorld, monkeypatch: pytest.MonkeyPatch
) -> None:
    world = settlement_world
    activate(world.factory)
    audit = ops._audit

    def fail(session: Session, action: str, *args: Any, **kwargs: Any) -> Any:
        if action == "driver.cash_settlement.receipt_read":
            raise sa.exc.SQLAlchemyError("PRIVATE-SETTLEMENT-SQL")
        return audit(session, action, *args, **kwargs)

    monkeypatch.setattr(ops, "_audit", fail)
    response = world.post()
    assert response.status_code == 503 and "PRIVATE-SETTLEMENT" not in response.text
    with world.factory() as session:
        for table in (
            models.payments,
            models.payment_commands,
            models.driver_cash_settlements,
            models.driver_cash_settlement_commands,
            models.driver_cash_settlement_items,
        ):
            assert session.scalar(sa.select(sa.func.count()).select_from(table)) == 0


def test_revoke_after_commit_denies_delivery_without_reverting_payments(
    settlement_world: SettlementWorld, monkeypatch: pytest.MonkeyPatch
) -> None:
    from test_operational_intents import _grant_permission

    world = settlement_world
    activate(world.factory)
    commit = Session.commit
    revoked = False

    def revoke(session: Session) -> None:
        nonlocal revoked
        commit(session)
        if not revoked:
            revoked = True
            world.remove_permission("orders.read")

    monkeypatch.setattr(Session, "commit", revoke)
    result = world.post()
    assert revoked and result.status_code == 403, result.text
    with world.factory() as session:
        assert session.scalar(sa.select(sa.func.count()).select_from(models.payments)) == 2
        _grant_permission(session, "orders.read")
        session.commit()
    recovered = world.post(recover=True)
    assert recovered.status_code == 200, recovered.text
    assert "total_cents" not in recovered.json()
    with world.factory() as session:
        assert session.scalar(sa.select(sa.func.count()).select_from(models.payments)) == 2


def test_recovery_never_bypasses_new_command_workspace_guard(
    settlement_world: SettlementWorld, monkeypatch: pytest.MonkeyPatch
) -> None:
    world = settlement_world
    activate(world.factory)
    assert world.post().status_code == 200
    monkeypatch.setenv("RESTAURANTOS_BRANCH_SCOPE_V2_ENABLED", "true")
    get_settings.cache_clear()
    try:
        assert world.post(recover=True).status_code == 200
        assert world.post(recover=True, key="f106-recovery-no-effect").status_code == 409
        assert world.post(key="f106-write-no-workspace").status_code in (403, 409)
        with world.factory() as session:
            assert session.scalar(sa.select(sa.func.count()).select_from(models.payments)) == 2
    finally:
        monkeypatch.delenv("RESTAURANTOS_BRANCH_SCOPE_V2_ENABLED")
        get_settings.cache_clear()


def test_closed_contracts_match_published_schemas() -> None:
    import json
    from pathlib import Path

    from restaurant_os.driver_settlement_views import (
        DriverSettlementCandidateV2,
        DriverSettlementReceiptV2,
    )

    root = Path(__file__).resolve().parents[3] / "packages/contracts/schemas"
    for name, model in (
        ("driver-settlement-candidate-v2", DriverSettlementCandidateV2),
        ("driver-settlement-receipt-v2", DriverSettlementReceiptV2),
    ):
        assert json.loads((root / (name + ".schema.json")).read_text()) == model.model_json_schema()
        assert model.model_json_schema()["additionalProperties"] is False


def test_recovery_rejects_other_actor_or_changed_scope(settlement_world: SettlementWorld) -> None:
    world = settlement_world
    activate(world.factory)
    assert world.post().status_code == 200
    other = world.client.post(
        "/api/v1/users",
        headers=_admin_headers(),
        json={
            "email": "other-settlement@fixture.invalid",
            "display_name": "Other cashier",
            "employee_code": "F106OT",
            "password": ident("synthetic-f106-user").upper() + "Aa1!",
            "role_id": ADMIN_ROLE_ID,
        },
    )
    assert other.status_code == 200, other.text
    token = create_session_token({"sub": other.json()["id"]}, get_settings().secret_key)
    response = world.client.post(
        PATH + "/recover",
        json=world.body,
        headers={
            "Authorization": f"Bearer {token}",
            "Idempotency-Key": KEY,
        },
    )
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["code"] == "driver_settlement_idempotency_conflict"
    for changed in (
        {"order_ids": world.body["order_ids"][:1]},
        {"branch_id": "018f6f73-2d0a-74f0-8f1c-000000009999"},
    ):
        response = world.client.post(
            PATH + "/recover",
            json={**world.body, **changed},
            headers={
                **_admin_headers(),
                "Idempotency-Key": KEY,
            },
        )
        assert response.status_code in (403, 409), response.text
    with world.factory() as session:
        assert session.scalar(sa.select(sa.func.count()).select_from(models.payments)) == 2
