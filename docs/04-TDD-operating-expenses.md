# TDD — Gastos operativos

## TDD-TS-134 Gastos, caja y estadísticas sin inventario

EXP-001 R3. Implementación y verificación local; resultados exactos y gates de publicación en el plan EXP-001. No extender pruebas de Compras
para simular Gastos: crear fixtures propias sin proveedor/presentación/insumo y reutilizar las de caja.
Pruebas del incremento: `apps/api/tests/test_operating_expenses.py`,
`test_operating_expenses_postgres.py`, `test_operating_expenses_migration.py`,
`tests/contract/test_operating_expenses_contract.py`,
`tests/frontend/test_operating_expenses.mjs` y `tests/browser/test_operating_expenses_e2e.mjs`.

## TDD-TC-316 Catálogo, migración y permisos

SC-599/603. RED de rutas/tablas inexistentes; alta/edición/archivo idempotentes, código único por
organización, snapshot histórico, versión y edición concurrente. Rechazar organización ajena,
concepto archivado y usuario sin permiso; permisos nuevos no se derivan de compras o rol por nombre.
Verificar matriz autorizada y no elevar legacy Administrador corporativo a Dueño. Upgrade/downgrade/
upgrade en SQLite y PostgreSQL; datos históricos intactos, downgrade con historia bloqueado,
sin autoimportar gastos por nombres ni crear catálogos productivos de ejemplo. Catálogo con un
concepto y ningún documento también bloquea downgrade, aunque falte un recibo de comando.

## TDD-TC-317 Documento sin inventario

SC-600. Crear sin proveedores/insumos/presentaciones/almacén configurado, en sucursal válida;
guardado/edición/descarte de borrador no crea movimientos. Validar fecha explícita, total entero
positivo, límites técnicos, impuesto opcional incluido, método cerrado, texto y evidencia acotados.
Rechazar supplier_id/presentation_id/item_id/warehouse_id/recipe_id y campos desconocidos en API.
Capturar conteos y contenido de tablas de inventario/costos/proveedores antes/después de cada comando;
usar además fixture con historia para demostrar que no la modifica. No basta afirmar cero FKs.

## TDD-TC-318 Efectivo y contexto

SC-601/603. Cero/una/varias cajas, preferencia obsoleta, mismo código en otra sucursal, turno ambiguo,
cerrado o reemplazado. Sólo expenses.manage+cash.movement.withdraw ve contexto mínimo, sin
cash.shift.read ni purchases.manage. Compra de referencia no participa. Confirmar gasto por 30000
centavos con esperado 200000 produce 170000; exactamente un EXPENSE withdrawal por total y auditoría,
sin recibo de inventario. Falta de referencia/evidencia, retiro o turno impide confirmar cash,
pero permite guardar draft. Preservar UI de error y rechazar movimiento manual forjado con fuente EXPENSE.

## TDD-TC-319 Otros métodos

SC-602. Parametrizar transfer/card/other sin turno y sin permisos de caja: confirma y aparece en
estadísticas sin movimientos, bancos, inventario ni proveedores. Campos de caja o método credit/
desconocido rechazados. No convertir otros métodos a efectivo ni tratar other como crédito.

## TDD-TC-320 Idempotencia, locks y fallos

SC-604. Crear/editar/confirmar/cancelar con recibos durables: replay mismo actor/body/version/key,
clave incompatible, permiso revocado, timeout antes/después del commit y recarga. Confirmación
doble misma/distinta clave y carreras contra cierre, reapertura, cancelación, edición y archivo de
concepto, con barreras deterministas en PostgreSQL y semántica de escritura SQLite. Una transición
y un retiro como máximo. Inyectar fallo después de movimiento, estado, auditoría y recibo: rollback
total. Verificar orden de locks, no deadlocks persistentes ni transacciones parciales. Intento incierto
mantiene key/body, y fallo de refresco UI no crea nuevo comando. Recuperación GET no asume fallo por
ausencia de recibo; resolve serializa tombstone y bloquea POST tardío con la misma clave.

## TDD-TC-321 Anulación y atribución temporal

SC-605. Cancelar draft sin efectos; confirmado sólo con permiso y motivo. Cash exige devolución
acreditada, permiso de compensación y turno original OPEN; crea depósito exacto con enlace único.
Original cerrado rechaza sin parcialidad. Compensación manual del retiro EXPENSE, del depósito
EXPENSE_CANCELLATION y de descendientes enlazados se rechaza incluso en replay; comprobar que caja,
documento y reportes quedan intactos. Anulación no cash no requiere caja ni ejecuta reembolso bancario. Reintentar o
concurrir anulación no duplica reversa, depósito o auditoría. Replay de confirmación después de anular
o cerrar recupera resultado sin nuevos efectos. Comparar historia inmutable e inventario idéntico.

## TDD-TC-322 Reportes sin doble conteo

SC-606. Fixture combina cash 30000 + transfer 100000 + compras + retiros históricos y reversas:
summary operativo neto 130000 antes de anulaciones, caja sólo -30000; reporte general distingue
fuentes y excluye movimientos EXPENSE enlazados. Anulación en otro día conserva positivo original y
negativo en periodo posterior. Fronteras UTC/local por zona de sucursal, null tax, cursor estable,
filtros ligados y suma de todas las páginas. Scope corporativo versus sucursal y reportes denegados
a operador sin permiso. Regresión `test_pco007_recipe_reports.py`,
`test_branch_reconciliation_reports.py`, `test_audit_money_public_regressions.py` y consumidores
`CorporateReconciliationDashboard.tsx`: jamás restar transferencias del esperado, ni contar retiro
EXPENSE como otro gasto ni clasificar por texto del concepto. Validar contratos/compatibilidad de
fuentes nuevas antes de release; SQL limitado/indexado, agregados no calculados por frontend.

## TDD-TC-323 Recorrido compartido y QA

SC-599..606. API real/BD aislada: crear concepto, capturar draft desde Admin y acceso POS, revisar
efectivo/caja/importe, confirmar, verificar movimiento/estadística, anular según política; repetir
no cash sin caja. No crear insumos/proveedores como prerequisito. Cambiar actor/sucursal con requests
en vuelo no filtra ni reasigna; validar navegación por permisos y teclado/foco en desktop/ancho
reducido con base clara neutral. Mostrar borrador/confirmado/anulado y errores en español.

Gates implementación: pruebas focales RED/GREEN, contratos, lint/mypy Python, typecheck/build,
E2E/QA, migración y carreras PostgreSQL aislado, SQLite del backend, trazabilidad, CI aplicable y
auditoría Sol R3. No se cambia gateway/offline; verificar ausencia de nueva ruta de escritura local
de Gastos. Canary productivo compensable sólo tras autorización explícita, con operación real.
