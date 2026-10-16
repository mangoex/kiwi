"""Observed PostgreSQL actor fences, not timing-only concurrency assertions."""

import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event
from uuid import uuid4

import pytest
import sqlalchemy as sa
from restaurant_os import branch_workspaces, models, operational_intents
from restaurant_os import operations as ops
from sqlalchemy.exc import DataError, IntegrityError
from sqlalchemy.orm import Session
from test_branch_workspace_postgres import context_engine as context_engine
from test_branch_workspace_postgres import pg_engine as pg_engine
from test_corporate_purchases import SECOND_BRANCH_ID
from test_platform_api import ADMIN_USER_ID, BRANCH_ID, _admin_headers

BODY = {"branch_id": BRANCH_ID, "lines": []}
PREPARE = {"kind": "order.create", "target_id": None, "payload": BODY}
KEY = "pg-operational-intent-synthetic-001"


def test_real_api_open_holds_governance_before_actor_against_version_mutation(
    context_engine, monkeypatch
):
    from restaurant_os import api
    from starlette.requests import Request

    engine, profile = context_engine
    secret = profile["branch_workspace_context"]
    key = "pg-cash-lifecycle-open-001"
    body = {"branch_id": BRANCH_ID, "register_id": "PG-AUDIT-OPEN", "opening_cash_cents": 5000}
    with Session(engine) as session:
        receipt = operational_intents.prepare_intent(
            session,
            ADMIN_USER_ID,
            {"kind": "cash.shift.open", "target_id": None, "payload": body},
            key,
            secret,
        )
    held, release, entered = Event(), Event(), Event()
    pid = []
    original = api._require_operational_workspace

    def hold_after_workspace(*args, **kwargs):
        original(*args, **kwargs)
        held.set()
        assert release.wait(8), "Opening was not released"

    monkeypatch.setattr(api, "_require_operational_workspace", hold_after_workspace)

    def opening():
        with Session(engine) as session:
            request = Request(
                {"type": "http", "headers": [(b"x-operational-intent", receipt["id"].encode())]}
            )
            return api.open_current_cash_shift(
                body,
                session,
                request,
                authorization=_admin_headers()["Authorization"],
                idempotency_key=key,
                branch_context=secret,
            )

    def mutate_version():
        with Session(engine) as session:
            pid.append(session.scalar(sa.text("SELECT pg_backend_pid()")))
            entered.set()
            ops._authority_governance_lock(session)
            ops._bump_authority_versions(session, [ADMIN_USER_ID])
            session.commit()
            return session.scalar(
                sa.select(models.users.c.authorization_version).where(
                    models.users.c.id == ADMIN_USER_ID
                )
            )

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(opening)
        try:
            assert held.wait(6), "Real API did not reach validated workspace"
            second = pool.submit(mutate_version)
            _wait_for_lock(engine, pid, entered)
        finally:
            release.set()
        result, version = first.result(timeout=8), second.result(timeout=8)
    assert result["status"] == "OPEN" and version == 2
    with Session(engine) as session:
        assert (
            session.scalar(sa.select(sa.func.count()).select_from(models.cash_shift_commands)) == 1
        )
        assert (
            operational_intents.recover_intent(session, ADMIN_USER_ID, receipt["id"])["state"]
            == "acknowledged"
        )


