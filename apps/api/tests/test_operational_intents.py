"""Durable uncertain-command tests use synthetic actors and server evidence."""

from uuid import NAMESPACE_URL, uuid5

import pytest
import sqlalchemy as sa
from restaurant_os import models
from restaurant_os import operations as ops
from restaurant_os.operational_intents import execute_intent
from restaurant_os.order_execution import defer_authorization_audit, defer_authorization_denial
from sqlalchemy.exc import OperationalError
from test_branch_scope_selection import _grant_selection
from test_branch_workspace_authority import _reissue
from test_branch_workspace_authority import workspace as workspace
from test_platform_api import ADMIN_ROLE_ID, ADMIN_USER_ID, BRANCH_ID, _admin_headers


def _prepared(client, fixture, headers, key="uncertain-order-synthetic-001"):
    profile = _reissue(client, headers).json()
    command_headers = {
        **headers,
        "X-Branch-Context": profile["branch_workspace_context"],
        "Idempotency-Key": key,
    }
    payload = {"branch_id": fixture["branch_id"], "register_id": "CAJA-01", "lines": []}
    result = client.post(
        "/api/v1/operational-intents",
        headers=command_headers,
        json={"kind": "order.create", "target_id": None, "payload": payload},
    )
    assert result.status_code == 200, result.text
    return result.json(), command_headers, payload


def test_preparation_survives_a_fresh_session_and_blocks_selection(workspace):
    client, fixture, factory, headers = workspace
    receipt, _, _ = _prepared(client, fixture, headers)
    assert receipt["state"] == "prepared"
    with factory() as session:
        assert session.scalar(sa.select(models.operational_command_intents.c.state)) == "prepared"
    change = client.post(
        "/api/v1/auth/branch-selections",
        headers={**headers, "Idempotency-Key": "uncertain-switch-synthetic-001"},
        json={"target_branch_id": BRANCH_ID, "expected_authorization_version": 1},
    )
    assert change.status_code == 409, change.text
    assert change.json()["detail"]["code"] == "branch_switch_uncertain_command"


def test_no_effect_is_proved_by_server_and_late_execution_is_rejected(workspace):
    client, fixture, factory, headers = workspace
    receipt, command_headers, payload = _prepared(client, fixture, headers)
    resolved = client.post(f"/api/v1/operational-intents/{receipt['id']}/resolve", headers=headers)
    assert resolved.status_code == 200, resolved.text
    assert resolved.json()["state"] == "no_effect"
    late = client.post(
        "/api/v1/orders",
        headers={**command_headers, "X-Operational-Intent": receipt["id"]},
        json=payload,
    )
    assert late.status_code == 409, late.text
    assert late.json()["detail"]["code"] == "operational_command_terminal"
    with factory() as session:
        assert (
            session.scalar(sa.select(sa.func.count()).select_from(models.order_create_commands))
            == 0
        )


def test_v2_financial_send_cannot_bypass_registration(workspace):
    client, fixture, _, headers = workspace
    profile = _reissue(client, headers).json()
    result = client.post(
        "/api/v1/orders",
        headers={
            **headers,
            "X-Branch-Context": profile["branch_workspace_context"],
            "Idempotency-Key": "uncertain-bypass-synthetic-001",
        },
        json={"branch_id": fixture["branch_id"], "lines": []},
    )
    assert result.status_code == 409, result.text
    assert result.json()["detail"]["code"] == "operational_command_required"


@pytest.fixture
def operational(workspace):
    client, fixture, factory, _ = workspace
    with factory() as session:
        _grant_selection(session, ADMIN_ROLE_ID, workspace=False)
    headers = _admin_headers()
    selected = client.post(
        "/api/v1/auth/branch-selections",
        headers={**headers, "Idempotency-Key": "uncertain-admin-context-001"},
        json={"target_branch_id": BRANCH_ID, "expected_authorization_version": 1},
    )
    assert selected.status_code == 200, selected.text
    profile = selected.json()
    with factory() as session:
        ops.open_cash_shift_idempotently(
            session, BRANCH_ID, "CAJA-01", 10000, "uncertain-test-shift-open-001", ADMIN_USER_ID
        )
    return client, factory, {**headers, "X-Branch-Context": profile["branch_workspace_context"]}


def _order_body():
    return {
        "branch_id": BRANCH_ID,
        "register_id": "CAJA-01",
        "order_type": "dine-in",
        "lines": [{"product_id": "018f6f73-2d0a-74f0-8f1c-000000000111", "quantity": 1}],
    }


def _prepare_command(client, headers, kind, body, key, target=None):
    response = client.post(
        "/api/v1/operational-intents",
        headers={**headers, "Idempotency-Key": key},
        json={"kind": kind, "target_id": target, "payload": body},
    )
    assert response.status_code == 200, response.text
    return response.json()


