from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse

from restaurant_os.api import router as platform_router
from restaurant_os.config import get_settings
from restaurant_os.health import readiness_payload


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="RestaurantOS API", version=settings.app_version)
    app.include_router(platform_router)

    static_dir = os.environ.get("STATIC_DIR", "/app/static")
    # For local dev fallback
    if not os.path.exists(static_dir):
        static_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../static"))

    @app.get("/", response_class=HTMLResponse, tags=["platform"])
    def platform_home() -> str:
        return (
            "<h1>RestaurantOS</h1>"
            "<p><a href='/pos/'>POS</a> | <a href='/admin/'>Admin</a> | <a href='/kds/'>KDS</a></p>"
        )

    def serve_spa(app_name: str, full_path: str):
        base_path = os.path.join(static_dir, app_name)
        file_path = os.path.join(base_path, full_path) if full_path else base_path
        if os.path.isfile(file_path):
            return FileResponse(file_path)
        index_path = os.path.join(base_path, "index.html")
        if os.path.isfile(index_path):
            return FileResponse(index_path)
        return HTMLResponse(
            f"<h3>{app_name} UI not built.</h3><p>Ensure static files are in {base_path}</p>"
        )

    @app.get("/admin{full_path:path}", tags=["platform"])
    def platform_admin(full_path: str):
        return serve_spa("admin-web", full_path.lstrip("/"))

    @app.get("/pos{full_path:path}", tags=["platform"])
    def platform_pos(full_path: str):
        return serve_spa("pos-web", full_path.lstrip("/"))

    @app.get("/kds{full_path:path}", tags=["platform"])
    def platform_kds(full_path: str):
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
