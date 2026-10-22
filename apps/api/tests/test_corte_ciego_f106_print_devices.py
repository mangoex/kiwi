"""TC-450/462: only the assigned printer can read one projected job payload."""

import json
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import jsonschema
import pytest
import sqlalchemy as sa
from corte_ciego_fixtures import ident
from restaurant_os import models
from restaurant_os import operations as ops
from sqlalchemy.orm import Session
from test_corte_ciego_f106_orders import AttendedWorld, attended_world
from test_platform_api import BRANCH_ID
from test_sec001_operational_boundary import _device_credential

__all__ = ["attended_world"]


@dataclass
class PrintWorld:
    world: AttendedWorld
    attempts: dict[str, str]
    device_id: str
    token: str

    def headers(self) -> dict[str, str]:
        return {"X-Device-Token": self.token}

    def claim(self, kind: str) -> Any:
        return self.world.client.post(
            f"/api/v1/print-attempts/{self.attempts[kind]}/claim",
            headers=self.headers(),
        )

    def payload(self, kind: str, token: str | None = None) -> Any:
        return self.world.client.get(
            f"/api/v1/print-attempts/{self.attempts[kind]}/payload",
            headers={"X-Device-Token": token or self.token},
        )


@pytest.fixture
def printers(attended_world: AttendedWorld) -> Iterator[PrintWorld]:
    world = attended_world
    with world.sessions() as session:
        for suffix in ("a", "b"):
            _device_credential(
                session,
                device_id=ident("printer-" + suffix),
                token=ident("printer-credential-" + suffix),
                capability="print.agent",
                organization_id=ops.ORGANIZATION_ID,
                branch_id=BRANCH_ID,
            )
        order = dict(
            session.execute(sa.select(models.orders).where(models.orders.c.id == world.order_id))
            .mappings()
            .one()
        )
        jobs = ops._create_print_jobs(session, order, {"id": ident("print-payment")}, ops._now())
        for job in jobs:
            value = {
                **job["payload"],
                "private_extra": "PRIVATE-DEVICE",
                "lines": [
                    {
                        **job["payload"]["lines"][0],
                        "cost_cents": 444,
                        "selected_modifiers": [
                            {
                                "option_id": "extra",
                                "option_name": "Extra",
                                "kitchen_text": "Sin salsa",
                                "price_delta_cents": 500,
                                "recipe_snapshot": {"cost_cents": 444},
                            }
                        ],
                    }
                ],
            }
            session.execute(
                models.print_jobs.update()
                .where(models.print_jobs.c.id == job["id"])
                .values(payload=value)
            )
        session.commit()
        attempts = {
            kind: str(
                session.scalar(
                    sa.select(models.print_attempts.c.id).where(
                        models.print_attempts.c.print_job_id == job["id"]
                    )
                )
            )
            for job in jobs
            for kind in (job["job_type"],)
        }
    yield PrintWorld(world, attempts, ident("printer-a"), ident("printer-credential-a"))


def test_device_pull_lists_metadata_without_ticket_snapshots(printers: PrintWorld) -> None:
    response = printers.world.client.get("/api/v1/print-attempts/pull", headers=printers.headers())
    assert response.status_code == 200, response.text
    assert {row["attempt_id"] for row in response.json()} == set(printers.attempts.values())
    assert all("payload" not in row for row in response.json())
    assert all(row["created_at"].endswith("Z") for row in response.json())
    assert "PRIVATE-DEVICE" not in response.text
    assert response.headers["cache-control"] == "no-store"


def test_direct_pull_cannot_omit_current_device(printers: PrintWorld) -> None:
    with printers.world.sessions() as session, pytest.raises(ops.AuthorizationError):
        ops.list_queued_print_attempts(session, ops.ORGANIZATION_ID, BRANCH_ID)


