# TDD - Ajustes de usabilidad en compras y POS

## TDD-TS-128 Relación proveedor-producto y excepción trazable

### TDD-TC-296 Selector por insumo y presentación

La prueba semántica exige `item_name`/`item_sku`/`supplier_name`, agrupación por `item_id` y filtro
normal por proveedor. API verifica que el listado autorizado devuelve etiquetas inequívocas. React
no calcula totales.

### TDD-TC-297 Excepción cerrada por omisión

Preview y creación rechazan presentación ajena sin casilla o motivo y no producen efectos. Con
casilla/motivo aceptan, conservan snapshot doble y cálculo exacto. Confirmación recibe inventario
sin actualizar precio/historial de la presentación ajena. Replay mantiene payload/fingerprint.

## TDD-TS-129 Preferencia visual gobernada

### TDD-TC-298 Persistencia, permiso y sesión

Migración `0073_pos_catalog_appearance` agrega default `true` y bloquea downgrade que perdería un
`false`; PostgreSQL excluye escritores antes del guard. API acepta sólo booleano con
`admin.manage`, audita y la sesión React aplica el valor confirmado sin consultar un gateway
obsoleto. Si existe gateway, un arranque con red combina la preferencia central de la misma sucursal
y un timeout central acotado conserva el bundle sin bloquear el arranque offline. Una prueba
de renovación verifica que un gateway SQLite con tabla `branches` previa agrega la columna antes
del upsert y conserva el valor recibido.

### TDD-TC-299 Alcance visual

Prueba semántica verifica que la condición retira visuales sólo de tarjetas centrales, activa una
clase de texto mayor y deja `getCatalogGroupIcon` incondicional dentro de `pos-sale-menu`. Typecheck,
build y QA en anchos afectados validan integración. El resultado del PUT debe ganar sobre un
snapshot gateway obsoleto mientras la sesión está viva.

## RED esperado

Falla inicialmente porque el editor no muestra nombres de insumo ni excepción, el backend rechaza
toda presentación ajena, la sucursal no persiste apariencia y el POS siempre renderiza visuales.

## Gates focales

```bash
node tests/frontend/test_purchase_workspace.mjs
node tests/frontend/test_pos_catalog_appearance.mjs
python -m pytest apps/api/tests/test_purchase_workspace.py -q
python -m pytest apps/api/tests/test_pos_catalog_appearance.py -q
python -m pytest apps/api/tests/test_pos_catalog_appearance_migration.py -q
python -m pytest apps/api/tests/test_pos_catalog_appearance_offline.py -q
pnpm --filter @restaurantos/admin-web typecheck
pnpm --filter @restaurantos/pos-web typecheck
pnpm --filter @restaurantos/pos-web build
python -m pytest tests/architecture/test_traceability.py -q
git diff --check
```

PostgreSQL es gate activado por migración/persistencia. Si no existe servicio local, queda pendiente
de CI y se reporta como no verificado; no se sustituye con SQLite.
