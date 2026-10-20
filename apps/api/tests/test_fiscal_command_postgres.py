"""Actual PostgreSQL preparation races and guarded migration rollback."""

import time
from datetime import datetime, timezone
from threading import Event, Thread, current_thread
from uuid import uuid4

import pytest
import sqlalchemy as sa
from fiscal_test_support import configuration_payload
from restaurant_os import models, operations
from restaurant_os.invoicing import commands, emitters
from sqlalchemy.orm import Session
from test_corporate_purchases_postgres import pg_engine as pg_engine
from test_fiscal_authority_postgres import _postgres_alembic
from test_fiscal_authority_postgres import migrated_fiscal_engine as migrated_fiscal_engine
from test_fiscal_command_preparation import RECEIVER
from test_fiscal_emitter_postgres import encryption as encryption
from test_platform_api import ADMIN_ROLE_ID, ADMIN_USER_ID, BRANCH_ID, _seed


def _seed_preparation(engine):
    now, order, shift, payment = (
        datetime.now(timezone.utc),
        str(uuid4()),
        str(uuid4()),
        str(uuid4()),
    )
    with Session(engine) as session:
        for code in ("invoicing.config.manage", "invoicing.issue"):
            permission = str(uuid4())
            session.execute(
                models.permissions.insert().values(
                    id=permission,
                    code=code,
                    description=code,
                    created_at=now,
                )
            )
            session.execute(
                models.role_permissions.insert().values(
                    role_id=ADMIN_ROLE_ID,
                    permission_id=permission,
                )
            )
        legal = session.scalar(
            sa.select(models.branches.c.legal_entity_id).where(models.branches.c.id == BRANCH_ID)
        )
        session.execute(
            models.legal_entities.update()
            .where(models.legal_entities.c.id == legal)
            .values(tax_id="KIW210101ABC")
        )
        session.execute(
            models.cash_shifts.insert().values(
                id=shift,
                organization_id=operations.ORGANIZATION_ID,
                branch_id=BRANCH_ID,
                register_code="FISCAL-PG",
                status="CLOSED",
                opening_cash_cents=0,
                opened_at=now,
                closed_at=now,
                created_at=now,
            )
        )
        session.execute(
            models.orders.insert().values(
                id=order,
                organization_id=operations.ORGANIZATION_ID,
                branch_id=BRANCH_ID,
                cash_shift_id=shift,
                folio="FISCAL-PG-0087",
                channel="POS",
                status="COMPLETED",
                total_cents=1999,
                currency="MXN",
                created_at=now,
            )
        )
        session.execute(
            models.payments.insert().values(
                id=payment,
                organization_id=operations.ORGANIZATION_ID,
                branch_id=BRANCH_ID,
                order_id=order,
                cash_shift_id=shift,
                method="cash",
                status="CONFIRMED",
                amount_cents=1999,
                currency="MXN",
                confirmed_at=now,
                created_at=now,
            )
        )
        session.commit()
        emitters.save_configuration(session, ADMIN_USER_ID, legal, configuration_payload())
    return order


