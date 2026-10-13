# SEC001-SYNTHETIC-FIXTURE provenance=restaurantos-audit-test-branch-workspace-route-guard-v1
"""Human operational guards share the durable workspace; devices stay independent."""

from datetime import datetime, timezone

import pytest
import sqlalchemy as sa
import test_branch_workspace_authority as workspace_specs
from restaurant_os import api, models
from restaurant_os.auth import create_session_token
from restaurant_os.config import get_settings
from restaurant_os.operations import update_role_permissions
from test_branch_workspace_authority import _reissue, _select
from test_platform_api import ADMIN_USER_ID, BRANCH_ID

workspace = workspace_specs.workspace


@pytest.fixture
def routed_workspace(workspace, monkeypatch):
    client, fixture, factory, headers = workspace
    with factory() as session:
        role = session.scalar(
            sa.select(models.user_roles.c.role_id).where(
                models.user_roles.c.user_id == fixture["supervisor_id"]
            )
        )
        for code in (
            "kds.tasks.operate",
            "print.jobs.read",
            "print.jobs.retry",
            "sync.events.read",
        ):
            permission = session.scalar(
                sa.select(models.permissions.c.id).where(models.permissions.c.code == code)
            )
            if permission is None:
                permission = "workspace-route-" + code
                session.execute(
                    models.permissions.insert().values(
                        id=permission,
                        code=code,
                        description="Synthetic " + code,
                        created_at=datetime.now(timezone.utc),
                    )
                )
            if not session.scalar(
                sa.select(models.role_permissions.c.permission_id).where(
                    models.role_permissions.c.role_id == role,
                    models.role_permissions.c.permission_id == permission,
                )
            ):
                session.execute(
                    models.role_permissions.insert().values(role_id=role, permission_id=permission)
                )
        session.commit()
    calls = []

    def read_branch(session, branch):
        calls.append(branch)
        return [{"scope": branch}]

    monkeypatch.setattr(api, "list_kds_tasks", read_branch)
    monkeypatch.setattr(api, "list_print_jobs", read_branch)
    monkeypatch.setattr(
        api,
        "list_sync_events",
        lambda session, organization, branch, checkpoint: read_branch(session, branch),
    )
    monkeypatch.setattr(
        api,
        "get_sync_status",
        lambda session, organization, branch: read_branch(session, branch)[0],
    )
    return client, fixture, factory, headers, calls


@pytest.mark.parametrize("path", ["/kds/tasks", "/print-jobs", "/sync/events", "/sync/status"])
def test_human_operational_reads_require_context_and_follow_persisted_selection(
    routed_workspace, path
):
    client, fixture, _, headers, calls = routed_workspace
    issued = _reissue(client, headers).json()
    missing = client.get(
        "/api/v1" + path, headers=headers, params={"branch_id": fixture["branch_id"]}
    )
    assert missing.status_code == 403, missing.text
    assert missing.json()["detail"]["code"] == "branch_context_required"
    crossed = client.get(
        "/api/v1" + path,
        headers={**headers, "X-Branch-Context": issued["branch_workspace_context"]},
        params={"branch_id": BRANCH_ID},
    )
    assert crossed.status_code == 403, crossed.text
    assert crossed.json()["detail"]["code"] == "branch_context_mismatch"
    assert calls == []
    selected = _select(client, headers, BRANCH_ID).json()
    stale = client.get(
        "/api/v1" + path,
        headers={**headers, "X-Branch-Context": issued["branch_workspace_context"]},
    )
    assert stale.status_code == 403, stale.text
    assert stale.json()["detail"]["code"] == "branch_context_superseded"
    current = client.get(
        "/api/v1" + path,
        headers={**headers, "X-Branch-Context": selected["branch_workspace_context"]},
    )
    assert current.status_code == 200, current.text
    assert calls == [BRANCH_ID], (
        "Omitted query branch resolves selected workspace, never home branch"
    )


@pytest.mark.parametrize("kind", ["kds", "print"])
def test_human_operational_commands_fence_before_domain_and_preserve_canonical_branch(
    routed_workspace, monkeypatch, kind
):
    client, fixture, _, headers, calls = routed_workspace
    issued = _reissue(client, headers).json()

    def command(session, resource, action, branch, **actors):
        calls.append((resource, branch, actors["actor_user_id"]))
        return {"id": resource, "branch_id": branch}

    monkeypatch.setattr(api, "advance_kds_task", command)
    monkeypatch.setattr(api, "retry_print_job", command)

    def post(context, branch):
        route = "/kds/tasks/task-qa/transition" if kind == "kds" else "/print-jobs/job-qa/retry"
        kwargs = (
            {"json": {"status": "IN_PROGRESS", **({"branch_id": branch} if branch else {})}}
            if kind == "kds"
            else {"params": {"branch_id": branch} if branch else {}}
        )
        return client.post(
            "/api/v1" + route,
            headers={
                **headers,
                "Idempotency-Key": "workspace-command-qa",
                **({"X-Branch-Context": context} if context else {}),
            },
            **kwargs,
        )

    missing = post(None, fixture["branch_id"])
    assert missing.status_code == 403, missing.text
    assert missing.json()["detail"]["code"] == "branch_context_required"
    crossed = post(issued["branch_workspace_context"], BRANCH_ID)
    assert crossed.status_code == 403, crossed.text
    assert crossed.json()["detail"]["code"] == "branch_context_mismatch"
    assert calls == []
    selected = _select(client, headers, BRANCH_ID).json()
    stale = post(issued["branch_workspace_context"], None)
    assert stale.status_code == 403, stale.text
    assert stale.json()["detail"]["code"] == "branch_context_superseded"
    current = post(selected["branch_workspace_context"], None)
    assert current.status_code == 200, current.text
    assert len(calls) == 1
    assert calls[0][1:] == (BRANCH_ID, fixture["supervisor_id"])


