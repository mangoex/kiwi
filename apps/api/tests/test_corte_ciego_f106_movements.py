"""Human movement commands never return financial summaries under the blind policy."""

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import sqlalchemy as sa
from corte_ciego_fixtures import grant_permission
from restaurant_os import models
from restaurant_os import operations as ops
from restaurant_os.auth import create_session_token
from restaurant_os.config import get_settings
from sqlalchemy.orm import Session, sessionmaker
from test_branch_workspace_authority import workspace as workspace
from test_cash_concepts import (
    BRANCH_A,
    BRANCH_B,
    CASHIER_ID,
    CASHIER_ROLE_ID,
    ORG_ID,
    OWNER_ID,
    OWNER_ROLE_ID,
    _cash_concept_client,
    _concept_payload,
)
from test_cash_ledger import _insert_shift, _movement_payload
from test_corte_ciego_f1_red import assert_blind
from test_operational_intents import _grant_permission, _prepare_command
from test_operational_intents import operational as operational
from test_platform_api import ADMIN_USER_ID


@pytest.fixture
def movement_world() -> Iterator[tuple[Any, Any, dict[str, Any]]]:
    client = _cash_concept_client()
    factory = client.app.state.test_session_factory
    with factory() as session:
        _insert_shift(session)
        for role in (CASHIER_ROLE_ID, OWNER_ROLE_ID):
            for code in ("cash.shift.read", "cash.movement.withdraw", "cash.movement.compensate"):
                grant_permission(session, role, code)
        session.commit()
        concept = ops.create_cash_concept(
            session, _concept_payload(), "f106-movement-concept", OWNER_ID
        )
    try:
        yield client, factory, _movement_payload(concept["id"])
    finally:
        client.close()


def activate(factory: Any) -> None:
    with factory() as session:
        session.execute(
            models.blind_cash_policy_revisions.insert().values(
                organization_id=ORG_ID,
                branch_id=BRANCH_A,
                revision=1,
                manifest_digest="a" * 64,
                minimum_api_version=2,
                minimum_client_version=2,
                minimum_gateway_version=2,
                event="activated",
                created_at=ops._now(),
            )
        )
        session.commit()


def remove_permission(factory: Any, code: str) -> None:
    with factory() as session:
        permission = session.scalar(
            sa.select(models.permissions.c.id).where(models.permissions.c.code == code)
        )
        session.execute(
            models.role_permissions.delete().where(
                models.role_permissions.c.role_id == CASHIER_ROLE_ID,
                models.role_permissions.c.permission_id == permission,
            )
        )
        session.commit()


def headers(actor: str = CASHIER_ID, key: str = "f106-movement-key") -> dict[str, str]:
    token = create_session_token({"sub": actor}, get_settings().secret_key)
    return {"Authorization": f"Bearer {token}", "Idempotency-Key": key}


def test_http_movement_receipt_preserves_stored_money(movement_world: Any) -> None:
    client, factory, body = movement_world
    activate(factory)
    result = client.post("/api/v1/cash/movements", headers=headers(), json=body)
    assert result.status_code == 200, result.text
    assert_blind(result.json())
    assert result.json()["action"] == "cash.movement.create"
    assert "movement" not in result.json() and "summary_at_commit" not in result.json()
    assert result.headers["cache-control"] == "no-store"
    with factory() as session:
        stored = session.scalar(sa.select(models.cash_movement_commands.c.result))
        assert stored["movement"]["amount_cents"] == 2000
        assert stored["summary_at_commit"]["expected_cash_cents"] == 8000


