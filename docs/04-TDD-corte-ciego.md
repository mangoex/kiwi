# TDD — CORTE-CIEGO-001

Estado: **contrato no implementado; lote RED F1-03 ejecutable, sin GREEN funcional**. Fuente:
PRD-FR-289..300, SDD §71/ADR-048 y [BDD](03-BDD-corte-ciego.md). Casos y suites
siguientes son contratos de prueba, no nombres de tests ya existentes ni resultados GREEN.
La formalización inicial corrió integridad/trazabilidad. F1-03 añade pruebas y fixtures
sin lógica funcional; cada incremento posterior debe conservar RED causal y verificar
GREEN tras autorización de implementación.

## TDD-TS-157 Autoridad financiera y reportes

Casos TDD-TC-450, TDD-TC-451 y TDD-TC-462. Fixtures con dos organizaciones, dos
sucursales, Cajero, Cajero jefe, Líder, Supervisor, Administrador, Dueño, delegado
limitado/revocado y dispositivo. Resolver autoridad persistida, no nombres. Enumerar
rutas/campos revisados, incluidos aliases, exportaciones, asistentes y replay; no
certificar confidencialidad mediante ausencia de un texto en pantalla.

## TDD-TC-450 Proyección ciega y delegación revocable

PRD-FR-289; BDD-SC-767/768; CC-AC01/02/12/15. Dominio/API/contratos antes y después de
COUNTED/FINALIZED: actor operativo ve sólo estado y declaración propia, sin esperado,
componentes, diferencia, cuadratura, venta, ticket promedio ni existencia de alerta.
Dueño y delegado ven datos únicamente bajo concesión/alcance vigente. Revocar entre
comando y replay/descarga elimina acceso a respuesta financiera previa. Cambiar IDs,
organización, sucursal, sesión o permisos no devuelve información ajena; denegación
sin efecto financiero. Revisar respuestas de mutación, errores/logs/eventos/caché,
no sólo GET. Permiso de lectura no finaliza, corrige ni modifica pagos.

## TDD-TC-451 Roles combinados y revisión individual

PRD-FR-290; BDD-SC-769/770; CC-AC02/16. Matriz efectiva con roles combinados y grants
generales/legacy; Líder equivale a encargado, otros nombres no lo convierten. Un grant
que contradiga restricción impide certificar preflight hasta resolverlo; la revisión
conserva origen y antes/después por usuario. Probar que retirar acceso financiero
no requiere conceder catalog.manage ni rompe recepción/KDS permitidos. Asignación
real de usuarios no forma parte del test ni de esta formalización.

## TDD-TS-158 Declaración conciliación e integridad

Casos TDD-TC-452..457 y TDD-TC-463. Reutilizar puntos de entrada de PCO-006 con
fixtures deterministas nuevas para el contrato ciego, preservando regresiones de
ledger, alcance, inmutabilidad y asociaciones. Centavos exactos; reloj controlado;
hash de estado antes/después en rechazos y fallos inyectados.

## TDD-TC-452 Responsables y finalización pendiente

PRD-FR-291; BDD-SC-771/772; CC-AC03/08. Cajero confirma sólo turno propio cerrado;
encargado sustituye con identidad/motivo sin cambiar responsable. Cajero, delegado
y dispositivo no finalizan; encargado/Dueño sí con resto de guardas satisfechas.
Ausencia de finalizador deja COUNTED ineditable. El mismo encargado sustituto
puede finalizar, sin cuatro ojos adicionales. Negativos: actor/periodo/cajero
afirmados, turno abierto, cajero legacy ambiguo y sucursal ajena. Captura inicial
por Dueño no se añade como positivo por inferencia. Acuse restringido no indica
cuadratura; finalizar no constituye aprobación del faltante.

## TDD-TC-453 Denominaciones medios y precisión

PRD-FR-292; BDD-SC-773; CC-AC05/06. Sólo Dueño configura denominaciones; snapshot
permanece tras cambio de catálogo. Ejemplo de fixture: dos piezas de 2000 y tres
de 500 centavos producen 5500; sumar fondo presente físicamente sin añadirlo dos
veces a la declaración. Rechazar piezas fraccionarias/negativas, denominación
inexistente y total fabricado por cliente. Verificar MXN, dos decimales en captura
manual de importes y distinción vacío/cero explícito. Declaración separada por
medio/referencias sin precargar esperado. Límites técnicos de captura se fijan
antes de construir sus pruebas; no inventar un tope de negocio en este documento.

## TDD-TC-454 Borrador confirmación y custodia

PRD-FR-292; BDD-SC-774; CC-AC07. Ediciones antes de confirmar conservan trazabilidad;
revisión visible, confirmación única, conflicto de versión/contenido sin reemplazar
original. Persistir detalles y total exacto atómicamente. Replay tras perder acuse
no duplica; reinicio no permite reconfirmar otro contenido. Capturista queda
registrado; entrega posterior añade receptor/hora UTC, sin inferir entrega por
confirmación ni cambiar cantidades confirmadas.

