"""ConfigParser-safe boundary for Alembic's SQLAlchemy URL option."""

from alembic.config import Config


def set_alembic_database_url(config: Config, database_url: str) -> None:
    """Store a SQLAlchemy URL without letting ConfigParser interpolate percent escapes."""
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