@pytest.mark.parametrize("same_key", [True, False], ids=["exact-replay", "conflicting-intention"])
def test_prepare_serializes_on_observed_pg_lock_and_preserves_one_intention(
    pg_engine,
    encryption,
    monkeypatch,
    same_key,
):
    order = _seed_preparation(pg_engine)
    staged, release, started = Event(), Event(), Event()
    results, failures, pids = [], [], []
    original = commands._audit

    def hold(session, **kwargs):
        if current_thread().name == "fiscal-prepare-first" and kwargs["action"].endswith(
            "prepared"
        ):
            staged.set()
            assert release.wait(12)
        original(session, **kwargs)

    monkeypatch.setattr(commands, "_audit", hold)

    def prepare(second=False):
        try:
            with Session(pg_engine) as session:
                if second:
                    pids.append(session.scalar(sa.text("SELECT pg_backend_pid()")))
                    started.set()
                result = commands.prepare_issue(
                    session,
                    operations.ORGANIZATION_ID,
                    BRANCH_ID,
                    [order],
                    RECEIVER,
                    actor=ADMIN_USER_ID,
                    idempotency_key=(
                        "different-pg-intent" if second and not same_key else "same-pg-intent"
                    ),
                )
                results.append(result)
        except Exception as exc:
            failures.append(exc)

    first = Thread(target=prepare, name="fiscal-prepare-first")
    second = Thread(target=prepare, kwargs={"second": True}, name="fiscal-prepare-second")
    first.start()
    try:
        assert staged.wait(8)
        second.start()
        assert started.wait(3)
        deadline, observed = time.monotonic() + 5, False
        while time.monotonic() < deadline:
            with pg_engine.connect() as connection:
                observed = connection.scalar(
                    sa.text("SELECT wait_event_type='Lock' FROM pg_stat_activity WHERE pid=:pid"),
                    {"pid": pids[0]},
                )
            if observed:
                break
            time.sleep(0.02)
        assert observed, "Competing fiscal preparation never waited on an actual PostgreSQL lock"
    finally:
        release.set()
        first.join(15)
        if second.ident is not None:
            second.join(15)
    assert not first.is_alive() and not second.is_alive()
    if same_key:
        assert failures == [] and len(results) == 2 and results[0] == results[1]
    else:
        assert len(results) == 1 and len(failures) == 1
        assert isinstance(failures[0], operations.BusinessError)
        assert failures[0].code == "fiscal_order_reserved"
    with pg_engine.connect() as connection:
        for table in (
            models.fiscal_commands,
            models.fiscal_command_orders,
            models.fiscal_order_reservations,
            models.fiscal_command_outbox,
        ):
            assert connection.scalar(sa.select(sa.func.count()).select_from(table)) == 1
        retained_tables = (
            models.fiscal_commands,
            models.fiscal_command_orders,
            models.fiscal_order_reservations,
            models.fiscal_command_outbox,
            models.offline_authorization_rollouts,
            models.offline_authorization_leases,
            models.offline_authorization_cutovers,
            models.operational_command_intents,
        )
        before = {
            table.name: [dict(row) for row in connection.execute(sa.select(table)).mappings()]
            for table in retained_tables
        }
        assert before[models.offline_authorization_rollouts.name]
        head_before = connection.scalar(sa.text("SELECT version_num FROM alembic_version"))
        assert head_before == "0098_mobile_customer_profile"
    # All sessions are closed before Alembic needs a DDL lock.
    url = pg_engine.url.render_as_string(hide_password=False)
    pg_engine.dispose()
    blocked = _postgres_alembic(url, "downgrade", "0086_fiscal_emitters")
    # Head includes the seeded clean-install rollout: 0088 must preserve that evidence first.
    assert blocked.returncode != 0 and "0088 downgrade blocked" in blocked.stderr
    with pg_engine.connect() as connection:
        assert connection.scalar(sa.text("SELECT version_num FROM alembic_version")) == head_before
        for table in retained_tables:
            assert [dict(row) for row in connection.execute(sa.select(table)).mappings()] == (
                before[table.name]
            )


