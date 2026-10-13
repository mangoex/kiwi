"""PostgreSQL migration and competing context rotation evidence."""

import hashlib
import time
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event, Thread

import pytest
import sqlalchemy as sa
from restaurant_os import models
from restaurant_os.auth import create_session_token
from restaurant_os.branch_workspaces import (
    reissue_branch_context,
    select_branch_workspace,
    validate_branch_context,
)
from restaurant_os.config import get_settings
from restaurant_os.operational_guard import OperationalRouteGuard
from restaurant_os.operations import (
    AuthorizationError,
    BusinessError,
    build_session_profile,
    open_cash_shift_idempotently,
)
from sqlalchemy.orm import Session
from test_branch_scope_selection import _grant_selection
from test_corporate_purchases import SECOND_BRANCH_ID
from test_corporate_purchases_postgres import pg_engine as pg_engine
from test_platform_api import ADMIN_ROLE_ID, ADMIN_USER_ID, BRANCH_ID


@pytest.fixture
def context_engine(pg_engine, monkeypatch):
    monkeypatch.setenv("RESTAURANTOS_BRANCH_SCOPE_V2_ENABLED", "true")
    get_settings.cache_clear()
    with Session(pg_engine) as session:
        assert session.scalar(sa.text("SHOW statement_timeout")) == "15s"
        _grant_selection(session, ADMIN_ROLE_ID, workspace=False)
        initial = select_branch_workspace(
            session,
            ADMIN_USER_ID,
            {
                "target_branch_id": BRANCH_ID,
                "expected_authorization_version": 1,
            },
            "pg-workspace-initial",
        )
    yield pg_engine, initial
    get_settings.cache_clear()


def test_concurrent_reissue_replay_rotates_one_context_without_plaintext(context_engine):
    engine, initial = context_engine
    barrier = Barrier(2)

    def rotate():
        with Session(engine) as session:
            barrier.wait(timeout=8)
            return reissue_branch_context(
                session,
                ADMIN_USER_ID,
                {
                    "context_id": initial["branch_workspace_context_id"],
                    "expected_authorization_version": 1,
                },
                "pg-workspace-concurrent-reissue",
            )

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: rotate(), range(2)))
    assert {result["branch_workspace_secret_version"] for result in results} == {2, 3}
    latest = max(results, key=lambda result: result["branch_workspace_secret_version"])
    stale = min(results, key=lambda result: result["branch_workspace_secret_version"])
    with Session(engine) as session:
        row = session.execute(sa.select(models.branch_workspace_sessions)).mappings().one()
        assert (
            row["token_hash"]
            == hashlib.sha256(latest["branch_workspace_context"].encode()).hexdigest()
        )
        assert (
            session.scalar(
                sa.select(sa.func.count()).select_from(models.branch_context_reissue_commands)
            )
            == 1
        )
        assert (
            validate_branch_context(
                session, ADMIN_USER_ID, BRANCH_ID, latest["branch_workspace_context"]
            )["id"]
            == initial["branch_workspace_context_id"]
        )
        with pytest.raises(AuthorizationError) as rejected:
            validate_branch_context(
                session, ADMIN_USER_ID, BRANCH_ID, stale["branch_workspace_context"]
            )
        assert rejected.value.code == "branch_context_superseded"
        for result in results:
            assert result["branch_workspace_context"] not in str(dict(row))
    with Session(engine) as session:
        profile = build_session_profile(session, ADMIN_USER_ID)
        assert profile["active_branch"]["id"] == BRANCH_ID
        assert profile["branch_workspace_context"] is None
        assert profile["branch_workspace_secret_version"] == 3


def test_competing_selections_preserve_one_current_workspace(context_engine):
    engine, _ = context_engine
    barrier = Barrier(2)

    def select(target):
        with Session(engine) as session:
            barrier.wait(timeout=8)
            return select_branch_workspace(
                session,
                ADMIN_USER_ID,
                {
                    "target_branch_id": target,
                    "expected_authorization_version": 1,
                },
                f"pg-workspace-competing-{target}",
            )

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(select, (BRANCH_ID, SECOND_BRANCH_ID)))
    with Session(engine) as session:
        rows = session.execute(sa.select(models.branch_workspace_sessions)).mappings().all()
        assert len(rows) == 3
        active = [row for row in rows if row["state"] == "active"]
        assert len(active) == 1
        current = next(
            result for result in results if result["branch_workspace_context_id"] == active[0]["id"]
        )
        obsolete = next(
            result for result in results if result["branch_workspace_context_id"] != active[0]["id"]
        )
        assert (
            validate_branch_context(
                session, ADMIN_USER_ID, active[0]["branch_id"], current["branch_workspace_context"]
            )["id"]
            == active[0]["id"]
        )
        with pytest.raises(AuthorizationError) as rejected:
            validate_branch_context(
                session,
                ADMIN_USER_ID,
                obsolete["active_branch"]["id"],
                obsolete["branch_workspace_context"],
            )
        assert rejected.value.code == "branch_context_superseded"
        assert (
            session.scalar(sa.select(sa.func.count()).select_from(models.branch_selection_commands))
            == 3
        )


