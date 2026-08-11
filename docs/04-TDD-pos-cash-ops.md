# TDD — POS-CASH-OPS-001 estrategia de verificación

**Estado:** PCO-001 ejecuta autorización, bootstrap/transición y migración SQLite de partes de `TDD-TS-077`,
`TDD-TC-073`, `TDD-TS-084` y `TDD-TS-087`: semillas/proyección, branch `NULL`, escalación Dueño,
preservación aditiva, bootstrap/transición y downgrade controlado. `TDD-TS-085` permanece definido; ningún caso de
movimientos, cortes, reapertura, reportes, frontend/E2E o PostgreSQL se considera ejecutado por esa
evidencia.

## TDD-TS-077 Autorización y perfiles acumulativos

Dominio y API comprueban herencia positiva/negativa proyectada por permisos, actor ausente, rol visible
alterado, branch `NULL` legacy, sucursal u organización ajena, escalación a Dueño y preservación de
especialidades. PCO-001 no ejecuta flujos futuros de movimientos/cortes/reportes ni frontend/E2E.

## TDD-TC-073 Ningún perfil inferior escala por UI o payload

Given un Cajero y un payload que nombra a Dueño o cambia branch_id
When llama un comando de corte, receta, reporte o caja superior
Then Python rechaza por permiso o alcance y audita la denegación sin mutación.

## TDD-TS-078 Ledger de depósitos, retiros y efectivo esperado

Pruebas Python con centavos y `Decimal` cubren concepto, turno abierto, referencia/evidencia, idempotencia igual/distinta, compensación, fórmula de efectivo esperado y compra cash enlazada. Integración PostgreSQL/SQLite comprueba índices únicos, concurrencia y auditoría. El contrato prueba que el navegador no puede fijar esperado ni diferencia.

## TDD-TC-074 Reintento no duplica efectivo esperado

Given fondo, pago cash y retiro con una idempotency key
When el comando se reintenta y después se intenta con payload distinto
Then el primer reintento devuelve el original y el segundo devuelve idempotency_conflict.

## TDD-TS-079 Cuentas, detalle histórico y solicitud de reapertura

API/contrato cubre filtros, cursor, folio/cliente, alcance, snapshots y solicitud sin mutación. Seguridad
prueba que pagado/cerrado/producción iniciada no se enmienda, solicitud de Cajero jefe+ y autorización
de Dueño cuando PCO-005 implemente las rutas. E2E cubre lista, detalle y motivo visible.

## TDD-TC-075 Reapertura no altera un pedido no elegible

Given pedido pagado con producción iniciada y una solicitud válida
When se registra solicitud y se intenta aplicarla
Then sólo existe solicitud auditable y pago, reservas, consumo, corte y versión permanecen iguales.

## TDD-TS-080 Turno operativo y monitor de ventas

Dominio/API cubre `OPEN -> CLOSING -> OPERATIVELY_CLOSED`, actor y resumen; verifica que cierre no cree corte ni acepte contado cero fabricado. Reportes cubre filtros, familias, servicio, impuestos, cortesías, conteos y drill-down. E2E/visual cubre español, responsive, carga/error y rutas protegidas.

## TDD-TC-076 Cierre operativo conserva corte pendiente

Given turno abierto con efectivo esperado distinto de cero
When Cajero jefe lo cierra operativamente
Then no se crea user_cash_cut ni diferencia ficticia y el resumen conserva sus operaciones.

## TDD-TS-081 Corte por usuario, exactitud y concurrencia

Dominio cubre tupla de alcance, operaciones incluidas una sola vez, contado/esperado/diferencia en centavos, reporte inmutable y compensación propuesta. Integración PostgreSQL y SQLite cubre lock, unicidad, solicitudes concurrentes, reintentos y rollback. E2E cubre captura real de contado.

## TDD-TC-077 Dos cortes concurrentes no duplican operaciones

