# TDD - Selección previa de opción por categoría

## TDD-TS-075 POS-CAT-004 catálogo y flujo de opción

Casos:

- `0034_category_option_selection` crea FKs, checks, unicidades e índices y conserva una sola
  cabeza Alembic; el ciclo upgrade/downgrade/upgrade corre sobre SQLite y PostgreSQL conforme a la
  infraestructura disponible.
- el adaptador usado por `alembic/env.py` escapa `%` sólo para `Config.set_main_option`, recupera
  exactamente el URL lógico para el driver y cubre socket/credenciales percent-encoded y URL sin `%`;
  esta evidencia implementa `BDD-SC-264`, no el escenario POS `BDD-SC-261`;
- la capa Python rechaza valor de otro grupo, producto de otra categoría u organización y duplicado;
  activar una configuración incompleta no deja escritura parcial y registra auditoría de cada cambio;
- `/categories?branch_id=` y `/catalog/products?branch_id=` comparten elegibilidad por sucursal,
  precio y disponibilidad, proyectan `selection` nullable y fallan cerrados para productos sin
  asignación; las categorías sin grupo siguen compatibles;
- los endpoints corporativos requieren `catalog.manage`, POS requiere `pos.operate`, y el contrato
  JSON Schema versionado valida tipos, const, mínimos, propiedades adicionales y variantes nulas y
  activas de `selection_group`/`selection`, con fixtures negativos controlados;
- `tests/frontend/test_pos_category_options.mjs` compila `categoryOptionFlow.ts` con `tsc` y prueba
  orden, filtro categoría/opción/búsqueda, reset, obsolescencia y una transición consumida por POS
  que preserva carrito y búsqueda mientras limpia únicamente personalización transitoria;
- `tests/frontend/test_admin_category_options.mjs` prueba hidratación del mismo grupo actualizado,
  cambio de categoría y estado de edición explícita de valores; las pruebas API verifican update de
  código/nombre, relaciones cruzadas, permisos y auditoría de crear/actualizar/reasignar;
- las pruebas de arquitectura comprueban documentación, matriz, rutas corporativas, roles, clases y
  orden estático de componentes, no sustituyen la evidencia visual. La evidencia visual local del
  flujo completo se registra separadamente; se ejecutan regresiones POS-UX-001, POS-VAR-001/002/003
  y POS-ORD-002.
- cobertura devuelve cada producto relevante con su asignación actual o `null`; la reasignación es
  explícita, hidratar otra categoría no filtra valores de la anterior y un usuario sólo
  `catalog.manage` puede cargar la administración sin `pos.operate`.
- no se asigna un valor inactivo/archivado y no se puede desactivar/archivar un valor que rompería
  un grupo activo; los errores de código, estado, orden y duplicado son de dominio estables y no
  dejan mutaciones parciales.
- la carga POS tiene Reintentar testeable y un selector sin valores visibles no se representa como
  cuadrícula vacía silenciosa.

## TDD-TC-071 Venta de producto concreto después de selector

Given Ensaladas tiene Tamaño y el producto ENSALADA CHICA asignado a Chica con precio vigente
When el Cajero elige Chica y crea el pedido con turno abierto
Then sólo `product_id` concreto llega a la operación
And el backend ignora precio o label manipulados, congela snapshot y calcula el total en centavos.

## Comandos focalizados

```bash
python3 -m pytest tests/architecture/test_pos_category_options.py
pnpm test:pos-category-options
(cd apps/api && python3 -m alembic heads -v)
```