## TDD-TC-455 Fuentes de conciliación por medio

PRD-FR-293; BDD-SC-775/776/777; CC-AC06/08/09. Efectivo: 10000 + 50000 + 2000 - 7000
= 55000; declaración 54000 -> -1000, declaración 56000 -> +1000. Pago tarjeta 20000
no modifica cash. Caso separado mixto 50000: 20000 cash/30000 tarjeta; no contar venta
y movimiento como dos entradas. Comprobante no verificado no confirma transferencia.
Plataforma/canal/cobrador, depósitos, comisiones y liquidación se mantienen separados.
Repartidor entrega tarde en turno receptor con enlace único sin reabrir el anterior.
Cancelar sin devolución confirmada no mueve dinero. Propinas sin entradas/entregas
trazables no se habilitan integradas. Fuente insuficiente conserva pendiente motivado,
no expected=0; resultados posteriores enlazados no sobrescriben snapshot. Pendiente
externo conocido permite finalizar, operaciones locales desconocidas no.

## TDD-TC-456 Diferencia cero y avisos diferidos a fase tres

PRD-FR-294; BDD-SC-778/779; CC-AC08/09. Probar -1, 0 y +1 centavo; conservar resultado
exacto, no bloquear sólo por diferencia. Sobrante cash 100 y faltante tarjeta 100 no
dan cuadratura neta. Fuente insuficiente no inventa faltante. Fases 0..2 preservan
evidencia durable del resultado/evento sin afirmar envío. Para fase 3: destinatario
Dueño o delegado con alcance y designación, reintento por fallo de canal sin bloquear
corte ni producir nueva diferencia, sin fuga al acuse operativo. No usar un envío
real como prueba de esta formalización ni elegir proveedor/canal no aprobado.

## TDD-TC-457 Reporte de error y compensación exclusiva

PRD-FR-295; BDD-SC-780/781; CC-AC11. Operador reporta motivo/evidencia sin ver esperado
ni solicitar formalmente compensación. Sólo Dueño solicita/decide/aplica, pudiendo
ser el mismo actor; negativos de encargado/delegado incluso manipulando IDs.
COUNTED no se edita: original finaliza bajo todas las guardas antes de compensar.
Verificar imagen aprobada, original/delta enlazados, auditoría y consultas protegidas;
ledger/pagos/asociaciones idénticos. Replay y fallo intermedio no duplican compensación.
Errores de pago/retiro no se solucionan creando dinero desde corrección de conteo.

## TDD-TS-159 Permisos colaterales de pedidos e inventario

Casos TDD-TC-458/459. Pruebas dirigidas a autorización y paridad entre UI/API/servicios;
conservar guardas de estados, recepción parcial, producción y correcciones canónicas.
No sustituir pruebas del dominio ni ampliar módulos dentro de CORTE-CIEGO-001.

## TDD-TC-458 Autorización exacta en pedidos

PRD-FR-296; BDD-SC-782/783; CC-AC16. Borrador propio editable; descuento/cortesía
incluso en borrador requiere encargado/Dueño. ACCEPTED sin pago también exige
autorización para cambio/cancelación. Versionar contenido autorizado; cambio de
pedido o acción lo invalida, replay idéntico no duplica efectos. Capturar solicitante,
autorizador con credenciales propias, motivo y antes/después; sin sesión heredada.
Ausencia de autorizador no aplica. Estado IN_PROGRESS incompatible sigue bloqueado,
cancelación producida permitida exige merma/recuperación y pagos usan compensación
canónica, con sus autorizaciones adicionales. No otorgar retiros ni nuevos comandos
offline de pedidos en estos positivos.

## TDD-TC-459 Recepción ciega y revisión administrativa

PRD-FR-297; BDD-SC-784/785; CC-AC16. Encargado recibe cantidades/parciales/diferencias
contra compra autorizada sin costos en UI ni payload; lectura de precio sólo por
concesión explícita, limitada y vigente. No concede mutación de catálogo/conversión.
Capturista no ve teórico/costos/diferencias y submit no genera movimiento. Dueño o
responsable administrativo autorizado revisa/aprueba sin segundo aprobador obligatorio;
encargado/delegado financiero solos no. Preservar compras/ventas/traspasos concurrentes
y ledger histórico usando pruebas de conteo existentes como regresión.

## TDD-TS-160 Offline transición y recorridos completos

Casos TDD-TC-460/461/464/465. SQLite/gateway para durabilidad y outbox/inbox;
PostgreSQL aislado para finalización y autoridad central, sesiones/clientes de versiones
distintas para transición. No aceptar mocks que den por acreditada completitud.

## TDD-TC-460 Cierre local y finalización central