@pytest.mark.parametrize("invalid", ["branch", "actor"])
def test_human_route_denial_with_unknown_ids_is_audited_without_foreign_key_failure(
    routed_workspace, invalid
):
    client, fixture, factory, headers, calls = routed_workspace
    issued = _reissue(client, headers).json()
    unknown = "018f6f73-2d0a-74f0-8f1c-000000099999"
    with factory().get_bind().connect() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")
        assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar() == 1
    if invalid == "actor":
        headers = {
            "Authorization": "Bearer "
            + create_session_token({"sub": unknown}, get_settings().secret_key)
        }
    branch = unknown if invalid == "branch" else fixture["branch_id"]
    response = client.get(
        "/api/v1/kds/tasks",
        params={"branch_id": branch},
        headers={
            **headers,
            "X-Branch-Context": issued["branch_workspace_context"],
        },
    )
    assert response.status_code == 403, response.text
    code = "branch_context_mismatch" if invalid == "branch" else "actor_not_authorized"
    assert response.json()["detail"]["code"] == code
    assert calls == []
    with factory() as session:
        audit = (
            session.execute(
                sa.select(models.audit_events).where(
                    models.audit_events.c.action == "operational_route.denied"
                )
            )
            .mappings()
            .one()
        )
        assert audit["payload"]["code"] == code
        assert audit["branch_id"] == (None if invalid == "branch" else branch)
        assert audit["actor_user_id"] == (None if invalid == "actor" else fixture["supervisor_id"])
        assert issued["branch_workspace_context"] not in str(dict(audit))


def test_human_route_context_does_not_replace_permission_or_authorization_version(routed_workspace):
    client, fixture, factory, headers, calls = routed_workspace
    issued = _reissue(client, headers).json()
    with factory() as session:
        role = session.scalar(
            sa.select(models.user_roles.c.role_id).where(
                models.user_roles.c.user_id == fixture["supervisor_id"]
            )
        )
        permission_ids = list(
            session.scalars(
                sa.select(models.role_permissions.c.permission_id)
                .join(
                    models.permissions,
                    models.permissions.c.id == models.role_permissions.c.permission_id,
                )
                .where(
                    models.role_permissions.c.role_id == role,
                    models.permissions.c.code != "kds.tasks.operate",
                )
            )
        )
        update_role_permissions(session, role, permission_ids, actor_user_id=ADMIN_USER_ID)
    stale = client.get(
        "/api/v1/kds/tasks",
        headers={
            **headers,
            "X-Branch-Context": issued["branch_workspace_context"],
        },
    )
    assert stale.status_code == 403, stale.text
    assert stale.json()["detail"]["code"] == "authorization_version_conflict"
    fresh = _reissue(client, headers, key="workspace-after-permission-qa", version=2).json()
    denied = client.get(
        "/api/v1/kds/tasks",
        headers={
            **headers,
            "X-Branch-Context": fresh["branch_workspace_context"],
        },
    )
    assert denied.status_code == 401, denied.text
    assert denied.json()["detail"]["code"] == "operational_route_denied"
    assert calls == []


@pytest.mark.parametrize(
    "capability,route",
    [
        ("kds.operate", "/kds/tasks"),
        ("gateway.sync", "/sync/events"),
    ],
)
def test_device_route_keeps_persisted_scope_with_mobility_enabled(
    routed_workspace, capability, route
):
    from test_sec001_operational_boundary import _device_credential

    client, _, factory, _, calls = routed_workspace
    with factory() as session:
        _device_credential(
            session,
            device_id="workspace-device-qa",
            token="synthetic-device-qa",
            capability=capability,
            organization_id="org-device-qa",
            branch_id="branch-device-qa",
        )
    response = client.get(
        "/api/v1" + route,
        params={"branch_id": BRANCH_ID},
        headers={
            "X-Device-Token": "synthetic-device-qa",
            "X-Branch-Context": "ignored-human-context",
        },
    )
    assert response.status_code == 200, response.text
    assert calls == ["branch-device-qa"]
