"""TC-451/461: controlled PostgreSQL barriers, never SQLite concurrency evidence."""

from __future__ import annotations

import time
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event
from typing import Any

import pytest
import sqlalchemy as sa
from corte_ciego_fixtures import grant_permission
from corte_ciego_storage import isolated_database, seed_authority
from restaurant_os import models, operations
from restaurant_os.financial_access import FinancialAccessService
from restaurant_os.financial_authority import FinancialAuthority
from sqlalchemy.orm import Session
from test_cash_concepts import (
    BRANCH_A,
    CASHIER_ID,
    CASHIER_ROLE_ID,
    ORG_ID,
    OWNER_ID,
    OWNER_ROLE_ID,
)


@pytest.fixture
def pg_authority() -> Iterator[sa.Engine]:
    yield from isolated_database("postgresql")


def wait_until_blocked(engine: sa.Engine, pid: int) -> None:
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        with engine.connect() as connection:
            waiting = connection.scalar(
                sa.text(
                    "SELECT wait_event_type = 'Lock' AND wait_event = 'advisory' "
                    "FROM pg_stat_activity WHERE pid=:pid"
                ),
                {"pid": pid},
            )
        if waiting:
            return
        time.sleep(0.02)
    pytest.fail("Contender did not reach the real shared/exclusive governance barrier")


@pytest.mark.parametrize("reader_first", [True, False])
@pytest.mark.parametrize("mutation", ["revoke", "role"])
def test_read_materialization_and_authority_mutation_serialize(
    pg_authority: sa.Engine,
    monkeypatch: pytest.MonkeyPatch,
    reader_first: bool,
    mutation: str,
) -> None:
    grant = seed_authority(pg_authority)
    with Session(pg_authority) as session:
        grant_permission(session, OWNER_ROLE_ID, "admin.manage")
        session.commit()
    arrived, release, contender_started = Event(), Event(), Event()
    contender_pid: list[int] = []
    original_audit = operations._audit

    def audit_barrier(*args: Any, **kwargs: Any) -> None:
        original_audit(*args, **kwargs)
        if not reader_first:
            arrived.set()
            assert release.wait(10), "Release writer before transaction commit"

    monkeypatch.setattr(operations, "_audit", audit_barrier)

    def reader() -> bool:
        with Session(pg_authority) as session:
            if not reader_first:
                contender_pid.append(int(session.scalar(sa.text("SELECT pg_backend_pid()"))))
                contender_started.set()
            policy = FinancialAuthority(session, CASHIER_ID, ORG_ID)

            def materialize() -> int:
                # Real query while authority lock is retained; value is test-only metadata.
                value = int(
                    session.scalar(
                        sa.select(sa.func.count()).select_from(models.financial_access_grants)
                    )
                )
                if reader_first:
                    arrived.set()
                    assert release.wait(10), "Release materialization before writer can revoke"
                return value

            try:
                assert policy.materialize([(BRANCH_A, "sales")], materialize) == 1
                session.commit()
                return True
            except operations.AuthorizationError:
                return False

    def writer() -> None:
        with Session(pg_authority) as session:
            if reader_first:
                contender_pid.append(int(session.scalar(sa.text("SELECT pg_backend_pid()"))))
                contender_started.set()
            if mutation == "revoke":
                FinancialAccessService(session, ORG_ID).revoke(
                    OWNER_ID, grant, "stop", {"reason": "Stop"}
                )
            else:
                operations.update_role_permissions(session, CASHIER_ROLE_ID, [], OWNER_ID)

    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(reader if reader_first else writer)
        second = None
        try:
            assert arrived.wait(10)
            second = executor.submit(writer if reader_first else reader)
            assert contender_started.wait(5)
            wait_until_blocked(pg_authority, contender_pid[0])
        finally:
            release.set()
        assert second is not None
        first_result, second_result = first.result(timeout=15), second.result(timeout=15)
        assert (first_result if reader_first else second_result) is reader_first
    with Session(pg_authority) as session:
        with pytest.raises(operations.AuthorizationError):
            FinancialAuthority(session, CASHIER_ID, ORG_ID).require_financial([(BRANCH_A, "sales")])


def test_concurrent_duplicate_issue_has_one_grant_command_audit_and_version(
    pg_authority: sa.Engine,
) -> None:
    seed_authority(pg_authority)
    barrier = Barrier(2)

    def issue() -> dict[str, Any]:
        with Session(pg_authority) as session:
            barrier.wait(timeout=10)
            return FinancialAccessService(session, ORG_ID).issue(
                OWNER_ID,
                "concurrent",
                {
                    "subject_user_id": CASHIER_ID,
                    "reason": "Same exact intent",
                    "scopes": [{"branch_id": BRANCH_A, "dataset": "cash.cuts"}],
                },
            )

    with ThreadPoolExecutor(max_workers=2) as executor:
        first, second = executor.submit(issue), executor.submit(issue)
        results = [first.result(timeout=15), second.result(timeout=15)]
    assert results[0]["grant_id"] == results[1]["grant_id"]
    assert sorted(result["replay"] for result in results) == [False, True]
    with Session(pg_authority) as session:
        assert (
            session.scalar(sa.select(sa.func.count()).select_from(models.financial_access_grants))
            == 2
        )
        assert (
            session.scalar(sa.select(sa.func.count()).select_from(models.financial_access_commands))
            == 2
        )
        assert (
            session.scalar(
                sa.select(sa.func.count())
                .select_from(models.audit_events)
                .where(
                    models.audit_events.c.action == "financial_access.issued",
                )
            )
            == 2
        )
        assert (
            session.scalar(
                sa.select(models.users.c.authorization_version).where(
                    models.users.c.id == CASHIER_ID,
                )
            )
            == 3
        )


def test_repeatable_read_cannot_reuse_a_stale_authority_snapshot(pg_authority: sa.Engine) -> None:
    seed_authority(pg_authority)
    with pg_authority.connect().execution_options(isolation_level="REPEATABLE READ") as connection:
        with Session(bind=connection) as session:
            with pytest.raises(operations.BusinessError) as error:
                FinancialAuthority(session, CASHIER_ID, ORG_ID).require_financial(
                    [(BRANCH_A, "sales")]
                )
            assert error.value.code == "cash_authorization_changed"
