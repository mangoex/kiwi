"""Focused frontend contract for POS-VAR-002 administrative surfaces."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_corporate_ingredient_variations_have_tabs_catalog_and_preview_contract() -> None:
    source = _read("apps/admin-web/src/features/catalog/VariationNotes.tsx")
    for value in (
        "Notas simples", "Cambios de insumos", "/catalog/ingredient-variations",
        "/catalog/ingredient-variations/${id}", "/categories",
        "Nuevo cambio de insumo", "Buscar insumo", "Quitar todo de la receta",
        "Precio adicional MXN", "Productos relacionados", "Reintentar", "Ver preview",
        "Hay incompatibles", "Desmárcalos", "assignments/${assignment.product_id}",
        "method: 'DELETE'", "Etiqueta Con", "Etiqueta Sin", "Editar relación",
        "Guardar relación", "setEditingAssignment(assignment)", "active_add_assignments",
    ):
        assert value in source
    assert "localStorage" not in source


def test_branch_supervisor_has_only_effective_availability_controls() -> None:
    source = _read("apps/pos-web/src/features/admin/BranchAdminVariations.tsx")
    assert "/branch-administration/catalog/ingredient-variations" in source
    assert "Notas simples" in source and "Cambios de insumos" in source
    assert "Disponible" in source and "No disponible" in source and "Heredar" in source
    assert "catalog.branch.manage" in source
    assert all(
        value in source
        for value in ("inventory_item_name", "inventory_item_sku", "unit_code")
    )
    assert "localStorage" not in source