def _execute_order(operational, key="uncertain-real-order-001"):
    client, _, headers = operational
    body = _order_body()
    receipt = _prepare_command(client, headers, "order.create", body, key)
    command_headers = {**headers, "Idempotency-Key": key, "X-Operational-Intent": receipt["id"]}
    sent = client.post("/api/v1/orders", headers=command_headers, json=body)
    assert sent.status_code == 200, sent.text
    return receipt, command_headers, sent.json()


def test_real_order_and_intent_commit_together_then_replay_and_minimal_recovery(operational):
    client, factory, headers = operational
    receipt, command_headers, result = _execute_order(operational)
    with factory() as session:
        row = session.execute(sa.select(models.operational_command_intents)).mappings().one()
        assert row["state"] == "applied" and row["resource_id"] == result["id"]
        before = {
            table.name: session.scalar(sa.select(sa.func.count()).select_from(table))
            for table in (
                models.orders,
                models.order_create_commands,
                models.inventory_movements,
                models.production_tasks,
            )
        }
    replay = client.post("/api/v1/orders", headers=command_headers, json=_order_body())
    assert replay.status_code == 200, replay.text
    assert replay.json() == result
    recovered = client.post(f"/api/v1/operational-intents/{receipt['id']}/resolve", headers=headers)
    assert recovered.status_code == 200, recovered.text
    assert recovered.json() == {**receipt, "state": "acknowledged", "resource_id": result["id"]}
    assert set(recovered.json()) == {"id", "kind", "branch_id", "state", "resource_id"}
    assert client.get("/api/v1/operational-intents", headers=headers).json() == []
    with factory() as session:
        after = {
            table.name: session.scalar(sa.select(sa.func.count()).select_from(table))
            for table in (
                models.orders,
                models.order_create_commands,
                models.inventory_movements,
                models.production_tasks,
            )
        }
        assert after == before


def test_recovery_does_not_renew_financial_permission(operational):
    client, factory, headers = operational
    receipt, command_headers, result = _execute_order(operational)
    with factory() as session:
        permission = session.scalar(
            sa.select(models.permissions.c.id).where(models.permissions.c.code == "orders.create")
        )
        session.execute(
            models.role_permissions.delete().where(
                models.role_permissions.c.role_id == ADMIN_ROLE_ID,
                models.role_permissions.c.permission_id == permission,
            )
        )
        session.execute(
            models.users.update()
            .where(models.users.c.id == ADMIN_USER_ID)
            .values(authorization_version=2)
        )
        session.commit()
    recovered = client.post(
        f"/api/v1/operational-intents/{receipt['id']}/resolve", headers=_admin_headers()
    )
    assert recovered.status_code == 200, recovered.text
    assert recovered.json()["resource_id"] == result["id"]
    denied = client.post("/api/v1/orders", headers=command_headers, json=_order_body())
    assert denied.status_code == 403, denied.text
    assert denied.json()["detail"]["code"] == "authorization_version_conflict"


@pytest.mark.parametrize("field,value", [("lines", []), ("owner_name", "Changed synthetic owner")])
def test_changed_payload_never_executes_under_same_intention(operational, field, value):
    client, factory, headers = operational
    receipt = _prepare_command(client, headers, "order.create", _order_body(), "uncertain-body-001")
    sent = client.post(
        "/api/v1/orders",
        headers={
            **headers,
            "Idempotency-Key": "uncertain-body-001",
            "X-Operational-Intent": receipt["id"],
        },
        json={**_order_body(), field: value},
    )
    assert sent.status_code == 409, sent.text
    assert sent.json()["detail"]["code"] == "idempotency_conflict"
    with factory() as session:
        assert (
            session.scalar(sa.select(sa.func.count()).select_from(models.order_create_commands))
            == 0
        )
        assert session.scalar(sa.select(models.operational_command_intents.c.state)) == "prepared"


def test_other_actor_cannot_read_or_resolve_intention(workspace):
    client, fixture, _, headers = workspace
    receipt, _, _ = _prepared(client, fixture, headers)
    foreign = client.post(
        f"/api/v1/operational-intents/{receipt['id']}/resolve", headers=_admin_headers()
    )
    assert foreign.status_code == 404, foreign.text
    assert client.get("/api/v1/operational-intents", headers=_admin_headers()).json() == []


