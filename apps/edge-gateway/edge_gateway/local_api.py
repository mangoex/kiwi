from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Protocol
from uuid import uuid4

from fastapi import FastAPI, Header, HTTPException, Request, Response, status

from edge_gateway.outbox import GatewayOutbox, InvalidCommandEnvelope

UTC = timezone.utc
CAPABILITY = "cash.movement.create.v1"

class GrantVerifier(Protocol):
    def __call__(self, token: str) -> dict[str, Any] | None: ...


def create_local_cash_app(
    outbox: GatewayOutbox,
    device_config: dict[str, str],
    verify_grant: GrantVerifier,
) -> FastAPI:
    _validate_device_config(device_config)
    app = FastAPI()

    def identity(authorization: str | None) -> tuple[dict[str, Any], str]:
        if not authorization or not authorization.startswith("Offline "):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "offline authorization required")
        token = authorization.removeprefix("Offline ").strip()
        grant = verify_grant(token)
        if grant is None or not _grant_matches(grant, device_config):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "offline authorization rejected")
        return grant, token

    @app.post("/api/v1/local/cash/movements", status_code=status.HTTP_201_CREATED)
    async def create_movement(
        request: Request,
        response: Response,
        authorization: str | None = Header(default=None),
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ) -> dict[str, Any]:
        grant, token = identity(authorization)
        if not idempotency_key:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Idempotency-Key required")
        try:
            payload = await request.json()
        except ValueError as exc:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY, "payload must be JSON"
            ) from exc
        if not isinstance(payload, dict):
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "payload must be object")
        now = datetime.now(UTC).isoformat()
        envelope = {
            "schema_version": "1.0",
            "command_id": str(uuid4()),
            "idempotency_key": idempotency_key,
            "organization_id": device_config["organization_id"],
            "branch_id": device_config["branch_id"],
            "source_device_id": device_config["source_device_id"],
            "actor_user_id": grant["actor_user_id"],
            "command_type": CAPABILITY,
            "occurred_at": now,
            "accepted_at": now,
            "offline_grant": token,
            "payload": payload,
        }
        if not _within_window(grant, now):
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "grant window rejected")
        try:
            command = outbox.enqueue_command(envelope)
        except InvalidCommandEnvelope as exc:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
        body = _redact(command)
        if body["command_id"] != envelope["command_id"]:
            response.status_code = status.HTTP_200_OK
        return body

    @app.get("/api/v1/local/cash/movements")
    def list_movements(authorization: str | None = Header(default=None)) -> dict[str, Any]:
        identity(authorization)
        return {"items": outbox.list_local_status(device_config)}

    return app


def _validate_device_config(device_config: dict[str, str]) -> None:
    required = {"organization_id", "branch_id", "source_device_id"}
    if set(device_config) != required or any(not value for value in device_config.values()):
        raise ValueError("invalid gateway device configuration")


def _grant_matches(
    grant: dict[str, Any] | None, device_config: dict[str, str]
) -> bool:
    return bool(
        grant
        and grant.get("kind") == "offline_grant.v2"
        and grant.get("version") == 2
        and grant.get("capabilities") == [CAPABILITY]
        and isinstance(grant.get("actor_user_id"), str)
        and grant["actor_user_id"]
        and all(grant.get(field) == device_config[field] for field in device_config)
    )


def _within_window(grant: dict[str, Any], accepted_at: str) -> bool:
    try:
        accepted = int(datetime.fromisoformat(accepted_at).timestamp())
        issued = int(grant["iat"])
        expires = int(grant["exp"])
    except (KeyError, TypeError, ValueError):
        return False
    return issued <= accepted <= expires


def _redact(command: dict[str, Any]) -> dict[str, Any]:
    fields = (
        "id",
        "command_id",
        "idempotency_key",
        "status",
        "occurred_at",
        "accepted_at",
        "created_at",
        "attempts",
        "confirmed_checkpoint",
        "confirmed_at",
        "conflict_code",
    )
    return {field: command[field] for field in fields}