PRD-FR-298; BDD-SC-786/787/788; CC-AC04/13/15. Gateway con identidad/lease válida guarda
conteo en SQLite, reinicia, recupera y reenvía la misma declaración. Acuse perdido no
duplica ni produce segunda captura. Sin autoridad vigente, nuevos comandos sensibles
se bloquean; no renovar lease localmente. Al reconectar, autoridad obsoleta/conflicto
conserva evidencia pendiente sin compensación automática. Cola vacía con fuente faltante
o hueco debe impedir FINALIZED; completar cierre y todas las fuentes permite encargado/
Dueño central. Completitud se prueba contra protocolo técnico definido antes del
incremento, no contra ausencia de mensajes únicamente. Caída prolongada/gateway caído
no transforma contingencia en confirmado; no prometer revocación instantánea offline.

## TDD-TC-461 Activación entre turnos y clientes incompatibles

PRD-FR-299; BDD-SC-789/790; CC-AC02/12/14/15. Tabla de preflight con turno OPEN,
COUNTED pendiente, operación local sin recibir, lease previa vigente, cliente viejo
y grant acumulado: cada incompatibilidad impide activar. Flujo compatible termina
pendientes sin forzar datos; ensayo por usuario y fecha/versión de política conservados.
Sesiones/respuestas tardías/descargas no reabren acceso financiero después de activar.
Turno cruza medianoche/cambio horario: UTC semiabierto/zona snapshot preservados.
Piloto falla: no ampliar; reversión mantiene confidencialidad y originales.

## TDD-TC-462 Reportes restringidos sin reconstrucción directa

PRD-FR-300; BDD-SC-791/792; CC-AC01/02/12. Encargado: número de tickets y top 10
de su sucursal por día/semana/mes; Cajero sin ese reporte. Ranking sólo nombre/posición,
sin cantidades/precios/ingresos/costos/márgenes incluso en JSON/download. Definición
canónica de tickets y reimpresión no crea venta. Pedidos individuales limitados a
atención/seguimiento autorizado. Probar intento de reunir listado/exportación masiva
monetaria a través de paginación, filtros, asistentes y otras superficies: paginar
una descarga completa no satisface la restricción. Dueño/delegado pueden consultar
agregados bajo concesión vigente. No afirmar imposibilidad de estimación humana.

## TDD-TC-463 Concurrencia atomicidad y exclusividad

PRD-FR-291/292/298; BDD-SC-793/794; CC-AC04/07/10. PostgreSQL real aislado: confirmar/
confirmar, finalizar/finalizar, local/central, finalizar/revocar autoridad y cierre/
pago/retiro/recepción. Un solo efecto o rechazo sin escritura parcial; operaciones
con asociaciones exclusivas incluso con periodos distintos. Inyectar fallo entre
cada escritura sensible, incluida auditoría y comando: rollback coherente y replay
recuperable. SQLite cubre semántica y constraints, no sustituye locks PostgreSQL.

## TDD-TC-464 Migración aditiva e historia sin desglose inventado

PRD-FR-299; BDD-SC-789/790; CC-AC03/12/14/15. Una vez exista migración: esquema vacío
y con cortes DRAFT/COUNTED/FINALIZED y compensaciones; conservar bytes/valores canónicos
de originales y asociaciones. No fabricar denominaciones, comprobantes ni cajero
ambiguo; legacy explícito. Snapshot de denominaciones/zona/periodo no cambia. Downgrade
con historia falla sin borrar; recuperación de app no restaura exposición financiera.
No asignar número de revisión ni ejecutar una migración productiva en este paquete.

## TDD-TC-465 Recorrido de roles y captura ciega

PRD-FR-289..300; BDD-SC-767/771/774/776/780/782/784/786/789/791/792; CC-AC01..16.
E2E local: abrir/cobrar/cerrar turno, capturar borrador, confirmar, esperar finalizador,
finalizar con acuse ciego, lectura Dueño, reporte de error y compensación. Variante
offline sólo tras protocolo soportado; variante con conciliación externa pendiente.
UI verifica foco/teclado, errores y estados reales, total propio, cero/vacío y ausencia
de éxito definitivo optimista. QA visual dirigida a pantallas/breakpoints afectados,
sin matriz universal. Permisos restringidos no rompen venta/recepción/KDS autorizados.

## Evidencia reutilizable y gates de implementación

Puntos de partida, **no cobertura acreditada de este contrato**:

- [Dominio](../apps/api/tests/test_user_cash_cuts.py),
  [contratos](../apps/api/tests/test_user_cash_cut_contracts.py),
  [PostgreSQL](../apps/api/tests/test_user_cash_cuts_postgres.py) y
  [migración](../apps/api/tests/test_user_cash_cuts_migration.py).
- [Cierre](../apps/api/tests/test_cash_shift_operational_close.py),
  [offline](../apps/api/tests/test_offline_order_cash_close.py),
  [sync](../apps/api/tests/test_pco008_cash_sync.py) y
  [gateway](../tests/edge_gateway/test_pco008_cash_outbox.py).
