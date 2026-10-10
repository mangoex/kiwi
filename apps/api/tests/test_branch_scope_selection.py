"""Focused BRANCH-SCOPE-001 selection and POS module-visibility regressions."""

from datetime import datetime, timezone
from uuid import NAMESPACE_URL, uuid5

import sqlalchemy as sa
from restaurant_os import models
from restaurant_os.operations import ORGANIZATION_ID
from test_platform_api import (
    ADMIN_ROLE_ID,
    ADMIN_USER_ID,
    BRANCH_ID,
    _admin_headers,
    _branch_admin_fixture,
    _client_with_seeded_database,
    _login_headers,
    _test_session_factory,
)

SELECT_PERMISSION_ID = str(uuid5(NAMESPACE_URL, "restaurantos:permission:pos.branch.select"))


def _grant_selection(session, role_id: str, *, workspace: bool) -> None:
    if not session.execute(
        sa.select(models.permissions.c.id).where(
            models.permissions.c.code == "pos.branch.select"
        )
    ).scalar_one_or_none():
        session.execute(
            models.permissions.insert().values(
                id=SELECT_PERMISSION_ID,
                code="pos.branch.select",
                description="Seleccionar una sucursal autorizada en POS.",
                created_at=datetime(2026, 10, 10, tzinfo=timezone.utc),
            )
        )
    session.execute(
        models.role_permissions.insert().values(
            role_id=role_id, permission_id=SELECT_PERMISSION_ID
        )
    )
    if workspace:
        session.execute(
            models.role_authority_grants.insert().values(
                role_id=role_id,
                authority_kind="organization_branch_workspaces",
                created_at=datetime(2026, 10, 10, tzinfo=timezone.utc),
            )
        )
    session.commit()


def test_corporate_administrator_selects_branch_through_explicit_command() -> None:
    client = _client_with_seeded_database()
    fixture = _branch_admin_fixture(client)
    with _test_session_factory(client)() as session:
        _grant_selection(session, ADMIN_ROLE_ID, workspace=False)

    profile = client.get("/api/v1/auth/session", headers=_admin_headers()).json()
    assert profile["scope"]["can_select_branch"] is True
    assert profile["scope"]["authorization_version"] == 1
    assert set(profile["scope"]["allowed_branch_ids"]) == {BRANCH_ID, fixture["branch_id"]}

    selected = client.post(
        "/api/v1/auth/branch-selections",
        headers={**_admin_headers(), "Idempotency-Key": "branch-select-admin-norte"},
        json={
            "current_branch_id": BRANCH_ID,
            "target_branch_id": fixture["branch_id"],
            "expected_authorization_version": 1,
        },
    )
    assert selected.status_code == 200, selected.text
    assert selected.json()["active_branch"]["id"] == fixture["branch_id"]

    replay = client.post(
        "/api/v1/auth/branch-selections",
        headers={**_admin_headers(), "Idempotency-Key": "branch-select-admin-norte"},
        json={
            "current_branch_id": BRANCH_ID,
            "target_branch_id": fixture["branch_id"],
            "expected_authorization_version": 1,
        },
    )
    assert replay.status_code == 200, replay.text
    assert replay.json()["active_branch"]["id"] == fixture["branch_id"]
    conflict = client.post(
        "/api/v1/auth/branch-selections",
        headers={**_admin_headers(), "Idempotency-Key": "branch-select-admin-norte"},
        json={
            "current_branch_id": fixture["branch_id"],
            "target_branch_id": BRANCH_ID,
            "expected_authorization_version": 1,
        },
    )
    assert conflict.status_code == 409, conflict.text
    assert conflict.json()["detail"]["code"] == "idempotency_conflict"
    with _test_session_factory(client)() as session:
        assert session.execute(
            sa.select(sa.func.count()).select_from(models.branch_selection_commands)
        ).scalar_one() == 1
        assert session.execute(
            sa.select(sa.func.count()).select_from(models.audit_events).where(
                models.audit_events.c.action == "auth.branch_selected"
            )
        ).scalar_one() == 1


