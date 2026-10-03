# UIX-USABILITY-001 — plan e implementación

**Riesgo:** R3 por compra/inventario, persistencia, permisos y migración. La receta reutiliza
autoridad R3 existente; la presentación POS aislada sería R1.

## Contratos e invariantes

- Producto presenta directamente su única receta efectiva usando el escritor PCO-007; historia y
  administración masiva no cambian.
- Compra normal sólo usa presentaciones del proveedor. La excepción requiere acción y motivo,
  congela ambos proveedores, no muta catálogo ajeno y conserva cálculos Python `Decimal`.
- Apariencia es booleana por sucursal, default visible, escrita con `admin.manage`; menú superior
  siempre conserva iconos.
- El contrato de negocio offline no se amplía; el snapshot de sucursal incorpora compatibilidad
  aditiva para que gateways existentes acepten la preferencia. No se ejecuta migración productiva
  ni se modifica información histórica.

## Secuencia y tareas

1. Actualizar PRD, SDD/ADR, BDD, TDD y matriz.
2. Crear RED focal para editor directo, compra excepcional y apariencia persistida.
3. Adaptar `RecipeManager` a presentación embebida y retirar el paso intermedio en Productos.
4. Extender contrato/editor/backend de compras, snapshot y confirmación sin tocar catálogo ajeno.
5. Agregar migración, endpoint, sesión, Configuración y render central del POS.
6. Ejecutar pruebas afectadas, typecheck/build, migración SQLite, gate PostgreSQL disponible,
   QA visual, trazabilidad y `git diff --check`.
7. Someter el diff R3 a auditoría Sol independiente y corregir hallazgos antes del cierre.

## Preguntas operativas y señales

- ¿Qué líneas usaron la excepción? Snapshot y conteo en `purchase.created`.
- ¿La excepción alteró catálogo ajeno? Prueba de no cambio en presentación/historial.
- ¿Quién cambió visuales y en qué sucursal? `pos.catalog_appearance.updated`.
- ¿La receta efectiva y su workspace cargaron antes de editar? Estados bloqueantes y pruebas UI.

## Estado

Implementación local cerrada el 2026-10-03. La auditoría Sol R3 independiente terminó sin
hallazgos bloqueantes después de corregir identidad nombre+SKU, refresco con gateway, compatibilidad
SQLite y carrera del downgrade PostgreSQL.

Evidencia local:

- RED focal observado para editor embebido, excepción de compra y apariencia persistida.
- `apps/api/tests/test_purchase_workspace.py`: 53 verdes.
- Apariencia API/migración/offline: 6 verdes; contrato/arquitectura/trazabilidad: 22 verdes.
- Pruebas semánticas afectadas, Ruff, mypy focal con imports opcionales ignorados, typechecks y builds
  Admin/POS verdes; `git diff --check` verde.

Gates pendientes declarados: PostgreSQL focal omitido por ausencia de
`SR_WORKSPACE_TEST_POSTGRES_URL`; Playwright/QA visual real no disponible; CI no ejecutado. No se
autorizó ni realizó commit, push, despliegue, migración o cambio de datos productivos. Node 20
produjo advertencia de engine frente a `>=22.12` y Vite advirtió chunks mayores de 500 kB.