@pytest.mark.parametrize("fault", ["commit", "rollback"])
def test_domain_cannot_commit_or_discard_the_shared_transaction(operational, fault):
    client, factory, headers = operational
    body, key = _order_body(), "uncertain-atomicity-001"
    receipt = _prepare_command(client, headers, "order.create", body, key)
    with factory() as session:

        def bad_domain():
            if fault == "commit":
                session.commit()
            else:
                session.rollback()
            return {"id": "not-a-domain-proof"}

        with pytest.raises(ops.BusinessError) as error:
            execute_intent(
                session,
                ADMIN_USER_ID,
                receipt["id"],
                "order.create",
                None,
                body,
                key,
                headers["X-Branch-Context"],
                bad_domain,
            )
        assert error.value.code in (
            "operational_command_atomicity_violation",
            "operational_command_evidence_conflict",
        )
        session.commit()
    with factory() as session:
        assert session.scalar(sa.select(models.operational_command_intents.c.state)) == "prepared"


def test_preparation_replay_is_exact_and_preserves_original_hash(operational):
    client, factory, headers = operational
    body, key = _order_body(), "uncertain-prepare-replay-001"
    receipt = _prepare_command(client, headers, "order.create", body, key)
    assert _prepare_command(client, headers, "order.create", body, key) == receipt
    conflict = client.post(
        "/api/v1/operational-intents",
        headers={**headers, "Idempotency-Key": key},
        json={
            "kind": "order.create",
            "target_id": None,
            "payload": {**body, "register_id": "CAJA-02"},
        },
    )
    assert conflict.status_code == 409, conflict.text
    assert conflict.json()["detail"]["code"] == "idempotency_conflict"
    with factory() as session:
        assert (
            session.scalar(
                sa.select(sa.func.count()).select_from(models.operational_command_intents)
            )
            == 1
        )


def test_real_payment_and_intent_share_commit_and_replay(operational):
    client, factory, headers = operational
    _, _, order = _execute_order(operational)
    body = {"amount_cents": order["total_cents"], "method": "card", "register_id": "CAJA-01"}
    key = "uncertain-real-payment-001"
    receipt = _prepare_command(client, headers, "payment.confirm", body, key, order["id"])
    command_headers = {**headers, "Idempotency-Key": key, "X-Operational-Intent": receipt["id"]}
    path = f"/api/v1/orders/{order['id']}/payments"
    result = client.post(path, headers=command_headers, json=body)
    assert result.status_code == 200, result.text
    replay = client.post(path, headers=command_headers, json=body)
    assert replay.status_code == 200 and replay.json() == result.json(), replay.text
    with factory() as session:
        command = session.execute(sa.select(models.payment_commands)).mappings().one()
        row = (
            session.execute(
                sa.select(models.operational_command_intents).where(
                    models.operational_command_intents.c.id == receipt["id"]
                )
            )
            .mappings()
            .one()
        )
        assert row["state"] == "applied" and row["resource_id"] == command["payment_id"]
        assert session.scalar(sa.select(sa.func.count()).select_from(models.payments)) == 1
    recovered = client.post(f"/api/v1/operational-intents/{receipt['id']}/resolve", headers=headers)
    assert recovered.status_code == 200 and recovered.json()["state"] == "acknowledged"


def _grant_permission(session, code):
    permission = session.scalar(
        sa.select(models.permissions.c.id).where(models.permissions.c.code == code)
    )
    if not permission:
        permission = str(uuid5(NAMESPACE_URL, "restaurantos:operational-intent-test:" + code))
        session.execute(
            models.permissions.insert().values(
                id=permission, code=code, description=code, created_at=ops._now()
            )
        )
    exists = session.scalar(
        sa.select(models.role_permissions.c.role_id).where(
            models.role_permissions.c.role_id == ADMIN_ROLE_ID,
            models.role_permissions.c.permission_id == permission,
        )
    )
    if not exists:
        session.execute(
            models.role_permissions.insert().values(role_id=ADMIN_ROLE_ID, permission_id=permission)
        )
    session.commit()


def test_central_denial_deferral_is_explicit_and_restores_its_owner():
    denial = {
        "actor_user_id": ADMIN_USER_ID,
        "permission_code": "orders.create",
        "branch_id": BRANCH_ID,
        "reason": "permission_not_granted",
    }
    with defer_authorization_audit() as ordinary:
        assert defer_authorization_denial(**denial) is False
        assert ordinary == []
        with defer_authorization_audit(central_owner=True) as owned:
            assert defer_authorization_denial(**denial) is True
            assert owned == [denial]
        assert defer_authorization_denial(**denial) is False
    assert defer_authorization_denial(**denial) is False


def test_intent_body_is_bounded_before_authentication(workspace):
    client, _, factory, _ = workspace
    result = client.post(
        "/api/v1/operational-intents",
        content=b"x" * 262145,
        headers={"Content-Type": "application/json"},
    )
    assert result.status_code == 413
    assert result.json()["detail"]["code"] == "workspace_payload_too_large"
    with factory() as session:
        assert (
            session.scalar(
                sa.select(sa.func.count()).select_from(models.operational_command_intents)
            )
            == 0
        )


