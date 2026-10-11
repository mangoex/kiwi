# SEC001-SYNTHETIC-FIXTURE provenance=restaurantos-grokbot-agent-tools-contract-v1
from __future__ import annotations

from pathlib import Path

import yaml
from restaurant_os.config import get_settings
from restaurant_os.main import create_app

ROOT = Path(__file__).resolve().parents[3]
CONTRACT = ROOT / "packages/contracts/openapi/kiwi-agent-tools-v1.openapi.yaml"

EXPECTED_AGENT_OPERATIONS = {
    ("post", "/api/v1/agent-auth/token"),
    ("get", "/api/v1/agent-tools/context"),
    ("get", "/api/v1/agent-tools/catalog/items"),
    ("get", "/api/v1/agent-tools/sales/summary"),
    ("get", "/api/v1/agent-tools/inventory/items"),
    ("get", "/api/v1/agent-tools/inventory/stock"),
    ("get", "/api/v1/agent-tools/recipes"),
    ("get", "/api/v1/agent-tools/suppliers"),
    ("get", "/api/v1/agent-tools/purchase-needs"),
    ("post", "/api/v1/agent-tools/proposals/catalog"),
    ("post", "/api/v1/agent-tools/proposals/inventory-items"),
    ("post", "/api/v1/agent-tools/proposals/recipes"),
    ("post", "/api/v1/agent-tools/purchase-drafts"),
    ("get", "/api/v1/agent-tools/operations/{operation_id}"),
}


def _operations(schema: dict) -> set[tuple[str, str]]:
    return {
        (method, path)
        for path, path_item in schema["paths"].items()
        for method in path_item
        if method in {"get", "post", "put", "patch", "delete"}
    }


def test_tdd_tc_358_contract_matches_runtime_and_exposes_no_apply_commands() -> None:
    contract = yaml.safe_load(CONTRACT.read_text(encoding="utf-8"))
    settings = get_settings()
    previous = settings.grokbot_agent_tools_enabled
    settings.grokbot_agent_tools_enabled = True
    try:
        runtime = create_app().openapi()
    finally:
        settings.grokbot_agent_tools_enabled = previous

    assert contract["openapi"] == "3.1.0"
    assert contract["info"]["version"] == "1.0.0-rc.1"
    assert EXPECTED_AGENT_OPERATIONS <= _operations(contract)
    assert EXPECTED_AGENT_OPERATIONS <= _operations(runtime)

    runtime_agent_operations = {
        operation
        for operation in _operations(runtime)
        if operation[1].startswith("/api/v1/agent-tools")
        or operation[1] == "/api/v1/agent-auth/token"
    }
    assert runtime_agent_operations == EXPECTED_AGENT_OPERATIONS
    assert not any(
        forbidden in path
        for _method, path in runtime_agent_operations
        for forbidden in ("confirm", "receive", "payment", "cash", "movement", "cancel")
    )

    operation_ids = [
        operation["operationId"]
        for path_item in contract["paths"].values()
        for method, operation in path_item.items()
        if method in {"get", "post", "put", "patch", "delete"}
    ]
    assert len(operation_ids) == len(set(operation_ids))
    for schema_name in (
        "AgentContext",
        "SalesSummary",
        "CatalogProposalCommand",
        "InventoryItemProposalCommand",
        "RecipeProposalCommand",
        "PurchaseDraftCommand",
        "AgentOperation",
    ):
        assert contract["components"]["schemas"][schema_name]["additionalProperties"] is False

    error_schema = contract["components"]["schemas"]["BusinessError"]
    assert error_schema["required"] == ["detail"]
    detail_schema = contract["components"]["schemas"]["BusinessErrorDetail"]
    assert set(detail_schema["required"]) == {"code", "message", "correlation_id"}

    invalid_request_paths = {
        "/api/v1/agent-auth/token",
        "/api/v1/agent-tools/catalog/items",
        "/api/v1/agent-tools/sales/summary",
        "/api/v1/agent-tools/inventory/items",
        "/api/v1/agent-tools/inventory/stock",
        "/api/v1/agent-tools/recipes",
        "/api/v1/agent-tools/suppliers",
        "/api/v1/agent-tools/purchase-needs",
        "/api/v1/agent-tools/operations/{operation_id}",
    }
    for path in invalid_request_paths:
        assert (
            "400"
            in contract["paths"][path]["get" if path != "/api/v1/agent-auth/token" else "post"][
                "responses"
            ]
        )
