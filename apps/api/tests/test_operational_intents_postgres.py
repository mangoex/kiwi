"""Observed PostgreSQL actor fences, not timing-only concurrency assertions."""

import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event

import pytest
import sqlalchemy as sa
from restaurant_os import branch_workspaces, models, operational_intents
from restaurant_os import operations as ops
from sqlalchemy.orm import Session
from test_branch_workspace_postgres import context_engine as context_engine
from test_branch_workspace_postgres import pg_engine as pg_engine
from test_corporate_purchases import SECOND_BRANCH_ID
from test_platform_api import ADMIN_USER_ID, BRANCH_ID

BODY = {"branch_id": BRANCH_ID, "lines": []}
PREPARE = {"kind": "order.create", "target_id": None, "payload": BODY}
KEY = "pg-operational-intent-synthetic-001"


def _wait_for_lock(engine, pid, entered):
    assert entered.wait(6), "Contender did not enter"
    deadline = time.monotonic() + 6
    while time.monotonic() < deadline:
        with engine.connect() as connection:
            wait = connection.scalar(
                sa.text("SELECT wait_event_type FROM pg_stat_activity WHERE pid=:pid"),
                {"pid": pid[0]},
            )
        if wait == "Lock":
            return
        time.sleep(0.025)
    raise AssertionError("No real PostgreSQL Lock observed")


@pytest.mark.parametrize("winner", ["prepare", "select"])
def test_prepare_and_selection_share_observed_actor_fence(context_engine, monkeypatch, winner):
    engine, profile = context_engine
    held, release, entered = Event(), Event(), Event()
    pid = []
    original_audit = operational_intents._audit
    original_new = branch_workspaces._new_workspace

    def hold_preparation(*args, **kwargs):
        original_audit(*args, **kwargs)
        if args[-1] == "prepared":
            held.set()
            assert release.wait(8), "Preparation was not released"

    def hold_selection(*args, **kwargs):
        result = original_new(*args, **kwargs)
        held.set()
        assert release.wait(8), "Selection was not released"
        return result

    monkeypatch.setattr(
        operational_intents, "_audit", hold_preparation if winner == "prepare" else original_audit
    )
    monkeypatch.setattr(
        branch_workspaces, "_new_workspace", hold_selection if winner == "select" else original_new
    )

    def run(kind, contender=False):
        with Session(engine) as session:
            if contender:
                pid.append(session.scalar(sa.text("SELECT pg_backend_pid()")))
                entered.set()
            try:
                if kind == "prepare":
                    return operational_intents.prepare_intent(
                        session, ADMIN_USER_ID, PREPARE, KEY, profile["branch_workspace_context"]
                    )
                return branch_workspaces.select_branch_workspace(
                    session,
                    ADMIN_USER_ID,
                    {"target_branch_id": SECOND_BRANCH_ID, "expected_authorization_version": 1},
                    "pg-uncertain-select-synthetic-001",
                )
            except ops.BusinessError as error:
                return error.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(run, winner)
        try:
            assert held.wait(6), "Winner did not hold its fence"
            second = pool.submit(run, "select" if winner == "prepare" else "prepare", True)
            _wait_for_lock(engine, pid, entered)
        finally:
            release.set()
        first_result, second_result = first.result(timeout=8), second.result(timeout=8)
    assert isinstance(first_result, dict)
    assert second_result == (
        "branch_switch_uncertain_command" if winner == "prepare" else "branch_context_superseded"
    )
    with Session(engine) as session:
        pending = session.scalar(
            sa.select(sa.func.count()).select_from(models.operational_command_intents)
        )
        assert pending == (1 if winner == "prepare" else 0)
        row = (
            session.execute(
                sa.select(models.branch_workspace_sessions).where(
                    models.branch_workspace_sessions.c.state == "active"
                )
            )
            .mappings()
            .one()
        )
        assert row["branch_id"] == (BRANCH_ID if winner == "prepare" else SECOND_BRANCH_ID)


@pytest.mark.parametrize("terminal", [False, True])
def test_0090_downgrade_preserves_pending_and_terminal_history(context_engine, terminal):
    engine, profile = context_engine
    with Session(engine) as session:
        receipt = operational_intents.prepare_intent(
            session, ADMIN_USER_ID, PREPARE, KEY, profile["branch_workspace_context"]
        )
        if terminal:
            receipt = operational_intents.recover_intent(session, ADMIN_USER_ID, receipt["id"])
        tables = (
            models.operational_command_intents,
            models.branch_workspace_sessions,
            models.audit_events,
        )
        before = {
            table.name: [
                dict(row)
                for row in session.execute(sa.select(table).order_by(table.c.id)).mappings().all()
            ]
            for table in tables
        }
    env = {
        **os.environ,
        "RESTAURANTOS_DATABASE_URL": str(engine.url.render_as_string(hide_password=False)),
    }
    env.pop("DATABASE_URL", None)
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "alembic.ini", "downgrade", "-1"],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        text=True,
        capture_output=True,
        timeout=45,
    )
    assert result.returncode != 0
    assert "0090 downgrade blocked: operational command history exists" in result.stderr
    with Session(engine) as session:
        assert (
            session.scalar(sa.text("SELECT version_num FROM alembic_version"))
            == "0090_operational_intents"
        )
        after = {
            table.name: [
                dict(row)
                for row in session.execute(sa.select(table).order_by(table.c.id)).mappings().all()
            ]
            for table in tables
        }
        assert after == before


