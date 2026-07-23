"""Architecture checks for POS-UX-001 operational checkout and inventory."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
POS = ROOT / "apps" / "pos-web" / "src"
DOCS = ROOT / "docs"


def _pos_source(relative_path: str) -> str:
    return (POS / relative_path).read_text(encoding="utf-8")


def test_checkout_uses_only_canonical_branch_context() -> None:
    source = _pos_source("features/pos/PointOfSale.tsx")
    assert "session?.active_branch?.id || ''" in source
    assert "resolvePosBranchId" not in source
    assert "branch_id: branchId" in source


def test_customer_search_is_remote_debounced_and_cancelable() -> None:
    source = _pos_source("features/pos/PointOfSale.tsx")
    assert "phone," in source
    assert "validMexicanPhone(customerPhone)" in source
    assert "q: query" not in source
    assert "limit: '20'" in source
    assert "window.setTimeout" in source and ", 300)" in source
    assert "AbortController" in source
    assert "controller.abort()" in source


def test_customer_selection_is_independent_from_search_results() -> None:
    source = _pos_source("features/pos/PointOfSale.tsx")
    assert "const [selectedCustomer, setSelectedCustomer]" in source
    select_body = source.split("const selectCustomer", 1)[1].split(
        "const clearCustomer", 1
    )[0]
    assert "setSelectedCustomer(customer)" in select_body
    assert "setSearchResults([])" in select_body
    assert "setSelectedAddressId" in select_body


def test_checkout_address_form_is_complete_and_branch_scoped() -> None:
    source = _pos_source("features/pos/PointOfSale.tsx")
    for field in (
        "alias",
        "street",
        "exterior_number",
        "interior_number",
        "neighborhood",
        "postal_code",
        "city",
        "municipality",
        "state",
        "cross_streets",
        "references",
        "delivery_instructions",
        "is_default",
    ):
        assert field in source
    assert "JSON.stringify({ ...form, branch_id: branchId })" in source
    assert "setSelectedAddressId(addr.id)" in source


def test_legacy_address_is_reference_only_and_copy_is_explicit() -> None:
    source = _pos_source("features/pos/PointOfSale.tsx")
    assert "Domicilio heredado por confirmar" in source
    assert "Copiar domicilio heredado a Referencias" in source
    assert "set('references', legacyAddressReference)" in source
    initial_form = source.split("const [form, setForm]", 1)[1].split(");", 1)[0]
    assert "references: ''" in initial_form


def test_delivery_requires_customer_and_active_address() -> None:
    source = _pos_source("features/pos/PointOfSale.tsx")
    assert "a.status === 'active'" in source
    assert "orderType !== 'delivery' || (selectedCustomer && selectedAddressId)" in source
    assert "disabled={!canCheckout || !paymentMethod}" in source
    assert "Falta seleccionar domicilio de entrega" in source


def test_pos_keeps_horizontal_catalog_hierarchy_and_right_cart() -> None:
    source = _pos_source("features/pos/PointOfSale.tsx")
    styles = _pos_source("App.css")
    for class_name in (
        "pos-sale-menu",
        "pos-sale-submenu",
        "pos-sale-products",
        "pos-sale-complements",
        "pos-sale-cart",
    ):
        assert f'className="{class_name}"' in source or class_name in source
        assert f".{class_name}" in styles
    assert source.index('className="pos-sale-menu"') < source.index(
        'className="pos-sale-submenu"'
    )
    assert source.index('className="pos-sale-submenu"') < source.index(
        'className="pos-sale-products"'
    )


def test_pos_requires_and_sends_explicit_payment_method() -> None:
    source = _pos_source("features/pos/PointOfSale.tsx")
    for method in ("cash", "debit_card", "credit_card", "transfer"):
        assert method in source
    assert "method: paymentMethod" in source
    assert "disabled={!canCheckout || !paymentMethod}" in source
    assert "setPaymentMethod(null)" in source


def test_checkout_has_no_dead_controls_or_raw_fetch() -> None:
    source = _pos_source("features/pos/PointOfSale.tsx")
    for forbidden in ("Tables", "Discount", "Save Bill", "Voucher", "Order Details"):
        assert forbidden not in source
    assert re.search(r"\bfetch\s*\(", source) is None
    assert "fetchApi" in source


def test_inventory_uses_only_the_branch_stock_contract() -> None:
    source = _pos_source("features/inventory/PosInventory.tsx")
    assert "session?.active_branch?.id || ''" in source
    assert "/inventory/stock?branch_id=${encodeURIComponent(branchId)}" in source
    assert source.count("/inventory/") == 1
    assert "resolvePosBranchId" not in source


def test_inventory_states_are_ledger_based_without_arbitrary_threshold() -> None:
    source = _pos_source("features/inventory/PosInventory.tsx")
    for label in (
        "Existencias teóricas derivadas de movimientos",
        "Con existencia",
        "Sin existencia",
        "Existencia negativa",
        "Último movimiento",
    ):
        assert label in source
    assert "qty > 0" in source
    assert "qty === 0" in source
    assert "qty < 0" in source
    assert "qty < 20" not in source


def test_pos_ux_specification_and_traceability_exist() -> None:
    bdd = (DOCS / "03-BDD-pos-operational-ux.md").read_text(encoding="utf-8")
    tdd = (DOCS / "04-TDD-pos-operational-ux.md").read_text(encoding="utf-8")
    matrix = (DOCS / "05-matriz-trazabilidad.md").read_text(encoding="utf-8")
    for scenario in (*range(156, 163), 231):
        assert f"BDD-SC-{scenario}" in bdd
    assert "TDD-TS-055" in tdd and "TDD-TC-048" in tdd and "TDD-TC-064" in tdd
    assert "PRD-NFR-018" in matrix
    assert "TDD-TS-055" in matrix
