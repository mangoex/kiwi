# Cierre local RECIPES-UX-001

Fecha: 2026-09-24. Riesgo: R3 por recetas, inventario y costo. Alcance: continuidad de Productos al
editor canónico de recetas; no se modificaron backend, esquema, fórmulas ni autoridad financiera.

## Resultado

- Producto nuevo o existente abre su receta exacta sin abandonar Productos ni repetir la búsqueda.
- El editor conserva versionado, alcance, idempotencia y autoridad Python; bruto y costo cliente son
  vistas previas y no se envían.
- Rendimiento, unidad, filtro de insumos y merma porcentual son visibles. Valores de merma vacíos,
  negativos, exponenciales o fuera de rango bloquean el PUT.
- El éxito permanece abierto para revisión. Error, conflicto o fallo de lectura conservan la captura;
  un baseline desconocido bloquea escritura hasta una relectura confirmada.

## Evidencia local

- Cinco pruebas semánticas focales: verdes (`recipe_product_flow`, master-detail, admin product flow,
  PCO-007 recipe y CapsuleTabs).
- `pnpm --filter @restaurantos/admin-web typecheck`: verde.
- `pnpm --filter @restaurantos/admin-web build`: verde, 1633 módulos transformados.
- `tests/architecture/test_traceability.py`: 8 passed.
- Navegador sintético Chrome en 390, 768 y 1440 px: verde; incluye GET 503 con reintento, merma
  inválida sin PUT, guardado confirmado sin autocierre y PUT 409 que conserva el borrador.
- `git diff --check`: verde.
- Auditoría independiente R3 posterior a correcciones: aprobada sin hallazgos bloqueantes.

## Límites y riesgo residual

- Node local es 20.20.2 y el monorepo declara `>=22`; pnpm emitió advertencia. Vite también conserva
  la advertencia existente por un chunk mayor a 500 kB.
- La suite frontend completa queda para CI conforme a `GOV-TEST-001`. Una ejecución adicional del
  browser retro heredado detectó su aserción preexistente de color neutro en login, fuera de este
  flujo; la prueba focal nueva sí quedó verde y se agregó al job browser de CI.
- PostgreSQL, SQLite y migraciones no se activaron porque no cambiaron persistencia, SQL ni gateway.
- No se ejecutaron CI remoto, commit, push, despliegue, migración ni validación productiva.
