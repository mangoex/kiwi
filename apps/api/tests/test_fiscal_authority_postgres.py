# SEC001-SYNTHETIC-FIXTURE provenance=restaurantos-audit-test-fiscal-authority-postgres-v1
"""FISCAL-001 actual PostgreSQL registry migration, fencing and history protection."""

import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from threading import Event, Thread, current_thread
from uuid import uuid4

import pytest
import sqlalchemy as sa
from restaurant_os import models, operations
from restaurant_os.invoicing.eligibility import payment_snapshot
from restaurant_os.invoicing.service import InvoicingService
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from test_corporate_purchases_postgres import pg_engine as pg_engine
from test_platform_api import ADMIN_USER_ID, BRANCH_ID

PREVIOUS = "0084_branch_workspaces"
REVISION = "0085_fiscal_permissions"


def _postgres_alembic(url, *arguments):
    env = {**os.environ, "RESTAURANTOS_DATABASE_URL": url}
    env.pop("DATABASE_URL", None)
    return subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "alembic.ini", *arguments],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
        timeout=120,
    )


@pytest.fixture
def migrated_fiscal_engine():
    url = os.environ.get("CORP_PUR_TEST_POSTGRES_URL")
    if not url:
        pytest.skip("CORP_PUR_TEST_POSTGRES_URL is required; configured in CI")
    parsed = make_url(url)
    if (
        not parsed.drivername.startswith("postgresql")
        or parsed.host not in {"localhost", "127.0.0.1"}
        or not (parsed.database or "").startswith("corp_pur_")
        or parsed.query
    ):
        raise RuntimeError("Fiscal tests require an isolated local corp_pur_* database")
    engine = sa.create_engine(url)
    with engine.begin() as connection:
        connection.execute(sa.text("DROP SCHEMA public CASCADE"))
        connection.execute(sa.text("CREATE SCHEMA public"))
    result = _postgres_alembic(url, "upgrade", PREVIOUS)
    assert result.returncode == 0, result.stdout + result.stderr
    yield engine, url
    engine.dispose()


def test_fiscal_registry_migration_preserves_pg_authority_and_downgrade_history(
    migrated_fiscal_engine,
):
    engine, url = migrated_fiscal_engine
    with engine.begin() as connection:
        org = connection.scalar(sa.text("SELECT id FROM organizations LIMIT 1"))
        role = connection.scalar(
            sa.text(
                "SELECT role_id FROM role_authority_grants "
                "WHERE authority_kind='organization_all_permissions' LIMIT 1"
            )
        )
        connection.execute(
            sa.text(
                "INSERT INTO users (id, organization_id, email, display_name, status, "
                "authorization_version, created_at, updated_at) VALUES "
                "('fiscal-pg-owner', :org, 'fiscal-pg@example.invalid', 'Fixture', 'active', "
                "5, '2026-10-13', '2026-10-13')"
            ),
            {"org": org},
        )
        connection.execute(
            sa.text("INSERT INTO user_roles (user_id, role_id) VALUES ('fiscal-pg-owner', :role)"),
            {"role": role},
        )
    result = _postgres_alembic(url, "upgrade", REVISION)
    assert result.returncode == 0, result.stdout + result.stderr
    with engine.begin() as connection:
        assert (
            connection.scalar(
                sa.text("SELECT authorization_version FROM users WHERE id='fiscal-pg-owner'")
            )
            == 6
        )
        assert (
            connection.scalar(
                sa.text("SELECT COUNT(*) FROM permissions WHERE code LIKE 'invoicing.%'")
            )
            == 5
        )
        assert (
            connection.scalar(
                sa.text(
                    "SELECT COUNT(*) FROM role_permissions rp "
                    "JOIN permissions p ON rp.permission_id=p.id "
                    "WHERE p.code LIKE 'invoicing.%'"
                )
            )
            == 0
        )
        connection.execute(
            sa.text(
                "INSERT INTO role_permissions (role_id, permission_id) SELECT :role, id "
                "FROM permissions WHERE code='invoicing.read'"
            ),
            {"role": role},
        )
    blocked = _postgres_alembic(url, "downgrade", PREVIOUS)
    assert blocked.returncode != 0
    assert "0085 downgrade blocked: fiscal authority or history exists" in blocked.stderr
    with engine.connect() as connection:
        assert (
            connection.scalar(
                sa.text("SELECT authorization_version FROM users WHERE id='fiscal-pg-owner'")
            )
            == 6
        )
        assert (
            connection.scalar(
                sa.text("SELECT COUNT(*) FROM permissions WHERE code LIKE 'invoicing.%'")
            )
            == 5
        )


