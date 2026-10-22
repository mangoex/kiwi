"""Mandatory isolated PostgreSQL capture, migration and authority evidence."""

import base64
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier, Event
from uuid import uuid4

import pytest
import sqlalchemy as sa
from restaurant_os import models
from restaurant_os import supplier_xml_imports as xml
from restaurant_os.branch_workspaces import reissue_branch_context, select_branch_workspace
from restaurant_os.config import get_settings
from restaurant_os.operations import BusinessError
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from test_branch_scope_selection import _grant_selection
from test_platform_api import ADMIN_ROLE_ID, ADMIN_USER_ID, BRANCH_ID, _seed
from test_supplier_cfdi_identity import SOURCE

ENV = "SUPPLIER_XML_TEST_POSTGRES_URL"
TABLES = (
    models.supplier_document_imports,
    models.supplier_document_import_conflicts,
    models.supplier_document_import_commands,
)


def _url():
    value = os.environ.get(ENV)
    if not value:
        pytest.fail(f"{ENV} required: PostgreSQL gate cannot be skipped")
    url = make_url(value)
    if (
        not url.drivername.startswith("postgresql")
        or url.host not in {"127.0.0.1", "localhost"}
        or not (url.database or "").startswith("supplier_xml_test_")
        or url.query
    ):
        raise RuntimeError("XML tests require an isolated loopback supplier_xml_test_* database")
    return value


def _migrate(url, action, revision):
    env = {**os.environ, "RESTAURANTOS_DATABASE_URL": url}
    env.pop("DATABASE_URL", None)
    return subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "alembic.ini", action, revision],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
        timeout=90,
    )


@pytest.fixture(scope="module")
def pg():
    url = _url()
    engine = sa.create_engine(
        url, connect_args={"options": "-c statement_timeout=15000 -c lock_timeout=10000"}
    )
    # Guard above precedes every destructive operation; this database is only a test fixture.
    with engine.begin() as connection:
        connection.execute(sa.text("DROP SCHEMA public CASCADE"))
        connection.execute(sa.text("CREATE SCHEMA public"))
    result = _migrate(url, "upgrade", "head")
    assert result.returncode == 0, result.stderr
    yield engine
    engine.dispose()


@pytest.fixture(autouse=True)
def seed(pg, monkeypatch):
    monkeypatch.setenv("RESTAURANTOS_SUPPLIER_XML_IMPORTS_ENABLED", "true")
    monkeypatch.setenv(
        "RESTAURANTOS_FISCAL_ENCRYPTION_KEYS",
        json.dumps({"test": base64.b64encode(bytes(range(32))).decode()}),
    )
    monkeypatch.setenv("RESTAURANTOS_FISCAL_ACTIVE_ENCRYPTION_KEY_ID", "test")
    get_settings.cache_clear()
    with pg.begin() as connection:
        connection.execute(sa.text("SET LOCAL statement_timeout = 60000"))
        names = [n for n in sa.inspect(connection).get_table_names() if n != "alembic_version"]
        quoted = ",".join(connection.dialect.identifier_preparer.quote(n) for n in names)
        connection.execute(sa.text("TRUNCATE " + quoted + " CASCADE"))
    with Session(pg) as session:
        _seed(session)
        session.execute(models.legal_entities.update().values(tax_id="BBB010101BBB"))
        session.commit()
    yield
    get_settings.cache_clear()


def _capture(session, key="pg-xml-1", original=SOURCE, secret=None):
    return xml.capture_original(session, ADMIN_USER_ID, BRANCH_ID, original, key, secret)


def _snapshot(connection, tables):
    return {
        t.name: list(connection.execute(sa.select(t).order_by(t.c.id)).mappings()) for t in tables
    }


