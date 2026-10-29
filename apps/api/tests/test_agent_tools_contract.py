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
    ("get", "/api/v1/agent-tools/expenses/summary"),
    ("get", "/api/v1/agent-tools/payments/by-method"),
    ("get", "/api/v1/agent-tools/cash/cuts"),
    ("get", "/api/v1/agent-tools/cash/daily-reconciliation"),
    ("get", "/api/v1/agent-tools/inventory/items"),
    ("get", "/api/v1/agent-tools/inventory/stock"),
    ("get", "/api/v1/agent-tools/inventory/movements"),
    ("get", "/api/v1/agent-tools/recipes"),
    ("get", "/api/v1/agent-tools/suppliers"),
    ("get", "/api/v1/agent-tools/purchase-presentations"),
    ("get", "/api/v1/agent-tools/purchases/history"),
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
    assert contract["info"]["version"] == "1.0.0-rc.5"
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
        for method, path in runtime_agent_operations
        for forbidden in ("confirm", "receive", "cancel")
    )
    assert {
        operation for operation in runtime_agent_operations if "payment" in operation[1]
    } == {("get", "/api/v1/agent-tools/payments/by-method")}
    assert {operation for operation in runtime_agent_operations if "cash" in operation[1]} == {
        ("get", "/api/v1/agent-tools/cash/cuts"),
        ("get", "/api/v1/agent-tools/cash/daily-reconciliation"),
    }
    assert not any(
        method != "get" and "movement" in path for method, path in runtime_agent_operations
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
        "InventoryMovement",
        "PurchasePresentation",
        "PurchaseHistoryDocument",
        "PurchaseHistoryLine",
        "CashCut",
        "ExpenseSummary",
        "PaymentMethodSummary",
        "DailyReconciliation",
    ):
        assert contract["components"]["schemas"][schema_name]["additionalProperties"] is False

    assert set(contract["components"]["schemas"]["InventoryMovement"]["properties"]) == {
        "id",
        "item_id",
        "warehouse_id",
        "movement_type",
        "quantity_delta",
        "unit_id",
        "effective_at",
        "status",
    }
    assert set(contract["components"]["schemas"]["CashCut"]["properties"]) == {
        "id",
        "branch_id",
        "register_code",
        "period_start",
        "period_end",
        "finalized_at",
        "opening_cash_cents",
        "cash_payment_cents",
        "deposit_cents",
        "withdrawal_cents",
        "expected_cash_cents",
        "counted_cash_cents",
        "difference_cents",
        "compensated",
    }
    assert set(contract["components"]["schemas"]["PurchasePresentation"]["properties"]) == {
        "id",
        "supplier_id",
        "supplier_name",
        "item_id",
        "item_name",
        "code",
        "name",
        "commercial_quantity",
        "commercial_unit_id",
        "base_unit_id",
        "base_unit_yield",
        "usable_content",
        "yield_percent",
        "tax_rate",
        "last_net_price",
        "cost_per_base_unit",
        "currency",
        "preferred",
        "version",
    }
    assert set(contract["components"]["schemas"]["PurchaseHistoryDocument"]["properties"]) == {
        "id",
        "supplier_id",
        "supplier_name",
        "supplier_name_source",
        "currency",
        "currency_source",
        "document_type",
        "document_date",
        "confirmed_at",
        "cancelled_at",
        "status",
        "subtotal",
        "discount_total",
        "tax_total",
        "freight_total",
        "total",
        "lines",
    }
    assert set(contract["components"]["schemas"]["PurchaseHistoryLine"]["properties"]) == {
        "item_id",
        "item_name",
        "item_name_source",
        "presentation_id",
        "presentation_name",
        "presentation_name_source",
        "presentation_quantity",
        "base_quantity",
        "unit_price",
        "discount",
        "tax",
        "line_total",
        "inventory_cost",
        "cost_per_base_unit",
    }
    capability_enum = contract["components"]["schemas"]["AgentContext"]["properties"][
        "capabilities"
    ]["items"]["enum"]
    assert "agent.purchases.read" in capability_enum
    assert "agent.cash_cuts.read" in capability_enum
    assert "agent.operating_expenses.read" in capability_enum
    assert "agent.payment_methods.read" in capability_enum
    assert "agent.cash_reconciliation.read" in capability_enum
    assert "agent.cash_personal_data.read" in capability_enum

    error_schema = contract["components"]["schemas"]["BusinessError"]
    assert error_schema["required"] == ["detail"]
    detail_schema = contract["components"]["schemas"]["BusinessErrorDetail"]
    assert set(detail_schema["required"]) == {"code", "message", "correlation_id"}

    invalid_request_paths = {
        "/api/v1/agent-auth/token",
        "/api/v1/agent-tools/catalog/items",
        "/api/v1/agent-tools/sales/summary",
        "/api/v1/agent-tools/expenses/summary",
        "/api/v1/agent-tools/payments/by-method",
        "/api/v1/agent-tools/cash/cuts",
        "/api/v1/agent-tools/cash/daily-reconciliation",
        "/api/v1/agent-tools/inventory/items",
        "/api/v1/agent-tools/inventory/stock",
        "/api/v1/agent-tools/inventory/movements",
        "/api/v1/agent-tools/recipes",
        "/api/v1/agent-tools/suppliers",
        "/api/v1/agent-tools/purchase-presentations",
        "/api/v1/agent-tools/purchases/history",
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
