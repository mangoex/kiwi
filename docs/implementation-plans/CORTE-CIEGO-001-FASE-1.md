# CORTE-CIEGO-001 — plan de implementación de fase 1

## Estado actual verificable — 2026-10-22

| Bloque | Terminado localmente | Pendiente de cierre |
|---|---|---|
| F1-01..05 | Especificaciones, pruebas iniciales, autoridad y proyecciones de caja | Integración integral del paquete |
| F1-06 | Lectores, canales y diagnóstico humano de sync; dos hallazgos de auditoría de descargas corregidos | Reconciliar manifiesto final de rutas/campos |
| F1-07 | Respuestas tardías, caché, metadatos de sesión y primera adaptación de turnos/cortes | Completar movimientos de caja, cuentas, gastos, canales, reportes y demás consumidores; QA integral |
| F1-08 | Sin cierre | Recepción sin costos, ajuste/revisión separadas, autorizaciones exactas y recorridos operativos |
| F1-09 | Privacidad al suspender política, regresión local/PG | Preflight individual, clientes/leases incompatibles, ensayo completo de transición |
| F1-10 | Evidencia focal acumulada | Integración completa, gateway/E2E y CI del commit |
| F1-11 | Auditoría independiente iniciada; dos hallazgos reproducidos/corregidos | Revisión del diff final y cierre integral |

**Fase 1 abierta. No se ha desplegado, migrado ni cambiado configuración o datos de producción.**
Esta tabla resume el estado vigente; los apartados cronológicos inferiores conservan evidencia.


Fecha: 2026-10-21. Base inspeccionada: `abc4e7f`, con formalización documental local
de CC-D01..12. **F1-04/05 implementadas localmente; F1-06 en revisión de cobertura, F1-07 en implementación y F1-09 parcial.
El usuario autorizó terminar F1-06..11; producción conserva autorización separada.**
El plan inicial fue R0. F1-01/02 ahora completan diseño documental R3 por permisos,
datos financieros, persistencia y autoridad offline. F1-04 añade runtime R3 de autoridad;
el corte ciego integral continúa pendiente y no está activado.

Autoridad: [paquete aprobado](CORTE-CIEGO-001.md), [PRD](../01-PRD.md)
PRD-FR-289/290/300, [SDD](../02-SDD.md) §71.1/2/12 y ADR-048;
PRD-FR-291/295/296/297/298/299 para fronteras de operación y transición.
[BDD](../03-BDD-corte-ciego.md), [TDD](../04-TDD-corte-ciego.md) y
[matriz](../05-matriz-trazabilidad.md) conservan autoridad. No se crean nuevos
IDs PRD/BDD/TDD ni se cambia su estado Disenado por preparar este plan.

## 1. Resultado y frontera de la fase

Separar las capacidades de leer estado operativo, capturar, finalizar, leer resultados
financieros, consultar acuse y corregir. Para la política nueva, Cajero/encargado deben
poder operar según su función sin recibir esperado, componentes agregados, diferencias,
venta total, ticket promedio o señal de alerta/cuadratura. Dueño y delegado explícito
consultan únicamente lo autorizado; revocar debe invalidar acceso posterior, incluidos
replay, historia y exportaciones. Finalizar no concede lectura financiera.

La fase entrega autoridad, proyecciones, contratos, integración UI, reportes restringidos
y preparación de transición. Conserva fórmulas, snapshots, asociaciones, ledger y flujos
canónicos; no reconstruye historia ni crea una segunda máquina de corte.

Fuera de implementación de fase 1: denominaciones/custodia y nueva captura de fase 2,
conciliación por medio, recuperación integral de conteo offline y entrega de alertas de
fase 3; compras sugeridas y márgenes. Las capacidades de captura/finalización/corrección
se separan aquí, pero no habilitan flujos nuevos incompletos. La recepción sin costos,
autorizaciones de pedidos y revisión administrativa de inventario son dependencias
colaterales: completar la adaptación de permisos/proyecciones que este cambio requiera,
sin sustituir sus máquinas de dominio ni afirmar que un workflow inexistente ya funciona.

**Terminar fase 1 no activa el corte ciego completo.** El código futuro puede verificarse
en entorno aislado; activación requiere contrato completo del recorrido elegible, revisión
individual y CC-D11. Si una operación necesita fase 2 o una guarda colateral no disponible,
esa carencia bloquea habilitarla; no se concede autoridad amplia como solución temporal.

## 2. Evidencia estática y superficies a recorrer

Resumen inicial, ampliado por el [inventario completo F1-01](CORTE-CIEGO-001-ACCESOS.md)
con 407 entradas (405 combinaciones método/ruta únicas) y superficies no HTTP. No es prueba de explotación:

| Superficie observada | Evidencia local | Trabajo necesario |
|---|---|---|
| Resumen de turno | [api.py](../../apps/api/restaurant_os/api.py): GET `/cash-shifts/summary` autoriza con `cash.shift.read` | Separar consulta operativa de respuesta financiera y revisar alias hermanos. |
| Detalle de turno | Mismo archivo: GET `/cash/shifts/{cash_shift_id}` serializa turno y cierre bajo `cash.shift.read` | Contrato operativo con allowlist; cierre/snapshot monetario sólo a lector financiero. |
| Movimientos | Mismo archivo: GET `/cash-movements` usa `cash.shift.read` | Evitar que listado de movimientos reconstruya componentes financieros; conservar acciones individuales autorizadas. |
| Servicio y semilla de roles | [operations.py](../../apps/api/restaurant_os/operations.py): `authorize_branch_scope`, `_assign_default_role_permissions`, `_cash_summary_for_shift`, `UserCashCutService` | Guardas compartidas, división de autoridad y proyección de list/detail/mutaciones/replay; sin alterar fórmula. |
| Cliente de cortes | [userCashCuts.ts](../../apps/pos-web/src/features/settings/userCashCuts.ts) exige campos financieros y usa create/read agregados | Separar parsers/capacidades; no rellenar importes ocultos con cero ni null como arreglo de UI. |
| UI de cortes | [UserCashCutsPanel.tsx](../../apps/pos-web/src/features/settings/UserCashCutsPanel.tsx) | Renderizar acuse operativo y vista financiera según contrato, sin recuperar información oculta. |
| Contratos | [schemas](../../packages/contracts/schemas): familias cash-shift y user-cash-cut, listas, detalles y respuestas de mutaciones | Definir versión/proyecciones y compatibilidad antes del primer cambio de respuesta. |
| Reportes/asistentes | [reconciliation_reports.py](../../apps/api/restaurant_os/reconciliation_reports.py), [agent_tools.py](../../apps/api/restaurant_os/agent_tools.py), SalesMonitor y paneles POS/Admin | Recorrer desde permiso hasta respuesta, incluyendo consultas indirectas y exportaciones. |
| Sesión/offline | [session.ts](../../apps/pos-web/src/session.ts), [offline_authorization.py](../../apps/api/restaurant_os/offline_authorization.py), gateway/leases | Revalidación, cachés y sesión antigua; ningún bundle viejo debe evadir la política al activar. |

El inventario enlazado registra origen, guarda, datos, consumidores y destino por
familia, con handlers/aliases y límites de cobertura. F1-03 lo convierte en pruebas
negativas/positivas; no considerar este cierre documental una garantía de runtime.

## 3. Orden de ejecución y tareas

**F1-01/02 completadas documentalmente; F1-03 con lote inicialmente RED; F1-04/05 implementadas y verificadas localmente; F1-06 en curso y F1-07..11 pendientes.** Responsables son funciones sugeridas,
no delegaciones ni asignaciones de usuarios reales. Cada tarea con runtime requiere
prueba RED por la causa esperada antes del cambio y GREEN focal después.

| ID / orden | Tarea y responsable funcional | Entrega comprobable | Dependencia y pruebas principales |
|---|---|---|---|
| F1-01 — completada documentalmente | Inventariar accesos y consumidores. Backend + frontend | Mapa origen → guarda → dato → consumidor; lista de rutas/aliases reales y requisitos de operación. Baseline reproducible con actores sintéticos. | Entrada: contrato aprobado. TC-450/451/462, AC01/02/16. No inspeccionar ni modificar cuentas productivas por defecto. |
| F1-02 — completada documentalmente | Cerrar diseño técnico mínimo. Arquitectura | SDD del incremento con códigos de capacidad, proyecciones operativa/financiera, contratos versionados, delegación/revocación, composición de grants y compatibilidad. Distinguir acuse de resultado y autorización de acción de lectura. | F1-01. Decidir reutilizar/dividir/versionar permisos sin inferir autoridad del nombre del rol; validar tablas de ejemplos contra CC-P01..18. |
| F1-03 — fixtures y lote RED preparados | Preparar fixtures y RED de autoridad/contratos. QA + backend | Dos organizaciones/sucursales, roles, delegado vigente/revocado y grants acumulados; pruebas de JSON, alias, scopes, mutación y replay que demuestren brecha por la razón correcta. | F1-02. TC-450/451/452/462; no usar ausencia de endpoint o error de fixture como RED de seguridad. |
| F1-04 — implementada localmente | Implementar capacidades, delegación y alcance. Backend | Evaluación server-side vigente y común para consultas/comandos; facultades de consulta separadas de finalizar/corregir. Si necesita persistencia, migración aditiva y tests antes de aplicarla. | F1-03. TC-450/451; Dueño por autoridad persistida, delegado por concesión explícita. Grant general incompatible impide aprobar preflight. |
| F1-05 — implementada localmente | Separar proyecciones de turnos/cortes. Backend + contratos | DTO operativo sin campos financieros/derivados y DTO financiero protegido; mismo criterio en listas, detalles, aliases, apertura/cierre y resultados de mutaciones. Snapshot interno intacto. | F1-04. TC-450/452; acuse autorizado equivalente en replay, cero no sustituye dato omitido, sin extraer cálculo a frontend. |
| F1-06 | Cerrar consultas indirectas y reportes. Backend + reportes | Movimientos/pagos, dashboards, historial/exportaciones, asistentes y descargas respetan autoridad; encargado recibe tickets/top 10 sin importes/cantidades y consulta individual acotada. | F1-05 e inventario completo. TC-450/462: probar paginación/filtros como vía de reconstrucción, no sólo tabla visible. Delegación no eleva identidad técnica. |
| F1-07 | Adaptar clientes y sesiones. Frontend + backend | Parsers/tipos para proyecciones, acciones por capacidad, estados de acuse, lectura financiera separada; limpiar/inutilizar caché incompatible, evitar respuestas tardías y cliente antiguo. | F1-05/06. TC-450/461/462/465 parcial. Servidor sigue protegiendo aun manipulando UI. Actualizar contrato antes de consumirlo. |
| F1-08 | Verificar permisos colaterales. Backend + QA | Venta/cobro/KDS y recepción autorizados siguen operando; recepción no expone costos ni exige catalog.manage; conteo no autoriza ajuste; descuentos/cambios conservan autorización exacta. | F1-04..07. TC-451/458/459/465 parcial. Si hay un hueco previo de workflow, registrarlo como dependencia bloqueante del recorrido, no darlo por implementado. |
| F1-09 | Ensayar transición, revocación y reversión. Backend + operación | Dry-run de asignación antes/después en fixtures, bloqueo de clientes/leases incompatibles y preflight por sucursal; historia intacta y rollback de aplicación sin reabrir fugas. | F1-04..08. TC-461/464 y porción de TC-460/463 afectada por autoridad. No ejecutar cambios sobre usuarios reales. |
| F1-10 | Verificar integración y preparar handoff. QA + equipo | Evidencia focal backend/frontend/contratos, PostgreSQL y gateway afectados, E2E de roles; CI del commit y manifiesto de rutas/campos revisados. | F1-01..09. Sin exclusiones nuevas ni pruebas desactivadas para obtener verde. |
| F1-11 | Auditoría independiente R3 y cierre de fase. Revisor Sol con contexto fresco | Una revisión del cambio completo: autoridad, fugas, replay/revocación, historia, concurrencia y recuperación; corregir hallazgos y repetir sólo gates afectados. | F1-10. Handoff con afirmación/evidencia/refutación/resultado/riesgo residual. Cierre no autoriza activar piloto. |

Secuencia crítica: **01 → 02 → 03 → 04 → 05 → 06 → 07 → 08 → 09 → 10 → 11**.
La recopilación de consumidores frontend y fixtures puede prepararse durante F1-01/02;
no adelantar grants, cliente o respuestas productivas antes de cerrar contrato/compatibilidad.
Los cambios pueden dividirse en incrementos revisables, pero ninguno se activa dejando
una superficie alternativa con lectura amplia o una operación necesaria inutilizable.

## 4. Decisiones técnicas de F1-02, cerradas sin reabrir producto

Resolución canónica en [SDD técnico](../02-SDD-corte-ciego-fase-1.md): §2 capacidades,
§3 delegación/persistencia/revocación, §4/5 contratos y replay, §6/7 accesos indirectos,
§8 transición. La lista siguiente conserva el alcance que debía resolverse:

1. Matriz exacta capacidad → actor/alcance → ruta → campos. Elegir códigos de permiso
   nuevos o reutilizados y migración compatible de semilla/roles; `cash.shift.read` no
   seguirá siendo prueba suficiente de autoridad financiera en la política nueva.
2. Contratos operativos y financieros de turnos/cortes, acuses de comandos y replay.
   Fijar tratamiento de versiones antiguas y errores explícitos; un DTO con importes
   ocultos o un cliente que pide el detalle financiero para mostrar estado es inválido.
