"""Historical inspection exercises real read-only database access and corruption fixtures."""

import json
import subprocess
import sys
from uuid import uuid4

import pytest
import sqlalchemy as sa
from restaurant_os import models, operations
from restaurant_os.system_diagnostics import diagnose, diagnostic_engine, readonly_snapshot
from sqlalchemy.orm import Session
from test_platform_api import ADMIN_USER_ID, BRANCH_ID, _seed
from test_system_remediation_postgres import open_shift, purchase_seed


@pytest.fixture
def history(tmp_path):
    database = tmp_path / "history.sqlite"
    writer = sa.create_engine(sa.URL.create("sqlite+pysqlite", database=str(database)))
    models.metadata.create_all(writer)
    with Session(writer) as session:
        _seed(session)
    purchase = purchase_seed(writer, cash=True)
    open_shift(writer)
    with Session(writer) as session:
        operations.confirm_purchase_document(
            session, purchase["id"], "diagnostic-confirm", "CAJA-01", ADMIN_USER_ID
        )
    reader = diagnostic_engine(str(writer.url))
    try:
        yield writer, reader, purchase["id"]
    finally:
        reader.dispose()
        writer.dispose()


def fingerprint(engine):
    with engine.connect() as connection:
        return {
            table.name: sorted(
                repr(dict(row)) for row in connection.execute(sa.select(table)).mappings()
            )
            for table in models.metadata.tables.values()
        }


def test_valid_history_stays_identical_and_read_only(history):
    writer, reader, _ = history
    before = fingerprint(writer)
    report = diagnose(reader, operations.ORGANIZATION_ID)
    assert report["findings"] == []
    assert report["repairs_performed"] is False
    assert report["coverage_partial"] is False
    assert report["purchase_count"] == report["purchases_scanned"] == 1
    assert fingerprint(writer) == before
    with readonly_snapshot(reader) as connection:
        with pytest.raises(sa.exc.DBAPIError):
            connection.execute(models.purchase_documents.delete())
    assert fingerprint(writer) == before


@pytest.mark.parametrize(
    "corruption", ["duplicate_cash", "duplicate_receipt", "cash_flag", "missing_event"]
)
def test_corrupt_purchase_is_reported_without_sensitive_fields_or_repairs(history, corruption):
    writer, reader, purchase_id = history
    with writer.begin() as connection:
        if corruption == "missing_event":
            connection.execute(
                models.purchase_documents.update()
                .where(models.purchase_documents.c.id == purchase_id)
                .values(status="cancelled", confirmed_at=None)
            )
        elif corruption == "cash_flag":
            connection.execute(
                models.purchase_documents.update()
                .where(models.purchase_documents.c.id == purchase_id)
                .values(paid_from_cash=False)
            )
        else:
            table = (
                models.cash_movements
                if corruption == "duplicate_cash"
                else models.inventory_movements
            )
            statement = sa.select(table)
            if corruption == "duplicate_receipt":
                statement = statement.where(table.c.movement_type == "PURCHASE_RECEIPT")
            row = dict(connection.execute(statement.limit(1)).mappings().one())
            row.update(id="diagnostic-duplicate", idempotency_key="diagnostic-duplicate-key")
            connection.execute(table.insert().values(**row))
        connection.execute(
            models.purchase_documents.update()
            .where(models.purchase_documents.c.id == purchase_id)
            .values(notes="PRIVATE-DIAGNOSTIC-MARKER", folio="PRIVATE-FOLIO")
        )
    before = fingerprint(writer)
    report = diagnose(reader, operations.ORGANIZATION_ID)
    assert any(row["record_id"] == purchase_id for row in report["findings"])
    serialized = json.dumps(report)
    assert "PRIVATE" not in serialized
    assert ADMIN_USER_ID not in serialized
    assert fingerprint(writer) == before


