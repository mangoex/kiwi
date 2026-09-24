"""Real additive Alembic migration preserves pending categories and protects history."""

import sqlite3

from test_cash_ledger_migration import _sqlite_alembic

PREVIOUS = "0069_selectable_compound_product"
REVISION = "0070_catalog_classification"


def test_sqlite_upgrade_preserves_categories_and_roundtrip(tmp_path):
    path = tmp_path / "classification.db"
    result = _sqlite_alembic(path, "upgrade", PREVIOUS)
    assert result.returncode == 0, result.stderr
    with sqlite3.connect(path) as connection:
        connection.execute(
            "INSERT INTO product_categories "
            "(id,organization_id,name,display_order,status,created_at,updated_at) "
            "VALUES ('synthetic','org','MIXED',9,'inactive','2026-09-24','2026-09-24')"
        )
        before = connection.execute("SELECT * FROM product_categories").fetchall()
    result = _sqlite_alembic(path, "upgrade", REVISION)
    assert result.returncode == 0, result.stderr
    with sqlite3.connect(path) as connection:
        after = connection.execute("SELECT * FROM product_categories").fetchall()
        assert [row[:-2] for row in after] == before
        assert all(row[-2:] == (None, 1) for row in after)
    result = _sqlite_alembic(path, "downgrade", PREVIOUS)
    assert result.returncode == 0, result.stderr
    result = _sqlite_alembic(path, "upgrade", REVISION)
    assert result.returncode == 0, result.stderr
    with sqlite3.connect(path) as connection:
        connection.execute(
            "UPDATE product_categories SET classification_code='food' WHERE id='synthetic'"
        )
    result = _sqlite_alembic(path, "downgrade", PREVIOUS)
    assert result.returncode != 0
    assert "Classification history exists" in result.stderr


def test_sqlite_schema_rejects_unknown_classification_and_nonpositive_version(tmp_path):
    path = tmp_path / "constraints.db"
    result = _sqlite_alembic(path, "upgrade", REVISION)
    assert result.returncode == 0, result.stderr
    with sqlite3.connect(path) as connection:
        for classification, version in (("coffee", 1), ("food", 0), ("drinks", -1)):
            try:
                connection.execute(
                    "INSERT INTO product_categories "
                    "(id,organization_id,name,status,created_at,updated_at,"
                    "classification_code,configuration_version) "
                    "VALUES ('bad','org','BAD','active','2026-09-24','2026-09-24',?,?)",
                    (classification, version),
                )
            except sqlite3.IntegrityError:
                continue
            raise AssertionError("Database constraint accepted invalid configuration")
