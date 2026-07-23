"""Architecture contract for the POS orders master-detail experience."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_orders_detail_is_an_inline_right_panel_not_a_modal() -> None:
    source = _read("apps/pos-web/src/features/history/History.tsx")
    assert "Modal" not in source
    assert 'className="orders-history-layout"' in source
    assert 'aria-label="Detalle del pedido"' in source
    assert "orders-history-detail" in source
    assert "Selecciona un pedido para revisar su detalle" in source


def test_selected_row_and_existing_actions_remain_available() -> None:
    source = _read("apps/pos-web/src/features/history/History.tsx")
    assert "selected?.id === order.id" in source
    assert "is-selected" in source
    assert "Confirmar pagado" in source
    assert "Editar pedido" in source
    assert "/payments" in source
    assert "edit_order_id" in source


def test_master_detail_is_responsive_and_traceable() -> None:
    styles = _read("apps/pos-web/src/App.css")
    bdd = _read("docs/03-BDD-pos-order-operations-wave.md")
    tdd = _read("docs/04-TDD-pos-order-operations-wave.md")
    matrix = _read("docs/05-matriz-trazabilidad.md")
    assert "grid-template-columns: minmax(0, 1fr) minmax(340px, 390px)" in styles
    assert "@media (max-width: 1100px)" in styles
    assert "BDD-SC-248" in bdd and "BDD-SC-248" in matrix
    assert "TDD-TS-073" in tdd and "TDD-TC-069" in tdd
    assert "TDD-TS-073" in matrix and "TDD-TC-069" in matrix
