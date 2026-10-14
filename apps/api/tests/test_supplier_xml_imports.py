"""Private unverified capture has no purchase, inventory, cash or payable effects."""

import asyncio
import base64
import importlib
import importlib.util
import json
from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from restaurant_os import models
from restaurant_os.api import get_session
from restaurant_os.config import get_settings
from restaurant_os.main import app
from restaurant_os.operations import BusinessError
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from test_platform_api import ADMIN_ROLE_ID, ADMIN_USER_ID, BRANCH_ID, _admin_headers, _seed
from test_supplier_cfdi_identity import SOURCE


@pytest.fixture
def engine(monkeypatch):
    monkeypatch.setenv("RESTAURANTOS_SUPPLIER_XML_IMPORTS_ENABLED", "true")
    monkeypatch.setenv(
        "RESTAURANTOS_FISCAL_ENCRYPTION_KEYS",
        json.dumps({"test": base64.b64encode(bytes(range(32))).decode()}),
    )
    monkeypatch.setenv("RESTAURANTOS_FISCAL_ACTIVE_ENCRYPTION_KEY_ID", "test")
    get_settings.cache_clear()
    db = sa.create_engine(
        "sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )

    @sa.event.listens_for(db, "connect")
    def foreign_keys(connection, record):
        connection.execute("PRAGMA foreign_keys=ON")

    models.metadata.create_all(db)
    with Session(db) as session:
        _seed(session)
        session.execute(models.legal_entities.update().values(tax_id="BBB010101BBB"))
        session.commit()
    yield db
    db.dispose()
    get_settings.cache_clear()


def service():
    return importlib.import_module("restaurant_os.supplier_xml_imports")


def capture(session, source=SOURCE, key="xml-command-1"):
    return service().capture_original(session, ADMIN_USER_ID, BRANCH_ID, source, key, None)


def test_capture_replay_and_private_original(engine):
    api = service()
    with Session(engine) as session:
        tables = (models.purchase_documents, models.inventory_movements, models.cash_movements)
        previous = {
            table.name: list(session.execute(sa.select(table)).mappings()) for table in tables
        }
        first = capture(session)
        original = dict(
            session.execute(sa.select(models.supplier_document_imports)).mappings().one()
        )
        assert first == capture(session)
        assert "AAA010101AAA" not in original["original_ciphertext"]
        assert "BBB010101BBB" not in json.dumps(first)
        assert api.download_original(session, ADMIN_USER_ID, first["id"]) == SOURCE
        assert (
            session.scalar(
                sa.select(sa.func.count()).select_from(models.supplier_document_import_commands)
            )
            == 1
        )
        for table in tables:
            assert list(session.execute(sa.select(table)).mappings()) == previous[table.name]


def test_new_key_duplicate_and_changed_hash_preserve_original(engine):
    api = service()
    with Session(engine) as session:
        first = capture(session)
        before = dict(session.execute(sa.select(models.supplier_document_imports)).mappings().one())
        for source, key, code in [
            (SOURCE, "xml-command-2", "supplier_xml_duplicate"),
            (SOURCE + b" ", "xml-command-3", "supplier_xml_hash_conflict"),
        ]:
            with pytest.raises(api.SupplierXmlResultError) as error:
                capture(session, source, key)
            assert error.value.code == code and error.value.import_id == first["id"]
            with pytest.raises(api.SupplierXmlResultError) as replay:
                capture(session, source, key)
            assert replay.value.code == code
        assert (
            dict(session.execute(sa.select(models.supplier_document_imports)).mappings().one())
            == before
        )
        assert (
            session.scalar(
                sa.select(sa.func.count()).select_from(models.supplier_document_import_conflicts)
            )
            == 1
        )
        assert (
            session.scalar(
                sa.select(sa.func.count()).select_from(models.supplier_document_import_commands)
            )
            == 3
        )


def test_same_key_changed_bytes_rejected_before_second_effect(engine):
    with Session(engine) as session:
        capture(session)
        with pytest.raises(BusinessError) as error:
            capture(session, SOURCE + b" ")
        assert error.value.code == "idempotency_key_conflict"
        assert (
            session.scalar(
                sa.select(sa.func.count()).select_from(models.supplier_document_import_conflicts)
            )
            == 0
        )


def test_crypto_tampering_and_audit_failure_release_no_original(engine, monkeypatch):
    api = service()
    with Session(engine) as session:
        first = capture(session)
        before = session.scalar(sa.select(sa.func.count()).select_from(models.audit_events))

        def fail(*args, **kwargs):
            raise RuntimeError("synthetic audit failure")

        with monkeypatch.context() as patcher:
            patcher.setattr(api.ops, "_audit", fail)
            with pytest.raises(RuntimeError):
                api.download_original(session, ADMIN_USER_ID, first["id"])
        session.rollback()
        assert session.scalar(sa.select(sa.func.count()).select_from(models.audit_events)) == before
        session.execute(models.supplier_document_imports.update().values(original_sha256="0" * 64))
        session.commit()
        with pytest.raises(BusinessError) as error:
            api.download_original(session, ADMIN_USER_ID, first["id"])
        assert error.value.code == "supplier_xml_crypto_unavailable"


@pytest.fixture
def client(engine):
    def session_dependency():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = session_dependency
    with TestClient(app) as value:
        yield value
    app.dependency_overrides.clear()


def test_real_http_capture_metadata_attachment_and_duplicate(client):
    headers = {
        **_admin_headers(),
        "Content-Type": "application/xml",
        "Idempotency-Key": "xml-http-1",
    }
    path = f"/api/v1/purchases/xml-imports/branches/{BRANCH_ID}"
    created = client.post(path, content=SOURCE, headers=headers)
    assert created.status_code == 200, created.text
    identifier = created.json()["id"]
    metadata = client.get(f"/api/v1/purchases/xml-imports/{identifier}", headers=_admin_headers())
    assert metadata.status_code == 200 and metadata.json()["status"] == "unverified"
    assert "BBB010101BBB" not in metadata.text
    original = client.get(
        f"/api/v1/purchases/xml-imports/{identifier}/original", headers=_admin_headers()
    )
    assert original.status_code == 200 and original.content == SOURCE
    assert original.headers["cache-control"] == "no-store"
    assert original.headers["content-disposition"].startswith("attachment;")
    duplicate = client.post(
        path, content=SOURCE, headers={**headers, "Idempotency-Key": "xml-http-2"}
    )
    assert duplicate.status_code == 409 and duplicate.json()["detail"]["import_id"] == identifier


def test_resolve_after_capture_disabled_and_history_branch_closed(client, engine, monkeypatch):
    with Session(engine) as session:
        first = capture(session)
        session.execute(
            models.branches.update()
            .where(models.branches.c.id == BRANCH_ID)
            .values(status="inactive")
        )
        session.commit()
    monkeypatch.setenv("RESTAURANTOS_SUPPLIER_XML_IMPORTS_ENABLED", "false")
    get_settings.cache_clear()
    result = client.post(
        "/api/v1/purchases/xml-imports/resolve",
        headers={**_admin_headers(), "Idempotency-Key": "xml-command-1"},
    )
    assert result.status_code == 200 and result.json() == first, result.text
    original = client.get(
        f"/api/v1/purchases/xml-imports/{first['id']}/original", headers=_admin_headers()
    )
    assert original.status_code == 200 and original.content == SOURCE


@pytest.mark.parametrize(
    "extra",
    [{"content-type": "text/plain"}, {"content-encoding": "gzip"}, {"content-length": "1048577"}],
)
def test_http_invalid_frontier_creates_nothing(client, engine, extra):
    response = client.post(
        f"/api/v1/purchases/xml-imports/branches/{BRANCH_ID}",
        content=SOURCE,
        headers={
            **_admin_headers(),
            "content-type": "application/xml",
            "Idempotency-Key": "bad-frontier",
            **extra,
        },
    )
    assert response.status_code in {413, 422}
    with Session(engine) as session:
        assert (
            session.scalar(sa.select(sa.func.count()).select_from(models.supplier_document_imports))
            == 0
        )


def test_revocation_after_preflight_before_body_commit(client, engine, monkeypatch):
    from restaurant_os import supplier_xml_upload

    original_reader = supplier_xml_upload.read_original

    async def revoke(request):
        data = await original_reader(request)
        with Session(engine) as session:
            session.execute(
                models.users.update()
                .where(models.users.c.id == ADMIN_USER_ID)
                .values(status="inactive")
            )
            session.commit()
        return data

    monkeypatch.setattr(supplier_xml_upload, "read_original", revoke)
    response = client.post(
        f"/api/v1/purchases/xml-imports/branches/{BRANCH_ID}",
        content=SOURCE,
        headers={
            **_admin_headers(),
            "content-type": "application/xml",
            "Idempotency-Key": "revoked-upload",
        },
    )
    assert response.status_code == 403
    with Session(engine) as session:
        assert (
            session.scalar(
                sa.select(sa.func.count()).select_from(models.supplier_document_import_commands)
            )
            == 0
        )


def test_xml_one_mib_http_contract_exceeds_workspace_json_limit(client):
    original = SOURCE + b" " * (1048576 - len(SOURCE))
    result = client.post(
        f"/api/v1/purchases/xml-imports/branches/{BRANCH_ID}",
        content=original,
        headers={**_admin_headers(), "content-type": "application/xml", "Idempotency-Key": "large"},
    )
    assert result.status_code == 200, result.text


def test_anonymous_xml_is_rejected_before_body_receive(client):
    received, sent = [], []

    async def receive():
        received.append(True)
        return {"type": "http.request", "body": b"<r/>", "more_body": False}

    async def send(message):
        sent.append(message)

    path = f"/api/v1/purchases/xml-imports/branches/{BRANCH_ID}"
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "headers": [(b"content-type", b"application/xml")],
        "server": ("testserver", 80),
        "client": ("testclient", 123),
    }
    asyncio.run(app(scope, receive, send))
    assert next(m["status"] for m in sent if m["type"] == "http.response.start") in {401, 403}
    assert received == []


