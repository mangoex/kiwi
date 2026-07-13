from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REVIEW = ROOT / "apps/admin-web/src/features/imports/LegacyImportReview.tsx"
PRODUCTS = ROOT / "apps/admin-web/src/features/catalog/ProductsList.tsx"
API = ROOT / "apps/api/restaurant_os/api.py"
DOMAIN = ROOT / "apps/api/restaurant_os/legacy_import.py"


def test_review_separates_each_pending_entity_type() -> None:
    source = REVIEW.read_text()

    assert "type PendingType = 'presentation' | 'product' | 'recipe'" in source
    assert "Presentaciones" in source
    assert "Productos" in source
    assert "Recetas" in source
    assert "entity_summary" in source


def test_review_explains_safe_canonical_actions() -> None:
    source = REVIEW.read_text()

    assert "Ir a Proveedores" in source
    assert "Configurar producto" in source
    assert "Capturar receta" in source
    assert "No guardes una receta vacía" in source
    assert "el costo heredado es sólo referencia" in source


def test_review_identifies_records_without_rendering_raw_payload() -> None:
    source = REVIEW.read_text()

    assert "normalized_payload" in source
    assert "name: textValue(payload.name)" in source
    assert "sku: textValue(payload.sku)" in source
    assert "raw_payload" not in source


def test_review_filters_and_paginates_on_the_server() -> None:
    source = REVIEW.read_text()

    assert "entity_type=${selectedType}" in source
    assert "limit=${PAGE_SIZE}" in source
    assert "offset=${page * PAGE_SIZE}" in source
    assert "setPage((current) => current + 1)" in source


def test_backend_exposes_entity_summary_and_validates_filter() -> None:
    api_source = API.read_text()
    domain_source = DOMAIN.read_text()

    assert "entity_type: str | None = None" in api_source
    assert '"entity_summary": _legacy_import_entity_summary' in domain_source
    assert '"invalid_import_entity_type"' in domain_source
    assert "models.legacy_import_records.c.entity_type == entity_type" in domain_source


def test_product_catalog_honors_import_review_search_link() -> None:
    review_source = REVIEW.read_text()
    products_source = PRODUCTS.read_text()

    assert "`/products?search=${encodeURIComponent(sku)}`" in review_source
    assert "useSearchParams" in products_source
    assert "searchParams.get('search')" in products_source
    assert "filteredProducts.map" in products_source
