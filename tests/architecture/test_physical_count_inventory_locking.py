"""Static contract for the shared inventory writer lock protocol."""

from __future__ import annotations

import re
from pathlib import Path

OPERATIONS = (
    Path(__file__).resolve().parents[2]
    / "apps"
    / "api"
    / "restaurant_os"
    / "operations.py"
)


def _function_source(source: str, name: str) -> str:
    match = re.search(
        rf"^def {re.escape(name)}\(.*?(?=^def |\Z)",
        source,
        flags=re.DOTALL | re.MULTILINE,
    )
    assert match, f"Missing inventory writer {name}"
    return match.group(0)


def test_absolute_inventory_writers_lock_full_item_set_before_ledger_access() -> None:
    source = OPERATIONS.read_text(encoding="utf-8")
    writers = {
        "confirm_production_batch": "_physical_inventory_quantity(",
        "_confirm_purchase_document": "_physical_inventory_quantity(",
        "_cancel_purchase_document": "_physical_inventory_quantity(",
        "confirm_waste_record": "_physical_inventory_quantity(",
        "reverse_waste_record": "models.inventory_movements.insert(",
        "send_inventory_transfer": "_physical_inventory_quantity(",
        "receive_inventory_transfer": "_physical_inventory_quantity(",
        "create_physical_count_session": "_physical_inventory_quantity(",
        "approve_physical_count_session": "_physical_inventory_quantity(",
    }

    for function_name, first_inventory_access in writers.items():
        function = _function_source(source, function_name)
        bulk_lock = function.index("_acquire_inventory_advisory_locks(")
        inventory_access = function.index(first_inventory_access)
        assert bulk_lock < inventory_access, (
            f"{function_name} must lock its complete item set before inventory access"
        )


def test_bulk_inventory_lock_is_deduplicated_and_sorted() -> None:
    source = OPERATIONS.read_text(encoding="utf-8")
    helper = _function_source(source, "_acquire_inventory_advisory_locks")
    assert "sorted({str(item_id) for item_id in item_ids})" in helper
    assert "_acquire_inventory_advisory_lock(" in helper
