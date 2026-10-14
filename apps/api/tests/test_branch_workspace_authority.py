"""Durable workspace regressions with synthetic actors and two branches."""

import hashlib
from datetime import datetime, timezone

import pytest
import sqlalchemy as sa
from restaurant_os import models
from restaurant_os.config import get_settings
from restaurant_os.operations import ORGANIZATION_ID, update_role_permissions
from sqlalchemy.exc import IntegrityError
from test_branch_scope_selection import _grant_selection
from test_platform_api import (
    ADMIN_USER_ID,
    BRANCH_ID,
    _admin_headers,
    _branch_admin_fixture,
    _client_with_seeded_database,
    _login_headers,
    _test_session_factory,
)


@pytest.fixture
def workspace(monkeypatch):
    monkeypatch.setenv("RESTAURANTOS_BRANCH_SCOPE_V2_ENABLED", "true")
    get_settings.cache_clear()
    client = _client_with_seeded_database()
    fixture = _branch_admin_fixture(client)
    factory = _test_session_factory(client)
    with factory() as session:
        role_id = session.scalar(
            sa.select(models.user_roles.c.role_id).where(
                models.user_roles.c.user_id == fixture["supervisor_id"]
            )
        )
        _grant_selection(session, role_id, workspace=True)
    headers = _login_headers(client, "supervisor.norte@kiwi.local", "Temporal123+")
    yield client, fixture, factory, headers
    get_settings.cache_clear()


def _reissue(client, headers, context_id=None, key="workspace-initial-qa", version=1):
    return client.post(
        "/api/v1/auth/branch-context-reissues",
        headers={**headers, "Idempotency-Key": key},
        json={"context_id": context_id, "expected_authorization_version": version},
    )


def _select(client, headers, target, key="workspace-select-qa"):
    return client.post(
        "/api/v1/auth/branch-selections",
        headers={**headers, "Idempotency-Key": key},
        json={"target_branch_id": target, "expected_authorization_version": 1},
    )


def test_initial_issue_get_hydration_and_rotation_do_not_persist_secret(workspace):
    client, fixture, factory, headers = workspace
    initial = _reissue(client, headers)
    assert initial.status_code == 200, initial.text
    issued = initial.json()
    assert issued["active_branch"]["id"] == fixture["branch_id"]
    assert issued["branch_workspace_secret_version"] == 1
    secret = issued["branch_workspace_context"]
    assert len(secret) >= 32
    hydrated = client.get("/api/v1/auth/session", headers=headers).json()
    assert hydrated["branch_workspace_context"] is None
    assert hydrated["branch_context_reissue_required"] is True
    assert hydrated["branch_workspace_context_id"] == issued["branch_workspace_context_id"]
    replay = _reissue(client, headers).json()
    assert replay["branch_workspace_context_id"] == issued["branch_workspace_context_id"]
    assert replay["branch_workspace_secret_version"] == 2
    assert replay["branch_workspace_context"] != secret
    with factory() as session:
        row = session.execute(sa.select(models.branch_workspace_sessions)).mappings().one()
        assert (
            row["token_hash"]
            == hashlib.sha256(replay["branch_workspace_context"].encode()).hexdigest()
        )
        assert secret not in str(dict(row))
        assert secret not in str(
            session.execute(sa.select(models.branch_context_reissue_commands)).all()
        )


def test_selection_survives_get_and_replay_rotates_only_current_context(workspace):
    client, _, factory, headers = workspace
    initial = _reissue(client, headers)
    assert initial.status_code == 200, initial.text
    selected = _select(client, headers, BRANCH_ID)
    assert selected.status_code == 200, selected.text
    result = selected.json()
    hydrated = client.get("/api/v1/auth/session", headers=headers).json()
    assert hydrated["active_branch"]["id"] == BRANCH_ID
    assert hydrated["branch_workspace_context_id"] == result["branch_workspace_context_id"]
    assert hydrated["branch_workspace_context"] is None
    replay = _select(client, headers, BRANCH_ID).json()
    assert replay["branch_workspace_context_id"] == result["branch_workspace_context_id"]
    assert replay["branch_workspace_secret_version"] == 2
    with factory() as session:
        assert (
            session.scalar(
                sa.select(sa.func.count())
                .select_from(models.branch_workspace_sessions)
                .where(models.branch_workspace_sessions.c.state == "active")
            )
            == 1
        )


