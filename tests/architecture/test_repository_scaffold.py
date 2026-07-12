from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_required_monorepo_paths_exist() -> None:
    required_paths = [
        "apps/api",
        "apps/worker",
        "apps/edge-gateway",
        "apps/admin-web",
        "apps/pos-web",
        "apps/kds-web",
        "packages/contracts",
        "packages/domain-types",
        "packages/test-fixtures",
        "infra/docker",
        "infra/easypanel",
        "docs",
        "tests/architecture",
    ]

    missing = [path for path in required_paths if not (ROOT / path).exists()]

    assert missing == []


def test_contract_schemas_exist() -> None:
    schemas = [
        "health.schema.json",
        "command-envelope.schema.json",
        "event-envelope.schema.json",
        "purchase-command.schema.json",
    ]

    missing = [
        schema
        for schema in schemas
        if not (ROOT / "packages" / "contracts" / "schemas" / schema).exists()
    ]

    assert missing == []


def test_dockerfiles_start_web_process_without_blocking_migrations() -> None:
    for path in ["Dockerfile", "infra/docker/api.Dockerfile"]:
        content = (ROOT / path).read_text(encoding="utf-8")

        assert '"uvicorn", "restaurant_os.main:app"' in content
        assert "alembic upgrade head && uvicorn" not in content
