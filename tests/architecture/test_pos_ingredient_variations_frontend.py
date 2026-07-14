"""Architecture contract for POS-VAR-003 separated comments and extras."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_corporate_routes_keep_comments_and_additional_ingredients_separate() -> None:
    comments = _read("apps/admin-web/src/features/catalog/VariationNotes.tsx")
    extras = _read("apps/admin-web/src/features/catalog/IngredientExtras.tsx")
    app = _read("apps/admin-web/src/App.tsx")
    layout = _read("apps/admin-web/src/components/AdminLayout.tsx")
    assert "Comentarios del pedido" in comments
    assert "Indicaciones para cocina; no cambian precio, receta ni inventario." in comments
    assert "Cambios de insumos" not in comments
    assert "/catalog/ingredient-variations" not in comments
    for value in (
        "Ingredientes adicionales", "/catalog/ingredient-variations",
        "allow_add: true", "allow_remove: false", "remove_quantity: '0'",
        "Cantidad Decimal", "Precio adicional (MXN)", "Productos relacionados",
        "/categories", "Ver preview", "Hay incompatibles", "Desmárcalos",
        "assignments/${editing.product_id}", "method: 'DELETE'", "mxnToCentsExact",
        "Acciones de retiro heredadas", "Comentarios del pedido",
        "ApiError", "operationalError", "mainError", "editError", "resetCreate",
        "setLabel(`Porción extra de ${item.name}`)", "role=\"alert\"",
    ):
        assert value in extras
    assert "Permitir Sin" not in extras and "Quitar todo de la receta" not in extras
    assert "if (!label)" not in extras
    assert 'path="variations"' in app and 'path="ingredient-extras"' in app
    assert "Comentarios del pedido" in layout and "Ingredientes adicionales" in layout
    assert "localStorage" not in comments and "localStorage" not in extras


def test_branch_routes_and_pos_sections_are_separated_and_guarded() -> None:
    notes = _read("apps/pos-web/src/features/admin/BranchAdminVariations.tsx")
    extras = _read("apps/pos-web/src/features/admin/BranchAdminIngredientExtras.tsx")
    app = _read("apps/pos-web/src/App.tsx")
    hub = _read("apps/pos-web/src/features/admin/AdminHub.tsx")
    pos = _read("apps/pos-web/src/features/pos/PointOfSale.tsx")
    assert "/branch-administration/catalog/variation-notes" in notes
    assert "/branch-administration/catalog/ingredient-variations" not in notes
    assert "Comentarios del pedido" in notes and "catalog.branch.manage" in notes
    assert "/branch-administration/catalog/ingredient-variations" in extras
    assert "Ingredientes adicionales" in extras
    assert all(
        value in extras
        for value in ("inventory_item_name", "Disponible", "No disponible", "Heredar")
    )
    assert "localStorage" not in notes and "localStorage" not in extras
    assert 'path="administration/ingredient-extras"' in app
    assert app.count('permission="branch.admin.access"') >= 2
    assert "Comentarios del pedido" in hub and "Ingredientes adicionales" in hub
    assert "Personaliza ${modifierProduct?.name || ''}" in pos
    assert "Comentarios del pedido" in pos and "Ingredientes adicionales" in pos
    assert "variation_kind === 'ingredient_extra'" in pos
    assert "aria-pressed" in pos and "minHeight: 48" in pos
    assert "variation_kind === 'ingredient'" not in pos


def test_exact_money_runner_remains_in_frontend_gate() -> None:
    assert (ROOT / "tests/frontend/test_ingredient_variation_money.mjs").is_file()
    package = _read("package.json")
    assert "test:ingredient-variation-money" in package
