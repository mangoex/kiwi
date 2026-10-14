"""PostgreSQL migration and competing context rotation evidence."""

import hashlib
import time
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event, Thread

import pytest
import sqlalchemy as sa
from fastapi import HTTPException
from restaurant_os import api, branch_workspaces, expenses, models, workspace_fences
from restaurant_os import operations as ops
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
from test_operational_intents import _grant_permission
from test_platform_api import ADMIN_ROLE_ID, ADMIN_USER_ID, BRANCH_ID, _admin_headers
from test_purchase_workspace import _presentation, _purchase_payload


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


def test_concurrent_selection_replay_audits_each_committed_rotation(context_engine):
    engine, initial = context_engine
    barrier = Barrier(2)

    def replay():
        with Session(engine) as session:
            barrier.wait(timeout=8)
            return select_branch_workspace(
                session,
                ADMIN_USER_ID,
                {"target_branch_id": BRANCH_ID, "expected_authorization_version": 1},
                "pg-workspace-initial",
            )

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: replay(), range(2)))
    assert {result["branch_workspace_secret_version"] for result in results} == {2, 3}
    latest = max(results, key=lambda result: result["branch_workspace_secret_version"])
    stale = min(results, key=lambda result: result["branch_workspace_secret_version"])
    with Session(engine) as session:
        rows = session.execute(sa.select(models.branch_workspace_sessions)).mappings().all()
        assert len(rows) == 1
        assert rows[0]["state"] == "active"
        assert rows[0]["id"] == initial["branch_workspace_context_id"]
        command = session.execute(sa.select(models.branch_selection_commands)).mappings().one()
        audits = (
            session.execute(
                sa.select(models.audit_events).where(
                    models.audit_events.c.action == "auth.branch_context_reissued",
                    models.audit_events.c.entity_id == initial["branch_workspace_context_id"],
                )
            )
            .mappings()
            .all()
        )
        assert len(audits) == 2
        assert {audit["payload"]["secret_version"] for audit in audits} == {2, 3}
        assert all(audit["payload"]["selection_command_id"] == command["id"] for audit in audits)
        assert all(audit["payload"]["reason"] == "selection_replay" for audit in audits)
        assert (
            validate_branch_context(
                session, ADMIN_USER_ID, BRANCH_ID, latest["branch_workspace_context"]
            )["id"]
            == rows[0]["id"]
        )
        with pytest.raises(AuthorizationError) as rejected:
            validate_branch_context(
                session, ADMIN_USER_ID, BRANCH_ID, stale["branch_workspace_context"]
            )
        assert rejected.value.code == "branch_context_superseded"
        persisted = str(
            [dict(row) for row in rows] + [dict(audit) for audit in audits] + [dict(command)]
        )
        for result in [initial, *results]:
            assert result["branch_workspace_context"] not in persisted


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



def _wait_for_document_lock(engine, pid, entered):
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

def _document_confirmation(engine, family, initial):
    with Session(engine) as session:
        if family == "purchase":
            supplier = ops.create_supplier(
                session, {"code": "PG-DOC", "commercial_name": "Synthetic"}, ADMIN_USER_ID
            )
            presentation = ops.create_purchase_presentation(
                session, _presentation(supplier["id"]), ADMIN_USER_ID
            )
            document = ops.create_purchase_document(
                session,
                _purchase_payload(supplier["id"], presentation["id"]),
                ADMIN_USER_ID,
                "pg-document-draft",
            )
        else:
            for code in ("expense.concept.manage", "expenses.manage", "expenses.cancel"):
                _grant_permission(session, code)
            concept = expenses.command(
                session,
                ADMIN_USER_ID,
                "concept.create",
                None,
                {"code": "PG-DOC", "name": "Synthetic", "description": "Synthetic"},
                "pg-document-concept",
            )
            document = expenses.command(
                session,
                ADMIN_USER_ID,
                "document.create",
                None,
                {
                    "branch_id": BRANCH_ID,
                    "concept_id": concept["id"],
                    "document_date": "2026-10-14",
                    "total_cents": 25000,
                    "tax_cents": None,
                    "payment_method": "transfer",
                    "reference": "PG-DOCUMENT",
                    "notes": "",
                    "evidence_refs": [],
                },
                "pg-document-draft",
            )

    def write():
        with Session(engine) as session:
            arguments = dict(
                session=session,
                authorization=_admin_headers()["Authorization"],
                branch_context=initial["branch_workspace_context"],
            )
            if family == "purchase":
                return api.confirm_purchase_endpoint(
                    purchase_id=document["id"],
                    payload={},
                    idempotency_key_header="pg-document-confirm",
                    **arguments,
                )
            return api.expense_confirm(
                expense_id=document["id"],
                payload={"branch_id": BRANCH_ID, "version": document["version"]},
                idempotency_key="pg-document-confirm",
                **arguments,
            )

    return document, write


def _document_effects(engine, family, target):
    with Session(engine) as session:
        table = models.purchase_documents if family == "purchase" else models.expense_documents
        row = dict(session.execute(sa.select(table).where(table.c.id == target)).mappings().one())
        tables = (
            models.inventory_movements,
            models.inventory_cost_states,
            models.cash_movements,
            models.expense_commands,
        )
        effects = {
            table.name: [
                dict(row)
                for row in session.execute(sa.select(table).order_by(*table.primary_key)).mappings()
            ]
            for table in tables
        }
        return row, effects


