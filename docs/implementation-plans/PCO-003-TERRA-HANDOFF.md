# PCO-003 — paquete de implementación para Terra

**Preparó:** Sol
**Implementa y prueba:** Terra medium
**Audita y acepta:** Sol
**Fecha:** 2026-08-11
**Estado:** implementación Terra y auditoría técnica Sol aceptadas localmente; publicación separada
**Base obligatoria:** `origin/main` en `e30785b` o descendiente exacto
**Rama objetivo:** `codex/pco-003-cash-ledger`

## 1. Objetivo verificable

Implementar el ledger único de caja para depósitos y retiros manuales, compensaciones inmutables,
compras cash enlazadas y efectivo esperado determinista en Python. El POS debe permitir únicamente las
acciones autorizadas, consumir conceptos efectivos de backend y no declarar éxito si la red falla.

PCO-003 no implementa cierre operativo nuevo, corte, reapertura, monitor/reportes, outbox/inbox ni
datos productivos. SQLite se prueba como base del API/migración; el flujo offline pertenece a PCO-008.

## 2. Autoridad y trazabilidad

| Elemento | Fuente canónica |
|---|---|
| Producto | `PRD-FR-216`, `PRD-NFR-020/021/024` |
| Autorización | `SDD-ADR-015`, SDD §38.1 y permisos PCO-001 |
| Ledger/compatibilidad | SDD §38.2.2 y `SDD-ADR-025` |
| Comportamiento | `BDD-SC-278..280`, `294`, `302..305`; catálogo `296/301` preservado |
| Pruebas | `TDD-TS-078`, `TDD-TC-074/079/085..088` |
| Estado | fila `PRD-FR-216` de la matriz, `Disenado` hasta auditoría verde |

La instrucción del Dueño autoriza implementación, iteraciones Sol/Terra y publicación posterior a
auditoría; no autoriza Easypanel, migración productiva ni flujo con datos reales.

## 3. Alcance obligatorio

1. Extender `cash_movements` aditivamente y preservar todas las filas legacy:
   - `concept_id`, `concept_version_id`, `concept_snapshot` JSON;
   - `reference`, `evidence_refs` JSON;
   - `compensates_movement_id` y relación compatible con `reversal_of_id`;
   - ningún campo nuevo obligatorio para historia legacy.
2. Crear `cash_movement_commands`:
   - unicidad `(organization_id, idempotency_key)`;
   - actor, `create|compensate`, objetivo, hash canónico, resultado estable, estado y UTC;
   - replay exacto antes de revalidar estado mutable; misma key/identidad distinta = conflicto.
3. Garantizar un solo turno `OPEN` por `(branch_id, register_code)`:
   - preflight de migración que aborta ante duplicidad;
   - índice parcial único SQLite/PostgreSQL;
   - runtime detecta ambigüedad y devuelve `cash_shift_ambiguous`, nunca `.first()` silencioso.
4. Crear servicio Python de movimiento manual:
   - actor y alcance canónicos;
   - Cajero puede `withdrawal`; Cajero jefe+ también `deposit` conforme a permisos persistidos;
   - turno OPEN y caja explícita;
   - importe entero positivo, rechazando `bool`;
   - concepto activo/efectivo/tipo compatible y snapshot inmutable;
   - referencia obligatoria recortada 1..600;
   - 1..10 `evidence_refs`, strings opacos recortados 1..600;
   - no aceptar campos derivados o propiedades adicionales.
   - `reason_code` usa código técnico de hasta 48 caracteres; el código de concepto completo vive en
     snapshot y no se trunca silenciosamente.
5. Crear compensación Dueño:
   - sólo `cash.movement.compensate`;
   - mismo importe positivo, tipo opuesto, turno/sucursal original OPEN;
   - motivo 1..600 y evidencia obligatoria;
   - no compensar compensación, fila ajena/no confirmada o ya revertida por cualquiera de las dos
     relaciones; una carrera confirma exactamente una.
6. Unificar compra cash:
   - confirmación recibe `register_id` explícito cuando `paid_from_cash=true`;
   - nuevas filas canónicas usan `withdrawal`, `source_type=PURCHASE`, `source_id=document_id`;
   - cancelación durante el turno original OPEN crea un `deposit` exacto enlazado;
   - reintentos no duplican; filas legacy `purchase/cash_reversal` permanecen y se proyectan.
   - la cancelación interna conserva `purchases.manage`; no requiere permiso Dueño de compensación.
   - `reason_code/reason` NOT NULL se derivan del concepto en manual y de código/motivo estable en
     compensaciones; nunca quedan vacíos.
