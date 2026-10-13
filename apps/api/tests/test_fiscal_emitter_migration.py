"""Actual additive SQLite migration: preserve history and constrain issuer references."""

import os
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

PREVIOUS = "0085_fiscal_permissions"
REVISION = "0086_fiscal_emitters"


def _sqlite_alembic(path, *arguments):
    env = {**os.environ, "RESTAURANTOS_DATABASE_URL": f"sqlite+pysqlite:///{path}"}
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


@pytest.fixture(scope="module")
def baseline(tmp_path_factory):
    path = tmp_path_factory.mktemp("fiscal-emitter-migration") / "baseline.db"
    result = _sqlite_alembic(path, "upgrade", PREVIOUS)
    assert result.returncode == 0, result.stdout + result.stderr
    with sqlite3.connect(path) as connection:
        org = connection.execute("SELECT id FROM organizations LIMIT 1").fetchone()[0]
        branch = connection.execute("SELECT id FROM branches LIMIT 1").fetchone()[0]
        connection.execute(
            "INSERT INTO facturapi_config (id,organization_id,is_enabled,api_key,"
            "organization_rfc,created_at,updated_at) VALUES "
            "('legacy-config',?,1,'synthetic-legacy-secret','SYN010101AAA','2026-10-13','2026-10-13')",
            (org,),
        )
        connection.execute(
            "INSERT INTO cfdi_invoices (id,organization_id,branch_id,folio_number,rfc_emisor,"
            "rfc_receptor,nombre_receptor,codigo_postal_receptor,regimen_fiscal_receptor,"
            "total_cents,raw_sat_response,created_at) VALUES "
            "('legacy-invoice',?,?,'QA','SYN010101AAA','XAXX010101000','Synthetic','80000',"
            "'616',1999,'{\"private\":\"original\"}','2026-10-13')",
            (org, branch),
        )
    return path


@pytest.fixture
def database(baseline, tmp_path):
    path = tmp_path / "emitter.db"
    shutil.copyfile(baseline, path)
    return path


def _upgrade(path):
    result = _sqlite_alembic(path, "upgrade", REVISION)
    assert result.returncode == 0, result.stdout + result.stderr


def test_upgrade_preserves_legacy_config_and_payload_without_fabricating_origin(database):
    with sqlite3.connect(database) as connection:
        before = connection.execute("SELECT * FROM facturapi_config").fetchall()
        historical = connection.execute("SELECT * FROM cfdi_invoices").fetchall()[0]
    _upgrade(database)
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT * FROM facturapi_config").fetchall() == before
        columns = [row[1] for row in connection.execute("PRAGMA table_info(cfdi_invoices)")]
        after = connection.execute("SELECT * FROM cfdi_invoices").fetchall()[0]
        assert after[: len(historical)] == historical
        assert after[columns.index("emitter_configuration_id")] is None
        assert after[columns.index("emitter_configuration_version")] is None
        assert (
            connection.execute("SELECT COUNT(*) FROM fiscal_emitter_configurations").fetchone()[0]
            == 0
        )
    result = _sqlite_alembic(database, "downgrade", PREVIOUS)
    assert result.returncode == 0, result.stdout + result.stderr
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT * FROM facturapi_config").fetchall() == before
        assert connection.execute("SELECT * FROM cfdi_invoices").fetchall()[0] == historical


@pytest.mark.parametrize("history", ["identity", "revision"])
def test_history_prevents_destructive_downgrade(database, history):
    _upgrade(database)
    with sqlite3.connect(database) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        org, emitter = connection.execute(
            "SELECT organization_id,id FROM legal_entities LIMIT 1"
        ).fetchone()
        actor = connection.execute("SELECT id FROM users LIMIT 1").fetchone()[0]
        connection.execute(
            "INSERT INTO fiscal_emitter_configurations "
            "VALUES ('qa-config',?,?,1,'2026-10-13','2026-10-13')",
            (org, emitter),
        )
        if history == "revision":
            connection.execute(
                "INSERT INTO fiscal_emitter_configuration_versions VALUES "
                "('qa-revision','qa-config',1,'synthetic-encrypted-envelope',?,'2026-10-13')",
                (actor,),
            )
    result = _sqlite_alembic(database, "downgrade", PREVIOUS)
    assert result.returncode != 0
    assert "0086 downgrade blocked" in result.stderr
    with sqlite3.connect(database) as connection:
        assert (
            connection.execute("SELECT version_num FROM alembic_version").fetchone()[0] == REVISION
        )
        assert (
            connection.execute("SELECT COUNT(*) FROM fiscal_emitter_configurations").fetchone()[0]
            == 1
        )


@pytest.mark.parametrize("version", [None, 1])
def test_partial_or_missing_revision_reference_is_rejected_by_database(database, version):
    _upgrade(database)
    with sqlite3.connect(database) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE cfdi_invoices SET emitter_configuration_id='unknown',"
                "emitter_configuration_version=? WHERE id='legacy-invoice'",
                (version,),
            )
        connection.rollback()
        assert (
            connection.execute(
                "SELECT emitter_configuration_id FROM cfdi_invoices WHERE id='legacy-invoice'"
            ).fetchone()[0]
            is None
        )