def test_real_0091_roundtrip_preserves_ledgers(pg):
    result = _migrate(_url(), "downgrade", "0091_cash_lifecycle_intents")
    assert result.returncode == 0, result.stderr
    try:
        # Reflect the historical schema once: later columns do not exist at revision 0091.
        with pg.connect() as connection:
            historical = sa.MetaData()
            ledgers = tuple(sa.Table(name, historical, autoload_with=connection) for name in (
                "branches", "purchase_documents", "inventory_movements", "cash_movements",
            ))
            before = _snapshot(connection, ledgers)
            assert all(not sa.inspect(connection).has_table(t.name) for t in TABLES)
        result = _migrate(_url(), "upgrade", "head")
        assert result.returncode == 0, result.stderr
        with pg.connect() as connection:
            assert _snapshot(connection, ledgers) == before
        result = _migrate(_url(), "downgrade", "0091_cash_lifecycle_intents")
        assert result.returncode == 0, result.stderr
        with pg.connect() as connection:
            assert all(not sa.inspect(connection).has_table(t.name) for t in TABLES)
            assert _snapshot(connection, ledgers) == before
    finally:
        result = _migrate(_url(), "upgrade", "head")
        assert result.returncode == 0, result.stderr
    with pg.connect() as connection:
        assert _snapshot(connection, ledgers) == before


def test_real_downgrade_blocks_history_and_keeps_all_rows(pg):
    with Session(pg) as session:
        _capture(session)
        with pytest.raises(xml.SupplierXmlResultError):
            _capture(session, "pg-conflict", SOURCE + b" ")
    with pg.connect() as connection:
        before = _snapshot(connection, TABLES)
    result = _migrate(_url(), "downgrade", "0091_cash_lifecycle_intents")
    assert result.returncode != 0 and "downgrade blocked" in result.stderr
    with pg.connect() as connection:
        assert _snapshot(connection, TABLES) == before
        assert (
            connection.scalar(sa.text("SELECT version_num FROM alembic_version"))
            == "0102_order_exceptions"
        )


@pytest.mark.parametrize("target", ["actor", "branch", "receiver"])
def test_current_authority_and_receiver_are_locked_until_transaction_finishes(pg, target):
    with Session(pg) as held:
        entity = xml.authorize_capture(held, ADMIN_USER_ID, BRANCH_ID, None)
        table, identifier = {
            "actor": (models.users, ADMIN_USER_ID),
            "branch": (models.branches, BRANCH_ID),
            "receiver": (models.legal_entities, entity["id"]),
        }[target]
        with Session(pg) as mutation:
            mutation.execute(sa.text("SET LOCAL lock_timeout='200ms'"))
            with pytest.raises(sa.exc.OperationalError):
                mutation.execute(
                    table.update().where(table.c.id == identifier).values(status="inactive")
                )
            mutation.rollback()
        held.rollback()
        with Session(pg) as mutation:
            mutation.execute(
                table.update().where(table.c.id == identifier).values(status="inactive")
            )
            mutation.commit()


@pytest.mark.parametrize("different_key", [False, True])
def test_competing_sessions_persist_one_original_and_replayable_results(pg, different_key):
    barrier = Barrier(2)

    def submit(index):
        with Session(pg) as session:
            barrier.wait(timeout=8)
            key = f"pg-competing-{index if different_key else 0}"
            try:
                return _capture(session, key)["id"]
            except xml.SupplierXmlResultError as error:
                assert different_key and error.code == "supplier_xml_duplicate"
                return error.import_id

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = [f.result(timeout=20) for f in [executor.submit(submit, i) for i in range(2)]]
    assert results[0] == results[1]
    with Session(pg) as session:
        assert session.scalar(sa.select(sa.func.count()).select_from(TABLES[0])) == 1
        assert session.scalar(sa.select(sa.func.count()).select_from(TABLES[2])) == (
            2 if different_key else 1
        )
        assert xml.download_original(session, ADMIN_USER_ID, results[0]) == SOURCE


@pytest.mark.parametrize("violation", ["wrong_branch", "invalid_status", "conflict_link"])
def test_database_constraints_cannot_cross_scope_or_certify_document(pg, violation):
    with Session(pg) as session:
        _capture(session)
        before = _snapshot(session, TABLES)
        command = dict(session.execute(sa.select(TABLES[2])).mappings().one())
        branch_b = None
        if violation == "wrong_branch":
            branch_b = dict(session.execute(sa.select(models.branches)).mappings().one())
            branch_b.update(id=str(uuid4()), code="XML-B", name="Synthetic branch B")
            session.execute(models.branches.insert().values(**branch_b))
            session.commit()
        with pytest.raises(sa.exc.IntegrityError):
            if violation == "wrong_branch":
                session.execute(
                    TABLES[2].update().values(branch_id=branch_b["id"])
                )
            elif violation == "invalid_status":
                session.execute(TABLES[0].update().values(fiscal_validation="valid"))
            else:
                session.execute(
                    TABLES[2]
                    .update()
                    .values(result_kind="conflict", conflict_id=command["import_id"])
                )
        session.rollback()
        assert _snapshot(session, TABLES) == before