@pytest.mark.parametrize("winner", ["execute", "recover"])
def test_execution_and_recovery_serialize_before_deciding_effect(
    context_engine, monkeypatch, winner
):
    engine, profile = context_engine
    body = {
        "branch_id": BRANCH_ID,
        "register_id": "CAJA-01",
        "lines": [{"product_id": "018f6f73-2d0a-74f0-8f1c-000000000111", "quantity": 1}],
    }
    with Session(engine) as session:
        ops.open_cash_shift_idempotently(
            session, BRANCH_ID, "CAJA-01", 10000, "pg-intent-open-synthetic-001", ADMIN_USER_ID
        )
        receipt = operational_intents.prepare_intent(
            session,
            ADMIN_USER_ID,
            {"kind": "order.create", "target_id": None, "payload": body},
            KEY,
            profile["branch_workspace_context"],
        )
    held, release, entered = Event(), Event(), Event()
    pid = []
    original = operational_intents._audit
    state = "applied" if winner == "execute" else "no_effect"

    def hold(*args, **kwargs):
        original(*args, **kwargs)
        if args[-1] == state:
            held.set()
            assert release.wait(8), "Winner was not released"

    monkeypatch.setattr(operational_intents, "_audit", hold)

    def run(kind, contender=False):
        with Session(engine) as session:
            if contender:
                pid.append(session.scalar(sa.text("SELECT pg_backend_pid()")))
                entered.set()
            try:
                if kind == "recover":
                    return operational_intents.recover_intent(session, ADMIN_USER_ID, receipt["id"])
                return operational_intents.execute_intent(
                    session,
                    ADMIN_USER_ID,
                    receipt["id"],
                    "order.create",
                    None,
                    body,
                    KEY,
                    profile["branch_workspace_context"],
                    lambda: ops.create_local_order(
                        session,
                        body["lines"],
                        branch_id=BRANCH_ID,
                        register_id="CAJA-01",
                        actor_user_id=ADMIN_USER_ID,
                        idempotency_key=KEY,
                        commit=False,
                    ),
                )
            except ops.BusinessError as error:
                return error.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(run, winner)
        try:
            assert held.wait(6), "Winner did not hold its fence"
            second = pool.submit(run, "recover" if winner == "execute" else "execute", True)
            _wait_for_lock(engine, pid, entered)
        finally:
            release.set()
        first_result, second_result = first.result(timeout=8), second.result(timeout=8)
    assert isinstance(first_result, dict)
    if winner == "execute":
        assert second_result["state"] == "acknowledged"
        assert second_result["resource_id"] == first_result["id"]
    else:
        assert (
            first_result["state"] == "no_effect" and second_result == "operational_command_terminal"
        )
    with Session(engine) as session:
        expected = 1 if winner == "execute" else 0
        assert session.scalar(sa.select(sa.func.count()).select_from(models.orders)) == expected
        assert (
            session.scalar(sa.select(sa.func.count()).select_from(models.order_create_commands))
            == expected
        )
        assert session.scalar(sa.select(models.operational_command_intents.c.state)) == (
            "acknowledged" if winner == "execute" else "no_effect"
        )


@pytest.mark.parametrize("winner", ["recover", "select"])
def test_recovery_and_selection_share_the_same_observed_fence(context_engine, monkeypatch, winner):
    engine, profile = context_engine
    with Session(engine) as session:
        receipt = operational_intents.prepare_intent(
            session, ADMIN_USER_ID, PREPARE, KEY, profile["branch_workspace_context"]
        )
    held, release, entered = Event(), Event(), Event()
    pid = []
    audit, shift_guard = operational_intents._audit, branch_workspaces._assert_no_open_shift

    def hold_recovery(*args, **kwargs):
        audit(*args, **kwargs)
        if args[-1] == "no_effect":
            held.set()
            assert release.wait(8)

    def hold_selection(*args, **kwargs):
        shift_guard(*args, **kwargs)
        held.set()
        assert release.wait(8)

    monkeypatch.setattr(
        operational_intents, "_audit", hold_recovery if winner == "recover" else audit
    )
    monkeypatch.setattr(
        branch_workspaces,
        "_assert_no_open_shift",
        hold_selection if winner == "select" else shift_guard,
    )

    def run(kind, contender=False):
        with Session(engine) as session:
            if contender:
                pid.append(session.scalar(sa.text("SELECT pg_backend_pid()")))
                entered.set()
            try:
                if kind == "recover":
                    return operational_intents.recover_intent(session, ADMIN_USER_ID, receipt["id"])
                return branch_workspaces.select_branch_workspace(
                    session,
                    ADMIN_USER_ID,
                    {"target_branch_id": SECOND_BRANCH_ID, "expected_authorization_version": 1},
                    "pg-intent-after-recovery-001",
                )
            except ops.BusinessError as error:
                return error.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(run, winner)
        try:
            assert held.wait(6)
            second = pool.submit(run, "select" if winner == "recover" else "recover", True)
            _wait_for_lock(engine, pid, entered)
        finally:
            release.set()
        first_result, second_result = first.result(timeout=8), second.result(timeout=8)
    if winner == "recover":
        assert first_result["state"] == "no_effect"
        assert second_result["active_branch"]["id"] == SECOND_BRANCH_ID
    else:
        assert first_result == "branch_switch_uncertain_command"
        assert second_result["state"] == "no_effect"
    with Session(engine) as session:
        assert session.scalar(sa.select(models.operational_command_intents.c.state)) == "no_effect"
        context = (
            session.execute(
                sa.select(models.branch_workspace_sessions).where(
                    models.branch_workspace_sessions.c.state == "active"
                )
            )
            .mappings()
            .one()
        )
        assert context["branch_id"] == (SECOND_BRANCH_ID if winner == "recover" else BRANCH_ID)
