"""TC-450/462: human print queues and retries cannot export ticket snapshots."""

from typing import Any

import pytest
import sqlalchemy as sa
from corte_ciego_fixtures import grant_permission, ident
from restaurant_os import models
from restaurant_os import operations as ops
from restaurant_os.auth import create_session_token
from restaurant_os.config import get_settings
from test_corte_ciego_f106_orders import AttendedWorld, attended_world
from test_platform_api import BRANCH_ID

__all__ = ["attended_world"]


def headers(world: AttendedWorld) -> dict[str, str]:
    token = create_session_token({"sub": world.actor_id}, get_settings().secret_key)
    return {"Authorization": f"Bearer {token}"}


def seed_job(world: AttendedWorld) -> str:
    job = ident("restricted-print")
    with world.sessions() as session:
        grant_permission(session, world.role_id, "print.jobs.read")
        grant_permission(session, world.role_id, "print.jobs.retry")
        session.execute(
            models.print_jobs.insert().values(
                id=job,
                organization_id=ops.ORGANIZATION_ID,
                branch_id=BRANCH_ID,
                order_id=world.order_id,
                job_type="ticket",
                target="POS-CAJA-01",
                status="FAILED",
                attempts=1,
                payload={"total_cents": 9500, "private_snapshot": "PRIVATE-PRINT"},
                last_error="PRIVATE-PRINT-ERROR",
                created_at=ops._now(),
                printed_at=None,
            )
        )
        session.commit()
    return job


def test_human_print_list_never_selects_payload_or_free_error(
    attended_world: AttendedWorld,
) -> None:
    world = attended_world
    job = seed_job(world)
    statements: list[str] = []
    engine = world.sessions.kw["bind"]

    def observe(_conn: Any, _cursor: Any, statement: str, *_args: Any) -> None:
        if statement.lstrip().upper().startswith("SELECT") and "print_jobs" in statement:
            statements.append(statement)

    sa.event.listen(engine, "before_cursor_execute", observe)
    try:
        result = world.client.get("/api/v1/print-jobs", headers=headers(world))
    finally:
        sa.event.remove(engine, "before_cursor_execute", observe)
    assert result.status_code == 200, result.text
    assert result.json()[0]["id"] == job
    assert "PRIVATE-PRINT" not in result.text
    assert not {"payload", "last_error"}.intersection(result.json()[0])
    assert result.headers["cache-control"] == "no-store"
    assert statements and all(
        ".payload" not in sql and ".last_error" not in sql for sql in statements
    )


def test_print_list_direct_service_requires_current_human(attended_world: AttendedWorld) -> None:
    world = attended_world
    seed_job(world)
    with world.sessions() as session, pytest.raises(ops.AuthorizationError):
        ops.list_print_jobs(session, BRANCH_ID)


@pytest.mark.parametrize("change", ["order_closed", "permission"])
def test_retry_rechecks_context_even_for_existing_key(
    attended_world: AttendedWorld, change: str
) -> None:
    world = attended_world
    job = seed_job(world)
    auth = {**headers(world), "Idempotency-Key": "restricted-print-retry"}
    path = f"/api/v1/print-jobs/{job}/retry"
    first = world.client.post(path, headers=auth)
    assert first.status_code == 200, first.text
    assert "PRIVATE-PRINT" not in first.text
    assert "payload" not in first.json()["job"]
    replay = world.client.post(path, headers=auth)
    assert replay.status_code == 200 and replay.json()["replayed"] is True
    assert replay.json()["attempt"]["id"] == first.json()["attempt"]["id"]
    with world.sessions() as session:
        if change == "order_closed":
            session.execute(
                models.orders.update()
                .where(models.orders.c.id == world.order_id)
                .values(status="CLOSED")
            )
        else:
            permission = session.scalar(
                sa.select(models.permissions.c.id).where(
                    models.permissions.c.code == "orders.create"
                )
            )
            session.execute(
                models.role_permissions.delete().where(
                    models.role_permissions.c.role_id == world.role_id,
                    models.role_permissions.c.permission_id == permission,
                )
            )
        session.commit()
    denied = world.client.post(path, headers=auth)
    assert denied.status_code == 403, denied.text
    with world.sessions() as session:
        assert (
            session.scalar(
                sa.select(sa.func.count())
                .select_from(models.print_attempts)
                .where(models.print_attempts.c.print_job_id == job)
            )
            == 1
        )


def test_retry_without_context_does_not_enqueue(attended_world: AttendedWorld) -> None:
    world = attended_world
    job = seed_job(world)
    with world.sessions() as session:
        session.execute(
            models.orders.update()
            .where(models.orders.c.id == world.order_id)
            .values(status="CLOSED")
        )
        session.commit()
    with world.sessions() as session, pytest.raises(ops.AuthorizationError):
        ops.retry_print_job(
            session, job, "forbidden-retry", BRANCH_ID, actor_user_id=world.actor_id
        )
    with world.sessions() as session:
        assert (
            session.scalar(
                sa.select(models.print_jobs.c.status).where(models.print_jobs.c.id == job)
            )
            == "FAILED"
        )
        assert (
            session.scalar(
                sa.select(sa.func.count())
                .select_from(models.print_attempts)
                .where(models.print_attempts.c.print_job_id == job)
            )
            == 0
        )


@pytest.mark.parametrize("typ", ["agent", "device"])
def test_service_token_cannot_impersonate_print_human(
    attended_world: AttendedWorld,
    typ: str,
) -> None:
    world = attended_world
    job = seed_job(world)
    token = create_session_token({"sub": world.actor_id, "typ": typ}, get_settings().secret_key)
    auth = {"Authorization": f"Bearer {token}", "Idempotency-Key": "typed-token-retry"}
    assert world.client.get("/api/v1/print-jobs", headers=auth).status_code == 403
    assert world.client.post(f"/api/v1/print-jobs/{job}/retry", headers=auth).status_code == 403


def test_print_retry_audit_failure_rolls_back_without_disclosing_sql(
    attended_world: AttendedWorld,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    world = attended_world
    job = seed_job(world)
    original = ops._audit

    def fail_audit(*args: Any, **kwargs: Any) -> Any:
        if kwargs.get("action") == "print_job.retried":
            raise sa.exc.SQLAlchemyError("PRIVATE-PRINT-SQL")
        return original(*args, **kwargs)

    monkeypatch.setattr(ops, "_audit", fail_audit)
    result = world.client.post(
        f"/api/v1/print-jobs/{job}/retry",
        headers={**headers(world), "Idempotency-Key": "audit-failure"},
    )
    assert result.status_code == 503 and "PRIVATE-PRINT" not in result.text
    with world.sessions() as session:
        assert (
            session.scalar(
                sa.select(models.print_jobs.c.status).where(models.print_jobs.c.id == job)
            )
            == "FAILED"
        )
        assert (
            session.scalar(
                sa.select(sa.func.count())
                .select_from(models.print_attempts)
                .where(models.print_attempts.c.print_job_id == job)
            )
            == 0
        )
