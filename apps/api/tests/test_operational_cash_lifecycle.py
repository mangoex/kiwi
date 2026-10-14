"""Real cash lifecycle effects must share the durable central command owner."""

import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from restaurant_os import models
from restaurant_os import operations as ops
from sqlalchemy.exc import OperationalError
from test_branch_workspace_authority import workspace as workspace
from test_operational_intents import _grant_permission, _prepare_command
from test_operational_intents import operational as operational
from test_platform_api import ADMIN_ROLE_ID, ADMIN_USER_ID, BRANCH_ID


def _case(factory, operation):
    if operation == "compensate":
        from test_cash_concepts import _concept_payload
        from test_cash_ledger import _movement_payload

        with factory() as session:
            for code in (
                "cash.concept.manage",
                "cash.concept.read",
                "cash.movement.withdraw",
                "cash.movement.compensate",
            ):
                _grant_permission(session, code)
            session.execute(
                models.roles.update()
                .where(models.roles.c.id == ADMIN_ROLE_ID)
                .values(scope="organization")
            )
            grant = session.scalar(
                sa.select(models.role_authority_grants.c.role_id).where(
                    models.role_authority_grants.c.role_id == ADMIN_ROLE_ID
                )
            )
            if grant:
                session.execute(
                    models.role_authority_grants.update()
                    .where(models.role_authority_grants.c.role_id == ADMIN_ROLE_ID)
                    .values(authority_kind="organization_all_permissions")
                )
            else:
                session.execute(
                    models.role_authority_grants.insert().values(
                        role_id=ADMIN_ROLE_ID,
                        authority_kind="organization_all_permissions",
                        created_at=ops._now(),
                    )
                )
            session.commit()
            concept = ops.create_cash_concept(
                session, _concept_payload(), "cash-lifecycle-concept-001", ADMIN_USER_ID
            )
            movement = ops.create_cash_movement(
                session,
                _movement_payload(concept["id"]),
                "cash-lifecycle-source-001",
                ADMIN_USER_ID,
            )
        target = movement["movement"]["id"]
        return (
            "cash.movement.compensate",
            f"/cash/movements/{target}/compensations",
            target,
            {"reason": "Corrección sintética", "evidence_refs": ["evidence://ticket/audit"]},
        )
    if operation == "open":
        return (
            "cash.shift.open",
            "/cash/shifts/open",
            None,
            {"branch_id": BRANCH_ID, "register_id": "CAJA-AUDIT", "opening_cash_cents": 5000},
        )
    with factory() as session:
        shift_id = session.scalar(sa.select(models.cash_shifts.c.id))
    if operation == "close":
        return "cash.shift.close", f"/cash/shifts/{shift_id}/close-operationally", shift_id, {}
    return (
        "cash.shift.close.register",
        "/cash-shifts/close",
        None,
        {"branch_id": BRANCH_ID, "register_id": "CAJA-01"},
    )


@pytest.mark.parametrize("operation", ["open", "close", "close-register", "compensate"])
def test_cash_lifecycle_cannot_bypass_preparation(operational, operation):
    client, factory, headers = operational
    _, endpoint, _, body = _case(factory, operation)
    with factory() as session:
        before = [dict(row) for row in session.execute(sa.select(models.cash_shifts)).mappings()]
    result = client.post(
        f"/api/v1{endpoint}",
        headers={**headers, "Idempotency-Key": "cash-lifecycle-bypass-001"},
        json=body,
    )
    assert result.status_code == 409, result.text
    assert result.json()["detail"]["code"] == "operational_command_required"
    with factory() as session:
        assert [
            dict(row) for row in session.execute(sa.select(models.cash_shifts)).mappings()
        ] == before