def test_legacy_replay_after_write_revocation_has_no_snapshot_query(movement_world: Any) -> None:
    _, factory, body = movement_world
    with factory() as session:
        original = ops.create_cash_movement(session, body, "f106-old-movement", CASHIER_ID)
    activate(factory)
    remove_permission(factory, "cash.movement.withdraw")
    statements: list[str] = []
    raw_snapshots: list[str] = []
    engine = factory.kw["bind"]

    def observe(_conn: Any, _cursor: Any, sql: str, _params: Any, context: Any, _many: Any) -> None:
        if sql.lstrip().upper().startswith("SELECT"):
            statements.append(sql)
            statement = context.compiled.statement if context.compiled else None
            if isinstance(statement, sa.sql.Select) and any(
                column is models.cash_movement_commands.c.result
                for column in statement.selected_columns
            ):
                raw_snapshots.append(sql)

    sa.event.listen(engine, "before_cursor_execute", observe)
    try:
        with factory() as session:
            result = ops.create_cash_movement(session, body, "f106-old-movement", CASHIER_ID)
    finally:
        sa.event.remove(engine, "before_cursor_execute", observe)
    assert_blind(result)
    assert result["resource_id"] == original["movement"]["id"]
    assert not any(
        "cash_movements.amount_cents" in sql or "payments.amount_cents" in sql for sql in statements
    )
    # JSON_EXTRACT(result, path) references the column but only returns a resource ID.
    assert not raw_snapshots
    with factory() as session:
        with pytest.raises(ops.AuthorizationError):
            ops.create_cash_movement(session, body, "f106-new-not-allowed", CASHIER_ID)
    remove_permission(factory, "cash.shift.read")
    with factory() as session:
        with pytest.raises(ops.AuthorizationError):
            ops.create_cash_movement(session, body, "f106-old-movement", CASHIER_ID)


def test_no_read_prevents_effect_and_foreign_scope_cannot_replay(movement_world: Any) -> None:
    _, factory, body = movement_world
    with factory() as session:
        ops.create_cash_movement(session, body, "f106-scoped-movement", CASHIER_ID)
    activate(factory)
    with factory() as session:
        with pytest.raises(ops.AuthorizationError):
            ops.create_cash_movement(session, body, "f106-scoped-movement", OWNER_ID)
    with factory() as session:
        with pytest.raises(ops.BusinessError):
            ops.create_cash_movement(
                session, {**body, "branch_id": BRANCH_B}, "f106-scoped-movement", CASHIER_ID
            )
    remove_permission(factory, "cash.shift.read")
    with factory() as session:
        with pytest.raises(ops.AuthorizationError):
            ops.create_cash_movement(session, body, "f106-no-read", CASHIER_ID)
    with factory() as session:
        assert session.scalar(sa.select(sa.func.count()).select_from(models.cash_movements)) == 1


def test_compensation_is_closed_and_still_requires_owner(movement_world: Any) -> None:
    client, factory, body = movement_world
    with factory() as session:
        original = ops.create_cash_movement(session, body, "f106-source-movement", CASHIER_ID)
    activate(factory)
    target = original["movement"]["id"]
    correction = {"reason": "Synthetic correction", "evidence_refs": ["evidence://f106/owner"]}
    denied = client.post(
        f"/api/v1/cash/movements/{target}/compensations", headers=headers(), json=correction
    )
    assert denied.status_code == 403, denied.text
    result = client.post(
        f"/api/v1/cash/movements/{target}/compensations", headers=headers(OWNER_ID), json=correction
    )
    assert result.status_code == 200, result.text
    assert_blind(result.json())
    assert result.json()["action"] == "cash.movement.compensate"
    with factory() as session:
        amounts = session.scalars(sa.select(models.cash_movements.c.amount_cents)).all()
        assert amounts == [2000, 2000]


@pytest.mark.parametrize("typ", ["agent", "device"])
def test_technical_token_cannot_use_human_movement_endpoint(movement_world: Any, typ: str) -> None:
    client, factory, body = movement_world
    activate(factory)
    token = create_session_token({"sub": CASHIER_ID, "typ": typ}, get_settings().secret_key)
    result = client.post(
        "/api/v1/cash/movements",
        headers={**headers(), "Authorization": f"Bearer {token}"},
        json=body,
    )
    assert result.status_code == 403, result.text
    with factory() as session:
        assert session.scalar(sa.select(sa.func.count()).select_from(models.cash_movements)) == 0


def test_published_movement_receipt_schema_matches_runtime() -> None:
    from restaurant_os.cash_movement_views import CashMovementReceiptV2

    schema = (
        Path(__file__).resolve().parents[3]
        / "packages/contracts/schemas/cash-movement-command-receipt-v2.schema.json"
    )
    assert (
        json.loads(schema.read_text(encoding="utf-8")) == CashMovementReceiptV2.model_json_schema()
    )


