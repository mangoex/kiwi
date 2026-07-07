from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from restaurant_os.config import get_settings
from restaurant_os.health import readiness_payload
from restaurant_os.platform_shell import render_platform_shell


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="RestaurantOS API", version=settings.app_version)

    @app.get("/", response_class=HTMLResponse, tags=["platform"])
    def platform_home() -> str:
        return render_platform_shell("/")

    @app.get("/admin", response_class=HTMLResponse, tags=["platform"])
    def platform_admin() -> str:
        return render_platform_shell("/admin")

    @app.get("/pos", response_class=HTMLResponse, tags=["platform"])
    def platform_pos() -> str:
        return render_platform_shell("/pos")

    @app.get("/kds", response_class=HTMLResponse, tags=["platform"])
    def platform_kds() -> str:
        return render_platform_shell("/kds")

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
