"""Architecture contract for POS-UX-002 product-card presentation."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_pos_product_card_specs_and_traceability_exist() -> None:
    prd = _read("docs/01-PRD.md")
    sdd = _read("docs/02-SDD.md")
    bdd = _read("docs/03-BDD-pos-product-card-presentation.md")
    tdd = _read("docs/04-TDD-pos-product-card-presentation.md")
    matrix = _read("docs/05-matriz-trazabilidad.md")

    assert "PRD-FR-214" in prd and "POS-UX-002" in sdd
    assert "BDD-FEAT-075" in bdd
    for identifier in range(265, 270):
        assert f"BDD-SC-{identifier}" in bdd and f"BDD-SC-{identifier}" in matrix
    assert "TDD-TS-076" in tdd and "TDD-TC-072" in tdd


def test_concrete_products_alone_resolve_product_card_presentation() -> None:
    source = _read("apps/pos-web/src/features/pos/PointOfSale.tsx")
    selector = source.split("activeSelectionGroup.values.map", 1)[1].split(
        ") : filteredProducts.length", 1
    )[0]
    product_map = source.split("filteredProducts.map((product) =>", 1)[1].split(
        "</section>", 1
    )[0]

    assert "productCardPresentation" not in selector
    assert "pos-sale-product-card--icon" not in selector
    assert "getProductIcon(activeCategory, 48)" in selector
    assert "const presentation = productCardPresentation(product.image_url);" in product_map
    assert (
        "pos-sale-product-card--${presentation}" in product_map
    )
    assert "pos-sale-product-visual--${presentation}" in product_map
    assert "getProductIcon(product.category, 32)" in product_map
    assert "<img" not in product_map
    assert "onClick={() => void selectProduct(product)}" in product_map
    assert "formatMxnCents(product.price_cents)" in product_map


def test_icon_only_css_preserves_required_dimensions() -> None:
    css = _read("apps/pos-web/src/App.css")

    icon = re.search(
        r"\.pos-sale-product-visual--icon\s*\{(?P<rules>[^}]*)\}", css, re.S
    )
    assert icon
    for declaration in (
        "height: 52px",
        "min-height: 52px",
        "max-height: 52px",
        "flex-basis: 52px",
        "flex-shrink: 0",
    ):
        assert declaration in icon.group("rules")
    icon_label = r"\.pos-sale-product-card--icon\s*>\s*span\s*\{[^}]*"
    assert re.search(icon_label + r"font-size:\s*14px", css, re.S)
    assert re.search(icon_label + r"line-height:\s*1\.25", css, re.S)
    assert re.search(icon_label + r"font-weight:\s*700", css, re.S)
    assert "overflow-wrap: anywhere" in css
    assert ".pos-sale-product-visual--with-image" not in css
    assert ".pos-sale-product-visual img" not in css
