from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol

from edge_gateway.outbox import GatewayOutbox


class GatewayTransport(Protocol):
    def __call__(self, command: dict[str, Any]) -> dict[str, Any]: ...


class CashSyncWorker:
    """Reconcile cash commands; injected transport keeps tests deterministic."""

    def __init__(self, outbox: GatewayOutbox, transport: GatewayTransport) -> None:
        self.outbox = outbox
        self.transport = transport

    def reconcile_once(self, now: str, *, limit: int = 50) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for command in self.outbox.claim_pending_commands(now=now, limit=limit):
            try:
                response = self.transport(_transport_envelope(command))
            except (TimeoutError, ConnectionError, OSError):
                results.append(
                    self.outbox.release_transport_failure(command["idempotency_key"], now=now)
                )
                continue
            status = response.get("status")
            if status == "CONFIRMED":
                checkpoint = response.get("checkpoint")
                if (
                    isinstance(checkpoint, bool)
                    or not isinstance(checkpoint, int)
                    or checkpoint <= 0
                ):
                    results.append(
                        self.outbox.release_transport_failure(
                            command["idempotency_key"], now=now
                        )
                    )
                else:
                    results.append(
                        self.outbox.mark_confirmed(command["idempotency_key"], checkpoint)
                    )
                continue
            if status == "CONFLICT":
                results.append(
                    self.outbox.mark_conflict(
                        command["idempotency_key"], str(response.get("code") or "sync_conflict")
                    )
                )
                continue
            status_code = response.get("status_code", 500)
            if (
                isinstance(status_code, int)
                and not isinstance(status_code, bool)
                and 400 <= status_code < 500
            ):
                results.append(
                    self.outbox.mark_conflict(
                        command["idempotency_key"], str(response.get("code") or "sync_conflict")
                    )
                )
            else:
                results.append(
                    self.outbox.release_transport_failure(command["idempotency_key"], now=now)
                )
        return results


def _transport_envelope(command: dict[str, Any]) -> dict[str, Any]:
    """Strip local state before crossing the strict central contract boundary."""
    return {
        "schema_version": "1.0",
        **{
            field: command[field]
            for field in (
                "command_id",
                "idempotency_key",
                "organization_id",
                "branch_id",
                "source_device_id",
                "actor_user_id",
                "command_type",
                "occurred_at",
                "accepted_at",
                "offline_grant",
                "payload",
            )
        },
    }


class LocalCashAdapter:
    def __init__(
        self,
        outbox: GatewayOutbox,
        identity: dict[str, str],
        grant: Callable[[], str],
    ) -> None:
        self.outbox = outbox
        self.identity = identity
        self.grant = grant

    def create(
        self,
        payload: dict[str, Any],
        idempotency_key: str,
        command_id: str,
        occurred_at: str,
    ) -> dict[str, Any]:
        return self.outbox.enqueue_command(
            {
                "schema_version": "1.0",
                "command_id": command_id,
                "idempotency_key": idempotency_key,
                "organization_id": self.identity["organization_id"],
                "branch_id": self.identity["branch_id"],
                "source_device_id": self.identity["source_device_id"],
                "actor_user_id": self.identity["actor_user_id"],
                "command_type": "cash.movement.create.v1",
                "occurred_at": occurred_at,
                "accepted_at": occurred_at,
                "offline_grant": self.grant(),
                "payload": payload,
            }
        )