def test_old_selection_cannot_revive_after_switch_back(workspace):
    client, fixture, _, headers = workspace
    assert _reissue(client, headers).status_code == 200
    assert _select(client, headers, BRANCH_ID).status_code == 200
    assert (
        _select(client, headers, fixture["branch_id"], "workspace-switch-back").status_code == 200
    )
    replay = _select(client, headers, BRANCH_ID)
    assert replay.status_code == 409, replay.text
    assert replay.json()["detail"]["code"] == "idempotent_result_superseded"
    assert (
        client.get("/api/v1/auth/session", headers=headers).json()["active_branch"]["id"]
        == fixture["branch_id"]
    )


def test_each_selection_replay_audits_rotation_without_secret(workspace):
    client, fixture, factory, headers = workspace
    initial = _reissue(client, headers).json()
    selected = _select(client, headers, BRANCH_ID).json()
    replays = [_select(client, headers, BRANCH_ID).json() for _ in range(2)]
    assert [result["branch_workspace_secret_version"] for result in replays] == [2, 3]
    with factory() as session:
        command = session.execute(sa.select(models.branch_selection_commands)).mappings().one()
        audits = (
            session.execute(
                sa.select(models.audit_events).where(
                    models.audit_events.c.action == "auth.branch_context_reissued",
                    models.audit_events.c.entity_id == selected["branch_workspace_context_id"],
                )
            )
            .mappings()
            .all()
        )
        assert len(audits) == 2
        assert {audit["payload"]["secret_version"] for audit in audits} == {2, 3}
        for audit in audits:
            assert audit["actor_user_id"] == fixture["supervisor_id"]
            assert audit["branch_id"] == BRANCH_ID
            assert audit["payload"]["authorization_version"] == 1
            assert audit["payload"]["selection_command_id"] == command["id"]
            assert audit["payload"]["reason"] == "selection_replay"
        persisted = str(session.execute(sa.select(models.audit_events)).mappings().all())
        for result in [initial, selected, *replays]:
            assert result["branch_workspace_context"] not in persisted
        assert "workspace-select-qa" not in persisted


@pytest.mark.parametrize(
    "operation", ["selection", "selection_replay", "reissue", "reissue_replay"]
)
def test_workspace_command_owns_rollback_after_partial_audit(workspace, monkeypatch, operation):
    from restaurant_os import operations
    from restaurant_os.branch_workspaces import reissue_branch_context, select_branch_workspace

    client, fixture, factory, headers = workspace
    if operation != "reissue":
        assert _reissue(client, headers).status_code == 200
    if operation == "selection_replay":
        assert _select(client, headers, BRANCH_ID).status_code == 200
    tables = (
        models.branch_workspace_sessions,
        models.branch_selection_commands,
        models.branch_context_reissue_commands,
        models.audit_events,
    )

    def snapshot(session):
        return [
            [dict(row) for row in session.execute(sa.select(table).order_by(table.c.id)).mappings()]
            for table in tables
        ]

    with factory() as session:
        before = snapshot(session)
    original_audit = operations._audit

    def fail_after_audit(*args, **kwargs):
        original_audit(*args, **kwargs)
        raise RuntimeError("injected-partial-workspace-audit")

    monkeypatch.setattr(operations, "_audit", fail_after_audit)
    with factory() as session:
        with pytest.raises(RuntimeError, match="injected-partial-workspace-audit"):
            if operation.startswith("selection"):
                select_branch_workspace(
                    session,
                    fixture["supervisor_id"],
                    {"target_branch_id": BRANCH_ID, "expected_authorization_version": 1},
                    "workspace-select-qa"
                    if operation.endswith("replay")
                    else "workspace-new-selection",
                )
            else:
                reissue_branch_context(
                    session,
                    fixture["supervisor_id"],
                    {"context_id": None, "expected_authorization_version": 1},
                    "workspace-initial-qa",
                )
        assert not session.in_transaction()
        session.commit()
        assert snapshot(session) == before