def test_domain_secondary_denial_preserves_403_and_audit_without_partial_effect(operational):
    from test_cash_ledger import _movement_payload

    client, factory, headers = operational
    with factory() as session:
        _grant_permission(session, "cash.movement.withdraw")
        permission = session.scalar(
            sa.select(models.permissions.c.id).where(
                models.permissions.c.code == "cash.concept.read"
            )
        )
        if permission:
            session.execute(
                models.role_permissions.delete().where(
                    models.role_permissions.c.role_id == ADMIN_ROLE_ID,
                    models.role_permissions.c.permission_id == permission,
                )
            )
            session.commit()
    body = _movement_payload("018f6f73-2d0a-74f0-8f1c-000000009999")
    key = "uncertain-secondary-denial-001"
    receipt = _prepare_command(client, headers, "cash.movement.create", body, key)
    result = client.post(
        "/api/v1/cash/movements",
        headers={**headers, "Idempotency-Key": key, "X-Operational-Intent": receipt["id"]},
        json=body,
    )
    assert result.status_code == 403, result.text
    assert result.json()["detail"]["code"] == "permission_denied"
    with factory() as session:
        assert session.scalar(sa.select(models.operational_command_intents.c.state)) == "prepared"
        assert (
            session.scalar(sa.select(sa.func.count()).select_from(models.cash_movement_commands))
            == 0
        )
        assert (
            session.scalar(
                sa.select(sa.func.count())
                .select_from(models.audit_events)
                .where(
                    models.audit_events.c.action == "authorization.denied",
                    models.audit_events.c.entity_id == "cash.concept.read",
                )
            )
            == 1
        )


def test_lost_result_after_real_commit_recovers_applied_without_duplicate_effect(
    operational, monkeypatch
):
    client, factory, headers = operational
    key, body = "uncertain-postcommit-loss-001", _order_body()
    receipt = _prepare_command(client, headers, "order.create", body, key)
    with factory() as session:
        real_commit = session.commit

        def commit_then_lose_result():
            real_commit()
            raise OperationalError(
                "synthetic-private-statement",
                {"private": "synthetic"},
                RuntimeError("synthetic-private-parameters"),
            )

        monkeypatch.setattr(session, "commit", commit_then_lose_result)
        with pytest.raises(ops.BusinessError) as error:
            execute_intent(
                session,
                ADMIN_USER_ID,
                receipt["id"],
                "order.create",
                None,
                body,
                key,
                headers["X-Branch-Context"],
                lambda: ops.create_local_order(
                    session,
                    body["lines"],
                    branch_id=BRANCH_ID,
                    register_id="CAJA-01",
                    actor_user_id=ADMIN_USER_ID,
                    idempotency_key=key,
                    commit=False,
                ),
            )
        assert error.value.code == "operational_command_persistence_unavailable"
        assert "synthetic-private" not in error.value.message
    result = client.post(f"/api/v1/operational-intents/{receipt['id']}/resolve", headers=headers)
    assert result.status_code == 200 and result.json()["state"] == "acknowledged", result.text
    with factory() as session:
        assert (
            session.scalar(sa.select(sa.func.count()).select_from(models.order_create_commands))
            == 1
        )
        assert session.scalar(sa.select(sa.func.count()).select_from(models.orders)) == 1


def test_real_cash_movement_and_intent_share_commit_and_replay(operational):
    from test_cash_concepts import _concept_payload
    from test_cash_ledger import _movement_payload

    client, factory, headers = operational
    with factory() as session:
        _grant_permission(session, "cash.concept.manage")
        _grant_permission(session, "cash.movement.withdraw")
        _grant_permission(session, "cash.concept.read")
        concept = ops.create_cash_concept(
            session, _concept_payload(), "uncertain-concept-001", ADMIN_USER_ID
        )
    body = _movement_payload(concept["id"])
    key = "uncertain-real-movement-001"
    receipt = _prepare_command(client, headers, "cash.movement.create", body, key)
    command_headers = {**headers, "Idempotency-Key": key, "X-Operational-Intent": receipt["id"]}
    result = client.post("/api/v1/cash/movements", headers=command_headers, json=body)
    assert result.status_code == 200, result.text
    replay = client.post("/api/v1/cash/movements", headers=command_headers, json=body)
    assert replay.status_code == 200, replay.text
    assert result.json()["movement"] == replay.json()["movement"]
    with factory() as session:
        row = session.execute(sa.select(models.operational_command_intents)).mappings().one()
        assert row["state"] == "applied" and row["resource_id"] == result.json()["movement"]["id"]
        assert (
            session.scalar(sa.select(sa.func.count()).select_from(models.cash_movement_commands))
            == 1
        )
    recovered = client.post(f"/api/v1/operational-intents/{receipt['id']}/resolve", headers=headers)
    assert recovered.status_code == 200 and recovered.json()["state"] == "acknowledged"
