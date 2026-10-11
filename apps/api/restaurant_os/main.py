from __future__ import annotations

import logging
import os
import re
import time
from collections.abc import Awaitable, Callable
from pathlib import Path
from uuid import UUID

from fastapi import FastAPI, Request
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response

from restaurant_os.agent_rate_limit import RedisAgentRateLimiter
from restaurant_os.agent_tools import router as agent_tools_router
from restaurant_os.api import reconciliation_v2_router
from restaurant_os.api import router as platform_router
from restaurant_os.auth import verify_session_token
from restaurant_os.config import get_settings
from restaurant_os.health import readiness_payload
from restaurant_os.public_order_rate_limit import (
    InMemoryPublicOrderRateLimiter,
    RedisPublicOrderRateLimiter,
)
from restaurant_os.workspace_body_limit import WorkspaceBodyLimitMiddleware

logger = logging.getLogger(__name__)


_PHONE_USER_AGENT = re.compile(
    r"iPhone|iPod|Windows Phone|BlackBerry|Opera Mini|Android.+Mobile",
    re.IGNORECASE,
)


def _agent_rate_identity(authorization: str, secret_key: str) -> str:
    """Derive a stable non-secret identity signal before the limiter HMACs it."""
    if authorization.startswith("Bearer "):
        token = authorization.removeprefix("Bearer ").strip()
        payload = verify_session_token(token, secret_key)
        if payload and payload.get("typ") == "agent" and payload.get("sub"):
            return f"agent:{str(payload['sub'])[:64]}"
    return "unauthenticated"


def _agent_log_context(request: Request, identity_signal: str) -> dict[str, str | None]:
    branch_id = request.query_params.get("branch_id")
    try:
        branch_id = str(UUID(branch_id)) if branch_id else None
    except (ValueError, TypeError, AttributeError):
        branch_id = None
    route = request.scope.get("route")
    route_path = getattr(route, "path", None)
    fallback_path = request.url.path
    if fallback_path.startswith("/api/v1/agent-tools/operations/"):
        fallback_path = "/api/v1/agent-tools/operations/{operation_id}"
    identity_id = (
        identity_signal.removeprefix("agent:") if identity_signal.startswith("agent:") else None
    )
    return {
        "identity_id": identity_id,
        "operation": f"{request.method} {route_path or fallback_path}",
        "branch_id": branch_id,
    }


def _request_prefers_mobile_menu(request: Request) -> bool:
    mobile_hint = request.headers.get("sec-ch-ua-mobile")
    if mobile_hint == "?1":
        return True
    if mobile_hint == "?0":
        return False
    return bool(_PHONE_USER_AGENT.search(request.headers.get("user-agent", "")))