Given dos transacciones para el mismo cajero, caja, turno y periodo
When ambas finalizan
Then una confirma y la otra falla de forma determinista sin segunda asociación de operaciones.

## TDD-TS-082 Venta por insumos y reportes con historia congelada

Unitarias Python cubren agregación `Decimal`, unidades, periodos, recetas/snapshots distintos, líneas compensadas y datos incompletos fail-closed. API cubre alcance Supervisor/Administrador/Dueño. El contrato impide que TypeScript calcule fórmulas.

## TDD-TC-078 Receta actual no reescribe venta histórica

Given una línea aceptada con snapshot de receta versión uno
When se publica receta versión dos y se consulta el periodo anterior
Then el reporte usa sólo versión uno y expone la procedencia.

## TDD-TC-079 Compra cash y compensación no duplican esperado

Given fondo 10000, pago 5000, depósito 1000, retiro 2000 y compra cash WITHDRAWAL 3000
When se calcula esperado y después se compensa la compra con DEPOSIT 3000
Then los resultados son 11000 y 14000 centavos y cada movimiento participa exactamente una vez.

## TDD-TC-080 Corte parcialmente solapado rechaza operación ya asociada

Given un corte FINALIZED que contiene una operación del turno uno
When el primer corte se reabre/compensa por una política futura y se finaliza otro corte parcialmente solapado que intenta asociarla
Then falla cash_cut_already_finalized y un corte del turno dos no puede usarla.

## TDD-TC-081 Invariante de grant organizacional y mapeo append-only

SQLite prueba dos filas `reversed` históricas para el mismo usuario/perfil y rechaza dos
`pending|mapped` activos. Dominio prueba que `admin.manage` legacy no cambia scope, borra ni reemplaza
permisos de un rol con `organization_all_permissions`; el actor con el grant puede renombrarlo sin
perder autorización dinámica. También prueba que `access.organization.all_branches` como permiso
ordinario no concede permisos futuros ni crea el grant. PostgreSQL aislado valida una autoridad Dueño,
dos asignaciones exactas y un mapping histórico revertido sin mapping activo.

## TDD-TS-088 Bootstrap y transición explícita de perfiles

Dominio SQLite prueba bootstrap con los dos correos configurados, organización/actor/procedencia
explícitos, usuarios preexistentes/activos con rol legacy preservado, atomicidad, replay estable, conflicto y ausencia sin cuentas
nuevas. Prueba dry-run sin PII, creación `PENDING`, aplicación aditiva, reversión `REVERSED`, snapshot,
idempotencia, segundo ciclo histórico, conflicto concurrente, replay de carrera con payload distinto,
stale legacy por ausencia o sucursal distinta y destino reasignado. Prueba además que una denegación,
incluido actor cross-org existente, revierte escritura ajena antes de persistir su auditoría en la
organización objetivo, y que organización inexistente/inactiva falla antes de autoridad/auditoría sin
violar FK. PostgreSQL aislado ejecuta upgrade/downgrade/re-upgrade, bootstrap exacto/replay y el ciclo
dry-run/PENDING/MAPPED/REVERSED/replay con fixture determinista. No equivale a bootstrap ni E2E sobre
usuarios o datos productivos.

## TDD-TC-082 Bootstrap no tiene escalación general

Given usuarios preexistentes, una organización explícita y los dos correos autorizados
When se intenta variar correo, organización, actor, procedencia o dejar una asignación parcial
Then el comando falla sin asignaciones nuevas y conserva auditoría de rechazo cuando aplica.

## TDD-TC-083 Reversión sólo retira la asignación creada por el mapping

Given un mapping aplicado que conservó una especialidad existente
When se revierte con su key y actor autorizado
Then se retira únicamente el perfil destino agregado, snapshot y filas históricas permanecen y un
reintento devuelve el estado `REVERSED`. Si la fila destino ya no coincide exactamente con la sucursal
registrada por el mapping, el caso falla y no modifica el estado.

## TDD-TS-083 Offline, outbox/inbox e idempotencia de caja