3. Persistencia y revocación de delegación: autoridad concedente conforme a Dueño,
   sucursales/información explícitas, auditoría, vínculo con versión de autorización;
   definir carrera lectura/revocación y momento de revalidación. No crear automáticamente
   delegados desde Administrador/Supervisor ni reinterpretar todos los grants como delegación.
4. Accesos indirectos: contratos para detalle individual autorizado y reportes restringidos;
   tratamiento de filtros/paginación/exportación que permita reconstruir ventas. Definir
   calendario de periodos contra indicador canónico y límites de búsqueda sin cambiar
   reglas de negocio ni inventar una nueva definición de ticket.
5. Habilitación y compatibilidad por sucursal/versión, preflight, drenado de leases y
   reversión segura. Si se usa un mecanismo de activación, ausencia de configuración no
   debe habilitar el nuevo recorrido ni servir datos amplios a un actor ya restringido.

Se actualizaron SDD/ADR, refinamientos BDD/TDD y enlaces de matriz; PRD conserva las
reglas aprobadas. Tablas/rutas/permisos están especificados en el SDD, sin schemas
ejecutables, migración ni asignaciones aplicadas.

## 5. Pruebas y criterios de salida

| Bloque | Prueba positiva | Intento de refutación / negativo | Referencias |
|---|---|---|---|
| Operador ciego | Cajero/encargado consulta estado y declaración permitida antes/después del corte | JSON oculto, alias, closure, mutación, replay, error/log, indicador de cuadratura/alerta o suma indirecta revela datos | BDD-767; TC-450; AC01/02 |
| Dueño/delegado | Lectura financiera dentro de concesión vigente | Otra organización/sucursal, concesión revocada, rol visible falsificado; lectura no habilita finalizar/corregir | BDD-768; TC-450/451 |
| Roles efectivos | Líder actúa como encargado; funciones ajenas al cambio se preservan | Cajero jefe/Supervisor/Administrador o grant general evaden la separación | BDD-769/770; TC-451 |
| Acciones separadas | Encargado/Dueño puede finalizar recorrido compatible sin revelar importes al encargado | Cajero, delegado o dispositivo finaliza; crear/capturar se usa como autorización universal | BDD-771/772; TC-452; AC08 |
| Reportes | Encargado ve tickets y top 10 de su sucursal por día/semana/mes | Ranking devuelve cantidades/precios; paginar/exportar permite sumar venta; Cajero obtiene reporte | BDD-791/792; TC-462 |
| Historia/replay | Originales inmutables y respuesta según autoridad vigente | Acuse guardado bajo permiso anterior o cursor/descarga de otra sesión devuelve snapshot financiero | BDD-768/790; TC-450/461/464 |
| Colaterales | Venta, recepción y KDS autorizados operan sin lectura financiera | Conceder catalog.manage, perder guardas de descuento/cancelación o convertir conteo en ajuste | BDD-782..785; TC-458/459 |
| Persistencia/autoridad | Una concesión/revocación confirma atómicamente y deja auditoría protegida | Fallo parcial, autorización vieja en replay, carrera revocación/lectura/mutación o lease previa | TC-450/460/461/463/464, según superficie tocada |

Los identificadores abreviados BDD/TC/AC remiten a BDD-SC, TDD-TC y CC-AC de los
documentos canónicos. La cobertura de TC-452/458..461/463..465 es sólo la porción
afectada; no marcar esos casos completos ni PRD de fase 2 como Probado por acabar fase 1.

Puntos de partida existentes para extender o usar como regresión:

- API/dominio: [cortes](../../apps/api/tests/test_user_cash_cuts.py),
  [contratos](../../apps/api/tests/test_user_cash_cut_contracts.py),
  [turno](../../apps/api/tests/test_cash_shift_operational_close.py),
  [PCO-004](../../apps/api/tests/test_pco004_contracts.py),
  [autoridad workspace](../../apps/api/tests/test_branch_workspace_authority.py).
- Reportes/agentes: [conciliación](../../apps/api/tests/test_branch_reconciliation_reports.py),
  [reportes HTTP](../../apps/api/tests/test_pco007_http.py),
  [contratos de agentes](../../apps/api/tests/test_agent_tools_contract.py).
- PostgreSQL/migración: [corte concurrente](../../apps/api/tests/test_user_cash_cuts_postgres.py),
  [corte migración](../../apps/api/tests/test_user_cash_cuts_migration.py),
  [autoridad](../../apps/api/tests/test_branch_authority_postgres.py),
  [workspace](../../apps/api/tests/test_branch_workspace_postgres.py).
- Frontend: [cortes](../../tests/frontend/test_pos_user_cash_cuts.mjs),
  [sesión](../../tests/frontend/test_pos_session_handoff.mjs),
  [monitor](../../tests/frontend/test_pos_operational_shift_sales_monitor.mjs),
  [reportes](../../tests/frontend/test_reconciliation_reports.mjs).

Estas suites no acreditan hoy el contrato ciego. Añadir pruebas de frontera donde falten;
una prueba semántica de texto no sustituye API real ni E2E de autorización.

## 6. Ejecución de gates, después de autorizar código

Desde la raíz, seleccionar los casos afectados de las suites anteriores más los nuevos
tests de cada incremento. Ejemplo de grupo base de corte (no sustituye las pruebas nuevas):

```powershell
.\.venv\Scripts\python.exe -B -m pytest apps/api/tests/test_user_cash_cuts.py apps/api/tests/test_user_cash_cut_contracts.py apps/api/tests/test_cash_shift_operational_close.py -q -p no:cacheprovider
pnpm test:pos-user-cash-cuts
pnpm test:pos-session-handoff
pnpm test:pos-operational-shift-sales-monitor
pnpm typecheck
git diff --check
```

Backend: Ruff y mypy focales de módulos modificados; añadir pruebas de reportes/agentes,
sesiones y colaterales según F1-01. PostgreSQL aislado para delegación/revocación/locks y
migración si aplica; SQLite/gateway para leases, caché/sync y compatibilidad tocadas.
No usar base productiva ni presentar tests omitidos por falta de DB como aprobados.
Build de POS/Admin afectados al cambiar contratos/empaquetado/rutas o antes de release;
E2E con roles y QA visual de estados/breakpoints realmente modificados.

[CI actual](../../.github/workflows/ci.yml) configura typecheck backend/gateway, pytest,
URLs PostgreSQL aisladas (incluida PCO006), typecheck frontend y suite semántica. Eso no
prueba que un test nuevo se recolecte/ejecute ni que exista E2E de corte ciego: F1-10 debe
verificar colección, skips, artefactos y gate del commit exacto. Incorporar el gate faltante
o ejecutarlo focalmente con evidencia; suite completa aplicable una vez en CI. Suite
completa local sólo bajo GOV-TEST-001, sin repeticiones indiscriminadas.

## 7. Transición, observabilidad y límites de autorización

F1-09 prepara simulación/dry-run, no modifica cuentas reales. Antes de activar, se requiere
un manifiesto revisado de usuario/alcance/permisos antes-después, concesiones explícitas,
compatibilidades/leases resueltas y evidencia de turnos previos concluidos/sincronizados.
No activar a mitad de turno ni finalizar o compensar historia para forzar elegibilidad.
No fabricar denominaciones legacy. Fecha/sucursal y cambios productivos conservan
autorización separada; decidir un plan no autoriza ejecutarlo.

La reversión mantiene historial y restricciones vigentes: detener ampliación, recuperar
una versión compatible y conservar comandos/evidencia. Nunca volver a una API que exponga
importes ni degradar esquema con historia. Si fase 2 está pendiente, documentar claramente
qué capacidades de fase 1 se verificaron sin presentar el corte completo como habilitado.

Señales futuras en la auditoría/handoff del mismo incremento, sin importes en logs generales:

1. ¿Qué actor consultó o intentó consultar datos financieros? Acción, sucursal, versión
   de autoridad/política y resultado; detalle sensible sólo en auditoría protegida.
2. ¿Un replay, exportación o sesión anterior intentó reutilizar autoridad revocada?
   Correlación de comando/sesión y código de rechazo, sin payload financiero.
3. ¿Qué impide activar una sucursal con seguridad? Bloqueador de usuario/grant/lease,
   cliente o turno, con estado verificable y sin publicar importes al operador.

## 8. Criterio de terminado y evidencia de este plan

Fase 1 sólo se cerrará cuando: inventario de superficies esté completo; contratos y
autoridad estén implementados; pruebas positivas/negativas y gates afectados pasen;
no exista fuga alternativa ni elevación por rol/grant/replay; operación autorizada siga
funcionando; transición/reversión estén verificadas y auditoría R3 independiente cerrada.
El reporte distinguirá evidencia local/CI/Git/despliegue y cobertura parcial de fase 2.
La matriz sólo avanzará estado con evidencia real del requisito completo correspondiente.

### Cierre documental F1-01/02 — 2026-10-21

Entregas: [inventario](CORTE-CIEGO-001-ACCESOS.md), [diseño técnico](../02-SDD-corte-ciego-fase-1.md),
SDD §71.14/ADR-048 y refinamientos BDD/TDD/matriz. Las doce decisiones y estados Disenado
se conservan. No se modificaron código, tests, esquemas ejecutables, permisos o datos.

Baseline existente, con fixtures aisladas y comando reproducible en inventario:
**30 passed, 1 skipped** en 75.50 s. Omitido roundtrip PostgreSQL por ausencia de
PCO004_TEST_POSTGRES_ROUNDTRIP_URL; warning Starlette/httpx deprecado, sin silenciamiento.
Es evidencia PCO-006, no RED/GREEN de corte ciego. Integridad documental: **9 pruebas de trazabilidad pasaron**, 463 enlaces locales
verificados, fences/espacios y `git diff --check` correctos. El manifiesto conserva dos
duplicidades de decorador existentes: 407 entradas, 405 método-rutas únicas.
No CI nuevo, prueba UI, migración ni piloto.

| Afirmación de diseño | Evidencia y refutación documental | Resultado / riesgo residual |
|---|---|---|
| Acción y lectura no se confunden | SDD §2/4/5; intentar finalizar con grant de sólo lectura y extraer snapshot por replay/colisión | Diseño exige capacidades independientes y acuse. Implementación/concurrencia quedan por probar en TC-450/452/463. |
| Inventario incluye vías indirectas | AST + mapa de familias: perfil cliente con ticket promedio, logs raw, AI, intents, gateway; intentar salir por alias o descarga | 407 entradas/405 método-rutas únicas y no HTTP enumerados; no prueba dinámica de ausencia de fugas ni cobertura de plugins externos. |
| Revocación no depende del navegador | SDD §3/8; lectura en vuelo, exporte previo, roles acumulados y lease desconectado | Autoridad vigente, locks/versiones y fencing diseñados. No se promete retirar archivos/bytes enviados ni revocación instantánea offline. PostgreSQL pendiente. |
| Historia y operación autorizada se preservan | Registro aditivo, no edición de ledger/snapshots, precio de pedido individual, recepción sin costos; intentar rollback a API amplia | Contrato cerrado; migración, compatibilidad y pruebas positivas siguen pendientes. Activación requiere recorrido completo y revisión por usuario. |

Revisión independiente R3 con contexto fresco (`audit_f10102`): **cerrada sin hallazgos
documentales pendientes**. Hallazgo P2 sobre reimpresión como contexto autoemitido
resuelto en SDD §6/9 y TC-462; revisor confirmó cierre. Se verificaron focalmente
composición de grants, calendario, Dueño, recepción sin gestión corporativa y conteo
sin alias amplio. La revisión no certifica runtime ni sustituye F1-11 futuro.

F1-01 y F1-02 quedan completadas documentalmente. Siguiente trabajo: F1-03 con
autorización de código; no iniciar retirando permisos reales ni cambiando respuestas
productivas. La implementación completa de fase 1 y el mapeo de usuarios siguen pendientes.

## 9. F1-03 — fixtures y pruebas RED

Alcance autorizado: pruebas R3 y datos sintéticos, **sin implementar lógica funcional**.
Se activan TDD/matriz y este handoff. PRD/SDD/BDD conservan las doce decisiones; no se
modificaron runtime, migraciones, contratos productivos, roles reales, CI ni configuración.

### Archivos y fronteras de la fixture

[Datos](../../apps/api/tests/corte_ciego_fixtures.py),
[oráculos de contrato](../../apps/api/tests/corte_ciego_contracts.py),
[RED](../../apps/api/tests/test_corte_ciego_f1_red.py) y
[controles](../../apps/api/tests/test_corte_ciego_f1_controls.py).

SQLite in-memory por caso; organización A con sucursales A/B y organización ajena con
su sucursal. Roles sintéticos: Dueño baseline, Cajero, Líder, Cajero jefe, Administrador,
Supervisor, delegado, revocado y perfil acumulado. Concesiones explícitas: cash.cuts en A,
sales en B; revocación incrementa authorization_version. Pago y depósito no nulos,
turno cerrado y corte COUNTED creados con servicios baseline; snapshots para consultas.
No se accede a DATABASE_URL ni a datos productivos. La excepción de IA sustituye sólo
el I/O del proveedor; el handler, servicio y SQL siguen reales, observados por evento SQL.

Las cuatro relaciones futuras de política/grants se crean en metadata **separada**,
únicamente como inputs de fixture. No implementan lookup/ACL, comandos de delegación,
FK productivas, locks ni migración. El runtime actual las ignora, que es parte de la
integración pendiente observada. No es una activación real ni un ensayo de despliegue.
Sustituir bootstrap por migración real en F1-04 manteniendo los datos/expectativas; no
hacer pasar los tests agregando una política falsa en el helper.