def test_owner_without_home_must_select_instead_of_first_branch(workspace):
    from test_platform_api import ADMIN_ROLE_ID

    client, _, factory, _ = workspace
    with factory() as session:
        _grant_selection(session, ADMIN_ROLE_ID, workspace=False)
    profile = client.get("/api/v1/auth/session", headers=_admin_headers()).json()
    assert profile["scope"]["can_select_branch"] is True
    assert profile["active_branch"] is None
    assert profile["branch_selection_required"] is True
    rejected = _reissue(client, _admin_headers())
    assert rejected.status_code == 409, rejected.text
    assert rejected.json()["detail"]["code"] == "branch_selection_required"


def test_reissue_conflicting_payload_and_old_authority_are_denied(workspace):
    client, fixture, factory, headers = workspace
    issued = _reissue(client, headers).json()
    conflict = _reissue(client, headers, issued["branch_workspace_context_id"])
    assert conflict.status_code == 409, conflict.text
    assert conflict.json()["detail"]["code"] == "idempotency_conflict"
    with factory() as session:
        session.execute(
            models.users.update()
            .where(models.users.c.id == fixture["supervisor_id"])
            .values(authorization_version=2)
        )
        session.commit()
    stale = _reissue(
        client, headers, issued["branch_workspace_context_id"], "workspace-stale-authority"
    )
    assert stale.status_code == 409, stale.text
    assert stale.json()["detail"]["code"] == "authorization_version_conflict"


def test_rollout_disabled_rejects_new_selection(workspace, monkeypatch):
    client, _, _, headers = workspace
    monkeypatch.setenv("RESTAURANTOS_BRANCH_SCOPE_V2_ENABLED", "false")
    get_settings.cache_clear()
    rejected = _select(client, headers, BRANCH_ID)
    assert rejected.status_code == 409, rejected.text
    assert rejected.json()["detail"]["code"] == "branch_scope_v2_disabled"
    profile = client.get("/api/v1/auth/session", headers=headers)
    assert profile.status_code == 200, profile.text
    assert profile.json()["scope"]["can_select_branch"] is False


def test_authorization_schema_probe_preserves_pending_transaction(workspace):
    from restaurant_os.operations import _user_authorization_version

    _, fixture, factory, _ = workspace
    with factory() as session:
        session.execute(
            models.users.update()
            .where(models.users.c.id == fixture["supervisor_id"])
            .values(authorization_version=2)
        )
        assert _user_authorization_version(session, fixture["supervisor_id"]) == 2
        session.commit()
    with factory() as session:
        assert _user_authorization_version(session, fixture["supervisor_id"]) == 2


def test_cash_serialization_preserves_existing_workspace_fence_transaction(workspace):
    from restaurant_os.operations import (
        _begin_cash_shift_serialization,
        _user_authorization_version,
    )

    _, fixture, factory, _ = workspace
    with factory() as session:
        session.execute(sa.text("BEGIN IMMEDIATE"))
        session.execute(
            models.users.update()
            .where(models.users.c.id == fixture["supervisor_id"])
            .values(authorization_version=2)
        )
        _begin_cash_shift_serialization(session)
        assert (
            session.scalar(
                sa.select(models.users.c.authorization_version).where(
                    models.users.c.id == fixture["supervisor_id"]
                )
            )
            == 2
        )
        session.commit()
    with factory() as session:
        assert _user_authorization_version(session, fixture["supervisor_id"]) == 2


def test_permission_without_governed_grant_does_not_create_mobility(workspace):
    client, fixture, factory, headers = workspace
    with factory() as session:
        role_id = session.scalar(
            sa.select(models.user_roles.c.role_id).where(
                models.user_roles.c.user_id == fixture["supervisor_id"]
            )
        )
        session.execute(
            models.role_authority_grants.delete().where(
                models.role_authority_grants.c.role_id == role_id
            )
        )
        session.execute(
            models.roles.update().where(models.roles.c.id == role_id).values(scope="organization")
        )
        session.commit()
    profile = client.get("/api/v1/auth/session", headers=headers).json()
    assert "pos.branch.select" in profile["permissions"]
    assert profile["scope"]["can_select_branch"] is False
    denied = _select(client, headers, BRANCH_ID)
    assert denied.status_code == 403, denied.text
    assert denied.json()["detail"]["code"] == "permission_denied"