@pytest.mark.parametrize("winner", ["execute", "recover"])
def test_real_cash_close_and_recovery_share_observed_fence(context_engine, monkeypatch, winner):
    engine, profile = context_engine
    key = "pg-cash-lifecycle-close-001"
    with Session(engine) as session:
        shift = ops.open_cash_shift_idempotently(
            session, BRANCH_ID, "CAJA-01", 10000, "pg-cash-setup-001", ADMIN_USER_ID
        )
        receipt = operational_intents.prepare_intent(
            session,
            ADMIN_USER_ID,
            {"kind": "cash.shift.close", "target_id": shift["id"], "payload": {}},
            key,
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
            assert release.wait(8)

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
                    "cash.shift.close",
                    shift["id"],
                    {},
                    key,
                    profile["branch_workspace_context"],
                    lambda: ops.close_cash_shift_operationally(
                        session, shift["id"], key, ADMIN_USER_ID, commit=False
                    ),
                )
            except ops.BusinessError as error:
                return error.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(run, winner)
        try:
            assert held.wait(6)
            second = pool.submit(run, "recover" if winner == "execute" else "execute", True)
            _wait_for_lock(engine, pid, entered)
        finally:
            release.set()
        first_result, second_result = first.result(timeout=8), second.result(timeout=8)
    assert isinstance(first_result, dict)
    if winner == "execute":
        assert first_result["cash_shift"]["status"] == "OPERATIVELY_CLOSED"
        assert second_result["state"] == "acknowledged"
    else:
        assert (
            first_result["state"] == "no_effect" and second_result == "operational_command_terminal"
        )
    with Session(engine) as session:
        assert session.scalar(
            sa.select(sa.func.count()).select_from(models.cash_shift_closures)
        ) == (1 if winner == "execute" else 0)
        assert session.scalar(
            sa.select(models.cash_shifts.c.status).where(models.cash_shifts.c.id == shift["id"])
        ) == ("OPERATIVELY_CLOSED" if winner == "execute" else "OPEN")


def test_migrated_key_constraint_matches_each_domain(context_engine):
    engine, profile = context_engine
    with Session(engine) as session:
        receipt = operational_intents.prepare_intent(
            session, ADMIN_USER_ID, PREPARE, KEY, profile["branch_workspace_context"]
        )
        table = models.operational_command_intents
        template = dict(
            session.execute(sa.select(table).where(table.c.id == receipt["id"])).mappings().one()
        )
        for kind, key, accepted in (
            ("cash.movement.create", "x", True),
            ("cash.movement.create", "x" * 180, True),
            ("cash.movement.create", "", False),
            ("cash.movement.create", "x" * 181, False),
            ("order.create", "x" * 12, True),
            ("order.create", "x" * 160, True),
            ("order.create", "x", False),
            ("order.create", "x" * 161, False),
            ("payment.confirm", "x" * 12, True),
            ("payment.confirm", "x" * 160, True),
            ("payment.confirm", "x", False),
            ("payment.confirm", "x" * 161, False),
        ):
            row = {
                **template,
                "id": str(uuid4()),
                "kind": kind,
                "command_namespace": operational_intents.command_namespace(kind),
                "idempotency_key": key,
                "target_id": BRANCH_ID if kind == "payment.confirm" else None,
            }
            if accepted:
                with session.begin_nested():
                    session.execute(sa.insert(table).values(**row))
            else:
                with pytest.raises((IntegrityError, DataError)):
                    with session.begin_nested():
                        session.execute(sa.insert(table).values(**row))
        session.commit()
    with Session(engine) as session:
        assert session.scalar(sa.select(sa.func.count()).select_from(table)) == 7


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
        [
            sys.executable,
            "-m",
            "alembic",
            "-c",
            "alembic.ini",
            "downgrade",
            "0089_offline_cutovers",
        ],
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
            == "0097_public_tracking_event_index"
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


@pytest.mark.parametrize("terminal", [False, True])
def test_0091_cash_history_blocks_postgres_downgrade(context_engine, terminal):
    engine, profile = context_engine
    body = {"branch_id": BRANCH_ID, "register_id": "PG-HISTORY", "opening_cash_cents": 0}
    with Session(engine) as session:
        receipt = operational_intents.prepare_intent(
            session,
            ADMIN_USER_ID,
            {"kind": "cash.shift.open", "target_id": None, "payload": body},
            "pg-new-cash-history",
            profile["branch_workspace_context"],
        )
        if terminal:
            operational_intents.recover_intent(session, ADMIN_USER_ID, receipt["id"])
        before = dict(
            session.execute(sa.select(models.operational_command_intents)).mappings().one()
        )
    result = _cash_lifecycle_alembic(engine, "downgrade", "0090_operational_intents")
    assert result.returncode != 0
    assert "0091 downgrade blocked: cash lifecycle command history exists" in result.stderr
    with Session(engine) as session:
        assert (
            dict(session.execute(sa.select(models.operational_command_intents)).mappings().one())
            == before
        )
        assert (
            session.scalar(sa.text("SELECT version_num FROM alembic_version"))
            == "0097_public_tracking_event_index"
        )