Los grants legacy deliberadamente conservados exponen colisiones/compatibilidades;
no son una recomendación de asignación ni un preflight válido. Dueño y perfil general
acumulado comparten autoridad legacy: el positivo actual sólo acredita Dueño baseline,
no la futura clasificación gobernada. F1-04 deberá ligar revisión individual y autoridad
persistida; está prohibido resolverlo con nombre de usuario, etiqueta o IDs de fixture.

### Cobertura y secuencia de GREEN futura

| Caso | RED / control preparado | Destino del cierre funcional |
|---|---|---|
| TC-450 | 7 lecturas/aliases × Cajero/Líder; comandos legacy count/replay/finalize; acuse de finalización y replay monetarios; ámbito ajeno sin mutación | F1-04/05: política, guardas, DTO/contratos v2 y bloqueo v1. Rutas v2 inexistentes no se usan como RED por 404. |
| TC-450/451 | 8 perfiles frente a sales A; grant cash.cuts A + sales B no concede sales A; revocación antes de lectura con importe no nulo; consulta sin branch | F1-04/06: resolución vigente por par/actor y cobertura completa de consulta. |
| TC-452 | Cajero/delegado/Admin con create legacy no deben finalizar; Líder con finalize nuevo no debe depender de create; escritura rechazada debe conservar hash de negocio | F1-04/05: separación real de acción/lectura. No hace falta implementar denominaciones para demostrar esta brecha. |
| TC-450/462 | Historial de pagos/movimientos, perfil de cliente y cuentas con filtro/paginación; pedido por ID sin atención/contexto | F1-06: lectura masiva financiera protegida y detalle individual acotado; positivos de operación deberán acompañar su implementación. |
| TC-450 | IA llega a SELECT monetario sin autorización; sólo proveedor externo sustituido | F1-06: guarda común previa a SQL/contexto; no basta denegar después de consultarlo. |
| TC-450/462 | Oráculos de acuse/reporte admiten mínimos y rechazan monetarios/derivados/cantidades/extra keys, incluyendo 0/null/false | F1-05/06: aplicar a salidas reales v2 cuando existan; no confundir validar ejemplos con verificar endpoint nuevo. |

Cobertura total del inventario y pruebas de carreras PostgreSQL, exportes/intents,
colisión IntegrityError, dispositivos/leases, reimpresiones, calendarios, permisos
colaterales y UI siguen como gates de F1-04..10. No se reemplazan por mocks ni por un
skip nuevo. F1-03 prepara el lote ejecutable de entrada; no cierra la verificación
exhaustiva de fase 1 ni permite activar la política.

### Comandos reproducibles y evidencia

```powershell
.\.venv\Scripts\python.exe -B -m pytest apps/api/tests/test_corte_ciego_f1_controls.py apps/api/tests/test_corte_ciego_f1_red.py -q --tb=short -p no:cacheprovider
.\.venv\Scripts\python.exe -B -m pytest apps/api/tests/test_user_cash_cuts.py apps/api/tests/test_user_cash_cut_contracts.py -q -p no:cacheprovider
.\.venv\Scripts\python.exe -B -m ruff check apps/api/tests/corte_ciego_fixtures.py apps/api/tests/corte_ciego_contracts.py apps/api/tests/test_corte_ciego_f1_controls.py apps/api/tests/test_corte_ciego_f1_red.py
.\.venv\Scripts\python.exe -B -m mypy --follow-imports=silent apps/api/tests/corte_ciego_fixtures.py apps/api/tests/corte_ciego_contracts.py apps/api/tests/test_corte_ciego_f1_controls.py apps/api/tests/test_corte_ciego_f1_red.py
.\.venv\Scripts\python.exe -B -m pytest tests/architecture/test_traceability.py -q -p no:cacheprovider
git diff --check
```

Resultado local final: **42 RED esperados, 18 passed, 0 errores, 0 skips** en
138.74 s (60 casos). Se inspeccionaron los 42 mensajes: todos alcanzan la aserción
contractual CC-F1, sin 404/422/500 ni errores de setup contados como RED. Los 18 verdes
son 16 controles de fixture/oráculo y 2 negativos de alcance ya preservados.
JUnit local: `tmp/corte-ciego-f103-final.xml`; generado como evidencia temporal, no CI.
Integridad: **9 pruebas de trazabilidad correctas** y `git diff --check`.
Revisión independiente R3 con contexto fresco (`audit_f103`): **sin hallazgos
pendientes en el lote revisado**. Dos P2 corregidos y revalidados: código del control
de organización ajena y probe de IA que inicialmente sustituía demasiado dominio.
El revisor inspeccionó los 60 casos del JUnit final y confirmó causalidad de los 42 RED.
Cierre de este lote inicial ejecutable de F1-03; no certificación exhaustiva de la fase.
Baseline focal existente: **13 passed**, sin skips; lint y typecheck focal de los cuatro
archivos correctos. Mypy verifica los archivos nuevos; follow-imports=silent limita
el reporte de módulos ajenos sin omitir estos archivos. No type-ignore, xfail, skip,
exclusión de recolección ni cambio de CI añadidos. Warning existente de Starlette/httpx
no silenciado. CI que recolecte el lote quedará rojo hasta implementación autorizada;
no se presenta como rama lista para publicar ni se solicita activar un piloto.

| Afirmación | Refutación/evidencia | Resultado y riesgo residual |
|---|---|---|
| RED representa brecha y no infraestructura | Guardas de status descartan 404/422/500; fixtures/controles y revisión de failure messages; mutaciones comparan estado | Sólo cuentan fallos causales; errores de preparación se corrigen antes de registrar resultado. |
| Repetir no escribe, pero puede filtrar | Snapshot de ledger/cortes/operaciones/comandos antes/después y replay real, también tras revocar | Hash intacto se comprueba antes de ausencia de campos. No acredita carrera concurrente. |
| No se altera lógica funcional | Diff limitado a cuatro archivos tests y autoridad documental activada; SQL sobre engine de fixture | Sin runtime/migración/deploy; staging no prueba integridad de persistencia productiva. |
| IA prueba frontera real | Servicio original y listener SQL; únicamente _call_external_provider sustituido | Una guarda futura dentro del servicio puede hacer GREEN; no se elimina mediante stub. |


## 10. F1-04 — capacidades, delegación y alcance

Autorización: petición explícita de implementar únicamente F1-04, con pruebas dirigidas,
sin producción ni fases siguientes. R3 por permisos/persistencia. No cambia las doce
resoluciones ni fórmulas, dinero, estados de caja, snapshots o asignaciones reales.

Entregado:

- Evaluador `financial_authority.py`: capacidad exacta, actor activo, organización,
  ámbito del mismo rol y pares sucursal/dataset; Dueño requiere revisión individual
  persistida vigente más autoridad organizacional. El bit financiero o grant general
  por sí solos no sirven. Delegación no concede captura, finalización ni corrección.
- `financial_access.py` y tres rutas `/api/v2/financial-access/grants`: emitir, revocar,
  listar metadata. Emisión/revocación atómicas, idempotentes y auditadas; reautorizan
  antes del replay. Rechazan autodelegación innecesaria, comodines, pares repetidos,
  datos de otra organización y actores técnicos. Errores DB devuelven 503 genérico.
- Migración aditiva `0101_financial_authority`: seis relaciones, nueve códigos sin
  asignarlos, FKs compuestas, constraints y triggers append-only. Downgrade rechaza
  evidencia o capacidades asignadas. No crea revisiones Owner ni activa sucursales.
- Gobierno existente de roles impide autoasignar nuevas capacidades con admin.manage;
  incluye asignación, cambio de ámbito y apply/reverse de transiciones. Para los códigos
  existentes inventory.count.review/approve, esta restricción se activa sólo si existe
  política nueva activa en la organización; fuera de ella se conserva el baseline.
  Su workflow de revisión/aprobación sigue en F1-08, no se implementó aquí.
- Fixtures F1-03 usan las tablas reales y el comando real de revocación. No se cambió
  ninguna expectativa RED de endpoints, ni se añadieron skips/xfail/exclusiones.

### Evidencia dirigida

| Gate | Resultado local |
|---|---|
| RED de entrada `test_corte_ciego_f1_red.py -k legacy_create_cannot_finalize --maxfail=1` | Falló por finalización no autorizada y modificación real de estado, no por error de fixture. Su handler legacy sigue pendiente de F1-05. |
| `test_corte_ciego_f104.py`, `test_corte_ciego_f104_storage.py`, `test_corte_ciego_f104_postgres.py`, controles F1-03, cash cuts dominio/contratos, cumulative_profiles y branch_authority_remediation | 118 passed, 0 skipped; `tmp/corte-ciego-f104-directed.xml`. Incluye 55 pruebas de autoridad/API, 6 de migración (SQLite/PG), 6 PG de concurrencia/aislamiento y 51 de controles/regresión. |
| Frontera de tokens humanos/técnicos | 3 passed, 0 skipped tras endurecer transporte; `tmp/corte-ciego-f104-auth.xml`. Total dirigido: 121 passed. |
| PostgreSQL local aislado | `alembic upgrade head` desde DB vacía llegó a 0101; PostgreSQL 18.6 en 127.0.0.1:55441, DB `corte_ciego_f104_test`, sin conexiones productivas. CI queda configurado con DB propia en PostgreSQL 16; no ejecutado remoto. |
| Ruff y mypy focal | Verificados en runtime nuevo, operations/models/main, fixtures y pruebas modificadas. Sin silenciamientos nuevos. |
| Trazabilidad/diff | `tests/architecture/test_traceability.py`: 9 passed; `git diff --check` limpio. No equivale a CI ni despliegue. |
| RED residual F1-03 | 42 failed, 2 passed, 0 errors, 0 skipped; todas las fallas CC-F1 previstas. `tmp/corte-ciego-f104-residual-red.xml`. Expectativas conservadas para F1-05/06. |

Las barreras PG comprueban lectura primero y revocación primero, también cambio real de
permisos mediante `update_role_permissions`. Verifican espera en `pg_stat_activity`,
no sólo orden de threads. Un duplicado concurrente produce una concesión, un comando,
una auditoría y un incremento; snapshots REPEATABLE READ se rechazan. SQLite tiene FKs
habilitadas en los tests de migración y prueba triggers, rollback y no contaminación.

### Revisión independiente y afirmaciones R3

Auditoría Sol con contexto fresco `audit_f104`: una revisión y seguimiento de correcciones.
Encontró autoescalación por administración de roles, autodelegación invalidante y errores
DB con parámetros; se corrigieron y agregaron pruebas. La revisión posterior agregó
protección del conteo bajo política nueva y autorización antes de incrementar versión
al restaurar roles. Cerró hallazgos sin otro bypass concreto; pruebas ejecutadas por el
agente implementador, revisión independiente estática. La revisión final también
confirmó la frontera de tokens humanos/técnicos sin nuevos hallazgos.

| Afirmación | Evidencia e intento de refutación | Resultado / riesgo residual |
|---|---|---|
| El grant general y acumular roles no bastan | Ocho perfiles, bit aislado, admin.manage autoasignando/trasladando roles, Owner sin autoridad vigente | Denegados por evaluador/comandos nuevos. Preflight y revisión real de cuentas siguen F1-09. |
| Alcance es unión de pares exactos | cash.cuts A + sales B, combinación cruzada, scope ajeno, wildcard, eliminación del bit por gobierno real | Pares no concedidos denegados antes de callback de lectura. Integración a lectores legacy sigue F1-05/06. |
| Revocación confirmada vence a nuevas lecturas | Barreras PG en ambos órdenes, mismo lock que mutación de roles, reconsulta tras commit | Cumple en primitiva y comandos. Bytes materializados antes del commit pueden estar en tránsito; no se promete retirarlos. |
| No hay cambios parciales ni duplicados | Fallos inyectados al insertar scope/comando/auditoría, replay/conflicto y concurrencia de misma key | Rollback de grant/versión/comando y una emisión efectiva. No acredita replay de cortes/intents todavía. |
| Historia protegida y rollback no destructivo | UPDATE/DELETE contra seis tablas en SQLite/PG, FKs entre organizaciones y downgrade con evidencia | Rechazados. DB admin privilegiado puede cambiar esquema; activar/purgar evidencia no forma parte de APIs F1-04. |
| Owner no se deduce de nombre ni permisos amplios | Revisión vinculada a authorization_version y autoridad actual; mutación gobernada invalida revisión | Fail-closed. Contraseña/cambio de roles exige revisión nueva; no hay bootstrap automático. Carga gobernada de revisiones queda F1-09. |

### Preguntas operativas y señales existentes

1. ¿Se emitió o revocó realmente una concesión? `financial_access_commands` más evento
   `financial_access.issued/revoked/already_revoked`, actor, sujeto, command_id y UTC.
2. ¿Un reintento duplicó autoridad? Mismo command_id/grant_id y replay=true; no nuevo
   incremento ni auditoría de éxito. Payload distinto produce idempotency_key_conflict.
3. ¿La autoridad cambió o el almacenamiento falló? Códigos estables
   cash_authorization_changed, financial_access_denied y financial_access_unavailable;
   sin importes ni SQL en errores. No se añade un canal de alertas de fase 3.

### Límite de cierre

F1-04 entrega primitivas y administración de concesiones, no el recorrido completo de
corte ciego. Los handlers legacy, DTO, reportes, UI, gateway, exportes, preflight y las
reglas de captura/finalización central siguen en sus tareas posteriores. La suite RED
F1-03 continúa activa; no se presenta la suite total ni CI como verdes. Ninguna sucursal
quedó activada, ningún usuario real cambió y no hubo commit, push, despliegue ni migración
productiva. Para activar se mantienen CC-D11 y las dependencias de fases 1/2/3 aplicables.


## 11. F1-05 — proyecciones de turnos y cortes

