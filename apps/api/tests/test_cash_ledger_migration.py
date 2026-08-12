from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

import pytest
import sqlalchemy as sa

ROOT = Path(__file__).resolve().parents[3]
API_DIR = ROOT / "apps" / "api"


def _sqlite_alembic(database_path: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    env = {
        **os.environ,
        "RESTAURANTOS_DATABASE_URL": f"sqlite+pysqlite:///{database_path}",
    }
    return subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "alembic.ini", *arguments],
        cwd=API_DIR,
        env=env,
        capture_output=True,
        text=True,
    )


def _postgres_url() -> str:
    url = os.environ.get("PCO003_TEST_POSTGRES_ROUNDTRIP_URL")
    if not url:
        pytest.skip("PCO003_TEST_POSTGRES_ROUNDTRIP_URL is required")
    parsed = urlparse(url)
    if parsed.hostname not in {"127.0.0.1", "localhost"} or not parsed.path.startswith(
        "/pco003_"
    ):
        raise RuntimeError("PCO-003 migration tests require a local pco003_* database")
    return url


def _postgres_alembic(url: str, *arguments: str) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "RESTAURANTOS_DATABASE_URL": url}
    env.pop("DATABASE_URL", None)
    return subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "alembic.ini", *arguments],
        cwd=API_DIR,
        env=env,
        capture_output=True,
        text=True,
    )


def _insert_legacy_movement(connection: sqlite3.Connection) -> tuple[str, ...]:
    organization_id = connection.execute("SELECT id FROM organizations LIMIT 1").fetchone()[0]
    branch_id = connection.execute("SELECT id FROM branches LIMIT 1").fetchone()[0]
    user_id = connection.execute("SELECT id FROM users LIMIT 1").fetchone()[0]
    shift_id = "018f6f73-2d0a-74f0-8f1c-000000009801"
    movement_id = "018f6f73-2d0a-74f0-8f1c-000000009802"
    connection.execute(
        """
        INSERT INTO cash_shifts (
            id, organization_id, branch_id, register_code, status, opening_cash_cents,
            opened_at, closed_at, created_at
        ) VALUES (?, ?, ?, 'LEGACY-01', 'CLOSED', 10000, ?, ?, ?)
        """,
        (
            shift_id,
            organization_id,
            branch_id,
            "2026-08-11T18:00:00+00:00",
            "2026-08-11T18:00:00+00:00",
            "2026-08-11T18:00:00+00:00",
        ),
    )
    connection.execute(
        """
        INSERT INTO cash_movements (
            id, organization_id, branch_id, cash_shift_id, movement_type, amount_cents,
            reason_code, reason, source_type, source_id, actor_user_id, idempotency_key,
            status, reversal_of_id, created_at
        ) VALUES (?, ?, ?, ?, 'cash_reversal', 3000, 'LEGACY', 'legacy reversal',
                  'legacy', NULL, ?, 'legacy-001', 'confirmed', NULL, ?)
        """,
        (
            movement_id,
            organization_id,
            branch_id,
            shift_id,
            user_id,
            "2026-08-11T18:00:01+00:00",
        ),
    )
    connection.commit()
    return tuple(
        connection.execute(
            """
            SELECT id, movement_type, amount_cents, reason_code, reason, source_type,
                   source_id, status, reversal_of_id, idempotency_key
            FROM cash_movements WHERE id = ?
            """,
            (movement_id,),
        ).fetchone()
    )


def test_sqlite_roundtrip_preserves_legacy_values_and_schema_fingerprint(tmp_path: Path) -> None:
    database_path = tmp_path / "pco003-roundtrip.db"
    initial = _sqlite_alembic(database_path, "upgrade", "0036_cash_concepts")
    assert initial.returncode == 0, initial.stderr
    connection = sqlite3.connect(database_path)
    try:
        legacy_shape = tuple(
            row[1] for row in connection.execute("PRAGMA table_info(cash_movements)")
        )
        legacy_values = _insert_legacy_movement(connection)
    finally:
        connection.close()
    upgraded = _sqlite_alembic(database_path, "upgrade", "0037_cash_movement_ledger")
    assert upgraded.returncode == 0, upgraded.stderr
    connection = sqlite3.connect(database_path)
    try:
        columns = tuple(
            row[1] for row in connection.execute("PRAGMA table_info(cash_movements)")
        )
        indexes = {
            row[1] for row in connection.execute("PRAGMA index_list(cash_movements)")
        }
        shift_indexes = {
            row[1] for row in connection.execute("PRAGMA index_list(cash_shifts)")
        }
        current_values = tuple(
            connection.execute(
                """
                SELECT id, movement_type, amount_cents, reason_code, reason, source_type,
                       source_id, status, reversal_of_id, idempotency_key
                FROM cash_movements WHERE id = ?
                """,
                ("018f6f73-2d0a-74f0-8f1c-000000009802",),
            ).fetchone()
        )
        assert legacy_shape == columns[: len(legacy_shape)]
        assert legacy_values == current_values
        assert "ix_cash_movements_branch_shift_created" in indexes
        assert "uq_cash_movements_compensates_movement" in indexes
        assert "uq_cash_shifts_open_register" in shift_indexes
        command_table = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
            ("cash_movement_commands",),
        ).fetchone()
        assert command_table == ("cash_movement_commands",)
    finally:
        connection.close()
    downgraded = _sqlite_alembic(database_path, "downgrade", "0036_cash_concepts")
    assert downgraded.returncode == 0, downgraded.stderr
    upgraded_again = _sqlite_alembic(database_path, "upgrade", "0037_cash_movement_ledger")
    assert upgraded_again.returncode == 0, upgraded_again.stderr


