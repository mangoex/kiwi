# SEC001-SYNTHETIC-FIXTURE provenance=restaurantos-audit-test-branch-authority-remediation-v1
"""H14 authority mutation regressions; no workspace completeness claim."""

import pytest
import sqlalchemy as sa
from restaurant_os import models
from restaurant_os.operations import (
    BusinessError,
    assign_user_role,
    delete_role,
    delete_user,
    select_pos_branch,
    update_role,
    update_role_permissions,
    update_user,
)
from test_branch_scope_selection import _grant_selection
from test_platform_api import (
    ADMIN_ROLE_ID,
    ADMIN_USER_ID,
    _branch_admin_fixture,
    _client_with_seeded_database,
    _test_session_factory,
)


def _setup():
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
    return factory, fixture, role_id


def test_workspace_grant_role_scope_cannot_be_promoted():
    factory, fixture, role_id = _setup()
    with factory() as session:
        with pytest.raises(BusinessError, match="scope"):
            update_role(session, role_id, scope="organization", actor_user_id=ADMIN_USER_ID)
        assert (
            session.scalar(sa.select(models.roles.c.scope).where(models.roles.c.id == role_id))
            == "branch"
        )
        assert (
            session.scalar(
                sa.select(models.users.c.authorization_version).where(
                    models.users.c.id == fixture["supervisor_id"]
                )
            )
            == 1
        )


def test_unassigned_workspace_role_cannot_be_deleted():
    factory, _, role_id = _setup()
    with factory() as session:
        session.execute(models.user_roles.delete().where(models.user_roles.c.role_id == role_id))
        session.commit()
        with pytest.raises(BusinessError, match="deleted"):
            delete_role(session, role_id, ADMIN_USER_ID)
        assert (
            session.scalar(
                sa.select(models.role_authority_grants.c.role_id).where(
                    models.role_authority_grants.c.role_id == role_id
                )
            )
            == role_id
        )


def test_permission_change_versions_only_assigned_users_and_ignores_noop():
    factory, fixture, role_id = _setup()
    with factory() as session:
        ids = list(
            session.scalars(
                sa.select(models.role_permissions.c.permission_id).where(
                    models.role_permissions.c.role_id == role_id
                )
            )
        )
        extra = session.scalar(
            sa.select(models.permissions.c.id).where(models.permissions.c.id.not_in(ids))
        )
        changed = ids + [extra]
        update_role_permissions(session, role_id, changed, ADMIN_USER_ID)
        assert (
            session.scalar(
                sa.select(models.users.c.authorization_version).where(
                    models.users.c.id == fixture["supervisor_id"]
                )
            )
            == 2
        )
        assert (
            session.scalar(
                sa.select(models.users.c.authorization_version).where(
                    models.users.c.id == ADMIN_USER_ID
                )
            )
            == 1
        )
        update_role_permissions(session, role_id, list(reversed(changed)), ADMIN_USER_ID)
        update_role(session, role_id, name="Perfil renombrado", actor_user_id=ADMIN_USER_ID)
        assert (
            session.scalar(
                sa.select(models.users.c.authorization_version).where(
                    models.users.c.id == fixture["supervisor_id"]
                )
            )
            == 2
        )


def test_new_assignment_and_suspension_increment_authority_version():
    factory, fixture, _ = _setup()
    with factory() as session:
        assign_user_role(
            session, fixture["supervisor_id"], ADMIN_ROLE_ID, actor_user_id=ADMIN_USER_ID
        )
        assert (
            session.scalar(
                sa.select(models.users.c.authorization_version).where(
                    models.users.c.id == fixture["supervisor_id"]
                )
            )
            == 2
        )
        assign_user_role(
            session, fixture["supervisor_id"], ADMIN_ROLE_ID, actor_user_id=ADMIN_USER_ID
        )
        assert (
            session.scalar(
                sa.select(models.users.c.authorization_version).where(
                    models.users.c.id == fixture["supervisor_id"]
                )
            )
            == 2
        )
        delete_user(session, fixture["supervisor_id"], ADMIN_USER_ID)
        assert (
            session.scalar(
                sa.select(models.users.c.authorization_version).where(
                    models.users.c.id == fixture["supervisor_id"]
                )
            )
            == 3
        )


def test_combined_password_and_role_change_versions_once():
    factory, fixture, _ = _setup()
    with factory() as session:
        update_user(
            session,
            fixture["supervisor_id"],
            actor_user_id=ADMIN_USER_ID,
            role_id=ADMIN_ROLE_ID,
            password="NewSyntheticPassword123+",
        )
        assert (
            session.scalar(
                sa.select(models.users.c.authorization_version).where(
                    models.users.c.id == fixture["supervisor_id"]
                )
            )
            == 2
        )


