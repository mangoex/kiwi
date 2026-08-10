# TDD - Presentación de tarjetas de producto POS

## TDD-TS-076 POS-UX-002 presentación de tarjetas concretas

Casos:

- `tests/frontend/test_pos_product_card_presentation.mjs` compila e importa el helper puro de
  presentación y verifica que `null`, `undefined`, cadena vacía y espacios producen `fallback`,
  mientras una URL no vacía produce `image`.
- `tests/architecture/test_pos_product_card_presentation.py` verifica requisitos, BDD, TDD y matriz;
  que el helper y los modificadores se calculan sólo en `filteredProducts.map(product)`; que el
  selector previo conserva sus clases y su icono de 48 px; y que CSS fija y contiene tanto el
  contenedor de fotografía de 72 px como su `img`, y limita 52 px/32 px/14 px/1.25 al fallback.
- La evidencia visual local inspecciona estilos computados y flujo real con producto sin imagen,
  producto con imagen y selector Tamaño, en el viewport de referencia y en `<=1120 px`. Confirma
  ausencia de desbordamiento midiendo el padre y el elemento `img`, consola sin errores nuevos,
  selector sin modificación de carrito y alta/retiro del producto concreto.
- No se agregan dependencias, assets, migraciones ni cambios de backend, API, precio, carrito o
  complementos.

## TDD-TC-072 Clasificación y uso aislado de presentación de tarjeta

Given una URL de imagen opcional de un producto concreto
When el POS determina su presentación
Then una URL ausente o compuesta sólo por espacios produce fallback compacto
And una URL no vacía conserva la imagen y su texto alternativo
And el selector previo de categoría no usa ese helper ni los modificadores de tarjeta concreta.

## Comandos focalizados

```bash
python3 -m pytest tests/architecture/test_pos_product_card_presentation.py -q
pnpm test:pos-product-card-presentation
pnpm test:pos-category-options
python3 -m pytest tests/architecture/test_pos_category_options.py tests/architecture/test_pos_operational_ux.py tests/architecture/test_traceability.py -q
pnpm --filter @restaurantos/pos-web typecheck
pnpm --filter @restaurantos/pos-web build
```
