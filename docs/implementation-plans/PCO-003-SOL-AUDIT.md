# PCO-003 — auditoría de Sol a la implementación de Terra

**Fecha:** 2026-08-12
**Alcance:** ledger append-only de caja, compensaciones, compra cash enlazada y efectivo esperado.
**Estado:** implementación, auditoría técnica, publicación, despliegue, migración y canary productivo
autenticado aceptados. `BDD-SC-306` / `TDD-TC-089` quedaron comprobados con efecto neto cero.

## 1. Autoridad y frontera

- Sol definió y auditó PRD, SDD, BDD, TDD, ADR, matriz y handoff de `PCO-003`.
- Terra implementó en la tarea separada `019ff431-e2b7-76f1-badc-316aaf35e512` y recibió
  iteraciones correctivas hasta satisfacer los invariantes.
- Se preservaron PCO-001/002 y los archivos no rastreados ajenos del usuario.
- Durante la auditoría local no se leyó ni modificó la `DATABASE_URL` original. En el rollout
  productivo autorizado del 2026-08-12 se usó Easypanel exclusivamente para preflight, respaldo,
  migración y verificación de la base original `restaurantos`; `database-prueba` quedó fuera del
  release. El canary final ejecutó sólo un retiro QA de 100 centavos y su compensación exacta; no
  ejecutó outbox, cierre nuevo, corte, reapertura, reportes ni módulos PCO-004+.

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

El usuario inició sesión en el navegador integrado. Sol no leyó cookies, almacenamiento de sesión ni
contraseñas. El recorrido autenticado posterior comprobó el ledger, sus estados traducidos, la acción
gobernada y la creación/compensación real descrita en la sección 9.

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

Commit, PR, CI, merge, despliegue, migración y operación empresarial autenticada quedaron comprobados
como gates distintos. PCO-003 completa el Gate 5 funcional. El siguiente paquete funcional sigue
siendo `PCO-004`: cierre operativo y monitor trazable; no forma parte de esta entrega.

## 8. Hallazgo de canary autenticado — 2026-08-12

La sesión productiva autenticada llegó correctamente al ledger de Centro, mostró cero movimientos y
detectó `CAJA-01` cerrada. Antes de escribir historia real, Sol confirmó que el POS desplegado sólo
permite crear depósitos/retiros: no presenta la compensación gobernada que el backend ya soporta y
tampoco refresca el ledger después del POST de creación. El canary se detuvo sin publicar concepto,
abrir turno ni crear movimiento. `BDD-SC-306` y `TDD-TC-089` gobiernan la corrección; PCO-003 no cierra
Gate 5 hasta implementar, auditar, desplegar y repetir el flujo original→compensación con efecto neto
cero.

La iteración Terra posterior implementó la proyección `eligible|compensated|compensation|ineligible`,
la acción POS exclusiva de Dueño, payload cerrado, refresco de ledger/resumen y una máquina de estado
que conserva la clave únicamente durante el mismo intento incierto. Sol rechazó la primera versión
porque Cancelar podía trasladar clave y campos a otra fila; Terra corrigió y Sol integró el resultado
byte por byte. Evidencia local posterior: `268 passed, 8 skipped`, 25 pruebas dirigidas, frontend
semántico, Ruff, trazabilidad `8 passed`, typecheck y build POS con Node 24 (`1581 modules`) verdes.
PostgreSQL aislado no se repitió porque el servidor local anterior ya no estaba disponible; no se usó
producción como sustituto. La publicación posterior quedó en PR #19. Antes del redeploy, Sol detectó
que la UI todavía exponía enums ingleses; Terra implementó traducciones cerradas con fallback neutro,
Sol auditó con Node 24 y PR #20 quedó verde y fusionada.

## 9. Cierre del canary productivo autenticado — 2026-08-12

El primer intento de concepto QA reveló que `datetime-local` se precargaba con componentes UTC y
desplazaba la vigencia siete horas en `America/Mazatlan`. No se forzó el dato ni se creó movimiento:
el concepto `QA_PCO003_CANARY_20260812` quedó archivado con sus tres versiones históricas. Sol añadió
SDD/BDD/TDD y handoff; Terra corrigió la presentación local y conservó una sola conversión a UTC en el
payload. PR #21 pasó Docker, frontend y Python y fue fusionada.

Evidencia final:

| Gate | Evidencia |
|---|---|
| Fuente final | PR #19, #20 y #21 fusionadas; `main` y runtime en `a1c5fcf5e90659aeed0f97508956c52819a9f7e6` |
| CI hotfix final | Docker `6s`, frontend `41s`, Python `2m17s`, todos verdes |
| Salud | `/health/ready`: servicio, PostgreSQL y Redis `ok`; `/health/version`: SHA final exacto |
| Esquema | Alembic `0037_cash_movement_ledger (head)` después del redeploy |
| Turno | Se reutilizó el turno ya `OPEN` de Constitución/`CAJA-01`; no se abrió ni cerró turno QA |
| Concepto final | `QA_PCO003_CANARY_FINAL_20260812`, vigente de inmediato y archivado al terminar |
| Movimiento original | `withdrawal`, 100 centavos, `confirmed`; UI `Retiro` / `Elegible para compensación` |
| Compensación | `deposit`, 100 centavos, `confirmed`, `reversal_of_id` y `compensates_movement_id` iguales al original |
| Efectivo esperado | `$500.00 -> $499.00 -> $500.00`, calculado por backend y actualizado sin recarga manual |
| Journal | Dos comandos completados: creación y compensación |
| Auditoría | Un evento `cash_movement.created` y uno `cash_movement.compensated` |
| UI final | Original `Compensado`, fila opuesta `Compensación`, tipos en español y sin otra acción `Compensar` |

La historia productiva queda append-only por diseño: dos movimientos compensados, dos comandos y sus
auditorías permanecen. Ambos conceptos QA quedaron archivados y no aparecen en operaciones nuevas.