def test_branch_supervisor_needs_persisted_workspace_grant_to_select() -> None:
    client = _client_with_seeded_database()
    fixture = _branch_admin_fixture(client)
    with _test_session_factory(client)() as session:
        role_id = session.execute(
            sa.select(models.user_roles.c.role_id).where(
                models.user_roles.c.user_id == fixture["supervisor_id"]
            )
        ).scalar_one()
        _grant_selection(session, str(role_id), workspace=True)

    headers = _login_headers(client, "supervisor.norte@kiwi.local", "Temporal123+")
    profile = client.get("/api/v1/auth/session", headers=headers).json()
    assert profile["scope"]["can_select_branch"] is True
    assert profile["scope"]["level"] == "branch"
    assert profile["scope"]["home_branch_id"] == fixture["branch_id"]
    assert set(profile["scope"]["allowed_branch_ids"]) == {BRANCH_ID, fixture["branch_id"]}

    legacy_get = client.get(
        "/api/v1/auth/session",
        params={"branch_id": BRANCH_ID},
        headers=headers,
    )
    assert legacy_get.status_code == 409, legacy_get.text
    assert legacy_get.json()["detail"]["code"] == "branch_selection_requires_command"

    selected = client.post(
        "/api/v1/auth/branch-selections",
        headers={**headers, "Idempotency-Key": "branch-select-supervisor-piloto"},
        json={
            "current_branch_id": fixture["branch_id"],
            "target_branch_id": BRANCH_ID,
            "expected_authorization_version": 1,
        },
    )
    assert selected.status_code == 200, selected.text
    assert selected.json()["active_branch"]["id"] == BRANCH_ID


def test_fixed_branch_profile_cannot_select_another_branch() -> None:
    client = _client_with_seeded_database()
    fixture = _branch_admin_fixture(client)
    headers = _login_headers(client, "supervisor.norte@kiwi.local", "Temporal123+")

    profile = client.get("/api/v1/auth/session", headers=headers).json()
    assert profile["scope"]["can_select_branch"] is False
    assert profile["scope"]["allowed_branch_ids"] == [fixture["branch_id"]]
    denied = client.post(
        "/api/v1/auth/branch-selections",
        headers={**headers, "Idempotency-Key": "branch-select-fixed-supervisor"},
        json={
            "current_branch_id": fixture["branch_id"],
            "target_branch_id": BRANCH_ID,
            "expected_authorization_version": 1,
        },
    )
    assert denied.status_code == 403, denied.text
    assert denied.json()["detail"]["code"] == "permission_denied"
    with _test_session_factory(client)() as session:
        assert session.execute(
            sa.select(sa.func.count()).select_from(models.branch_selection_commands)
        ).scalar_one() == 0


def test_open_shift_blocks_branch_selection_without_changing_context() -> None:
    client = _client_with_seeded_database()
    fixture = _branch_admin_fixture(client)
    with _test_session_factory(client)() as session:
        _grant_selection(session, ADMIN_ROLE_ID, workspace=False)
        session.execute(
            models.cash_shifts.insert().values(
                id="018f6f73-2d0a-74f0-8f1c-000000009977",
                organization_id=ORGANIZATION_ID,
                branch_id=BRANCH_ID,
                register_code="QA-SWITCH",
                status="OPEN",
                opening_cash_cents=0,
                cashier_user_id=ADMIN_USER_ID,
                opened_at=datetime(2026, 10, 10, tzinfo=timezone.utc),
                closed_at=None,
                created_at=datetime(2026, 10, 10, tzinfo=timezone.utc),
            )
        )
        session.commit()

    blocked = client.post(
        "/api/v1/auth/branch-selections",
        headers={**_admin_headers(), "Idempotency-Key": "branch-select-open-shift"},
        json={
            "current_branch_id": BRANCH_ID,
            "target_branch_id": fixture["branch_id"],
            "expected_authorization_version": 1,
        },
    )
    assert blocked.status_code == 409, blocked.text
    assert blocked.json()["detail"]["code"] == "branch_switch_open_shift"
    with _test_session_factory(client)() as session:
        assert session.execute(
            sa.select(sa.func.count()).select_from(models.branch_selection_commands)
        ).scalar_one() == 0


def test_session_hides_unconfigured_pos_modules_and_requires_branch_mapping() -> None:
    client = _client_with_seeded_database()
    now = datetime(2026, 10, 10, tzinfo=timezone.utc)
    with _test_session_factory(client)() as session:
        session.execute(
            models.channel_integrations.insert().values(
                id="018f6f73-2d0a-74f0-8f1c-000000009971",
                organization_id=ORGANIZATION_ID,
                provider="RAPPI",
                is_enabled=True,
                environment="sandbox",
                client_id=None,
                client_secret=None,
                webhook_secret=None,
                auto_accept=True,
                default_prep_time_minutes=20,
                created_at=now,
                updated_at=now,
            )
        )
        session.execute(
            models.channel_store_mappings.insert().values(
                id="018f6f73-2d0a-74f0-8f1c-000000009972",
                organization_id=ORGANIZATION_ID,
                branch_id=BRANCH_ID,
                provider="RAPPI",
                external_store_id="rappi-qa",
                is_active=True,
                created_at=now,
                updated_at=now,
            )
        )
        session.commit()

    modules = client.get("/api/v1/auth/session", headers=_admin_headers()).json()["pos_modules"]
    assert modules == {
        "uber_eats": False,
        "didi_food": False,
        "rappi": True,
        "invoicing": False,
    }