def test_unique_operational_workspace_includes_recovery_state(workspace):
    client, _, factory, headers = workspace
    issued = _reissue(client, headers)
    assert issued.status_code == 200, issued.text
    with factory() as session:
        row = dict(session.execute(sa.select(models.branch_workspace_sessions)).mappings().one())
        row.update(id="018f6f73-2d0a-74f0-8f1c-000000009999", state="recovery_only")
        with pytest.raises(IntegrityError):
            session.execute(models.branch_workspace_sessions.insert().values(**row))
        session.rollback()
        assert (
            session.scalar(sa.select(sa.func.count()).select_from(models.branch_workspace_sessions))
            == 1
        )


def test_fence_rejects_old_secret_other_branch_and_new_version(workspace):
    from restaurant_os.branch_workspaces import validate_branch_context
    from restaurant_os.operations import AuthorizationError

    client, fixture, factory, headers = workspace
    old = _reissue(client, headers).json()
    new = _select(client, headers, BRANCH_ID).json()
    with factory() as session:
        with pytest.raises(AuthorizationError) as rejected:
            validate_branch_context(
                session,
                fixture["supervisor_id"],
                fixture["branch_id"],
                old["branch_workspace_context"],
            )
        assert rejected.value.code == "branch_context_superseded"
    with factory() as session:
        with pytest.raises(AuthorizationError) as rejected:
            validate_branch_context(
                session,
                fixture["supervisor_id"],
                fixture["branch_id"],
                new["branch_workspace_context"],
            )
        assert rejected.value.code == "branch_context_mismatch"
    with factory() as session:
        assert (
            validate_branch_context(
                session, fixture["supervisor_id"], BRANCH_ID, new["branch_workspace_context"]
            )["id"]
            == new["branch_workspace_context_id"]
        )
        session.execute(
            models.users.update()
            .where(models.users.c.id == fixture["supervisor_id"])
            .values(authorization_version=2)
        )
        session.commit()
    with factory() as session:
        with pytest.raises(AuthorizationError) as rejected:
            validate_branch_context(
                session, fixture["supervisor_id"], BRANCH_ID, new["branch_workspace_context"]
            )
        assert rejected.value.code == "authorization_version_conflict"


def test_late_audit_failure_rolls_back_selection_and_secret(workspace, monkeypatch):
    from restaurant_os import operations
    from restaurant_os.branch_workspaces import select_branch_workspace

    client, fixture, factory, headers = workspace
    initial = _reissue(client, headers).json()

    def fail_audit(*args, **kwargs):
        raise RuntimeError("injected-audit-failure")

    monkeypatch.setattr(operations, "_audit", fail_audit)
    with factory() as session:
        with pytest.raises(RuntimeError, match="injected"):
            select_branch_workspace(
                session,
                fixture["supervisor_id"],
                {
                    "target_branch_id": BRANCH_ID,
                    "expected_authorization_version": 1,
                },
                "workspace-rollback-injected",
            )
        assert not session.in_transaction()
        session.commit()
    with factory() as session:
        row = session.execute(sa.select(models.branch_workspace_sessions)).mappings().one()
        assert row["id"] == initial["branch_workspace_context_id"]
        assert row["state"] == "active"
        assert (
            row["token_hash"]
            == hashlib.sha256(initial["branch_workspace_context"].encode()).hexdigest()
        )
        assert (
            session.scalar(sa.select(sa.func.count()).select_from(models.branch_selection_commands))
            == 0
        )