def test_payload_requires_claim_and_current_assigned_device(printers: PrintWorld) -> None:
    assert printers.payload("ticket").status_code == 403
    assert printers.claim("ticket").status_code == 200
    assert printers.payload("ticket", ident("printer-credential-b")).status_code == 403
    response = printers.payload("ticket")
    assert response.status_code == 200, response.text
    assert response.json()["payload"]["total_cents"] == 9500
    jsonschema.validate(
        response.json()["payload"],
        json.loads(
            (
                Path(__file__).resolve().parents[3]
                / "packages/contracts/schemas/print-ticket-payload-v2.schema.json"
            ).read_text(encoding="utf-8")
        ),
    )
    assert response.json()["payload"]["lines"][0]["line_total_cents"] == 9500
    assert "PRIVATE-DEVICE" not in response.text and "recipe_snapshot" not in response.text
    assert "cost_cents" not in response.text
    assert response.headers["cache-control"] == "no-store"
    with printers.world.sessions() as session:
        assert (
            session.scalar(
                sa.select(sa.func.count())
                .select_from(models.audit_events)
                .where(models.audit_events.c.action == "print_attempt.payload_read")
            )
            == 1
        )
        originals = session.scalars(sa.select(models.print_jobs.c.payload)).all()
        assert all(raw["private_extra"] == "PRIVATE-DEVICE" for raw in originals)


def test_kitchen_payload_has_no_money_even_inside_modifiers(printers: PrintWorld) -> None:
    assert printers.claim("kitchen").status_code == 200
    response = printers.payload("kitchen")
    assert response.status_code == 200, response.text
    assert "cents" not in response.text and "payment_id" not in response.text
    jsonschema.validate(
        response.json()["payload"],
        json.loads(
            (
                Path(__file__).resolve().parents[3]
                / "packages/contracts/schemas/print-kitchen-payload-v2.schema.json"
            ).read_text(encoding="utf-8")
        ),
    )
    assert (
        response.json()["payload"]["lines"][0]["selected_modifiers"][0]["kitchen_text"]
        == "Sin salsa"
    )


@pytest.mark.parametrize("change", ["revoked", "finished"])
def test_payload_stops_after_revocation_or_ack(printers: PrintWorld, change: str) -> None:
    assert printers.claim("ticket").status_code == 200
    if change == "finished":
        response = printers.world.client.post(
            f"/api/v1/print-attempts/{printers.attempts['ticket']}/ack",
            headers=printers.headers(),
            json={"acknowledgement": "printed-001"},
        )
        assert response.status_code == 200, response.text
    else:
        with printers.world.sessions() as session:
            session.execute(
                models.device_credentials.update()
                .where(models.device_credentials.c.id == printers.device_id)
                .values(revoked_at=ops._now())
            )
            session.commit()
    assert printers.payload("ticket").status_code == 403


def test_direct_claim_requires_real_scoped_device(printers: PrintWorld) -> None:
    with printers.world.sessions() as session, pytest.raises(ops.AuthorizationError):
        ops.claim_print_attempt(session, printers.attempts["ticket"], ident("unknown-device"))
    with printers.world.sessions() as session:
        assert (
            session.scalar(
                sa.select(models.print_attempts.c.status).where(
                    models.print_attempts.c.id == printers.attempts["ticket"]
                )
            )
            == "QUEUED"
        )


def test_unauthorized_payload_never_selects_snapshot(printers: PrintWorld) -> None:
    assert printers.claim("ticket").status_code == 200
    statements: list[str] = []
    engine = printers.world.sessions.kw["bind"]

    def observe(_conn: Any, _cursor: Any, statement: str, *_args: Any) -> None:
        if statement.lstrip().upper().startswith("SELECT"):
            statements.append(statement)

    sa.event.listen(engine, "before_cursor_execute", observe)
    try:
        assert printers.payload("ticket", ident("printer-credential-b")).status_code == 403
    finally:
        sa.event.remove(engine, "before_cursor_execute", observe)
    assert not any("print_jobs.payload" in sql for sql in statements)