def test_sqlite_preflight_rejects_duplicate_open_and_incoherent_legacy_rows(tmp_path: Path) -> None:
    database_path = tmp_path / "pco003-preflight.db"
    assert _sqlite_alembic(database_path, "upgrade", "0036_cash_concepts").returncode == 0
    connection = sqlite3.connect(database_path)
    try:
        organization_id = connection.execute("SELECT id FROM organizations LIMIT 1").fetchone()[0]
        branch_id = connection.execute("SELECT id FROM branches LIMIT 1").fetchone()[0]
        user_id = connection.execute("SELECT id FROM users LIMIT 1").fetchone()[0]
        for suffix in ("1", "2"):
            connection.execute(
                """
                INSERT INTO cash_shifts (
                    id, organization_id, branch_id, register_code, status,
                    opening_cash_cents, opened_at, closed_at, created_at
                ) VALUES (?, ?, ?, 'DUPLICATE', 'OPEN', 0, ?, NULL, ?)
                """,
                (
                    f"018f6f73-2d0a-74f0-8f1c-00000000981{suffix}",
                    organization_id,
                    branch_id,
                    "2026-08-11T18:00:00+00:00",
                    "2026-08-11T18:00:00+00:00",
                ),
            )
        connection.commit()
    finally:
        connection.close()
    duplicate = _sqlite_alembic(database_path, "upgrade", "0037_cash_movement_ledger")
    assert duplicate.returncode != 0
    assert "duplicate OPEN shifts" in duplicate.stdout + duplicate.stderr
    connection = sqlite3.connect(database_path)
    try:
        connection.execute("DELETE FROM cash_shifts WHERE register_code = 'DUPLICATE'")
        connection.execute(
            """
            INSERT INTO cash_shifts (
                id, organization_id, branch_id, register_code, status,
                opening_cash_cents, opened_at, closed_at, created_at
            ) VALUES (?, ?, ?, 'INCOHERENT', 'CLOSED', 0, ?, ?, ?)
            """,
            (
                "018f6f73-2d0a-74f0-8f1c-000000009819",
                organization_id,
                branch_id,
                "2026-08-11T18:00:00+00:00",
                "2026-08-11T18:00:00+00:00",
                "2026-08-11T18:00:00+00:00",
            ),
        )
        connection.execute(
            """
            INSERT INTO cash_movements (
                id, organization_id, branch_id, cash_shift_id, movement_type,
                amount_cents, reason_code, reason, source_type, source_id,
                actor_user_id, idempotency_key, status, reversal_of_id, created_at
            ) VALUES (?, ?, ?, ?, 'cash_reversal', 1, 'LEGACY', 'bad', 'legacy', NULL,
                      ?, 'incoherent', 'confirmed', ?, ?)
            """,
            (
                "018f6f73-2d0a-74f0-8f1c-000000009820",
                organization_id,
                branch_id,
                "018f6f73-2d0a-74f0-8f1c-000000009819",
                user_id,
                "018f6f73-2d0a-74f0-8f1c-000000009899",
                "2026-08-11T18:00:01+00:00",
            ),
        )
        connection.commit()
    finally:
        connection.close()
    incoherent = _sqlite_alembic(database_path, "upgrade", "0037_cash_movement_ledger")
    assert incoherent.returncode != 0
    assert "incoherent legacy reversal" in incoherent.stdout + incoherent.stderr


def test_sqlite_downgrade_blocks_new_ledger_history(tmp_path: Path) -> None:
    database_path = tmp_path / "pco003-history.db"
    assert _sqlite_alembic(database_path, "upgrade", "0037_cash_movement_ledger").returncode == 0
    connection = sqlite3.connect(database_path)
    try:
        organization_id = connection.execute("SELECT id FROM organizations LIMIT 1").fetchone()[0]
        user_id = connection.execute("SELECT id FROM users LIMIT 1").fetchone()[0]
        connection.execute(
            """
            INSERT INTO cash_movement_commands (
                id, organization_id, actor_user_id, target_movement_id, command_type,
                idempotency_key, request_hash, result, status, created_at
            ) VALUES (?, ?, ?, NULL, 'create', 'history', ?, '{}', 'completed', ?)
            """,
            (
                "018f6f73-2d0a-74f0-8f1c-000000009999",
                organization_id,
                user_id,
                "0" * 64,
                "2026-08-11T18:00:00+00:00",
            ),
        )
        connection.commit()
    finally:
        connection.close()
    blocked = _sqlite_alembic(database_path, "downgrade", "0036_cash_concepts")
    assert blocked.returncode != 0
    assert "Safe downgrade blocked: cash movement ledger history exists" in (
        blocked.stdout + blocked.stderr
    )