def test_cash_open_fence_serializes_before_branch_selection(context_engine):
    engine, initial = context_engine
    fenced, release, contender_started = Event(), Event(), Event()
    failures, results, backend_pid = [], [], []

    def open_shift():
        try:
            with Session(engine) as session:
                validate_branch_context(
                    session, ADMIN_USER_ID, BRANCH_ID, initial["branch_workspace_context"]
                )
                fenced.set()
                assert release.wait(12), "Parent must release the controlled actor fence"
                results.append(
                    open_cash_shift_idempotently(
                        session, BRANCH_ID, "PG-FENCE", 0, "pg-fenced-cash-open", ADMIN_USER_ID
                    )
                )
        except BaseException as error:
            failures.append(error)

    def switch():
        try:
            with Session(engine) as session:
                backend_pid.append(session.scalar(sa.text("SELECT pg_backend_pid()")))
                contender_started.set()
                try:
                    select_branch_workspace(
                        session,
                        ADMIN_USER_ID,
                        {
                            "target_branch_id": SECOND_BRANCH_ID,
                            "expected_authorization_version": 1,
                        },
                        "pg-switch-during-cash-open",
                    )
                except BusinessError as error:
                    results.append(error.code)
        except BaseException as error:
            failures.append(error)

    first, second = Thread(target=open_shift), Thread(target=switch)
    first.start()
    try:
        assert fenced.wait(12)
        second.start()
        assert contender_started.wait(8)
        deadline, waiting = time.monotonic() + 5, False
        while time.monotonic() < deadline:
            with engine.connect() as connection:
                waiting = bool(
                    connection.scalar(
                        sa.text(
                            "SELECT wait_event_type = 'Lock' "
                            "AND wait_event IN ('transactionid', 'tuple') "
                            "FROM pg_stat_activity WHERE pid = :pid"
                        ),
                        {"pid": backend_pid[0]},
                    )
                )
            if waiting:
                break
            time.sleep(0.02)
        assert waiting, "Selection must wait for the actor fence held by cash opening"
    finally:
        release.set()
        first.join(15)
        if second.ident:
            second.join(15)
    assert not first.is_alive() and not second.is_alive()
    assert not failures, failures
    assert "branch_switch_open_shift" in results
    with Session(engine) as session:
        shifts = session.execute(sa.select(models.cash_shifts)).mappings().all()
        assert len(shifts) == 1
        assert shifts[0]["branch_id"] == BRANCH_ID
        workspace = session.execute(sa.select(models.branch_workspace_sessions)).mappings().one()
        assert workspace["id"] == initial["branch_workspace_context_id"]
        assert (
            session.scalar(sa.select(sa.func.count()).select_from(models.branch_selection_commands))
            == 1
        )


def test_human_operational_guard_holds_actor_fence_until_resource_transaction_ends(context_engine):
    engine, initial = context_engine
    authorization = "Bearer " + create_session_token(
        {"sub": ADMIN_USER_ID}, get_settings().secret_key
    )
    fenced, release, contender_started = Event(), Event(), Event()
    failures, branches, results, backend_pid = [], [], [], []

    def scoped_resource():
        try:
            with Session(engine) as session:
                actor = OperationalRouteGuard().require_human(
                    session,
                    authorization,
                    "pos.operate",
                    None,
                    branch_context=initial["branch_workspace_context"],
                )
                branches.append(actor.branch_id)
                fenced.set()
                assert release.wait(12), "Parent must release the controlled resource transaction"
                # The resource must still belong to A before this transaction releases the fence.
                row = session.scalar(
                    sa.select(models.branch_workspace_sessions.c.branch_id).where(
                        models.branch_workspace_sessions.c.id
                        == initial["branch_workspace_context_id"],
                        models.branch_workspace_sessions.c.state == "active",
                    )
                )
                assert row == actor.branch_id == BRANCH_ID
                session.rollback()
        except BaseException as error:
            failures.append(error)

    def switch():
        try:
            with Session(engine) as session:
                backend_pid.append(session.scalar(sa.text("SELECT pg_backend_pid()")))
                contender_started.set()
                results.append(
                    select_branch_workspace(
                        session,
                        ADMIN_USER_ID,
                        {
                            "target_branch_id": SECOND_BRANCH_ID,
                            "expected_authorization_version": 1,
                        },
                        "pg-switch-during-operational-resource",
                    )
                )
        except BaseException as error:
            failures.append(error)

    first, second = Thread(target=scoped_resource), Thread(target=switch)
    first.start()
    try:
        assert fenced.wait(12)
        second.start()
        assert contender_started.wait(8)
        deadline, waiting = time.monotonic() + 5, False
        while time.monotonic() < deadline:
            with engine.connect() as connection:
                waiting = bool(
                    connection.scalar(
                        sa.text(
                            "SELECT wait_event_type = 'Lock' "
                            "AND wait_event IN ('transactionid', 'tuple') "
                            "FROM pg_stat_activity WHERE pid = :pid"
                        ),
                        {"pid": backend_pid[0]},
                    )
                )
            if waiting:
                break
            time.sleep(0.02)
        assert waiting, "Selection must wait until the resource transaction ends"
        assert results == []
    finally:
        release.set()
        first.join(15)
        if second.ident:
            second.join(15)
    assert not first.is_alive() and not second.is_alive()
    assert not failures, failures
    assert branches == [BRANCH_ID]
    assert len(results) == 1
    assert results[0]["active_branch"]["id"] == SECOND_BRANCH_ID
    with Session(engine) as session:
        with pytest.raises(AuthorizationError) as rejected:
            validate_branch_context(
                session, ADMIN_USER_ID, BRANCH_ID, initial["branch_workspace_context"]
            )
        assert rejected.value.code == "branch_context_superseded"