@pytest.mark.parametrize("family", ["purchase", "expense"])
@pytest.mark.parametrize("winner", ["write", "select"])
def test_document_confirmation_and_selection_share_transaction_fence(
    context_engine, monkeypatch, family, winner
):
    engine, initial = context_engine
    document, write = _document_confirmation(engine, family, initial)
    before = _document_effects(engine, family, document["id"])
    held, release, entered = Event(), Event(), Event()
    pid, results, failures = [], {}, []
    original_context, original_new = (
        workspace_fences._branch_context,
        branch_workspaces._new_workspace,
    )

    def hold_context(*args, **kwargs):
        original_context(*args, **kwargs)
        if winner == "write":
            held.set()
            assert release.wait(8), "Confirmation was not released"

    def hold_selection(*args, **kwargs):
        value = original_new(*args, **kwargs)
        if winner == "select":
            held.set()
            assert release.wait(8), "Selection was not released"
        return value

    monkeypatch.setattr(workspace_fences, "_branch_context", hold_context)
    monkeypatch.setattr(branch_workspaces, "_new_workspace", hold_selection)

    def run(kind, contender=False):
        try:
            if kind == "write":
                if contender:
                    # Capture the PID of the same connection used by the real API wrapper.
                    original_factory = (
                        api.confirm_purchase_endpoint
                        if family == "purchase"
                        else api.expense_confirm
                    )
                    with Session(engine) as session:
                        pid.append(session.scalar(sa.text("SELECT pg_backend_pid()")))
                        entered.set()
                        args = dict(
                            session=session,
                            authorization=_admin_headers()["Authorization"],
                            branch_context=initial["branch_workspace_context"],
                            payload={}
                            if family == "purchase"
                            else {"branch_id": BRANCH_ID, "version": document["version"]},
                        )
                        results[kind] = original_factory(
                            **(
                                {
                                    "purchase_id": document["id"],
                                    "idempotency_key_header": "pg-document-confirm",
                                }
                                if family == "purchase"
                                else {
                                    "expense_id": document["id"],
                                    "idempotency_key": "pg-document-confirm",
                                }
                            ),
                            **args,
                        )
                else:
                    results[kind] = write()
            else:
                with Session(engine) as session:
                    if contender:
                        pid.append(session.scalar(sa.text("SELECT pg_backend_pid()")))
                        entered.set()
                    results[kind] = select_branch_workspace(
                        session,
                        ADMIN_USER_ID,
                        {"target_branch_id": SECOND_BRANCH_ID, "expected_authorization_version": 1},
                        "pg-document-select",
                    )
        except HTTPException as error:
            results[kind] = error.detail["code"]
        except BaseException as error:
            failures.append(error)

    loser = "select" if winner == "write" else "write"
    first, second = Thread(target=run, args=(winner,)), Thread(target=run, args=(loser, True))
    first.start()
    try:
        assert held.wait(8)
        second.start()
        _wait_for_document_lock(engine, pid, entered)
        assert results == {}
    finally:
        release.set()
        first.join(15)
        if second.ident:
            second.join(15)
    assert not first.is_alive() and not second.is_alive()
    assert not failures, failures
    assert results["select"]["active_branch"]["id"] == SECOND_BRANCH_ID
    after = _document_effects(engine, family, document["id"])
    if winner == "write":
        assert results["write"]["status"] == "confirmed"
        assert after[0]["status"] == "confirmed" and after[0]["branch_id"] == BRANCH_ID
        assert after[1] != before[1]
    else:
        assert results["write"] == "branch_context_superseded"
        assert after == before


@pytest.mark.parametrize("family", ["purchase", "expense"])
def test_document_confirmation_commits_before_authority_version_change(
    context_engine, monkeypatch, family
):
    engine, initial = context_engine
    document, write = _document_confirmation(engine, family, initial)
    held, release, entered = Event(), Event(), Event()
    pid, results, failures = [], [], []
    original = workspace_fences._branch_context

    def hold(*args, **kwargs):
        original(*args, **kwargs)
        held.set()
        assert release.wait(8), "Confirmation was not released"

    monkeypatch.setattr(workspace_fences, "_branch_context", hold)

    def confirmation():
        try:
            results.append(write())
        except BaseException as error:
            failures.append(error)

    def authority():
        try:
            with Session(engine) as session:
                pid.append(session.scalar(sa.text("SELECT pg_backend_pid()")))
                entered.set()
                ops._authority_governance_lock(session)
                ops._bump_authority_versions(session, [ADMIN_USER_ID])
                session.commit()
        except BaseException as error:
            failures.append(error)

    first, second = Thread(target=confirmation), Thread(target=authority)
    first.start()
    try:
        assert held.wait(8)
        second.start()
        _wait_for_document_lock(engine, pid, entered)
        assert results == []
    finally:
        release.set()
        first.join(15)
        if second.ident:
            second.join(15)
    assert not first.is_alive() and not second.is_alive()
    assert not failures, failures
    assert results[0]["status"] == "confirmed"
    before = _document_effects(engine, family, document["id"])
    with pytest.raises(HTTPException) as rejected:
        write()
    assert rejected.value.status_code == 403
    assert rejected.value.detail["code"] == "authorization_version_conflict"
    assert _document_effects(engine, family, document["id"]) == before
