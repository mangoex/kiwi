# TDD - Catálogo POS progresivo

## TDD-TS-098 POS-UX-003 flujo progresivo y composición de modificadores

Casos:

- `progressiveCatalogStage` cubre categorías, selector previo, productos, Favoritos directo y modificadores sin
  calcular precio ni mutar carrito;
- la transición de menú/categoría/opción reutiliza `transitionCatalogNavigation`: limpia sólo
  personalización transitoria y preserva carrito/búsqueda;
- `modifierSelectionsMeetMinimums` deshabilita Agregar si cualquier grupo no satisface su mínimo y
  no convierte un grupo opcional en obligatorio;
- el POS sólo muestra opciones del grupo modificador activo, mantiene pestañas para todos los grupos
  y vuelve a productos después de confirmar;
- loading, error, vacío y Reintentar permanecen en la región activa y los controles usan semántica
  accesible.

## TDD-TC-193 Añadir producto personalizado sin perder contexto

Given Ensaladas, Chica y un carrito existente
When el Cajero cumple los mínimos de complementos y selecciona Agregar al pedido
Then se conserva el carrito y la región central vuelve a los productos Chica
And no cambia precio, contrato de carrito ni el `product_id` concreto.

## Comandos focalizados

```bash
node tests/frontend/test_pos_progressive_catalog.mjs
pnpm typecheck --filter @restaurantos/pos-web
pnpm --filter @restaurantos/pos-web build
python3 -m pytest tests/architecture/test_pos_progressive_catalog.py
```