def test_header_resolve_sql_fault_is_private(client, engine, caplog):
    key = "private-command-sentinel"
    with Session(engine) as session:
        capture(session, key=key)

    @sa.event.listens_for(engine, "before_cursor_execute")
    def fail(connection, cursor, statement, parameters, context, executemany):
        if (
            statement.lstrip().startswith("SELECT")
            and "supplier_document_import_commands" in statement
        ):
            assert key in str(parameters)
            raise sa.exc.StatementError(
                "storage fault", statement, parameters, RuntimeError("offline")
            )

    try:
        response = client.post(
            "/api/v1/purchases/xml-imports/resolve",
            headers={**_admin_headers(), "Idempotency-Key": key},
        )
    finally:
        sa.event.remove(engine, "before_cursor_execute", fail)
    assert response.status_code == 503
    assert key not in response.text and key not in caplog.text


def test_resolve_rejects_json_without_echoing_secrets(client):
    response = client.post(
        "/api/v1/purchases/xml-imports/resolve",
        json={"key": "secret-validation-sentinel" * 10},
        headers=_admin_headers(),
    )
    assert response.status_code == 422
    assert "secret-validation-sentinel" not in response.text


@pytest.mark.parametrize("fault", ["original", "command", "audit"])
def test_partial_capture_failure_rolls_back_every_effect(engine, monkeypatch, fault):
    api = service()
    with Session(engine) as session:
        before = session.scalar(sa.select(sa.func.count()).select_from(models.audit_events))

        def fail_audit(*args, **kwargs):
            raise RuntimeError("synthetic audit failure")

        if fault == "audit":
            monkeypatch.setattr(api.ops, "_audit", fail_audit)

        @sa.event.listens_for(engine, "after_cursor_execute")
        def fail(connection, cursor, statement, parameters, context, executemany):
            table = (
                "supplier_document_imports"
                if fault == "original"
                else "supplier_document_import_commands"
            )
            if fault != "audit" and statement.startswith("INSERT INTO " + table):
                raise RuntimeError("synthetic after-insert failure")

        try:
            with pytest.raises(RuntimeError):
                capture(session)
        finally:
            sa.event.remove(engine, "after_cursor_execute", fail)
        for table in (
            models.supplier_document_imports,
            models.supplier_document_import_commands,
            models.supplier_document_import_conflicts,
        ):
            assert session.scalar(sa.select(sa.func.count()).select_from(table)) == 0
        assert session.scalar(sa.select(sa.func.count()).select_from(models.audit_events)) == before