def test_initial_reissue_cannot_switch_after_authority_change_with_open_shift(workspace):
    client, fixture, factory, headers = workspace
    assert _reissue(client, headers).status_code == 200
    selected = _select(client, headers, BRANCH_ID)
    assert selected.status_code == 200, selected.text
    selected_id = selected.json()["branch_workspace_context_id"]
    with factory() as session:
        now = datetime(2026, 10, 10, tzinfo=timezone.utc)
        session.execute(
            models.cash_shifts.insert().values(
                id="018f6f73-2d0a-74f0-8f1c-000000009876",
                organization_id=ORGANIZATION_ID,
                branch_id=BRANCH_ID,
                register_code="SOL-SWITCH",
                status="OPEN",
                opening_cash_cents=0,
                cashier_user_id=fixture["supervisor_id"],
                opened_at=now,
                closed_at=None,
                created_at=now,
            )
        )
        session.commit()
        role_id = session.scalar(
            sa.select(models.user_roles.c.role_id).where(
                models.user_roles.c.user_id == fixture["supervisor_id"]
            )
        )
        permissions = list(
            session.scalars(
                sa.select(models.role_permissions.c.permission_id).where(
                    models.role_permissions.c.role_id == role_id
                )
            )
        )
        extra = session.scalar(
            sa.select(models.permissions.c.id).where(models.permissions.c.id.not_in(permissions))
        )
        update_role_permissions(session, role_id, permissions + [extra], ADMIN_USER_ID)
        assert (
            session.scalar(
                sa.select(models.users.c.authorization_version).where(
                    models.users.c.id == fixture["supervisor_id"]
                )
            )
            == 2
        )
    rejected_selection = client.post(
        "/api/v1/auth/branch-selections",
        headers={
            **headers,
            "Idempotency-Key": "sol-explicit-switch-blocked",
        },
        json={"target_branch_id": fixture["branch_id"], "expected_authorization_version": 2},
    )
    assert rejected_selection.status_code == 409, rejected_selection.text
    assert rejected_selection.json()["detail"]["code"] == "branch_switch_open_shift"
    refreshed = _reissue(client, headers, key="sol-after-authority-refresh", version=2)
    assert refreshed.status_code == 409, refreshed.text
    assert refreshed.json()["detail"]["code"] == "branch_switch_open_shift"
    with factory() as session:
        live = (
            session.execute(
                sa.select(models.branch_workspace_sessions).where(
                    models.branch_workspace_sessions.c.state == "active"
                )
            )
            .mappings()
            .one()
        )
        assert live["id"] == selected_id
        assert live["branch_id"] == BRANCH_ID
        assert (
            session.scalar(
                sa.select(sa.func.count()).select_from(models.branch_context_reissue_commands)
            )
            == 1
        )


@pytest.mark.parametrize("path", ["/cash-shifts/open", "/cash/shifts/open"])
def test_direct_cash_open_cannot_bypass_blocked_branch_selection(workspace, path):
    client, fixture, factory, headers = workspace
    initial = _reissue(client, headers).json()
    operational_headers = {**headers, "X-Branch-Context": initial["branch_workspace_context"]}
    opened = client.post(
        "/api/v1" + path,
        headers={
            **operational_headers,
            "Idempotency-Key": "workspace-open-branch-a",
        },
        json={
            "branch_id": fixture["branch_id"],
            "register_id": "QA-WORKSPACE",
            "opening_cash_cents": 0,
        },
    )
    assert opened.status_code == 200, opened.text
    blocked = _select(client, headers, BRANCH_ID)
    assert blocked.status_code == 409, blocked.text
    assert blocked.json()["detail"]["code"] == "branch_switch_open_shift"
    bypass = client.post(
        "/api/v1" + path,
        headers={
            **operational_headers,
            "Idempotency-Key": "workspace-direct-bypass-b",
        },
        json={"branch_id": BRANCH_ID, "register_id": "QA-WORKSPACE", "opening_cash_cents": 0},
    )
    assert bypass.status_code == 403, bypass.text
    assert bypass.json()["detail"]["code"] == "branch_context_mismatch"
    with factory() as session:
        shifts = (
            session.execute(
                sa.select(models.cash_shifts).where(
                    models.cash_shifts.c.cashier_user_id == fixture["supervisor_id"]
                )
            )
            .mappings()
            .all()
        )
        assert len(shifts) == 1
        assert shifts[0]["branch_id"] == fixture["branch_id"]
        assert shifts[0]["status"].upper() == "OPEN"


