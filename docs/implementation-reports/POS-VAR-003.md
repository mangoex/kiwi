# POS-VAR-003 — separación de comentarios e ingredientes adicionales

## Decisión y compatibilidad

POS-VAR-003 separa comentarios del pedido (`preset_instruction`, sin efecto comercial ni de
inventario) de ingredientes adicionales (`add`, inventario/costo y cargo explícito opcional). No
revierte POS-VAR-002: conserva tablas, endpoints, IDs, opciones remove y snapshots históricos.
Para ventas nuevas bloquea remove asociado a `ingredient_variation_products`, sin afectar otros
modificadores remove/substitute legítimos.

## Esquema y operación

No hay migración nueva ni modificación de `0026_ingredient_variations`; la única head permanece
`0026_ingredient_variations`. El catálogo corporativo y administración de sucursal usan rutas y
menús separados para Comentarios del pedido e Ingredientes adicionales. Permisos corporativos son
`catalog.manage`; disponibilidad de sucursal exige `branch.admin.access` y
`catalog.branch.manage` sobre la sucursal canónica.

## Implementación

El catálogo corporativo queda dividido en `/admin/variations` (**Comentarios del pedido**) y
`/admin/ingredient-extras` (**Ingredientes adicionales**). El primero conserva exclusivamente el
CRUD POS-VAR-001. El segundo usa el catálogo compatible de `ingredient_variations`, presenta
cantidad Decimal y unidad base por producto, preview de productos/categorías activos y captura el
cargo como MXN exacto antes de enviar `add_price_delta_cents`. Las acciones remove heredadas se
advierten aparte y no son editables ni seleccionables.

La administración de sucursal queda igualmente dividida entre
`/pos/administration/variations` y `/pos/administration/ingredient-extras`. El supervisor sólo
puede elegir Disponible, No disponible o Heredar con `branch.admin.access` y
`catalog.branch.manage` sobre la sucursal de sesión; no puede alterar catálogo, cantidad ni precio.
El cajero no recibe las tarjetas ni las rutas protegidas.

En backend, preview, bulk apply y update individual rechazan remove con
`ingredient_extra_add_only`; las opciones `remove_option_id` que ya existen se excluyen de
`GET /products/{product_id}/modifiers` y del read model de sucursal. La defensa de creación de
pedido vuelve a rechazar su `option_id` manualmente antes de modificar snapshots. Las opciones
`remove` ajenas a `ingredient_variation_products` permanecen disponibles. Reactivar una definición
restaura sólo sus `add_option_id` activos. Se preservan auditorías, command log, snapshots, KDS y
comandas existentes.

## Evidencia y riesgos

Las pruebas focalizadas cubren contrato add-only, exactitud Decimal, replay idempotente, ocultación
y rechazo de remove heredado, costo/reserva/consumo de adicionales, comentarios
`preset_instruction`, permisos y superficies separadas. Antes del commit, `pnpm install
--frozen-lockfile`, `pnpm typecheck` y los builds admin/POS/KDS finalizaron con exit 0;
`python3 -m pytest` finalizó con **155 passed** y `ruff check apps/api tests` con exit 0. La
validación usa Node 20.20.2 aunque el repositorio declara Node >=22: es una advertencia ambiental
sin dependencia alterada. El SHA se registra con el commit de entrega. Riesgo operativo: remove heredado puede seguir existir
como dato auditado, pero no puede usarse en ventas nuevas; la operación debe crear una indicación
en Comentarios del pedido para “Sin …”.