def test_committed_capture_lost_ack_resolves_one_effect(engine, monkeypatch):
    with Session(engine) as session:
        commit = session.commit

        def lost_ack():
            commit()
            raise sa.exc.OperationalError(
                "COMMIT", {}, RuntimeError("synthetic lost acknowledgement")
            )

        with monkeypatch.context() as patch:
            patch.setattr(session, "commit", lost_ack)
            with pytest.raises(BusinessError) as error:
                capture(session)
            assert error.value.code == "supplier_xml_persistence_unavailable"
    with Session(engine) as session:
        assert (
            service().resolve_command(session, ADMIN_USER_ID, "xml-command-1")["status"]
            == "unverified"
        )
        for table in (models.supplier_document_imports, models.supplier_document_import_commands):
            assert session.scalar(sa.select(sa.func.count()).select_from(table)) == 1


@pytest.mark.parametrize("fault", ["timeout", "oversize", "truncated", "disconnect"])
def test_reader_deadline_stream_size_and_disconnect_are_bounded(monkeypatch, fault):
    from restaurant_os import supplier_xml_upload as upload
    from starlette.requests import Request

    monkeypatch.setattr(upload, "UPLOAD_DEADLINE_SECONDS", 0.01)
    received = []

    async def receive():
        received.append(True)
        if fault == "timeout":
            await asyncio.sleep(1)
        if fault == "disconnect":
            return {"type": "http.disconnect"}
        return {
            "type": "http.request",
            "body": b"x" * (1048577 if fault == "oversize" else 1),
            "more_body": False,
        }

    headers = [(b"content-type", b"application/xml")]
    if fault == "truncated":
        headers.append((b"content-length", b"2"))
    request = Request({"type": "http", "headers": headers}, receive)
    with pytest.raises(BusinessError) as error:
        asyncio.run(upload.read_original(request))
    assert (
        error.value.code
        == {
            "timeout": "xml_upload_timeout",
            "oversize": "xml_size_exceeded",
            "truncated": "xml_content_length_invalid",
            "disconnect": "xml_content_length_invalid",
        }[fault]
    )
    assert len(received) == 1


