"""F1-05 must preserve the real workspace/intent execution boundary."""

from typing import Any

import sqlalchemy as sa
from restaurant_os import models
from restaurant_os.operations import ORGANIZATION_ID, _now
from test_branch_workspace_authority import workspace as workspace
from test_corte_ciego_f1_red import assert_blind
from test_operational_intents import _grant_permission, _prepare_command
from test_operational_intents import operational as operational
from test_platform_api import BRANCH_ID


def activate(factory: Any) -> None:
    with factory() as session:
        for code in ("cash.shift.read", "cash.shift.open", "cash.shift.close"):
            _grant_permission(session, code)
        session.execute(
            models.blind_cash_policy_revisions.insert().values(
                organization_id=ORGANIZATION_ID,
                branch_id=BRANCH_ID,
                revision=1,
                manifest_digest="c" * 64,
                minimum_api_version=2,
                minimum_client_version=2,
                minimum_gateway_version=2,
                event="activated",
                created_at=_now(),
            )
        )
        session.commit()


def test_v2_shift_preserves_intent_atomicity_and_blind_replay(operational: Any) -> None:
    client, factory, headers = operational
    activate(factory)
    body = {"branch_id": BRANCH_ID, "register_id": "F105-INTENT", "opening_cash_cents": 100}
    intent = _prepare_command(client, headers, "cash.shift.open", body, "f105-intent-open", None)
    command_headers = {
        **headers,
        "Idempotency-Key": "f105-intent-open",
        "X-Operational-Intent": intent["id"],
    }
    result = client.post("/api/v2/cash/shifts/open", headers=command_headers, json=body)
    assert result.status_code == 200, result.text
    assert_blind(result.json())
    shift = result.json()["resource_id"]
    replay = client.post("/api/v2/cash/shifts/open", headers=command_headers, json=body)
    assert replay.status_code == 200, replay.text
    assert replay.json()["replay"] is True
    assert replay.json()["command_id"] == result.json()["command_id"]
    with factory() as session:
        assert (
            session.scalar(
                sa.select(models.operational_command_intents.c.state).where(
                    models.operational_command_intents.c.id == intent["id"],
                )
            )
            == "applied"
        )
    resolved = client.post(f"/api/v1/operational-intents/{intent['id']}/resolve", headers=headers)
    assert resolved.status_code == 200, resolved.text
    intent = _prepare_command(client, headers, "cash.shift.close", {}, "f105-intent-close", shift)
    result = client.post(
        f"/api/v2/cash/shifts/{shift}/close-operationally",
        json={},
        headers={
            **headers,
            "Idempotency-Key": "f105-intent-close",
            "X-Operational-Intent": intent["id"],
        },
    )
    assert result.status_code == 200, result.text
    assert_blind(result.json())
    assert result.json()["status"] == "OPERATIVELY_CLOSED"


def test_v2_cannot_bypass_required_intent(operational: Any) -> None:
    client, factory, headers = operational
    activate(factory)
    with factory() as session:
        before = list(session.scalars(sa.select(models.cash_shift_commands.c.id)))
    response = client.post(
        "/api/v2/cash/shifts/open",
        json={
            "branch_id": BRANCH_ID,
            "register_id": "F105-INTENT",
            "opening_cash_cents": 100,
        },
        headers={**headers, "Idempotency-Key": "f105-no-intent"},
    )
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["code"] == "operational_command_required"
    with factory() as session:
        assert list(session.scalars(sa.select(models.cash_shift_commands.c.id))) == before
