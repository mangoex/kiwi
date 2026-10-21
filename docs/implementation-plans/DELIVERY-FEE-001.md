# DELIVERY-FEE-001 — plan de implementación del catálogo de domicilio

Fecha: 2026-10-21. Estado: **núcleo POS online implementado y probado localmente; CI y release pendientes**.
Riesgo R3: precios/totales, IVA, pagos, caja, historia, persistencia y canales.
Miguel autorizó implementar con «proceed» después de revisar el diseño. No se ha hecho commit/push,
migrado, configurado ni cobrado en producción. Migraciones de prueba sólo en DB local aislada.

## 1. Decisiones y alcance

Miguel confirmó en esta conversación:

- Catálogo de servicios/tarifas de domicilio con precios versionados, separado de alimentos/recetas.
- Tarifa inicial $28.00 MXN con IVA 16% incluido; más tarifas posibles después, por distancia/zona.
- **Una sola tarifa por pedido**, elegida entre las disponibles; sustituir, no acumular.
- Predeterminada al elegir domicilio, Quitar y Restaurar desde comanda; retiro explícito persistente.
- Envío gratis configurable cuando productos tras descuentos/cortesías válidos **alcancen o superen**
  el umbral; incluir modificadores cobrables, excluir envío y propina. Umbral inicial desactivado:
  aún no se aportó un monto productivo. $500 y tarifas adicionales de pruebas son fixtures.

Primer recorrido operativo: Admin + POS online + cobro/ticket/reportes/concepto fiscal coherentes.
Preparar compatibilidad de todos los escritores antes de activar una sucursal/canal; integraciones
y offline se habilitan por incrementos probados. No calcular distancias ni contratar mapas en este
paquete. Tampoco restaurar los tres productos borrados, inventar sueldo del repartidor ni claves SAT.

