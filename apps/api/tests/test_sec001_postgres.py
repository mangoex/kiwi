from __future__ import annotations

import os
import subprocess
import sys
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import sqlalchemy as sa
from restaurant_os import models
from restaurant_os.operations import BusinessError, claim_print_attempt
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

API_DIR = Path(__file__).resolve().parents[1]


def _validate_sec001_postgres_url(url: str) -> str:
    parsed = make_url(url)
    database = parsed.database or ""
    if (
        not parsed.drivername.startswith("postgresql")
        or parsed.host not in {"127.0.0.1", "localhost"}
        or not database.startswith("sec001_")
        or database in {"restaurantos", "kiwi-postgres"}
    ):
        raise RuntimeError(
            "SEC001_TEST_POSTGRES_URL must be local PostgreSQL with database sec001_*"
        )
    return url


def _sec001_postgres_url() -> str:
    url = os.environ.get("SEC001_TEST_POSTGRES_URL")
    if not url:
        pytest.skip("SEC001_TEST_POSTGRES_URL is not configured")
    return _validate_sec001_postgres_url(url)


def _alembic_environment(url: str) -> dict[str, str]:
    """Give Alembic the already validated SEC URL without generic URL fallback."""
    environment = dict(os.environ)
    environment.pop("DATABASE_URL", None)
    environment["RESTAURANTOS_DATABASE_URL"] = url
    return environment


def _run_alembic(url: str, *arguments: str) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "alembic.ini", *arguments],
        cwd=API_DIR,
        env=_alembic_environment(url),
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stdout + result.stderr)


def _reset_and_upgrade(url: str) -> None:
    """Destructive only to validated local sec001_* databases; never uses generic URLs."""
    engine = sa.create_engine(url)
    try:
        with engine.begin() as connection:
            connection.execute(sa.text("DROP SCHEMA public CASCADE"))
            connection.execute(sa.text("CREATE SCHEMA public"))
    finally:
        engine.dispose()
    _run_alembic(url, "upgrade", "head")


@pytest.mark.parametrize(
    "url",
    [
        "postgresql+psycopg://u:p@example.test/sec001_safe",
        "postgresql+psycopg://u:p@localhost/restaurantos",
        "sqlite:///sec001_safe",
    ],
)
def test_sec001_postgres_url_guard_rejects_without_connecting(url: str) -> None:
    with pytest.raises(RuntimeError):
        _validate_sec001_postgres_url(url)


def test_sec001_alembic_subprocess_isolated_from_generic_database_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    url = "postgresql+psycopg://postgres:postgres@127.0.0.1:5432/sec001_test"
    monkeypatch.setenv("DATABASE_URL", "postgresql://untrusted.example/not-used")
    monkeypatch.setenv("RESTAURANTOS_DATABASE_URL", "postgresql://untrusted.example/not-used")
    captured: dict[str, object] = {}

    def fake_run(arguments: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        captured["arguments"] = arguments
        captured.update(kwargs)
        return subprocess.CompletedProcess(arguments, 0, "", "")

    monkeypatch.setattr(subprocess, "run", fake_run)

    _run_alembic(url, "upgrade", "head")

    environment = captured["env"]

    assert isinstance(environment, dict)
    assert environment["RESTAURANTOS_DATABASE_URL"] == url
    assert "DATABASE_URL" not in environment
    assert API_DIR.is_dir()
    assert (API_DIR / "alembic.ini").is_file()
    assert captured["cwd"] == API_DIR
    assert captured["arguments"] == [
        sys.executable,
        "-m",
        "alembic",
        "-c",
        "alembic.ini",
        "upgrade",
        "head",
    ]


def test_sec001_postgres_migration_constraints_and_downgrade_guard() -> None:
    """Opt-in only: no generic database environment variable is read by this gate."""
    url = _sec001_postgres_url()
    _reset_and_upgrade(url)
    _run_alembic(url, "downgrade", "0042_recipe_reports")
    _run_alembic(url, "upgrade", "head")
    engine = sa.create_engine(url)
    now = datetime.now(timezone.utc)
    try:
        with engine.begin() as connection:
            constraints = (
                connection.execute(
                    sa.text(
                        "SELECT conname FROM pg_constraint "
                        "WHERE conrelid = 'print_attempts'::regclass"
                    )
                )
                .scalars()
                .all()
            )
            assert {"ck_print_attempt_state_fields", "ck_print_attempt_status"} <= set(constraints)
            connection.execute(
                sa.text(
                    "INSERT INTO device_credentials "
                    "(id, organization_id, branch_id, capability, token_hash, key_version, "
                    "expires_at, created_at) VALUES (:id, :organization_id, :branch_id, "
                    "'print.agent', :token_hash, 'v1', :expires_at, :created_at)"
                ),
                {
                    "id": "sec001-postgres-history",
                    "organization_id": "018f6f73-2d0a-74f0-8f1c-000000000001",
                    "branch_id": "018f6f73-2d0a-74f0-8f1c-000000000003",
                    "token_hash": "a" * 64,
                    "expires_at": now + timedelta(minutes=1),
                    "created_at": now,
                },
            )
        with pytest.raises(RuntimeError, match="SEC-001 device or print history blocks downgrade"):
            _run_alembic(url, "downgrade", "0042_recipe_reports")
    finally:
        engine.dispose()


def test_sec001_postgres_claim_race_has_one_winner() -> None:
    url = _sec001_postgres_url()
    _reset_and_upgrade(url)
    engine = sa.create_engine(url)
    now = datetime.now(timezone.utc)
    try:
        with Session(engine) as session:
            session.execute(
                models.print_jobs.insert().values(
                    id="sec001-race-job",
                    organization_id="018f6f73-2d0a-74f0-8f1c-000000000001",
                    branch_id="018f6f73-2d0a-74f0-8f1c-000000000003",
                    order_id="sec001-race-order",
                    job_type="ticket",
                    target="printer",
                    status="QUEUED",
                    payload={},
                    attempts=1,
                    last_error=None,
                    created_at=now,
                    printed_at=None,
                )
            )
            session.execute(
                models.print_attempts.insert().values(
                    id="sec001-race-attempt",
                    print_job_id="sec001-race-job",
                    organization_id="018f6f73-2d0a-74f0-8f1c-000000000001",
                    branch_id="018f6f73-2d0a-74f0-8f1c-000000000003",
                    idempotency_key="sec001-race-key",
                    request_hash="a" * 64,
                    status="QUEUED",
                    created_at=now,
                )
            )
            session.commit()
        barrier = threading.Barrier(2)
        outcomes: list[str] = []

        def claim(device: str) -> None:
            with Session(engine) as session:
                barrier.wait(timeout=10)
                try:
                    claim_print_attempt(session, "sec001-race-attempt", device)
                    outcomes.append("claimed")
                except BusinessError:
                    outcomes.append("denied")

        workers = [
            threading.Thread(target=claim, args=(device,)) for device in ("agent-a", "agent-b")
        ]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join(timeout=10)
        assert outcomes.count("claimed") == outcomes.count("denied") == 1
    finally:
        engine.dispose()
