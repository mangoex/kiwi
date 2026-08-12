# PCO-003 — auditoría de Sol a la implementación de Terra

**Fecha:** 2026-08-11
**Alcance:** ledger append-only de caja, compensaciones, compra cash enlazada y efectivo esperado.
**Estado:** implementación y auditoría técnica local aceptadas; publicación, despliegue y migración
productiva son gates independientes.

## 1. Autoridad y frontera

- Sol definió y auditó PRD, SDD, BDD, TDD, ADR, matriz y handoff de `PCO-003`.
- Terra implementó en la tarea separada `019ff431-e2b7-76f1-badc-316aaf35e512` y recibió
  iteraciones correctivas hasta satisfacer los invariantes.
- Se preservaron PCO-001/002 y los archivos no rastreados ajenos del usuario.
- No se leyó ni modificó la `DATABASE_URL` original. No se usaron Easypanel, datos reales, outbox,
  cierre nuevo, corte, reapertura, reportes ni módulos PCO-004+.

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

Se preparó un build POS, SQLite y credenciales desechables, y se levantó el API local. El navegador
integrado rechazó por política el acceso a las URLs locales/privadas; por tanto, no se declara QA
visual ejecutada ni se fabrican capturas o resultados responsive. Los contratos, prueba Node,
typecheck y build sí fueron ejecutados. Esta limitación es evidencia de entorno, no un fallo funcional
observado ni una autorización para usar producción como sustituto.

## 6. Publicación y siguiente incremento

Commit, PR, CI, merge y push se registran como gates distintos de la aceptación local. Easypanel,
migración productiva y flujo empresarial real requieren autorización posterior. El siguiente paquete
funcional es `PCO-004`: cierre operativo y monitor trazable; no forma parte de esta entrega.
