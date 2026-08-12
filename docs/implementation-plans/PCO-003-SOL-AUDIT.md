# PCO-003 — auditoría de Sol a la implementación de Terra

**Fecha:** 2026-08-12
**Alcance:** ledger append-only de caja, compensaciones, compra cash enlazada y efectivo esperado.
**Estado:** implementación, auditoría técnica, publicación, despliegue y migración productiva
aceptados. El flujo empresarial autenticado permanece como gate operativo explícito; no se declara
ejecutado sin una sesión de un Dueño.

## 1. Autoridad y frontera

- Sol definió y auditó PRD, SDD, BDD, TDD, ADR, matriz y handoff de `PCO-003`.
- Terra implementó en la tarea separada `019ff431-e2b7-76f1-badc-316aaf35e512` y recibió
  iteraciones correctivas hasta satisfacer los invariantes.
- Se preservaron PCO-001/002 y los archivos no rastreados ajenos del usuario.
- Durante la auditoría local no se leyó ni modificó la `DATABASE_URL` original. En el rollout
  productivo autorizado del 2026-08-12 se usó Easypanel exclusivamente para preflight, respaldo,
  migración y verificación de la base original `restaurantos`; `database-prueba` quedó fuera del
  release. No se ejecutaron movimientos de negocio, outbox, cierre nuevo, corte, reapertura,
  reportes ni módulos PCO-004+.

## 2. Resultado implementado

`PCO-003` incorpora:

- migración aditiva `0037_cash_movement_ledger`, command journal idempotente, unicidad de turno
  abierto e índices equivalentes en Alembic y metadata;
- depósitos y retiros manuales append-only con concepto efectivo y snapshot congelado;
- referencia y evidencias obligatorias sin fuga en auditoría ni respuesta de consulta;
- compensación exacta, opuesta, única e inmutable, compatible con reversas legacy;
- compra cash y cancelación enlazadas al mismo ledger y a una caja explícita;
- fórmula autoritativa en Python: fondo + pagos cash confirmados + depósitos - retiros;
- lock/guard compartido entre movimiento, compra, compensación y cierre vigente;
- API canónica de creación, compensación y consulta paginada con alcance de organización/sucursal;
- contratos JSON Schema cerrados y POS mínimo con permisos separados, parser decimal determinista,
  idempotencia estable y mensaje de operación no confirmada ante error de red.

El flujo offline y `pending_sync` permanecen deliberadamente en `PCO-008`.

## 3. Hallazgos de Sol e iteraciones

1. Terra preservó la lectura legacy `cash.shift.read` además del permiso canónico
   `cash.movement.read`, evitando una regresión de perfiles ya publicados.
2. Se corrigió el tipo del submit React a `React.FormEvent<HTMLFormElement>` después de que el
   typecheck productivo detectara el problema.
3. La suite completa reveló siete expectativas de fase ancladas a la head `0036` y a la ausencia de
   rutas PCO-003. Se actualizaron como garantías aditivas: PCO-002 permanece y la head es `0037`.
4. Se verificó que el POS no deriva efectivo esperado ni usa `parseFloat`; el backend Python conserva
   toda autoridad financiera.

## 4. Evidencia automatizada

| Gate | Resultado |
|---|---|
| Dominio, API, contratos, concurrencia y migración dirigidos | `23 passed, 1 skipped` |
| PostgreSQL 16 aislado | `7 passed` |
| Pruebas de fase corregidas | `39 passed` |
| POS TypeScript | verde |
| Prueba Node del formulario POS | verde |
| POS Vite build | `1581 modules transformed`, verde |
| Ruff dirigido | `All checks passed!` |
| Integridad del diff | `git diff --check` limpio |
| Suite completa posterior a correcciones | `267 passed, 7 skipped in 349.44s` |

PostgreSQL se ejecutó sólo en localhost sobre bases `pco003_*`. Las pruebas incluyeron roundtrip
`0036 -> 0037 -> 0036 -> 0037`, downgrade bloqueado con historia, idempotencia y carreras reales de
movimiento contra movimiento, cierre y compra.

## 5. QA visual

La QA local inicial quedó bloqueada porque el navegador integrado rechazó las URLs privadas. En el
rollout autorizado se verificó la URL pública con Chrome headless en `1440x900` y `768x1024`:

- `/pos/cash-movements` sin credencial redirige a `/admin/login` con HTTP 200;
- el formulario de acceso es visible y queda contenido en ambos tamaños;
- no existe overflow horizontal ni error JavaScript de página;
- el escritorio reportó únicamente el 404 no funcional del favicon.

No se ingresaron contraseñas ni se reutilizaron cookies del usuario. Por ello no se declara todavía
el recorrido visual autenticado del ledger, sus permisos, estados ni la creación/compensación real.

## 6. Evidencia de rollout productivo — 2026-08-12

| Gate | Evidencia |
|---|---|
| Fuente publicada | PR #17 integrada en `main`; SHA `9a9f10f2da2e8b189034d760ba4bb5f15e85784f` |
| Base objetivo | `restaurantos` en `kiwi-postgres`; `database-prueba` no participó |
| Respaldo | `pre-pco003-2026-08-12`, finalizado y con acción Restore disponible |
| Preflight | `0036_cash_concepts`; 13 turnos, 2 abiertos, 0 grupos abiertos duplicados, 0 reversas incoherentes, 0 movimientos y 0 conceptos |
| Migración | `0036_cash_concepts -> 0037_cash_movement_ledger`; Alembic confirmó `0037` como `head` antes y después del redeploy |
| Estructura | tabla `cash_movement_commands`, seis columnas nuevas e índices `uq_cash_shifts_open_register`, `uq_cash_movements_compensates_movement` e `ix_cash_movements_branch_shift_created` presentes |
| Conservación | 13 turnos, 2 abiertos, 0 movimientos, 0 conceptos, 0 comandos y 0 duplicados después de migrar |
| Runtime | contenedor nuevo `paperclip_kiwirestaurante.1.khxa3928p1q3ca0o1ngxbrueb` |
| Salud | `/health/ready`: PostgreSQL y Redis `ok`; `/health/version`: commit `9a9f10f2da2e8b189034d760ba4bb5f15e85784f` |
| Observabilidad corregida | `RESTAURANTOS_GIT_COMMIT` estaba anclada a `3957f8e`; se cambió de forma aislada al SHA publicado y se redeplegó |

La migración no creó movimientos ni comandos de caja. El rollback de aplicación conserva el esquema
compatible; el downgrade de esquema continúa bloqueándose en cuanto exista historia PCO-003, y el
respaldo verificado queda como vía de restauración controlada.

## 7. Publicación y siguiente incremento

Commit, PR, CI, merge, despliegue y migración quedaron comprobados como gates distintos de la
aceptación local. Falta únicamente la operación empresarial autenticada y compensada con un Dueño
para completar el Gate 5 funcional. El siguiente paquete funcional sigue siendo `PCO-004`: cierre
operativo y monitor trazable; no forma parte de esta entrega.
