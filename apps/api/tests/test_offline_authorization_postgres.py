"""Real PostgreSQL grant/selection serialization and FK audit compatibility."""

import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Event
from uuid import uuid4

import pytest
import sqlalchemy as sa
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from restaurant_os import models
from restaurant_os import operations as ops
from restaurant_os.branch_workspaces import select_branch_workspace
from sqlalchemy.orm import Session
from test_branch_workspace_postgres import context_engine as context_engine
from test_branch_workspace_postgres import pg_engine as pg_engine
from test_corporate_purchases import SECOND_BRANCH_ID
from test_platform_api import ADMIN_USER_ID, BRANCH_ID

UTC = timezone.utc


def _device(engine):
    now = datetime.now(UTC)
    device = str(uuid4())
    with Session(engine) as session:
        session.execute(
            models.device_credentials.insert().values(
                id=device,
                organization_id=ops.ORGANIZATION_ID,
                branch_id=BRANCH_ID,
                capability="gateway.sync",
                token_hash="0" * 64,
                key_version="synthetic",
                expires_at=now + timedelta(hours=3),
                revoked_at=None,
                created_at=now,
            )
        )
        session.commit()
    return device


@pytest.mark.parametrize("winner", ["grant", "selection"])
def test_grant_and_selection_share_observed_actor_governance_fence(
    context_engine, monkeypatch, winner
):
    engine, initial = context_engine
    device = _device(engine)
    key = Ed25519PrivateKey.generate()
    monkeypatch.setattr(ops, "_offline_grant_signing_material", lambda: (key, "synthetic"))
    reached, release, entered = Event(), Event(), Event()
    loser_pid = []
    audit = ops._audit
    expected_action = (
        "auth.offline_grant_registered" if winner == "grant" else "auth.branch_selected"
    )

    def hold_audit(session, *args, **kwargs):
        if kwargs.get("action") == expected_action:
            reached.set()
            assert release.wait(timeout=10)
        return audit(session, *args, **kwargs)

    monkeypatch.setattr(ops, "_audit", hold_audit)

    def run(kind, losing=False):
        with Session(engine) as session:
            if losing:
                loser_pid.append(session.scalar(sa.text("SELECT pg_backend_pid()")))
                entered.set()
            try:
                if kind == "grant":
                    result = ops.issue_offline_cash_grant(
                        session,
                        actor_user_id=ADMIN_USER_ID,
                        organization_id=ops.ORGANIZATION_ID,
                        branch_id=BRANCH_ID,
                        source_device_id=device,
                        branch_context=initial["branch_workspace_context"],
                    )
                else:
                    result = select_branch_workspace(
                        session,
                        ADMIN_USER_ID,
                        {"target_branch_id": SECOND_BRANCH_ID, "expected_authorization_version": 1},
                        "pg-offline-authority-selection",
                    )
                return "success", result
            except (ops.BusinessError, ops.AuthorizationError) as exc:
                return "rejected", exc.code

    loser = "selection" if winner == "grant" else "grant"
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(run, winner)
        second = None
        try:
            assert reached.wait(timeout=8)
            second = pool.submit(run, loser, True)
            assert entered.wait(timeout=5)
            observed = None
            deadline = time.monotonic() + 6
            while time.monotonic() < deadline:
                with engine.connect() as observer:
                    observed = observer.execute(
                        sa.text(
                            "SELECT wait_event_type,wait_event FROM pg_stat_activity WHERE pid=:pid"
                        ),
                        {"pid": loser_pid[0]},
                    ).first()
                if observed and observed[0] == "Lock":
                    break
                time.sleep(0.05)
            assert observed and tuple(observed) == ("Lock", "advisory")
            assert not second.done()
        finally:
            release.set()
        assert first.result(timeout=8)[0] == "success"
        assert second is not None
        result = second.result(timeout=8)
        assert result == (
            "rejected",
            "branch_switch_offline_grant" if winner == "grant" else "branch_context_superseded",
        )
    with Session(engine) as session:
        rows = (
            session.execute(
                sa.select(models.branch_workspace_sessions).where(
                    models.branch_workspace_sessions.c.state == "active"
                )
            )
            .mappings()
            .all()
        )
        assert len(rows) == 1
        assert rows[0]["branch_id"] == (BRANCH_ID if winner == "grant" else SECOND_BRANCH_ID)
        assert session.scalar(
            sa.select(sa.func.count()).select_from(models.offline_authorization_leases)
        ) == (1 if winner == "grant" else 0)


def test_locked_grant_actor_allows_fk_audit_writer_without_losing_mutex(
    context_engine, monkeypatch
):
    engine, initial = context_engine
    device = _device(engine)
    key = Ed25519PrivateKey.generate()
    monkeypatch.setattr(ops, "_offline_grant_signing_material", lambda: (key, "synthetic"))
    reached, release = Event(), Event()
    audit = ops._audit

    def hold_audit(session, *args, **kwargs):
        if kwargs.get("action") == "auth.offline_grant_registered":
            reached.set()
            assert release.wait(timeout=10)
        return audit(session, *args, **kwargs)

    monkeypatch.setattr(ops, "_audit", hold_audit)

    def grant():
        with Session(engine) as session:
            return ops.issue_offline_cash_grant(
                session,
                actor_user_id=ADMIN_USER_ID,
                organization_id=ops.ORGANIZATION_ID,
                branch_id=BRANCH_ID,
                source_device_id=device,
                branch_context=initial["branch_workspace_context"],
            )

    def write_audit():
        with Session(engine) as session:
            audit(
                session,
                action="synthetic.concurrent.audit",
                entity_type="synthetic",
                entity_id=str(uuid4()),
                branch_id=BRANCH_ID,
                actor_user_id=ADMIN_USER_ID,
                payload={},
            )
            session.commit()

    with ThreadPoolExecutor(max_workers=2) as pool:
        producer = pool.submit(grant)
        try:
            assert reached.wait(timeout=8)
            writer = pool.submit(write_audit)
            writer.result(timeout=5)
            assert not producer.done()
        finally:
            release.set()
        producer.result(timeout=8)
    with Session(engine) as session:
        assert (
            session.scalar(
                sa.select(sa.func.count())
                .select_from(models.audit_events)
                .where(models.audit_events.c.action == "synthetic.concurrent.audit")
            )
            == 1
        )
