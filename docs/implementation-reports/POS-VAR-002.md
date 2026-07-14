# POS-VAR-002 — variaciones de insumos relacionadas con productos

## Alcance

- Incorpora `PRD-FR-200`, `BDD-FEAT-058` (`BDD-SC-175..184`) y `TDD-TS-058`/`TDD-TC-051`.
- La migración `0026_ingredient_variations` agrega definiciones por insumo y asignaciones lógicas
  sin borrado físico; materializa opciones `add`/`remove` en el grupo separado **Cambios de
  ingredientes**.
- El pedido conserva el motor de modificadores, el snapshot, el costo promedio por sucursal y los
  flujos existentes de reserva, consumo, KDS e impresión. El precio al cliente sólo usa el delta
  explícito configurado.
- El catálogo corporativo expone definición, listado, detalle, preview, aplicación idempotente,
  edición y archivo lógico de asignaciones. El POS recibe opciones enriquecidas y mantiene exclusión
  mutua de Con/Sin por variación; el backend vuelve a rechazar el conflicto.

## Seguridad y operación

Las operaciones corporativas requieren `catalog.manage`. La administración de sucursal exige
`branch.admin.access` y `catalog.branch.manage`, usa la sucursal canónica y sólo modifica
Disponible/No disponible/Heredar por opción. Los comandos sensibles emiten eventos de auditoría.
POS-VAR-001 y el grupo **Variaciones y cambios** no se reutilizan ni se alteran.

## Reversibilidad

El downgrade elimina exclusivamente las dos tablas de metadatos nuevas. No modifica
`modifier_options`, pedidos, snapshots ni movimientos históricos.