@pytest.mark.parametrize("operation", ["open", "close", "close-register", "compensate"])
def test_real_cash_lifecycle_replays_and_recovers_minimum(operational, operation):
    client, factory, headers = operational
    kind, endpoint, target, body = _case(factory, operation)
    receipt = _prepare_command(client, headers, kind, body, "x", target)
    command_headers = {**headers, "Idempotency-Key": "x", "X-Operational-Intent": receipt["id"]}
    sent = client.post(f"/api/v1{endpoint}", headers=command_headers, json=body)
    assert sent.status_code == 200, sent.text
    replay = client.post(f"/api/v1{endpoint}", headers=command_headers, json=body)
    assert replay.status_code == 200 and replay.json() == sent.json(), replay.text
    with factory() as session:
        row = session.execute(sa.select(models.operational_command_intents)).mappings().one()
        assert row["state"] == "applied" and row["resource_id"]
        source = (
            models.cash_movement_commands
            if operation == "compensate"
            else models.cash_shift_commands
        )
        assert session.scalar(sa.select(sa.func.count()).select_from(source)) == 2
        if operation == "compensate":
            assert row["resource_id"] == sent.json()["movement"]["id"] != target
    recovered = client.post(f"/api/v1/operational-intents/{receipt['id']}/resolve", headers=headers)
    assert recovered.status_code == 200 and recovered.json()["state"] == "acknowledged", (
        recovered.text
    )