@pytest.mark.parametrize("path", ["/cash-shifts/open", "/cash/shifts/open"])
def test_cash_open_requires_current_workspace_secret(workspace, path):
    client, fixture, factory, headers = workspace
    initial = _reissue(client, headers).json()
    body = {
        "branch_id": fixture["branch_id"],
        "register_id": "QA-WORKSPACE",
        "opening_cash_cents": 0,
    }
    missing = client.post(
        "/api/v1" + path,
        headers={
            **headers,
            "Idempotency-Key": "workspace-open-missing-context",
        },
        json=body,
    )
    assert missing.status_code == 403, missing.text
    assert missing.json()["detail"]["code"] == "branch_context_required"
    fresh = _reissue(
        client, headers, initial["branch_workspace_context_id"], "workspace-rotate-before-open"
    ).json()
    stale = client.post(
        "/api/v1" + path,
        headers={
            **headers,
            "Idempotency-Key": "workspace-open-stale-context",
            "X-Branch-Context": initial["branch_workspace_context"],
        },
        json=body,
    )
    assert stale.status_code == 403, stale.text
    assert stale.json()["detail"]["code"] == "branch_context_superseded"
    valid = client.post(
        "/api/v1" + path,
        headers={
            **headers,
            "Idempotency-Key": "workspace-open-valid-context",
            "X-Branch-Context": fresh["branch_workspace_context"],
        },
        json=body,
    )
    assert valid.status_code == 200, valid.text
    with factory() as session:
        assert session.scalar(sa.select(sa.func.count()).select_from(models.cash_shifts)) == 1


@pytest.mark.parametrize("path", ["/cash-shifts/open", "/cash/shifts/open"])
def test_cash_fence_invalid_branch_denial_keeps_nullable_audit_and_no_effect(workspace, path):
    client, _, factory, headers = workspace
    issued = _reissue(client, headers).json()
    with factory().get_bind().connect() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")
        assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar() == 1
    response = client.post(
        "/api/v1" + path,
        headers={
            **headers,
            "Idempotency-Key": "workspace-invalid-branch-audit",
            "X-Branch-Context": issued["branch_workspace_context"],
        },
        json={
            "branch_id": "018f6f73-2d0a-74f0-8f1c-000000099999",
            "register_id": "QA-FENCE",
            "opening_cash_cents": 0,
        },
    )
    assert response.status_code == 403, response.text
    assert response.json()["detail"]["code"] == "branch_context_mismatch"
    with factory() as session:
        assert session.scalar(sa.select(sa.func.count()).select_from(models.cash_shifts)) == 0
        audit = (
            session.execute(
                sa.select(models.audit_events).where(
                    models.audit_events.c.entity_id == "branch.workspace"
                )
            )
            .mappings()
            .one()
        )
        assert audit["payload"]["reason"] == "branch_context_mismatch"
        assert audit["branch_id"] is None
        assert issued["branch_workspace_context"] not in str(dict(audit))


def test_workspace_denial_missing_actor_keeps_nullable_audit_actor(workspace):
    from restaurant_os.api import _require_operational_workspace
    from restaurant_os.operations import AuthorizationError

    _, fixture, factory, _ = workspace
    with factory().get_bind().connect() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")
    with factory() as session:
        with pytest.raises(AuthorizationError) as rejected:
            _require_operational_workspace(
                session, "018f6f73-2d0a-74f0-8f1c-000000099999", fixture["branch_id"], None
            )
        assert rejected.value.code == "actor_not_authorized"
        audit = (
            session.execute(
                sa.select(models.audit_events).where(
                    models.audit_events.c.entity_id == "branch.workspace"
                )
            )
            .mappings()
            .one()
        )
        assert audit["actor_user_id"] is None
        assert audit["branch_id"] == fixture["branch_id"]
        assert audit["payload"]["reason"] == "actor_not_authorized"
