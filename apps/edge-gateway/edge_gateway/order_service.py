"""Authorized local order execution over a retained, signed catalog bundle."""

from __future__ import annotations

import base64
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import uuid4

import sqlalchemy as sa
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.encoders import jsonable_encoder
from restaurant_os import models
from restaurant_os.offline_order_contracts import canonical_envelope, validate_envelope
from restaurant_os.offline_orders import require_grant_scope, verify_bundle, verify_order_grant
from restaurant_os.operations import BusinessError, _audit
from restaurant_os.order_execution import (
    ExecutionContext,
    defer_authorization_audit,
    next_id,
    order_execution_context,
)
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from edge_gateway.order_outbox import OrderOutbox, commands


class LocalOrderService:
    def __init__(
        self,
        outbox: OrderOutbox,
        catalog_engine: Engine,
        bundle: dict[str, Any],
        keyring: dict[str, Any],
        signing_key: Ed25519PrivateKey,
    ) -> None:
        self.outbox = outbox
        self.catalog_engine = catalog_engine
        self.bundle = verify_bundle(bundle, keyring)
        self.manifest = self.bundle["manifest"]
        self.keyring = keyring
        self.signing_key = signing_key

    def authorize(self, token: str, now: datetime) -> dict[str, Any]:
        self.outbox.ensure_active_bundle(
            str(self.bundle["hash"]), int(self.manifest["lease_epoch"])
        )
        grant = verify_order_grant(token, self.keyring, now, check_expiry=True)
        for key in ("organization_id", "branch_id", "device_id", "bundle_id", "lease_epoch"):
            if grant.get(key) != self.manifest.get(key):
                raise BusinessError(
                    "offline_order_grant_scope_invalid", "Authorization scope differs"
                )
        if grant["bundle_hash"] != self.bundle["hash"]:
            raise BusinessError("offline_order_bundle_mismatch", "Authorization catalog differs")
        expires = datetime.fromtimestamp(self.manifest["expires_at"], UTC)
        issued = datetime.fromtimestamp(self.manifest["issued_at"], UTC)
        if not issued <= now < expires:
            raise BusinessError("offline_order_bundle_expired", "Catalog authorization expired")
        return grant

    def execute(
        self,
        token: str,
        command_type: str,
        payload: dict[str, Any],
        idempotency_key: str,
        *,
        aggregate_id: str | None = None,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        now = now or datetime.now(UTC)
        grant = self.authorize(token, now)
        intent = {
            "command_type": command_type,
            "payload": payload,
            "aggregate_id": aggregate_id,
            "branch_id": grant["branch_id"],
        }

        def apply(
            session: Session, local_sequence: int, previous_hash: str | None
        ) -> tuple[dict[str, Any], dict[str, Any]]:
            from restaurant_os.offline_orders import execute_order_intent

            # UUIDv7 timestamp is an identifier only; stream sequence determines causality.
            milliseconds = int(now.timestamp() * 1000)
            random_bits = uuid4().int
            from uuid import UUID

            command_id = str(
                UUID(
                    int=(milliseconds << 80)
                    | (7 << 76)
                    | (random_bits & ((1 << 76) - 1) & ~(3 << 62))
                    | (2 << 62)
                )
            )
            with order_execution_context(ExecutionContext(command_id, now)):
                first_id = next_id()
            order_id = aggregate_id or first_id
            sequence = (
                session.scalar(
                    sa.select(sa.func.max(commands.c.sequence)).where(
                        commands.c.aggregate_id == order_id
                    )
                )
                or 0
            ) + 1
            envelope = {
                "schema_version": "ord-off/v1",
                "command_id": command_id,
                "command_type": command_type,
                "idempotency_key": idempotency_key,
                "aggregate_id": order_id,
                "sequence": sequence,
                "previous_hash": previous_hash,
                "organization_id": grant["organization_id"],
                "branch_id": grant["branch_id"],
                "device_id": grant["device_id"],
                "actor_id": grant["actor_id"],
                "accepted_at": now.isoformat(),
                "grant": token,
                "bundle_id": self.manifest["bundle_id"],
                "bundle_hash": self.bundle["hash"],
                "lease_epoch": grant["lease_epoch"],
                "local_sequence": local_sequence,
                "payload": payload,
                "device_signature": "",
            }
            require_grant_scope(grant, envelope)
            envelope["device_signature"] = (
                base64.urlsafe_b64encode(self.signing_key.sign(canonical_envelope(envelope)))
                .decode()
                .rstrip("=")
            )
            validate_envelope(envelope)
            with Session(self.catalog_engine) as catalog:
                catalog.execute(sa.text("PRAGMA query_only=ON"))
                result = execute_order_intent(session, envelope, catalog, commit=False)
            if command_type == "create" and str(result.get("id")) != order_id:
                raise BusinessError("offline_order_identity_mismatch", "Order identity differs")
            return envelope, jsonable_encoder(result, custom_encoder={Decimal: str})

        with defer_authorization_audit() as denials:
            try:
                row = self.outbox.accept(
                    grant["actor_id"],
                    idempotency_key,
                    intent,
                    apply,
                    aggregate_id=aggregate_id,
                    bundle_hash=str(self.bundle["hash"]),
                    lease_epoch=int(self.manifest["lease_epoch"]),
                )
            except BusinessError:
                # Domain/outbox has rolled back. Persist only the denial audit in
                # its own transaction, without reviving any rejected order effect.
                if denials:
                    with Session(self.outbox.engine) as rejected:
                        with rejected.begin():
                            for denial in denials:
                                _audit(
                                    rejected,
                                    action="authorization.denied",
                                    entity_type="permission",
                                    entity_id=denial["permission_code"],
                                    payload={
                                        "permission": denial["permission_code"],
                                        "reason": denial["reason"],
                                    },
                                    branch_id=denial["branch_id"],
                                    actor_user_id=denial["actor_user_id"],
                                )
                raise
        return {
            **row["result"],
            "_offline": {
                "command_id": row["command_id"],
                "status": row["status"],
                "checkpoint": row["checkpoint"],
                "code": row["detail"],
            },
        }

    def order_for_task(self, task_id: str, grant: dict[str, Any]) -> str:
        with Session(self.outbox.engine) as session:
            order_id = session.scalar(
                sa.select(models.production_tasks.c.order_id).where(
                    models.production_tasks.c.id == task_id,
                    models.production_tasks.c.branch_id == grant["branch_id"],
                )
            )
            if order_id is None:
                raise BusinessError("task_not_found", "Task was not found")
            return str(order_id)