def test_read_revoked_after_commit_does_not_disclose_or_duplicate(
    movement_world: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, factory, body = movement_world
    activate(factory)
    commit = Session.commit
    revoked = False

    def revoke_after_commit(session: Session) -> None:
        nonlocal revoked
        commit(session)
        if not revoked:
            revoked = True
            remove_permission(factory, "cash.shift.read")

    monkeypatch.setattr(Session, "commit", revoke_after_commit)
    result = client.post("/api/v1/cash/movements", headers=headers(), json=body)
    assert revoked and result.status_code == 403, result.text
    with factory() as session:
        assert session.scalar(sa.select(sa.func.count()).select_from(models.cash_movements)) == 1
        grant_permission(session, CASHIER_ROLE_ID, "cash.shift.read")
        session.commit()
    replay = client.post("/api/v1/cash/movements", headers=headers(), json=body)
    assert replay.status_code == 200 and replay.json()["replay"] is True, replay.text
    assert_blind(replay.json())
    with factory() as session:
        assert session.scalar(sa.select(sa.func.count()).select_from(models.cash_movements)) == 1


def test_failed_audit_returns_safe_error_and_no_effect(
    movement_world: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, factory, body = movement_world
    activate(factory)
    audit = ops._audit

    def fail(session: Session, action: str, *args: Any, **kwargs: Any) -> Any:
        if action == "cash_movement.receipt_read":
            raise sa.exc.SQLAlchemyError("PRIVATE-MOVEMENT-SQL")
        return audit(session, action, *args, **kwargs)

    monkeypatch.setattr(ops, "_audit", fail)
    result = client.post("/api/v1/cash/movements", headers=headers(), json=body)
    assert result.status_code == 503 and "PRIVATE-MOVEMENT" not in result.text
    with factory() as session:
        assert session.scalar(sa.select(sa.func.count()).select_from(models.cash_movements)) == 0


def test_active_movement_intent_executes_and_recovers_real_receipt(operational: Any) -> None:
    client, factory, auth = operational
    with factory() as session:
        for code in (
            "cash.movement.withdraw",
            "cash.concept.manage",
            "cash.concept.read",
            "cash.shift.read",
        ):
            _grant_permission(session, code)
        concept = ops.create_cash_concept(
            session, _concept_payload(), "f106-intent-concept", ADMIN_USER_ID
        )
    activate(factory)
    body = _movement_payload(concept["id"])
    key = "f106-movement-real-intent"
    intent = _prepare_command(client, auth, "cash.movement.create", body, key)
    command_headers = {**auth, "Idempotency-Key": key, "X-Operational-Intent": intent["id"]}
    result = client.post("/api/v1/cash/movements", headers=command_headers, json=body)
    assert result.status_code == 200, result.text
    assert_blind(result.json())
    replay = client.post("/api/v1/cash/movements", headers=command_headers, json=body)
    assert (
        replay.status_code == 200 and replay.json()["resource_id"] == result.json()["resource_id"]
    )
    assert_blind(replay.json())
    recovered = client.post(f"/api/v1/operational-intents/{intent['id']}/resolve", headers=auth)
    assert recovered.status_code == 200 and recovered.json()["state"] == "acknowledged"
    assert recovered.json()["resource_id"] == result.json()["resource_id"]


def test_active_policy_keeps_device_sync_ack_minimal_without_human_read_grant() -> None:
    from test_cash_ledger import _withdrawal_concept
    from test_pco008_cash_sync import DEVICE_ID, _envelope, _new_session, _valid_grant

    engine, session = _new_session()
    try:
        concept = _withdrawal_concept(session)
        envelope = _envelope(str(concept["id"]))
        activate(sessionmaker(bind=engine))
        first = ops.receive_sync_command(
            session,
            envelope,
            actor_device_id=DEVICE_ID,
            grant_verifier=_valid_grant,
        )
        replay = ops.receive_sync_command(
            session,
            envelope,
            actor_device_id=DEVICE_ID,
            grant_verifier=_valid_grant,
        )
        assert first["status"] == "CONFIRMED" and replay["replayed"] is True
        assert set(first) == {"status", "checkpoint", "replayed", "movement"}
        assert first["movement"] == replay["movement"]
        assert set(first["movement"]) == {"id", "status"}
        assert session.scalar(sa.select(sa.func.count()).select_from(models.cash_movements)) == 1
        # A technical transport receipt never grants the actor a human cash read.
        with pytest.raises(ops.AuthorizationError):
            ops.create_cash_movement(
                session,
                _movement_payload(str(concept["id"])),
                envelope["idempotency_key"],
                CASHIER_ID,
            )
    finally:
        session.close()
        engine.dispose()