def test_configuration_authorization_is_fenced_until_commit(pg_engine, monkeypatch):
    actor, role, config = (str(uuid4()) for _ in range(3))
    now = datetime.now(timezone.utc)
    with Session(pg_engine) as session:
        permission = session.scalar(
            sa.select(models.permissions.c.id).where(
                models.permissions.c.code == "invoicing.config.manage"
            )
        )
        if permission is None:
            permission = str(uuid4())
            session.execute(
                models.permissions.insert().values(
                    id=permission,
                    code="invoicing.config.manage",
                    description="Synthetic fiscal config",
                    created_at=now,
                )
            )
        session.execute(
            models.roles.insert().values(
                id=role,
                organization_id=operations.ORGANIZATION_ID,
                name="Synthetic fiscal configurator",
                scope="organization",
                created_at=now,
            )
        )
        session.execute(
            models.role_permissions.insert().values(role_id=role, permission_id=permission)
        )
        session.execute(
            models.users.insert().values(
                id=actor,
                organization_id=operations.ORGANIZATION_ID,
                email="sol-config-race@example.invalid",
                display_name="Synthetic configurator",
                status="active",
                authorization_version=1,
                created_at=now,
                updated_at=now,
            )
        )
        session.execute(models.user_roles.insert().values(user_id=actor, role_id=role))
        session.execute(
            models.facturapi_config.insert().values(
                id=config,
                organization_id=operations.ORGANIZATION_ID,
                is_enabled=True,
                organization_legal_name="Synthetic emitter",
                organization_rfc="SYNTHETIC",
                organization_tax_system="601",
                organization_zip="80000",
                created_at=now,
                updated_at=now,
            )
        )
        session.commit()

    authorized, release, revoke_started, revoked = Event(), Event(), Event(), Event()
    failures, backend_pid, save_result = [], [], []
    original = InvoicingService.get_config

    def pause_after_authorization(self, session, organization):
        result = original(self, session, organization)
        if current_thread().name == "sol-fiscal-save" and not authorized.is_set():
            authorized.set()
            assert release.wait(8)
        return result

    monkeypatch.setattr(InvoicingService, "get_config", pause_after_authorization)

    def save():
        try:
            with Session(pg_engine) as session:
                save_result.append(
                    InvoicingService().save_config(
                        session,
                        operations.ORGANIZATION_ID,
                        {"is_enabled": False},
                        actor_user_id=actor,
                    )
                )
        except BaseException as error:
            failures.append(error)

    def revoke():
        try:
            with Session(pg_engine) as session:
                backend_pid.append(session.scalar(sa.text("SELECT pg_backend_pid()")))
                revoke_started.set()
                operations.update_role_permissions(session, role, [], ADMIN_USER_ID)
                revoked.set()
        except BaseException as error:
            failures.append(error)

    first = Thread(target=save, name="sol-fiscal-save")
    second = Thread(target=revoke, name="sol-fiscal-revoke")
    first.start()
    waiting, overtook = False, False
    try:
        assert authorized.wait(8)
        second.start()
        assert revoke_started.wait(5)
        deadline = time.monotonic() + 4
        while time.monotonic() < deadline:
            if revoked.is_set():
                overtook = True
                break
            with pg_engine.connect() as connection:
                waiting = bool(
                    connection.scalar(
                        sa.text(
                            "SELECT wait_event_type = 'Lock' FROM pg_stat_activity WHERE pid=:pid"
                        ),
                        {"pid": backend_pid[0]},
                    )
                )
            if waiting:
                break
            time.sleep(0.02)
    finally:
        release.set()
        first.join(12)
        if second.ident:
            second.join(12)
    assert not first.is_alive() and not second.is_alive()
    assert not failures
    assert len(save_result) == 1 and revoked.is_set()
    with Session(pg_engine) as session:
        assert (
            session.scalar(
                sa.select(models.users.c.authorization_version).where(models.users.c.id == actor)
            )
            == 2
        )
        assert (
            session.scalar(
                sa.select(models.facturapi_config.c.is_enabled).where(
                    models.facturapi_config.c.id == config
                )
            )
            is False
        )
    assert not overtook and waiting, "Revocation committed before a stale-authority config write"


