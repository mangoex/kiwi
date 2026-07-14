"""Focused frontend contract for POS-VAR-002 administrative surfaces."""

import json
import subprocess
import tempfile
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
        "Precio adicional (MXN)", "inputMode=\"decimal\"", "placeholder=\"0.00\"",
        "add_price_delta_mxn", "mxnToCentsExact", "centsToMxn",
        "Productos relacionados", "Reintentar", "Ver preview",
        "Hay incompatibles", "Desmárcalos", "assignments/${assignment.product_id}",
        "method: 'DELETE'", "Etiqueta Con", "Etiqueta Sin", "Editar relación",
        "Guardar relación", "setEditingAssignment(assignment)", "active_add_assignments",
    ):
        assert value in source
    assert "definitionActions" not in source
    assert "localStorage" not in source


def test_mxn_surcharge_conversion_is_exact_and_executable() -> None:
    source_file = ROOT / "apps/admin-web/src/features/catalog/ingredientVariationMoney.ts"
    with tempfile.TemporaryDirectory() as temporary_directory:
        output_dir = Path(temporary_directory)
        compile_result = subprocess.run(
            [
                str(ROOT / "node_modules/.bin/tsc"),
                "--target", "ES2022", "--module", "NodeNext", "--moduleResolution", "NodeNext",
                "--outDir", str(output_dir), str(source_file),
            ],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        assert compile_result.returncode == 0, compile_result.stderr
        script = """
import { mxnToCentsExact, centsToMxn } from __MODULE__;
const invalid = ['', '-1', '20.001', 'letras', 'NaN', 'Infinity', '90071992547409.92'];
console.log(JSON.stringify({
  pesos: mxnToCentsExact('20'),
  oneDecimal: mxnToCentsExact('20.5'),
  twoDecimals: mxnToCentsExact('20.50'),
  display: centsToMxn(2000),
  roundTrip: centsToMxn(mxnToCentsExact('20.50')),
  invalid: invalid.map((value) => {
    try { mxnToCentsExact(value); return false; } catch { return true; }
  }),
}));
""".replace("__MODULE__", json.dumps((output_dir / "ingredientVariationMoney.js").as_uri()))
        executed = subprocess.run(
            ["node", "--input-type=module", "-e", script],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
    assert executed.returncode == 0, executed.stderr
    assert json.loads(executed.stdout) == {
        "pesos": 2000,
        "oneDecimal": 2050,
        "twoDecimals": 2050,
        "display": "20.00",
        "roundTrip": "20.50",
        "invalid": [True] * 7,
    }


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