Autorización: «Procede» a la propuesta F1-05, después de F1-04. Riesgo R3 por caja,
permisos y concurrencia. Alcance local: contratos/lecturas/acuse de turnos y cortes,
no F1-06, asignaciones reales, activación, commit/push ni producción.

### Entrega

- `cash_views.py` y `cash_financial_schemas.py`: DTO cerrados operativos, financieros,
  declaración propia y páginas separadas; autorización antes de SELECT monetario.
- `cash_views_api.py`: rutas v2 con identidad humana y contratos publicados en OpenAPI;
  apertura/cierre conservan dominio, workspace e intent existentes. Crear/contar/finalizar
  nuevos por HTTP siguen bloqueados por fase 2; permiten recuperar acuse histórico propio.
- `cash_command_views.py` y enlaces focales en operations: capacidad exacta, lectura
  previa al efecto y revalidación tras commit; replay conserva identidad/estado de la
  operación original, política vigente y omisión de datos financieros. Correcciones
  Dueño mantienen compensaciones e historia, con id/estado de solicitud en el acuse.
- `cash_legacy_guard.py`: los 18 handlers/aliases mixtos de turno/corte v1 llevan guarda
  explícita; recurso determina sucursal y omitir branch no amplía compatibilidad.
- No se añade migración. Se conserva cálculo canónico de expected/difference, snapshots,
  movimientos/pagos, inventario y reglas aprobadas CC-D01..12.