def test_snapshot_holds_all_source_row_locks_until_transaction_ends(pg_engine):
    now = datetime.now(timezone.utc)
    order, shift, payment, request, correction, adjustment = (str(uuid4()) for _ in range(6))
    with Session(pg_engine) as setup:
        setup.execute(
            models.orders.insert().values(
                id=order,
                organization_id=operations.ORGANIZATION_ID,
                branch_id=BRANCH_ID,
                folio="SOL-FISCAL-PG",
                channel="UBER_EATS",
                status="COMPLETED",
                total_cents=1999,
                currency="MXN",
                created_at=now,
            )
        )
        setup.execute(
            models.cash_shifts.insert().values(
                id=shift,
                organization_id=operations.ORGANIZATION_ID,
                branch_id=BRANCH_ID,
                register_code="SOL-FISCAL-PG",
                status="CLOSED",
                opening_cash_cents=0,
                opened_at=now,
                closed_at=now,
                created_at=now,
            )
        )
        setup.execute(
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
        setup.execute(
            models.order_reopen_requests.insert().values(
                id=request,
                organization_id=operations.ORGANIZATION_ID,
                branch_id=BRANCH_ID,
                order_id=order,
                status="APPLIED",
                order_version_snapshot=1,
                order_status_snapshot="COMPLETED",
                before_snapshot={"total_cents": 1999},
                reason="Synthetic correction",
                evidence_refs=["synthetic-evidence"],
                requested_by_user_id=ADMIN_USER_ID,
                requested_at=now,
                decided_by_user_id=ADMIN_USER_ID,
                decided_at=now,
                decision_reason="Authorized fixture",
                applied_by_user_id=ADMIN_USER_ID,
                applied_at=now,
                created_at=now,
                updated_at=now,
            )
        )
        setup.execute(
            models.order_corrections.insert().values(
                id=correction,
                organization_id=operations.ORGANIZATION_ID,
                branch_id=BRANCH_ID,
                order_id=order,
                request_id=request,
                folio="COR-SOL-FISCAL-PG",
                captured_order_version=1,
                resulting_order_version=1,
                before_snapshot={"total_cents": 1999},
                after_snapshot={"total_cents": 499},
                currency="MXN",
                corrected_total_cents=499,
                settlement_delta_cents=-1500,
                status="APPLIED",
                actor_user_id=ADMIN_USER_ID,
                applied_at=now,
            )
        )
        setup.execute(
            models.order_payment_adjustments.insert().values(
                id=adjustment,
                correction_id=correction,
                original_payment_id=payment,
                adjustment_type="REFUND",
                amount_cents=1500,
                method="transfer",
                currency="MXN",
                status="CONFIRMED",
                evidence_refs=["synthetic-evidence"],
                created_at=now,
            )
        )
        setup.commit()

    sources = (
        (models.orders, order, models.orders.c.version),
        (models.payments, payment, models.payments.c.amount_cents),
        (models.order_corrections, correction, models.order_corrections.c.corrected_total_cents),
        (
            models.order_payment_adjustments,
            adjustment,
            models.order_payment_adjustments.c.amount_cents,
        ),
    )
    pids, failures = {}, []
    done = {table.name: Event() for table, _, _ in sources}

    def writer(table, source_id, column):
        try:
            with Session(pg_engine) as write:
                pids[table.name] = write.scalar(sa.text("SELECT pg_backend_pid()"))
                # No-op updates provide row-lock evidence without changing source history.
                write.execute(
                    table.update().where(table.c.id == source_id).values({column.name: column})
                )
                write.commit()
                done[table.name].set()
        except BaseException as exc:
            failures.append(exc)

    threads = [Thread(target=writer, args=source, daemon=True) for source in sources]
    with Session(pg_engine) as holding:
        snapshot = payment_snapshot(holding, operations.ORGANIZATION_ID, BRANCH_ID, order)
        assert snapshot.total_cents == snapshot.paid_cents == 499
        assert snapshot.payment_ids == (payment,)
        assert snapshot.correction_ids == (correction,)
        assert snapshot.adjustment_ids == (adjustment,)
        for thread in threads:
            thread.start()
        try:
            deadline = time.monotonic() + 5
            blocked = set()
            while time.monotonic() < deadline:
                if len(pids) == len(sources):
                    with pg_engine.connect() as observer:
                        blocked = set(
                            observer.scalars(
                                sa.text(
                                    "SELECT pid FROM pg_stat_activity WHERE pid IN :pids "
                                    "AND wait_event_type = 'Lock'"
                                ).bindparams(sa.bindparam("pids", expanding=True)),
                                {"pids": list(pids.values())},
                            )
                        )
                    if blocked == set(pids.values()):
                        break
                time.sleep(0.02)
            assert len(pids) == len(sources)
            assert blocked == set(pids.values()), (pids, blocked, failures)
            assert not any(event.is_set() for event in done.values())
            assert holding.in_transaction()
        finally:
            holding.rollback()
            for thread in threads:
                thread.join(5)
    assert not failures
    assert all(event.is_set() for event in done.values())
    with Session(pg_engine) as check:
        assert payment_snapshot(check, operations.ORGANIZATION_ID, BRANCH_ID, order) == snapshot


@pytest.fixture
def fiscal_read_v2(monkeypatch):
    from restaurant_os.config import get_settings

    monkeypatch.setenv("RESTAURANTOS_BRANCH_SCOPE_V2_ENABLED", "true")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.mark.parametrize(
    "branch_status,role_scope",
    [("active", "organization"), ("inactive", "organization"), ("inactive", "branch")],
)
def test_download_reauthorization_cannot_be_overtaken_before_audit_commit(
    pg_engine, monkeypatch, branch_status, role_scope, fiscal_read_v2
):
    actor, role, permission, invoice, sat_uuid = (str(uuid4()) for _ in range(5))
    now = datetime.now(timezone.utc)
    with Session(pg_engine) as setup:
        setup.execute(
            models.permissions.insert().values(
                id=permission,
                code="invoicing.read",
                description="Synthetic download reader",
                created_at=now,
            )
        )
        setup.execute(
            models.roles.insert().values(
                id=role,
                organization_id=operations.ORGANIZATION_ID,
                name="Synthetic reader",
                scope=role_scope,
                created_at=now,
            )
        )
        setup.execute(
            models.role_permissions.insert().values(role_id=role, permission_id=permission)
        )
        setup.execute(
            models.users.insert().values(
                id=actor,
                organization_id=operations.ORGANIZATION_ID,
                email="sol-artifact@example.invalid",
                display_name="Synthetic reader",
                status="active",
                authorization_version=1,
                created_at=now,
                updated_at=now,
            )
        )
        setup.execute(
            models.user_roles.insert().values(
                user_id=actor, role_id=role, branch_id=BRANCH_ID if role_scope == "branch" else None
            )
        )
        setup.execute(
            models.facturapi_config.insert().values(
                id="download-known-legacy-origin",
                organization_id=operations.ORGANIZATION_ID,
                organization_rfc="SYN010101AAA",
                api_key="sk_test_synthetic_download_origin",
                created_at=now,
                updated_at=now,
            )
        )
        setup.execute(
            models.cfdi_invoices.insert().values(
                id=invoice,
                organization_id=operations.ORGANIZATION_ID,
                branch_id=BRANCH_ID,
                facturapi_invoice_id="remote-safe",
                uuid_sat=sat_uuid,
                folio_number="SOL",
                rfc_emisor="SYN010101AAA",
                rfc_receptor="XAXX010101000",
                nombre_receptor="Synthetic",
                codigo_postal_receptor="80000",
                regimen_fiscal_receptor="616",
                uso_cfdi="S01",
                forma_pago_sat="01",
                metodo_pago_sat="PUE",
                total_cents=1999,
                currency="MXN",
                status="issued",
                raw_sat_response={"id": "remote-safe", "uuid": sat_uuid, "status": "valid"},
                created_at=now,
            )
        )
        setup.execute(
            models.branches.update()
            .where(models.branches.c.id == BRANCH_ID)
            .values(status=branch_status)
        )
        setup.commit()

    authorized, release, revoked, resource_written = Event(), Event(), Event(), Event()
    failures, returned, pids = [], [], {}
    original_audit = operations._audit

    original_commit = Session.commit

    def commit_then_allow_revocation(session):
        downloading = session.info.pop("download_audit_probe", False)
        original_commit(session)
        if downloading:
            assert revoked.wait(8), "Revocation must win before post-commit delivery"

    def pause_audit(session, **kwargs):
        if kwargs["action"] == "invoicing.document.downloaded":
            session.info["download_audit_probe"] = True
            authorized.set()
            assert release.wait(8)
        original_audit(session, **kwargs)

    class SyntheticPAC:
        def __init__(self, session):
            self.session = session

        def download_invoice(self, *_):
            assert not self.session.in_transaction(), (
                "PostgreSQL transaction survived into network I/O"
            )
            return b"private-synthetic-file"

    monkeypatch.setattr("restaurant_os.invoicing.service._audit", pause_audit)
    monkeypatch.setattr(Session, "commit", commit_then_allow_revocation)
    monkeypatch.setattr(
        InvoicingService, "get_client", lambda self, session, _: SyntheticPAC(session)
    )

    def download():
        try:
            with Session(pg_engine) as session:
                returned.append(
                    InvoicingService().download_invoice(
                        session, operations.ORGANIZATION_ID, invoice, "pdf", actor_user_id=actor
                    )
                )
        except BaseException as error:
            failures.append(error)

    def revoke():
        try:
            with Session(pg_engine) as session:
                pids["revocation"] = session.scalar(sa.text("SELECT pg_backend_pid()"))
                operations.update_role_permissions(session, role, [], ADMIN_USER_ID)
                revoked.set()
        except BaseException as error:
            failures.append(error)

    def resource_writer():
        try:
            with Session(pg_engine) as session:
                pids["document"] = session.scalar(sa.text("SELECT pg_backend_pid()"))
                # No-op update proves the row fence without rewriting document history.
                session.execute(
                    models.cfdi_invoices.update()
                    .where(models.cfdi_invoices.c.id == invoice)
                    .values(folio_number=models.cfdi_invoices.c.folio_number)
                )
                session.commit()
                resource_written.set()
        except BaseException as error:
            failures.append(error)

    first, second, third = (
        Thread(target=download),
        Thread(target=revoke),
        Thread(target=resource_writer),
    )
    first.start()
    try:
        assert authorized.wait(8)
        second.start()
        third.start()
        deadline = time.monotonic() + 5
        blocked = set()
        while time.monotonic() < deadline:
            if len(pids) == 2:
                with pg_engine.connect() as observer:
                    blocked = set(
                        observer.scalars(
                            sa.text(
                                "SELECT pid FROM pg_stat_activity WHERE pid IN :pids "
                                "AND wait_event_type = 'Lock'"
                            ).bindparams(sa.bindparam("pids", expanding=True)),
                            {"pids": list(pids.values())},
                        )
                    )
                if blocked == set(pids.values()):
                    break
            time.sleep(0.02)
        assert len(pids) == 2 and blocked == set(pids.values()), (pids, blocked, failures)
        assert not revoked.is_set() and not resource_written.is_set()
    finally:
        release.set()
        first.join(12)
        if second.ident:
            second.join(12)
        if third.ident:
            third.join(12)
    assert not first.is_alive() and not second.is_alive() and not third.is_alive()
    assert len(failures) == 1, failures
    assert isinstance(failures[0], operations.AuthorizationError)
    assert failures[0].code == "permission_denied"
    assert returned == [], "A revocation after audit commit must still prevent delivery"
    assert revoked.is_set() and resource_written.is_set()
