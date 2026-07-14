# POS-VAR-001 — variaciones preestablecidas

## Alcance implementado

- `PRD-FR-199`, `BDD-FEAT-057` y `BDD-SC-168..174` definen notas preestablecidas por producto;
- `modifier_groups`, `modifier_options` y `branch_modifier_options` se reutilizan sin migración;
- `preset_instruction` fuerza precio cero, sin efecto de receta/inventario y texto de cocina
  controlado por servidor;
- pedidos, snapshots, KDS y payload de impresión de cocina conservan las notas;
- administración corporativa (`/admin/variations`) y de sucursal
  (`/pos/administration/variations`) respetan `catalog.manage`, `branch.admin.access`,
  `catalog.branch.manage` y `pos.operate`;
- el POS muestra presets como botones táctiles multiselección y conserva modificadores avanzados e
  instrucciones libres.

## Migración y operación

No requiere migración: `modifier_options.effect_type` ya es `VARCHAR(24)` y las columnas usadas
por las invariantes ya existen. No se introdujo una nueva head Alembic. Las notas archivadas no se
eliminan y los snapshots históricos permanecen inmutables.

Los eventos de auditoría son `variation_note.created`, `variation_note.updated`,
`variation_note.archived`, `variation_note.reactivated` y `variation_note.branch_configured`.
Los errores de autorización continúan pasando por la auditoría `authorization.denied` existente.

## Verificación

La suite `TDD-TS-057` y el caso `TDD-TC-050` cubren invariantes, duplicados normalizados,
permisos, herencia por sucursal, snapshot, KDS, impresión, auditoría y los contratos frontend.