7. Efectivo esperado autoritativo:
   - `opening_cash_cents + confirmed cash payments + deposit - withdrawal`;
   - `cash_reversal` legacy equivale a depósito; estados distintos de `confirmed` se excluyen de forma
     explícita y observable, sin reescribirlos;
   - tipos confirmados desconocidos fallan `cash_ledger_unknown_type` en vez de omitirse;
   - compras/cancelaciones sólo participan por sus movimientos, nunca por un término adicional.
8. API/contratos/consulta:
   - `POST /api/v1/cash/movements`;
   - `POST /api/v1/cash/movements/{id}/compensations`;
   - `GET /api/v1/cash/movements` con branch, register, shift, tipo, UTC, cursor y límite acotado;
   - respuestas incluyen snapshot, `summary_at_commit` y, cuando aplique, `current_summary`, pero no
     confunden el snapshot de replay con el total actual ni exponen hashes/keys;
   - ningún error SQL/repr/traceback en la respuesta.
9. POS:
   - ruta/panel “Movimientos de caja” visible si tiene read/withdraw/deposit;
   - formulario por tipo permitido, conceptos efectivos de backend, importe/ref/evidencias;
   - conversión decimal a centavos con parser determinista, nunca `parseFloat`;
   - Idempotency-Key estable mientras la intención sea incierta y nueva sólo al éxito/conflicto final;
   - estados carga/vacío/error/éxito y mensaje de red “Operación no confirmada”; sin `pending_sync`.
10. Auditoría/logs:
    - `cash_movement.created`, `cash_movement.compensated` y rechazos sensibles;
    - auditoría sin referencia, evidencia, key ni hash; logs sin body/PII/secreto.
11. Serialización de turno:
    - movimiento manual, compra, compensación y cierre vigente comparten lock/guard por turno;
    - carrera cierre-versus-movimiento deja uno antes del resumen o rechaza el movimiento porque el
      turno ya no está OPEN; nunca permite una salida confirmada ausente del esperado final.

## 4. Contratos HTTP

`POST /api/v1/cash/movements`, `Idempotency-Key` obligatorio:

```json
{
  "branch_id": "uuid",
  "register_id": "CAJA-01",
  "movement_type": "withdrawal",
  "concept_id": "uuid",
  "amount_cents": 2000,
  "reference": "FOLIO-123",
  "evidence_refs": ["evidence://ticket/abc"]
}
```

No admite `actor_user_id`, `organization_id`, `cash_shift_id`, `concept_snapshot`, signo,
`expected_cash_cents`, `difference_cents`, `source_type` ni `source_id`.

`POST /api/v1/cash/movements/{id}/compensations`:

```json
{
  "reason": "Registro capturado por error",
  "evidence_refs": ["evidence://authorization/abc"]
}
```

Tipo, importe, sucursal, turno, concepto y target se derivan del original. Ambos comandos devuelven
`movement` y `summary` con componentes autoritativos. Crear: HTTP 200/201 según convención actual;
replay devuelve el mismo cuerpo. Consulta devuelve `{items, next_cursor}` y limita 1..100.

## 5. Errores estables

`actor_required`, `permission_denied`, `branch_scope_denied`, `idempotency_key_required`,
`idempotency_conflict`, `cash_shift_not_open`, `cash_shift_ambiguous`, `cash_concept_invalid`,
`cash_reference_required`, `cash_evidence_required`, `cash_movement_invalid`,
`cash_movement_not_found`, `cash_movement_already_compensated`, `cash_compensation_invalid` y
`cash_ledger_unknown_type`. Todos revierten primero cualquier trabajo parcial; API no filtra SQL.

## 6. Esquemas compartidos mínimos

- `cash-movement-command-v1.schema.json`
- `cash-movement-response-v1.schema.json`
- `cash-movement-list-v1.schema.json`
- `cash-compensation-command-v1.schema.json`

Draft 2020-12, `additionalProperties:false`, centavos integer `minimum:1`, enums exactos, límites de
strings/arreglos y timestamps RFC3339. Pruebas validan respuestas reales y negativos/bool/campos extra.

## 7. Migración `0037_cash_movement_ledger`

- Parent exacto `0036_cash_concepts`; una sola head.
- Preflight de turnos OPEN duplicados y relaciones legacy incoherentes antes de DDL dependiente.
- Columnas nullable, tabla de comandos e índices únicos/parciales necesarios.
- Declarar constraints/índices equivalentes en metadata y migración; verificarlos por reflexión, porque
  `metadata.create_all` no prueba por sí solo la revisión Alembic.
