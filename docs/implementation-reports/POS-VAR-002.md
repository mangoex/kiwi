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

La migración lineal `0026_ingredient_variations` agrega `ingredient_variations`,
`ingredient_variation_products` e `ingredient_variation_commands`. El command log conserva la
llave de idempotencia, hash canónico, actor, estado y resultado serializable; replay no vuelve a
materializar ni auditar y un hash diferente falla con `idempotency_conflict`.

El downgrade archiva las `modifier_options` materializadas y los grupos de ingredientes vacíos
antes de retirar los tres metadatos. No borra pedidos, snapshots, KDS, print jobs, movimientos ni
las opciones históricas.

## Corrección de auditoría

- El commit inicial `dec012f55fa33282d6c9a289788a743f2508b941` introdujo el vertical POS-VAR-002.
- La corrección posterior añade idempotencia persistente, guard contra colisión de grupo,
  recálculo/archivo de grupos vacíos, alcance de receta y sucursal canónico, preload runtime sin
  N+1, downgrade con datos, logs estructurados y pruebas de carrera preview→apply y
  reserva/consumo.
- La UI corporativa separa Notas simples de Cambios de insumos; el detalle usa preview obligatorio,
  categorías, asignaciones editables y desvinculación lógica. Branch Admin sólo opera
  Disponible/No disponible/Heredar bajo `branch.admin.access` + `catalog.branch.manage`.

## Auditoría final y tercer commit

La corrección final rechaza `float`, booleanos, valores no finitos y texto decimal inválido en las
cantidades POS-VAR-002; conserva `Decimal` o cadenas decimales exactas. También restaura al
reactivar sólo las acciones todavía permitidas por cada asignación, recalcula el grupo y prueba que
la opción deshabilitada no reaparece en `GET /products/{id}/modifiers`.

El read model de sucursal ahora entrega nombre, SKU y unidad del insumo. El editor corporativo abre
un formulario precargado de asignación y sólo ejecuta `PUT` al guardar. El listado filtra Con/Sin
por conteos de relaciones activas, no por etiquetas. Se reforzó el alcance por organización en
detalle, actualización y desvinculación, y el `PUT` individual registra
`ingredient_variation.assignment.updated` una sola vez incluso con replay idempotente.

## Operación y evidencia

Los eventos incluyen `ingredient_variation.created`, `.updated`, `.archived`, `.reactivated`,
`.assignment.bulk_applied`, `.assignment.archived` y `.branch_configured`. Preview, apply, replay,
conflicto y error registran IDs de variación, actor, sucursal y key/correlation, sin nombres ni PII.

La verificación ejecutada cubre la suite focalizada API/UI, migración con datos y los builds web;
el gate final registró exit 0 para `pnpm install --frozen-lockfile`, typecheck y los tres builds;
la suite focalizada API (12), contrato frontend (2), trazabilidad (4), roundtrip con datos (4), ruff,
alembic head y diff check. `python3 -m pytest -q` cerró con 153 passed en 84.37 s. Riesgos
restantes: el warning local de Node 20 (el proyecto declara Node 22) no cambia el comportamiento
probado y no se afirma evidencia Docker local.
