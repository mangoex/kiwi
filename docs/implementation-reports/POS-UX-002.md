# POS-UX-002 — jerarquía visual de tarjetas POS sin fotografía

## Alcance aprobado

Cambiar sólo las tarjetas de productos concretos sin `image_url` utilizable: fallback compacto,
icono existente menor y nombre más legible. Se preservan las tarjetas con fotografía y el selector
previo Tamaño (Chica/Grande), además de precio, carrito, complementos y contratos existentes.

## Trazabilidad

- Cambio: `POS-UX-002`.
- Requisito: `PRD-FR-214`.
- Diseño: sección 37 de `docs/02-SDD.md`. La sección 36 ya pertenecía a `POS-ATT-001`; no se
  renumeró historia documental existente.
- Comportamiento: `BDD-FEAT-075`, `BDD-SC-265` a `BDD-SC-269`.
- Verificación: `TDD-TS-076`, `TDD-TC-072`.

## Antes y después

- Antes: una tarjeta concreta sin `image_url` usaba el mismo contenedor visual de 72 px, icono de
  48 px y título de 12 px que el selector previo.
- Después: sólo `filteredProducts.map(product)` determina `image` o `fallback` con
  `productCardPresentation`. El fallback usa 52 px, icono Lucide de 32 px y título de 14 px,
  `line-height: 1.25`, peso 700 y ajuste de palabra; la tarjeta con imagen conserva 72 px,
  `<img alt={product.name}>` y `object-fit: contain`. El selector `activeSelectionGroup.values`
  permanece con `getProductIcon(activeCategory, 48)` y no usa el helper.

## Archivos modificados

- `apps/pos-web/src/features/pos/productCardPresentation.ts` — helper puro sin dependencias.
- `apps/pos-web/src/features/pos/PointOfSale.tsx` — modificadores sólo en la tarjeta concreta.
- `apps/pos-web/src/App.css` — reglas limitadas al fallback y preservación explícita de foto.
- `tests/frontend/test_pos_product_card_presentation.mjs` y
  `tests/architecture/test_pos_product_card_presentation.py` — prueba ejecutable del helper y
  contrato de integración estática.
- `package.json`, PRD, SDD, BDD, TDD y matriz — script y trazabilidad del cambio.

## Corrección posterior a auditoría inicial

Sol encontró que una foto podía conservar un padre de 72 px mientras el elemento `img` medía 156 px,
aumentaba el `scrollHeight` de la tarjeta y se superponía con el nombre/precio. La corrección acota
sólo `.pos-sale-product-visual--with-image` a 72 px rígidos y ocultos, y acota físicamente su `img`.
El fallback se fija de igual modo a 52 px. La prueba arquitectónica ya no inspecciona `git diff`:
verifica declaraciones CSS deterministas de dimensión y contención.

## Evidencia histórica RED a GREEN

- La primera implementación tuvo RED de arquitectura por ausencia de POS-UX-002, helper,
  modificadores y CSS; el primer GREEN aprobó 4 pruebas.
- La corrección de contención tuvo RED por ausencia del selector CSS específico de `img`; su GREEN
  aprobó la suite afectada. Estos conteos son antecedentes y no sustituyen la evidencia final.

## Segunda auditoría final de Sol

- Suite combinada vigente: `31 passed`, exit 0. El total es 31 porque se eliminó la prueba no
  determinista que leía `git diff`.
- `tests/frontend/test_pos_product_card_presentation.mjs`: exit 0.
- `tests/frontend/test_pos_category_options.mjs`: exit 0.
- TypeScript estricto de `@restaurantos/pos-web`: exit 0.
- Build de producción Vite: exit 0, 1579 módulos transformados.
- `git diff --check`: exit 0.
- Visual local con fixtures deterministas, 1440x900: foto padre e `img` de 72 px, tarjeta
  `clientHeight=scrollHeight=157`; fallback de 52 px, icono 32 px, nombre 14 px/700/17.5 px;
  sin solapamientos.
- Visual local con fixtures deterministas, 1000x800: foto padre e `img` de 72 px, fallback de
  52 px, sin solapamientos ni scroll horizontal.
- Selector previo intacto: padre 72 px, icono 48 px, nombre 12 px, sin modificadores de producto
  y carrito en $0. El flujo Grande → producto $185 → carrito $185 → eliminar → carrito vacío $0
  fue aprobado.
- La sesión visual, servidor temporal y enlaces temporales de `node_modules` fueron cerrados o
  retirados al concluir.

## Estado y riesgos residuales

Al iniciar: worktree limpio, HEAD separado `32981ec95fcf1d3d4e2549f3d297edfe5a5c5f28`, sin trabajo
ajeno que preservar. No hubo cambios backend, API, datos, precios, recetas, inventario, pedidos,
migraciones, assets, lockfile ni dependencias. La fila `PRD-FR-214` queda **Implementado** con los
gates afectados aprobados. No hubo commit, push, merge ni despliegue, ni validación contra datos o
activos reales de producción; la evidencia visual fue local con fixtures deterministas.
