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


def _reconciliation_fixture(engine, monkeypatch, tmp_path, domain):
    """Replace only this provisioned isolated fixture with canonical cash/order seeds."""
    from edge_gateway.order_outbox import OrderOutbox
    from edge_gateway.order_service import LocalOrderService
    from restaurant_os.offline_order_catalog import (
        build_catalog_snapshot,
        build_operational_seed,
        hydrate_bundle,
    )
    from restaurant_os.offline_orders import (
        acquire_gateway_lease,
        issue_order_grant,
        retain_bundle,
        sign_bundle,
    )
    from test_cash_concepts import CASHIER_ID, _seed_cash_concept_scope
    from test_cash_ledger import _grant_cash_permissions, _insert_shift, _withdrawal_concept
    from test_combo_compositions import COMBO
    from test_domain_offline_orders import _seed_combo_order_scope
    from test_pco008_cash_sync import _envelope

    with engine.begin() as connection:
        names = [
            name for name in sa.inspect(connection).get_table_names() if name != "alembic_version"
        ]
        quoted = ", ".join(connection.dialect.identifier_preparer.quote(name) for name in names)
        connection.execute(sa.text("TRUNCATE TABLE " + quoted + " RESTART IDENTITY CASCADE"))
    with Session(engine) as session:
        _seed_cash_concept_scope(session)
        _grant_cash_permissions(session, "cash.movement.withdraw", "cash.movement.deposit")
        _insert_shift(session)
        if domain == "orders":
            _seed_combo_order_scope(session)
        session.commit()
    device_id = _device(engine)
    issuer, device_key = Ed25519PrivateKey.generate(), Ed25519PrivateKey.generate()
    monkeypatch.setattr(ops, "_offline_grant_signing_material", lambda: (issuer, "qa"))
    monkeypatch.setattr(ops, "_offline_grant_keyring", lambda: {"qa": issuer.public_key()})
    with Session(engine) as session:
        if domain == "cash":
            concept = _withdrawal_concept(session)
            grant = ops.issue_offline_cash_grant(
                session,
                actor_user_id=CASHIER_ID,
                organization_id=ops.ORGANIZATION_ID,
                branch_id=BRANCH_ID,
                source_device_id=device_id,
            )["offline_grant"]
            now = datetime.now(UTC)
            return (
                CASHIER_ID,
                _envelope(
                    str(concept["id"]),
                    source_device_id=device_id,
                    offline_grant=grant,
                    occurred_at=now.isoformat(),
                    accepted_at=now.isoformat(),
                ),
                {"qa": issuer.public_key()},
                now,
            )
        now = datetime.now(UTC)
        acquire_gateway_lease(
            session,
            organization_id=ops.ORGANIZATION_ID,
            branch_id=BRANCH_ID,
            device_id=device_id,
            actor_id=ADMIN_USER_ID,
            public_key=device_key.public_key(),
            now=now,
        )
        issued = int(now.timestamp())
        bundle = sign_bundle(
            {
                "manifest": {
                    "schema_version": "ord-off/v1",
                    "organization_id": ops.ORGANIZATION_ID,
                    "branch_id": BRANCH_ID,
                    "device_id": device_id,
                    "bundle_id": str(uuid4()),
                    "lease_epoch": 1,
                    "issued_at": issued,
                    "expires_at": issued + 7200,
                },
                "catalog": build_catalog_snapshot(
                    session,
                    organization_id=ops.ORGANIZATION_ID,
                    branch_id=BRANCH_ID,
                ),
                "operational_seed": build_operational_seed(
                    session,
                    organization_id=ops.ORGANIZATION_ID,
                    branch_id=BRANCH_ID,
                    actor_ids=[ADMIN_USER_ID],
                ),
            },
            issuer,
            kid="qa",
        )
        keys = {"qa": issuer.public_key()}
        retain_bundle(session, bundle, keys, now=now)
        session.commit()
        grant = issue_order_grant(
            session,
            organization_id=ops.ORGANIZATION_ID,
            branch_id=BRANCH_ID,
            source_device_id=device_id,
            actor_id=ADMIN_USER_ID,
            bundle_id=bundle["manifest"]["bundle_id"],
            lease_epoch=1,
            capabilities=["orders.create"],
            private_key=issuer,
            kid="qa",
            now=now,
        )["grant"]
    outbox, catalog = OrderOutbox(tmp_path / "orders.db"), OrderOutbox(tmp_path / "catalog.db")
    hydrate_bundle(outbox.engine, bundle, include_operational_seed=True)
    hydrate_bundle(catalog.engine, bundle)
    local = LocalOrderService(outbox, catalog.engine, bundle, keys, device_key)
    local.execute(
        grant,
        "create",
        {"lines": [{"product_id": COMBO, "quantity": 1}], "register_id": "CAJA-01"},
        "signed-pg-order-001",
        now=now,
    )
    command = outbox.pending()[0]["envelope"]
    outbox.engine.dispose()
    catalog.engine.dispose()
    return ADMIN_USER_ID, command, keys, now