- No sembrar conceptos, no actualizar tipos/source/reversal legacy, no borrar datos.
- Downgrade a `0036` sólo si no hay comandos ni filas usando campos PCO-003; en otro caso:
  `Safe downgrade blocked: cash movement ledger history exists`.
- SQLite y PostgreSQL: `0036 -> 0037 -> 0036 -> 0037`, historia legacy y huella idénticas.
- Rollback de aplicación a una versión que ignore depósitos queda prohibido tras primera escritura;
  detener comandos nuevos y mantener lector PCO-003 o restaurar snapshot en mantenimiento.

## 8. Matriz RED → GREEN obligatoria

1. Arquitectura detecta rutas/contratos/migración ausentes y head anterior.
2. Migración y models exponen campos/tablas/índices exactos.
3. Retiro Cajero y depósito Cajero jefe pasan; negativos de permiso/branch pasan.
4. Turno inexistente/duplicado/cerrado falla sin escritura.
5. Importe cero/negativo/bool y campos derivados/extra fallan.
6. Concepto futuro/archivado/incompatible falla; snapshot efectivo queda congelado.
7. Referencia/evidencia límites, normalización y no fuga en auditoría/logs.
8. Replay idéntico produce una fila; cambio de actor/cualquier campo conflictúa.
9. Dos sesiones SQLite y dos PostgreSQL no duplican movimiento ni exponen excepción cruda.
10. Compensación exacta/opuesta/única; doble relación legacy/nueva bloqueada.
10a. Carrera cierre-versus-movimiento y cierre-versus-compra es determinista y no deja resumen parcial.
11. Fórmula `10000 + 5000 + 1000 - 2000 - 3000 = 11000`.
12. Tras compensar compra por `deposit 3000`, resultado `14000`, una vez cada fila.
13. Confirmar/cancelar compra con caja explícita es idempotente y conserva inventario transaccional.
14. Consulta filtra alcance/tipo/fechas, cursor estable y no cruza organización.
15. JSON Schema acepta respuestas reales y rechaza extras/bool/formatos inválidos.
16. POS oculta acciones sin permiso; backend vuelve a denegar llamada directa.
17. Parser TypeScript exacto acepta `0.01`, `10`, `10.50`; rechaza exponentes, negativos, más de dos
    decimales y overflow; Python sigue siendo autoridad.
18. Timeout/red conserva key y muestra no confirmado; no crea outbox/pending_sync.
19. Regresión PCO-001/002, compras, pagos, turnos, inventario y contratos completa verde.
20. SQLite/PostgreSQL, Ruff, typecheck, build, test frontend, QA visual y `git diff --check` verdes.

## 9. Orden obligatorio para Terra

1. Confirmar cwd/worktree, base `origin/main`, rama y no rastreados; preservarlos.
2. Leer `AGENTS.md`, `README`, PRD/SDD/BDD/TDD/matriz/ADR y este handoff.
3. Ejecutar baseline y añadir pruebas RED antes del código; conservar salida exacta.
4. Implementar migración/modelos, dominio Python, API/contratos y POS en ese orden.
5. No tocar PCO-004+, gateway/outbox, cierre/corte/reapertura/reportes.
6. Ejecutar SQLite y PostgreSQL aislado; PostgreSQL sólo localhost/base `pco003_*`, jamás DATABASE_URL.
7. Hacer QA funcional/visual con credenciales/SQLite efímeras y eliminarlas al terminar.
8. Actualizar matriz a `Implementado` sólo si todos los gates aplicables fueron ejecutados.
9. Entregar evidencia exacta a Sol; no commit, push, merge, deploy ni producción.

## 10. DoD de entrega a Sol

- archivos modificados y exclusiones preservadas;
- RED inicial y GREEN final con conteos/comandos;
- trazabilidad exacta FR/ADR/SC/TC;
- round-trip SQLite y PostgreSQL + huella legacy;
- prueba de concurrencia real y ausencia de error SQL crudo;
- pruebas de permisos, idempotencia, compensación, compra y fórmula;
- contratos y pruebas con respuestas reales;
- POS test/typecheck/build y QA visual desktop/reducido;
- auditoría/logs sin datos sensibles;
- suite completa, Ruff y `git diff --check`;
- riesgos/gates no ejecutados y confirmación de cero producción/publicación.

Sol repetirá los gates, inspeccionará cada invariante y devolverá correcciones a Terra hasta aceptar.