def test_0087_fiscal_history_blocks_downgrade(migrated_fiscal_engine, encryption):
    engine, url = migrated_fiscal_engine
    result = _postgres_alembic(url, "upgrade", "0087_fiscal_commands")
    assert result.returncode == 0, result.stdout + result.stderr
    with engine.begin() as connection:
        names = [
            name for name in sa.inspect(connection).get_table_names() if name != "alembic_version"
        ]
        quoted = ", ".join(connection.dialect.identifier_preparer.quote(name) for name in names)
        connection.execute(sa.text("TRUNCATE TABLE " + quoted + " RESTART IDENTITY CASCADE"))
    with Session(engine) as session:
        _seed(session)
    order = _seed_preparation(engine)
    with Session(engine) as session:
        commands.prepare_issue(
            session,
            operations.ORGANIZATION_ID,
            BRANCH_ID,
            [order],
            RECEIVER,
            actor=ADMIN_USER_ID,
            idempotency_key="historical-0087-downgrade",
        )
    with engine.connect() as connection:
        tables = (
            models.fiscal_commands,
            models.fiscal_command_orders,
            models.fiscal_order_reservations,
            models.fiscal_command_outbox,
        )
        before = {
            table.name: [dict(row) for row in connection.execute(sa.select(table)).mappings()]
            for table in tables
        }
        assert all(len(rows) == 1 for rows in before.values())
        assert not sa.inspect(connection).has_table("offline_authorization_rollouts")
    engine.dispose()
    blocked = _postgres_alembic(url, "downgrade", "0086_fiscal_emitters")
    assert blocked.returncode != 0 and "0087 downgrade blocked" in blocked.stderr
    with engine.connect() as connection:
        assert connection.scalar(sa.text("SELECT version_num FROM alembic_version")) == (
            "0087_fiscal_commands"
        )
        for table in tables:
            assert [dict(row) for row in connection.execute(sa.select(table)).mappings()] == (
                before[table.name]
            )


def test_pending_replay_serializes_actual_branch_deactivation(pg_engine, encryption, monkeypatch):
    order = _seed_preparation(pg_engine)
    staged, release, writer_started = Event(), Event(), Event()
    results, failures, writer_pids = [], [], []
    original = commands._public

    def prepare(session):
        return commands.prepare_issue(
            session,
            operations.ORGANIZATION_ID,
            BRANCH_ID,
            [order],
            RECEIVER,
            actor=ADMIN_USER_ID,
            idempotency_key="replay-branch-governance-qa",
        )

    with Session(pg_engine) as session:
        first = prepare(session)

    def hold(session, row):
        staged.set()
        assert release.wait(15)
        return original(session, row)

    monkeypatch.setattr(commands, "_public", hold)

    def reader():
        try:
            with Session(pg_engine) as session:
                results.append(prepare(session))
        except Exception as exc:
            failures.append(exc)

    def deactivate():
        try:
            with Session(pg_engine) as session:
                writer_pids.append(session.scalar(sa.text("SELECT pg_backend_pid()")))
                writer_started.set()
                operations.delete_branch(session, BRANCH_ID, actor_user_id=ADMIN_USER_ID)
        except Exception as exc:
            failures.append(exc)

    replay = Thread(target=reader, name="audit-fiscal-replay")
    writer = Thread(target=deactivate, name="audit-fiscal-deactivate")
    replay.start()
    try:
        assert staged.wait(6)
        writer.start()
        assert writer_started.wait(3)
        deadline, observed = time.monotonic() + 5, False
        while time.monotonic() < deadline:
            with pg_engine.connect() as connection:
                observed = connection.scalar(
                    sa.text("SELECT wait_event_type='Lock' FROM pg_stat_activity WHERE pid=:pid"),
                    {"pid": writer_pids[0]},
                )
            if observed:
                break
            time.sleep(0.02)
        assert observed, "Branch deactivation did not wait for the authorized fiscal replay"
    finally:
        release.set()
        replay.join(15)
        if writer.ident is not None:
            writer.join(15)
    assert not replay.is_alive() and not writer.is_alive()
    assert failures == [] and results == [first]
    with Session(pg_engine) as session:
        assert (
            session.scalar(
                sa.select(models.branches.c.status).where(models.branches.c.id == BRANCH_ID)
            )
            == "inactive"
        )
        with pytest.raises(operations.AuthorizationError):
            prepare(session)