def test_postgres_roundtrip_preserves_legacy_row_and_schema_constraints() -> None:
    url = _postgres_url()
    reset = _postgres_alembic(url, "downgrade", "0036_cash_concepts")
    assert reset.returncode == 0, reset.stderr
    baseline = _postgres_alembic(url, "upgrade", "0036_cash_concepts")
    assert baseline.returncode == 0, baseline.stderr
    engine = sa.create_engine(url, pool_pre_ping=True)
    legacy_shift_id = "018f6f73-2d0a-74f0-8f1c-000000009871"
    movement_id = "018f6f73-2d0a-74f0-8f1c-000000009872"
    with engine.begin() as connection:
        connection.execute(
            sa.text("DELETE FROM cash_movements WHERE id = :movement_id"),
            {"movement_id": movement_id},
        )
        connection.execute(
            sa.text("DELETE FROM cash_shifts WHERE id = :shift_id"),
            {"shift_id": legacy_shift_id},
        )
        organization_id = connection.execute(
            sa.text("SELECT id FROM organizations LIMIT 1")
        ).scalar_one()
        branch_id = connection.execute(sa.text("SELECT id FROM branches LIMIT 1")).scalar_one()
        user_id = connection.execute(sa.text("SELECT id FROM users LIMIT 1")).scalar_one()
        connection.execute(
            sa.text(
                """
                INSERT INTO cash_shifts (
                    id, organization_id, branch_id, register_code, status,
                    opening_cash_cents, opened_at, closed_at, created_at
                ) VALUES (:id, :organization_id, :branch_id, 'PG-LEGACY', 'CLOSED',
                          10000, :time, :time, :time)
                """
            ),
            {
                "id": legacy_shift_id,
                "organization_id": organization_id,
                "branch_id": branch_id,
                "time": "2026-08-11T18:00:00+00:00",
            },
        )
        connection.execute(
            sa.text(
                """
                INSERT INTO cash_movements (
                    id, organization_id, branch_id, cash_shift_id, movement_type,
                    amount_cents, reason_code, reason, source_type, source_id,
                    actor_user_id, idempotency_key, status, reversal_of_id, created_at
                ) VALUES (:id, :organization_id, :branch_id, :shift_id, 'cash_reversal',
                          3000, 'LEGACY', 'legacy reversal', 'legacy', NULL,
                          :user_id, 'pg-legacy-001', 'confirmed', NULL, :time)
                """
            ),
            {
                "id": movement_id,
                "organization_id": organization_id,
                "branch_id": branch_id,
                "shift_id": legacy_shift_id,
                "user_id": user_id,
                "time": "2026-08-11T18:00:01+00:00",
            },
        )
    upgraded = _postgres_alembic(url, "upgrade", "0037_cash_movement_ledger")
    assert upgraded.returncode == 0, upgraded.stderr
    inspector = sa.inspect(engine)
    columns = {column["name"] for column in inspector.get_columns("cash_movements")}
    indexes = {index["name"] for index in inspector.get_indexes("cash_movements")}
    shift_indexes = {index["name"] for index in inspector.get_indexes("cash_shifts")}
    foreign_keys = {
        foreign_key["name"] for foreign_key in inspector.get_foreign_keys("cash_movements")
    }
    with engine.connect() as connection:
        legacy_values = connection.execute(
            sa.text(
                """
                SELECT movement_type, amount_cents, reason_code, reason, source_type,
                       status, idempotency_key, concept_id, evidence_refs
                FROM cash_movements WHERE id = :id
                """
            ),
            {"id": movement_id},
        ).one()
    assert legacy_values == (
        "cash_reversal",
        3000,
        "LEGACY",
        "legacy reversal",
        "legacy",
        "confirmed",
        "pg-legacy-001",
        None,
        None,
    )
    assert {"concept_id", "evidence_refs", "compensates_movement_id"} <= columns
    assert "ix_cash_movements_branch_shift_created" in indexes
    assert "uq_cash_movements_compensates_movement" in indexes
    assert "uq_cash_shifts_open_register" in shift_indexes
    assert {
        "fk_cash_movements_concept",
        "fk_cash_movements_concept_version",
        "fk_cash_movements_compensates",
    } <= foreign_keys
    downgraded = _postgres_alembic(url, "downgrade", "0036_cash_concepts")
    assert downgraded.returncode == 0, downgraded.stderr
    upgraded_again = _postgres_alembic(url, "upgrade", "0037_cash_movement_ledger")
    assert upgraded_again.returncode == 0, upgraded_again.stderr
    engine.dispose()