def _migration():
    path = (
        Path(__file__).resolve().parents[1]
        / "alembic/versions/202610141230_0091_cash_lifecycle_intents.py"
    )
    spec = importlib.util.spec_from_file_location("cash_lifecycle_test_migration", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("terminal", [False, True])
def test_0091_roundtrip_preserves_0090_identity_and_history(operational, terminal):
    client, factory, headers = operational
    receipt = _prepare_command(
        client,
        headers,
        "order.create",
        {"branch_id": BRANCH_ID, "lines": []},
        "cash-history-legacy-001",
    )
    if terminal:
        resolved = client.post(
            f"/api/v1/operational-intents/{receipt['id']}/resolve", headers=headers
        )
        assert resolved.status_code == 200 and resolved.json()["state"] == "no_effect"
    with factory() as session:
        before = dict(
            session.execute(sa.select(models.operational_command_intents)).mappings().one()
        )
        before.pop("command_namespace")
        session.commit()
        connection = session.connection()
        with Operations.context(MigrationContext.configure(connection)):
            _migration().downgrade()
        old = sa.Table("operational_command_intents", sa.MetaData(), autoload_with=connection)
        assert "command_namespace" not in old.c
        assert dict(connection.execute(sa.select(old)).mappings().one()) == before
        with Operations.context(MigrationContext.configure(connection)):
            _migration().upgrade()
        current = sa.Table("operational_command_intents", sa.MetaData(), autoload_with=connection)
        after = dict(connection.execute(sa.select(current)).mappings().one())
        assert after.pop("command_namespace") == "order.create"
        assert after == before
        session.commit()


@pytest.mark.parametrize("terminal", [False, True])
def test_0091_never_drops_new_cash_history(operational, terminal):
    client, factory, headers = operational
    kind, _, target, body = _case(factory, "open")
    receipt = _prepare_command(client, headers, kind, body, "cash-history-001", target)
    if terminal:
        assert (
            client.post(
                f"/api/v1/operational-intents/{receipt['id']}/resolve", headers=headers
            ).status_code
            == 200
        )
    with factory() as session:
        before = dict(
            session.execute(sa.select(models.operational_command_intents)).mappings().one()
        )
        with Operations.context(MigrationContext.configure(session.connection())):
            with pytest.raises(
                RuntimeError, match="0091 downgrade blocked: cash lifecycle command history exists"
            ):
                _migration().downgrade()
        assert (
            dict(session.execute(sa.select(models.operational_command_intents)).mappings().one())
            == before
        )
        assert "command_namespace" in {
            c["name"]
            for c in sa.inspect(session.connection()).get_columns("operational_command_intents")
        }


def test_cash_namespace_refuses_incompatible_preparation(operational):
    client, factory, headers = operational
    kind, _, target, body = _case(factory, "open")
    receipt = _prepare_command(client, headers, kind, body, "x", target)
    close_kind, _, close_target, close_body = _case(factory, "close-register")
    conflict = client.post(
        "/api/v1/operational-intents",
        headers={**headers, "Idempotency-Key": "x"},
        json={"kind": close_kind, "target_id": close_target, "payload": close_body},
    )
    assert (
        conflict.status_code == 409 and conflict.json()["detail"]["code"] == "idempotency_conflict"
    )
    assert client.get("/api/v1/operational-intents", headers=headers).json() == [receipt]


def test_legacy_compensation_payload_cannot_override_route_on_replay(operational):
    from uuid import uuid4

    _, factory, _ = operational
    _, _, target, body = _case(factory, "compensate")
    with factory() as session:
        ops.compensate_cash_movement(session, target, body, "legacy-route-proof-001", ADMIN_USER_ID)
        with pytest.raises(ops.BusinessError) as error:
            ops.compensate_cash_movement(
                session,
                str(uuid4()),
                {**body, "movement_id": target},
                "legacy-route-proof-001",
                ADMIN_USER_ID,
            )
        assert error.value.code == "cash_compensation_invalid"


def test_failed_central_close_must_not_emit_financial_success(operational, monkeypatch):
    client, factory, headers = operational
    kind, endpoint, target, body = _case(factory, "close")
    receipt = _prepare_command(client, headers, kind, body, "sol-metric", target)
    metrics = []
    real_audit = ops._audit

    def audit_fail(session, action=None, *args, **kwargs):
        if action == "operational_command.applied":
            raise OperationalError(
                "synthetic-statement", {}, RuntimeError("Synthetic persistence failure")
            )
        return real_audit(session, action, *args, **kwargs)

    monkeypatch.setattr(ops, "_audit", audit_fail)
    monkeypatch.setattr(
        ops, "_record_pco004_metric", lambda metric, **fields: metrics.append((metric, fields))
    )
    result = client.post(
        "/api/v1" + endpoint,
        headers={**headers, "Idempotency-Key": "sol-metric", "X-Operational-Intent": receipt["id"]},
        json=body,
    )
    assert result.status_code == 503, result.text
    with factory() as session:
        assert session.scalar(sa.select(models.cash_shifts.c.status)) == "OPEN"
        assert (
            session.scalar(sa.select(sa.func.count()).select_from(models.cash_shift_closures)) == 0
        )
        assert session.scalar(sa.select(models.operational_command_intents.c.state)) == "prepared"
    assert not any(
        name == "cash_shift_operational_close_total" and fields["result"] == "success"
        for name, fields in metrics
    ), metrics


@pytest.mark.parametrize(
    "operation,bad_id", [("close", {"id": "invalid"}), ("compensate", ["invalid"])]
)
def test_malformed_result_resource_id_is_evidence_conflict(operational, operation, bad_id):
    client, factory, headers = operational
    kind, endpoint, target, body = _case(factory, operation)
    receipt = _prepare_command(client, headers, kind, body, "sol-malformed-proof", target)
    sent = client.post(
        "/api/v1" + endpoint,
        headers={
            **headers,
            "Idempotency-Key": "sol-malformed-proof",
            "X-Operational-Intent": receipt["id"],
        },
        json=body,
    )
    assert sent.status_code == 200, sent.text
    with factory() as session:
        row = session.execute(sa.select(models.operational_command_intents)).mappings().one()
        source = (
            models.cash_shift_commands if operation == "close" else models.cash_movement_commands
        )
        result = {"closure_id": bad_id} if operation == "close" else {"movement": {"id": bad_id}}
        session.execute(
            source.update().where(source.c.id == row["domain_command_id"]).values(result=result)
        )
        session.commit()
    ack = client.post(f"/api/v1/operational-intents/{receipt['id']}/resolve", headers=headers)
    assert (
        ack.status_code == 409
        and ack.json()["detail"]["code"] == "operational_command_evidence_conflict"
    ), ack.text
    with factory() as session:
        assert session.scalar(sa.select(models.operational_command_intents.c.state)) == "applied"
