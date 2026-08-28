# TDD - Presentación de tarjetas de producto POS

## TDD-TS-076 POS-UX-002 presentación de tarjetas concretas

Casos:

- `tests/frontend/test_pos_product_card_presentation.mjs` compila e importa el helper puro de
  presentación y verifica que `null`, `undefined`, cadena vacía, espacios y una URL no vacía
  producen `icon`; también comprueba que tarjetas y carrito no renderizan `img`.
- `tests/architecture/test_pos_product_card_presentation.py` verifica requisitos, BDD, TDD y matriz;
  que el helper y los modificadores se calculan sólo en `filteredProducts.map(product)`; que el
  selector previo conserva sus clases y su icono de 48 px; y que CSS limita la presentación de
  producto a 52 px/32 px/14 px/1.25 sin selectores de fotografía.
- La evidencia visual local inspecciona estilos computados y flujo real con producto sin imagen,
  producto con `image_url` y selector Tamaño, en el viewport de referencia y en `<=1120 px`.
  Confirma que no existen imágenes de producto, consola sin errores nuevos,
  selector sin modificación de carrito y alta/retiro del producto concreto.
- No se agregan dependencias, assets, migraciones ni cambios de backend, API, precio, carrito o
  complementos.

## TDD-TC-072 Clasificación y uso aislado de presentación de tarjeta

Given cualquier valor de image_url de un producto concreto
When el POS determina su presentación
Then siempre produce la presentación icon
And una URL no vacía no se renderiza en la tarjeta ni en el carrito
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