def _cash_lifecycle_alembic(engine, action, revision):
    env = {
        **os.environ,
        "RESTAURANTOS_DATABASE_URL": engine.url.render_as_string(hide_password=False),
    }
    env.pop("DATABASE_URL", None)
    return subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "alembic.ini", action, revision],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        text=True,
        capture_output=True,
        timeout=60,
    )


@pytest.mark.parametrize("terminal", [False, True])
def test_0091_postgres_backfill_preserves_populated_legacy_history(context_engine, terminal):
    engine, profile = context_engine
    with Session(engine) as session:
        receipt = operational_intents.prepare_intent(
            session, ADMIN_USER_ID, PREPARE, KEY, profile["branch_workspace_context"]
        )
        if terminal:
            operational_intents.recover_intent(session, ADMIN_USER_ID, receipt["id"])
        before = dict(
            session.execute(sa.select(models.operational_command_intents)).mappings().one()
        )
    down = _cash_lifecycle_alembic(engine, "downgrade", "0090_operational_intents")
    assert down.returncode == 0, down.stderr
    with engine.connect() as connection:
        old = sa.Table("operational_command_intents", sa.MetaData(), autoload_with=connection)
        legacy = dict(connection.execute(sa.select(old)).mappings().one())
        assert "command_namespace" not in legacy
        assert legacy == {key: value for key, value in before.items() if key != "command_namespace"}
    up = _cash_lifecycle_alembic(engine, "upgrade", "head")
    assert up.returncode == 0, up.stderr
    with Session(engine) as session:
        assert (
            dict(session.execute(sa.select(models.operational_command_intents)).mappings().one())
            == before
        )
        assert (
            session.scalar(sa.text("SELECT version_num FROM alembic_version"))
            == "0097_public_tracking_event_index"
        )


def test_0091_postgres_namespace_prevents_other_actor_incompatible_command(context_engine):
    engine, profile = context_engine
    body = {"branch_id": BRANCH_ID, "register_id": "PG-NAMESPACE", "opening_cash_cents": 0}
    with Session(engine) as session:
        operational_intents.prepare_intent(
            session,
            ADMIN_USER_ID,
            {"kind": "cash.shift.open", "target_id": None, "payload": body},
            "pg-shared-namespace",
            profile["branch_workspace_context"],
        )
        before = dict(
            session.execute(sa.select(models.operational_command_intents)).mappings().one()
        )
        actor = dict(
            session.execute(sa.select(models.users).where(models.users.c.id == ADMIN_USER_ID))
            .mappings()
            .one()
        )
        other = str(uuid4())
        session.execute(
            models.users.insert().values(
                **{**actor, "id": other, "email": "namespace-test@example.invalid"}
            )
        )
        collision = {
            **before,
            "id": str(uuid4()),
            "actor_user_id": other,
            "kind": "cash.shift.close.register",
        }
        with pytest.raises(IntegrityError, match="uq_operational_intent_namespace_key"):
            with session.begin_nested():
                session.execute(models.operational_command_intents.insert().values(**collision))
        spoof = {
            **collision,
            "id": str(uuid4()),
            "idempotency_key": "pg-namespace-spoof",
            "command_namespace": "payment.confirm",
        }
        with pytest.raises(IntegrityError, match="ck_operational_intent_namespace"):
            with session.begin_nested():
                session.execute(models.operational_command_intents.insert().values(**spoof))
        assert (
            dict(session.execute(sa.select(models.operational_command_intents)).mappings().one())
            == before
        )
