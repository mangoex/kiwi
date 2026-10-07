# MODIFIER-UX-001 — edición y prueba clara de modificadores

**Riesgo:** R3. El cambio es administrativo y no altera fórmulas, pero habilita copia y edición de
configuraciones que contienen recargos y efectos de inventario. Requiere evidencia dirigida,
trazabilidad y auditoría independiente antes de cierre.

## Objetivo y criterios de terminado

El administrador encuentra y edita los grupos antes de cualquier resultado auxiliar, puede cargar
el catálogo de origen para copiar y sólo solicita una vista previa cuando su selección es válida. La
historia termina cuando:

- la pestaña se reconoce como **Modificadores / Producto compuesto** y el editor aparece antes que
  preview y copia, incluso en productos sin grupos;
- la copia usa `/catalog/products`, presenta fallos y permanece deshabilitada sin catálogo u origen;
- el preview espera una acción explícita, recalcula una vez por acción y respeta mínimos y máximos
  antes de llamar al backend;
- alcanzar el máximo deshabilita únicamente opciones aún no seleccionadas del mismo grupo;
- el resultado muestra nombres de insumo, totales exactos recibidos y procedencia Python;
- `included_selections`, centavos, consumo, permisos, versión, idempotencia y snapshots conservan su
  implementación canónica sin duplicarse en React;
- BDD-SC-591 y TDD-TC-308 quedan verdes con pruebas focales, QA de navegador y revisión R3.

## Dependencias e invariantes

- Reutilizar `GET /catalog/products`; no crear rutas ni fuentes de catálogo paralelas.
- Mantener `GET/PUT /products/{id}/modifier-configuration` y sus versiones/idempotency keys.
- Mantener `POST /products/{id}/modifier-configuration/selection-preview` y `_price_order_line` como
  única fuente de precio, incluidos, receta y consumo.
- Usar `item_name` ya presente en el snapshot y `item_id` sólo como fallback; no añadir consultas N+1.
- No cambiar modelos, Alembic, PostgreSQL/SQLite, contratos offline, POS, KDS ni dependencias npm.
- Preservar borradores ante error y exigir confirmación antes de reemplazar por copia.

## Actividades

1. Añadir RED semántico y de navegador para ruta canónica, orden, cardinalidad y nombres.
2. Corregir la consulta del catálogo de copia y exponer carga/error sin habilitar comandos.
3. Reordenar el editor antes de las herramientas auxiliares.
4. Hacer explícita la vista previa, impedir solicitudes inválidas y bloquear exceso por grupo.
5. Presentar MXN mediante conversión exacta existente y nombres de insumo del DTO Python.
6. Ejecutar pruebas frontend/API focales, typecheck, build, trazabilidad, QA visual, diff check y
   auditoría independiente R3.

## Pruebas previstas

- `tests/frontend/test_admin_modifier_management.mjs`: contrato semántico de dependencias y orden.
- `tests/browser/test_compound_product_admin.mjs`: creación, copia visible, precondiciones, cálculo y
  nombres en un navegador real.
- `apps/api/tests/test_platform_api.py`: preview con fuente/huella, centavos e insumos nombrados.
- `tests/architecture/test_traceability.py`: IDs y relaciones PRD/BDD/TDD.

## Gates fuera del paquete local

CI, despliegue, migración de datos y canary productivo se mantienen separados. No se ejecutará una
suite local completa porque el cambio está acotado y CI ya contiene el recorrido de navegador; sí se
ejecutarán todos los gates focales que prueban esta superficie.

## Evidencia local y refutación R3

La fase RED falló en `test_admin_modifier_management.mjs` porque el editor aparecía después del
preview. Tras la implementación quedaron verdes la prueba semántica de modificadores y sus pruebas
adyacentes, typecheck de Admin y UI compartida, build de Admin, `9` pruebas de trazabilidad, Ruff del
focal API, el caso API de configuración/preview (`1 passed`, `89 deselected`) y el recorrido Chrome de
creación, guardado, máximo, preview, recálculo, catálogo disponible y catálogo fallido.

**Afirmación:** React no adquiere autoridad sobre recargos, incluidos ni consumo. **Evidencia:** sólo
convierte centavos de respuesta con `centsToMxn`; la prueba API obtiene `source=python`, huella, total
de `20000`, adicional de `1000` e insumos nombrados desde `_price_order_line`. **Intento de
refutación:** se configuraron incluidos y cantidad de línea junto con un recargo, y se compararon los
centavos exactos. **Resultado:** la autoridad permanece en Python. **Riesgo residual:** no se probó
contra datos productivos.

**Afirmación:** la UI no dispara previews inevitablemente inválidos ni excede el máximo. **Evidencia:**
Chrome registró cero solicitudes con el grupo obligatorio incompleto, deshabilitó la segunda opción
al alcanzar máximo uno y emitió exactamente una solicitud por acción explícita. **Intento de
refutación:** se repitió el cálculo sin cambiar selección y se confirmó una segunda solicitud Python,
sin reutilizar silenciosamente el resultado anterior. **Resultado:** precondición y recálculo
correctos. **Riesgo residual:** una edición concurrente del catálogo aún puede invalidar la selección;
el backend permanece autoritativo y su rechazo se presenta sin guardar.

**Afirmación:** la copia falla cerrada cuando su dependencia no está disponible. **Evidencia:** el
recorrido devolvió `503` en la lectura específica de `/catalog/products`; selector y confirmación
quedaron deshabilitados para una intención nueva. **Intento de refutación:** la auditoría independiente
restauró el caso de una respuesta perdida y detectó que el mismo `503` bloqueaba también el replay;
la regresión ahora crea el snapshot mediante `401` y reautenticación real del mismo actor, excluye
candidatos de sucursal y confirma que **Recuperar copia** envía exactamente el body y la clave
idempotente congelados aunque falle el catálogo; el mismo `503` se prueba por separado sin snapshot
y no emite ningún comando nuevo.
**Resultado:** las copias nuevas fallan cerradas sin catálogo, mientras la reconciliación incierta no
depende de esa lectura auxiliar. **Riesgo residual:** no se ejecutó una copia real contra PostgreSQL
porque no cambió el comando, locks, versión ni idempotencia existentes.

CI, PostgreSQL concurrente, despliegue, migración, canary y comportamiento productivo permanecen sin
verificar y no se presentan como aprobados. `git diff --check` quedó verde y el trabajo local ajeno no
fue modificado.
