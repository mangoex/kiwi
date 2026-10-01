"""Bound SR-WORKSPACE request bodies before FastAPI parses their JSON."""

from __future__ import annotations

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

MAX_WORKSPACE_BODY_BYTES = 262_144


class WorkspaceBodyLimitMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        path = str(scope.get("path", ""))
        covered = (
            path.startswith("/api/v1/purchases")
            or path.startswith("/api/v1/purchase-presentations")
            or (path.startswith("/api/v1/recipes/") and path.endswith("/preview"))
            or (
                path.startswith("/api/v1/products/")
                and (path.endswith("/recipe") or "/modifier-configuration" in path)
            )
            or (path.startswith("/api/v1/inventory/items/") and path.endswith("/cost-preview"))
        )
        if scope["type"] != "http" or scope.get("method") not in {"POST", "PUT"} or not covered:
            await self.app(scope, receive, send)
            return

        chunks = []
        size = 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            body = message.get("body", b"")
            size += len(body)
            if size > MAX_WORKSPACE_BODY_BYTES:
                response = JSONResponse(
                    {
                        "detail": {
                            "code": "workspace_payload_too_large",
                            "message": "Request exceeds 262144 bytes",
                        }
                    },
                    status_code=413,
                    headers={"Cache-Control": "no-store"},
                )
                await response(scope, receive, send)
                return
            chunks.append(body)
            if not message.get("more_body", False):
                break
        buffered = b"".join(chunks)
        replayed = False

        async def buffered_receive() -> Message:
            nonlocal replayed
            if not replayed:
                replayed = True
                return {"type": "http.request", "body": buffered, "more_body": False}
            return await receive()

        await self.app(scope, buffered_receive, send)