def test_source_writer_can_audit_while_prepare_waits_for_order(pg_engine, encryption):
    order = _seed_preparation(pg_engine)
    started = Event()
    results, failures, pids = [], [], []

    def prepare():
        try:
            with Session(pg_engine) as session:
                pids.append(session.scalar(sa.text("SELECT pg_backend_pid()")))
                started.set()
                results.append(
                    commands.prepare_issue(
                        session,
                        operations.ORGANIZATION_ID,
                        BRANCH_ID,
                        [order],
                        RECEIVER,
                        actor=ADMIN_USER_ID,
                        idempotency_key="source-writer-audit-qa",
                    )
                )
        except Exception as exc:
            failures.append(exc)

    thread = Thread(target=prepare, name="fiscal-waiting-for-source")
    with Session(pg_engine) as writer:
        writer.execute(
            sa.select(models.orders.c.id).where(models.orders.c.id == order).with_for_update()
        ).scalar_one()
        thread.start()
        try:
            assert started.wait(3)
            deadline, observed = time.monotonic() + 5, False
            while time.monotonic() < deadline:
                with pg_engine.connect() as connection:
                    observed = connection.scalar(
                        sa.text(
                            "SELECT wait_event_type='Lock' FROM pg_stat_activity WHERE pid=:pid"
                        ),
                        {"pid": pids[0]},
                    )
                if observed:
                    break
                time.sleep(0.02)
            assert observed, "Preparation never waited for the source order writer"
            # Match the canonical source writer -> audit/FK pattern. Identity locks
            # must permit FK KEY SHARE, otherwise both transactions form a cycle.
            writer.execute(sa.text("SET LOCAL lock_timeout='1000ms'"))
            operations._audit(
                writer,
                action="fiscal.test_source_writer",
                entity_type="order",
                entity_id=order,
                actor_user_id=ADMIN_USER_ID,
                branch_id=BRANCH_ID,
                payload={"source_lock_verified": True},
            )
            writer.commit()
        finally:
            writer.rollback()
            thread.join(15)
    assert not thread.is_alive() and failures == [] and len(results) == 1
    assert results[0]["total_cents"] == 1999 and results[0]["dispatch_ready"] is False


def test_source_writer_can_audit_without_governance_fk_deadlock(pg_engine, encryption, monkeypatch):
    order = _seed_preparation(pg_engine)
    source_locked, preparation_locked = Event(), Event()
    results, failures = [], []
    original = commands.payment_snapshot

    def waiting_snapshot(session, *args):
        preparation_locked.set()
        return original(session, *args)

    monkeypatch.setattr(commands, "payment_snapshot", waiting_snapshot)

    def source_writer():
        try:
            with Session(pg_engine) as session:
                session.scalar(
                    sa.select(models.orders.c.id)
                    .where(models.orders.c.id == order)
                    .with_for_update()
                )
                source_locked.set()
                assert preparation_locked.wait(12)
                operations._audit(
                    session,
                    action="synthetic.source-writer.audit",
                    entity_type="order",
                    entity_id=order,
                    payload={"synthetic": True},
                    branch_id=BRANCH_ID,
                    actor_user_id=ADMIN_USER_ID,
                )
                session.commit()
        except Exception as exc:
            failures.append(exc)

    def preparation():
        try:
            with Session(pg_engine) as session:
                results.append(
                    commands.prepare_issue(
                        session,
                        operations.ORGANIZATION_ID,
                        BRANCH_ID,
                        [order],
                        RECEIVER,
                        actor=ADMIN_USER_ID,
                        idempotency_key="source-audit-compatibility-qa",
                    )
                )
        except Exception as exc:
            failures.append(exc)

    writer = Thread(target=source_writer, name="audit-source-writer")
    prepared = Thread(target=preparation, name="audit-preparation-source-reader")
    writer.start()
    try:
        assert source_locked.wait(5)
        prepared.start()
    finally:
        writer.join(18)
        if prepared.ident is not None:
            prepared.join(18)
    assert not writer.is_alive() and not prepared.is_alive()
    assert failures == [], "Governance/source lock order blocked audit or fiscal preparation"
    assert len(results) == 1
    with pg_engine.connect() as connection:
        assert (
            connection.scalar(
                sa.select(sa.func.count())
                .select_from(models.audit_events)
                .where(models.audit_events.c.action == "synthetic.source-writer.audit")
            )
            == 1
        )
