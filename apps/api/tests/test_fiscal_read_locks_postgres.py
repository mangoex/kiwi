"""Fiscal HTTP and direct readers must never upgrade competing shared locks."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from threading import Event
from time import monotonic

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from restaurant_os import models
from restaurant_os import operations as ops
from restaurant_os.config import get_settings
from restaurant_os.database import get_session
from restaurant_os.invoicing.service import InvoicingService
from restaurant_os.main import create_app
from sqlalchemy.orm import Session
from test_corporate_purchases_postgres import pg_engine as pg_engine
from test_operational_intents import _grant_permission
from test_platform_api import ADMIN_USER_ID, BRANCH_ID, _admin_headers

INVOICE = "fiscal-reader-lock-invoice"


@pytest.mark.parametrize("entry", ["http-list", "http-detail", "pdf", "xml", "service-list"])
def test_concurrent_fiscal_readers_choose_lock_mode_before_financial_guard(
    pg_engine, monkeypatch, entry
):
    monkeypatch.setenv("RESTAURANTOS_BRANCH_SCOPE_V2_ENABLED", "true")
    get_settings.cache_clear()
    with Session(pg_engine) as session:
        _grant_permission(session, "invoicing.read")
        session.execute(models.cfdi_invoices.insert().values(
            id=INVOICE, organization_id=ops.ORGANIZATION_ID, branch_id=BRANCH_ID,
            folio_number="SYNTHETIC", rfc_emisor="SYN010101AAA", rfc_receptor="XAXX010101000",
            nombre_receptor="Synthetic", codigo_postal_receptor="80000",
            regimen_fiscal_receptor="616", total_cents=1234, status="draft", created_at=ops._now(),
        ))
        session.commit()
        before = list(session.execute(sa.select(models.cfdi_invoices)).mappings())

    held, release, second_entered = Event(), Event(), Event()
    pids = []

    @contextmanager
    def reader_session():
        with Session(pg_engine) as session:
            connection = session.connection()
            probe_info = connection.info
            index = len(pids)
            pids.append(connection.scalar(sa.text("SELECT pg_backend_pid()")))
            probe_info["fiscal_first_reader"] = index == 0
            if index == 1:
                second_entered.set()
            try:
                yield session
            finally:
                probe_info.pop("fiscal_first_reader", None)

    def dependency():
        with reader_session() as session:
            yield session

    def after_query(connection, cursor, statement, parameters, context, many):
        if (
            connection.info.get("fiscal_first_reader")
            and "pg_advisory_xact_lock_shared" in statement
            and not held.is_set()
        ):
            held.set()
            assert release.wait(10), "First reader was not released"

    app = create_app()
    app.dependency_overrides[get_session] = dependency
    client = TestClient(app)

    def read():
        if entry == "service-list":
            with reader_session() as session:
                result = InvoicingService().list_invoices(
                    session, ops.ORGANIZATION_ID, BRANCH_ID, actor_user_id=ADMIN_USER_ID
                )
                assert [row["id"] for row in result] == [INVOICE]
                return 200
        path = "/api/v1/invoicing/invoices"
        if entry != "http-list":
            path += f"/{INVOICE}"
        if entry in {"pdf", "xml"}:
            path += f"/{entry}"
        result = client.get(path, params={"branch_id": BRANCH_ID}, headers=_admin_headers())
        if entry in {"pdf", "xml"}:
            assert result.status_code == 409, result.text
            assert result.json()["detail"]["code"] == "fiscal_document_not_available"
        else:
            assert result.status_code == 200, result.text
        return result.status_code

    sa.event.listen(pg_engine, "after_cursor_execute", after_query)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(read)
            try:
                assert held.wait(10), "First reader never reached financial authority"
                second = pool.submit(read)
                assert second_entered.wait(10)
                deadline = monotonic() + 8
                with (
                    pg_engine.connect().execution_options(isolation_level="AUTOCOMMIT") as observer
                ):
                    while not observer.scalar(sa.text(
                        "SELECT wait_event_type = 'Lock' AND :first = ANY(pg_blocking_pids(pid)) "
                        "FROM pg_stat_activity WHERE pid=:second"
                    ), {"first": pids[0], "second": pids[1]}):
                        assert monotonic() < deadline, "Second reader did not wait on the first"
                        release.wait(0.02)
                assert not first.done() and not second.done()
            finally:
                release.set()
            expected = 409 if entry in {"pdf", "xml"} else 200
            assert first.result(timeout=12) == second.result(timeout=12) == expected
        with Session(pg_engine) as session:
            assert list(session.execute(sa.select(models.cfdi_invoices)).mappings()) == before
    finally:
        release.set()
        sa.event.remove(pg_engine, "after_cursor_execute", after_query)
        client.close()
        get_settings.cache_clear()
