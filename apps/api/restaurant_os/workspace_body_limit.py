"""Bound governed workspace and Agent Tools bodies before FastAPI parses them."""

from __future__ import annotations

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

MAX_WORKSPACE_BODY_BYTES = 262_144
MAX_AGENT_BODY_BYTES = 65_536


class WorkspaceBodyLimitMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        path = str(scope.get("path", ""))
        agent_covered = path.startswith(
            ("/api/v1/agent-auth/", "/api/v1/agent-tools/", "/api/v1/integrations/grokbot/")
        )
        workspace_covered = (
            path.startswith("/api/v1/purchases")
            or path.startswith("/api/v1/purchase-presentations")
            or (path.startswith("/api/v1/recipes/") and path.endswith("/preview"))
            or (
                path.startswith("/api/v1/products/")
                and (path.endswith("/recipe") or "/modifier-configuration" in path)
            )
            or (path.startswith("/api/v1/inventory/items/") and path.endswith("/cost-preview"))
        )
        covered = agent_covered or workspace_covered
        if scope["type"] != "http" or scope.get("method") not in {"POST", "PUT"} or not covered:
            await self.app(scope, receive, send)
            return

        max_bytes = MAX_AGENT_BODY_BYTES if agent_covered else MAX_WORKSPACE_BODY_BYTES
        chunks = []
        size = 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            body = message.get("body", b"")
            size += len(body)
            if size > max_bytes:
                code = "agent_schema_invalid" if agent_covered else "workspace_payload_too_large"
                detail: dict[str, object] = {
                    "code": code,
                    "message": f"Request exceeds {max_bytes} bytes",
                }
                if agent_covered:
                    detail["correlation_id"] = None
                response = JSONResponse(
                    {"detail": detail},
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
