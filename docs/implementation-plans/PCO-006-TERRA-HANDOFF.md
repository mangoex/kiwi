# PCO-006 — handoff mínimo de implementación para Terra

Fecha: 2026-08-15. Riesgo: R3. Autoridad: `PRD-FR-219`, `PRD-NFR-020/021/024`, sección
`38.2.7` del SDD, `BDD-SC-286/287/295/327..334` y `TDD-TS-081`, `TDD-TC-077/080/113..120`.

## Objetivo y límite

Implementar corte final por cajero responsable de un turno cerrado, con cálculo Python exacto,
operaciones asociadas una sola vez, historial inmutable y reapertura exclusivamente compensatoria.
No implementar PCO-007 reportes, PCO-008 offline/outbox, configuración de tolerancia distinta de
cero, impresión/Excel, conciliación bancaria, borrado histórico ni reutilizar el corte legacy.
Producción, `DATABASE_URL`, deploy y `alembic upgrade` productivo quedan fuera.

No crear documentos duplicados. Editar PRD/SDD/BDD/TDD sólo si el código descubre una contradicción
real; cualquier regla nueva se devuelve a Sol antes de implementarla.

## Decisiones cerradas

- El cajero canónico es el actor persistido al abrir el turno; nunca un nombre o ID confiado del UI.
- Un turno legado sin apertura inequívoca no es cortable. No inferir por ventas ni “último usuario”.
- El periodo final es exactamente `[cash_shifts.opened_at, cash_shift_closures.closed_at)`.
- Finalizar exige `OPERATIVELY_CLOSED`, estado `COUNTED`, versión vigente, tolerancia cero y Líder+.
- Esperado y diferencia se calculan en Python con enteros; React no suma ni resta.
- Pagos/movimientos se asocian append-only y cada operación sólo puede pertenecer a un corte.
- Dueño puede solicitar, decidir y compensar; no se inventa separación de cuatro ojos.
- Compensar corrige el reporte, no el ledger, y jamás libera asociaciones.

## Implementación mínima

1. RED focal antes de runtime para TC-113..120; conservar la evidencia RED exacta.
2. Migración `0041_user_cash_cuts` desde `0040_order_corrections`:
   `cash_shifts.cashier_user_id` nullable sólo por compatibilidad legacy; cinco tablas PCO-006,
   checks/FK/índices y unicidad global de asociación. Backfill sólo desde un comando de apertura
   único. Downgrade vacío permitido; con historia PCO-006 bloqueado explícitamente.
3. Modelos/contratos estrictos y `UserCashCutService` en backend Python; controladores HTTP delgados.
4. Endpoints versionados ya enumerados en SDD: create, counted-cash, finalize, list/detail,
   reopen request, approve/reject/compensate. Toda mutación exige `Idempotency-Key`.
5. Locks PostgreSQL y frontera SQLite proporcionada; no afirmar row locking SQLite.
6. Auditoría append-only y métricas `cash_cut_command_total{action,result}` y
   `cash_cut_difference_cents`; redacción conforme a SDD.
7. POS: integrar en administración de caja existente. Sólo turnos cerrados elegibles, captura de
   contado, confirmación, historial/detalle y acciones Dueño. Estados loading/vacío/error/conflicto.
8. Actualizar matriz a `Implementado` únicamente después de GREEN real y reporte de evidencia.

## Pruebas y gates

- Dominio/API focal: fórmula, estados, permisos/scope, esquema estricto, replay/conflicto, rollback,
  historial/redacción, reapertura y compensación.
- Migración SQLite y PostgreSQL: `0040 -> 0041 -> 0040 -> 0041`, backfill inequívoco, downgrade
  bloqueado con cada clase de historia.
- PostgreSQL aislado con `PCO006_TEST_POSTGRES_URL`; validar nombre `pco006_*`, base vacía/aislada y
  no leer `DATABASE_URL`. Carreras finalize/finalize, finalize/movimiento y asociación solapada.
- Contratos JSON Schema, prueba semántica frontend, TypeScript estricto y build.
- QA visual real a 1440x900 y 1000x800 para loading, COUNTED, FINALIZED, conflicto y error.
- Arquitectura/trazabilidad y `git diff --check`.
- La suite completa aplicable se ejecuta una vez en CI del PR; localmente sólo focales salvo
  diagnóstico o CI inconcluso.

## Entrega a Sol

Reportar archivos exactos, RED y GREEN con conteos, PostgreSQL/SQLite por separado, gates omitidos,
riesgos residuales y `git diff --check`. No commit, push, PR, merge ni producción hasta que Sol
termine la auditoría. No tocar archivos ajenos ni rescatar diffs globalmente reformateados.
