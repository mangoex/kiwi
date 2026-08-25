"""Fail-closed HTTPX transport for the central PCO-008 contract."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import httpx


class HTTPXGatewayTransport:
    def __init__(
        self,
        central_url: str,
        credential: str,
        *,
        timeout_seconds: float = 5.0,
        client_factory: Callable[..., httpx.Client] = httpx.Client,
    ) -> None:
        if not credential or timeout_seconds <= 0:
            raise ValueError("gateway transport configuration is invalid")
        self._url = f"{central_url.rstrip('/')}/api/v1/sync/commands"
        self._credential = credential
        self._client = client_factory(
            verify=True,
            trust_env=False,
            follow_redirects=False,
            timeout=httpx.Timeout(timeout_seconds),
        )

    def __call__(self, command: dict[str, Any]) -> dict[str, Any]:
        try:
            response = self._client.post(
                self._url,
                headers={"X-Device-Token": self._credential},
                json=command,
            )
        except httpx.TransportError as exc:
            raise ConnectionError("gateway central transport failed") from exc
        if response.status_code in {408, 425, 429}:
            return {"status_code": 503, "code": "transport_retryable"}
        if response.status_code >= 500:
            return {"status_code": response.status_code}
        if response.status_code >= 400:
            return {"status_code": response.status_code, "code": _error_code(response)}
        try:
            payload = response.json()
        except ValueError as exc:
            raise ConnectionError("gateway central response is malformed") from exc
        if not isinstance(payload, dict):
            raise ConnectionError("gateway central response is malformed")
        checkpoint = payload.get("checkpoint")
        if payload.get("status") == "CONFIRMED" and _positive_checkpoint(checkpoint):
            return {"status": "CONFIRMED", "checkpoint": checkpoint}
        if (
            payload.get("status") == "CONFLICT"
            and _positive_checkpoint(checkpoint)
            and isinstance(payload.get("code"), str)
            and payload["code"]
        ):
            return {"status": "CONFLICT", "checkpoint": checkpoint, "code": payload["code"]}
        raise ConnectionError("gateway central response is malformed")

    def close(self) -> None:
        self._client.close()


def _positive_checkpoint(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _error_code(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return "sync_conflict"
    detail = payload.get("detail") if isinstance(payload, dict) else None
    code = detail.get("code") if isinstance(detail, dict) else None
    if isinstance(code, str) and code:
        return code
    return "sync_conflict"