def _workspace(session, monkeypatch):
    monkeypatch.setenv("RESTAURANTOS_BRANCH_SCOPE_V2_ENABLED", "true")
    get_settings.cache_clear()
    branch_b = dict(session.execute(sa.select(models.branches)).mappings().one())
    branch_b.update(id=str(uuid4()), code="XML-B", name="Synthetic branch B")
    session.execute(models.branches.insert().values(**branch_b))
    _grant_selection(session, ADMIN_ROLE_ID, workspace=False)
    return select_branch_workspace(
        session,
        ADMIN_USER_ID,
        {"target_branch_id": BRANCH_ID, "expected_authorization_version": 1},
        "xml-workspace-select",
    )


def test_public_context_rotation_after_preflight_prevents_capture(pg, monkeypatch):
    with Session(pg) as session:
        selected = _workspace(session, monkeypatch)
        xml.authorize_capture(
            session, ADMIN_USER_ID, BRANCH_ID, selected["branch_workspace_context"]
        )
        session.rollback()
    with Session(pg) as session:
        reissue_branch_context(
            session,
            ADMIN_USER_ID,
            {
                "context_id": selected["branch_workspace_context_id"],
                "expected_authorization_version": 1,
            },
            "xml-rotate-before-write",
        )
    with Session(pg) as session:
        with pytest.raises(BusinessError) as error:
            _capture(session, secret=selected["branch_workspace_context"])
        assert error.value.code == "branch_context_superseded"
        assert all(session.scalar(sa.select(sa.func.count()).select_from(t)) == 0 for t in TABLES)


def test_public_rotation_waits_for_capture_audit_commit(pg, monkeypatch):
    with Session(pg) as session:
        selected = _workspace(session, monkeypatch)
    held, release, started = Event(), Event(), Event()
    pids = {}
    real_audit = xml.ops._audit

    def pause(session, action, *args, **kwargs):
        if action == "supplier_xml.captured":
            held.set()
            assert release.wait(10)
        return real_audit(session, action, *args, **kwargs)

    monkeypatch.setattr(xml.ops, "_audit", pause)

    def capture():
        with Session(pg) as session:
            return _capture(session, secret=selected["branch_workspace_context"])

    def rotate():
        with Session(pg) as session:
            pids["rotate"] = session.scalar(sa.text("SELECT pg_backend_pid()"))
            started.set()
            return reissue_branch_context(
                session,
                ADMIN_USER_ID,
                {
                    "context_id": selected["branch_workspace_context_id"],
                    "expected_authorization_version": 1,
                },
                "xml-rotate-after-write",
            )

    with ThreadPoolExecutor(max_workers=2) as executor:
        writer = executor.submit(capture)
        try:
            assert held.wait(8)
            rotation = executor.submit(rotate)
            assert started.wait(8)
            deadline = time.monotonic() + 5
            waiting = False
            while time.monotonic() < deadline:
                with pg.connect() as connection:
                    waiting = connection.scalar(
                        sa.text(
                            "SELECT wait_event_type='Lock' FROM pg_stat_activity WHERE pid=:pid"
                        ),
                        {"pid": pids["rotate"]},
                    )
                if waiting:
                    break
                time.sleep(0.02)
            assert waiting and not rotation.done()
        finally:
            release.set()
        first, changed = writer.result(timeout=15), rotation.result(timeout=15)
    assert changed["branch_workspace_secret_version"] == 2
    with Session(pg) as session:
        assert xml.download_original(session, ADMIN_USER_ID, first["id"]) == SOURCE
        with pytest.raises(BusinessError) as error:
            _capture(session, key="xml-stale", secret=selected["branch_workspace_context"])
        assert error.value.code == "branch_context_superseded"