@pytest.mark.parametrize("failure", ["snapshot", "audit"])
def test_payload_failure_is_closed_and_private(
    printers: PrintWorld,
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
) -> None:
    assert printers.claim("ticket").status_code == 200
    if failure == "snapshot":
        with printers.world.sessions() as session:
            job = session.scalar(
                sa.select(models.print_attempts.c.print_job_id).where(
                    models.print_attempts.c.id == printers.attempts["ticket"]
                )
            )
            session.execute(
                models.print_jobs.update()
                .where(models.print_jobs.c.id == job)
                .values(payload={"folio": "PRIVATE-DEVICE", "lines": "PRIVATE-DEVICE"})
            )
            session.commit()
    else:
        original = ops._audit

        def fail(*args: Any, **kwargs: Any) -> Any:
            if len(args) > 1 and args[1] == "print_attempt.payload_read":
                raise sa.exc.SQLAlchemyError("PRIVATE-DEVICE-SQL")
            return original(*args, **kwargs)

        monkeypatch.setattr(ops, "_audit", fail)
    response = printers.payload("ticket")
    assert response.status_code == (409 if failure == "snapshot" else 503), response.text
    assert "PRIVATE-DEVICE" not in response.text
    with printers.world.sessions() as session:
        assert (
            session.scalar(
                sa.select(sa.func.count())
                .select_from(models.audit_events)
                .where(models.audit_events.c.action == "print_attempt.payload_read")
            )
            == 0
        )


def test_revocation_after_audit_commit_prevents_payload_delivery(
    printers: PrintWorld,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert printers.claim("ticket").status_code == 200
    original_audit, original_commit = ops._audit, Session.commit

    def mark_audit(*args: Any, **kwargs: Any) -> Any:
        result = original_audit(*args, **kwargs)
        if len(args) > 1 and args[1] == "print_attempt.payload_read":
            args[0].info["revoke_after_commit"] = True
        return result

    def commit(session: Session) -> None:
        original_commit(session)
        if session.info.pop("revoke_after_commit", False):
            with printers.world.sessions() as writer:
                writer.execute(
                    models.device_credentials.update()
                    .where(models.device_credentials.c.id == printers.device_id)
                    .values(revoked_at=ops._now())
                )
                original_commit(writer)

    monkeypatch.setattr(ops, "_audit", mark_audit)
    monkeypatch.setattr(Session, "commit", commit)
    response = printers.payload("ticket")
    assert response.status_code == 403 and "9500" not in response.text


@pytest.mark.parametrize(
    "kind,model_name", [("ticket", "TicketPayload"), ("kitchen", "KitchenPayload")]
)
def test_print_payload_schema_matches_runtime(kind: str, model_name: str) -> None:
    from restaurant_os import print_device_views

    model = getattr(print_device_views, model_name)
    stored = json.loads(
        (
            Path(__file__).resolve().parents[3]
            / f"packages/contracts/schemas/print-{kind}-payload-v2.schema.json"
        ).read_text(encoding="utf-8")
    )
    assert stored == {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        **model.model_json_schema(),
    }


def test_policy_change_after_commit_prevents_payload_delivery(
    printers: PrintWorld, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert printers.claim("ticket").status_code == 200
    commit = Session.commit
    changed = False

    def suspend(session: Session) -> None:
        nonlocal changed
        commit(session)
        if not changed:
            changed = True
            with printers.world.sessions() as writer:
                policy = dict(
                    writer.execute(
                        sa.select(models.blind_cash_policy_revisions).where(
                            models.blind_cash_policy_revisions.c.branch_id == BRANCH_ID
                        )
                    )
                    .mappings()
                    .one()
                )
                writer.execute(
                    models.blind_cash_policy_revisions.insert().values(
                        {**policy, "revision": 2, "event": "suspended", "created_at": ops._now()}
                    )
                )
                commit(writer)

    monkeypatch.setattr(Session, "commit", suspend)
    response = printers.payload("ticket")
    assert changed and response.status_code == 409 and "9500" not in response.text, response.text


@pytest.mark.parametrize("command", ["pull", "claim"])
def test_suspended_policy_blocks_legacy_print_transport(printers: PrintWorld, command: str) -> None:
    from test_corte_ciego_f109_suspension import suspend

    with printers.world.sessions() as session:
        suspend(session, BRANCH_ID)
    response = (
        printers.world.client.get("/api/v1/print-attempts/pull", headers=printers.headers())
        if command == "pull"
        else printers.claim("ticket")
    )
    assert (
        response.status_code == 409 and response.json()["detail"]["code"] == "cash_policy_suspended"
    ), response.text
    assert "payload" not in response.json() and "9500" not in response.text
