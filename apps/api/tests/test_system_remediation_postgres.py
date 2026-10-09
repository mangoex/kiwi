"""AUD-CORE-001 real database races in an exclusively local test schema."""

import os
import time
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event, local
from uuid import uuid4

import pytest
import sqlalchemy as sa
from restaurant_os import models, operations
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from test_platform_api import ADMIN_USER_ID, BRANCH_ID, _seed
from test_purchase_workspace import ITEM_ID, _presentation, _purchase_payload


@pytest.fixture
def pg_engine():
    url = os.environ.get("AUDCORE_TEST_POSTGRES_URL")
    if not url:
        if os.environ.get("CI"):
            pytest.fail("Mandatory AUDCORE_TEST_POSTGRES_URL is missing")
        pytest.skip("AUDCORE_TEST_POSTGRES_URL is required for the real database gate")
    parsed = make_url(url)
    if (
        not parsed.drivername.startswith("postgresql")
        or parsed.host not in {"localhost", "127.0.0.1"}
        or not (parsed.database or "").startswith("audcore_")
        or parsed.query
    ):
        raise RuntimeError("AUD-CORE tests require an exclusive local audcore_* database")
    schema = "audcore_" + uuid4().hex
    admin = sa.create_engine(url)
    with admin.begin() as conn:
        conn.execute(sa.text(f'CREATE SCHEMA "{schema}"'))
    engine = sa.create_engine(
        url,
        connect_args={
            "options": f"-c search_path={schema} -c statement_timeout=20000 -c lock_timeout=15000"
        },
    )
    try:
        models.metadata.create_all(engine)
        with Session(engine) as session:
            _seed(session)
        yield engine
    finally:
        engine.dispose()
        with admin.begin() as conn:
            conn.execute(sa.text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


def purchase_seed(engine, cash=False):
    with Session(engine) as session:
        supplier = operations.create_supplier(
            session, {"code": "AUD-PG", "commercial_name": "Audit fixture"}, ADMIN_USER_ID
        )
        presentation = operations.create_purchase_presentation(
            session, _presentation(supplier["id"]), ADMIN_USER_ID
        )
        payload = _purchase_payload(supplier["id"], presentation["id"])
        if cash:
            payload.update(payment_method="cash", paid_from_cash=True)
        return operations.create_purchase_document(session, payload, ADMIN_USER_ID)


@pytest.mark.parametrize("corrupt", [False, True])
def test_historical_diagnostic_snapshot_is_read_only_and_detects_corruption(pg_engine, corrupt):
    from restaurant_os.system_diagnostics import diagnose, readonly_snapshot
    from test_system_diagnostics import fingerprint

    purchase = purchase_seed(pg_engine, cash=True)
    open_shift(pg_engine)
    with Session(pg_engine) as session:
        operations.confirm_purchase_document(
            session, purchase["id"], "diagnostic-pg-confirm", "CAJA-01", ADMIN_USER_ID
        )
    if corrupt:
        with pg_engine.begin() as connection:
            connection.execute(
                models.purchase_documents.update()
                .where(models.purchase_documents.c.id == purchase["id"])
                .values(paid_from_cash=False)
            )
    before = fingerprint(pg_engine)
    report = diagnose(pg_engine, operations.ORGANIZATION_ID)
    assert bool(report["findings"]) == corrupt
    assert report["repairs_performed"] is False
    assert fingerprint(pg_engine) == before
    with readonly_snapshot(pg_engine) as connection:
        assert connection.exec_driver_sql("SHOW transaction_read_only").scalar_one() == "on"
        with pytest.raises(sa.exc.DBAPIError):
            connection.execute(models.purchase_documents.delete())
    assert fingerprint(pg_engine) == before


def open_shift(engine):
    with Session(engine) as session:
        return operations.open_cash_shift(
            session, 200000, "CAJA-01", branch_id=BRANCH_ID, actor_user_id=ADMIN_USER_ID
        )


def test_reconciliation_midnight_and_operational_snapshot_on_postgres(pg_engine, monkeypatch):
    from datetime import datetime, timedelta, timezone

    from restaurant_os.reconciliation_reports import get_branch_daily_reconciliation

    opened_at = datetime(2026, 10, 8, 12, tzinfo=timezone.utc)
    monkeypatch.setattr(operations, "_now", lambda: opened_at)
    with pg_engine.begin() as connection:
        connection.execute(
            models.branches.update().where(models.branches.c.id == BRANCH_ID).values(timezone="UTC")
        )
    shift = open_shift(pg_engine)
    purchase = purchase_seed(pg_engine, cash=True)
    monkeypatch.setattr(operations, "_now", lambda: opened_at + timedelta(days=1))
    with Session(pg_engine) as session:
        confirmed = operations.confirm_purchase_document(
            session, purchase["id"], "report-confirm", "CAJA-01", ADMIN_USER_ID
        )
        from decimal import ROUND_HALF_UP, Decimal

        total_cents = int(
            (Decimal(str(confirmed["total"])) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        )
    monkeypatch.setattr(operations, "_now", lambda: opened_at + timedelta(days=2))
    with Session(pg_engine) as session:
        operations.close_cash_shift_operationally(
            session, shift["id"], "report-close", ADMIN_USER_ID
        )
    with Session(pg_engine) as session:
        frozen = dict(session.execute(sa.select(models.cash_shift_closures)).mappings().one())
        first = get_branch_daily_reconciliation(session, BRANCH_ID, "2026-10-08", ADMIN_USER_ID)
        second = get_branch_daily_reconciliation(session, BRANCH_ID, "2026-10-09", ADMIN_USER_ID)
        assert first["balance"]["expected_cash_in_register"] * 100 == 200000 - total_cents
        assert first["balance"]["physical_cash_count"] is None
        assert first["balance"]["difference"] is None
        assert first["population"]["frozen_shift_ids"] == [shift["id"]]
        assert first["activity"]["totals"]["supplier_expenses"] == 0
        assert second["activity"]["totals"]["supplier_expenses"] * 100 == total_cents
        assert second["balance"]["expected_cash_in_register"] == 0
        assert (
            dict(session.execute(sa.select(models.cash_shift_closures)).mappings().one()) == frozen
        )


def test_reconciliation_reader_holds_shift_share_until_projection_finishes(pg_engine):
    from restaurant_os.reconciliation_reports import get_branch_daily_reconciliation

    shift = open_shift(pg_engine)
    purchase = purchase_seed(pg_engine, cash=True)
    selected, release = Event(), Event()
    reader_pid = []
    writer_pid = []

    def after(conn, cursor, statement, parameters, context, executemany):
        if "FOR SHARE" in statement and "cash_shifts" in statement:
            selected.set()
            assert release.wait(10), "Reader was not released"

    sa.event.listen(pg_engine, "after_cursor_execute", after)

    def reader():
        with Session(pg_engine) as session:
            reader_pid.append(session.scalar(sa.text("select pg_backend_pid()")))
            zone = session.scalar(
                sa.select(models.branches.c.timezone).where(models.branches.c.id == BRANCH_ID)
            )
            from zoneinfo import ZoneInfo

            day = shift["opened_at"].astimezone(ZoneInfo(zone)).date().isoformat()
            return get_branch_daily_reconciliation(session, BRANCH_ID, day, ADMIN_USER_ID)

    def writer():
        with Session(pg_engine) as session:
            writer_pid.append(session.scalar(sa.text("select pg_backend_pid()")))
            return operations.confirm_purchase_document(
                session, purchase["id"], "share-guard-confirm", "CAJA-01", ADMIN_USER_ID
            )

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            reading = pool.submit(reader)
            assert selected.wait(10)
            writing = pool.submit(writer)
            blocked = False
            try:
                deadline = time.monotonic() + 8
                while time.monotonic() < deadline:
                    if writer_pid:
                        with pg_engine.connect() as connection:
                            blockers = connection.scalar(
                                sa.text("select pg_blocking_pids(:pid)"), {"pid": writer_pid[0]}
                            )
                        if reader_pid[0] in blockers:
                            blocked = True
                            break
                    time.sleep(0.02)
                assert blocked, "Writer did not wait on the report reader's actual PostgreSQL lock"
                assert not writing.done()
            finally:
                release.set()
            assert reading.result(timeout=10)["balance"]["expected_cash_in_register"] == 2000
            assert writing.result(timeout=10)["status"] == "confirmed"
    finally:
        release.set()
        sa.event.remove(pg_engine, "after_cursor_execute", after)


@pytest.mark.parametrize("fault", ["foreign_concept", "foreign_shift"])
def test_reconciliation_rejects_foreign_references_with_valid_fks(pg_engine, fault):
    from datetime import datetime, timedelta, timezone

    from restaurant_os.reconciliation_reports import (
        export_reconciliation_workbook,
        get_branch_daily_reconciliation,
        get_multi_branch_consolidated_report,
    )

    shift = open_shift(pg_engine)
    now = datetime(2026, 10, 9, 12, tzinfo=timezone.utc)
    foreign_org, concept, version, foreign_shift, movement = [str(uuid4()) for _ in range(5)]
    with Session(pg_engine) as session:
        session.execute(
            models.branches.update().where(models.branches.c.id == BRANCH_ID).values(timezone="UTC")
        )
        session.execute(
            models.cash_shifts.update()
            .where(models.cash_shifts.c.id == shift["id"])
            .values(opened_at=now, created_at=now)
        )
        session.execute(
            models.organizations.insert().values(
                id=foreign_org, name="PRIVATE_ORG", created_at=now, updated_at=now
            )
        )
        if fault == "foreign_concept":
            session.execute(
                models.cash_movement_concepts.insert().values(
                    id=concept,
                    organization_id=foreign_org,
                    code="PRIVATE_FOREIGN",
                    status="active",
                    created_by_user_id=ADMIN_USER_ID,
                    created_at=now,
                )
            )
            session.execute(
                models.cash_movement_concept_versions.insert().values(
                    id=version,
                    concept_id=concept,
                    version=1,
                    name="PRIVATE_PG_OTHER_ORG_CONCEPT",
                    allowed_movement_type="withdrawal",
                    requires_reference=True,
                    requires_evidence=True,
                    valid_from=now,
                    created_by_user_id=ADMIN_USER_ID,
                    created_at=now,
                )
            )
        else:
            session.execute(
                models.cash_shifts.insert().values(
                    id=foreign_shift,
                    organization_id=foreign_org,
                    branch_id=BRANCH_ID,
                    register_code="OTHER",
                    status="OPEN",
                    opening_cash_cents=0,
                    opened_at=now - timedelta(days=1),
                    created_at=now - timedelta(days=1),
                )
            )
        session.execute(
            models.cash_movements.insert().values(
                id=movement,
                organization_id=operations.ORGANIZATION_ID,
                branch_id=BRANCH_ID,
                cash_shift_id=shift["id"] if fault == "foreign_concept" else foreign_shift,
                movement_type="withdrawal" if fault == "foreign_concept" else "deposit",
                amount_cents=100,
                reason_code="TEST",
                reason="own",
                source_type="MANUAL",
                actor_user_id=ADMIN_USER_ID,
                idempotency_key="report-" + movement,
                status="confirmed",
                concept_id=concept if fault == "foreign_concept" else None,
                concept_version_id=version if fault == "foreign_concept" else None,
                reference="own",
                created_at=now,
            )
        )
        session.commit()
    with Session(pg_engine) as session:
        for read in (
            lambda: get_branch_daily_reconciliation(
                session, BRANCH_ID, "2026-10-09", ADMIN_USER_ID
            ),
            lambda: get_multi_branch_consolidated_report(
                session, "2026-10-09", "2026-10-09", BRANCH_ID, ADMIN_USER_ID
            ),
            lambda: export_reconciliation_workbook(session, BRANCH_ID, 10, 2026, ADMIN_USER_ID),
        ):
            with pytest.raises(operations.BusinessError) as error:
                read()
            assert error.value.code == "reconciliation_integrity_conflict"
            assert "PRIVATE" not in str(error.value)


@pytest.mark.parametrize("foreign_order", [False, True])
def test_payment_order_scope_preserves_distinct_capture_and_collection_shifts(
    pg_engine, foreign_order
):
    from datetime import timedelta

    from restaurant_os.reconciliation_reports import get_branch_daily_reconciliation

    collection = open_shift(pg_engine)
    capture_id, order_id, organization = str(uuid4()), str(uuid4()), str(uuid4())
    now = collection["opened_at"] + timedelta(seconds=1)
    with Session(pg_engine) as session:
        session.execute(
            models.branches.update().where(models.branches.c.id == BRANCH_ID).values(timezone="UTC")
        )
        session.execute(
            models.organizations.insert().values(
                id=organization, name="PRIVATE_ORG", created_at=now, updated_at=now
            )
        )
        session.execute(
            models.cash_shifts.insert().values(
                id=capture_id,
                organization_id=operations.ORGANIZATION_ID,
                branch_id=BRANCH_ID,
                register_code="CAPTURE",
                status="CLOSED",
                opening_cash_cents=0,
                opened_at=now - timedelta(days=1),
                closed_at=now - timedelta(hours=1),
                created_at=now - timedelta(days=1),
            )
        )
        session.execute(
            models.orders.insert().values(
                id=order_id,
                organization_id=organization if foreign_order else operations.ORGANIZATION_ID,
                branch_id=BRANCH_ID,
                cash_shift_id=capture_id,
                folio="PRIVATE_ORDER" if foreign_order else "OWN_ORDER",
                channel="POS",
                status="CLOSED",
                total_cents=1200,
                currency="MXN",
                customer_snapshot={"name": "PRIVATE_CUSTOMER"}
                if foreign_order
                else {"name": "Synthetic customer"},
                created_at=now - timedelta(days=1),
            )
        )
        session.execute(
            models.payments.insert().values(
                id=str(uuid4()),
                organization_id=operations.ORGANIZATION_ID,
                branch_id=BRANCH_ID,
                order_id=order_id,
                cash_shift_id=collection["id"],
                method="cash",
                status="CONFIRMED",
                amount_cents=1200,
                confirmed_at=now,
                created_at=now,
            )
        )
        session.commit()
    with Session(pg_engine) as session:
        if foreign_order:
            with pytest.raises(operations.BusinessError) as error:
                get_branch_daily_reconciliation(
                    session, BRANCH_ID, now.date().isoformat(), ADMIN_USER_ID
                )
            assert error.value.code == "reconciliation_integrity_conflict"
            assert "PRIVATE" not in str(error.value)
        else:
            report = get_branch_daily_reconciliation(
                session, BRANCH_ID, now.date().isoformat(), ADMIN_USER_ID
            )
            assert report["balance"]["cash_sales"] == 12
            assert report["activity"]["totals"]["cash_sales"] == 12
            assert report["balance"]["expected_cash_in_register"] == 2012


def test_historical_diagnostic_finds_orphans_of_real_cancellation_writers(pg_engine):
    from restaurant_os.system_diagnostics import diagnose
    from test_system_diagnostics import fingerprint

    purchase = purchase_seed(pg_engine, cash=True)
    open_shift(pg_engine)
    with Session(pg_engine) as session:
        operations.confirm_purchase_document(
            session, purchase["id"], "diagnostic-pg-source", "CAJA-01", ADMIN_USER_ID
        )
        operations.cancel_purchase_document(
            session, purchase["id"], "Diagnostic cancellation", ADMIN_USER_ID
        )
    assert diagnose(pg_engine, operations.ORGANIZATION_ID)["findings"] == []
    with pg_engine.begin() as connection:
        cash = dict(
            connection.execute(
                sa.select(models.cash_movements).where(
                    models.cash_movements.c.source_type == "PURCHASE_CANCELLATION"
                )
            )
            .mappings()
            .one()
        )
        for source in ("PURCHASE_CANCELLATION", "EXPENSE_CANCELLATION"):
            cash.update(
                id=source,
                source_type=source,
                source_id="missing-document",
                idempotency_key=source,
                reversal_of_id=None,
                compensates_movement_id=None,
            )
            connection.execute(models.cash_movements.insert().values(**cash))
        receipt = dict(
            connection.execute(
                sa.select(models.inventory_movements)
                .where(models.inventory_movements.c.source_type == "purchase_cancellation")
                .limit(1)
            )
            .mappings()
            .one()
        )
        receipt.update(
            id="orphan-inventory-cancellation",
            source_id="missing-document",
            idempotency_key="orphan-inventory-cancellation",
            reversal_of_id=None,
        )
        connection.execute(models.inventory_movements.insert().values(**receipt))
    before = fingerprint(pg_engine)
    report = diagnose(pg_engine, operations.ORGANIZATION_ID)
    assert {row["record_id"] for row in report["findings"]} == {
        "PURCHASE_CANCELLATION",
        "EXPENSE_CANCELLATION",
        "orphan-inventory-cancellation",
    }
    assert fingerprint(pg_engine) == before


def test_historical_diagnostic_checks_existing_reversal_sets_and_incoming_scope(pg_engine):
    from restaurant_os.system_diagnostics import diagnose
    from test_system_diagnostics import fingerprint

    purchase = purchase_seed(pg_engine, cash=True)
    open_shift(pg_engine)
    with Session(pg_engine) as session:
        operations.confirm_purchase_document(
            session, purchase["id"], "diagnostic-pg-set", "CAJA-01", ADMIN_USER_ID
        )
        operations.cancel_purchase_document(
            session, purchase["id"], "Diagnostic cancellation", ADMIN_USER_ID
        )
    assert diagnose(pg_engine, operations.ORGANIZATION_ID)["findings"] == []
    with pg_engine.begin() as connection:
        for kind, table in (
            ("cash", models.cash_movements),
            ("inventory", models.inventory_movements),
        ):
            row = dict(
                connection.execute(
                    sa.select(table)
                    .where(sa.func.upper(table.c.source_type) == "PURCHASE_CANCELLATION")
                    .limit(1)
                )
                .mappings()
                .one()
            )
            row.update(id=f"duplicate-{kind}", idempotency_key=f"duplicate-{kind}")
            if kind == "cash":
                row["compensates_movement_id"] = None
            connection.execute(table.insert().values(**row))
    before = fingerprint(pg_engine)
    report = diagnose(pg_engine, operations.ORGANIZATION_ID)
    assert {row["code"] for row in report["findings"]} >= {
        "duplicate_document_cash_reversal",
        "duplicate_document_inventory_reversal",
    }
    assert fingerprint(pg_engine) == before
    foreign_org = str(uuid4())
    foreign_ids = set()
    with pg_engine.begin() as connection:
        organization = dict(
            connection.execute(
                sa.select(models.organizations).where(
                    models.organizations.c.id == operations.ORGANIZATION_ID
                )
            )
            .mappings()
            .one()
        )
        organization.update(id=foreign_org, name="PRIVATE-FOREIGN-REVERSALS")
        connection.execute(models.organizations.insert().values(**organization))
        for kind, table in (
            ("cash", models.cash_movements),
            ("inventory", models.inventory_movements),
        ):
            connection.execute(table.delete().where(table.c.id == f"duplicate-{kind}"))
            condition = sa.func.upper(table.c.source_type) == "PURCHASE_CANCELLATION"
            foreign_ids.update(connection.execute(sa.select(table.c.id).where(condition)).scalars())
            connection.execute(table.update().where(condition).values(organization_id=foreign_org))
    before = fingerprint(pg_engine)
    report = diagnose(pg_engine, operations.ORGANIZATION_ID)
    assert {row["code"] for row in report["findings"]} >= {
        "document_cash_reversal_scope_conflict",
        "document_inventory_reversal_scope_conflict",
    }
    assert foreign_org not in str(report) and all(
        identifier not in str(report) for identifier in foreign_ids
    )
    assert fingerprint(pg_engine) == before


@pytest.mark.parametrize("cash", [False, True])
@pytest.mark.parametrize("race", ["confirm_cancel", "double_cancel"])
def test_purchase_cancel_races_preserve_one_history_and_net_effect(pg_engine, cash, race):
    purchase = purchase_seed(pg_engine, cash)
    if cash:
        open_shift(pg_engine)
    if race == "double_cancel":
        with Session(pg_engine) as session:
            operations.confirm_purchase_document(
                session, purchase["id"], "race-confirm", "CAJA-01", ADMIN_USER_ID
            )
    barrier = Barrier(2)

    def writer(index):
        barrier.wait(timeout=10)
        with Session(pg_engine) as session:
            try:
                if race == "confirm_cancel" and index == 0:
                    return operations.confirm_purchase_document(
                        session, purchase["id"], "race-confirm", "CAJA-01", ADMIN_USER_ID
                    )["status"]
                return operations.cancel_purchase_document(
                    session, purchase["id"], "Race cancellation", ADMIN_USER_ID
                )["status"]
            except operations.BusinessError as exc:
                return exc.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(writer, range(2)))
    assert "cancelled" in outcomes
    if race == "double_cancel":
        assert outcomes == ["cancelled", "cancelled"]
    else:
        assert set(outcomes) <= {"confirmed", "cancelled", "purchase_not_confirmable"}
    with Session(pg_engine) as session:
        row = operations.get_purchase_document(session, purchase["id"])
        assert row["status"] == "cancelled"
        received = row["confirmed_at"] is not None
        effects = (
            session.execute(
                sa.select(models.inventory_movements).where(
                    models.inventory_movements.c.source_id == purchase["id"]
                )
            )
            .mappings()
            .all()
        )
        assert len(effects) == (6 if received else 0)
        assert sum(m["quantity_delta"] for m in effects) == 0
        movements = (
            session.execute(
                sa.select(models.cash_movements).where(
                    models.cash_movements.c.source_id == purchase["id"]
                )
            )
            .mappings()
            .all()
        )
        assert len(movements) == (2 if received and cash else 0)
        if movements:
            original = next(m for m in movements if m["movement_type"] == "withdrawal")
            refund = next(m for m in movements if m["movement_type"] == "deposit")
            assert refund["reversal_of_id"] == original["id"]
            assert refund["amount_cents"] == original["amount_cents"]
        assert (
            session.scalar(
                sa.select(sa.func.count())
                .select_from(models.audit_events)
                .where(
                    models.audit_events.c.entity_id == purchase["id"],
                    models.audit_events.c.action == "purchase.cancelled",
                )
            )
            == 1
        )


def test_purchase_branch_lock_permits_manual_cash_foreign_key(pg_engine, monkeypatch):
    from test_cash_concepts import _concept_payload

    purchase = purchase_seed(pg_engine, cash=True)
    open_shift(pg_engine)
    with Session(pg_engine) as session:
        from test_platform_api import ADMIN_ROLE_ID

        for code in ("cash.concept.manage", "cash.concept.read", "cash.movement.withdraw"):
            pid = session.scalar(
                sa.select(models.permissions.c.id).where(models.permissions.c.code == code)
            )
            if pid is None:
                pid = str(uuid4())
                session.execute(
                    models.permissions.insert().values(
                        id=pid, code=code, description="Fixture", created_at=operations._now()
                    )
                )
            granted = session.scalar(
                sa.select(models.role_permissions.c.permission_id).where(
                    models.role_permissions.c.role_id == ADMIN_ROLE_ID,
                    models.role_permissions.c.permission_id == pid,
                )
            )
            if granted is None:
                session.execute(
                    models.role_permissions.insert().values(
                        role_id=ADMIN_ROLE_ID, permission_id=pid
                    )
                )
        session.commit()
        concept = operations.create_cash_concept(
            session,
            _concept_payload(),
            "aud-concept",
            actor_user_id=ADMIN_USER_ID,
        )
    manual_holds_shift, purchase_holds_branch = Event(), Event()
    original_guard = operations._guard_open_cash_shift

    def guard(session, *args, **kwargs):
        if session.info.get("manual"):
            shift = original_guard(session, *args, **kwargs)
            manual_holds_shift.set()
            assert purchase_holds_branch.wait(10)
            return shift
        purchase_holds_branch.set()
        return original_guard(session, *args, **kwargs)

    monkeypatch.setattr(operations, "_guard_open_cash_shift", guard)

    def manual():
        with Session(pg_engine) as session:
            session.info["manual"] = True
            return operations.create_cash_movement(
                session,
                {
                    "branch_id": BRANCH_ID,
                    "register_id": "CAJA-01",
                    "movement_type": "withdrawal",
                    "concept_id": concept["id"],
                    "amount_cents": 100,
                    "reference": "Test",
                    "evidence_refs": ["evidence://audcore/manual"],
                },
                "aud-manual",
                ADMIN_USER_ID,
            )

    def confirm():
        assert manual_holds_shift.wait(10)
        with Session(pg_engine) as session:
            return operations.confirm_purchase_document(
                session, purchase["id"], "aud-fk-confirm", "CAJA-01", ADMIN_USER_ID
            )

    with ThreadPoolExecutor(max_workers=2) as pool:
        first, second = pool.submit(manual), pool.submit(confirm)
        assert first.result(timeout=25)["movement"]["status"] == "confirmed"
        assert second.result(timeout=25)["status"] == "confirmed"


def test_cancel_winner_prevents_manual_compensation_from_stale_precheck(pg_engine, monkeypatch):
    from test_platform_api import ADMIN_ROLE_ID

    purchase = purchase_seed(pg_engine, cash=True)
    open_shift(pg_engine)
    with Session(pg_engine) as session:
        session.execute(
            models.role_authority_grants.insert().values(
                role_id=ADMIN_ROLE_ID,
                authority_kind="organization_all_permissions",
                created_at=operations._now(),
            )
        )
        if (
            session.scalar(
                sa.select(models.permissions.c.id).where(
                    models.permissions.c.code == "cash.movement.compensate"
                )
            )
            is None
        ):
            session.execute(
                models.permissions.insert().values(
                    id=str(uuid4()),
                    code="cash.movement.compensate",
                    description="Fixture",
                    created_at=operations._now(),
                )
            )
        session.commit()
        confirmed = operations.confirm_purchase_document(
            session, purchase["id"], "aud-manual-race-confirm", "CAJA-01", ADMIN_USER_ID
        )
    before_guard, cancellation_committed = Event(), Event()
    original_guard = operations._guard_open_cash_shift

    def guard(session, *args, **kwargs):
        if session.info.get("manual_compensation"):
            before_guard.set()
            assert cancellation_committed.wait(15)
        return original_guard(session, *args, **kwargs)

    monkeypatch.setattr(operations, "_guard_open_cash_shift", guard)

    def manual():
        with Session(pg_engine) as session:
            session.info["manual_compensation"] = True
            try:
                operations.compensate_cash_movement(
                    session,
                    confirmed["cash_movement_id"],
                    {"reason": "Real refund", "evidence_refs": ["evidence://audcore/refund"]},
                    "aud-manual-race-refund",
                    ADMIN_USER_ID,
                )
                return "confirmed"
            except operations.BusinessError as exc:
                session.rollback()
                return exc.code

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(manual)
        try:
            assert before_guard.wait(15), "Manual compensation must reach the shift guard"
            with Session(pg_engine) as session:
                cancelled = operations.cancel_purchase_document(
                    session, purchase["id"], "Real refund", ADMIN_USER_ID
                )
                assert cancelled["status"] == "cancelled"
        finally:
            cancellation_committed.set()
        outcome = future.result(timeout=25)
    assert outcome == "cash_movement_already_compensated", outcome
    with Session(pg_engine) as session:
        returns = (
            session.execute(
                sa.select(models.cash_movements).where(
                    models.cash_movements.c.reversal_of_id == confirmed["cash_movement_id"]
                )
            )
            .mappings()
            .all()
        )
        assert len(returns) == 1
        assert returns[0]["source_type"] == "PURCHASE_CANCELLATION"


@pytest.mark.parametrize("cash", [False, True])
def test_maximum_confirmation_key_keeps_effect_keys_within_database_limit(pg_engine, cash):
    purchase = purchase_seed(pg_engine, cash)
    if cash:
        open_shift(pg_engine)
    with Session(pg_engine) as session:
        result = operations.confirm_purchase_document(
            session, purchase["id"], "k" * 180, "CAJA-01", ADMIN_USER_ID
        )
        assert result["status"] == "confirmed"
        keys = session.scalars(
            sa.select(models.inventory_movements.c.idempotency_key).where(
                models.inventory_movements.c.source_id == purchase["id"]
            )
        ).all()
        assert len(keys) == len(set(keys)) == 3
        assert all(len(key) <= 180 for key in keys)
        if cash:
            assert len(session.scalar(sa.select(models.cash_movements.c.idempotency_key))) <= 180


def production_fixture(engine):
    purchase = purchase_seed(engine)
    with Session(engine) as session:
        original = dict(
            session.execute(
                sa.select(models.inventory_movements).where(
                    models.inventory_movements.c.item_id == ITEM_ID
                )
            )
            .mappings()
            .first()
        )
        quantity = session.scalar(
            sa.select(sa.func.sum(models.inventory_movements.c.quantity_delta)).where(
                models.inventory_movements.c.item_id == ITEM_ID
            )
        )
        original.update(
            id=str(uuid4()),
            quantity_delta=-quantity,
            total_cost=0,
            movement_type="SALE_CONSUMPTION",
            source_type="audit_fixture",
            source_id=None,
            idempotency_key=str(uuid4()),
        )
        session.execute(models.inventory_movements.insert().values(**original))
        session.commit()
        operations.confirm_purchase_document(
            session, purchase["id"], "kds-confirm", None, ADMIN_USER_ID
        )
    open_shift(engine)
    with Session(engine) as session:
        product = session.scalar(
            sa.select(models.recipes.c.product_id)
            .join(
                models.recipe_components,
                models.recipe_components.c.recipe_id == models.recipes.c.id,
            )
            .where(models.recipe_components.c.item_id == ITEM_ID)
            .limit(1)
        )
        order = operations.create_local_order(
            session,
            [{"product_id": product, "quantity": 1}],
            branch_id=BRANCH_ID,
            actor_user_id=ADMIN_USER_ID,
        )
        snapshot = (
            session.execute(
                sa.select(models.order_line_consumption_snapshots).where(
                    models.order_line_consumption_snapshots.c.order_id == order["id"]
                )
            )
            .mappings()
            .first()
        )
        components = [dict(c) for c in snapshot["components"] if c["item_id"] == ITEM_ID]
        components[0].update(gross_quantity="10", total_cost="0", unit_cost="0")
        session.execute(
            models.order_line_consumption_snapshots.update()
            .where(
                models.order_line_consumption_snapshots.c.order_line_id == snapshot["order_line_id"]
            )
            .values(components=components)
        )
        task = session.scalar(
            sa.select(models.production_tasks.c.id).where(
                models.production_tasks.c.order_id == order["id"]
            )
        )
        session.commit()
        operations.advance_kds_task(
            session, task, "IN_PROGRESS", BRANCH_ID, actor_user_id=ADMIN_USER_ID
        )
    return purchase, task


def test_real_kds_consumption_winner_blocks_purchase_cancellation_without_partial_effects(
    pg_engine,
):
    purchase, task = production_fixture(pg_engine)
    with Session(pg_engine) as session:
        operations.advance_kds_task(
            session, task, "COMPLETED", BRANCH_ID, actor_user_id=ADMIN_USER_ID
        )
        before = list(session.execute(sa.select(models.inventory_movements)).mappings())
        with pytest.raises(operations.BusinessError) as error:
            operations.cancel_purchase_document(
                session, purchase["id"], "KDS winner", ADMIN_USER_ID
            )
        assert error.value.code == "purchase_reversal_insufficient_stock"
        session.commit()
        assert list(session.execute(sa.select(models.inventory_movements)).mappings()) == before
        assert operations.get_purchase_document(session, purchase["id"])["status"] == "confirmed"


def test_real_kds_waits_for_purchase_branch_serialization(pg_engine, monkeypatch):
    purchase, task = production_fixture(pg_engine)
    ready, release, kds_started = Event(), Event(), Event()
    quantity = operations._physical_inventory_quantity
    fence = operations._require_order_write_fence
    application = "audcore-kds-" + uuid4().hex

    def pause(session, *args):
        result = quantity(session, *args)
        if session.info.get("cancel") and args[-1] == ITEM_ID:
            ready.set()
            assert release.wait(15)
        return result

    def observe_fence(session, branch):
        if session.info.get("kds"):
            kds_started.set()
        return fence(session, branch)

    monkeypatch.setattr(operations, "_physical_inventory_quantity", pause)
    monkeypatch.setattr(operations, "_require_order_write_fence", observe_fence)

    def cancel():
        with Session(pg_engine) as session:
            session.info["cancel"] = True
            return operations.cancel_purchase_document(
                session, purchase["id"], "Serialized", ADMIN_USER_ID
            )

    def complete():
        with Session(pg_engine) as session:
            session.execute(
                sa.text("SELECT set_config('application_name', :name, false)"),
                {"name": application},
            )
            session.info["kds"] = True
            return operations.advance_kds_task(
                session, task, "COMPLETED", BRANCH_ID, actor_user_id=ADMIN_USER_ID
            )

    with ThreadPoolExecutor(max_workers=2) as pool:
        cancelled = pool.submit(cancel)
        try:
            assert ready.wait(10)
            completed = pool.submit(complete)
            assert kds_started.wait(10)
            deadline = time.monotonic() + 5
            blocked = False
            with Session(pg_engine) as probe:
                while time.monotonic() < deadline:
                    probe.execute(sa.text("SELECT pg_stat_clear_snapshot()"))
                    blocked = bool(
                        probe.scalar(
                            sa.text(
                                "SELECT EXISTS(SELECT 1 FROM pg_stat_activity "
                                "WHERE application_name=:name AND wait_event_type='Lock')"
                            ),
                            {"name": application},
                        )
                    )
                    if blocked:
                        break
                    release.wait(0.05)
            assert blocked, "The real KDS writer bypassed the purchase branch lock"
        finally:
            release.set()
        assert cancelled.result(timeout=20)["status"] == "cancelled"
        assert completed.result(timeout=20)["status"] == "COMPLETED"


@pytest.mark.parametrize("same_key", [False, True])
def test_document_confirmation_race_has_one_receipt_set_and_audit(pg_engine, same_key):
    purchase = purchase_seed(pg_engine)
    barrier = Barrier(2)
    state = local()

    def before(conn, cursor, statement, parameters, context, executemany):
        if (
            not getattr(state, "seen", False)
            and statement.lstrip().startswith("SELECT")
            and "FROM purchase_documents" in statement
        ):
            state.seen = True
            state.wait_after = "FOR UPDATE" not in statement
            if not state.wait_after:
                barrier.wait(timeout=10)

    def after(conn, cursor, statement, parameters, context, executemany):
        if getattr(state, "wait_after", False):
            state.wait_after = False
            # Both unlocked reads have already executed: each baseline writer saw DRAFT.
            barrier.wait(timeout=10)

    sa.event.listen(pg_engine, "before_cursor_execute", before)
    sa.event.listen(pg_engine, "after_cursor_execute", after)

    def writer(index):
        with Session(pg_engine) as session:
            try:
                result = operations.confirm_purchase_document(
                    session,
                    purchase["id"],
                    "audcore-confirm-" + ("same" if same_key else str(index)),
                    None,
                    ADMIN_USER_ID,
                )
                return result["status"]
            except operations.BusinessError as exc:
                return exc.code

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(writer, range(2)))
    finally:
        sa.event.remove(pg_engine, "before_cursor_execute", before)
        sa.event.remove(pg_engine, "after_cursor_execute", after)
    assert outcomes.count("confirmed") == (2 if same_key else 1), outcomes
    if not same_key:
        assert outcomes.count("purchase_already_confirmed") == 1, outcomes
    with Session(pg_engine) as session:
        assert (
            session.scalar(
                sa.select(sa.func.count())
                .select_from(models.inventory_movements)
                .where(
                    models.inventory_movements.c.source_id == purchase["id"],
                    models.inventory_movements.c.movement_type == "PURCHASE_RECEIPT",
                )
            )
            == 3
        )
        assert (
            session.scalar(
                sa.select(sa.func.count())
                .select_from(models.audit_events)
                .where(
                    models.audit_events.c.action == "purchase.confirmed",
                    models.audit_events.c.entity_id == purchase["id"],
                )
            )
            == 1
        )
