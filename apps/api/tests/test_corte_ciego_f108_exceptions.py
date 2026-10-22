"""CC-D08: action permission alone cannot approve an accepted order exception."""

import pytest
import sqlalchemy as sa
from restaurant_os import models
from restaurant_os import operations as ops
from test_corte_ciego_f105_intents import activate
from test_corte_ciego_f106_amendments import AmendmentWorld
from test_corte_ciego_f106_amendments import amendment_world as amendment_world
from test_corte_ciego_f108_step_up import credential
from test_platform_api import ADMIN_USER_ID, _admin_headers


def test_cancel_action_without_exact_approval_has_no_effect(amendment_world: AmendmentWorld):
    world = amendment_world
    activate(world.factory)
    with world.factory() as session:
        before = list(session.execute(sa.select(models.inventory_movements)).mappings())
        with pytest.raises(ops.AuthorizationError, match="Exact supervisor"):
            ops.cancel_order(session, world.order, actor_user_id=ADMIN_USER_ID, commit=False)
        session.rollback()
        assert session.scalar(sa.select(models.orders.c.status)) == "ACCEPTED"
        assert list(session.execute(sa.select(models.inventory_movements)).mappings()) == before


def issue_payload(world: AmendmentWorld):
    with world.factory() as session:
        session.execute(
            models.user_credentials.delete().where(
                models.user_credentials.c.user_id == ADMIN_USER_ID
            )
        )
        secret = credential(session, ADMIN_USER_ID)
        session.commit()
    return {
        "action": "cancel",
        "expected_version": 1,
        "reason": "Exact authorized cancellation",
        "command": {},
        "supervisor_identity": ADMIN_USER_ID,
        "supervisor_secret": secret,
    }


def test_http_approval_binds_command_and_preserves_secret(amendment_world: AmendmentWorld):
    world = amendment_world
    activate(world.factory)
    payload = issue_payload(world)
    path = f"/api/v2/orders/{world.order}/exception-authorizations"
    malformed = world.client.post(
        path, headers=_admin_headers(), json={**payload, "extra": payload["supervisor_secret"]}
    )
    assert malformed.status_code == 409 and payload["supervisor_secret"] not in malformed.text
    malformed = world.client.post(path, headers=_admin_headers(), json=[payload])
    assert malformed.status_code == 422 and payload["supervisor_secret"] not in malformed.text
    approved = world.client.post(path, headers=_admin_headers(), json=payload)
    assert approved.status_code == 200, approved.text
    assert payload["supervisor_secret"] not in approved.text
    body = {
        "expected_version": 1,
        "reason": payload["reason"],
        "exception_authorization_id": approved.json()["authorization_id"],
    }
    cancel_path = f"/api/v1/orders/{world.order}/cancel"
    for changed in (
        {"reason": "Changed reason"},
        {"expected_version": 2},
        {"classification": "recovery"},
    ):
        denied = world.client.post(cancel_path, headers=_admin_headers(), json={**body, **changed})
        assert denied.status_code == 403, denied.text
    result = world.client.post(cancel_path, headers=_admin_headers(), json=body)
    assert result.status_code == 200, result.text
    again = world.client.post(cancel_path, headers=_admin_headers(), json=body)
    assert again.status_code in (403, 409), again.text
    with world.factory() as session:
        assert (
            session.scalar(
                sa.select(sa.func.count()).select_from(models.order_exception_consumptions)
            )
            == 1
        )
        assert payload["supervisor_secret"] not in str(
            session.execute(sa.select(models.audit_events)).mappings().all()
        )


def test_revoked_supervisor_cannot_consume_issued_approval(amendment_world: AmendmentWorld):
    world = amendment_world
    activate(world.factory)
    payload = issue_payload(world)
    approved = world.client.post(
        f"/api/v2/orders/{world.order}/exception-authorizations",
        headers=_admin_headers(),
        json=payload,
    )
    assert approved.status_code == 200, approved.text
    world.revoke("orders.exceptions.authorize")
    denied = world.client.post(
        f"/api/v1/orders/{world.order}/cancel",
        headers=_admin_headers(),
        json={
            "reason": payload["reason"],
            "expected_version": 1,
            "exception_authorization_id": approved.json()["authorization_id"],
        },
    )
    assert denied.status_code == 403, denied.text
    with world.factory() as session:
        assert session.scalar(sa.select(models.orders.c.status)) == "ACCEPTED"
        assert (
            session.scalar(
                sa.select(sa.func.count()).select_from(models.order_exception_consumptions)
            )
            == 0
        )


def test_no_approval_permission_is_not_replaced_by_public_identity(amendment_world: AmendmentWorld):
    world = amendment_world
    activate(world.factory)
    payload = issue_payload(world)
    world.revoke("orders.exceptions.authorize")
    response = world.client.post(
        f"/api/v2/orders/{world.order}/exception-authorizations",
        headers=_admin_headers(),
        json=payload,
    )
    assert response.status_code == 403, response.text


def test_http_amendment_exact_content_replay_and_recoverable_receipt(
    amendment_world: AmendmentWorld,
):
    world = amendment_world
    activate(world.factory)
    payload = issue_payload(world)
    payload.update(
        action="amend",
        reason=world.body["reason"],
        command={
            key: world.body[key]
            for key in ("lines", "delivery_selection", "delivery_quote_reference")
        },
    )
    path = f"/api/v2/orders/{world.order}/exception-authorizations"
    approved = world.client.post(path, headers=_admin_headers(), json=payload)
    assert approved.status_code == 200, approved.text
    identifier = approved.json()["authorization_id"]
    receipt_path = f"{path}/{identifier}/receipt"
    before = world.client.get(receipt_path, headers=_admin_headers())
    assert before.status_code == 200 and before.json()["applied"] is False, before.text
    world.body["exception_authorization_id"] = identifier
    original = world.body["delivery_selection"]
    world.body["delivery_selection"] = {"mode": "AUTO"}
    denied = world.post()
    assert denied.status_code == 403, denied.text
    world.body["delivery_selection"] = original
    applied = world.post()
    assert applied.status_code == 200, applied.text
    assert world.post().json() == applied.json()
    after = world.client.get(receipt_path, headers=_admin_headers())
    assert after.status_code == 200 and after.json()["applied"] is True, after.text
    assert set(after.json()) == {
        "projection",
        "schema_version",
        "policy_version",
        "authorization_id",
        "order_id",
        "action",
        "applied",
    }
    assert after.headers["cache-control"] == "no-store"
    world.revoke("orders.read")
    assert world.client.get(receipt_path, headers=_admin_headers()).status_code == 403


def test_expired_authorization_never_consumes(amendment_world: AmendmentWorld, monkeypatch):
    from datetime import timedelta

    world = amendment_world
    activate(world.factory)
    payload = issue_payload(world)
    approved = world.client.post(
        f"/api/v2/orders/{world.order}/exception-authorizations",
        headers=_admin_headers(),
        json=payload,
    )
    assert approved.status_code == 200, approved.text
    future = ops._now() + timedelta(minutes=3)
    monkeypatch.setattr(ops, "_now", lambda: future)
    denied = world.client.post(
        f"/api/v1/orders/{world.order}/cancel",
        headers=_admin_headers(),
        json={
            "reason": payload["reason"],
            "expected_version": 1,
            "exception_authorization_id": approved.json()["authorization_id"],
        },
    )
    assert (
        denied.status_code == 403 and denied.json()["detail"]["code"] == "order_exception_expired"
    ), denied.text
    with world.factory() as session:
        assert (
            session.scalar(
                sa.select(sa.func.count()).select_from(models.order_exception_consumptions)
            )
            == 0
        )
