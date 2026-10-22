"""Real credential-row revocation fences print payload materialization."""

import time
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from typing import Any

import pytest
import sqlalchemy as sa
from corte_ciego_fixtures import ident
from restaurant_os import models
from restaurant_os import operations as ops
from restaurant_os import print_device_views as views
from sqlalchemy.orm import Session
from test_cash_concepts import BRANCH_A
from test_corte_ciego_f105_postgres import pg_cash
from test_corte_ciego_f106_postgres import pg_sales
from test_sec001_operational_boundary import _device_credential

__all__ = ["pg_cash", "pg_sales"]


@pytest.mark.parametrize("reader_first", [True, False])
def test_payload_and_device_revocation_serialize(
    pg_sales: tuple[sa.Engine, str],
    monkeypatch: pytest.MonkeyPatch,
    reader_first: bool,
) -> None:
    engine, _ = pg_sales
    device = ident("pg-printer")
    with Session(engine) as session:
        _device_credential(
            session,
            device_id=device,
            token=ident("pg-printer-credential"),
            capability="print.agent",
            organization_id=ops.ORGANIZATION_ID,
            branch_id=BRANCH_A,
        )
        order = dict(
            session.execute(
                sa.select(models.orders).where(models.orders.c.id == ident("f106-order"))
            )
            .mappings()
            .one()
        )
        jobs = ops._create_print_jobs(session, order, {"id": ident("f106-pay")}, ops._now())
        session.commit()
        attempt = str(
            session.scalar(
                sa.select(models.print_attempts.c.id).where(
                    models.print_attempts.c.print_job_id == jobs[0]["id"]
                )
            )
        )
        ops.claim_print_attempt(session, attempt, device)
    reached, release, started, writer_done = Event(), Event(), Event(), Event()
    pids: list[int] = []
    original_audit, original_require = ops._audit, views.require_device
    read_calls = 0

    def audit(*args: Any, **kwargs: Any) -> Any:
        if reader_first and len(args) > 1 and args[1] == "print_attempt.payload_read":
            reached.set()
            assert release.wait(10)
        return original_audit(*args, **kwargs)

    def require(*args: Any, **kwargs: Any) -> None:
        nonlocal read_calls
        read_calls += 1
        if reader_first and read_calls == 2:
            assert writer_done.wait(10)
        original_require(*args, **kwargs)

    monkeypatch.setattr(ops, "_audit", audit)
    monkeypatch.setattr(views, "require_device", require)

    def read() -> str:
        with Session(engine) as session:
            if not reader_first:
                pids.append(int(session.scalar(sa.text("SELECT pg_backend_pid()"))))
                started.set()
            try:
                views.assigned_payload(session, attempt, device, ops.ORGANIZATION_ID, BRANCH_A)
            except ops.AuthorizationError:
                return "denied"
            return "allowed"

    def revoke() -> None:
        with Session(engine) as session:
            if reader_first:
                pids.append(int(session.scalar(sa.text("SELECT pg_backend_pid()"))))
                started.set()
            session.execute(
                models.device_credentials.update()
                .where(models.device_credentials.c.id == device)
                .values(revoked_at=ops._now())
            )
            if not reader_first:
                reached.set()
                assert release.wait(10)
            session.commit()
            writer_done.set()

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(read if reader_first else revoke)
        assert reached.wait(10)
        second = pool.submit(revoke if reader_first else read)
        assert started.wait(10)
        try:
            deadline = time.monotonic() + 8
            while time.monotonic() < deadline:
                with engine.connect() as connection:
                    blocked = connection.scalar(
                        sa.text("SELECT cardinality(pg_blocking_pids(:pid)) > 0"), {"pid": pids[0]}
                    )
                if blocked:
                    break
                time.sleep(0.02)
            else:
                pytest.fail("Credential contender did not block on the real database row")
        finally:
            release.set()
        results = first.result(15), second.result(15)
    assert results[0 if reader_first else 1] == "denied"
    with Session(engine) as session:
        assert session.scalar(
            sa.select(sa.func.count())
            .select_from(models.audit_events)
            .where(models.audit_events.c.action == "print_attempt.payload_read")
        ) == int(reader_first)
        with pytest.raises(ops.AuthorizationError):
            views.assigned_payload(session, attempt, device, ops.ORGANIZATION_ID, BRANCH_A)
