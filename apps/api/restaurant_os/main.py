import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse, Response

from restaurant_os.api import router as platform_router
from restaurant_os.config import get_settings
from restaurant_os.health import readiness_payload

logger = logging.getLogger(__name__)


def _run_auto_migrations() -> None:
    settings = get_settings()
    if not settings.database_url:
        return
    try:
        from alembic import command
        from alembic.config import Config

        current_dir = os.path.dirname(os.path.abspath(__file__))
        ini_candidates = [
            os.path.join(current_dir, "..", "alembic.ini"),
            os.path.join(current_dir, "alembic.ini"),
            os.path.abspath("alembic.ini"),
            os.path.abspath("apps/api/alembic.ini"),
        ]
        ini_path = next((p for p in ini_candidates if os.path.exists(p)), None)
        if ini_path:
            alembic_cfg = Config(ini_path)
            script_location = os.path.join(os.path.dirname(ini_path), "alembic")
            if os.path.exists(script_location):
                alembic_cfg.set_main_option("script_location", script_location)
            logger.info("Executing database auto-migration (alembic upgrade head)...")
            command.upgrade(alembic_cfg, "head")
            logger.info("Database auto-migration completed successfully.")
    except Exception as exc:
        logger.warning("Auto-migration skipped or error: %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    _run_auto_migrations()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="RestaurantOS API", version=settings.app_version, lifespan=lifespan)
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
        base_path = os.path.join(static_dir, app_name)
        cleaned = full_path.lstrip("/")
        if cleaned:
            file_path = os.path.join(base_path, cleaned)
            if os.path.isfile(file_path):
                return FileResponse(file_path)
        index_path = os.path.join(base_path, "index.html")
        if os.path.isfile(index_path):
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
