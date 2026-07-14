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
permisos, herencia por sucursal, snapshot, read model/API KDS, impresión, auditoría y los contratos
frontend. La pantalla `kds-web` continúa estática y no se declara como integrada con esos datos.

## Corrección posterior a auditoría

- Un grupo avanzado homónimo ya no se normaliza: se rechaza `variation_group_conflict` sin tocar
  sus opciones ni cardinalidad; un grupo exclusivamente preset compatible sí se reutiliza.
- `display_order` se valida como entero no booleano antes de persistir, por lo que POST y PUT
  devuelven error de negocio en lugar de `ValueError`/500.
- El reintento POS que devuelve cero grupos limpia el estado del modal antes de agregar el producto.
  El repositorio no tiene harness React de interacción; una función de transición pura y su contrato
  arquitectónico verifican esa secuencia determinista.
- El hub de sucursal filtra la tarjeta por `catalog.branch.manage`, manteniendo la guarda de ruta y
  la autorización backend como defensa en profundidad.
- Administración corporativa distingue carga, error y reintento para productos y notas, y separa
  edición de la acción confirmada de archivar/reactivar.
- Las pruebas verifican el `kitchen_text` del read model/API KDS, el payload kitchen y eventos de
  auditoría `created`, `updated`, `archived`, `reactivated` y `branch_configured`.