- [Semántica POS](../tests/frontend/test_pos_user_cash_cuts.mjs).

Tras autorización de código: RED focal del contrato afectado, Python/contratos y
lint/typecheck del módulo; frontend typecheck/semántica y build cuando corresponda;
PostgreSQL aislado para persistencia/concurrencia; SQLite/gateway para offline;
E2E crítico y QA dirigida. Suite aplicable una vez en CI según GOV-TEST-001, sin
silenciar ni excluir regresiones para obtener verde. Revisión independiente R3,
evidencia separada de local/CI/Git/migración/piloto. Canary sólo autorizado aparte.
Fase 3 prueba entrega de alertas; su ausencia no se presenta como entrega verificada.

## Refinamiento técnico F1-01/02 para preparar RED

Fuente de rutas/handlers: [inventario F1-01](implementation-plans/CORTE-CIEGO-001-ACCESOS.md).
Contratos de fixtures, campos, locks y errores: [SDD F1-02](02-SDD-corte-ciego-fase-1.md) §2..9.
F1-01/02 no agregaron tests ejecutables. F1-03 añade el lote vinculado al final;
los casos completos continúan sin evidencia GREEN funcional.

| Caso existente | Obligación concreta para F1-03 y ejecución posterior |
|---|---|
| TDD-TC-450 | Matriz endpoint/alias × actor × dataset × sucursal; deny de permiso aislado, campos extra, resultado almacenado y descarga. Repetir negativos sobre camino de colisión de command key, intents, CRM/customer order_summary, logs raw y AI antes de consulta/modelo. DTO financiero separado del acuse. |
| TDD-TC-451 | Grants acumulados y Dueño real gobernado; delegado limitado no obtiene finalize/capture/correction/catalog. Revocar e invalidar autorización sin borrar evidencia ni asignar roles reales. |
| TDD-TC-452 | Capture/finalize separados; no captura inicial Dueño inferida; replay es consulta autorizada de acuse, no reejecución; declaración propia no revela resultado. |
| TDD-TC-461 | Barreras deterministas PostgreSQL de revocación/lectura y mutación de roles; exporte generado antes y descargado después; sesión y respuesta tardías. Orden de locks del SDD, no sleeps. Gateway lease vencido/reconciliación preservan comandos. |
| TDD-TC-462 | Payload operativo sin monetarios/derivados, top10 sin cantidades, calendarios/empates/reimpresión, fin de año/mes/cambio horario; exact ID, cursor, expand y reimpresiones/retries en serie no crean ni evitan contexto persistido actor/pedido/acción/versión. Positivo cobro puntual conserva precio y cambio. |
| TDD-TC-464 | Migración aditiva/grants sin inferencia, política por sucursal, v1 upgrade sin fallback, rollback compatible preservando privacidad/historia; dry-run sin tocar cuentas reales. |
| TDD-TC-458/459/465 | Autoridad de pedido, recepción sin costos y revisión/aprobación de inventario conservadas; contratos UI por capacidad y cero como importe real, nunca sustituto de dato oculto. |

El baseline local 30 passed / 1 skipped de F1-01 cubre PCO-006 existente; no cubre estos
negativos ni carreras nuevas. PostgreSQL omitido por URL ausente queda pendiente de su
gate aislado. CI y pruebas semánticas/UI del futuro diff siguen sin ejecutar.

## F1-03 — fixtures y RED ejecutable

- [Fixtures](../apps/api/tests/corte_ciego_fixtures.py): dos organizaciones, tres sucursales,
  actores/roles acumulados, concesiones por pares y revocación/versionado; SQLite aislado.
- [Contratos de prueba](../apps/api/tests/corte_ciego_contracts.py): allowlists de acuse
  y reporte operativo, sin instalar schemas ni serializers de producción.
- [RED](../apps/api/tests/test_corte_ciego_f1_red.py): handlers/servicios reales para
  TC-450/451/452/462. No xfail/skip, endpoints falsos ni sustitución de autorización.
- [Controles](../apps/api/tests/test_corte_ciego_f1_controls.py): validez de datos,
  lectura Dueño baseline, aislamiento, idempotencia y refutación de las allowlists.

