"""Replay signed order intents without replacing an ambiguous command."""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from datetime import UTC, datetime
from threading import Lock
from typing import Any

import httpx

from edge_gateway.config import _validate_central_url
from edge_gateway.order_outbox import OrderOutbox

LOGGER = logging.getLogger(__name__)


class OrderSyncWorker:
    def __init__(
        self, outbox: OrderOutbox, send: Callable[[dict[str, Any]], dict[str, Any]]
    ) -> None:
        self.outbox = outbox
        self.send = send
        self._lock = Lock()

    def reconcile_once(self, *, limit: int = 100, now: str | None = None) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        if not self._lock.acquire(blocking=False):
            return results
        try:
            timestamp = (
                datetime.fromisoformat(now).timestamp() if now else datetime.now(UTC).timestamp()
            )
            for row in self.outbox.pending(limit, now=timestamp):
                try:
                    response = self.send(row["envelope"])
                except (ConnectionError, TimeoutError, httpx.TransportError):
                    self.outbox.defer(row["command_id"], now=timestamp)
                    if row["attempts"] == 0:
                        LOGGER.warning(
                            "offline.orders.sync_retry", extra={"command_id": row["command_id"]}
                        )
                    continue
                if (
                    not isinstance(response, dict)
                    or response.get("command_id") != row["command_id"]
                ):
                    self.outbox.defer(row["command_id"], now=timestamp)
                    continue
                status = response.get("status")
                if status == "confirmed":
                    checkpoint = response.get("checkpoint")
                    if type(checkpoint) is not int or checkpoint < 1:
                        self.outbox.defer(row["command_id"], now=timestamp)
                        continue
                    self.outbox.resolve(
                        row["command_id"], status="CONFIRMED", checkpoint=checkpoint
                    )
                elif status == "conflict":
                    detail = response.get("code")
                    if (
                        not isinstance(detail, str)
                        or re.fullmatch(r"[a-zA-Z0-9_.-]{1,160}", detail) is None
                    ):
                        self.outbox.defer(row["command_id"], now=timestamp)
                        continue
                    self.outbox.resolve(row["command_id"], status="CONFLICT", detail=detail)
                else:
                    self.outbox.defer(row["command_id"], now=timestamp)
                    continue
                results.append(self.outbox.get(row["command_id"]))
                LOGGER.info(
                    "offline.orders.sync_resolved",
                    extra={
                        "command_id": row["command_id"],
                        "result": status,
                        "checkpoint": response.get("checkpoint"),
                        "code": response.get("code"),
                    },
                )
            return results
        finally:
            self._lock.release()


class OrderTransport:
    def __init__(self, central_url: str, credential: str) -> None:
        _validate_central_url(central_url)
        self.client = httpx.Client(
            base_url=central_url.rstrip("/"),
            timeout=5,
            verify=True,
            trust_env=False,
            follow_redirects=False,
            headers={"X-Device-Token": credential},
        )

    def send(self, envelope: dict[str, Any]) -> dict[str, Any]:
        response = self.client.post("/api/v1/offline-orders/reconcile", json=envelope)
        # Only an authenticated, structured command receipt changes local state.
        # Auth failures, proxy errors and unavailable endpoints retain the intent.
        if response.status_code not in {200, 409}:
            raise ConnectionError("offline_order_sync_unavailable")
        try:
            payload = response.json()
        except ValueError as exc:
            raise ConnectionError("offline_order_sync_invalid_response") from exc
        if not isinstance(payload, dict):
            raise ConnectionError("offline_order_sync_invalid_response")
        return payload

    def close(self) -> None:
        self.client.close()