def _with_device_variant_headers(response: Response) -> Response:
    response.headers["Cache-Control"] = "no-store"
    response.headers["Vary"] = "Sec-CH-UA-Mobile, User-Agent"
    response.headers["Accept-CH"] = "Sec-CH-UA-Mobile"
    return response


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="RestaurantOS API", version=settings.app_version)
    app.add_middleware(WorkspaceBodyLimitMiddleware)
    app.state.public_order_intents_enabled = settings.public_order_intents_enabled
    if settings.public_order_intents_enabled:
        if settings.redis_url and settings.public_order_rate_limit_hmac_secret:
            app.state.public_order_rate_limiter = RedisPublicOrderRateLimiter(
                settings.redis_url,
                settings.public_order_global_rate_limit_per_minute,
                settings.public_order_client_rate_limit_per_minute,
                settings.public_order_rate_limit_hmac_secret,
            )
        else:
            app.state.public_order_rate_limiter = InMemoryPublicOrderRateLimiter(
                settings.public_order_global_rate_limit_per_minute,
                settings.public_order_client_rate_limit_per_minute,
                settings.public_order_rate_limit_hmac_secret or settings.secret_key,
            )
    app.include_router(platform_router)
    app.include_router(reconciliation_v2_router)
    app.state.grokbot_agent_tools_enabled = settings.grokbot_agent_tools_enabled
    if settings.grokbot_agent_tools_enabled:
        if settings.redis_url and settings.grokbot_agent_rate_limit_hmac_secret:
            app.state.grokbot_agent_rate_limiter = RedisAgentRateLimiter(
                settings.redis_url,
                settings.grokbot_agent_global_rate_limit_per_minute,
                settings.grokbot_agent_identity_rate_limit_per_minute,
                settings.grokbot_agent_rate_limit_hmac_secret,
            )
        else:
            app.state.grokbot_agent_rate_limiter = InMemoryPublicOrderRateLimiter(
                settings.grokbot_agent_global_rate_limit_per_minute,
                settings.grokbot_agent_identity_rate_limit_per_minute,
                settings.grokbot_agent_rate_limit_hmac_secret or settings.secret_key,
            )

        @app.middleware("http")
        async def governed_agent_rate_limit(
            request: Request, call_next: Callable[[Request], Awaitable[Response]]
        ) -> Response:
            if not request.url.path.startswith(("/api/v1/agent-auth/", "/api/v1/agent-tools/")):
                return await call_next(request)
            authorization = request.headers.get("authorization", "")[:4096]
            client_host = request.client.host if request.client else "unknown"
            identity_signal = _agent_rate_identity(authorization, settings.secret_key)
            client_signal = (
                identity_signal
                if identity_signal != "unauthenticated"
                else f"unauthenticated:{client_host}"
            )
            namespace = (
                "grokbot-agent-auth"
                if request.url.path.startswith("/api/v1/agent-auth/")
                else "grokbot-agent-tools"
            )
            limiter = getattr(request.app.state, "grokbot_agent_rate_limiter", None)
            started = time.monotonic()
            try:
                allowed = bool(limiter and limiter.allow(namespace, client_signal))
            except Exception as exc:
                logger.error(
                    "agent.request.denied",
                    extra={
                        **_agent_log_context(request, identity_signal),
                        "result": "denied",
                        "reason_code": "dependency_unavailable",
                        "duration_ms": int((time.monotonic() - started) * 1000),
                        "error_type": exc.__class__.__name__,
                    },
                )
                return JSONResponse(
                    status_code=503,
                    content={
                        "detail": {
                            "code": "dependency_unavailable",
                            "message": "Agent rate limiter is unavailable",
                            "correlation_id": None,
                        }
                    },
                )
            if not allowed:
                logger.warning(
                    "agent.request.denied",
                    extra={
                        **_agent_log_context(request, identity_signal),
                        "result": "denied",
                        "reason_code": "rate_limited",
                        "duration_ms": int((time.monotonic() - started) * 1000),
                    },
                )
                return JSONResponse(
                    status_code=429,
                    headers={"Retry-After": "60"},
                    content={
                        "detail": {
                            "code": "rate_limited",
                            "message": "Agent Tools rate limit exceeded",
                            "correlation_id": None,
                        }
                    },
                )
            response = await call_next(request)
            accepted = response.status_code < 400
            event = "agent.request.accepted" if accepted else "agent.request.denied"
            log = logger.info if accepted else logger.warning
            log(
                event,
                extra={
                    **_agent_log_context(request, identity_signal),
                    "result": "accepted" if accepted else "denied",
                    "reason_code": (
                        None
                        if accepted
                        else response.headers.get(
                            "X-Kiwi-Error-Code", f"http_{response.status_code}"
                        )
                    ),
                    "duration_ms": int((time.monotonic() - started) * 1000),
                },
            )
            return response

        @app.exception_handler(RequestValidationError)
        async def governed_agent_validation_error(
            request: Request, exc: RequestValidationError
        ) -> Response:
            if request.url.path.startswith(
                ("/api/v1/agent-auth", "/api/v1/agent-tools", "/api/v1/integrations/grokbot")
            ):
                return JSONResponse(
                    status_code=400,
                    content={
                        "detail": {
                            "code": "agent_schema_invalid",
                            "message": "Request does not match the Agent Tools contract",
                            "correlation_id": None,
                        }
                    },
                )
            return await request_validation_exception_handler(request, exc)

        app.include_router(agent_tools_router)

    static_dir = os.environ.get("STATIC_DIR", "/app/static")
    # For local dev fallback
    if not os.path.exists(static_dir):
        static_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../static"))

    def serve_spa(app_name: str, full_path: str) -> Response:
        base_path = Path(static_dir, app_name).resolve()
        cleaned = full_path.lstrip("/")
        if cleaned:
            file_path = (base_path / cleaned).resolve()
            try:
                file_path.relative_to(base_path)
            except ValueError:
                return Response(status_code=404)
            if file_path.is_file():
                return FileResponse(file_path)
            if (file_path / "index.html").is_file():
                return FileResponse(file_path / "index.html")
        index_path = base_path / "index.html"
        if index_path.is_file():
            return FileResponse(index_path)
        return HTMLResponse(
            f"<h3>{app_name} UI not built.</h3><p>Ensure static files are in {base_path}</p>"
        )

    def serve_static_asset(app_name: str, full_path: str) -> Response:
        base_path = Path(static_dir, app_name).resolve()
        cleaned = full_path.lstrip("/")
        if not cleaned:
            return Response(status_code=404)
        file_path = (base_path / cleaned).resolve()
        try:
            file_path.relative_to(base_path)
        except ValueError:
            return Response(status_code=404)
        if file_path.is_file():
            return FileResponse(file_path)
        return Response(status_code=404)

    uploads_dir = os.environ.get("UPLOADS_DIR", "/app/uploads")
    if not os.path.exists(uploads_dir):
        uploads_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../uploads"))
    os.makedirs(os.path.join(uploads_dir, "products"), exist_ok=True)

    def serve_upload(full_path: str) -> Response:
        base_path = Path(uploads_dir).resolve()
        cleaned = full_path.lstrip("/")
        if not cleaned:
            return Response(status_code=404)
        file_path = (base_path / cleaned).resolve()
        try:
            file_path.relative_to(base_path)
        except ValueError:
            return Response(status_code=404)
        if file_path.is_file():
            return FileResponse(file_path)
        return Response(status_code=404)

    @app.get("/uploads/{full_path:path}", tags=["platform"])
    def platform_uploads(full_path: str) -> Response:
        return serve_upload(full_path)

    @app.get("/", tags=["platform"])
    def platform_home(request: Request) -> Response:
        if _request_prefers_mobile_menu(request):
            return _with_device_variant_headers(RedirectResponse(url="/menu/", status_code=307))
        return _with_device_variant_headers(serve_spa("landing-web", ""))

    @app.get("/landing-assets/{full_path:path}", tags=["platform"])
    def platform_landing_asset(full_path: str) -> Response:
        return serve_static_asset("landing-web", full_path)

    @app.get("/menu{full_path:path}", tags=["platform"])
    def platform_menu(full_path: str) -> Response:
        return serve_spa("mobile-web", full_path.lstrip("/"))

    @app.get("/order{full_path:path}", tags=["platform"])
    def platform_order(full_path: str) -> Response:
        return serve_spa("mobile-web", full_path.lstrip("/"))

    @app.get("/mobile{full_path:path}", tags=["platform"])
    def platform_mobile(full_path: str) -> Response:
        return serve_spa("mobile-web", full_path.lstrip("/"))

    @app.get("/images/{full_path:path}", tags=["platform"])
    def platform_images(full_path: str) -> Response:
        return serve_spa("mobile-web", f"images/{full_path.lstrip('/')}")

    @app.get("/admin{full_path:path}", tags=["platform"])
    def platform_admin(full_path: str) -> Response:
        return serve_spa("admin-web", full_path.lstrip("/"))

    @app.get("/pos{full_path:path}", tags=["platform"])
    def platform_pos(full_path: str) -> Response:
        return serve_spa("pos-web", full_path.lstrip("/"))

    @app.get("/kds{full_path:path}", tags=["platform"])
    def platform_kds(full_path: str) -> Response:
        return serve_spa("kds-web", full_path.lstrip("/"))

    @app.get("/manual{full_path:path}", tags=["platform"])
    def platform_manual(full_path: str) -> Response:
        return serve_spa("landing-web", f"manual/{full_path.lstrip('/')}")

    @app.get("/health/live", tags=["health"])
    def live() -> dict[str, str]:
        return {"status": "ok", "service": settings.service_name}

    @app.get("/health/ready", tags=["health"])
    def ready() -> dict[str, object]:
        return readiness_payload(settings)

    @app.get("/health/version", tags=["health"])
    def version() -> dict[str, str]:
        return {
            "service": settings.service_name,
            "version": settings.app_version,
            "commit": settings.git_commit,
        }

    return app


app = create_app()