La evidencia exacta, comandos y matriz de cobertura están en el
[plan, cierre F1-03](implementation-plans/CORTE-CIEGO-001-FASE-1.md#9-f1-03--fixtures-y-pruebas-red).
En F1-03 las tablas fueron staging; F1-04 las sustituye por schema real y prueba
la migración. F1-05 conecta turnos/cortes; los lectores indirectos legacy de F1-06 aún no consumen el evaluador nuevo. Los tests muestran la integración pendiente mediante
respuestas/acciones reales; no demuestran que una política nueva ya esté activada.

Cobertura preparada: rechazo de aliases v1 y comandos/replay legacy, capacidades
capture/finalize distintas, campos financieros en acuse, revocación antes de nueva
lectura/replay, grants de dataset/sucursal sin producto cartesiano, ámbito ajeno,
consultas financieras sin sucursal, listas monetarias y perfil/historial de cliente,
consulta de pedido por ID sin contexto y consulta SQL de IA antes de autorización.
Las allowlists rechazan claves adicionales incluso con 0/null/false, campos anidados
monetarios y cantidades/precios/identificadores en ranking.

No acreditar con este lote: DTO v2 emitidos por rutas aún inexistentes, guardas de
preflight/Dueño gobernado, concesiones mediante comando real, exportes/intents,
IntegrityError concurrente, PostgreSQL/locks, dispositivos/leases, calendario calculado,
reimpresiones, KDS/cobro/recepción y UI. Esos gates se vinculan a F1-04..10 y deberán
obtener pruebas focales antes de cambiar el código correspondiente. Los controles
GREEN de fixtures/oráculos y el baseline no promueven requisitos a Implementado/Probado.


## F1-04 — verificación de autoridad implementada

- TC-450/451 y BDD-SC-768/769: `test_corte_ciego_f104.py` verifica evaluador real,
  comandos/API, roles acumulados, Owner revisado, grants superpuestos, revocación,
  errores sin SQL, actor humano y atomicidad. Intentos de autoescalación usan los
  comandos de gobierno reales. La concesión no asigna permisos automáticamente.
- TC-461 parcial: `test_corte_ciego_f104_postgres.py` prueba locks compartidos/exclusivos
  frente a revocación y edición de roles en ambos órdenes con barreras, replay de key
  concurrente y rechazo de aislamiento que conservaría snapshots obsoletos.
- TC-464 parcial: `test_corte_ciego_f104_storage.py` aplica 0101 real, FKs habilitadas,
  inmutabilidad de seis tablas, downgrade vacío y bloqueo con historia en ambos motores.
- Helper `corte_ciego_storage.py` sólo usa SQLite temporal y schemas UUID en una DB
  local corte_ciego_*. `CORTE_CIEGO_TEST_POSTGRES_URL` es obligatoria para esos tests;
  configurada en CI sin añadir skips. No borra public ni reinicia otras bases.

Resultados, revisión R3 y gates pendientes en el [plan §10](implementation-plans/CORTE-CIEGO-001-FASE-1.md#10-f1-04--capacidades-delegación-y-alcance).
No se acredita TC-450/451/461/464 integralmente: las conexiones a lectores/DTO,
replay de caja, exportes, gateway y preflight siguen pendientes. Los RED F1-03 se
conservan sin desactivar; el alcance dirigido F1-04 puede estar verde aunque la
suite integral siga RED. No se cambia por ello el estado global de PRD-FR-289..300.


## F1-05 — proyecciones y acuses de caja

- TC-450/452: `test_corte_ciego_f105.py` ejecuta rutas v2 reales, separa estado/finanzas,
  lectura Dueño/delegado, sucursal/dataset, revocación, capturador propio, gate fase 2,
  aliases v1, ausencia de consulta monetaria antes de autorización y schemas cerrados.
  Comprueba hash del estado histórico, idempotencia, correcciones compensatorias y
  validación previa de lectura de acuse; cambio de política tras commit produce 409
  y recuperación con la misma key sin otro efecto.
- TC-461/463 parcial: `test_corte_ciego_f105_postgres.py` prueba materialización real
  del DTO con importes no nulos frente a revocación/edición de roles, en ambos órdenes,
  bajo barreras PostgreSQL. Repite apertura y finalización concurrentes con la misma
  key; una sola mutación y dos acuses sin finanzas. Consulta también el acuse COUNTED
  histórico después de finalizar, sin reemplazarlo por el estado actual.
- `test_corte_ciego_f105_intents.py`: apertura/cierre v2 preservan workspace, intent
  persistido, atomicidad y acuse; rechaza ejecutar sin preparación requerida.
- Regresión: suites existentes de cortes/contratos, apertura/cierre operativo,
  lifecycle de caja y bloqueo de cierre con gateway; carrera PostgreSQL de cierre/pago.
- `test_corte_ciego_f1_red.py` permanece completo, sin skip/xfail ni cambio de
  expectativas. Su porción F1-05 pasa; reportes/consultas indirectas F1-06 continúan RED.

No se acredita UI, gateway nuevo, denominaciones, completitud central fase 2, exportes,
preflight ni activación. F1-04 ya prueba migración 0101; F1-05 no cambia esquema.
Evidencia exacta y auditoría en [plan §11](implementation-plans/CORTE-CIEGO-001-FASE-1.md#11-f1-05--proyecciones-de-turnos-y-cortes).

## F1-06 — cobertura incremental de lectores

- TC-450/451/461 parcial, comandos de movimientos: `test_corte_ciego_f106_movements.py`
  verifica respuestas HTTP/dominio, replays de snapshots previos, retiro diferenciado
  de lectura/escritura, actor y sucursal alterados, fallos de auditoría, transacción
  exterior y payload técnico, incluido sync con política activa sin conceder lectura
  humana. `test_corte_ciego_f106_movement_postgres.py` verifica duplicados, rollback
  exterior y auditoría fallida; `test_corte_ciego_f106_intent_postgres.py` conserva la
  prueba de compensación real con el acuse nuevo. Regresiones del ledger,
  lifecycle/intents y PCO-008 conservan sus invariantes.

- TC-450/451/462: `test_corte_ciego_f106.py` cubre reporte operativo real, day/week/month,
  calendario local y horario de verano, límite semiabierto, top diez con desempate
  estable y nombres del snapshot, schema cerrado y ausencia de SELECT monetario.
  Verifica páginas financieras, servicios directos, payload de notificaciones, CRM
  corporativo y revalidación antes/después de proveedor AI. Contratos JSON publicados
  se comparan con los schemas runtime para impedir divergencia.
- TC-450: `test_corte_ciego_f106_agents.py` usa credencial técnica real sintética:
  baseline legible, activación sintética, rechazo sin inferir audiencia humana.
- TC-450/461 parcial: `test_corte_ciego_f106_fiscal.py` verifica listado, detalle y
  PDF/XML sin consultar dinero antes de autorización y revocación durante transporte.
  Conserva suites de descarga/autorización/historia fiscal como regresión.
- TC-461/463 parcial: `test_corte_ciego_f106_postgres.py` ejecuta SQL real de reporte y
  páginas financieras, con datos/FK y ambas órdenes de carrera lectura/revocación.
- TC-450/451/462 parcial: `test_corte_ciego_f106_operational.py` verifica listados v2
  de pedidos/clientes: feed mixto paginado y búsqueda sin SELECT monetario, rechazo de
  cursor con filtros distintos, sucursal ajena incluso sin resultados, pérdida de
  `orders.read`, teléfonos, domicilios con precisión y perfil fiscal. El schema anidado
  rechaza campos financieros adicionales; los payloads de importación no salen.
  La consulta histórica del Dueño conserva sus importes; servicios internos sin autoridad
  financiera deniegan. El lote PostgreSQL añade feed mixto, cursor y extracción de campos
  JSON con FK reales. Regresiones: importación legacy y recorrido de múltiples domicilios.
- El archivo `test_corte_ciego_f1_red.py` ahora pasa sus 44 casos sin debilitarlos.
  Esto acredita sus superficies concretas, no cobertura total del inventario F1-01.

- TC-450/451/461/462 parcial: `test_corte_ciego_f106_orders.py` prueba detalle de una
  venta creada por comando real, denegación por ID ajeno aun con motivo/versión enviados,
  consulta histórica financiera, cierre del pedido/turno, actor desactivado y permiso
  retirado. Modificación y asignación de entrega ejecutadas, solicitud pendiente frente
  a reapertura aprobada y cambio de versión. Observa ausencia de SELECT de historia,
  verifica auditoría persistida y fallo cerrado cuando ésta falla; la cotización conserva
  importe y auditoría. Contrato anidado cerrado y resolución de solicitudes web bajo
  la misma guarda. No sustituye el recorrido de impresión ni autoriza grants reales.
- TC-461/463 parcial: `test_corte_ciego_f106_order_postgres.py` comprueba las dos órdenes
  lectura/retiro real de permisos con espera del advisory lock y DTO monetario real.
  El actor carece de delegación financiera para aislar la prueba de atención. Verifica
  también que la guarda canónica de escritura toma autoridad antes del recurso de sucursal.

Pendientes: integración contextual en impresión/replays y canales restantes, proyecciones operativas restantes,
intents/logs, UI, gateway/transición y auditoría integral F1-11. La evidencia acumulada y
los límites se registran en [plan §12](implementation-plans/CORTE-CIEGO-001-FASE-1.md#12-f1-06--avance-de-lectores-y-reportes).


Incremento TDD-TC-450/462 de impresión humana:
`test_corte_ciego_f106_print.py` verifica lista sin SELECT payload/error, servicio sin
actor, retry y replay con contexto retirado por dos causas, rechazo de dos audiencias
técnicas y rollback ante fallo de auditoría. Fixtures usan actor, pedido y permisos
reales en base desechable; no sustituyen las guardas. PostgreSQL ejecuta lectura,
retry/replay, denegación posterior y conservación del payload original en
`test_corte_ciego_f106_print_postgres.py`. Esta prueba no acredita por sí sola todas
las carreras de la cola ni la frontera de dispositivo. La prueba SQLite de reintentos
simultáneos sincroniza antes de entrar al comando: la nueva reserva de escritura
serializa las entradas; conserva las mismas aserciones de un único intento.


Impresión técnica, TDD-TC-450/462: `test_corte_ciego_f106_print_devices.py` comprueba
cola sin contenido, claim auténtico, asignación individual, revocación/fin, servicio
sin dispositivo, SQL sin payload ante denegación, proyección anidada, schemas publicados,
fallos cerrados y revocación posterior al commit de auditoría. En PostgreSQL,
`test_corte_ciego_f106_device_postgres.py` ejerce ambos órdenes lector/revocador con
credencial/FK reales y comprueba espera efectiva con pg_blocking_pids; no sustituye
el recorrido de una impresora física ni el preflight de compatibilidad de F1-09.


Solicitudes operativas, TDD-TC-450/461/462 parcial:
`test_corte_ciego_f106_intents.py` usa preparación/ejecución reales, activación posterior,
retiro diferenciado de lectura/escritura, SQL observado, audiencia técnica y autoridad
cambiada después de commit. `test_corte_ciego_f106_intent_postgres.py` verifica apertura/
cierre reales con IDs JSON, compensación real y evidencia inconsistente en datos
desechables, más recuperación concurrente sin duplicar la resolución. Se conservan
regresiones de atomicidad y no efecto en `test_operational_intents.py`.

Acuses de pedidos/pagos, TDD-TC-450/462: `test_corte_ciego_f106_command_receipts.py`
verifica metadata cerrada, SQL sin snapshots/totales en replay, revocación diferenciada,
cierre de turno/pedido, preflight de lectura antes de cobro, fallo de entrega después
de confirmar, recuperación sin duplicado, preview con contexto/auditoría y paridad de
schema. `test_corte_ciego_f106_receipt_postgres.py` usa pagos reales, dos llamadas
simultáneas con la misma clave y rollback de una transacción exterior commit=False.
La fixture compartida de atención ahora comprueba el acuse del alta; el detalle de
pedido continúa comprobando total 9500 y líneas por la consulta autorizada separada.

Liquidaciones, TDD-TC-450/451/461/462 parcial:
`test_corte_ciego_f106_settlements.py` verifica selección sin suma, conservación de
pendientes, acuse cerrado, replay histórico sin consulta monetaria, lectura/escritura
separadas, recuperación sin efecto y audiencia humana. Se complementa con el gate
PostgreSQL de concurrencia y rollback bajo política activa; no sustituye adaptación
del consumidor POS ni activación de sucursales.

`test_corte_ciego_f106_settlement_postgres.py` usa esquemas aislados con FK reales:
misma clave concurrente devuelve un acuse único; claves distintas sobre los mismos
pedidos producen un ganador; auditoría fallida revierte pagos, comandos e items.
La suite HTTP también cubre revocación tras commit, auditoría fallida, rechazo de
actor/cuerpo/sucursal ajenos y recuperación sin el workspace exigido para cobrar.

Reapertura de pedidos, TDD-TC-450/451/461/462 parcial:
`test_corte_ciego_f106_reopen.py` verifica acuses de solicitud/decisión/aplicación,
replay histórico sin cargar dinero, identidad original, lectura actual independiente
de escritura, listado sin before_snapshot y audiencias humanas. La regresión PCO-005
conserva el dominio de corrección, fórmulas, snapshots y compensaciones.

`test_corte_ciego_f106_reopen_postgres.py` verifica misma clave/claves distintas
concurrentes, una compensación real y rollback junto con auditoría del acuse. Las
pruebas HTTP cubren rollback de solicitud, decisión y aplicación, revocación después
de commit, historial financiero del Dueño revisado y denegación del operador.
El caso de listado vacío mantiene la denegación existente para actor inactivo;
no se presenta como un RED ni exige un cambio artificial de dominio.

Modificaciones de pedidos, TDD-TC-450/451/461/462 parcial:
`test_corte_ciego_f106_amendments.py` prueba modificación real de envío, acuse sin
dinero, SQL sin snapshots financieros, replay histórico, recuperación sin escritura,
audiencias técnicas, claves/cuerpos ajenos, rollback y revocación después de commit.
Los casos históricos sin hash usan fixtures de formato antiguo, sin reescritura
productiva. Deben verificarse transacciones exteriores commit=False y concurrencia
en PostgreSQL, además de regresiones de envío, POS e integración offline afectada.

Logs de integraciones, TDD-TC-450/451/461 parcial: pruebas sobre las cuatro rutas,
administrador/Dueño, payloads anidados, SQL sin columnas sensibles, permisos retirados,
audiencias técnicas, organización ajena, suspensión, auditoría fallida y revocación
tras commit. Comparar originales antes/después y conservar las regresiones de canales.
`test_corte_ciego_f106_integration_logs_postgres.py` verifica selección CASE del estado,
conservación de originales y fallo de auditoría con PostgreSQL/FK reales. Los estados
internos error/failed se conservan; texto libre desconocido se proyecta como unknown.

Gastos, TDD-TC-450/451/461/462 parcial: fixtures reales de documento/concepto/turno;
verificar agregados financieros, metadata paginada, detalle propio por versión,
replay sin result monetario, permiso de lectura independiente de escritura, lápidas
terminales y workspace. Probar retiro/compensación, revocación, fallos de auditoría,
concurrencia PostgreSQL y regresiones EXP-001; no modificar saldos o historia como arreglo.
F1-06 / TC-450/451/462: verificar cancelación con importe no nulo, contrato cerrado,
identidades técnicas, lectura revocada, fallo de auditoría, revocación tras commit,
commit=False, rechazo de duplicado y carrera real PostgreSQL. Regresiones de cancelación
antes/después de producción conservan reservas, merma/recuperación y pagos.

TC-450/451/462, aceptación/asignación: probar ambas rutas de aceptación pública,
pedido pendiente, replay sin SELECT de result/snapshot, identidad original, scopes,
revocación y auditoría, concurrencia PostgreSQL y regresiones de inventario/canales.

TC-450/451/462, historial de repartidores: comprobar denegación antes de SQL monetario,
concesiones por dataset/sucursal y revocación, consolidado, actor humano, auditoría y
revalidación tras commit. Ejecutar también contra PostgreSQL aislado y conservar las
regresiones del historial administrativo sin política activada.

TC-450/451/462, bandejas de canales: probar cuatro proveedores, SQL sin importes ni
snapshots completos, schema cerrado, estado/límite, alcance/identidad, fallo de auditoría
y revocación. Verificar selección JSON y preservación de originales en PostgreSQL.

Refinamiento TDD-TC-450/462: test_corte_ciego_f106_sync_events.py verifica payload
histórico sintético con dinero, proyección SQL sin payload/event_type, actor/scope,
auditoría y revalidación; regresión SEC001 verifica transporte original por dispositivo.
PostgreSQL valida consulta e integridad del evento bajo FK reales.

Refutación de auditoría independiente F1-06: revocar lectura financiera después del
commit de auditoría de descarga fiscal y suspender/revisar política después del commit
de entrega a impresora. Los tests test_fiscal_download_rechecks_after_audit_commit y
test_policy_change_after_commit_prevents_payload_delivery reproducen la entrega anterior
y exigen denegación sin bytes del documento/ticket. No cambia autoridad de negocio.

Refinamiento TDD-TC-461/464: test_corte_ciego_f109_suspension.py añade revisión de
suspensión a una fixture activa y refuta rollback por v1/v2, finanzas y cuentas; verifica
que no se consulten columnas monetarias, no cambie historia ni se concedan capacidades
administrativas protegidas mediante una política suspendida.

F1-07: `tests/frontend/test_corte_ciego_f107_read_context.mjs` prueba respuestas GET
en vuelo y durante parseo, cambio de credencial/autoridad/sucursal, limpieza de caché
y preservación de evidencias pendientes. La protección no depende de ocultar columnas.

F1-07 sesión: test_corte_ciego_f107_session.py contrasta Dueño revisado, delegado
por sucursal/dataset, cajero, grant revocado y política suspendida; el snapshot es
metadato propio, sin convertir capacidad de lectura en acción.


F1-07, TC-450/461/462: test_corte_ciego_f107_cash_screens.mjs prueba capacidades
operativas sin lectura financiera legacy, parsers cerrados y evidencia de comandos
por actor/sucursal con recuperación al remount. test_operational_intents.mjs incluye
preparación central y 409 post-commit para open/close v2. La regresión PostgreSQL
test_corte_ciego_f107_session_postgres.py comprueba revocación persistida sin perder
concesiones independientes ni alterar el fondo histórico. No acredita cierre F1-10.

F1-08, TC-458/459: `test_corte_ciego_f108_inventory.py` refuta alias heredado,
comodín organizacional sin revisión y aprobación implícita por permiso de revisión;
el recorrido HTTP prueba conteo enviado con diferencia, proyección ciega y ausencia de
movimientos ante denegación, seguido de aprobación explícita. Se mantienen regresiones
de conteo legacy. `test_corte_ciego_f108_step_up.py` rechaza código público sin secreto,
administrador sin autoridad explícita y admite secreto propio de autorizador o Dueño.
Recepción y autorización exacta de cambios/cancelaciones siguen pendientes de este bloque.

TC-462, lecturas fiscales concurrentes: `test_fiscal_read_locks_postgres.py` pausa al primer lector
tras su guarda financiera y observa al segundo esperando en PostgreSQL al primero. Listado,
detalle y entradas PDF/XML HTTP, más listado directo del servicio, deben terminar sin ascender
locks compartidos competidores. Las entradas PDF/XML usan un documento draft y conservan el
rechazo de descarga; la carrera fiscal de auditoría cubre por separado revocación post-commit
y cero bytes entregados. La espera se prueba con `pg_blocking_pids`, no con un retraso supuesto.
El verificador de evidencia PostgreSQL exige recolección y aprobación de esta suite; una omisión
o un caso omitido impiden aprobar CI.
