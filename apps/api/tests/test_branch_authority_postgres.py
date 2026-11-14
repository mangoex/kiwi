"""PostgreSQL evidence for shared-role enumeration versus new assignments."""

import time
from threading import Event, Thread

import sqlalchemy as sa
from restaurant_os import models, operations
from sqlalchemy.orm import Session
from test_corporate_purchases_postgres import pg_engine as pg_engine
from test_platform_api import ADMIN_USER_ID, BRANCH_ID


def test_permission_change_cannot_miss_a_concurrent_assignment(pg_engine, monkeypatch):
    with Session(pg_engine) as session:
        role = operations.create_role(session, "PG authority", actor_user_id=ADMIN_USER_ID)
        permission_id = session.scalar(
            sa.select(models.permissions.c.id).where(models.permissions.c.code == "pos.operate")
        )
    enumerated, release, contender_started = Event(), Event(), Event()
    backend_pid, failures = [], []
    original = operations._role_authority_users

    def enumerate_users(session, role_id):
        result = original(session, role_id)
        if role_id == role["id"]:
            assert result == []
            enumerated.set()
            assert release.wait(8), "Parent must release the controlled barrier"
        return result

    monkeypatch.setattr(operations, "_role_authority_users", enumerate_users)

    def change_permissions():
        try:
            with Session(pg_engine) as session:
                operations.update_role_permissions(
                    session, role["id"], [permission_id], ADMIN_USER_ID
                )
        except BaseException as error:
            failures.append(error)

    def assign():
        try:
            with Session(pg_engine) as session:
                backend_pid.append(session.scalar(sa.text("SELECT pg_backend_pid()")))
                contender_started.set()
                operations.assign_user_role(
                    session, ADMIN_USER_ID, role["id"], BRANCH_ID, ADMIN_USER_ID
                )
        except BaseException as error:
            failures.append(error)

    first, second = Thread(target=change_permissions), Thread(target=assign)
    first.start()
    try:
        assert enumerated.wait(8)
        second.start()
        assert contender_started.wait(5)
        deadline, waiting = time.monotonic() + 5, False
        while time.monotonic() < deadline:
            with pg_engine.connect() as connection:
                waiting = connection.scalar(
                    sa.text(
                        "SELECT wait_event_type = 'Lock' AND wait_event = 'advisory' "
                        "FROM pg_stat_activity WHERE pid = :pid"
                    ),
                    {"pid": backend_pid[0]},
                )
            if waiting:
                break
            time.sleep(0.02)
        assert waiting, "The new assignment must wait behind the role authority transaction"
    finally:
        release.set()
        first.join(12)
        if second.ident:
            second.join(12)
    assert not first.is_alive() and not second.is_alive()
    assert not failures, failures
    with Session(pg_engine) as session:
        assert (
            session.scalar(
                sa.select(models.users.c.authorization_version).where(
                    models.users.c.id == ADMIN_USER_ID
                )
            )
            == 2
        )
        assert (
            session.scalar(
                sa.select(models.user_roles.c.role_id).where(
                    models.user_roles.c.user_id == ADMIN_USER_ID,
                    models.user_roles.c.role_id == role["id"],
                )
            )
            == role["id"]
        )
        assert (
            session.scalar(
                sa.select(models.role_permissions.c.permission_id).where(
                    models.role_permissions.c.role_id == role["id"]
                )
            )
            == permission_id
        )


def test_updating_existing_role_branch_updates_row_under_governance_lock_on_postgres(pg_engine):
    from test_corporate_purchases import SECOND_BRANCH_ID

    with Session(pg_engine) as session:
        role = operations.create_role(
            session, "Líder PG", scope="branch", actor_user_id=ADMIN_USER_ID
        )
        created = operations.create_user(
            session,
            email="amayrani.pg@kiwi.local",
            display_name="Amayrani PG",
            actor_user_id=ADMIN_USER_ID,
            role_id=role["id"],
            branch_id=BRANCH_ID,
            employee_code="CHLD01",
        )
        user_id = created["id"]
        version_initial = session.scalar(
            sa.select(models.users.c.authorization_version).where(models.users.c.id == user_id)
        )
        assert version_initial == 1

        operations.update_user(
            session,
            user_id,
            email="amayrani.pg@kiwi.local",
            display_name="Amayrani PG",
            actor_user_id=ADMIN_USER_ID,
            role_id=role["id"],
            branch_id=SECOND_BRANCH_ID,
            employee_code="CHLD01",
        )
        branch_after = session.scalar(
            sa.select(models.user_roles.c.branch_id).where(
                models.user_roles.c.user_id == user_id,
                models.user_roles.c.role_id == role["id"],
            )
        )
        assert branch_after == SECOND_BRANCH_ID
        version_after = session.scalar(
            sa.select(models.users.c.authorization_version).where(models.users.c.id == user_id)
        )
        assert version_after == 2
        audit_payload = session.scalar(
            sa.select(models.audit_events.c.payload).where(
                models.audit_events.c.entity_id == user_id,
                models.audit_events.c.action == "user_role.branch_updated",
            )
        )
        assert audit_payload == {
            "role_id": role["id"],
            "previous_branch_id": BRANCH_ID,
            "branch_id": SECOND_BRANCH_ID,
        }
