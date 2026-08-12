# PCO-003 — handoff Terra: compensación POS descubierta por canary

## Objetivo

Cerrar exclusivamente `BDD-SC-306` / `TDD-TC-089`: acción Dueño para compensar desde el ledger POS,
proyección backend inequívoca del estado de compensación y convergencia inmediata de ledger/resumen.
No implementar PCO-004+, offline/outbox, cierre/corte, reapertura ni reportes.

## RED obligatorio

1. Contrato/listado: original elegible, original compensado, fila compensación, turno cerrado y fila
   legacy proyectan `compensation_state` y `compensated_by_movement_id` deterministas.
2. Backend: la proyección se calcula contra toda la base autorizada, no sólo la página; no modifica
   historia y no concede permisos. La compensación revalida permiso/turno/unicidad como hoy.
3. Frontend: Dueño ve una única acción `Compensar` sólo en `eligible`; perfiles sin
   `cash.movement.compensate` no la renderizan.
4. Formulario: sólo motivo y evidencia; no existen controles ni propiedades request para monto,
   tipo, concepto, branch, shift, actor o target editable.
5. Idempotencia: error de red conserva la clave/intención; éxito o conflicto explícito la limpia.
6. Convergencia: crear y compensar vuelven a consultar GET `/cash/movements`; muestran ambas filas y
   `current_summary` sin recarga manual.
7. Negativos: doble clic/replay, original ya compensado, turno cerrado, branch ajena y permiso ausente
   no crean otra fila ni muestran éxito falso.

## Implementación mínima esperada

- Extender schema `cash-movement-list-v1` y serialización/listado sin migración.
- Resolver vínculos entrantes en una consulta acotada por los IDs de la página o estrategia
  equivalente sin N+1; `eligible` debe considerar estado real del turno.
- Ampliar tipo `LedgerItem`, UI de estados y formulario de compensación en `CashMovements.tsx`.
- Extraer lógica determinista de estado/idempotencia a `cashMovementForm.ts` cuando facilite prueba
  pura; no calcular dinero en TypeScript.
- Reutilizar `POST /cash/movements/{id}/compensations` y su respuesta autoritativa.
- Refrescar ledger tras ambos POST y exponer el `current_summary` recibido sólo como presentación.

## Gates

- Pruebas Python dirigidas de ledger/API/JSON Schema, SQLite y PostgreSQL aislado cuando aplique.
- Pruebas frontend semánticas de DOM/estado, no sólo búsquedas regex; typecheck y build POS.
- Suite completa afectada, Ruff, trazabilidad y `git diff --check`.
- QA visual local desktop/tablet para vacío, elegible, confirmación, compensado, error y permiso
  negativo. No usar producción ni credenciales reales.
- Sin commit, push, merge, Easypanel ni datos reales. Entregar a Sol diff y evidencia exacta.
