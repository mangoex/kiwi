from __future__ import annotations

# ruff: noqa: E501
import hashlib
import json
import subprocess
import sys
import threading
from collections.abc import Generator
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from restaurant_os import models
from restaurant_os.database import get_session
from restaurant_os.internal_seed import apply_manifest
from restaurant_os.main import create_app
from restaurant_os.operational_guard import OperationalRouteGuard
from restaurant_os.operations import (
    BusinessError,
    acknowledge_print_attempt,
    advance_kds_task,
    claim_print_attempt,
    fail_print_attempt,
    retry_print_job,
)
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


def _client() -> TestClient:
    engine = create_engine(
        "sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    models.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    app = create_app()

    def override() -> Generator[Session, None, None]:
        with factory() as session:
            yield session

    app.dependency_overrides[get_session] = override
    client = TestClient(app)
    client.app.state.sec001_session_factory = factory
    return client


def _client_session(client: TestClient) -> Session:
    return client.app.state.sec001_session_factory()


def test_tc141_operational_routes_deny_anonymous_without_side_effects() -> None:
    client = _client()
    calls = (
        ("get", "/api/v1/kds/tasks", None),
        ("post", "/api/v1/kds/tasks/missing/transition", {"status": "IN_PROGRESS"}),
        ("get", "/api/v1/print-jobs", None),
        ("post", "/api/v1/print-jobs/missing/retry", None),
        ("post", "/api/v1/sync/commands", {"invalid": True}),
        ("get", "/api/v1/sync/events", None),
        ("get", "/api/v1/sync/status", None),
    )
    for method, path, payload in calls:
        request_kwargs = {"json": payload} if payload is not None else {}
        response = getattr(client, method)(path, **request_kwargs)
        assert response.status_code in {401, 403}, path
    assert client.get("/api/v1/kds/tasks", headers={"X-Actor-User-Id": "forged"}).status_code == 401
    assert (
        client.get("/api/v1/kds/tasks", headers={"Authorization": "Bearer invalid"}).status_code
        == 401
    )
    assert client.post("/api/v1/seed_menu").status_code == 404
    assert client.post("/api/v1/seed_branches").status_code == 404


def test_tc142_seed_is_not_an_http_surface() -> None:
    client = _client()
    schema = client.get("/openapi.json").json()
    assert "/api/v1/seed_menu" not in schema["paths"]
    assert "/api/v1/seed_branches" not in schema["paths"]


def _session() -> Session:
    engine = create_engine("sqlite+pysqlite://")
    models.metadata.create_all(engine)
    return Session(engine)


def test_tc143_device_expiry_revocation_capability_and_scope_leave_zero_effects() -> None:
    session = _session()
    now = datetime.now(timezone.utc)
    token = "device-" + "test-token"
    session.execute(
        models.device_credentials.insert().values(
            id="device-a",
            organization_id="org-a",
            branch_id="branch-a",
            capability="kds.operate",
            token_hash=hashlib.sha256(token.encode()).hexdigest(),
            key_version="v1",
            expires_at=now + timedelta(minutes=5),
            revoked_at=None,
            created_at=now,
        )
    )
    session.commit()
    guard = OperationalRouteGuard()
    assert (
        guard.require_device(session, token, "kds.operate", "org-a", "branch-a").user_id
        == "device-a"
    )
    before_denials = session.execute(models.device_credentials.select()).mappings().all()
    for capability, organization, branch in (
        ("print.agent", "org-a", "branch-a"),
        ("kds.operate", "org-b", "branch-a"),
        ("kds.operate", "org-a", "branch-b"),
    ):
        with pytest.raises(HTTPException):
            guard.require_device(session, token, capability, organization, branch)
    session.execute(
        models.device_credentials.update()
        .where(models.device_credentials.c.id == "device-a")
        .values(revoked_at=now)
    )
    session.commit()
    with pytest.raises(HTTPException):
        guard.require_device(session, token, "kds.operate", "org-a", "branch-a")
    with pytest.raises(HTTPException):
        guard.require_device(session, "invalid-token", "kds.operate", "org-a", "branch-a")
    session.execute(
        models.device_credentials.insert().values(
            id="device-expired",
            organization_id="org-a",
            branch_id="branch-a",
            capability="kds.operate",
            token_hash=hashlib.sha256(b"expired").hexdigest(),
            key_version="v1",
            expires_at=now - timedelta(seconds=1),
            revoked_at=None,
            created_at=now,
        )
    )
    session.commit()
    with pytest.raises(HTTPException):
        guard.require_device(session, "expired", "kds.operate", "org-a", "branch-a")
    after_denials = session.execute(models.device_credentials.select()).mappings().all()
    assert [row["id"] for row in after_denials] == [row["id"] for row in before_denials] + [
        "device-expired"
    ]
    denials = (
        session.execute(
            models.audit_events.select().where(
                models.audit_events.c.action == "operational_route.denied"
            )
        )
        .mappings()
        .all()
    )
    assert denials and all("token" not in json.dumps(row["payload"]).lower() for row in denials)


def test_tc144_print_attempts_are_idempotent_and_ack_is_the_only_completion() -> None:
    session = _session()
    now = datetime.now(timezone.utc)
    session.execute(
        models.print_jobs.insert().values(
            id="job-a",
            organization_id="org-a",
            branch_id="branch-a",
            order_id="order-a",
            job_type="ticket",
            target="printer",
            status="FAILED",
            payload={},
            attempts=0,
            last_error="offline",
            created_at=now,
            printed_at=None,
        )
    )
    session.commit()
    first = retry_print_job(session, "job-a", "retry-key-0001", "branch-a")
    replay = retry_print_job(session, "job-a", "retry-key-0001", "branch-a")
    assert first["attempt"]["status"] == "QUEUED" and replay["replayed"] is True
    with pytest.raises(BusinessError) as active_attempt:
        retry_print_job(session, "job-a", "retry-key-0002", "branch-a")
    assert active_attempt.value.code == "print_job_transition_invalid"
    claimed = claim_print_attempt(session, first["attempt"]["id"], "device-a")
    assert claimed["status"] == "CLAIMED"
    with pytest.raises(BusinessError):
        acknowledge_print_attempt(session, first["attempt"]["id"], "other-device", "ack")
    acknowledged = acknowledge_print_attempt(session, first["attempt"]["id"], "device-a", "ack")
    assert acknowledged["status"] == "PRINTED"
    assert (
        acknowledge_print_attempt(session, first["attempt"]["id"], "device-a", "ack")["status"]
        == "PRINTED"
    )
    with pytest.raises(BusinessError):
        acknowledge_print_attempt(session, first["attempt"]["id"], "device-a", "altered")
    assert retry_print_job(session, "job-a", "retry-key-0001", "branch-a")["replayed"] is True
    assert session.execute(models.print_jobs.select()).mappings().one()["status"] == "PRINTED"


def test_tc143_print_agent_pull_is_scoped_and_denies_invalid_devices() -> None:
    client = _client()
    now = datetime.now(timezone.utc)
    token = "pull-device-token"
    with _client_session(client) as session:
        session.execute(
            models.device_credentials.insert(),
            [
                {"id": "agent-a", "organization_id": "org-a", "branch_id": "branch-a", "capability": "print.agent", "token_hash": hashlib.sha256(token.encode()).hexdigest(), "key_version": "v1", "expires_at": now + timedelta(minutes=5), "revoked_at": None, "created_at": now},
                {"id": "agent-b", "organization_id": "org-b", "branch_id": "branch-b", "capability": "print.agent", "token_hash": hashlib.sha256(b"other-agent").hexdigest(), "key_version": "v1", "expires_at": now + timedelta(minutes=5), "revoked_at": None, "created_at": now},
                {"id": "agent-expired", "organization_id": "org-a", "branch_id": "branch-a", "capability": "print.agent", "token_hash": hashlib.sha256(b"expired-agent").hexdigest(), "key_version": "v1", "expires_at": now - timedelta(seconds=1), "revoked_at": None, "created_at": now},
            ],
        )
        for job_id, organization_id, branch_id in (("pull-a", "org-a", "branch-a"), ("pull-b", "org-b", "branch-b")):
            session.execute(models.print_jobs.insert().values(id=job_id, organization_id=organization_id, branch_id=branch_id, order_id=job_id, job_type="ticket", target="printer", status="QUEUED", payload={"safe": True}, attempts=1, last_error=None, created_at=now, printed_at=None))
            session.execute(models.print_attempts.insert().values(id=f"attempt-{job_id}", print_job_id=job_id, organization_id=organization_id, branch_id=branch_id, idempotency_key=f"key-{job_id}", request_hash="a" * 64, status="QUEUED", created_at=now))
        session.commit()
    response = client.get("/api/v1/print-attempts/pull", headers={"X-Device-Token": token})
    assert response.status_code == 200
    assert [item["attempt_id"] for item in response.json()] == ["attempt-pull-a"]
    assert client.get("/api/v1/print-attempts/pull", headers={"X-Device-Token": "expired-agent"}).status_code == 403
    with _client_session(client) as session:
        session.execute(models.device_credentials.update().where(models.device_credentials.c.id == "agent-a").values(revoked_at=now))
        session.commit()
    assert client.get("/api/v1/print-attempts/pull", headers={"X-Device-Token": token}).status_code == 403


def test_tc144_agent_failure_is_atomic_replayable_and_allows_next_retry() -> None:
    session = _session()
    now = datetime.now(timezone.utc)
    session.execute(models.print_jobs.insert().values(id="job-fail", organization_id="org-a", branch_id="branch-a", order_id="order-a", job_type="ticket", target="printer", status="FAILED", payload={}, attempts=0, last_error=None, created_at=now, printed_at=None))
    session.commit()
    attempt = retry_print_job(session, "job-fail", "retry-fail-001", "branch-a")["attempt"]
    claim_print_attempt(session, attempt["id"], "device-a")
    with pytest.raises(RuntimeError):
        fail_print_attempt(session, attempt["id"], "device-a", "OFFLINE", fail_after_update=True)
    assert session.execute(models.print_attempts.select()).mappings().one()["status"] == "CLAIMED"
    failed = fail_print_attempt(session, attempt["id"], "device-a", "OFFLINE")
    assert failed["status"] == "FAILED" and failed["error_code"] == "OFFLINE"
    assert fail_print_attempt(session, attempt["id"], "device-a", "OFFLINE")["status"] == "FAILED"
    with pytest.raises(BusinessError):
        fail_print_attempt(session, attempt["id"], "device-b", "OFFLINE")
    next_attempt = retry_print_job(session, "job-fail", "retry-fail-002", "branch-a")
    assert next_attempt["replayed"] is False


def test_tc142_internal_seed_dry_run_apply_and_replay_are_deterministic() -> None:
    session = _session()
    manifest = {
        "organization_id": "org-seed",
        "environment": "test",
        "operations": [{"type": "ensure_organization", "id": "org-seed", "name": "Synthetic Seed"}],
    }
    assert apply_manifest(session, manifest, apply=False, actor_id="operator")["dry_run"] is True
    assert session.execute(models.organizations.select()).all() == []
    applied = apply_manifest(session, manifest, apply=True, actor_id="operator")
    replay = apply_manifest(session, manifest, apply=True, actor_id="operator")
    assert applied["replayed"] is False and replay["replayed"] is True
    assert session.execute(models.organizations.select()).mappings().one()["id"] == "org-seed"
    with pytest.raises(ValueError):
        apply_manifest(
            session,
            {
                "organization_id": "org-seed",
                "environment": "test",
                "operations": [{"type": "ensure_organization", "id": "other", "name": "Other"}],
            },
            apply=True,
            actor_id="operator",
        )
    assert session.execute(models.organizations.select()).mappings().one()["id"] == "org-seed"


def test_tc144_claim_race_and_injected_ack_failure_leave_no_partial_state() -> None:
    session = _session()
    now = datetime.now(timezone.utc)
    session.execute(
        models.print_jobs.insert().values(
            id="job-race",
            organization_id="org-a",
            branch_id="branch-a",
            order_id="order-a",
            job_type="ticket",
            target="printer",
            status="FAILED",
            payload={},
            attempts=0,
            last_error=None,
            created_at=now,
            printed_at=None,
        )
    )
    session.commit()
    attempt = retry_print_job(session, "job-race", "retry-race-0001", "branch-a")["attempt"]
    with pytest.raises(RuntimeError):
        claim_print_attempt(session, attempt["id"], "device-a", fail_after_update=True)
    assert session.execute(models.print_attempts.select()).mappings().one()["status"] == "QUEUED"
    claimed = claim_print_attempt(session, attempt["id"], "device-a")
    with pytest.raises(BusinessError):
        claim_print_attempt(session, attempt["id"], "device-b")
    with pytest.raises(RuntimeError):
        acknowledge_print_attempt(session, claimed["id"], "device-a", "ack", fail_after_update=True)
    assert session.execute(models.print_attempts.select()).mappings().one()["status"] == "CLAIMED"
    assert session.execute(models.print_jobs.select()).mappings().one()["status"] == "CLAIMED"


def test_tc144_claim_race_uses_two_connections_and_one_winner(tmp_path: Path) -> None:
    engine = create_engine(
        f"sqlite:///{tmp_path / 'claim-race.db'}",
        connect_args={"check_same_thread": False, "timeout": 5},
    )
    models.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as setup:
        now = datetime.now(timezone.utc)
        setup.execute(
            models.print_jobs.insert().values(
                id="job-concurrent",
                organization_id="org-a",
                branch_id="branch-a",
                order_id="order-a",
                job_type="ticket",
                target="printer",
                status="FAILED",
                payload={},
                attempts=0,
                last_error=None,
                created_at=now,
                printed_at=None,
            )
        )
        setup.commit()
        attempt_id = retry_print_job(setup, "job-concurrent", "retry-concurrent-1", "branch-a")[
            "attempt"
        ]["id"]
    barrier = threading.Barrier(2)
    outcomes: list[str] = []

    def contender(device_id: str) -> None:
        with factory() as concurrent_session:
            barrier.wait(timeout=5)
            try:
                claim_print_attempt(concurrent_session, attempt_id, device_id)
                outcomes.append("claimed")
            except (BusinessError, OperationalError):
                outcomes.append("denied")

    threads = [
        threading.Thread(target=contender, args=(device_id,))
        for device_id in ("device-a", "device-b")
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)
        assert not thread.is_alive()
    with factory() as verify:
        attempt = verify.execute(models.print_attempts.select()).mappings().one()
        job = verify.execute(models.print_jobs.select()).mappings().one()
    assert sorted(outcomes) == ["claimed", "denied"]
    assert attempt["status"] == job["status"] == "CLAIMED"
    assert attempt["claimed_by_device_id"] in {"device-a", "device-b"}


def test_tc144_audit_records_actor_without_ack_material() -> None:
    session = _session()
    now = datetime.now(timezone.utc)
    session.execute(
        models.print_jobs.insert().values(
            id="job-audit",
            organization_id="org-a",
            branch_id="branch-a",
            order_id="order-a",
            job_type="ticket",
            target="printer",
            status="FAILED",
            payload={},
            attempts=0,
            last_error=None,
            created_at=now,
            printed_at=None,
        )
    )
    session.commit()
    attempt = retry_print_job(
        session, "job-audit", "retry-audit-001", "branch-a", actor_user_id="human-a"
    )["attempt"]
    claim_print_attempt(session, attempt["id"], "device-a")
    acknowledge_print_attempt(session, attempt["id"], "device-a", "ack-material-must-not-appear")
    events = session.execute(models.audit_events.select()).mappings().all()
    by_action = {event["action"]: event for event in events}
    assert by_action["print_job.retried"]["actor_user_id"] == "human-a"
    assert by_action["print_attempt.claimed"]["payload"]["device_id"] == "device-a"
    assert by_action["print_attempt.acknowledged"]["payload"]["device_id"] == "device-a"
    assert "ack-material-must-not-appear" not in json.dumps([event["payload"] for event in events])


def test_tc144_database_rejects_incoherent_print_attempt_state() -> None:
    session = _session()
    now = datetime.now(timezone.utc)
    session.execute(
        models.print_jobs.insert().values(
            id="job-invariant", organization_id="org-a", branch_id="branch-a", order_id="order-a",
            job_type="ticket", target="printer", status="FAILED", payload={}, attempts=0,
            last_error=None, created_at=now, printed_at=None,
        )
    )
    session.commit()
    with pytest.raises(IntegrityError):
        session.execute(
            models.print_attempts.insert().values(
                id="attempt-invariant", print_job_id="job-invariant", organization_id="org-a",
                branch_id="branch-a", idempotency_key="invariant-key-001", request_hash="a" * 64,
                status="QUEUED", claimed_by_device_id="device-a", claimed_at=now, ack_hash=None,
                created_at=now, acked_at=None,
            )
        )
        session.commit()
    session.rollback()


def test_tc143_kds_audit_retains_human_or_device_actor_without_credential_material() -> None:
    session = _session()
    now = datetime.now(timezone.utc)
    session.execute(
        models.production_tasks.insert().values(
            id="task-audit",
            organization_id="org-a",
            branch_id="branch-a",
            order_id="order-a",
            order_line_id="line-a",
            station="hot",
            status="PENDING",
            product_name="Synthetic",
            quantity=1,
            created_at=now,
            started_at=None,
            completed_at=None,
        )
    )
    session.commit()
    advance_kds_task(session, "task-audit", "IN_PROGRESS", "branch-a", actor_user_id="human-a")
    event = (
        session.execute(
            models.audit_events.select().where(
                models.audit_events.c.action == "production_task.transitioned"
            )
        )
        .mappings()
        .one()
    )
    assert event["actor_user_id"] == "human-a"
    assert "token" not in json.dumps(event["payload"]).lower()


def test_tc142_cli_uses_explicit_sqlite_url_and_replays(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "organization_id": "org-cli",
                "environment": "test",
                "operations": [
                    {"type": "ensure_organization", "id": "org-cli", "name": "Synthetic"}
                ],
            }
        )
    )
    database_url = f"sqlite:///{tmp_path / 'seed.db'}"
    command = [
        sys.executable,
        "-m",
        "restaurant_os.internal_seed",
        str(manifest),
        "--apply",
        "--actor",
        "operator",
        "--confirm-environment",
        "test",
        "--sqlite-url",
        database_url,
    ]
    first = subprocess.run(command, cwd=Path(__file__).parents[1], text=True, capture_output=True)
    second = subprocess.run(command, cwd=Path(__file__).parents[1], text=True, capture_output=True)
    assert first.returncode == second.returncode == 0
    assert json.loads(first.stdout)["replayed"] is False
    assert json.loads(second.stdout)["replayed"] is True