@pytest.mark.parametrize("domain", ["cash", "orders"])
@pytest.mark.parametrize("winner", ["reconciliation", "revocation"])
def test_signed_reconciliation_fence_retained_until_commit(
    pg_engine,
    monkeypatch,
    tmp_path,
    domain,
    winner,
):
    from restaurant_os import offline_orders
    from restaurant_os.config import get_settings

    monkeypatch.setenv("RESTAURANTOS_BRANCH_SCOPE_V2_ENABLED", "false")
    monkeypatch.setenv("RESTAURANTOS_SIGNED_OFFLINE_AUTHORITY_ENABLED", "true")
    get_settings.cache_clear()
    actor, command, keys, now = _reconciliation_fixture(pg_engine, monkeypatch, tmp_path, domain)
    reached, release, entered = Event(), Event(), Event()
    loser_pid = []
    insert = offline_orders._insert_reconciliation_receipt

    def hold_cash(point):
        if winner == "reconciliation" and point == "after_audit":
            reached.set()
            assert release.wait(timeout=10)

    def hold_order(*args, **kwargs):
        insert(*args, **kwargs)
        if winner == "reconciliation":
            reached.set()
            assert release.wait(timeout=10)

    monkeypatch.setattr(ops, "_pco008_fault", hold_cash)
    monkeypatch.setattr(offline_orders, "_insert_reconciliation_receipt", hold_order)

    def run(kind, losing=False):
        with Session(pg_engine) as session:
            if losing:
                loser_pid.append(session.scalar(sa.text("SELECT pg_backend_pid()")))
                entered.set()
            if kind == "revocation":
                ops._authority_governance_lock(session)
                ops._bump_authority_versions(session, [actor])
                if winner == "revocation":
                    reached.set()
                    assert release.wait(timeout=10)
                session.commit()
                return None
            if domain == "cash":
                return ops.receive_sync_command(
                    session, command, actor_device_id=command["source_device_id"]
                )
            return offline_orders.reconcile_order_command(
                session,
                command,
                keyring=keys,
                now=now,
                commit=True,
            )

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(run, winner)
            second = None
            try:
                assert reached.wait(timeout=8)
                loser = "revocation" if winner == "reconciliation" else "reconciliation"
                second = pool.submit(run, loser, True)
                assert entered.wait(timeout=5)
                deadline = time.monotonic() + 6
                observed = None
                while time.monotonic() < deadline:
                    with pg_engine.connect() as observer:
                        observed = observer.execute(
                            sa.text(
                                "SELECT wait_event_type,wait_event FROM pg_stat_activity "
                                "WHERE pid=:pid"
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
            first_result = first.result(timeout=8)
            assert second is not None
            second_result = second.result(timeout=8)
        receipt = first_result if winner == "reconciliation" else second_result
        assert receipt["status"].lower() == (
            "confirmed" if winner == "reconciliation" else "conflict"
        )
        if winner == "revocation":
            assert receipt["code"] == "offline_authorization_version_stale"
        with Session(pg_engine) as session:
            effect = models.cash_movements if domain == "cash" else models.orders
            assert session.scalar(sa.select(sa.func.count()).select_from(effect)) == (
                1 if winner == "reconciliation" else 0
            )
            assert (
                session.scalar(
                    sa.select(models.users.c.authorization_version).where(
                        models.users.c.id == actor,
                    )
                )
                == 2
            )
            replay = run("reconciliation")
            assert replay["checkpoint"] == receipt["checkpoint"]
            assert replay["status"] == receipt["status"]
    finally:
        get_settings.cache_clear()


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
