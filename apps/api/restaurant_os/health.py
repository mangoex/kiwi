from collections.abc import Callable
from dataclasses import dataclass

from redis import Redis
from sqlalchemy import create_engine, text

from restaurant_os.config import Settings


@dataclass(frozen=True)
class DependencyStatus:
    name: str
    status: str
    detail: str


def _check_postgres(database_url: str) -> DependencyStatus:
    try:
        engine = create_engine(
            database_url,
            pool_pre_ping=True,
            connect_args={"connect_timeout": 2},
        )
        with engine.connect() as connection:
            connection.execute(text("select 1"))
        engine.dispose()
    except Exception as exc:
        return DependencyStatus("postgres", "down", exc.__class__.__name__)

    return DependencyStatus("postgres", "ok", "reachable")


def _check_redis(redis_url: str) -> DependencyStatus:
    try:
        client = Redis.from_url(redis_url, socket_connect_timeout=2, socket_timeout=2)
        client.ping()
        client.close()
    except Exception as exc:
        return DependencyStatus("redis", "down", exc.__class__.__name__)

    return DependencyStatus("redis", "ok", "reachable")


def check_dependencies(
    settings: Settings,
    postgres_checker: Callable[[str], DependencyStatus] = _check_postgres,
    redis_checker: Callable[[str], DependencyStatus] = _check_redis,
) -> list[DependencyStatus]:
    checks: list[DependencyStatus] = []

    if settings.database_url:
        checks.append(postgres_checker(settings.database_url))
    else:
        checks.append(DependencyStatus("postgres", "not_configured", "DATABASE_URL is missing"))

    if settings.redis_url:
        checks.append(redis_checker(settings.redis_url))
    else:
        checks.append(DependencyStatus("redis", "not_configured", "REDIS_URL is missing"))

    return checks


def readiness_payload(settings: Settings) -> dict[str, object]:
    dependencies = check_dependencies(settings)
    is_ready = all(dependency.status == "ok" for dependency in dependencies)

    return {
        "status": "ok" if is_ready else "degraded",
        "service": settings.service_name,
        "environment": settings.environment,
        "dependencies": [
            {
                "name": dependency.name,
                "status": dependency.status,
                "detail": dependency.detail,
            }
            for dependency in dependencies
        ],
    }