@pytest.mark.parametrize("reason", ["other_branch", "config_only", "revoked_actor"])
def test_read_and_resolve_require_actual_resource_authority(engine, reason):
    api = service()
    with Session(engine) as session:
        first = capture(session)
        if reason == "other_branch":
            branch = dict(session.execute(sa.select(models.branches)).mappings().one())
            branch.update(id=str(uuid4()), code="XML-B", name="Synthetic branch B")
            session.execute(models.branches.insert().values(**branch))
            session.execute(
                models.roles.update()
                .where(models.roles.c.id == ADMIN_ROLE_ID)
                .values(scope="branch")
            )
            session.execute(
                models.user_roles.update()
                .where(models.user_roles.c.user_id == ADMIN_USER_ID)
                .values(branch_id=branch["id"])
            )
        elif reason == "config_only":
            session.execute(
                models.role_permissions.delete().where(
                    models.role_permissions.c.role_id == ADMIN_ROLE_ID,
                )
            )
            from test_operational_intents import _grant_permission
            _grant_permission(session, "invoicing.config.manage")
        else:
            session.execute(
                models.users.update()
                .where(models.users.c.id == ADMIN_USER_ID)
                .values(status="inactive")
            )
        session.commit()
        for operation in (
            lambda: api.metadata(session, ADMIN_USER_ID, first["id"]),
            lambda: api.download_original(session, ADMIN_USER_ID, first["id"]),
            lambda: api.resolve_command(session, ADMIN_USER_ID, "xml-command-1"),
        ):
            with pytest.raises(BusinessError):
                operation()
        assert (
            session.scalar(
                sa.select(sa.func.count()).select_from(models.supplier_document_import_commands)
            )
            == 1
        )


def _migration():
    path = (
        Path(__file__).resolve().parents[1]
        / "alembic/versions/202610141700_0092_supplier_xml_imports.py"
    )
    spec = importlib.util.spec_from_file_location("test_supplier_0092", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_sqlite_revision_roundtrip_preserves_existing_ledgers(engine, monkeypatch):
    migration = _migration()
    tables = (
        models.supplier_document_imports,
        models.supplier_document_import_conflicts,
        models.supplier_document_import_commands,
    )
    with engine.begin() as connection:
        ledgers = (models.branches, models.inventory_movements, models.cash_movements)
        before = {t.name: list(connection.execute(sa.select(t)).mappings()) for t in ledgers}
        for table in reversed(tables):
            table.drop(connection)
        monkeypatch.setattr(migration.op, "get_bind", lambda: connection)
        migration.upgrade()
        assert all(sa.inspect(connection).has_table(t.name) for t in tables)
        migration.downgrade()
        assert all(not sa.inspect(connection).has_table(t.name) for t in tables)
        assert {
            t.name: list(connection.execute(sa.select(t)).mappings()) for t in ledgers
        } == before


def test_sqlite_revision_cannot_destroy_private_history(engine, monkeypatch):
    migration = _migration()
    with Session(engine) as session:
        capture(session)
    with engine.begin() as connection:
        monkeypatch.setattr(migration.op, "get_bind", lambda: connection)
        original = list(connection.execute(sa.select(models.supplier_document_imports)).mappings())
        with pytest.raises(RuntimeError, match="downgrade blocked"):
            migration.downgrade()
        assert (
            list(connection.execute(sa.select(models.supplier_document_imports)).mappings())
            == original
        )
