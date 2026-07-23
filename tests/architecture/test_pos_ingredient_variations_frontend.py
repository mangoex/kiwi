"""Architecture contract for global order comments and universal POS extras."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_corporate_catalog_keeps_comments_and_universal_extras_separate() -> None:
    comments = _read("apps/admin-web/src/features/catalog/VariationNotes.tsx")
    extras = _read("apps/admin-web/src/features/catalog/IngredientExtras.tsx")
    app = _read("apps/admin-web/src/App.tsx")
    layout = _read("apps/admin-web/src/components/AdminLayout.tsx")

    assert "Comentarios del pedido" in comments
    assert "Configura indicaciones de cocina por subcategoría" in comments
    for value in (
        "Elige subcategorías",
        "Abre una categoría y marca las que correspondan.",
        "OPERATIONAL_GROUPS",
        "operationalGroupForStation",
        "Alimentos",
        "Bebidas",
        "Otros",
        "selectedCategoryIds",
        "selectedProductIds",
        "dos espacios",
        "Revisar aplicación",
        "Aplicar comentarios",
    ):
        assert value in comments
    assert "/catalog/ingredient-variations" not in comments
    assert "/catalog/order-comments" not in extras
    for value in (
        "Ingredientes adicionales",
        "/catalog/ingredient-variations",
        "Cantidad Decimal",
        "Precio de venta (MXN)",
        "Disponible para cualquier producto",
        "Guardar y activar",
        "mxnToCentsExact",
        "needs_review",
        "role=\"alert\"",
        "Cargando ingredientes adicionales",
        "No hay ingredientes adicionales",
    ):
        assert value in extras
    for legacy_control in (
        "/assignments",
        "Editar y productos",
        "Productos relacionados",
        "allow_add",
        "allow_remove",
        "Relacionar ",
    ):
        assert legacy_control not in extras
    assert "Permitir Sin" not in extras and "Quitar todo de la receta" not in extras
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
    assert "variation_kind === 'ingredient_extra'" in pos
    assert "aria-pressed" in pos and "pos-sale-complements" in pos
    assert "variation_kind === 'ingredient'" not in pos
    assert "disabled={cart.length === 0 || extrasLoading}" in pos
    assert "Línea destino" in pos and "Selecciona una línea" in pos
    assert "commentPresets.map((comment) => comment.id)" in pos
    assert "Comentario: {comment.text}" in pos


def test_preview_is_bound_to_exact_text_and_product_destinations() -> None:
    comments = _read("apps/admin-web/src/features/catalog/VariationNotes.tsx")
    for value in (
        "orderCommentPreviewFingerprint",
        "comments: text",
        "[...new Set(productIds)].sort()",
        "previewFingerprint",
        "currentPreviewFingerprint",
        "invalidatePreview()",
        "Los comentarios o las subcategorías cambiaron después de la vista previa",
        "onClick={requestCurrentPreview}",
        "onClick={applyCurrentPreview}",
        "const currentPreview = previewFingerprint === currentPreviewFingerprint ? preview : null",
    ):
        assert value in comments


def test_comment_targets_expand_categories_into_active_subcategory_products() -> None:
    comments = _read("apps/admin-web/src/features/catalog/VariationNotes.tsx")
    for value in (
        "product.status !== 'archived'",
        "product.category_id && selectedCategoryIds.includes(product.category_id)",
        "activeProducts.filter((product) => product.category_id === category.id).length",
        "aria-expanded={expanded}",
        'type="checkbox"',
        "selectedCategoryIds.length",
        "selectedProductIds.length",
        ".split(/(?:,|\\n|\\s{2,})/)",
    ):
        assert value in comments


def test_cents_only_cart_runner_remains_in_frontend_gate() -> None:
    pos = _read("apps/pos-web/src/features/pos/PointOfSale.tsx")
    package = _read("package.json")
    assert (ROOT / "apps/pos-web/src/features/pos/cartMoney.ts").is_file()
    assert (ROOT / "tests/frontend/test_pos_global_comments_extras.mjs").is_file()
    assert "test:pos-global-comments-extras" in package
    assert "cartLineTotalCents" in pos and "cartSubtotalCents" in pos
    assert "formatMxnCents" in pos
    assert "price_cents / 100" not in pos
    assert "sale_price_cents / 100" not in pos
