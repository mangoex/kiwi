"""TDD-TS-149: read-only public tracking, privacy and operational projection."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from jsonschema import validate
from restaurant_os import models
from test_platform_api import BRANCH_ID, _admin_headers, _test_session_factory
from test_public_order_intents import (
    _AvailableRateLimiter,
    _BrokenRateLimiter,
    _capture_counts,
    _client_with_seeded_database,
    _enable_public_order_capture,
    _intent_id,
    _payload,
    _post_intent,
)


def _created() -> tuple[TestClient, str]:
    client = _client_with_seeded_database()
    _enable_public_order_capture(client)
    client.app.state.public_order_tracking_rate_limiter = _AvailableRateLimiter()
    result = _post_intent(client, _payload())
    assert result.status_code == 201
    return client, str(result.json()["public_reference"])


def _track(client: TestClient, reference: str) -> Any:
    statements: list[str] = []
    with _test_session_factory(client)() as session:
        bind = session.get_bind()

    def capture(*args: Any) -> None:
        statements.append(str(args[2]).lstrip().split()[0].upper())

    sa.event.listen(bind, "before_cursor_execute", capture)
    try:
        result = client.get(f"/api/v1/public/order-intents/{reference}?tracking=true")
    finally:
        sa.event.remove(bind, "before_cursor_execute", capture)
    assert not set(statements) & {
        "INSERT", "UPDATE", "DELETE", "CREATE", "DROP", "ALTER", "TRUNCATE", "REPLACE",
    }
    return result


def test_pending_tracking_is_minimal_read_only_and_uncached() -> None:
    client, reference = _created()
    before = _capture_counts(client)
    result = _track(client, reference)
    assert result.status_code == 200
    data = result.json()
    assert data["display_status"] == "PENDING_REVIEW"
    assert data["operational_status"] is None and data["folio"] is None
    assert data["branch_id"] == BRANCH_ID and data["service_type"] == "takeout"
    assert not data["terminal"]
    assert set(data) == {
        "public_reference", "status", "version", "total_cents", "branch_id", "branch_name",
        "service_type", "created_at", "updated_at", "operational_status", "display_status",
        "folio", "terminal",
    }
    assert result.headers["cache-control"] == "no-store"
    assert result.headers["referrer-policy"] == "no-referrer"
    schema_path = (
        Path(__file__).resolve().parents[3]
        / "packages/contracts/schemas/public-order-tracking-v1.schema.json"
    )
    validate(data, json.loads(schema_path.read_text(encoding="utf-8")))
    assert _capture_counts(client) == before
    assert set(client.get(f"/api/v1/public/order-intents/{reference}").json()) == {
        "public_reference", "status", "version", "total_cents",
    }


def test_tracking_follows_scoped_order_and_preserves_closed_return() -> None:
    client, reference = _created()
    accepted = client.post(
        f"/api/v1/order-intents/{_intent_id(client, reference)}/accept", headers=_admin_headers(),
        json={"expected_version": 1},
    )
    assert accepted.status_code == 201, accepted.text
    order_id = accepted.json()["id"]
    for status in ("ACCEPTED", "IN_PRODUCTION", "READY", "IN_DELIVERY", "DELIVERED"):
        with _test_session_factory(client)() as session:
            session.execute(models.orders.update().where(models.orders.c.id == order_id).values(
                status=status,
            ))
            session.commit()
        data = _track(client, reference).json()
        assert data["display_status"] == status
        assert data["folio"] == accepted.json()["folio"]
    with _test_session_factory(client)() as session:
        session.execute(models.orders.update().where(models.orders.c.id == order_id).values(
            status="CLOSED",
        ))
        session.commit()
    assert _track(client, reference).json()["display_status"] == "CLOSED"
    with _test_session_factory(client)() as session:
        session.execute(models.order_events.insert().values(
            id=str(uuid4()), order_id=order_id, event_type="RETURNED", payload={},
            created_at=datetime(2026, 10, 16, 12, 0, tzinfo=timezone.utc),
        ))
        session.commit()
    assert _track(client, reference).json()["display_status"] == "RETURNED"
    assert _track(client, reference).json()["terminal"]
    with _test_session_factory(client)() as session:
        session.execute(models.public_order_intents.update().where(
            models.public_order_intents.c.public_reference == reference,
        ).values(
            accepted_order_id=None,
        ))
        session.commit()
    assert _track(client, reference).status_code == 404


def test_tracking_rejects_cross_branch_order_pointer_without_leaking_details() -> None:
    client, reference = _created()
    accepted = client.post(
        f"/api/v1/order-intents/{_intent_id(client, reference)}/accept", headers=_admin_headers(),
        json={"expected_version": 1},
    )
    assert accepted.status_code == 201
    with _test_session_factory(client)() as session:
        branch = dict(session.execute(sa.select(models.branches).where(
            models.branches.c.id == BRANCH_ID,
        )).mappings().one())
        branch.update(id=str(uuid4()), code="TRACKING-OTHER", name="Other branch")
        session.execute(models.branches.insert().values(**branch))
        session.execute(models.orders.update().where(
            models.orders.c.id == accepted.json()["id"],
        ).values(branch_id=branch["id"]))
        session.commit()
    response = _track(client, reference)
    assert response.status_code == 404
    assert "Other branch" not in response.text


@pytest.mark.parametrize("reference", [
    "SUC01-00001", str(uuid4()), "PI-INVALID", "PI-" + uuid4().hex.upper(),
])
def test_tracking_never_resolves_operational_folio_or_internal_id(reference: str) -> None:
    client, _ = _created()
    assert _track(client, reference).status_code == 404


def test_tracking_limiter_fails_closed_and_does_not_trust_forwarded_ip() -> None:
    client, reference = _created()
    signals: list[tuple[str, str]] = []

    class Denied:
        def allow(self, bucket: str, signal: str) -> bool:
            signals.append((bucket, signal))
            return False

    client.app.state.public_order_tracking_rate_limiter = Denied()
    result = client.get(f"/api/v1/public/order-intents/{reference}?tracking=true", headers={
        "X-Forwarded-For": "spoofed", "User-Agent": "tracking-test",
    })
    assert result.status_code == 429
    assert result.headers["retry-after"] == "60"
    assert signals == [("tracking:v1", f"testclient\ntracking-test\n{reference}")]
    assert result.headers["cache-control"] == "no-store"
    client.app.state.public_order_tracking_rate_limiter = _BrokenRateLimiter()
    assert _track(client, reference).status_code == 503
    client.app.state.public_order_tracking_rate_limiter = None
    assert _track(client, reference).status_code == 503