Precisión técnica única en [SDD F1 §9](../02-SDD-corte-ciego-fase-1.md#9-precisión-de-implementación-f1-05).
PRD y BDD no cambian: se implementa una porción de comportamientos ya aprobados.
Se activaron SDD (contratos concretos), TDD (cobertura), matriz (evidencia parcial)
y este cierre. PRD-FR-289..300 conservan estado global Disenado.

### Evidencia local

| Gate | Resultado / evidencia |
|---|---|
| RED de entrada | Dos aliases reales devolvieron 200 con política activa, donde se exigía 409; `test_corte_ciego_f1_red.py -k active_policy_rejects_legacy_aliases --maxfail=2`. No fallo por ausencia de ruta. |
| API/SQLite F1-05 | 35 passed, 0 skipped: 33 casos API/SQLite y 2 de workspace/intent real. `tmp/corte-ciego-f105-api-final.xml`. Incluye validación y publicación de contratos OpenAPI. Con los 6 PG: 41 pruebas nuevas verdes. |
| PostgreSQL F1-05 | 6 passed, 0 skipped; cuatro órdenes de lectura/autoridad, duplicado de apertura y duplicado de finalización+replay histórico. Incluidos en `tmp/corte-ciego-f105-final.xml` (38 passed: 32 API/SQLite + 6 PG antes del último test de OpenAPI). |
| Regresiones caja | 51 passed en cortes, contratos, apertura/cierre, lifecycle e interlock gateway. La primera corrida omitió el caso PG por su variable preexistente; se ejecutó luego en DB local propia y pasó: `tmp/corte-ciego-f105-close-race.xml`. Total 52 regresiones distintas verificadas. |
| Controles F1-03 | 16 passed; fixtures, Owner real, idempotencia y contratos. Incluidos en `tmp/corte-ciego-f105-sqlite.xml` (63 passed: 22 F1-05 iniciales + 25 RED convertidos + 16 controles). |
| RED F1-03 íntegro | 25 passed, 19 failed, 0 skipped, sin cambiar expectativas. `tmp/corte-ciego-f105-residual-red.xml/.txt`. Los 19 corresponden sólo a reportes/lectores indirectos F1-06. |
| Lint/tipos | ruff focal verde (8 módulos + 3 suites nuevas); mypy verde en los 8 módulos, después del enlace de response_model. |
| Documentación | 9 passed en test_traceability; git diff --check limpio. |

Comandos reproducibles principales:

```powershell
.venv/Scripts/python.exe -B -m pytest apps/api/tests/test_corte_ciego_f105.py apps/api/tests/test_corte_ciego_f105_intents.py -q
# CORTE_CIEGO_TEST_POSTGRES_URL: sólo DB local corte_ciego_* desechable.
.venv/Scripts/python.exe -B -m pytest apps/api/tests/test_corte_ciego_f105_postgres.py -q
.venv/Scripts/python.exe -B -m pytest apps/api/tests/test_user_cash_cuts.py apps/api/tests/test_user_cash_cut_contracts.py apps/api/tests/test_cash_shift_operational_close.py apps/api/tests/test_operational_cash_lifecycle.py apps/api/tests/test_offline_order_cash_close.py -q
.venv/Scripts/python.exe -B -m pytest apps/api/tests/test_corte_ciego_f1_red.py -q
.venv/Scripts/python.exe -B -m pytest tests/architecture/test_traceability.py -q
```

La prueba de carrera heredada exige `PCO004_TEST_POSTGRES_ROUNDTRIP_URL` local pco004_*;
se creó `pco004_f105_20261021_verification` en el cluster temporal puerto 55441, se aplicó
el historial Alembic allí y nunca se apuntó a producción. Los tests nuevos usan schemas
UUID propios bajo `corte_ciego_f104_test`, con 0101 real. CI remoto no se ejecutó.

### Auditoría R3 y refutaciones

Auditor Sol independiente `audit_f105`, contexto fresco, en un único ciclo con
reverificación de sus correcciones. Detectó: lectura de acuse posterior al efecto,
estado/id incorrecto en correcciones, schemas financieros/declaración no cerrados y
revisión de política potencialmente vieja después de commit. Se corrigieron y se
agregaron pruebas; verificación focal posterior, incluido enlace de schemas a FastAPI/OpenAPI, sin hallazgos accionables pendientes.

| Afirmación | Evidencia e intento de refutación | Resultado / riesgo residual |
|---|---|---|
| Estado/acuse no revela finanzas | Importes no nulos; schemas extra=forbid, snapshots antiguos, cero/null/derivados y routes/aliases | Omite campos; lectura propia separada. Pagos/reportes/clientes/IA todavía abiertos según RED F1-06: no activar. |
| Delegación no concede otra sucursal/dataset ni ejecución | Actor acumulado, grant cash.cuts A + sales B, revocación y finalizar con create legacy | Denegación dirigida; preflight/asignaciones reales siguen F1-09. |
| Reintento no ejecuta dos veces ni usa autoridad vieja | Duplicados PostgreSQL, pérdida de capture/read, cambio de política entre commit/salida, conteo histórico después de finalizar | Mismo command_id/acuse; pérdida de read deniega; política cambiada devuelve 409 y misma key recupera. Bytes ya enviados no son revocables. |
| Historia y caja canónica conservadas | Hash de estado tras lecturas/replay/denegaciones, compensación conserva corte original, carrera cierre/pago | Sin reescritura histórica; PG real y SQLite verificados. Nuevo protocolo offline y completitud fase 2 no acreditados. |
| Revocación serializa con materialización | Barreras PG: reader-first y writer-first para revocar y cambiar rol, consulta financiera real | Writer espera al DTO ya autorizado; nuevas lecturas tras confirmación denegadas. No se midió carga/latencia de locks por organización. |

No hubo UI modificada ni QA visual/build frontend. No hubo nuevo esquema, despliegue,
canary ni cambio de datos reales. Suite completa local omitida por GOV-TEST-001; el lote
RED íntegro documenta los pendientes deliberados, sin xfail, exclusiones ni silencios.
F1-06 es el siguiente incremento; F1-05 por sí sola no completa el corte ciego.

## 12. F1-06 — avance de lectores y reportes

Estado: **en curso; no acredita terminar F1-06 ni fase 1**. Autorización vigente:
terminar toda la implementación de fase 1, conservando CC-D01..12. No se activó ninguna
sucursal real ni se modificaron asignaciones, datos o configuración productivos.

Implementado en este lote:

- Guardas vigentes antes de cargar dinero en dashboard, pagos/movimientos legacy,
  reportes de ventas/gastos/envíos, conciliación y Excel; servicios internos de esos
  reportes también validan autoridad. Scope omitido exige cobertura organizacional,
  incluso en páginas vacías. Permisos funcionales anteriores siguen siendo adicionales.
- Reporte operativo v2 con calendario civil de sucursal, tickets distintos confirmados
  y ranking de diez nombres/posiciones, sin cargar importes. Nuevas páginas financieras
  v2 de pagos/movimientos con schemas cerrados, no-store y autorización independiente
  de permisos de escritura.
- Ejecutivo AI comprueba ventas de todas las sucursales y costos administrativos,
  libera transacción antes de red y revalida antes de enviar y devolver. CRM autoriza
  todas las sucursales del historial; origen del cliente no limita sus compras.
  Las notificaciones del dashboard no cargan payload monetario de auditoría de caja.
- Agentes técnicos de ventas/cortes conservan baseline fuera de política nueva, pero
  no acceden a finanzas bajo ella sin un protocolo de audiencia humana aprobado.
- Listado/detalle/PDF/XML fiscal requieren sales además de permiso fiscal; metadata
  de sucursal se resuelve antes de consultar el cuerpo monetario. Descarga revalida
  después del proveedor y no devuelve bytes tras revocación. No se alteró emisión.
- Listados operativos v2 de pedidos/clientes con contratos cerrados. Pedidos conserva
  paginación y filtros del feed POS/web sin hidratar dinero; clientes conserva contactos,
  domicilios, precisión de coordenadas, perfil fiscal y referencia importada sin cargar
  historial de compra/segmento de consumo. Los servicios legacy de clientes también
  comprueban autoridad financiera; origen de sucursal no acota el historial de compras.

Evidencia local acumulada de este lote (sin CI remoto):

- RED inicial íntegro: 19 fallas de autoridad, 25 verdes. Mismo archivo después del
  cambio: **44 verdes**, sin modificar expectativas ni añadir skip/xfail.
- `tmp/corte-ciego-f106-readers.xml`: **95 verdes** (33 casos F1-06, 2 agentes,
  44 del lote inicialmente RED y 16 controles). Incluye calendario, medianoche,
  horario de verano, ranking con empates, SQL sin columnas monetarias, revocación,
  scope y acceso directo a servicios. No prueba por sí solo todo el manifiesto.
- `tmp/corte-ciego-f106-fiscal.xml`: **67 verdes** (5 casos nuevos y 62 regresiones).
- `tmp/corte-ciego-f106-postgres.xml`: **3 verdes**, tablas/FK reales y migración 0101
  en schema desechable. Reporte/página con datos no nulos y ambas órdenes de carrera
  entre lectura de pagos y revocación, verificando espera real de advisory lock.
- Regresiones de ejecutivo/dashboard/conciliación/PCO007/ledger: 66 verdes y una
  falla de compatibilidad inicial; corregida y reejecutada verde individualmente
  (`test_audit_remediation.py -k dashboard`). Total: 67 casos distintos verificados.
  CRM y lectores técnicos baseline: 3 verdes adicionales en `f106-collateral.xml`.
- Schemas publicados y trazabilidad: 12 verdes (3 contratos, 9 arquitectura).
  Ruff focal y mypy de 16 módulos modificados: verdes; `git diff --check` correcto.
  El cluster PostgreSQL desechable se detuvo después de verificar los gates.

Incremento de listados operativos (posterior al lote anterior):

- RED de clientes v2: 404 por contrato todavía inexistente, sólo prueba de funcionalidad
  nueva. RED de seguridad directo: dos servicios legacy devolvían historia sin autoridad
  (`corte-ciego-f106-customer-domain-red.txt`, DID NOT RAISE); corregidos sin alterar
  las expectativas de denegación.
- `tmp/corte-ciego-f106-operational.xml`: **17 verdes**, listados operativos, schemas
  publicados y casos seleccionados de reportes/clientes. Prueba paginación mixta,
  ausencia de SELECT monetario, alcance, permiso vigente y contratos anidados.
- `tmp/corte-ciego-f106-customer-regressions.xml`: **3 verdes**, dos de importación
  legacy y recorrido de múltiples domicilios/consulta/venta del cliente.
- `tmp/corte-ciego-f106-operational-postgres.xml`: **1 verde**, extracción JSON,
  contactos con precisión y feed mixto con cursor sobre tablas/FK reales. La primera
  ejecución detectó un permiso funcional ausente en la fixture; se añadió `orders.read`
  al actor sintético por la vía de permisos real, sin sustituir autorización.
- Mypy focal de los cinco módulos afectados: verde. Ruff focal: verde. No se modificó
  UI ni se publicó este incremento. No acredita contexto monetario individual ni cierre
  de F1-06. Revisión independiente integral y CI del commit siguen en F1-10/11.

Afirmación adicional: buscar/paginar contactos o pedidos no consulta ni devuelve finanzas.
Refutación: importes históricos no nulos, snapshot e importación con campos monetarios,
página vacía de sucursal ajena, permiso retirado, cursor alterado y campo extra anidado.
Resultado: denegaciones/allowlists verificadas en las superficies anteriores. Riesgo residual:
faltan detalle individual, impresión e integración de los consumidores; no activar la política
en usuarios reales. Los textos de contacto introducidos manualmente no son una clasificación
automática de sensibilidad; la garantía cubre campos financieros estructurados.

### Detalle puntual de pedido — F1-06

El servicio de detalle y `GET /api/v2/orders/{id}?expected_version=...` resuelven
autoridad antes de consultar dinero. Reutilizan aceptación auditada, modificación
ejecutada, entrega asignada o reapertura aprobada del actor, según SDD §6. ID, motivo
libre o solicitud pendiente no crean autoridad. La atención ordinaria caduca con cierre
del pedido/turno o pérdida de permisos; historia fuera de contexto requiere `sales`.
Contrato cerrado `attended-order-detail-v2`: conserva importes/partidas/pagos del pedido,
sin snapshots crudos ni consultas a historia de ventas/correcciones/eventos para el
operador. Cada consulta HTTP de detalle y cotización histórica confirma auditoría sin importes.
Un fallo de auditoría o un snapshot no proyectable impide entregar el detalle.

La guarda de escritura de pedidos toma gobierno antes de sucursal. La lectura materializa
bajo gobierno/sucursal/turno/pedido, y conserva los límites transaccionales de los comandos.
No añade tabla ni migra historia. Las solicitudes web por ID mantienen la resolución
canónica y la guarda financiera; fuera de política activa conservan el comportamiento previo.

Evidencia de este incremento:

- RED de seguridad: cuatro actores obtenían detalle por servicio interno sin contexto
  (`tmp/corte-ciego-f106-orders-red.txt`, DID NOT RAISE). Ahora deniega antes de SELECT
  monetario. Pruebas positivas usan venta, modificación, asignación y aprobación reales.
- `tmp/corte-ciego-f106-orders.xml`: **25 verdes**, 16 casos de detalle y 9 de listados
  operativos. Cobertura adicional de snapshot inválido: RED por ValidationError que incluía
  el texto capturado; ahora devuelve error de negocio sin ese contenido. Resultado focal
  en `tmp/corte-ciego-f106-orders-projection-final.txt` (2 verdes, uno de ellos regresión).
  Cierre del módulo de detalle tras esa corrección: `tmp/corte-ciego-f106-orders-final.xml`,
  **17 verdes**, sin omitir casos. Los nueve casos de listados permanecen en el lote anterior.
- PostgreSQL: **2 verdes** en `tmp/corte-ciego-f106-orders-postgres.xml`, ambos órdenes de
  lectura/retiro de permisos con espera real del advisory lock y DTO monetario. Se revocó
  por servicio real la concesión financiera inicial de la fixture para probar sólo atención.
  La prueba del bloqueo de gobierno del escritor falló inicialmente (0 locks compartidos)
  y pasó después de la corrección (`tmp/corte-ciego-f106-orders-lock.txt`, **1 verde**).
- `tmp/corte-ciego-f106-orders-regressions.xml`: **113 verdes**, reapertura, solicitudes
  web, correcciones, cargos de entrega, fencing y runtime de gateway. Una ejecución anterior
  detectó la resolución de IDs web omitida en la guarda HTTP; se corrigió y el lote final pasó.
- `tmp/corte-ciego-f106-orders-contracts.xml`: **59 verdes** (44 RED originales íntegros,
  6 schemas publicados, 9 de trazabilidad). Mypy de seis módulos verde; proyección con
  manejo de errores reverificada focalmente. Ruff focal y diff-check correctos.

Afirmación: un actor no puede convertir una consulta por ID o una solicitud pendiente en
historia monetaria. Refutación: enumeración, motivo/versión inventados, reapertura pendiente,
actor ajeno, retiro de permiso, cierre, snapshot inválido y fallo de auditoría. Resultado:
denegación/contrato cerrado; PG serializa autoridad y lectura. Riesgo residual: faltan
impresión/replays y otras familias del manifiesto; la prueba de la escritura acredita la
barrera, no todas las carreras futuras de transición. No se activa ni se publica este lote.

Señales concretas: `order.detail_read` identifica quién vio qué pedido y con qué origen,
versión y política, sin dinero; 403 identifica falta de autoridad/contexto; 409 distingue
versión/captura incompatible por su código; 503 señala persistencia indisponible. No se
afirma instrumentación global de todos los lectores restantes.

Preguntas operativas de este lote: ¿una consulta fue rechazada por alcance o por cambio
de autoridad? HTTP 403/409 y código de negocio, sin contenido monetario. ¿el proveedor
terminó pero el actor perdió acceso? Revalidación y código de rechazo; revocación conserva
su auditoría canónica. ¿se publicó o activó el cambio? Estado separado Git/CI/despliegue;
este lote sólo tiene evidencia local. Auditoría integral de lecturas y señales pendientes
se comprueban al cerrar F1-10/11, sin afirmar instrumentación que todavía no existe.

| Afirmación | Evidencia / intento de refutación | Resultado y límite |
|---|---|---|
| Paginar o quitar branch no amplía concesión | Lote RED original, páginas vacías, servicios directos, grants exactos y revocación | Deniega en superficies integradas; faltan otras familias del manifiesto. |
| Reporte del encargado no entrega dinero/cantidades | Schema cerrado, observador SQL, ranking con 12 productos, empate e importes no nulos | Sólo nombres/posiciones y tickets; clientes aún no conectados. |
| Revocar durante I/O impide devolver resultado privado | Proveedor sintético revoca grant real en IA y PDF; PostgreSQL disputa lector/revocador | No devuelve resultado posterior a revocación; no retracta bytes ya enviados. |
| Regla no modifica historia ni habilita comandos de caja | Lecturas/proyecciones y capas de autorización; se preservan snapshots/captura bloqueada | No activa fase 2 ni demuestra completitud de sincronización. |

Siguiente trabajo obligatorio dentro de F1-06: extender el contexto a impresión/replays,
completar campos y vistas operativos necesarios de pedidos pendientes, rutas restantes de
historial/integración/intents y contraste completo del manifiesto. Después F1-07 integra
pantallas/sesión; F1-08 verifica colaterales; F1-09 transición/reversión, incluida privacidad
tras suspensión; F1-10 evidencia integral y F1-11 auditoría Sol independiente del conjunto.
No sustituir estos pendientes por las pruebas verdes de este lote.


### Impresión humana — F1-06, avance local

Se protegieron el listado humano y retry en las rutas existentes: metadata cerrada,
sin seleccionar payload/error libre, actor vigente y permiso funcional; retry exige
contexto persistido del pedido incluso para la misma clave. La auditoría de la nueva
cola incluye origen y versiones, sin importes. Error de persistencia no expone SQL;
tokens de audiencia técnica no se admiten como humano. El payload original permanece
intacto. El contenido técnico de la cola y su entrega a dispositivos siguen pendientes.

Evidencia:

- RED válido de cinco casos: salida con PRIVATE-PRINT y servicios que no denegaban
  listado anónimo/retry sin contexto (`tmp/corte-ciego-f106-print-red.txt`). Antes de
  obtenerlo se corrigió la fixture: las rutas de impresión exigen Bearer y permisos
  explícitos; el 401 inicial no se consideró evidencia de la brecha.
- Dos RED adicionales: tokens tipados agent/device devolvían lista como humano
  (`tmp/corte-ciego-f106-print-token-red.txt`). Ahora deniegan ambos endpoints.
- `tmp/corte-ciego-f106-print.xml`: **8 verdes**, incluida pérdida de contexto en replay,
  ausencia de consultas a payload/error y rollback completo por fallo de auditoría.
- `tmp/corte-ciego-f106-print-postgres.xml`: **1 verde**, esquema/FK reales, lectura,
  retry/replay, cierre posterior y payload inalterado. No sustituye carreras de revocación
  de otras superficies ni acredita todavía despacho técnico por dispositivo.
- Regresiones operativas/workspace/auditoría: **47 verdes y 1 fallo inicial** en
  `tmp/corte-ciego-f106-print-regressions.xml`. La reserva SQLite impedía alcanzar una
  barrera puesta dentro del bloqueo; se movió al inicio concurrente del comando,
  conservando todas las aserciones y sin silenciar excepciones. Caso corregido:
  **1 verde** en `tmp/corte-ciego-f106-print-concurrency.xml`.
- Mypy de tres módulos y Ruff focal verdes; trazabilidad: 9 verdes; diff-check correcto.
  No hubo CI remoto, cambio UI, publicación ni activación productiva.

Afirmación: listar/reintentar trabajos humanos no recupera snapshots monetarios ni
convierte la clave previa en autoridad. Refutación: payload y error con marcador privado,
SELECT observado, ID conocido, contexto retirado/cierre, audiencia técnica, fallo de
persistencia y reintentos simultáneos. Resultado: denegación o metadata explícita,
con un intento y payload original conservado. Riesgo residual: faltan frontera técnica,
replays restantes y transición; no activar la política en sucursales reales todavía.

Preguntas operativas: ¿por qué se autorizó el retry? `print_job.retried` registra
origen/versión/actor. ¿se duplicó el intento? clave estable, mismo attempt_id y contador
canónico. ¿falló almacenamiento? 503 sin contenido privado; si el commit ya ocurrió,
la misma clave recupera el acuse sólo conservando autoridad. Próximo bloque: entrega
técnica de trabajos y payload de cocina, luego replays e integración restantes antes de F1-07.


### Dispositivos de impresión — F1-06, avance local

La cola técnica bajo política activa entrega metadata sin payload (límite 100,
orden determinista, timestamp UTC). Claim valida credencial persistida vigente;
la ruta nueva `/print-attempts/{attempt_id}/payload` sólo entrega el trabajo CLAIMED
al dispositivo asignado de esa organización/sucursal. La proyección cerrada de cocina
omite dinero incluso dentro de modificadores; ticket conserva los datos propios de
la operación y descarta recetas/costos/snapshots extras. Se conserva el original.
La lectura audita y vuelve a validar después de commit, sin SQL en errores.

Evidencia local:

- RED de seguridad: pull devolvía snapshots y servicios permitían omitir o inventar
  dispositivo. Los 404 de la ruta nueva se registran como RED de funcionalidad, no
  como prueba de seguridad (`tmp/corte-ciego-f106-print-devices-red.txt`).
- `tmp/corte-ciego-f106-print-devices.xml`: **13 verdes**, incluidos dos contratos
  publicados, aislamiento de dispositivo, fin/revocación, SQL sin payload ante
  denegación, contenido anidado, error privado y revocación después de audit commit.
- Metadata de cola ajustada a DTO/timestamp UTC y reverificada: **1 verde** en
  `tmp/corte-ciego-f106-device-queue-final.txt` (subconjunto del módulo anterior).
- `tmp/corte-ciego-f106-device-postgres.xml`: **2 verdes**, ambos órdenes lector/
  revocador. Espera real comprobada con pg_blocking_pids, credencial/FK reales,
  materialización y auditoría reales; la barrera sólo ordena la concurrencia.
- `tmp/corte-ciego-f106-device-regressions.xml`: **48 verdes**, operativas, workspace
  y auditoría, incluida concurrencia SQLite previamente adaptada.
- Mypy de tres módulos, Ruff focal, 9 de trazabilidad y diff-check: verdes. Cluster
  PostgreSQL desechable detenido y pidfile ausente. Sin CI remoto, UI ni producción.

Afirmación: descargar contenido exige asignación y credencial vigentes; cocina no
transporta importes estructurados. Refutación: descarga antes de claim, dispositivo
ajeno, credencial retirada, intento terminado, SELECT observado, marcador privado,
modificador con precio/costo y revocación compitiendo con lectura en PostgreSQL.
Resultado: denegación o proyección cerrada; auditoría sin contenido. Riesgo residual:
los bytes entregados antes de revocar no se retractan; compatibilidad del spooler real
no demostrada. La búsqueda en apps/tests y referencias del repositorio no encontró un
consumidor de impresión ejecutable: F1-09 debe exigir evidencia del protocolo nuevo
antes de permitir activación. No se creó ni configuró una impresora externa.

Preguntas operativas: ¿quién descargó qué trabajo? `print_attempt.payload_read` conserva
id/dispositivo/tipo; ¿por qué no hay contenido? 403 por alcance/asignación o credencial,
409 por snapshot/política y 503 por persistencia, sin valores privados; ¿terminó impresión?
se mantienen claim/ack/fail/recovery y sus estados/auditoría canónicos.

Siguiente: revisar snapshots de respuesta de pedidos/pagos/reintentos e intents, más
las vistas pendientes de revisión operativa, y contrastar familias restantes del inventario.
F1-06 continúa abierto; F1-07..11 siguen pendientes. Este incremento no equivale a
terminar corte ciego ni habilitar una sucursal.


### Acuses de alta de pedido y pago — F1-06, avance local

Alta/recuperación de pedido y confirmación/replay de pago bajo política activa devuelven
acuse propio sin dinero, publicado como `order-command-receipt-v2`. El comando conserva
su snapshot original. Los replays seleccionan metadata, no response_snapshot ni total
del pedido. Lectura actual (`orders.read`), actor y sucursal se revalidan; perder sólo
escritura permite recuperar el acuse propio, no ejecutar una operación nueva. Se comprueba
lectura antes del efecto. Vista previa de pago exige contexto de pedido, conserva precio/
cambio y confirma auditoría con revalidación posterior. No se implementaron pantallas.

Evidencia:

- RED inicial válido: recuperación sin proyección cerrada, recuperación rechazada por
  perder sólo escritura, pago con respuesta monetaria y preview que no denegaba al
  perder contexto. Una ruta mal escrita en la primera ejecución se corrigió antes de
  tomar evidencia (`tmp/corte-ciego-f106-command-receipts-red.txt`, 4 fallas y 1 verde).
- `tmp/corte-ciego-f106-command-receipts.xml`: **43 verdes**, cinco casos iniciales
  más detalle e impresión humana/técnica con la fixture de alta adaptada al acuse.
  Precio 9500 permanece comprobado en detalle autorizado y preview, no se borró su prueba.
- `tmp/corte-ciego-f106-receipts-final.xml`: **10 verdes**, módulo extendido con
  SQL sin snapshot/total en replay, preflight sin efecto, fallo posterior al commit y
  recuperación sin duplicar, HTTP preview auditado y schema publicado/runtime.
- `tmp/corte-ciego-f106-receipts-regressions.xml`: **30 verdes**, cobro/impresión,
  idempotencia de pago/alta, recuperación y snapshots malformados, pedido pendiente,
  carrera SQLite y rollback de snapshots de pago, cálculo exacto de efectivo.
- `tmp/corte-ciego-f106-receipts-postgres.xml`: **2 verdes**, pago real duplicado
  concurrente da un solo efecto/acuse; rollback del llamador con commit=False revierte
  pago y auditoría. Tablas/FK reales; snapshots guardan el importe original 5678.
- Mypy de tres módulos, Ruff focal, nueve de trazabilidad y diff-check: verdes.
  Sin CI remoto, UI, publicación ni producción; se detuvo el cluster desechable.

Afirmación: poseer una clave no concede importes históricos ni otro pago; retirar sólo
escritura no impide consultar el acuse propio autorizado. Refutación: retiro diferenciado
read/write, cierre de pedido/turno, SQL observado, fallo después de confirmar, duplicados
concurrentes y transacción exterior revertida. Resultado: metadata propia o denegación;
efectos históricos originales se conservan. Riesgo residual: intents históricos, otras
mutaciones/liquidaciones y consumidores aún requieren integración; suspensión/transición
seguras permanecen F1-09. No se afirma que todo replay del inventario esté protegido.

Preguntas operativas: ¿hubo efecto aunque falló el acuse? misma clave referencia el
comando/pago único; ¿quién recuperó el acuse? `operational_command.receipt_read` registra
actor/acción/pedido/política sin importes; ¿se perdió permiso o persistencia? 403/503
sin snapshots/SQL. No interpretar el 503 posterior a commit como cancelación del pago.

Próximo bloque: `operational_intents` (respuestas guardadas antes de la política),
liquidaciones y replays restantes; después contraste final de familias y F1-07.
F1-06 y el objetivo de fase 1 permanecen abiertos.

### Recuperación de solicitudes operativas — F1-06, avance local

Se verificó que el intent ya devolvía metadata, pero su prueba cargaba snapshots
monetarios completos y no exigía lectura vigente del acuse. Ahora preparar/ejecutar/
listar/resolver validan el permiso de lectura propio por tipo/sucursal bajo la política,
antes del efecto y después del commit. Recuperar no exige volver a tener escritura.
Las rutas humanas rechazan tokens técnicos. La evidencia usa IDs/columnas explícitas
y extracción JSON; compensaciones conservan sus enlaces e igualdad exacta en SQL.
No se alteran resultados históricos ni estados canónicos.

Evidencia local:

- RED inicial en `tmp/corte-ciego-f106-intents-red.txt`: carga de snapshot/total,
  audiencia técnica y retiro de lectura de caja. Los negativos de `orders.read`
  necesitaron corregir la fixture: el actor conservaba autoridad organizacional
  alternativa. Se retiró sólo en datos sintéticos y se otorgaron permisos explícitos;
  borrar una fila de permiso sin quitar esa autoridad no constituye revocación efectiva.
- `tmp/corte-ciego-f106-intents-final.xml`: **9 verdes**, recuperación de alta real
  anterior a la política, lectura/escritura separadas, denegación sin resolver,
  preparación sin efecto al faltar lectura, audiencia humana, permiso de caja propio,
  revocación después de commit y rollback ante fallo de auditoría sin SQL privado.
- `tmp/corte-ciego-f106-intents-postgres.xml`: **3 verdes**, apertura/cierre reales y
  referencias JSON, compensación real con refutaciones de importe/dirección/enlace,
  recuperación simultánea con una única transición/auditoría. Base/FK reales aisladas;
  se corrigieron errores de fixture (workspace de sucursal única, permisos de concepto,
  evidencia obligatoria y forma real del acuse de apertura), sin debilitar el dominio.
- `tmp/corte-ciego-f106-intents-integrated.xml`: **46 verdes**, las nueve pruebas
  nuevas, 28 regresiones de intents/turnos y nueve de trazabilidad, sin skips. Las
  nueve nuevas están incluidas en 46; no se suman nuevamente. Con PostgreSQL son
  **49 casos verdes** para este incremento, no para toda la fase 1.
- Mypy de `operational_intents.py` y `api.py`, Ruff focal y diff-check verdes.
  PostgreSQL desechable detenido, pidfile ausente. No hubo publicación, CI remoto,
  cambio de UI ni actuación sobre producción.

Afirmación: un intent previo no renueva autoridad de lectura ni requiere cargar su
respuesta financiera histórica para probar el efecto. Refutación: retiro efectivo de
read/write, credencial técnica, SQL observado, pérdida de lectura después de commit,
auditoría fallida, compensación inconsistente y resoluciones simultáneas. Resultado:
acuse mínimo o denegación, efecto y evidencia conservados. Riesgo residual: las
respuestas de los comandos de movimientos de caja/liquidaciones aún se deben proyectar;
proteger la recuperación del intent no acredita todos sus callbacks. La suspensión de
política y clientes antiguos siguen pendientes de F1-09; no activar sucursales todavía.

Preguntas operativas: ¿el comando se aplicó o quedó sin efecto? Estado y resource_id
del acuse autorizado; ¿se resolvió dos veces? Una transición y auditoría canónica;
¿se confirmó pero se perdió lectura al responder? 403/409, sin revertir el efecto
confirmado; ¿falló persistencia? 503 sin SQL/payload y recuperación con la misma identidad.

Siguiente bloque: respuestas de movimientos de caja y liquidaciones, replays restantes
y contraste del inventario; después F1-07 integra pantallas y sesiones. F1-06 sigue abierto.

### Acuses de movimientos de caja — F1-06, avance local

Las fronteras humanas de alta/compensación envuelven el núcleo canónico y entregan
`CashMovementReceiptV2` bajo política activa. No envían movimiento monetario, concepto
libre, evidencias ni resúmenes almacenados/actuales. Replays leen sólo referencias y
metadata; determinan sucursal desde el comando persistido, revalidan actor/lectura y
conservan el snapshot original. Una acción nueva requiere las guardas originales de
escritura, Dueño para compensar y protección de movimientos vinculados a documentos.
`commit=False` conserva la transacción exterior. Los endpoints rechazan audiencia
técnica y devuelven errores seguros/no-store.

El único consumidor interno del resultado completo, reconciliación de caja del
gateway, llama al núcleo después de sus guardas existentes de credencial, lease,
actor y alcance. Su acuse técnico continúa limitado a id/estado; no se amplía ni
se convierte en permiso financiero humano. No se editó el gateway ni se activó una
política real. Se publicó el schema del acuse y se actualizaron SDD/BDD/TDD/matriz;
PRD mantiene las reglas aprobadas.

Evidencia local:

- `tmp/corte-ciego-f106-movements-red.txt`: **6 RED** por respuestas monetarias,
  replays, falta de lectura y audiencias técnicas. Una aserción SQL posterior confundía
  referencia JSON_EXTRACT con selección del snapshot completo; se corrigió para
  inspeccionar las columnas proyectadas, manteniendo los negativos de importes.
- `tmp/corte-ciego-f106-movements-integrated.xml`: **55 verdes**, diez casos nuevos
  más ledger, lifecycle/intents y reconciliación central PCO-008. Incluye revocación
  tras commit, rollback por auditoría y ejecución/replay/recuperación de intent real.
- `tmp/corte-ciego-f106-movements-postgres.xml`: **6 verdes**, tres nuevos de
  duplicado real, rollback exterior y fallo de auditoría, más tres de intents.
  Se adaptó la prueba de compensación a la referencia del acuse; sus importes se
  siguen verificando en el ledger y sus refutaciones de integridad se conservaron.
- `tmp/corte-ciego-f106-movement-active-sync.xml`: **1 verde adicional**, transporte
  real con lease sintética/criptografía inyectada y política activa, acuse mínimo,
  replay único y denegación de lectura humana. No acredita entrega offline integral.
- `tmp/corte-ciego-f106-movement-last.xml`: reverificación focal de sync y actor/
  sucursal ajenos, incluida en los casos anteriores; no sumar como cobertura distinta.
- `tmp/corte-ciego-f106-movement-trace.txt`: **9 verdes**. Mypy de tres módulos,
  Ruff focal y diff-check verdes. Sin CI remoto, publicación, UI ni producción.

Afirmación: una respuesta humana/replay no revela el saldo de caja y no cambia la
historia para ocultarlo. Refutación: snapshot anterior a política, retiro read/write,
actor/sucursal cambiados, token técnico, SQL observado, auditoría fallida, revocación
tras commit, duplicados y rollback exterior. Resultado: acuse cerrado o denegación,
un solo movimiento y snapshot intacto. Riesgo residual: F1-06 aún tiene liquidaciones,
otras familias del inventario y consumidores pendientes; suspensión/compatibilidad
siguen en F1-09. La auditoría independiente del conjunto corresponde a F1-11.

Preguntas operativas: ¿se registró aunque falló la entrega? Reintento/recuperación con
la misma identidad y resource_id; ¿quién consultó el acuse? `cash_movement.receipt_read`
sin importes; ¿se duplicó o falló almacenamiento? command_id/replay y 503 seguro,
con ledger/snapshot/auditoría atómicos. No interpretar un rechazo posterior a commit
como cancelación del movimiento.

Siguiente: liquidaciones de repartidores, incluyendo totales de candidatos, snapshot
de respuesta y métrica con importe, después lectores restantes y F1-07. Este bloque
no cierra la fase 1 ni habilita el corte ciego integral.

### Liquidaciones de repartidores — F1-06, avance local

El selector conserva repartidores activos y pendientes de inactivos/trasladados sin
sumar importes bajo política activa. La confirmación y sus replays entregan un acuse
cerrado; pagos, items y snapshots monetarios internos se conservan. Recuperación por
cuerpo/clave originales sólo lee un comando propio existente con permiso vigente y
no exige mantener escritura ni workspace. Confirmar nuevo lote sí conserva cobro,
workspace, caja abierta y reglas de elegibilidad. La métrica de resultado ya no lleva
importe. Rutas humanas/no-store, errores SQL seguros y revalidación tras commit.

Evidencia local del incremento:

- `tmp/corte-ciego-f106-settlements-red.txt`: cinco RED por suma del selector,
  respuesta/replay monetarios y audiencias técnicas; no se contabiliza como RED válido
  la ausencia inicial de la ruta de recuperación. El preflight sin lectura ya fallaba
  por la guarda de los pagos hijos; ahora se exige antes de consultar el lote monetario.
- `tmp/corte-ciego-f106-settlements-integrated.xml`: **12 verdes**, once pruebas
  nuevas de contratos/HTTP/autoridad y la regresión integral de liquidaciones anterior.
  Incluye pendientes de repartidor trasladado/inactivo, recuperación sin workspace,
  snapshot histórico intacto, SQL sin importes en replay, scopes e identidades ajenas,
  fallo de auditoría y revocación posterior a commit. Sin skips.
- `tmp/corte-ciego-f106-settlements-postgres.xml`: **3 verdes**, misma clave y
  claves distintas concurrentes, un lote/dos pagos por 28500, snapshot original íntegro
  y rollback completo si falla la auditoría del acuse. Esquemas desechables con FK reales.
- `tmp/corte-ciego-f106-settlement-trace.txt`: **9 verdes**. Mypy de tres módulos y
  Ruff focal y diff-check verdes. Schemas cerrados de candidato/acuse guardados localmente
  y comprobados por paridad; OpenAPI describe las dos proyecciones compatibles.
- Son **15 pruebas funcionales distintas más 9 de trazabilidad**; no sumar las
  reverificaciones scope/actor sobre la suite integrada. PostgreSQL temporal detenido,
  pidfile ausente. La suite completa y CI del paquete continúan pendientes de F1-10.
- Se corrigieron dos datos de fixture del actor alternativo: código de empleado de
  seis caracteres y rol organizacional sin sucursal. No son fallos de negocio ni RED
  de autorización. También se comparó el snapshot con su valor persistido original:
  HTTP normaliza UTC a Z, mientras el JSON histórico conserva +00:00.

Afirmación: el operador conserva liquidación/recuperación sin acceso al importe
agregado y sin duplicar cobros. Intentos de refutación: replay histórico, retiro de
read/write, actor/cuerpo/sucursal ajenos, token técnico, revocación después de commit,
auditoría fallida, clave desconocida y dos cobros concurrentes. Resultado: acuse
cerrado o denegación, con historia y atomicidad conservadas en los casos probados.
Riesgo residual: POS aún consume el contrato previo (F1-07); suspensión/compatibilidad
de política y revisión individual siguen en F1-09, y auditoría del conjunto en F1-11.
No activar sucursales por este resultado. No hubo CI remoto, publicación ni producción.

Preguntas operativas: ¿se confirmó el lote? command_id/id/estado del acuse y auditoría
canónica; ¿se repitió? métrica success/replay sin importe y mismas referencias;
¿se confirmó pero se perdió lectura? denegación tras commit, recuperación posterior
con permiso vigente, sin interpretar el rechazo como anulación; ¿falló persistencia?
503 seguro y rollback del lote antes de commit.

Siguiente: completar contraste de ORDER/INTENT y demás lectores pendientes del
inventario. La inspección distingue fulfillment (snapshot actual sólo id/estado/tipo)
de aplicación de correcciones, que aún conserva importes en su respuesta/replay.
No asumir que todo snapshot es monetario ni que toda familia ya está cerrada.
Después sigue F1-07, pantallas y sesiones. F1-06 permanece abierto.

### Reapertura y corrección de pedidos — F1-06, avance local

Las respuestas de solicitud/decisión ya eran operativas; aplicación y replay podían
devolver delta y compensación monetaria. La frontera común ahora entrega acuses
cerrados bajo política activa, exige actor original y lectura vigente, separa replay
de nueva escritura y revalida tras commit. El listado no carga before_snapshot.
El núcleo conserva permisos, fórmulas, compensaciones y snapshots; sólo cede el commit
al envoltorio cuando hay acuse activo para incluir su auditoría atómicamente.
El detalle financiero autorizado del pedido sigue mostrando la corrección histórica.

Evidencia local:

- `tmp/corte-ciego-f106-reopen-red.txt`: **6 RED**, acuse/aplicación/replay, listado
  que carga before_snapshot y audiencias técnicas. La solicitud inicial carecía del
  contrato nuevo; no se afirma que su DTO anterior tuviera importes estructurados.
- `tmp/corte-ciego-f106-reopen-integrated.xml`: **78 verdes**, seis casos nuevos y
  72 regresiones de reapertura/correcciones/contratos canónicos.
- `tmp/corte-ciego-f106-reopen.xml`: **10 verdes**, los seis anteriores más rollback
  de corrección, revocación tras commit, acceso financiero del Dueño revisado y schema.
- `tmp/corte-ciego-f106-reopen-boundaries.xml`: **3 verdes adicionales**, rollback
  de solicitud/decisión con auditoría y actor inactivo ante listado vacío. Este último
  ya estaba protegido por require_permission; no se inventó un cambio de dominio.
  El fallo inicial del inyector de auditoría se corrigió para aceptar el argumento
  `action` tanto por nombre como por posición; no fue un fallo de persistencia.
- `tmp/corte-ciego-f106-reopen-postgres.xml`: **3 verdes**, misma clave/claves distintas
  concurrentes, una compensación por -500 con pago original 500 y rollback real del
  efecto/acuse. Esquemas aislados y FK reales; PostgreSQL temporal detenido.
- `tmp/corte-ciego-f106-reopen-trace.txt`: **9 verdes**; mypy de tres módulos, Ruff
  focal y diff-check verdes. Se mantiene la verificación focal del rechazo legacy
  sin cuerpo completo en `tmp/corte-ciego-f106-reopen-legacy.txt`.

Son 13 casos nuevos de lectura/contratos, 72 regresiones y tres casos PostgreSQL:
**88 funcionales distintos**, más nueve de trazabilidad. Las reverificaciones no
se suman de nuevo. No hubo CI remoto, publicación, cambio de UI ni producción.

Afirmación: recuperar no transfiere el resultado financiero ni crea otra corrección.
Evidencia/refutación: identidad distinta, retiro de escritura/lectura, SQL observado,
revocación tras confirmar, auditoría fallida y dos solicitudes concurrentes. Resultado:
acuse cerrado o denegación; compensación e historia originales permanecen vinculadas.
Riesgo residual: adaptación POS, compatibilidad/suspensión de política y auditoría del
conjunto siguen pendientes en F1-07/09/11. Este bloque no certifica todos los lectores.

Preguntas operativas: ¿se aplicó la corrección? id del comando/solicitud/corrección y
estado histórico del acuse; ¿quién recuperó? auditoría order.reopen.receipt_read sin
importe; ¿falló antes o después de confirmar? 503 previo revierte el efecto, denegación
posterior no lo anula y permite recuperar con autoridad vigente. Los eventos canónicos
mantienen su evidencia financiera interna bajo los permisos correspondientes.

Siguiente hallazgo concreto: `amend_order` conserva una salida histórica
`after_snapshot.delivery_response` que sólo revisa orders.read en ese camino.
Se debe contrastar con el contexto puntual y la revocación antes de cerrar ORDER.
Después quedan gastos y payloads de logs de integración dentro de F1-06; las
adaptaciones de catálogo/recepción permanecen en F1-08. F1-06 continúa en curso.

### Modificaciones de pedidos — F1-06, avance local 2026-10-22

La modificación ahora devuelve un acuse operativo bajo política activa. Recuperar
una clave propia exige lectura vigente y no reejecuta el cambio; las respuestas
históricas de envío quedan internas. La nueva ruta de recuperación permite consultar
metadata histórica aunque no exista hash antiguo. Un POST de ejecución sin hash
demostrable exige esa recuperación explícita; no reconstruye una intención supuesta.
Los nuevos comandos guardan hash completo, incluido carrito sin envío. Las reglas
de versión, pago, producción, reservas y tarifas permanecen en el núcleo existente.

Evidencia local:

- `tmp/corte-ciego-f106-amendments-red.txt`: cuatro fallos esperados iniciales
  (acuse, respuesta histórica de envío y dos audiencias técnicas), un control verde.
- `tmp/corte-ciego-f106-amendments-integrated.xml`: **72 verdes**, trece pruebas
  nuevas y regresiones de envío, POS, fencing offline y contexto puntual de pedidos.
- `tmp/corte-ciego-f106-amendments-postgres.xml`: **4 verdes**, misma clave y claves
  distintas concurrentes, rollback exterior commit=False y fallo de auditoría.
  Esquemas aislados/FK reales; PostgreSQL temporal detenido y pidfile ausente.
- `tmp/corte-ciego-f106-amendments-boundaries.xml`: **5 verdes**, tres casos
  históricos reverificados con actor existente y dos nuevos de lectura previa y
  actor ajeno vigente. La selección focal no sustituye la suite de trazabilidad.
- `tmp/corte-ciego-f106-amendments-trace.txt`: **9 verdes**. Ruff focal, mypy
  de cuatro módulos (`...amendments-mypy.txt`) y `git diff --check` verdes.
- `tmp/corte-ciego-f106-amendments-combo.txt`: **1 regresión verde** de cambios
  sucesivos de combo y cancelación final sin reserva remanente.

Son **79 pruebas funcionales distintas** (15 nuevas HTTP/dominio, 60 regresiones y
cuatro PostgreSQL), más nueve de trazabilidad. Sin CI remoto ni publicación.

Afirmación: recuperar el acuse no revela dinero histórico ni modifica otra vez.
Evidencia/refutación: SQL observado sin snapshots/totales, cambio de cuerpo,
actor ajeno/nulo, pérdida de lectura/escritura, revocación posterior a commit,
auditoría fallida, rollback exterior y dos solicitudes concurrentes. Resultado:
acuse cerrado o denegación, una modificación efectiva y snapshots conservados.
Riesgo residual: POS todavía debe consumir el acuse y consultar detalle separado;
transición/suspensión siguen en F1-09 y auditoría independiente integral en F1-11.

Preguntas operativas: ¿se aplicó? command_id/versión histórica del acuse; ¿quién
recuperó? auditoría order.amendment.receipt_read sin importes; ¿falló antes o después
del commit? fallo previo revierte, denegación posterior conserva el efecto y permite
recuperarlo con lectura restituida. No se modifica ninguna configuración productiva.

Siguiente: logs de integración y gastos dentro de F1-06; después F1-07. Se confirmó
que las cuatro rutas de logs (Uber Eats, DiDi Food, Rappi y WhatsApp) llaman a
`ChannelIntegrationService.list_webhook_logs` y devuelven payload_raw/error libres
con admin.manage. Según SDD §7 deben entregar metadata segura; el log no contiene
sucursal resuelta que permita atribuir automáticamente autoridad sobre el original.
El consumidor Admin `IntegrationsHub` utiliza tipo/evento, estado, fecha y event_id;
su contrato seguro debe reflejarse en F1-07. Este hallazgo aún no está corregido.

### Logs de integraciones — F1-06, avance local 2026-10-22

El hallazgo anterior queda corregido para las cuatro listas humanas. El servicio
también exige actor vigente y permiso administrativo antes de consultar; bajo
protección devuelve metadata cerrada y no carga payload, firma, errores ni campos
externos libres. Estado error/failed conserva el diagnóstico; otros valores no
reconocidos se muestran como unknown. El original no se borra ni se reescribe.
Como no existe sucursal resuelta por registro, la lista no acepta un filtro como
prueba de acceso al original. Suspender política no elimina esta protección.

Evidencia local:

- `tmp/corte-ciego-f106-logs-red.txt`: **11 fallos esperados** por payload/columnas
  sensibles y credenciales técnicas; `...logs-initial.txt` convierte esos 11 a verde.
- `tmp/corte-ciego-f106-logs-integrated.xml`: **47 verdes**, 23 casos nuevos y
  24 regresiones de Uber Eats, DiDi Food, Rappi y WhatsApp.
- `tmp/corte-ciego-f106-logs-postgres.xml`: **2 verdes**, proyección del estado,
  original conservado y fallo de auditoría con esquemas/FK reales aislados.
- `tmp/corte-ciego-f106-logs-final.xml`: **11 verdes**, estado error del servidor,
  schema reverificado y nueve de trazabilidad.
- Ruff focal, mypy de tres módulos (`...logs-mypy.txt`, proyección reverificada en
  `...logs-final-mypy.txt`) y diff-check verdes. PostgreSQL temporal detenido.

Total sin duplicar reverificaciones: **50 funcionales distintos y 9 de trazabilidad**.
Sin CI remoto, commit, push, despliegue ni cambios de UI en este incremento.

Afirmación: metadata de diagnóstico no habilita exportar originales no atribuidos.
Evidencia/refutación: cuatro proveedores/Dueño/administrador, texto privado anidado,
SQL observado, actor ajeno/inactivo/sin permiso, llamada de servicio sin identidad,
token técnico, límites negativos, parámetros de payload/sucursal, suspensión,
fallo de auditoría, revocación y activación entre commit y entrega. Resultado:
metadata segura o denegación; originales intactos. Riesgo residual: IntegrationsHub
todavía consume tipo/event_id antiguos y se adapta en F1-07; no hay descarga del
original sin procedencia demostrada. Auditoría independiente integral sigue F1-11.

Preguntas operativas: ¿hubo recepción o error? estado enumerado/fecha/proveedor;
¿qué registro investigar? id interno; ¿quién consultó? auditoría integration.logs.read
con actor/proveedor y sin contenido. Fallo de persistencia devuelve 503 seguro.

Siguiente: cerrar gastos (consulta puntual, lista, resumen, comandos y recuperación),
manteniendo autoridad administrativa/retiros/compensaciones y los originales. Después
contrastar las superficies restantes del inventario antes de pasar a F1-07. F1-06
y la fase 1 siguen en curso; este bloque no constituye activación del corte ciego.

### Gastos — F1-06, avance local 2026-10-22

Lista/resumen monetarios requieren expenses; lista v2 y cash-context sólo metadata.
Detalle de borrador propio exige contexto de edición ejecutada y versión vigente;
historial financiero sigue separado. Comandos/recuperaciones entregan acuses cerrados,
conservan originales y abandono terminal, retiros y compensaciones. Las fronteras son
humanas/no-store y revalidan la autoridad tras commit.

Evidencia local, sin sumar dos veces casos repetidos:
- `tmp/corte-ciego-f106-expenses-integrated.xml`: 66 verdes (9 nuevos y 57 regresiones).
- `...expenses-boundaries.xml`: 15 verdes; `...expenses-final.xml`: 10 verdes (incluye
  nueve de trazabilidad). El último añadido había separado incorrectamente dos pruebas;
  se corrigió la estructura sin cambiar expectativas y se ejecutó el archivo completo.
- `...expenses-verified.xml`: 17 verdes, incluyendo scopes exactos/revocación y cambio
  de versión después del commit de auditoría, antes de entregar un borrador.
- `...expenses-postgres.xml` y `...expenses-legacy-postgres.xml`: 5 + 5 verdes con
  PostgreSQL aislado real, confirmación/abandono concurrentes y atomicidad de auditoría.
- Ruff focal verde; mypy de fuentes registrado en `...expenses-mypy.txt` y
  `...expenses-final-mypy.txt`. Unión de JUnit: **84 funcionales y 9 de trazabilidad**.

Afirmación: operar un gasto no permite consultar su historia monetaria ni multiplicar
el movimiento. Evidencia/refutación: replay sin escritura, lectura revocada, actor
distinto, dataset/sucursal cruzados, consulta SQL observada, error de auditoría,
abandono frente a confirmación y modificación del borrador en vuelo. Resultado:
acuse/proyección autorizada o rechazo; retiros y originales conservados. Riesgo residual:
ExpensesWorkspace sigue pendiente en F1-07; transición/suspensión y auditoría integral
permanecen F1-09/11. No se ha ejecutado CI ni publicado/activado este incremento.

Preguntas operativas: ¿se ejecutó o abandonó? estado/id del comando; ¿quién consultó?
auditoría de lectura con actor/sucursal/política; ¿se perdió acceso durante la respuesta?
denegación vigente y recuperación autorizada, sin devolver errores SQL ni importes.

Siguiente dentro de F1-06: respuestas de cancelación y contraste final de ORDER antes
de adaptar pantallas. Gastos verificado no equivale a cerrar todos los lectores.

### Cancelación de pedidos — F1-06, avance local 2026-10-22

Se reprodujo la fuga del registro completo de pedido (importe y snapshots de cliente)
en la respuesta de cancelación. Bajo política activa ahora se entrega el contrato
cerrado order-cancellation-receipt-v2, con lectura y cancelación independientes,
identidad humana y no-store. La serialización por sucursal precede a la lectura de
estado; efecto y auditoría comparten commit. No se cambia la regla de duplicados ni
la clasificación de cancelaciones producidas. commit=False pertenece al llamador.

Evidencia local:
- `tmp/corte-ciego-f106-cancel-red.xml`: dos RED por respuesta monetaria y cancelación
  sin lectura; `...cancel-initial.xml`: ambos convertidos a verde.
- `...cancel-integrated.xml`: **16 verdes**, 12 casos de proyección/autoridad/atomicidad
  y cuatro regresiones canónicas de cancelación antes/después de producción.
- `...cancel-postgres.xml`: **2 verdes**, dos cancelaciones concurrentes producen una
  cancelación/liberación y un rechazo; fallo de auditoría revierte estado y movimientos.
- `...cancel-regressions.xml`: **36 verdes**, 27 regresiones de combos/canales/fencing
  offline y nueve de trazabilidad. **Total: 45 funcionales distintos y 9 de trazabilidad**.
- Ruff de fuentes/pruebas y mypy de operations/api/order_cancellation_views verdes.

Afirmación: el acuse no habilita historia monetaria ni duplica el efecto. Refutación:
importe no nulo, contrato exacto, actor sin lectura o sin cancelación, audiencias técnicas,
revocación tras commit, activación durante respuesta legacy, fallo de auditoría,
rollback del llamador y carrera PostgreSQL. Resultado: acuse o denegación, importe
original intacto y una sola liberación. Merma/recuperación conservan sus cantidades.
Riesgo residual: la autorización exacta CC-D08 se verifica en F1-08, clientes en F1-07,
privacidad tras suspensión en F1-09 y auditoría independiente integral en F1-11.

Preguntas operativas: ¿se canceló? estado operativo y evento ORDER_CANCELLED;
¿quién recibió el acuse? auditoría order.cancellation.receipt_read;
¿falló antes o después de persistir? error seguro y consulta operativa vigente. Una
revocación posterior no deshace la cancelación ni permite entregar el registro original.

Siguiente: contrastar aceptación pública/pendiente y respuestas de asignación/estado de
ORDER, incluidas identidades y revalidación tras commit. La revisión estática encontró
accept_pending_order llamando get_order_detail después del commit; falta demostrar
su comportamiento bajo la política nueva. No se presenta como defecto dinámico probado.
F1-06 sigue abierto. No hubo CI remoto, commit/push ni cambios productivos.

### Aceptación y asignación — F1-06, avance local 2026-10-22

Las dos rutas de aceptación pública, la aceptación de pendientes y la asignación de
repartidor entregan OrderAcceptanceReceiptV2 bajo política. Se separa el acuse del
importe/domicilio histórico. Recuperación exige lectura vigente y prueba del actor
original; perder escritura no impide recuperar, y sólo el efecto nuevo exige fence
de escritura. La aceptación pública serializa su clave organizacional antes del
bloqueo de sucursal; la aceptación de pendiente exige el hecho PENDING a ACCEPTED.
Efecto y auditoría comparten commit; commit=False conserva el control del llamador.

Evidencia local:
- `tmp/corte-ciego-f106-acceptance-red.xml`: tres RED reales por exposición de
  importes/snapshots, después de corregir el código de empleado de la fixture.
  `...acceptance-initial.xml`: los tres convertidos a verde.
- `...acceptance-boundaries.xml` descubrió dependencia indebida de fence de escritura
  para un replay. Se corrigió; también se corrigió la firma del inyector de fallo de
  auditoría para aceptar llamadas posicionales y por nombre, sin debilitar expectativas.
- `...acceptance-integrated.xml`: 46 verdes, 17 nuevas y 29 regresiones públicas.
- `...acceptance-final.xml`: seis verificaciones adicionales verdes: revocación después
  del commit en tres acciones, intención de reparto distinta, prueba de pendiente y schema.
- `...acceptance-postgres.xml`: seis verdes, carreras y rollback del llamador en las
  tres acciones. `...acceptance-pending-postgres.xml`: dos reverificaciones del filtro
  JSON de auditoría. `...acceptance-public-postgres.xml`: tres verdes, incluidas claves
  competidoras que no pueden aceptar dos veces, después de serializar la clave global.
- `...acceptance-regressions.xml`: 25 verdes, 16 combos/canales/fencing y nueve de
  trazabilidad. Total sin duplicar reverificaciones: **75 funcionales y 9 de trazabilidad**.
- Ruff de fuentes/pruebas y mypy de api/operations/order_acceptance_views verdes;
  el módulo de proyección se reverificó después del último cambio de bloqueo.
- `tmp/corte-ciego-f106-original-red-check.xml`: las **44 pruebas RED originales**
  pasan ahora sin modificar expectativas. Son evidencia adicional, no cobertura de
  todas las superficies: el historial de repartidores descrito debajo sigue pendiente.

Afirmación: aceptar/asignar no permite recuperar snapshots históricos ni repetir efectos.
Refutación: importe/domicilio no nulos, SQL observado en replay, actor diferente,
lectura o escritura revocadas, cambio de repartidor, token técnico, fallo de auditoría,
revocación después del commit, solicitudes simultáneas con misma/distinta clave y
rollback externo. Resultado: acuse/denegación, originales intactos, una aceptación y
una asignación. No se tomó una aceptación pública como prueba de transición pendiente.
Riesgo residual: consumidores F1-07, autorización exacta F1-08, suspensión/compatibilidad
F1-09, CI integral F1-10 y auditoría independiente del conjunto F1-11 siguen pendientes.

Preguntas operativas: ¿se aceptó/asignó? id/estado del acuse y hecho canónico;
¿quién lo recuperó? order.acceptance.receipt_read con actor/política;
¿la revocación ocurrió tras el efecto? estado persistido y posterior respuesta denegada,
sin reemitir snapshots. Ninguna señal nueva contiene importes o domicilios.

Siguiente F1-06: historial GET /drivers/{driver_id}/deliveries, encontrado con
admin.manage y selección del snapshot completo, todavía sin autoridad financiera.
Luego reconciliar las familias restantes del manifiesto y pasar a F1-07. Este bloque
no cierra F1-06 ni fase 1 y no se ha publicado ni desplegado.


### Historial de repartidores y bandejas de canales — F1-06, 2026-10-22

Terminado localmente:
- Historial de repartidor: sales por ámbito además de admin.manage; sin bypass por
  rol administrativo, identidad técnica ni sucursal actual del repartidor.
- Cuatro bandejas: proyección operacional cerrada aun para Dueño; detalle monetario
  conserva autoridad independiente. El filtro de estado se aplica antes del límite.
- Originales preservados; auditoría y revalidación de identidad, permiso y política.

Evidencia:
- Historial: driver-history-red.xml (2 fallos esperados); driver-history-integrated.xml
  (20 verdes: 10 nuevas, 1 regresión y 9 trazabilidad); driver-history-postgres.xml
  (2 verdes). Prefijo común tmp/corte-ciego-f106-.
- Canales: channel-orders-red.xml (4 fallos reales por exposición); integrated.xml
  (20 verdes: 11 pruebas de canales y 9 trazabilidad); postgres.xml (2 verdes).
  Prefijo común tmp/corte-ciego-f106-channel-orders-.
- El primer lote de límites detectó dos errores en pruebas: falso positivo al confundir
  JSON_EXTRACT con selección del snapshot completo y display_code obligatorio ausente
  en fixture. Se corrigieron las pruebas conservando las exigencias de privacidad.

Afirmación: ninguna bandeja permite reconstruir importes. Refutación: inspección SQL,
metadatos externos con marcador privado, Dueño/cajero, filtro/100 resultados y cambio
de autoridad entre commit y entrega. Resultado: 13 pruebas funcionales verdes, dos
sobre PostgreSQL real; originales inalterados. Riesgo residual: pantallas F1-07 y
transición/suspensión F1-09 pendientes; auditoría independiente en curso sobre el conjunto.

Pendiente inmediato: revisar transporte de sincronización y reconciliar familias del
inventario antes de cerrar F1-06. F1-07..11 siguen pendientes; no hubo producción.


### Sincronización humana y refutaciones de auditoría — F1-06

GET /sync/events ahora separa diagnóstico humano de transporte de gateway. Selección SQL
cerrada sin payload ni event_type libre; permiso/sucursal/identidad, auditoría y revalidación.
Transporte técnico original permanece bajo su credencial y ámbito. Evidencia en tmp/:
- corte-ciego-f106-sync-events-red.xml: 1 fallo real por payload histórico sintético.
- sync-events-initial.xml: 42 verdes (1 nueva y 41 regresiones de workspace/SEC001).
- sync-events-boundaries.xml: 16 verdes (7 propias y 9 trazabilidad).
- sync-events-postgres.xml: 1 verde. Los tres últimos usan prefijo corte-ciego-f106-.

Auditoría Sol: impresión comprobaba credencial después de commit pero no política;
descarga fiscal comprobaba autoridad antes de commit pero no después. Ambas pruebas
reprodujeron entrega indebida (audit-download-red.xml: 2 fallos). Se compara política
actual y se reautoriza documento/identidad tras commit. audit-download-green.xml:
20 verdes, sin cambiar los documentos originales. Prefijo corte-ciego-f106-.
Ruff y mypy focales de esos cuatro módulos pasaron. Esto no sustituye cierre F1-11.

### Suspensión segura — F1-09 parcial

Los probes compartidos nunca interpretan suspended como ausencia de política. Responden
cash_policy_suspended antes de lectura/acción; la asignación de inventory.count.review/
approve conserva la guarda administrativa aun suspendida. Prepared sin activación previa
conserva compatibilidad; prepared posterior no puede restablecer legacy.

Evidencia tmp/corte-ciego-f109-: suspension-red.xml (5 fallos), suspension-initial.xml
(96 verdes incluyendo F1-04/05), suspension-boundaries.xml (17 verdes: 7 focales,
1 PostgreSQL y 9 trazabilidad), prepared-red.xml (regresión detectada al añadir suspensión),
prepared-green.xml (8 verdes tras preservar preparación anterior a primera activación).
No activa políticas reales. Preflight completo, versiones/leases y reversión operativa pendientes.

### Sesiones y cliente — F1-07 iniciado

El cliente compartido descarta GET tardío, incluso durante parseo, al cambiar credencial,
workspace, autorización o política confirmada. POS/Admin invalidan caché de consultas y
estado de lectura al publicar un contexto distinto; no borran evidencias durables por
limpiar una vista. Prueba runtime frontend nueva: test_corte_ciego_f107_read_context.mjs,
registrada en test:frontend-semantic. RED probado antes de implementación. Regresiones de
intents y recuperación de sesión pasaron; typecheck completo pasó antes del descriptor final.

/auth/session incorpora financial_access propio calculado por el evaluador central;
identidades técnicas denegadas y no-store. Pruebas de sesión y typecheck posteriores en curso.
Todavía no se presentan las nuevas pantallas ni se declara integrada la fase 1.


### Checkpoint Git solicitado — 2026-10-22

El usuario autoriza commit, merge y push del avance. La fase 1 continúa abierta;
este checkpoint no autoriza despliegue, migración ni activación. Se excluyen cambios
ajenos de docs/10-operacion-easypanel.md y la entrada ajena de
scripts/repository_policy_allowlist.json, y toda evidencia temporal de tmp/.
Se refrescan únicamente cuatro hashes de excepciones sintéticas preexistentes para
los archivos de CI/tests que sí cambió este paquete; no se añaden exclusiones nuevas.

F1-07: sesión central cerrada con autoridad efectiva por sucursal y invalidación al
cambiar política también en Admin. El descriptor pasó de 183 SELECT para dos sucursales
a cumplir el límite de 30 sin cachear decisiones. Evidencia local:
66 pruebas de autoridad/sesión verdes (session-query-green.xml); 10 de PostgreSQL y
trazabilidad (checkpoint-pg-trace.xml); typecheck del monorepo y Ruff/mypy focales verdes.
F1-09: impresión pull/claim también bloqueada al suspender; 16 pruebas verdes
(print-suspension-green.xml). Archivos JUnit con prefijo corte-ciego- en tmp/.

Turnos/cortes POS usan contratos v2 bajo política activa: estado operativo sin importes,
lectura financiera separada por dataset, suspensión visible y sin fallback legacy.
La nueva captura/finalización de corte permanece fuera de alcance hasta fase 2.
Los parsers rechazan cifras agregadas extra, sucursal ajena, revisión antigua y acuse
de otro recurso. La lectura financiera muestra explícitamente el registro original
cuando existen compensaciones; no calcula un resultado actualizado en el cliente.

Auditoría Sol del mismo ciclo detectó falta de preparación de intents para POST v2
y pérdida de la identidad de comando incierto al remontar/recibir 409 post-commit.
RED runtime reproducido en test_operational_intents.mjs y corregido: preparación
central para open/close v2, evidencia local exacta por organización/actor/sucursal/caja,
prohibición de reemplazo y bloqueo ante corrupción. El revisor revalidó las correcciones
sin otro bloqueo material para este checkpoint; no acredita cierre de F1-07..11.

Afirmación: una respuesta incierta no genera un comando nuevo al reintentar.
Evidencia/refutación: pérdida de respuesta/409 post-commit, remount, actor/sucursal ajenos,
reemplazo de clave y evidencia corrupta en pruebas frontend ejecutadas. Resultado: verdes.
Riesgo residual: faltan integración de las demás pantallas, gateway/leases, transición
y recorrido integral; no se activa la política en producción.

Preguntas operativas del incremento: ¿el comando quedó pendiente o confirmado?,
¿el rechazo provino de cambio de autoridad/política?, ¿puede recuperarse la misma
identidad tras navegar? Los acuses y errores estables existentes, el registro central
de intents y su recuperación responden estas preguntas; no se registran importes en
telemetría de sesión. No se añade un canal de alertas ni se cambia el ledger.

Control previo a publicación: Ruff verde en todos los archivos Python del checkpoint y
mypy verde en sus 48 módulos backend. Pruebas runtime frontend de capacidades/DTOs,
identidad durable, sesión y transporte v2 verdes. Vista aislada de componentes revisada
a 390 px con datos sintéticos; la QA visual del POS completo continúa pendiente.
CI, build de release y recorrido completo de fase 1 no se presentan como aprobados.