La investigación base permanece en
`C:/workspace/kiwi/investigacion_cargo_domicilio.md`. Precedentes: [cargo por tipo de orden de
Parrot](https://soporte.parrotsoftware.com.mx/es_MX/menu-pos/cargos-por-servicio-por-tipo-de-orden),
[importe predeterminado de Fudo](https://soporte.fu.do/es/articles/11731518-como-asignar-un-costo-de-envio-sobre-mis-pedidos-de-delivery)
y [separación de reembolso del repartidor en Toast](https://support.toasttab.com/en/article/Delivery-Reimbursement).
El extracto histórico de Soft Restaurant 11 sobre zonas no certifica runtime actual ni que siempre
sea ajeno a productos. Las decisiones confirmadas por Miguel gobiernan Kiwi, no las de un proveedor.

## 2. Autoridad y hallazgos del checkout

Especificación: PRD-FR-283..288; SDD §70 / ADR-047; BDD-FEAT-154, SC-745..766;
TDD-TS-154..156, TC-438..449 y sus seis filas de matriz. Respetar FR-020/024/025/026/034,
FR-054/059/217/218/266/267/276 y NFR-012. Matriz: Probado para FR283..286 por evidencia local; Scaffold para FR287/288. No acredita CI ni release.

Base local observada: `main`, `c5554b8`; no es evidencia del remoto ni del despliegue.

| Frontera real | Hallazgo y consecuencia para las tareas |
| --- | --- |
| `apps/api/restaurant_os/operations.py`: `quote_local_order`, `create_local_order` | Cotiza líneas y ajustes, total sin cargo de envío; tax_cents NULL. Creación enlaza líneas con reservas/tareas. Crear agregado de servicio, no línea productiva ficticia. |
| `apps/api/restaurant_os/api.py`: `/orders/quote`, creación y enmienda | La cotización aún no recibe selección/tipo delivery. Extender DTO, autoridad y compatibilidad; no limitarse a dibujar un selector. |
| `operations.py`: `amend_order`, `pay_order`, `settle_driver_cash_orders` | Enmienda impaga con versión/permiso; pago y recaudación necesitan compartir revisión monetaria y exclusión concurrente. |
| `apps/pos-web/src/features/pos/PointOfSale.tsx`, `editableOrderRestore.ts`, `useCashierOrderRequest.ts` | Quote HTTP, borradores, confirmación y recuperación deben transportar intención de envío, sin reinsertar lo retirado ni aplicar respuesta tardía. |
| `apps/api/restaurant_os/models.py`, Alembic y gateway | Se requieren estructuras y snapshots aditivos; head observado 0099, revalidar antes de asignar revisión. |
| `operations.py`: `_create_print_jobs`; `reconciliation_reports.py`, monitor/cortes | Impresión parte de líneas y total; extender proyección del cargo y sus snapshots sin contaminar cocina/food cost ni reconstruir historia con tarifa actual. |
| `apps/api/restaurant_os/invoicing/service.py`: `create_receipt_for_order` | Ruta observada agrupa total como Consumo en restaurante y convierte a float. Su adaptación al desglose exacto es dependencia real; no declararla compatible por existir un módulo fiscal. |
| `invoicing/commands.py`, `eligibility.py`, serializador/adaptador | Preservar intención durable, elegibilidad, emisor/mapeo aprobado y Decimal de cargo. El diseño del fee no certifica los gaps fiscales restantes ni activa OPEN-006/007. |
| `.github/workflows/ci.yml`, `tests/architecture/test_ci_gates.py`, `scripts/verify_postgres_evidence.py` | CI tiene pytest global y listas explícitas de browser/semánticas/evidencia PG. Cablear los destinos nuevos; prueba descubierta no equivale a gate obligatorio ejecutado. |

Cambios ajenos al inicio: `docs/10-operacion-easypanel.md`,
`scripts/repository_policy_allowlist.json` y `tmp/`; preservarlos y excluirlos de este paquete.

## 3. Tareas ejecutables y dependencias

Estado por tarea en §7. Cada incremento runtime registra RED causal, GREEN y
regresión focal; no se crean tests omitidos ni se silencian gates para obtener verde.

| ID | Resultado revisable | Depende de | Prueba / salida |
| --- | --- | --- | --- |
| P00 | Plan, PRD, SDD, BDD, TDD y matriz, con aclaraciones del usuario y auditoría documental. | Investigación | Trazabilidad, integridad y revisión; no certifica runtime. |
| D00 | Revalidar Git/CI/esquema/canales reales y fixtures; inventariar escritores delivery y documentos fiscales activos. | P00 | Baseline y head libres; lista de recorridos piloto compatibles. |
| D01 | Contrato de catálogo/política y migración aditiva, índices, constraints y permisos existentes. | D00 | RED/GREEN TC438/439/449; upgrade/downgrade aislados, sin seed productivo. |
| D02 | Fijar referencia verificable de quote, vigencia, DTO v2, HTTP/errores y hash de intención; motor Decimal/selección/umbral. | D01 | RED/GREEN TC440/442/443; matriz completa de límites y sin DML productivo al cotizar. |
| D03 | Persistir cargo/revisión y totales en crear/enmendar/recuperar; serializar con pago y liquidación. | D02 | RED/GREEN TC441/444, PG con dos conexiones, fallos y replay tras cambio de tarifa. |
| D04 | Admin Catálogos > Servicios de domicilio: tarifas/versiones, default, ámbito y umbral opcional. | D01/D02 | TC438/439/445, semántica/typecheck; no exige receta ni altera workspace POS. |
| D05 | Comanda POS: selector único, quitar/restaurar, gratis, borradores y recuperación. | D02/D03 | TC440/441/442/445; respuesta tardía, conflicto y cambio de tipo; no precio libre. |
| D06 | Detalle, ticket/hoja entrega, reimpresión, correcciones PCO-005B y snapshots de venta/conciliación/corte/recaudación. | D03 | TC443/446/447; fee-only sin consumo, imagen corregida y delta con cargo, componentes y total concilian, legacy explícito. |
| D07 | Concepto fiscal separado en preparación/recibo/exportación y adaptador exacto, sin duplicar consumo. | D03/D06 | TC447 + regresiones fiscales existentes; configuración incompleta bloquea emisión, no venta por impuestos inventados. |
| D08 | Cablear CI: nuevas semánticas/browser, PostgreSQL obligatorio y tests de los propios gates. | D01..D07 | TC449; fallar si falta DB o suite real ejecutada; suite completa aplicable una vez en CI. |
| V01 | Verificación integrada Admin → comanda → pago → ticket → reportes → adaptador aislado. | D04..D08 | TC438..447/449, QA focal, lint/typecheck/build y evidencia por revisión exacta. |
| V02 | Auditoría R3 independiente del diff runtime con contexto fresco y correcciones. | V01 | Afirmaciones refutadas con evidencia; una sola revisión del cambio, sin sustituir CI. |
| R01 | Preparar migración/configuración y canary de sucursal/canal con recuperación/drenado; mostrar resultado para aprobación. | V02/CI verde | Autorización productiva separada; mapeo fiscal/umbral real explícitos antes de habilitar sus funciones. |
| C01 | Adaptar contrato por escritor de intenciones/aceptación, Asistto y marketplaces; propiedad del fee. | D03/D06/D07 | TC448 por canal; no duplicación ni omisión por cliente antiguo. No habilitar canales por herencia de un flag POS. |
| O01 | Política/tarifas en SQLite, grants/fencing, comandos y snapshots firmados, outbox/inbox y recovery. | D03/C01 según canal | TC448/449 con PG/SQLite y gateway reales; precio central cambiado, tampering y replay. |
| R02 | Auditar, verificar CI y proponer activación acotada de cada canal/offline listo. | C01/O01 | Autorización separada, observación y rollback compatible con historia. |

D07 es dependencia de release del recorrido fiscal habilitado; si FISCAL-001 carece todavía de
información canónica de alimentos o dispatch seguro, registrar el bloqueo y conservar emisión
cerrada. No etiquetar el conjunto como CFDI completo ni desplegar un atajo de “Consumo total”.
El piloto no puede usarse para evadir una frontera fiscal que ya esté habilitada en esa sucursal.

## 4. Criterios verificables de terminado

1. Catálogo sin producto/receta con precio versionado y default válido; alcance de sucursal explícito.
2. Delivery sugiere 28; elegir otra tarifa sustituye; retirar persiste y restaurar es explícito.
3. Umbral desactivado mantiene cobro; con fixture 500, base 499.99 cobra y 500/500.01 exenta.
4. Descuentos válidos modifican base; envío/propina no la completan; combo/modificadores una sola vez.
5. Quote/pedido/pago/ticket/reporte/fiscal usan revisión canónica; base/IVA del envío exactos, sin
   falsear impuestos de alimentos ni cobrar retrospectivamente a pedidos legacy.
6. Tarifa no genera consumo, reserva, tarea o unidad/ranking de alimentos. La edición sólo del fee
   no toca producción. Recaudación del repartidor y su remuneración permanecen distintas.
7. Pago frente a retiro concurrente y reintentos tienen un resultado efectivo consistente; no hay
   escritura parcial, ampliación de permisos o precio aportado por cliente como autoridad.
8. Canales/plataformas no duplican cargo ni lo omiten por incompatibilidad; offline conserva precio
   autorizado/snapshot y ambos dialectos sólo cuando su incremento esté probado.
9. Migración/rollback preservan historia; CI exige los gates que afirma. Despliegue, DB, configuración
   y comportamiento productivo tienen evidencia distinta de local/Git/documentación.

## 5. Afirmaciones R3 y refutaciones

Las obligaciones y refutaciones del diseño se conservan aquí; evidencia runtime y límites en §7.

| Afirmación | Evidencia prevista | Intento de refutación | Resultado actual / riesgo residual |
| --- | --- | --- | --- |
| Una tarifa a la vez y retiro persistente. | TC440/445, constraint y snapshots. | Array/duplicado, reload, respuesta atrasada, salir/regresar a delivery. | Contrato definido; runtime pendiente. |
| Umbral y precio exactos sin consumo. | TC442/443, ledger antes/después. | 49999/50000/50001, descuento, combo, propina, sustituir gratis y restaurar retiro. | Diseño determinista; falta evidencia ejecutada. |
| Historia y pago mantienen revisión consistente. | TC438/441/444/446. | Publicar entre quote/create, archivar antes de replay, pago y retiro simultáneos. | Bloqueos/snapshots exigidos; carrera PG pendiente. |
| Fiscal y reportes no duplican ni inventan dinero. | TC446/447, adaptador aislado y sumas. | Consumo total legacy + fee, alimentos sin impuesto, refund, varios pedidos con redondeo. | Gap de recibo identificado; mapping SAT/emisor y runtime pendientes. |
| Ningún canal viejo evade o duplica tarifa. | TC448/449 por escritor y PG/SQLite. | Cliente v1, webhook con fee ajeno, payload manipulado, gateway viejo o precio central cambiado. | Inventario definitivo D00 y pruebas futuras; no activación implícita. |

Cuatro preguntas operativas y señales están en SDD §70.6; no crear otro documento de observabilidad.
No registrar teléfonos/domicilios, payload fiscal ni secretos en las señales de seguimiento.

## 6. Evidencia de planificación previa a «proceed»

Baseline antes de editar y verificación posterior con `.venv/Scripts/python.exe`:
`tests/architecture/test_traceability.py`: **9 passed**. Se comprobó UTF-8, fences, whitespace,
22 escenarios y 12 casos nuevos; `git diff --check` del paquete sin errores.

Auditoría independiente con contexto fresco `sol_design_audit`: **sin bloqueantes documentales**.
Contrastó correcciones contra `operations.py` (total actual derivado de líneas), revisó FR-217 y
verificó whitespace; su intento de pytest mediante `python` no arrancó por el alias Microsoft
Store y no se cuenta como evidencia. La ejecución válida es la de `.venv` indicada arriba.
La refutación de perder el fee en PCO-005B quedó incorporada a SDD §70.4/D06/TC447; se añadieron
oráculos 52799→50000 = REFUND 2799 y 50000→52799 = CHARGE 2799, con original inmutable y delta
de IVA de envío conocido. Son resultados aritméticos especificados, aún sin prueba runtime.
Pruebas runtime, lint/typecheck/build de implementación, PostgreSQL/SQLite/gateway, navegador,
CI, sandbox/PAC, canary y activación: **pendientes, no ejecutados por esta entrega de planificación**.
No se modifican estados existentes a Implementado por agregar estas especificaciones.


## 7. Cierre del incremento POS online autorizado

Base local `c5554b8`, cambios sin commit. `git fetch origin` observó `origin/main=427f54c`, dos
commits posteriores aún no integrados (disponibilidad de productos); la validación de este paquete
no certifica esa combinación. Reconciliar y ejecutar CI antes de release. Se preservaron cambios
locales ajenos de operación/allowlist/tmp; el hash existente del fixture sintético CI se actualiza
por el nuevo gate PostgreSQL, sin introducir exclusiones. Dos comprensiones tipadas equivalentes
en corporate_purchases/system_diagnostics sustituyen `dict(Sequence[Row])` para el gate mypy;
no cambian sus reglas de negocio ni silencian errores.

| Tarea | Estado real |
| --- | --- |
| P00/D00 | Completos para el incremento online; head0099 confirmado, inventario de escritores con guardas. |
| D01 | Catálogo/política corporativos y migración0100; revisión sin cambios conserva versión; downgrade vacío y bloqueo con historia probados. |
| D02 | Motor Decimal, selección única/umbral, HMAC120s, DTOv2, errores y refresco POS90s. |
| D03 | Crear/enmendar, snapshot/replay estable, serialización branch→order y branch→catalog; PG real. |
| D04/D05 | Admin y comanda con selección/Quitar/Restaurar/borrador, recuperación y precio del servidor; navegador real. |
| D06 | Pago/total/ticket payload/monitor/reporte separado y corrección umbral sin descuento. Impresora física y atribución por turno/repartidor pendientes. |
| D07 | Preparación exacta aislada y captura durable; agregado legacy bloqueado. Emisión completa depende de alimentos canónicos/dispatch FISCAL-001. |
| D08 | CI cableado para semánticas/browser/PG obligatorio, verificador de JUnit y tests del gate. CI remoto aún no ejecutado. |
| V01 | Evidencia local abajo; los límites fiscales/operativos no se declaran aprobados. |
| V02 | Auditoría independiente sol_runtime_audit, contexto fresco, integrada en este cierre. |
| R01/R02 | Pendientes de integración remota/CI y autorización de migración/configuración/despliegue/canary. |
| C01/O01 | No implementados como canales habilitados. Guardas de incompatibilidad transaccionales; sin activación implícita ni repricing offline. |

### Evidencia local exacta

- Catálogo/cálculo/comandos/correcciones/fiscal + monitor + trazabilidad/CI: **49 passed**.
- Regresión focal plataforma/correcciones: **64 passed, 108 deselected**.
- Preparación fiscal/Facturapi/lease HTTP/intenciones/DiDi: **59 passed**.
- PostgreSQL16 aislado: publicación concurrente, cobro vs retiro, reporte exacto: **3 passed**;
  migración/reversión vacía/bloqueo con historia: **1 passed** adicional. Ejecución final conjunta:
  **4 passed**, JUnit en `output/delivery-fee-postgres.xml`. El intento sin URL falló
  explícitamente como exige el gate; no se contabiliza como aprobación ni se usa skip.
- Semánticas `test:delivery-fee`, monitor/turno, checkout/idempotencia, borradores, admin-access:
  verdes. Typecheck del monorepo verde; builds de apps verdes, POS recompilado tras el reporte.
  Vite conserva advertencias de tamaño de bundle, sin error de compilación.
- Ruff focal verde y mypy **107 archivos sin errores**. Integridad/whitespace y política repo
  se verifican al cierre. CI completo, PAC/sandbox, impresora y canary no ejecutados.
- Browser real con API y DB SQLite sintéticas propias: catálogo; una tarifa, alternativa única,
  Quitar, reload manteniendo retiro, Restaurar, umbral gratis; cotizaciones 12300/13700/9500.
  Capturas 390/1024/1440 en `output/playwright/delivery-fee/`; no datos productivos. Hubo fallos
  de limpieza Windows EPERM tras pasar aserciones; no se contabilizaron como verdes. Se usa carpeta
  de fixtures propia bajo output, espera al cierre completo del proceso API y borrado asíncrono
  con reintentos y contención validada; el gate sólo queda verde cuando termina también la limpieza.
- RED causal previo del contrato nuevo: módulo frontend ausente y contrato/rutas nuevas sin
  implementación; después GREEN de los destinos indicados. Las regresiones nuevas de auditoría
  parten de reproducciones concretas, no de fabricar fallos documentales R0.

### Auditoría R3: afirmación, evidencia, refutación, resultado y residual

| Afirmación | Evidencia / intento de refutación | Resultado y límite |
| --- | --- | --- |
| No cobro retroactivo ni repricing histórico. | Auditoría reprodujo legacy9500→12300 al activar; prueba nueva activa después de crear. Producto cambiado/inactivo en fee-only probado. | Corregido: ausencia histórica permanece, cotización usa líneas capturadas. |
| Autoridad no se amplía. | Rol branch con catalog.manage publicaba catálogo/política200; ahora403. Replay debe reautorizar lectura y enmienda. | Guardas corporativas y orders.read preservadas; no concede permisos por nombre. |
| Cobro/enmienda consistentes. | Auditoría reprodujo deadlockPG40P01 del orden inverso; nuevo orden completó ambos. Test concurrente permite sólo pago12300 o retiro9500 con pago viejo rechazado. | Locks corregidos, snapshots/replay estables; CI pendiente sobre versión integrada. |
| Envío no consume ni duplica alimentos. | Prueba compara ledger y IDs productivos antes/después del retiro; snapshot pago12300 y envío2800 por separado. | Sin producto/receta/tarea nueva; ticket sólo líneas activas, cocina sin cargo. |
| Umbral/IVA/reportes concilian. | Límites49999/50000/50001, descuento950 sobre9500 da base8550 y total11350; reporte2800=2414+386; asignación de centavos conserva suma. | Conocido envío16%; impuestos de alimentos siguen desconocidos. |
| Corrección no reescribe pago/corte. | Original500 gratis→productos250+fee2800=3050, delta2550; original sigue500. Se intentó corrección descontada. | Compensación append-only; descuento en corrección/cambio de carrito se bloquea explícitamente hasta nueva autorización canónica. |
| Canal viejo no omite fee por carrera. | Publicación y chequeo comparten branch→catalog; cliente sinref409, fee externo no se suma local por defecto. | C01/O01 pendientes; bloquear incompatible no equivale a soportar esos canales. |
| Fiscal no duplica Consumo+envío. | Concepto Decimal28/IVA.16 y emisor distinto rechaza; agregado con snapshot falla antes de proveedor. | Emisión completa cerrada, sin claves SAT inventadas ni llamadas PAC. |

El posible P2 de paginación al cambiar filtros quedó refutado: SalesMonitor monta el panel con
key de sucursal/fechas/zona, reiniciando offset. Se reautoriza orders.read antes de devolver
snapshot de replay; prorrateo desempata sobre líneas ordenadas por created_at/id.

### Paso productivo aún no autorizado

Preparar el release integrado con CI verde; elegir sucursal/canales compatibles; revisar backup y
migración0100; crear tarifa28.00 y política **deshabilitada** con umbralNULL, revisar y habilitar
sólo tras autorización productiva. No restaurar productos borrados. Validar flujo fiscal activo
antes de habilitar: el piloto no puede evadir una emisión que ya se use. Rollback funcional:
deshabilitar para pedidos nuevos, drenar órdenes/grants, conservar tablas/snapshots; no downgrade
con historia. Canary acotado: cobro28, retiro, umbral fixture aislado, ticket, conciliación y
recaudación; nunca crear cobros ficticios productivos ni compensaciones sin autorización.


Comprobación final adicional: 30 pruebas de trazabilidad/gates/comandos/correcciones aprobadas;
regresión de retiro→restauración→replay estable y revocación de orders.read aprobada. Auditoría
independiente cerró sin bloqueantes confirmados; reprodujo denegación de lectura/replay con rol
que sólo conserva orders.amend. PostgreSQL de pruebas se detiene al concluir, sin daemon productivo.


Navegador final **exit0** tras esperar `close` del servidor y usar eliminación asíncrona:
selección/retiro/reload/restauración/umbral en POS; creación/cobro contra API aislada y reporte
visible en Monitor de ventas. Resumen observado: total12300, alimentos9500, envío2800,
base2414 e IVA386. Captura `report-1440.png`; QA visual focal de catálogo/comanda/reporte.
`repository_policy.py` verde y `git diff --check` limpio; cierre de trazabilidad/gates:23passed.
La revisión automática rechazó la limpieza manual de tres carpetas residuales sintéticas de
intentos anteriores con motivo «blocked by policy»; se conservan, sin reutilizarlas ni incluirlas
en Git. El browser sí elimina su propio fixture en la ejecución aprobada. No se intentó evadir
esa restricción ni tocar datos productivos.


Límite de compensaciones encadenadas del incremento online: una segunda corrección pagada de un
pedido con cargo de domicilio se rechaza con `delivery_correction_chain_pending`, conservando
la primera corrección y permitiendo replay de su mismo comando. Requiere contrato de saldo
compensado acumulado antes de habilitar otra corrección, no recalcular contra el pago original.
Regresión persistida: original3300/productos500/envío2800, retiro autorizado devuelve2800;
una nueva solicitud no puede devolver otros2800. RED causal: segunda corrección se aplicaba;
GREEN: una sola corrección. Es guarda técnica de compatibilidad, sin ampliar edición impaga.


Regresión final del guard de compensaciones encadenadas: **57 passed** (delivery_fee_corrections
más order_corrections), Ruff verde y mypy107 verde después del cambio; trazabilidad/gates23passed.
El gate PostgreSQL4passed cubre publicación/pago/reporte/migración; la prueba de doble devolución
se ejecutó en SQLite, no se presenta como carrera PostgreSQL específica de esa nueva guarda.

Auditoría independiente final de la misma corrección:3pruebas aprobadas; refutación de replay
de la primera compensación después de bloquear la segunda conserva exactamente su respuesta y
una sola corrección efectiva. Sin hallazgos pendientes; no certifica carrera PostgreSQL del guard.


## Publicación Git autorizada (2026-10-21)

Miguel autorizó commit, merge y push. Commit funcional `c3ba59a` en
`codex/delivery-fee-online`; se integra `origin/main=427f54c` conservando Disponibilidad y
Servicios de domicilio en rutas/hub/permisos. Conflictos sólo en CategorySubNav y adminAccess,
resueltos conservando ambas entradas. Hash del fixture CI actualizado al workflow combinado.
Runbook local ajeno, su hash pendiente y tmp quedan excluidos; cambios preservados.
Verificación integrada y CI mediante PR antes del merge a main. La autorización Git no aplica
migraciones, configuración, cobros ni despliegue productivos.


CI401 detectó ERR_UNSUPPORTED_RESOLVE_REQUEST en el harness de sesión: el barrel público ahora
exporta deliveryFee y los cargadores dataURL debían resolverlo. Se añade el módulo a cinco harness
existentes (sesión, workspace, fiscal e intenciones), sin retirar asserts ni silenciar errores.
Pruebas dirigidas de esos cinco harness verdes. Se actualizan sólo sus hashes sintéticos existentes.
La integración conserva typecheck/build,47pruebas focales y auditoría independiente sin bloqueantes.
