"""Create disposable schemas without mutating the application's shared metadata."""

from collections.abc import Iterable

import sqlalchemy as sa
from restaurant_os import models


def create_fixture_tables(
    engine: sa.Engine, *, tables: Iterable[sa.Table] | None = None
) -> None:
    metadata = sa.MetaData()
    for table in models.metadata.tables.values():
        table.to_metadata(metadata)
    selected = None if tables is None else [metadata.tables[table.key] for table in tables]
    metadata.create_all(engine, tables=selected)
