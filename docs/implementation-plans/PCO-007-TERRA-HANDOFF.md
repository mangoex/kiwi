# PCO-007 — handoff mínimo de implementación para Terra

Fecha: 2026-08-15. Riesgo: R3. Autoridad: `PRD-FR-220`, `PRD-NFR-002/016/018/020/021/023`,
SDD `38.2.8`, `BDD-SC-275/276/288/297/335..342` y `TDD-TS-082`,
`TDD-TC-078/121..128`.

## Objetivo y límite

Completar las capacidades faltantes del paso 7: Supervisor+ versiona recetas dentro de alcance,
Dueño administra receta corporativa, Supervisor+ consulta venta histórica por insumo y
Administrador/Dueño consulta gastos canónicos. Reutilizar el monitor de ventas PCO-004 y los
snapshots existentes; no reconstruirlo.

No implementar PCO-008 offline/outbox, exportación Excel, impresión, contabilidad general, CFDI,
reporte de merma nuevo, inventario nuevo, edición de ventas, configuración de día distinta a
00:00–23:59 local ni fórmulas en TypeScript. Producción, deploy, datos reales,
`RESTAURANTOS_DATABASE_URL`, `DATABASE_URL` y Alembic productivo quedan fuera.

No duplicar PRD/SDD/BDD/TDD. Si el código revela una contradicción o exige otra regla de negocio,
detener esa parte y devolverla a Sol; no elegirla silenciosamente.

## Contratos cerrados

- Receta: `recipes.manage` + actor + alcance backend. Supervisor/Administrador sólo sucursal
  asignada; `branch_id=NULL` exige authority grant organizacional real. Dueño puede corporativo o
  sucursal propia.
- `PUT /products/{id}/recipe` siempre crea versión; exige `Idempotency-Key` y
  `expected_active_recipe_id`. Rechaza versión, bruto, costo, estado, actor y organización cliente.
- Python usa `Decimal`, bloquea producto/receta, conserva versión anterior y registra command/audit.
- Venta por insumos parte de ventas confirmadas + snapshots de líneas/consumo; nunca receta vigente.
- Unidad incompatible se separa e identifica como incompleta; no se mezcla ni se sustituye por cero.
- Corrección PCO-005B se registra como delta en `applied_at`; no mueve la venta original.
- Compra y retiro cash enlazado forman un solo gasto `purchase`; cancelaciones/compensaciones son
  eventos inversos, no borrado. No inferir impuestos.
- Periodos son UTC semiabiertos; perfil de sucursal envía branch explícita y Dueño puede consolidar
  sólo su organización. Cursor y límites son estrictos.
- React presenta DTO y estados; no suma cantidades, impuestos, gastos ni deltas.

## Implementación mínima

1. Escribir RED focal para TC-121..128 y conservar salida exacta antes del runtime.
2. Migración `0042_recipe_reports` desde `0041_user_cash_cuts`: tabla
   `recipe_version_commands` con hash/respuesta/actor/objetivo y unicidad organización+key; índices
   de reportes sobre compras, movimientos y snapshots. Downgrade vacío; con commands falla cerrado.
3. Modelos Pydantic estrictos para versión de receta y queries/respuestas de reportes. Controladores
   HTTP delgados.
4. Refactor localizado de receta: reemplazar `catalog.manage`, resolver alcance, lock/concurrencia,
   expected version, idempotencia, auditoría y métricas. GET autenticado devuelve receta efectiva y
   procedencia.
5. `ReportingProjectionService` implementa `ingredient_sales` y `expenses` con `Decimal`, cursores
   ligados y DTO redactado. Evitar N+1; consultar lotes acotados.
6. Endpoints `GET /reports/ingredient-sales` y `GET /reports/expenses`; permisos y scope negativos
   son obligatorios.
7. POS agrega una sola superficie de reportes con pestañas por permiso. Admin enlaza a esa superficie
   para no duplicar frontend. Productos/RecipeManager muestran sólo capacidades permitidas, envían
   sucursal/expected/idempotency y ofrecen alcance corporativo sólo cuando la sesión proyecta el
   authority grant; backend sigue siendo autoridad.
8. Logs/métricas redactados. Actualizar matriz a `Implementado` sólo tras GREEN real y generar un
   reporte de evidencia corto sin repetir especificaciones.

## Gates proporcionales

- Dominio/API SQLite: permisos, scope, schema estricto, Decimal, snapshots, correcciones, gasto,
  cursores, replay/conflicto, rollback y redacción.
- Migración SQLite y PostgreSQL: `0041 -> 0042 -> 0041 -> 0042`, una head y bloqueo con history.
- PostgreSQL aislado: sólo `PCO007_TEST_POSTGRES_URL`; validar nombre `pco007_*`, host/base seguros,
  carrera recipe/recipe, unicidad e índices con `EXPLAIN`. Nunca leer variables genéricas.
- Frontend semántico: permisos, estados y ausencia de fórmulas; TypeScript estricto y builds de POS y
  Admin.
- QA visual real: 1440x900 y 1000x800 para receta, reporte vacío, datos, incompleto y error.
- Arquitectura/trazabilidad y `git diff --check`.
- Suite completa aplicable una vez en CI del PR. Localmente ejecutar focales; ampliar sólo por fallo
  diagnóstico o CI inconcluso.

## Entrega a Sol

Trabajar sobre el worktree/branch que Sol indique. Reportar archivos exactos, evidencia RED/GREEN,
conteos, PostgreSQL/SQLite separados, visual QA, gates omitidos y riesgos residuales. No usar
subagentes. No commit, push, PR, merge ni producción hasta la auditoría Sol. No tocar trabajo ajeno,
no reformatear archivos completos y no rescatar diffs de otras ramas.