def test_old_selection_version_is_rejected_after_permission_change(monkeypatch):
    from restaurant_os.config import get_settings

    monkeypatch.setenv("RESTAURANTOS_BRANCH_SCOPE_V2_ENABLED", "true")
    get_settings.cache_clear()
    factory, fixture, role_id = _setup()
    with factory() as session:
        ids = list(
            session.scalars(
                sa.select(models.role_permissions.c.permission_id).where(
                    models.role_permissions.c.role_id == role_id
                )
            )
        )
        extra = session.scalar(
            sa.select(models.permissions.c.id).where(models.permissions.c.id.not_in(ids))
        )
        update_role_permissions(session, role_id, ids + [extra], ADMIN_USER_ID)
        with pytest.raises(BusinessError) as rejected:
            select_pos_branch(
                session,
                fixture["supervisor_id"],
                {
                    "current_branch_id": fixture["branch_id"],
                    "target_branch_id": fixture["branch_id"],
                    "expected_authorization_version": 1,
                },
                "authority-stale-selection",
            )
        assert rejected.value.code == "authorization_version_conflict"
        get_settings.cache_clear()
        assert (
            session.scalar(sa.select(sa.func.count()).select_from(models.branch_selection_commands))
            == 0
        )


def test_authority_change_rolls_back_version_and_permissions_on_audit_failure(monkeypatch):
    from restaurant_os import operations

    factory, fixture, role_id = _setup()
    with factory() as session:
        before = set(
            session.scalars(
                sa.select(models.role_permissions.c.permission_id).where(
                    models.role_permissions.c.role_id == role_id
                )
            )
        )
        extra = session.scalar(
            sa.select(models.permissions.c.id).where(models.permissions.c.id.not_in(before))
        )

        def fail(*args, **kwargs):
            raise RuntimeError("Injected late audit failure")

        monkeypatch.setattr(operations, "_audit", fail)
        with pytest.raises(RuntimeError, match="Injected"):
            update_role_permissions(session, role_id, list(before) + [extra], ADMIN_USER_ID)
        session.rollback()
        assert (
            set(
                session.scalars(
                    sa.select(models.role_permissions.c.permission_id).where(
                        models.role_permissions.c.role_id == role_id
                    )
                )
            )
            == before
        )
        assert (
            session.scalar(
                sa.select(models.users.c.authorization_version).where(
                    models.users.c.id == fixture["supervisor_id"]
                )
            )
            == 1
        )


def test_assignment_to_foreign_organization_is_denied_without_version_change():
    factory, _, _ = _setup()
    with factory() as session:
        foreign_org, foreign_user, foreign_role = "foreign-org", "foreign-user", "foreign-role"
        for table, where, patch in [
            (models.organizations, sa.true(), {"id": foreign_org, "name": "Foreign"}),
            (
                models.users,
                models.users.c.id == ADMIN_USER_ID,
                {
                    "id": foreign_user,
                    "organization_id": foreign_org,
                    "email": "foreign@example.invalid",
                    "employee_code": None,
                },
            ),
            (
                models.roles,
                models.roles.c.id == ADMIN_ROLE_ID,
                {"id": foreign_role, "organization_id": foreign_org},
            ),
        ]:
            original = dict(session.execute(sa.select(table).where(where)).mappings().first())
            session.execute(table.insert().values(**{**original, **patch}))
        session.commit()
        with pytest.raises(BusinessError) as rejected:
            assign_user_role(session, foreign_user, foreign_role, actor_user_id=ADMIN_USER_ID)
        assert rejected.value.code == "user_not_found"
        assert (
            session.scalar(
                sa.select(sa.func.count())
                .select_from(models.user_roles)
                .where(models.user_roles.c.user_id == foreign_user)
            )
            == 0
        )
        assert (
            session.scalar(
                sa.select(models.users.c.authorization_version).where(
                    models.users.c.id == foreign_user
                )
            )
            == 1
        )


def test_legacy_authority_schema_preserves_reads_but_refuses_mutations():
    from restaurant_os.operations import (
        ORGANIZATION_ID,
        _bump_authority_versions,
        _user_authorization_version,
    )
    from sqlalchemy.orm import Session

    engine = sa.create_engine("sqlite+pysqlite://")
    with Session(engine) as session:
        session.execute(sa.text("CREATE TABLE users (id TEXT, organization_id TEXT)"))
        session.execute(
            sa.text("INSERT INTO users VALUES (:id, :org)"),
            {"id": "legacy-user", "org": ORGANIZATION_ID},
        )
        session.commit()
        assert _user_authorization_version(session, "legacy-user") == 1
        with pytest.raises(BusinessError) as rejected:
            _bump_authority_versions(session, ["legacy-user"])
        assert rejected.value.code == "authorization_migration_required"
        assert session.scalar(sa.text("SELECT COUNT(*) FROM users")) == 1