def test_cli_missing_url_and_missing_file_never_create_database(tmp_path, monkeypatch):
    monkeypatch.delenv("AUDCORE_DIAGNOSTIC_DATABASE_URL", raising=False)
    command = [
        sys.executable,
        "-m",
        "restaurant_os.system_diagnostics",
        "--organization-id",
        operations.ORGANIZATION_ID,
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    assert result.returncode == 2 and not result.stdout
    missing = tmp_path / "missing.sqlite"
    monkeypatch.setenv("AUDCORE_DIAGNOSTIC_DATABASE_URL", f"sqlite:///{missing}")
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    assert result.returncode == 2 and not result.stdout
    assert str(missing) not in result.stderr
    assert not missing.exists()


def test_terms_orphans_and_negative_stock_are_candidates_with_owned_ids_only(history):
    writer, reader, _ = history
    foreign_org, foreign_supplier = str(uuid4()), str(uuid4())
    with writer.begin() as connection:
        organization = dict(
            connection.execute(
                sa.select(models.organizations).where(
                    models.organizations.c.id == operations.ORGANIZATION_ID
                )
            )
            .mappings()
            .one()
        )
        organization.update(id=foreign_org, name="PRIVATE-FOREIGN-ORGANIZATION")
        connection.execute(models.organizations.insert().values(**organization))
        supplier = dict(connection.execute(sa.select(models.suppliers).limit(1)).mappings().one())
        supplier.update(id=foreign_supplier, organization_id=foreign_org)
        connection.execute(models.suppliers.insert().values(**supplier))
        connection.execute(
            models.supplier_branch_terms.insert().values(
                supplier_id=foreign_supplier,
                branch_id=BRANCH_ID,
                updated_at=organization["updated_at"],
            )
        )
        cash = dict(connection.execute(sa.select(models.cash_movements).limit(1)).mappings().one())
        cash.update(id="orphan-cash", source_id="missing-purchase", idempotency_key="orphan-cash")
        connection.execute(models.cash_movements.insert().values(**cash))
        cash.update(
            id="orphan-expense-cash",
            source_type="EXPENSE",
            source_id="missing-expense",
            idempotency_key="orphan-expense-cash",
        )
        connection.execute(models.cash_movements.insert().values(**cash))
        connection.execute(
            models.inventory_cost_states.update()
            .where(models.inventory_cost_states.c.branch_id == BRANCH_ID)
            .values(quantity_on_hand=-1)
        )
    before = fingerprint(writer)
    report = diagnose(reader, operations.ORGANIZATION_ID)
    assert {row["code"] for row in report["findings"]} >= {
        "supplier_terms_scope_conflict",
        "purchase_effect_parent_conflict",
        "expense_effect_parent_conflict",
        "negative_stock_requires_investigation",
    }
    assert foreign_org not in json.dumps(report) and foreign_supplier not in json.dumps(report)
    assert report["stock_causation_confirmed"] is False
    assert report["historical_report_execution_known"] is False
    assert report["periods_requiring_review"]
    assert fingerprint(writer) == before


def test_limit_and_unknown_scope_never_accredit_a_complete_scan(history):
    writer, reader, _ = history
    with writer.begin() as connection:
        purchase = dict(connection.execute(sa.select(models.purchase_documents)).mappings().one())
        purchase.update(
            id=str(uuid4()),
            folio="LIMIT-SECOND",
            status="draft",
            confirmed_at=None,
            confirmation_idempotency_key=None,
            cash_movement_id=None,
        )
        connection.execute(models.purchase_documents.insert().values(**purchase))
    report = diagnose(reader, operations.ORGANIZATION_ID, limit=1)
    assert report["coverage_partial"] is True
    assert report["purchase_count"] == 2 and report["purchases_scanned"] == 1
    with pytest.raises(ValueError, match="not found"):
        diagnose(reader, str(uuid4()))
    with pytest.raises(ValueError, match="scope or limit"):
        diagnose(reader, operations.ORGANIZATION_ID, limit=0)


def test_cli_sql_error_is_redacted(tmp_path, monkeypatch):
    database = tmp_path / "PRIVATE-STORAGE-MARKER.sqlite"
    engine = sa.create_engine(sa.URL.create("sqlite", database=str(database)))
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE unrelated (id INTEGER)")
    engine.dispose()
    monkeypatch.setenv("AUDCORE_DIAGNOSTIC_DATABASE_URL", str(engine.url))
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "restaurant_os.system_diagnostics",
            "--organization-id",
            operations.ORGANIZATION_ID,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2 and not result.stdout
    assert "PRIVATE" not in result.stderr and "SELECT" not in result.stderr


@pytest.mark.parametrize(
    "kind,source",
    [
        ("cash", "PURCHASE_CANCELLATION"),
        ("cash", "EXPENSE_CANCELLATION"),
        ("inventory", "purchase_cancellation"),
    ],
)
def test_orphan_cancellation_sources_use_the_writer_vocabulary(history, kind, source):
    writer, reader, _ = history
    table = models.cash_movements if kind == "cash" else models.inventory_movements
    with writer.begin() as connection:
        statement = sa.select(table)
        if kind == "inventory":
            statement = statement.where(table.c.movement_type == "PURCHASE_RECEIPT")
        row = dict(connection.execute(statement.limit(1)).mappings().one())
        row.update(
            id="orphan-cancellation",
            source_type=source,
            source_id="missing-document",
            idempotency_key="orphan-cancellation",
        )
        connection.execute(table.insert().values(**row))
    before = fingerprint(writer)
    report = diagnose(reader, operations.ORGANIZATION_ID)
    assert any(row["record_id"] == "orphan-cancellation" for row in report["findings"])
    assert fingerprint(writer) == before


@pytest.mark.parametrize("kind", ["cash", "inventory"])
def test_duplicate_reversal_with_valid_parent_is_not_reported_as_healthy(history, kind):
    writer, reader, purchase_id = history
    with Session(writer) as session:
        operations.cancel_purchase_document(
            session, purchase_id, "Diagnostic cancellation", ADMIN_USER_ID
        )
    assert diagnose(reader, operations.ORGANIZATION_ID)["findings"] == []
    table = models.cash_movements if kind == "cash" else models.inventory_movements
    source = "PURCHASE_CANCELLATION" if kind == "cash" else "purchase_cancellation"
    with writer.begin() as connection:
        reversal = dict(
            connection.execute(sa.select(table).where(table.c.source_type == source).limit(1))
            .mappings()
            .one()
        )
        reversal.update(id="duplicate-reversal", idempotency_key="duplicate-reversal")
        if kind == "cash":
            reversal["compensates_movement_id"] = None
        connection.execute(table.insert().values(**reversal))
    before = fingerprint(writer)
    report = diagnose(reader, operations.ORGANIZATION_ID)
    assert any(row["code"] == f"duplicate_document_{kind}_reversal" for row in report["findings"])
    assert fingerprint(writer) == before


def test_foreign_reversals_of_owned_originals_are_reported_without_foreign_ids(history):
    writer, reader, purchase_id = history
    with Session(writer) as session:
        operations.cancel_purchase_document(
            session, purchase_id, "Diagnostic cancellation", ADMIN_USER_ID
        )
    foreign_org = str(uuid4())
    foreign_ids = set()
    with writer.begin() as connection:
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
        for table in (models.cash_movements, models.inventory_movements):
            condition = sa.func.upper(table.c.source_type) == "PURCHASE_CANCELLATION"
            foreign_ids.update(connection.execute(sa.select(table.c.id).where(condition)).scalars())
            connection.execute(table.update().where(condition).values(organization_id=foreign_org))
    before = fingerprint(writer)
    report = diagnose(reader, operations.ORGANIZATION_ID)
    assert {row["code"] for row in report["findings"]} >= {
        "document_cash_reversal_scope_conflict",
        "document_inventory_reversal_scope_conflict",
    }
    assert foreign_org not in json.dumps(report)
    assert all(identifier not in json.dumps(report) for identifier in foreign_ids)
    assert fingerprint(writer) == before