Integración gateway SQLite/PostgreSQL cubre persistencia local, actor/alcance, reintento, reconexión, inbox duplicado, denegación remota, lag y estado visible. Recuperación verifica que no exista éxito final local ni compensación automática por conflicto.

## TDD-TS-084 Migraciones y downgrade reversibles

Alembic PostgreSQL y SQLite debe cubrir upgrade desde head, una head, downgrade y re-upgrade, roles
semilla, Administrador corporativo y especialidades. Debe rechazar downgrade si hay user_role de perfil,
mapping o grant externo, y permitirlo sólo tras reversión controlada sin borrar datos confirmados.
PCO-001 ejecuta SQLite y PostgreSQL aislado para perfiles; los modelos de caja posteriores siguen sólo
definidos.

## TDD-TS-085 Contratos, frontend y E2E por perfil

Validar JSON Schema versionado de endpoints, errores y serialización de centavos/Decimal. E2E por los seis perfiles cubre navegación autorizada/denegada, sucursal, movimientos, cuentas, monitor, corte y reportes. QA visual cubre escritorio/reducido, foco, teclado, contraste y estados vacío/carga/error.

## TDD-TS-086 Seguridad y observabilidad R3

Verificar step-up según política aprobada, rate limit, auditoría append-only de éxito/denegación, redacción de secreto/PII, correlation id, métricas y trazas. Regresión confirma que UI, logs y eventos no son fuente de autorización ni cálculo financiero.

## TDD-TS-087 Threat model, reversión y contratos de iteración 2

Prueba simulaciones de escalación, branch tampering, replay, autorización offline vencida, doble corte, evidencia/PII, modificación histórica y downgrade. Verifica aprobación humana antes de R3, fallo/reversión controlados, compatibilidad por fases y que rollback de aplicación, downgrade de esquema y compensación de negocio son procedimientos distintos.

## Cobertura directa PRD y BDD

| Suite/caso | PRD/NFR | BDD principal |
|---|---|---|
| TDD-TS-077, TDD-TC-073, TDD-TC-081, TDD-TS-088, TDD-TC-082, TDD-TC-083 | PRD-FR-215, NFR-020, NFR-024 | BDD-SC-270/271/277/298/299/300 ejecutados parcialmente por autorización/transición; 272..276/293 proyectados o negativos de ruta existente |
| TDD-TS-078, TDD-TC-074, TDD-TC-079 | PRD-FR-216, NFR-021 | BDD-SC-278..280, 294, 296 |
| TDD-TS-079, TDD-TC-075 | PRD-FR-217 | BDD-SC-281..283 |
| TDD-TS-080, TDD-TC-076 | PRD-FR-218 | BDD-SC-284, 285 |
| TDD-TS-081, TDD-TC-077, TDD-TC-080 | PRD-FR-219, NFR-021 | BDD-SC-286, 287, 295 |
| TDD-TS-082, TDD-TC-078 | PRD-FR-220, NFR-021 | BDD-SC-288, 297 |
| TDD-TS-083 | PRD-FR-216, NFR-022 | BDD-SC-289 |
| TDD-TS-084 | PRD-FR-215, NFR-024 | BDD-SC-290 |
| TDD-TS-085 | PRD-FR-215..220 | BDD-SC-270..297 definido; no ejecutado en PCO-001 |
| TDD-TS-086, TDD-TS-087 | NFR-020..024 | BDD-SC-271, 289..297 |

## Comandos previstos — estado `defined`, no ejecutados

```bash
python -m pytest apps/api/tests -q
python -m pytest tests/architecture/test_traceability.py -q
python -m ruff check apps/api tests
pnpm typecheck
pnpm --filter @restaurantos/pos-web test
pnpm --filter @restaurantos/pos-web build
git diff --check
```

Antes de implementación se añadirán comandos de integración PostgreSQL, SQLite gateway y Playwright; los nombres, fixtures, conteos y resultados permanecen pendientes hasta existir las pruebas.
