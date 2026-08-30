import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse, Response

from restaurant_os.api import router as platform_router
from restaurant_os.config import get_settings
from restaurant_os.health import readiness_payload
from restaurant_os.public_order_rate_limit import RedisPublicOrderRateLimiter


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="RestaurantOS API", version=settings.app_version)
    # Default OFF. If enabled without Redis, public writes remain fail-closed in the route.
    app.state.public_order_intents_enabled = settings.public_order_intents_enabled
    if (
        settings.public_order_intents_enabled
        and settings.redis_url
        and settings.public_order_rate_limit_hmac_secret
    ):
        app.state.public_order_rate_limiter = RedisPublicOrderRateLimiter(
            settings.redis_url,
            settings.public_order_global_rate_limit_per_minute,
            settings.public_order_client_rate_limit_per_minute,
            settings.public_order_rate_limit_hmac_secret,
        )
    app.include_router(platform_router)

    static_dir = os.environ.get("STATIC_DIR", "/app/static")
    # For local dev fallback
    if not os.path.exists(static_dir):
        static_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../static"))

    @app.get("/", response_class=HTMLResponse, tags=["platform"])
    def platform_home() -> str:
        return (
            "<h1>RestaurantOS</h1>"
            "<p>"
            "<a href='/menu/'>📱 Menú Clientes</a> | "
            "<a href='/pos/'>POS</a> | "
            "<a href='/admin/'>Admin</a> | "
            "<a href='/kds/'>KDS</a>"
            "</p>"
        )

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
        index_path = base_path / "index.html"
        if index_path.is_file():
            return FileResponse(index_path)
        return HTMLResponse(
            f"<h3>{app_name} UI not built.</h3><p>Ensure static files are in {base_path}</p>"
        )

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
