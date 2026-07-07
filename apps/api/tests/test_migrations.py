from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_audit_seed_payload_column_is_typed_as_json() -> None:
    migration = (
        ROOT
        / "apps"
        / "api"
        / "alembic"
        / "versions"
        / "202607071900_0002_base_operational_schema.py"
    ).read_text(encoding="utf-8")

    assert 'sa.column("payload", sa.JSON())' in migration

