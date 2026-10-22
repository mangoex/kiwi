# CORTE-CIEGO-001 — paquete de trabajo, fases 0 a 2

Fecha: 2026-10-21. Base inspeccionada: `abc4e7f`.
Estado: **CC-D01..12 aprobadas y formalizadas en la cadena canónica;
F1-04/05 implementadas localmente por autorización posterior; resto del alcance pendiente**.
Preparación y registro de aprobaciones: R0 documental. Formalización de decisiones:
**R3 contractual**, por dinero/permisos/offline, con alcance sólo de especificación
y revisión independiente; esa formalización no cambió runtime ni permisos reales.
La ejecución posterior F1-04/05 es R3 local con evidencia en el plan de fase 1.
Riesgo de la implementación futura: **R3**, por permisos, dinero, persistencia,
concurrencia y compatibilidad offline.

## 1. Objetivo, autoridad y alcance

Preparar el cierre de diferencias con las imágenes del cliente: corte ciego,
permisos por función y conteo verificable. Este paquete contiene decisiones
aprobadas, matriz funcional, criterios de aceptación y secuencia de trabajo.
La autorización original cubrió formalización. Solicitudes posteriores cubrieron
F1-01/02, fixtures/RED F1-03 e implementación local F1-04/05 con pruebas en bases
desechables; la migración aditiva pertenece a F1-04, F1-05 no añade esquema. No se autorizaron fases siguientes, commit/push, despliegue,
asignaciones reales ni migración/configuración productiva. Evidencia en el plan F1 §10/11.

Las seis imágenes y el plan de esta conversación son insumos de producto; sus
textos «pedida», «sugerida» y «por definir» no sustituyen una decisión aprobada.
Las recomendaciones no aprobadas tampoco cambian reglas. Las doce resoluciones
aprobadas se incorporan ahora como contrato objetivo, con activación futura según CC-D11.

Fuentes canónicas y puntos de partida:

- [Proceso](../../AGENTS.md): GOV-DEV-001, GOV-DOC-001, GOV-TEST-001 y GOV-REL-001.
- [PRD](../01-PRD.md): PRD-FR-005, 007, 050..058, 218, 219 y PRD-NFR-020..024.
- [SDD](../02-SDD.md): §38.2.7, PCO-006; autoridad offline y caja aplicables.
- [BDD de caja](../03-BDD-pos-cash-ops.md): BDD-SC-286/287 y 327..334.
- [TDD de caja](../04-TDD-pos-cash-ops.md): TDD-TS-081 y TDD-TC-113..120.
- [Matriz vigente](../05-matriz-trazabilidad.md) y
  [handoff PCO-006](PCO-006-TERRA-HANDOFF.md).

La formalización activa PRD/SDD/ADR/BDD/TDD/matriz por cambios explícitos de contrato,
autoridad, estados/proyecciones y cobertura. La tabla de §3.1 enlaza lo aprobado
con sus definiciones canónicas; los resultados runtime del nuevo contrato siguen pendientes.
Los identificadores `CC-D`, `CC-P`, `CC-AC` y `CC-W` son locales a este paquete;
no son nuevos requisitos PRD, escenarios BDD ni pruebas ejecutadas.

Fuera de fases 0..2: motor de compras, márgenes, fidelización, fiscal, programación
de notificaciones y contratación de canales externos. Los eventos de caja deben
conservar evidencia para la fase de alertas, sin construir aquí ese subsistema.
Compras, inventario y tickets aparecen en la matriz sólo para resolver permisos
relacionados; no se rediseñan sus flujos dentro de este paquete.

## 2. Punto de partida y protecciones que se conservan

| Evidencia actual | Diferencia con el objetivo |
|---|---|
| `GET /cash-shifts/summary` exige `cash.shift.read` y retorna resumen monetario; el perfil Cajero incluye ese permiso | Lectura operativa y lectura financiera no están separadas. Ver [API](../../apps/api/restaurant_os/api.py) y `_assign_default_role_permissions` / `_cash_summary_for_shift` en [operations](../../apps/api/restaurant_os/operations.py). |
| `UserCashCutService.counted_cash` recibe `counted_cash_cents` y `version` | No representa denominaciones ni declaración por otros medios. |
| PCO-006 exige Líder+ para finalizar y devuelve snapshot financiero al lector autorizado | Dar captura al cajero y ocultar resultados al encargado requiere cambiar explícitamente el contrato y las proyecciones. |
| Estados `DRAFT -> COUNTED -> FINALIZED`, reautorización, idempotencia y compensación | Se extienden; no se reemplazan por edición libre del corte. |
| BDD-SC-332/333 reserva al Dueño solicitar, decidir y compensar reapertura; no exige dos personas | Una delegación o separación de cuatro ojos es una decisión nueva, no una regla ya vigente. |

La auditoría previa de esta conversación reprodujo en SQLite una lectura del
esperado por un Cajero predeterminado y reportó 71 pruebas focales aprobadas.
Es evidencia antecedente, no una ejecución de este paquete ni certificación
productiva. El paquete confirma estáticamente los puntos de entrada anteriores.

Se preservan: fuente canónica de cajero/turno/periodo, centavos enteros y cálculo
Python, pagos y movimientos inmutables, asociaciones exclusivas de operaciones,
snapshots históricos, compensaciones referenciadas, separación por organización
y sucursal, reservas/consumos de inventario, recetas versionadas y recepciones
parciales. No se alteran saldos ni se reconstruye historia para hacer pasar un corte.

## 3. Fase 0: registro de decisiones

**CC-D01..12 están APROBADAS; registro de decisiones cerrado.** Cada resolución
conserva opción elegida, alcance, motivo, aprobador, fecha y evidencia de aceptación.
Los responsables funcionales sugeridos no acreditan participación adicional.
El cierre y formalización no completan el mapeo de usuarios ni la implementación;
tampoco conceden facultades no incluidas en las decisiones.

| ID | Decisión aprobada | Alcance, límites y seguimiento | Aprobación / dependencia |
|---|---|---|---|
| CC-D01 | **APROBADA.** Dueño con acceso financiero por defecto; delegado financiero con acceso explícito, limitado y revocable | Delegación admitida; Administrador/Supervisor no adquieren acceso por su nombre de rol. Alcance y aceptación registrados debajo | Aprobada por Miguel Gonzalez, 2026-10-21 / base de lecturas de fase 1; transición depende de CC-D02/11 |
| CC-D02 | **APROBADA.** Conservar roles, mapear Líder a encargado y revisar individualmente permisos efectivos antes de aplicar la distribución | Cajero Jefe sin equivalencia automática a encargado; Administrador/Supervisor sin acceso financiero automático. Revisar roles acumulados y grants generales; asignaciones concretas pendientes | Aprobada por Miguel Gonzalez, 2026-10-21 / base de transición de permisos; activación depende de CC-D11 |
| CC-D03 | **APROBADA.** Cajero captura su turno; encargado puede sustituirlo con identidad y motivo. Encargado o Dueño finaliza; el cajero no finaliza por sí mismo | Sin encargado ni Dueño disponible, el conteo confirmado queda pendiente de finalización e ineditable. Acuse del encargado sin esperado/diferencia; no se exige una segunda persona distinta si capturó por sustitución | Aprobada por Miguel Gonzalez, 2026-10-21 / captura y finalización; detalle D04, corrección D07 y offline D10 aprobados |
| CC-D04 | **APROBADA.** MXN, efectivo por denominaciones configurables por Dueño y declaración separada por medio; borrador editable trazable y confirmación única ineditable | Cero explícito distinto de no contado; suma de captura propia visible, esperado oculto. Conteo y entrega de custodia separados; conciliación resuelta en D05 | Aprobada por Miguel Gonzalez, 2026-10-21 / modelo de conteo; corrección D07 y offline D10 aprobados |
| CC-D05 | **APROBADA.** Conciliar cada medio por separado; efectivo esperado desde ledger confirmado y entradas/salidas contadas una vez | Permitir finalización con pendientes de conciliación explícitos, sin esperado cero inventado ni sobrescribir el corte. Repartidor, pago mixto, devoluciones y propinas según resolución; operaciones locales desconocidas bloquean finalización según D10 | Aprobada por Miguel Gonzalez, 2026-10-21 / conciliación por medio; tolerancia D06 y offline D10 aprobados |
| CC-D06 | **APROBADA.** Tolerancia inicial $0.00 MXN; registrar diferencia exacta por medio y avisar por cualquier resultado confirmado distinto de cero | Diferencia no bloquea finalización ni implica aprobar faltante; no compensar entre medios ni inventar diferencia por información incompleta. Envíos y reintentos corresponden a fase 3 | Aprobada por Miguel Gonzalez, 2026-10-21 / resultado del corte y regla de alertas, sin activar envíos |
| CC-D07 | **APROBADA.** Operador reporta error; sólo Dueño solicita formalmente, autoriza y aplica corrección vinculada sin editar original | Sin segundo aprobador. Conteo confirmado aún no finalizado conserva declaración original: se finaliza según D03 y después se compensa. No modifica ledger ni duplica pagos | Aprobada por Miguel Gonzalez, 2026-10-21 / correcciones y proyecciones |
| CC-D08 | **APROBADA.** Cajero edita borrador; todo cambio o cancelación posterior a aceptar requiere autorización del encargado o Dueño. Descuentos/cortesías también, incluso en borrador | Autorización individual para la acción exacta, sin compartir credenciales; conserva guardas por estado, pago y producción. Sin autorizador disponible queda pendiente | Aprobada por Miguel Gonzalez, 2026-10-21 / permisos de pedidos, sin aplicar grants |
| CC-D09 | **APROBADA.** Encargado recibe cantidades sin costos por defecto; acceso a precios mediante autorización explícita y limitada. Conteo ciego separado de revisión y aprobación administrativa del ajuste | Dueño o responsable administrativo expresamente autorizado revisa y aprueba; separación de funciones/permisos, sin obligación general de dos aprobadores. Recepción no concede administración del catálogo | Aprobada por Miguel Gonzalez, 2026-10-21 / permisos colaterales; asignaciones individuales pendientes D02/11 |
| CC-D10 | **APROBADA.** Captura local durable con acuse provisional; finalización central por encargado o Dueño tras verificar sincronización completa y autoridad vigente | Vencimientos o conflictos dejan pendientes con evidencia; sin renovación local de permisos, sobrescritura ni doble finalización. Completitud incluye cierre y operaciones de fuentes autorizadas, no sólo cola vacía | Aprobada por Miguel Gonzalez, 2026-10-21 / frontera offline; protocolo técnico y pruebas pendientes antes de habilitación |
| CC-D11 | **APROBADA.** Transición por sucursal entre turnos, con pendientes anteriores resueltos, permisos revisados individualmente y bloqueo de versiones incompatibles | Piloto inicial; concluir/sincronizar turnos y finalizar conteos previos por flujo compatible antes de activar. Historia inmutable y lectura bajo autoridad vigente; sin reconstruir denominaciones ni reversión que filtre importes | Aprobada por Miguel Gonzalez, 2026-10-21 / política de transición; sucursal, fecha y autorización productiva aún pendientes |
| CC-D12 | **APROBADA.** Encargado consulta número de tickets y top 10 por sucursal, día/semana/mes; top 10 sólo nombres y posiciones. Consulta individual acotada; agregados monetarios sólo Dueño o delegado financiero autorizado | Sin listados/exportaciones monetarias masivas para perfiles operativos ni cantidades/precios/costos/márgenes en ranking restringido. Misma protección en API y asistentes; no promete impedir estimaciones humanas | Aprobada por Miguel Gonzalez, 2026-10-21 / reportes y criterios contra exposición de información |

### Resolución CC-D01 — acceso financiero y delegación

- Estado: **APROBADA como decisión de producto del paquete**, sin implementación.
- Aprobador: Miguel Gonzalez, mediante instrucción explícita en esta conversación.
- Fecha: 2026-10-21, zona America/Mazatlan.
- Evidencia de aceptación: «Apruebo tu recomendación: Dueño por defecto y delegado
  financiero con acceso limitado y revocable. Regístralo en el paquete y pasemos
  a la decisión 2, sin implementar código.»
- Alcance aprobado: el Dueño tiene acceso por defecto al efectivo esperado y sus
  componentes agregados, ventas monetarias acumuladas, faltantes/sobrantes y ticket
  promedio. Un delegado financiero sólo consulta información y sucursales dentro
  de la delegación explícita concedida, que puede revocarse.
- Cajero y encargado mantienen oculta esa información antes y después del conteo;
  pueden ver el importe del pedido que atienden según sus permisos operativos.
  La restricción aplica en pantallas, API, reportes y exportaciones.
- La delegación no concede automáticamente corrección de cortes, modificación de
  pagos, administración de permisos ni facultades operativas. Administrador y
  Supervisor no reciben acceso financiero por el nombre del rol.
- Justificación aceptada: proteger el corte ciego y permitir apoyo financiero
  acotado sin conceder toda la autoridad del Dueño. Se descarta como política
  general el acceso exclusivo del Dueño sin posibilidad de delegación.
- Seguimiento: CC-D02 aprueba la distribución y revisión individual; CC-D11 aprueba
  la política de transición. Su ejecución y activación permanecen pendientes.
  CC-D07 reserva correcciones al Dueño. No se asignan personas,
  sucursales ni permisos concretos mediante esta aprobación.

### Resolución CC-D02 — distribución de roles y revisión individual

- Estado: **APROBADA como decisión de producto del paquete**, sin implementación.
- Aprobador: Miguel Gonzalez, mediante instrucción explícita en esta conversación.
- Fecha: 2026-10-21, zona America/Mazatlan.
- Evidencia de aceptación: «Apruebo la distribución de roles y la revisión
  individual de permisos antes de aplicarla. Registra CC-D02 como aprobada y
  pasemos a la decisión 3, sin implementar código.»
- Distribución aprobada: Cajero para operación de venta y captura autorizada, sin
  información financiera agregada; Líder como equivalente funcional del encargado,
  limitado a sus sucursales; Cajero Jefe como perfil operativo con facultades
  adicionales explícitas, sin equivalencia automática a encargado.
- Administrador y Supervisor conservan sus funciones administrativas autorizadas;
  el acceso financiero requiere la delegación de CC-D01. Dueño conserva autoridad
  y acceso financiero. No se renombran ni eliminan roles para lograr esta separación.
- Antes de aplicar cambios se revisarán los permisos efectivos de cada usuario,
  incluyendo roles combinados, especialidades, compatibilidades legacy y grants
  generales como `organization_all_permissions`. Una cuenta operativa restringida
  no debe conservar una autorización general que evada el corte ciego; las
  excepciones financieras deben quedar explícitas conforme a CC-D01.
- Justificación aceptada: impedir accesos indirectos por acumulación de permisos
  y preservar funciones necesarias sin retirar facultades indiscriminadamente.
- Seguimiento: CC-D03 resuelve responsables de captura y finalización. Permanecen
  pendientes revisión y mapeo de usuarios reales y ejecución de la transición
  cuya política aprueba CC-D11;
  CC-D09 ya define recepción, acceso a precios y autoridad de ajustes de inventario;
  CC-D08 ya define autorización de cambios/cancelaciones y descuentos/cortesías;
  CC-D04..07 ya definen captura, separación por medio, tolerancia/alertas y correcciones.
  Esta aprobación no modifica cuentas, sesiones, roles ni permisos persistidos.

### Resolución CC-D03 — captura y finalización del corte

- Estado: **APROBADA como decisión de producto del paquete**, sin implementación.
- Aprobador: Miguel Gonzalez, mediante instrucción explícita en esta conversación.
- Fecha: 2026-10-21, zona America/Mazatlan.
- Evidencia de aceptación: «Apruebo el flujo: el cajero captura y el encargado
  o Dueño finaliza; si no están disponibles, queda pendiente. Registra CC-D03
  como aprobada y pasemos a la decisión 4, sin implementar código.»
- Flujo aprobado: el Cajero cierra operativamente su turno, que ya no admite
  ventas, y cuenta/confirma su captura. Si está ausente, el encargado puede
  capturar por sustitución, registrando identidad y motivo sin cambiar al cajero
  responsable original del turno.
- Sólo encargado (Líder) o Dueño finaliza. El Cajero no finaliza por sí mismo.
  Si ambos están indisponibles, el conteo confirmado permanece pendiente de
  finalización e ineditable; no se reajusta para coincidir con el esperado.
- El encargado recibe acuse sin esperado, diferencia ni indicador de
  «cuadró/no cuadró», conforme a CC-D01. Consultar como delegado financiero
  no concede facultad para finalizar.
- No se exige una segunda persona distinta si el encargado capturó por
  sustitución. Finalizar registra el resultado, no aprueba un faltante.
- Justificación aceptada: distinguir declaración y finalización, conservar
  autoridad de Líder o Dueño y atender ausencias con trazabilidad sin editar
  la declaración confirmada.
- Seguimiento: CC-D04 aprueba el esquema de captura; CC-D07 aprueba correcciones y CC-D10 define
  las condiciones offline. No se amplían por inferencia las facultades de
  Administrador, Supervisor o Cajero Jefe, ni se define aquí apertura de otro turno.

### Resolución CC-D04 — desglose, borrador y confirmación única

- Estado: **APROBADA como decisión de producto del paquete**, sin implementación.
- Aprobador: Miguel Gonzalez, mediante instrucción explícita en esta conversación.
- Fecha: 2026-10-21, zona America/Mazatlan.
- Evidencia de aceptación: «Apruebo el esquema de captura, borrador editable y
  confirmación única. Registra CC-D04 como aprobada y pasemos a la decisión 5,
  sin implementar código.»
- Moneda: MXN en este incremento, sin conversiones de divisas. Efectivo declarado
  como cantidad de billetes y monedas por denominación habilitada; Python calcula
  el total exacto. Se cuenta todo el efectivo presente, incluido el fondo que
  permanezca en caja.
- El Dueño configura el catálogo de denominaciones. Cada conteo conserva las
  denominaciones utilizadas para que cambios posteriores no alteren su historia.
  La decisión no fija aquí un listado de denominaciones ni concede configuración
  a un delegado financiero por el solo hecho de consultar resultados.
- Débito, crédito, transferencias y plataformas habilitadas se declaran por
  separado, con importe y cantidad de comprobantes o referencias cuando corresponda.
  Vacío significa no contado; cero requiere declaración explícita. No se rellenan
  campos con el esperado del sistema.
- Se permite guardar y corregir borrador antes de confirmar, con trazabilidad.
  El cajero puede ver desglose y total de su propia captura, nunca el esperado.
  Una revisión del desglose precede a la confirmación única; después no se edita
  ni se reemplaza la declaración y las correcciones siguen CC-D07.
- Se registra quién contó. Una entrega posterior de efectivo o comprobantes
  registra receptor y fecha/hora; confirmar conteo no acredita por sí mismo
  entrega física ni cambio de custodia.
- Justificación aceptada: hacer verificable lo contado, reducir errores de suma,
  distinguir captura incompleta de cero real y evitar pérdida de trabajo antes de
  la confirmación, preservando después la declaración definitiva.
- Seguimiento: CC-D05 aprueba fuentes de comparación y tratamiento de pendientes;
  CC-D07 aprueba correcciones; CC-D10 define persistencia/sincronización offline.

### Resolución CC-D05 — conciliación por medio y pendientes explícitos

- Estado: **APROBADA como decisión de producto del paquete**, sin implementación.
- Aprobador: Miguel Gonzalez, mediante instrucción explícita en esta conversación.
- Fecha: 2026-10-21, zona America/Mazatlan.
- Evidencia de aceptación: «Apruebo la separación por medio y la finalización
  con pendientes de conciliación explícitos. Registra CC-D05 como aprobada y
  pasemos a la decisión 6, sin implementar código.»
- Efectivo: esperado desde el ledger vigente = fondo inicial + entradas
  confirmadas - salidas confirmadas. Cada efecto se contabiliza una sola vez.
- Débito/crédito: declaración contra pagos confirmados de cada tipo; el depósito
  bancario posterior se concilia aparte y no aumenta el efectivo del cajón.
- Transferencias: declaración contra transferencias confirmadas y referenciadas;
  un comprobante pendiente de verificar no acredita automáticamente cobro confirmado.
- Plataformas: separar cobros realizados por plataforma de los recibidos por
  restaurante. Liquidación, comisiones y ajustes se revisan aparte; el canal del
  pedido no determina por sí solo quién recibió el dinero.
- Pagos mixtos: cada parte pertenece a su medio. Pedido de $500 MXN con $200 en
  efectivo y $300 en tarjeta sólo aporta $200 al efectivo esperado.
- Repartidor: efectivo no entregado permanece pendiente bajo su responsabilidad.
  Al recibirlo, se registra en el turno receptor y se enlaza al pedido, sin duplicar
  venta/cobro ni reabrir el turno anterior. La venta y la recepción física son
  hechos distintos; nunca sumar ambos como dos entradas de efectivo.
- Devoluciones: afectan sólo el medio correspondiente mediante devolución o
  compensación confirmada. Cancelar el pedido no prueba devolución del dinero.
- Propinas: separadas de ventas; si pasan por caja, necesitan entradas y entregas
  trazables. Mientras ese flujo no exista, no se habilita su manejo integrado;
  esta decisión no implementa un módulo de propinas dentro del paquete.
- Información insuficiente: conservar declaración y motivo de pendiente por
  medio. No inventar esperado cero ni informar que está cuadrado. Encargado o
  Dueño puede finalizar la declaración del turno con excepciones documentadas;
  la autoridad financiera ve las conciliaciones pendientes. El acuse operativo
  conserva las restricciones de CC-D01/03.
- Resultados posteriores se vinculan sin sobrescribir corte ni declaración
  originales. Finalización de declaración y conciliación completa son dimensiones
  distintas; los estados/contratos concretos se definirán en SDD antes de código.
- Justificación aceptada: evitar faltantes ficticios por dinero aún en custodia
  del repartidor, banco o plataforma y evitar duplicar ingresos.
- Límite: pendientes de conciliación documentados no autorizan ignorar operaciones
  offline todavía desconocidas. CC-D10 define esa frontera; CC-D06 aprueba
  tolerancia/alertas y CC-D07 aprueba correcciones de una declaración ya confirmada.

### Resolución CC-D06 — tolerancia cero y aviso de diferencias

- Estado: **APROBADA como decisión de producto del paquete**, sin implementación.
- Aprobador: Miguel Gonzalez, mediante instrucción explícita en esta conversación.
- Fecha: 2026-10-21, zona America/Mazatlan.
- Evidencia de aceptación: «Apruebo tolerancia de $0.00, aviso por cualquier
  diferencia confirmada y finalización sin aprobar el faltante. Registra CC-D06
  como aprobada y pasemos a la decisión 7, sin implementar código.»
- Tolerancia inicial: $0.00 MXN. Conservar diferencia exacta en centavos por medio,
  tanto faltante como sobrante, sin redondearla a cero para declarar que cuadró.
  Un sobrante en efectivo no compensa automáticamente un faltante en tarjeta.
- La diferencia no bloquea la finalización por encargado o Dueño; queda para
  revisión. Finalizar no perdona, aprueba ni elimina un faltante. Se mantienen
  las demás validaciones y condiciones de CC-D03/05/10.
- Con fuente insuficiente, registrar pendiente de conciliación con motivo;
  no inventar diferencia. Cuando exista resultado confirmado distinto de cero,
  generar aviso al Dueño. Delegados sólo lo reciben con autorización vigente
  para esa información y designación como destinatarios.
- Cajero y encargado conservan acuse sin diferencia, «cuadró/no cuadró» ni
  indicación de que se generó alerta financiera, conforme a CC-D01/03.
- Fallo del canal: conservar aviso pendiente y reintentar sin bloquear el corte
  ni perder el evento. Registro de diferencias y umbral de notificación son
  conceptos separados: inicialmente se avisa toda diferencia confirmada no cero.
- Justificación aceptada: conocer frecuencia e impacto reales de las diferencias
  desde el inicio, sin ocultar pérdidas pequeñas repetidas ni cruzar medios.
  Un umbral o resumen futuro requiere una nueva decisión; no borra diferencias
  ni cambia resultados históricos.
- Alcance: la entrega de alertas sigue en fase 3. Esta aprobación fija la regla,
  no configura canales, destinatarios concretos ni envíos ahora. CC-D07 aprueba
  la corrección de declaraciones confirmadas sin editar sus originales.

### Resolución CC-D07 — reporte de errores y corrección exclusiva del Dueño

- Estado: **APROBADA como decisión de producto del paquete**, sin implementación.
- Aprobador: Miguel Gonzalez, mediante instrucción explícita en esta conversación.
- Fecha: 2026-10-21, zona America/Mazatlan.
- Evidencia de aceptación: «Apruebo que el operador reporte errores y sólo el
  Dueño solicite, autorice y aplique correcciones, sin segundo aprobador.
  Registra CC-D07 como aprobada y pasemos a la decisión 8, sin implementar código.»
- Cajero o encargado puede reportar un error con motivo y evidencia, dentro de
  su alcance, sin editar conteo ni consultar esperado. Reportar no crea por sí
  mismo una solicitud formal de compensación ni concede autoridad financiera.
- Sólo Dueño revisa el reporte y solicita formalmente la corrección con desglose
  o importe corregido, motivo y referencias de evidencia; sólo Dueño aprueba,
  rechaza y aplica. La delegación de consulta no concede estas facultades.
- No se exige un segundo aprobador: el mismo Dueño puede solicitar y aprobar,
  conservando identidad y evidencia de ambas acciones.
- La corrección es un ajuste vinculado: original, corrección y diferencia entre
  ambos permanecen consultables por autoridad financiera. No se borra ni
  sobrescribe la captura, no se liberan asociaciones y no se duplican pagos
  o movimientos al aplicar o reintentar la corrección.
- Error detectado en conteo confirmado todavía no finalizado: conservar y
  finalizar la declaración original conforme a CC-D03 y después aplicar la
  corrección autorizada. El reporte de error no habilita edición ni permite
  saltarse las restantes condiciones de finalización, incluida CC-D10.
- Justificación aceptada: corregir errores reales sin perder la declaración
  original, con un único procedimiento y sin crear una vía de edición posterior.
- Límite: corregir el conteo no crea dinero ni corrige venta, pago o retiro.
  Errores en operaciones requieren su procedimiento canónico correspondiente.
  Este registro no otorga permisos ni implementa reporte, compensación o alertas.

### Resolución CC-D08 — autorización de cambios de pedidos y descuentos

- Estado: **APROBADA como decisión de producto del paquete**, sin implementación.
- Aprobador: Miguel Gonzalez, mediante instrucción explícita en esta conversación.
- Fecha: 2026-10-21, zona America/Mazatlan.
- Evidencia de aceptación: «Apruebo autorización del encargado o Dueño para cambios
  y cancelaciones de pedidos aceptados, y para descuentos o cortesías. Registra
  CC-D08 como aprobada y pasemos a la decisión 9, sin implementar código.»
- El Cajero puede editar productos, cantidades y modificadores de su borrador no
  confirmado o descartarlo, conservando precios y validaciones del servidor.
  Todo cambio o cancelación posterior a aceptar el pedido, incluso sin pago,
  requiere autorización del encargado (Líder) o Dueño, con motivo.
- Descuentos y cortesías requieren esa autorización incluso antes de confirmar
  el pedido. El permiso de operar una venta no permite autorizarlos por sí mismo.
- La autorización corresponde a una acción concreta y su contenido revisado.
  El autorizador se identifica con sus propias credenciales; quedan registrados
  solicitante, autorizador, motivo y antes/después. No se comparten credenciales
  ni se hereda una sesión permanente de supervisor al cajero.
- Si cambia el pedido o el contenido autorizado, se requiere nueva autorización;
  un reintento idéntico no duplica efectos. Si no hay encargado ni Dueño disponible,
  la acción sensible queda pendiente, sin aplicarse.
- Autorizar no evade transiciones ni guardas por producción o pago: un cambio
  incompatible con el estado permanece bloqueado. Una cancelación permitida tras
  producción conserva la clasificación de merma o recuperación autorizada, sin
  devolución automática al inventario. Un pago original no se edita ni borra;
  cualquier corrección o devolución sigue el flujo canónico correspondiente.
- Justificación aceptada: permitir captura ágil del borrador y establecer control
  explícito cuando el cambio puede afectar cocina, inventario o dinero, con
  responsabilidad individual y sin eludir invariantes de RestaurantOS.
- Límite y seguimiento: no amplía autoridad del delegado financiero, ni resuelve
  o modifica permisos de retiros. CC-D10 define condiciones offline. CC-D02/11
  mantienen pendiente la revisión de usuarios y activación; no se aplican grants.

### Resolución CC-D09 — recepción, costos y ajustes de inventario

- Estado: **APROBADA como decisión de producto del paquete**, sin implementación.
- Aprobador: Miguel Gonzalez, mediante instrucción explícita en esta conversación.
- Fecha: 2026-10-21, zona America/Mazatlan.
- Evidencia de aceptación: «Apruebo recepción sin costos por defecto, acceso a
  precios con autorización explícita y ajustes con revisión y aprobación
  administrativa separadas. Registra CC-D09 como aprobada y pasemos a la decisión
  10, sin implementar código.»
- El encargado registra cantidades recibidas contra la compra autorizada,
  incluidas entregas parciales y diferencias justificadas. No ve precios ni
  costos por defecto; su consulta requiere concesión explícita y limitada cuando
  la función lo necesite. Recibir no concede modificar precios, presentaciones,
  conversiones ni administrar el catálogo.
- Cajero o encargado autorizado captura inventario físico dentro de su alcance,
  sin ver existencias teóricas, costos ni diferencias. Enviar el conteo no ajusta
  existencias. Se conservan las capacidades separadas de captura, revisión y
  aprobación de RestaurantOS.
- Dueño o responsable administrativo expresamente autorizado revisa y aprueba
  ajustes mediante permisos separados. Ser encargado no concede esa autoridad
  automáticamente. La separación es de funciones y permisos; no introduce una
  obligación general de dos aprobadores ni de personas distintas para cada etapa.
- Los ajustes generan movimientos trazables y preservan compras, ventas y
  traspasos registrados mientras se contaba; no sobrescriben saldos ni historia.
- La delegación financiera de caja no autoriza ajustes de inventario ni
  administración de compras. Acceder a precios tampoco concede por inferencia
  administración de recetas, márgenes, catálogo o información agregada de caja.
- Justificación aceptada: permitir recepción operativa sin abrir acceso general
  a costos y catálogo, y conservar el control administrativo antes de convertir
  una declaración física en movimientos de inventario.
- Seguimiento: revisar concesiones y asignaciones individuales según CC-D02/11,
  incluida autoridad heredada que reúna captura, revisión y aprobación. No se
  asignan responsables concretos ni se modifican cuentas o permisos persistidos.

### Resolución CC-D10 — captura offline y finalización central

- Estado: **APROBADA como decisión de producto del paquete**, sin implementación.
- Aprobador: Miguel Gonzalez, mediante instrucción explícita en esta conversación.
- Fecha: 2026-10-21, zona America/Mazatlan.
- Evidencia de aceptación: «Apruebo captura local con acuse provisional y
  finalización central tras verificar sincronización completa, con pendientes
  ante vencimientos o conflictos. Registra CC-D10 como aprobada y pasemos a la
  decisión 11, sin implementar código.»
- Ante pérdida de internet, permitir cierre operativo y conteo mediante gateway
  de sucursal con identidad y autorización offline válidas. Persistir en SQLite,
  sin depender sólo del navegador; conservar la declaración ante reinicios.
- La confirmación local es única e ineditable; su acuse indica guardado local y
  sincronización pendiente, sin esperado ni diferencias. No equivale a aceptación
  central ni a corte finalizado y no habilita una segunda captura al reconectar.
- Antes de finalizar, el servidor verifica cierre del turno y recepción completa
  de sus operaciones desde las fuentes autorizadas. Una cola vacía por sí sola
  no demuestra completitud. Sincronizar operaciones y conteo con idempotencia;
  recuperar el resultado sin duplicar efectos cuando se pierde el acuse.
- Sólo encargado o Dueño, con autoridad vigente, finaliza centralmente según
  CC-D03. Pendientes bancarios o de plataformas explícitos de CC-D05 son admisibles;
  operaciones locales desconocidas o sincronización incompleta bloquean la
  finalización. Se distingue completitud operativa de conciliación externa.
- Una autorización offline vencida bloquea nuevos comandos sensibles y conserva
  lo registrado. No se renuevan permisos localmente ni se promete revocación
  instantánea durante la desconexión. Al reconectar se valida autoridad vigente;
  un conflicto de autoridad o datos queda pendiente con evidencia preservada.
- No sobrescribir conteos, compensar automáticamente ni aceptar dos finalizaciones
  para resolver conflictos. Caída prolongada o fallo del gateway no habilitan
  ampliación de permisos ni corte definitivo: conservar evidencia recuperable;
  cualquier registro de contingencia queda pendiente, nunca como corte confirmado.
- Justificación aceptada: permitir contar y entregar el turno sin esperar internet,
  evitando calcular faltantes sobre operaciones ausentes y conservando la frontera
  entre persistencia local, sincronización y finalización central.
- Seguimiento: formalizar protocolo de completitud, autoridad y recuperación en
  SDD/BDD/TDD antes de implementar. Habilitación condicionada a pruebas de durabilidad,
  recuperación, autorización y ausencia de duplicados; sin soporte comprobado el
  recorrido queda fuera del piloto. Esta aprobación no certifica capacidad actual
  ni autoriza nuevos comandos offline de pedidos u otros dominios por inferencia.

### Resolución CC-D11 — transición por sucursal entre turnos

- Estado: **APROBADA como decisión de producto del paquete**, sin implementación.
- Aprobador: Miguel Gonzalez, mediante instrucción explícita en esta conversación.
- Fecha: 2026-10-21, zona America/Mazatlan.
- Evidencia de aceptación: «Apruebo la transición por sucursal entre turnos, con
  pendientes resueltos, revisión individual de permisos y bloqueo de versiones
  incompatibles. Registra CC-D11 como aprobada y pasemos a la decisión 12, sin
  implementar código.»
- Activar inicialmente una sucursal piloto, registrando fecha y versión de la
  política; ampliar después de verificar su operación. Revisar permisos efectivos
  y delegaciones de cada usuario antes de activar conforme a CC-D02, sin inferir
  autoridad por nombre de rol ni conservar grants que evadan las restricciones.
- Concluir y sincronizar turnos abiertos antes del cambio; no convertir un turno
  a mitad de operación. Conteos ya confirmados conservan su declaración original
  y se finalizan mediante flujo compatible antes de activar, sin segunda captura
  ni denominaciones inventadas. Pendientes anteriores incompatibles posponen la
  activación de esa sucursal; no se fuerzan cierres ni se alteran datos para avanzar.
- Exigir versiones compatibles y revalidación de autoridad; bloquear clientes
  incompatibles. Resolver o agotar autorizaciones offline anteriores antes de
  activar, conservando operaciones y evidencia pendientes según CC-D10.
- Conservar importes y documentos históricos originales e identificar cortes
  antiguos sin desglose. Desde la activación, consultas y exportaciones, incluso
  históricas, se rigen por los nuevos permisos; no se conserva acceso financiero
  por haber podido consultar antes ni se reconstruye detalle inexistente.
- Si falla el piloto, detener ampliación y recuperar mediante una versión
  compatible que conserve conteos y movimientos. No volver a una versión que
  exponga importes restringidos ni ejecutar una reversión destructiva de historia.
- Justificación aceptada: evitar dos reglas dentro de un mismo turno y accesos
  por sesiones antiguas, comprobar operación en una sucursal y preservar historia
  bajo la autoridad de consulta vigente.
- Seguimiento: la sucursal concreta, fecha, asignaciones y activación productiva
  requieren definición y autorización posteriores. Esta decisión aprueba la
  política, no despliegue, migraciones, cambios reales de permisos ni piloto.

### Resolución CC-D12 — reportes operativos y consulta acotada de tickets

- Estado: **APROBADA como decisión de producto del paquete**, sin implementación.
- Aprobador: Miguel Gonzalez, mediante instrucción explícita en esta conversación.
- Fecha: 2026-10-21, zona America/Mazatlan.
- Evidencia de aceptación: «Apruebo los reportes para el encargado, top 10 sólo
  con nombres y posiciones, consulta individual acotada y agregados monetarios
  para Dueño o delegado financiero. Registra CC-D12 como aprobada y cierra las
  decisiones, sin implementar código.»
- Cajero consulta pedidos que atiende; encargado consulta los de su sucursal
  necesarios para seguimiento y autorizaciones. Pueden ver el importe de la
  operación individual, sin habilitar historial monetario masivo ni exportaciones
  que permitan sumar directamente la venta del periodo.
- Encargado consulta número de tickets de su sucursal por día, semana y mes;
  el Cajero no recibe ese reporte. Mantener definición canónica del indicador,
  sin contar reimpresiones como ventas nuevas.
- Encargado consulta top 10 de productos de su sucursal para esos periodos, sólo
  con nombres y posiciones. La vista restringida omite cantidades, precios,
  ingresos, costos y márgenes.
- Venta total, ticket promedio, esperado y diferencias de caja se reservan al
  Dueño o delegado financiero dentro de su autorización, antes y después del
  corte, conforme a CC-D01. Lectura financiera no concede facultades operativas.
- Las restricciones se aplican a API, reportes, descargas, asistentes y demás
  superficies del paquete, no sólo a columnas visibles. Las consultas individuales
  no deben convertirse mediante listados o exportación en un agregado prohibido.
- Justificación aceptada: número de tickets y ranking ayudan a supervisar actividad
  y preferencias. Ticket promedio con número de tickets revela venta total;
  cantidades por producto combinadas con precios facilitan reconstruirla.
- Límite explícito: un operador que cobra conoce importes individuales y puede
  recordarlos o anotarlos. El compromiso es evitar exposición de agregados y
  reconstrucción directa mediante reportes del sistema, no impedir toda estimación.
- Seguimiento: concretar filtros, periodos y contratos de consulta al formalizar,
  con pruebas de alcance y exposición. No habilita reportes ni cambia grants.

### 3.1 Correspondencia canónica de las decisiones

Formalización documental autorizada, 2026-10-21. Todos los requisitos nuevos están
en estado `Disenado`; ningún escenario/caso nuevo se declara ejecutado. Diseño
común: SDD §71 y SDD-ADR-048. Las aprobaciones textuales anteriores se preservan.

| Decisión | PRD | SDD | BDD | TDD principal |
|---|---|---|---|---|
| CC-D01 | PRD-FR-289 | §71.1 | BDD-SC-767, BDD-SC-768 | TDD-TC-450 |
| CC-D02 | PRD-FR-290 | §71.2 | BDD-SC-769, BDD-SC-770 | TDD-TC-451 |
| CC-D03 | PRD-FR-291 | §71.3 | BDD-SC-771, BDD-SC-772 | TDD-TC-452 |
| CC-D04 | PRD-FR-292 | §71.4 | BDD-SC-773, BDD-SC-774 | TDD-TC-453, TDD-TC-454 |
| CC-D05 | PRD-FR-293 | §71.5 | BDD-SC-775, BDD-SC-776, BDD-SC-777 | TDD-TC-455 |
| CC-D06 | PRD-FR-294 | §71.6 | BDD-SC-778, BDD-SC-779 | TDD-TC-456 |
| CC-D07 | PRD-FR-295 | §71.7 | BDD-SC-780, BDD-SC-781 | TDD-TC-457 |
| CC-D08 | PRD-FR-296 | §71.8 | BDD-SC-782, BDD-SC-783 | TDD-TC-458 |
| CC-D09 | PRD-FR-297 | §71.9 | BDD-SC-784, BDD-SC-785 | TDD-TC-459 |
| CC-D10 | PRD-FR-298 | §71.10 | BDD-SC-786, BDD-SC-787, BDD-SC-788 | TDD-TC-460 |
| CC-D11 | PRD-FR-299 | §71.11 | BDD-SC-789, BDD-SC-790 | TDD-TC-461, TDD-TC-464 |
| CC-D12 | PRD-FR-300 | §71.12 | BDD-SC-791, BDD-SC-792 | TDD-TC-462 |

BDD-SC-793/794 y TDD-TC-463 cubren concurrencia/atomicidad transversal;
TDD-TC-465 define el recorrido crítico. La [matriz canónica](../05-matriz-trazabilidad.md)
conserva relaciones completas. Definiciones nuevas en [BDD](../03-BDD-corte-ciego.md)
y [TDD](../04-TDD-corte-ciego.md), con estrategia de evidencia y gates futuros.

## 4. Matriz de permisos formalizada por función

**Matriz funcional alineada con CC-D01..12 y SDD §71; asignaciones individuales y
códigos concretos pendientes. No describe grants vigentes.**
`P`: permitir bajo alcance. `N`: no conceder mediante ese perfil.
`C`: condicionado a la decisión y restricciones indicadas; no es permiso concedido.
Todo acceso requiere identidad activa y reautorización. Alcances:

- **Cajero**: turno propio y sucursal autorizada.
- **Encargado**: turnos de su sucursal asignada; sustitución de captura identificada.
- **Dueño**: organización y sucursales autorizadas según autoridad persistida.
- **Delegado financiero**: delegación opcional admitida por CC-D01; lectura financiera
  explícita, limitada y revocable, sin heredar autoridad de Dueño ni autorizar
  compensaciones por defecto. Las asignaciones concretas no están aprobadas.
- **Dispositivo**: capacidades técnicas específicas; nunca credenciales humanas.

| ID / acción o dato | Cajero | Encargado | Dueño | Delegado financiero | Dispositivo | Condición |
|---|---|---|---|---|---|---|
| CC-P01 Crear/cobrar pedido y consultar importe de la operación | P | P | P | N | N | CC-D12: Cajero en pedidos que atiende; encargado en su sucursal para seguimiento/autorización. Mantener guardas POS; sin historial monetario masivo ni exportación para sumar ventas. |
| CC-P02 Editar borrador propio no confirmado | P | P | P | N | N | CC-D08; sin saltar estados ni pago. |
| CC-P03 Autorizar modificación/cancelación de pedido aceptado | N | P | P | N | N | CC-D08 aprobada: toda acción posterior a aceptar, incluso sin pago; autorización concreta sin evadir estados, pagos ni consumo histórico. |
| CC-P04 Autorizar descuento/cortesía | N | P | P | N | N | CC-D08 aprobada: incluso en borrador; identidad del autorizador, motivo y alcance; quien captura no suplanta. |
| CC-P05 Consultar turno/estado operativo sin resumen monetario | P | P | P | C | C | Gateway sólo datos necesarios; KDS no lee caja. |
| CC-P06 Abrir/cerrar operativamente turno | P | P | P | N | C | Turno propio para Cajero; D10 aprueba cierre local con autorización offline válida. Apertura conserva contrato vigente, sin ampliación inferida. |
| CC-P07 Capturar y confirmar conteo único | P | P | C | N | C | D03/04/10 aprobadas: Cajero en su turno; encargado por sustitución identificada y motivada; borrador editable, confirmación única. Gateway persiste bajo autoridad humana válida con acuse provisional. Captura inicial por Dueño no concedida por estas decisiones; requiere resolución expresa si se incluye. |
| CC-P08 Finalizar corte y recibir acuse restringido | N | P | P | N | N | CC-D03/05/10 aprobadas: encargado o Dueño centralmente, con autoridad vigente y sincronización completa; si no, pendiente. Conciliaciones externas explícitas pueden seguir pendientes. Dispositivo no finaliza autónomamente ni offline. |
| CC-P09 Consultar acuse y declaración propia, sin esperado/diferencia | P | P | P | C | N | Sin editar captura confirmada; sustitución conforme a CC-D03 aprobada. |
| CC-P10 Consultar esperado, componentes agregados, diferencias y ventas monetarias | N | N | P | C | C | CC-D01 aprobada: delegado sólo bajo concesión vigente y alcance explícito; gateway sólo procesamiento interno necesario, sin exposición a operador. |
| CC-P11 Reporte de cantidad de tickets y top 10 | N | P | P | C | N | CC-D12 aprobada: encargado por sucursal, día/semana/mes; ranking sólo nombres/posiciones, sin cantidades, precios, costos ni venta. Delegado bajo alcance explícito; información financiera conforme a CC-D01. |
| CC-P12 Exportar/consultar historial financiero de cortes | N | N | P | C | N | Reautorizar cada lectura, descarga y exportación. |
| CC-P13 Solicitar, aprobar/rechazar y aplicar compensación del corte | N | N | P | N | N | CC-D07 aprobada: autoridad exclusiva de Dueño, sin segundo aprobador. Reportar error no es solicitar formalmente compensación. |
| CC-P14 Recibir cantidades contra compra | N | P | P | N | N | CC-D09 aprobada: encargado contra compra autorizada, parciales y diferencias justificadas; sin costos por defecto ni edición de catálogo. |
| CC-P15 Capturar conteo físico de inventario | P | P | P | N | N | Conservar captura ciega y alcance existentes. |
| CC-P16 Autorizar ajustes de inventario | N | N | P | N | N | CC-D09 aprobada: responsable administrativo con concesión explícita también puede revisar/aprobar; el perfil encargado por sí solo no concede esa autoridad. |
| CC-P17 Catálogos, recetas, precios, costos y márgenes | N | N | P | N | N | Especialidades administrativas por decisión separada, sin ampliar esta matriz. |
| CC-P18 Operar KDS/impresión | N | C | C | N | C | Capacidades existentes por estación/sucursal; no autoridad de caja. |

CC-D04 reserva al Dueño la configuración del catálogo de denominaciones; no se
deriva de lectura financiera ni se extiende al catálogo de productos/recetas.
Las denominaciones de cada conteo se conservan históricamente.
CC-D07 permite a Cajero y encargado reportar errores dentro de su alcance, sin
ampliar CC-P13 ni revelar esperado/diferencia. La delegación financiera sigue siendo
de consulta; no autoriza solicitar, aprobar ni aplicar compensaciones.
CC-D08 permite al Cajero solicitar las acciones de CC-P03/04, pero no autorizarlas.
Los retiros conservan sus guardas vigentes: esta decisión no aprueba ni amplía
su autoridad y se separan de CC-P04 para no confundirlos con descuentos/cortesías.
CC-D09 admite consulta de precios de compra mediante concesión explícita y
limitada; no convierte CC-P17 en un permiso general. El responsable administrativo
no es una columna adicional ni un rol concedido: sus facultades de revisión y
aprobación requieren asignación expresa conforme a CC-D02/09. Se separan funciones
y permisos sin exigir dos aprobadores. Capturar/enviar conteo no mueve inventario.

`N` no introduce por sí solo un motor de denegaciones que prevalezca sobre grants
organizacionales. Conforme a CC-D02 aprobada, la composición efectiva debe revisarse
individualmente antes de aplicar cambios.
Para cada usuario, el ensayo debe mostrar permisos efectivos antes/después y su
origen, incluyendo compatibilidades legacy. Administrador, Supervisor y Cajero
Jefe requieren mapeo explícito; no renombrarlos, eliminarlos ni degradarlos en lote.

Separar conceptualmente estas capacidades: leer estado operativo, capturar,
finalizar, leer resultado financiero, consultar acuse y decidir compensación.
El [SDD F1-02](../02-SDD-corte-ciego-fase-1.md) fija códigos y contratos técnicos,
conservando CC-P01..18. No son permisos instalados ni concesiones aprobadas a usuarios
reales: asignación y transición conservan revisión individual y autorización separada.

Fronteras obligatorias del inventario de accesos: endpoints canónicos y aliases de
caja; listado/detalle de turnos y cortes; respuestas de mutaciones y replay;
movimientos/pagos; dashboards/reportes/exportaciones; agentes/asistentes; eventos,
impresión y descargas; logs/errores; almacenamiento y caché del navegador; sesiones
antiguas; gateway, outbox/inbox y datos de diagnóstico. Revisar origen -> destino
sensible y guardas hermanas, no sólo visibilidad de componentes React.

## 5. Fase 2: criterios de aceptación formalizados

Se incorporan a BDD-SC-767..794 y TDD-TC-450..465. La tabla conserva IDs locales
para seguimiento; ningún criterio representa una prueba runtime ejecutada.

| ID / dependencias | Dado / cuando | Resultado comprobable |
|---|---|---|
| CC-AC01 / D01,D02,D12 | Cajero o encargado restringido consulta antes y después del conteo, incluso por API, alias, reporte, asistente o exportación | No recibe esperado, diferencias, componentes agregados ni venta/ticket promedio prohibidos. La respuesta tampoco incluye esos campos en JSON oculto, errores, descarga o replay. |
| CC-AC02 / D01,D02,D11 | Un usuario cambia IDs de sucursal/caja/corte, combina roles, usa una sesión anterior o pierde autoridad | La autorización efectiva y alcance se revalidan; no hay lectura/escritura ajena ni recuperación de respuesta financiera guardada con autorización antigua. Se cubren grants organizacionales según la decisión. |
| CC-AC03 / D03,D11 | Se abre un corte sobre un turno cerrado | Cajero, sucursal, caja y periodo derivan de fuentes persistidas; un turno legacy ambiguo falla cerrado. No se permite elegir otro cajero o periodo para evitar unicidad. |
| CC-AC04 / D03,D10 | Pago, retiro o recepción de efectivo de repartidor compite con el cierre operativo | Una serialización determina inclusión anterior al cierre o rechazo posterior; no hay operación perdida ni corte definitivo con efectos locales pendientes desconocidos. |
| CC-AC05 / D04 | Se guarda, revisa y confirma efectivo por denominaciones | Sólo MXN; Python suma denominación × número entero no negativo de piezas, incluido fondo presente, valida denominaciones/límites y rechaza total calculado por cliente como autoridad. Sólo Dueño configura denominaciones; el snapshot no cambia después. Captura propia y su total visibles, esperado oculto; vacío y cero explícito son distintos. |
| CC-AC06 / D04,D05 | Se declaran débito, crédito, transferencia o plataforma, con o sin evidencia suficiente | Comparación separada contra pagos confirmados y referencias; banco/plataforma no aumentan cajón. Comprobante sin verificar no confirma cobro. Fuente insuficiente conserva declaración y pendiente con motivo, nunca esperado cero supuesto. Liquidaciones posteriores se vinculan sin sobrescribir el corte; detalle financiero sólo bajo CC-D01. |
| CC-AC07 / D03,D04 | Se edita un borrador, se confirma tras revisar el desglose o compiten dos confirmaciones/replays | Borrador editable con trazabilidad; una sola captura confirmada e ineditable. Mismo comando devuelve acuse autorizado equivalente, otro contenido o versión obsoleta falla sin reemplazo. Fallo antes del commit no deja detalles parciales. Actor de conteo registrado; entrega posterior conserva receptor y fecha/hora, sin inferir custodia por confirmar. |
| CC-AC08 / D01,D03,D05,D06 | Se intenta finalizar un corte contado, existen conciliaciones pendientes explícitas o no hay encargado/Dueño disponible | Cajero y delegado sólo financiero reciben denegación sin mutación. Encargado o Dueño puede finalizar la declaración con pendientes documentados, sin declarar conciliación completa ni ignorar sincronización desconocida (D10). Sin disponibilidad queda pendiente e ineditable. Acuse del encargado sin esperado/diferencia ni «cuadró/no cuadró». No exige otra persona si capturó por sustitución; finalizar no aprueba un faltante. |
| CC-AC09 / D05,D06 | Fondo 10,000, pagos cash 50,000, depósitos 2,000 y retiros 7,000 centavos; contado 54,000; además se prueban pagos mixtos, entregas tardías y devoluciones | Esperado 55,000 y diferencia -1,000; contado 56,000 produce +1,000. Tarjeta de 20,000 no cambia efectivo. Caso separado de pago mixto 50,000: cash 20,000, tarjeta 30,000, sin duplicación. Repartidor pendiente no suma al cajón; entrega se vincula una vez al turno receptor sin reabrir el anterior. Cancelación sola no devuelve dinero; devolución confirmada afecta su medio una vez. Propinas sin flujo trazable no se habilitan como manejo integrado. |
| CC-AC10 / D03,D06 | Dos finalizaciones o cortes con periodos/operaciones solapados compiten | Una sola asociación por operación; replay no duplica. Rechazo, versión obsoleta o fallo inyectado dejan corte, asociaciones, comandos y auditoría coherentes. Probar en PostgreSQL real aislado. |
| CC-AC11 / D03,D07 | Operador reporta un error y Dueño solicita/decide/aplica corrección; también se prueba conteo confirmado aún no finalizado | Reporte acotado sin edición ni revelación financiera. Sólo Dueño solicita formalmente, aprueba/rechaza y aplica, pudiendo ser el mismo actor. Se finaliza primero la declaración original con las guardas vigentes; no se compensa antes ni se reabre su captura. Original y asociaciones permanecen; ajuste enlazado conserva autor, motivo protegido, evidencia y delta. No corrige ledger ni libera operaciones; replay no duplica. Cajero, encargado y delegado no adquieren autoridad por IDs o códigos de permiso. |
| CC-AC12 / D01,D11,D12 | Cambian catálogo, nombre, zona o permisos y se consulta un corte histórico | El snapshot original permanece. Lecturas obedecen autoridad actual. Cortes antiguos sin desglose se identifican como legacy; no se fabrican denominaciones ni comprobantes. |
| CC-AC13 / D10,D11 | Gateway pierde conectividad, reenvía o tiene grant revocado/vencido y luego sincroniza | Cierre/conteo local con identidad y autorización válidas, SQLite durable y confirmación única; acuse provisional sin esperado/diferencias. Central verifica cierre y todas las fuentes operativas, no sólo cola vacía, antes de finalizar por encargado/Dueño con autoridad vigente. Vencimiento bloquea nuevos comandos sensibles; conflicto conserva evidencia pendiente sin compensación automática. Sin soporte comprobado, recorrido fuera del piloto. |
| CC-AC14 / D11 | Turno cruza medianoche local o cambio horario; se activa una versión nueva | UTC semiabierto y zona snapshot conservados. Activación por sucursal entre turnos, tras concluir/sincronizar turnos anteriores y finalizar conteos confirmados por flujo compatible. Pendientes incompatibles bloquean transición; sin recortar historia, repetir captura ni inventar desglose. Usuarios revisados y clientes incompatibles bloqueados. |
| CC-AC15 / D01,D11 | Se pierde el acuse o se intenta revertir la aplicación/migración | Se recupera el resultado con reautorización. No se presenta éxito local como definitivo. Reversión no borra conteos, no reactiva una API que filtre importes y no hace downgrade destructivo con historia. |
| CC-AC16 / D02,D08,D09 | Se restringen permisos de caja y se recorren venta, descuento, recepción, inventario y KDS | Cajero edita borrador; cambios/cancelaciones tras aceptar y descuentos/cortesías incluso en borrador exigen encargado o Dueño con autorización concreta y motivo. Se conservan guardas de estado/pago/producción. Encargado recibe sin costos por defecto; acceso a precios explícito, conteo ciego y ajustes con revisión/aprobación administrativa separadas. No se otorga autoridad financiera para arreglar una dependencia de UI. |

Casos de frontera de CC-AC01/02/12 derivados de CC-D12: encargado consulta número
de tickets y ranking de su sucursal por día/semana/mes; Cajero no recibe ese reporte.
El ranking restringido sólo incluye nombres y posiciones, sin cantidades, precios,
ingresos, costos ni márgenes en pantalla o payload. Reimpresión no suma venta nueva.
Consulta individual de Cajero limitada a pedidos que atiende y de encargado a
seguimiento/autorización en su sucursal; no habilitar listado/exportación monetaria
masiva para reconstruir venta. Comprobar API, asistentes, descargas e historia,
no sólo UI. Dueño/delegado acceden a agregados únicamente bajo autoridad vigente
y alcance; no dar por cubierta toda estimación basada en memoria del operador.

Casos de frontera de CC-AC02/12/14/15 derivados de CC-D11: un turno abierto o
conteo confirmado pendiente impide activar la sucursal; no se transforma su
declaración al nuevo formato. Una concesión offline anterior aún vigente o datos
pendientes incompatibles impiden dar por completado el preflight. Tras activar,
sesión/cliente incompatible no recupera acceso a importes por API, replay o
exportación histórica. La revisión individual cubre acumulación de roles y grants.
Un corte antiguo sigue sin desglose cuando nunca lo tuvo. Reversión conserva
historia y restricciones; fallo del piloto detiene ampliación a otras sucursales.

Casos de frontera de CC-AC13 derivados de CC-D10: reinicio del gateway recupera
captura sin habilitar segunda confirmación; acuse perdido/reenvío no duplica efectos.
Cola vacía con una fuente operativa aún no conciliada no permite finalizar. Un
pendiente bancario conocido según CC-D05 no se confunde con operaciones locales
desconocidas. Grant vencido no se renueva localmente; al reconectar, autoridad
obsoleta o conflicto dejan evidencia pendiente, sin sobrescritura ni finalización
automática. Caída prolongada/fallo de gateway no convierten contingencia en corte
confirmado. Probar competencia local/central para impedir dos finalizaciones.

Casos de frontera de CC-AC16 derivados de CC-D09: recibir una compra parcial
registra cantidades/diferencias justificadas, sin exponer costos ni habilitar
edición de precios, conversiones o catálogo. Consulta de precios sólo con
concesión explícita y alcance vigente. Capturar/enviar conteo no revela teórico,
costos o diferencias al capturista ni mueve inventario. El perfil encargado o
delegado financiero por sí solo no aprueba ajustes; Dueño o responsable con
autoridad administrativa expresa revisa/aprueba sin exigir dos aprobadores.
El ajuste conserva movimientos concurrentes e historia; grants heredados no
deben eludir la revisión individual de CC-D02.

Casos de frontera de CC-AC16 derivados de CC-D08: pedido aceptado sin pago exige
autorización; descuento en borrador también. Sin autorizador la acción no se aplica.
Cambiar contenido o versión del pedido invalida la autorización anterior; replay
idéntico no duplica efectos. Registrar solicitante/autorizador y antes/después,
sin compartir credenciales ni transferir la sesión del autorizador al operador.
Verificar que la autorización no habilite una transición prohibida, edición de pago
ni reposición automática de producto ya elaborado; conservar merma/recuperación
y devolución/compensación según el flujo canónico aplicable.

Casos de frontera de CC-AC08/09 derivados de CC-D06: diferencias de -1 y +1 centavo
se conservan con tolerancia cero y no impiden finalizar por un actor autorizado;
cero no genera aviso de diferencia. Probar sobrante de 100 centavos en efectivo
y faltante de 100 en tarjeta: conservar ambos, sin resultado «cuadrado» por suma
neta. Fuente incompleta conserva pendiente y no dispara un faltante inventado.
El acuse del encargado no filtra resultados ni existencia de alerta.
Para fase 3: aviso al Dueño por resultado confirmado no cero; delegado necesita
alcance y designación; fallo de canal conserva pendiente/reintento sin bloquear
corte. Estos últimos criterios no acreditan entrega de alertas en fases 0..2.

La prueba de confidencialidad debe enumerar rutas y campos efectivamente revisados.
Ocultar textos con CSS no satisface CC-AC01. Tickets individuales y memoria del
operador pueden permitir estimaciones; el compromiso es evitar exposición y
reconstrucción directa por agregados prohibidos dentro de las superficies acordadas.

## 6. Secuencia de trabajo y activación documental

Plan detallado de CC-W03: [fase 1 — separación de permisos y lecturas financieras](CORTE-CIEGO-001-FASE-1.md).
Define F1-01..11, dependencias, pruebas y gates. F1-01/02 completan inventario y diseño
documental; F1-03 prepara fixtures y lote RED de pruebas; F1-04..11 pendientes,
sin implementar lógica funcional.

La implementación de lógica funcional está **NO INICIADA / NO AUTORIZADA**. La autorización
actual cubre preparación, registro/cierre de decisiones, formalización CC-W02 y
concreción documental F1-01/02 y fixtures/pruebas RED F1-03 de CC-W03.
No autoriza implementación ni activación productiva.

| Trabajo | Entrega y responsable funcional sugerido | Dependencia / salida |
|---|---|---|
| CC-W00 Preparar paquete | Este documento: decisiones, matriz y aceptación. Producto/arquitectura | Preparación documental completada; integridad verificada. |
| CC-W01 Resolver fase 0 | CC-D01..12 con aprobador/evidencia; roles reales mapeados sin cambios en cuentas. Dueño + operación + finanzas | Las 12 decisiones están aprobadas y su registro cerrado; mapeo individual de usuarios y concesiones aún pendiente. No equivale a fase 0 operativa completa. |
| CC-W02 Formalizar contratos | PRD-FR-289..300, SDD §71/ADR-048, BDD-SC-767..794, TDD-TS-157..160/TC-450..465 y matriz. Arquitectura/producto | Formalización documental completada; precisiones a baseline conservan evidencia histórica sin atribuir GREEN a contrato nuevo. Mapeo de usuarios no bloquea redactar, sí activar. |
| CC-W03 Implementar fase 1 | Permisos efectivos, proyecciones separadas, cierre de aliases y transición de sesiones/clientes. Backend/frontend | CC-W02 + autorización de código; RED focal CC-AC01/02/16, luego GREEN y revisión R3. |
| CC-W04 Diseñar persistencia de fase 2 | Contratos estrictos de denominaciones/medios, unicidad, estado, migración aditiva y adaptación de PCO-006. Arquitectura/backend | D03..07/10/11; distinguir cierre operativo, conteo y resultado sin reusar ledger como campo editable. |
| CC-W05 Implementar conteo y conciliación | Comandos atómicos, UX ciega, acuses, correcciones y frontera offline. Backend/frontend/gateway | CC-W03/04; RED/GREEN CC-AC03..15 según recorrido. No relajar tests históricos para dar verde. |
| CC-W06 Verificar y preparar piloto | Evidencia por commit, auditoría independiente Sol con contexto fresco, plan de reversión y preflight de respaldos/restauración. QA/operación | Gates del incremento verdes; operación sin soporte offline no se presenta como compatible. |
| CC-W07 Activar piloto | Una sucursal seleccionada, usuarios mapeados y turnos elegibles; observar cierre completo y corrección controlada | Autorización productiva separada; ampliar sólo con evidencia y sin bloqueos graves. |

Este paquete no crea una segunda máquina de corte ni reemplaza PCO-006. El detalle
de tablas, nuevos permisos, rutas, códigos de error y migración se define en SDD
después de las decisiones; no se publica aquí como contrato ya aprobado.

## 7. Verificación futura, evidencia y operación

Reutilizar y extender cobertura existente, sin dar por cubiertos los nuevos criterios:

| Cobertura | Punto de partida | Criterios |
|---|---|---|
| Dominio/API de corte y contratos | [user_cash_cuts](../../apps/api/tests/test_user_cash_cuts.py), [contratos](../../apps/api/tests/test_user_cash_cut_contracts.py) | AC01..03, AC05..12, AC15 |
| Cierre operativo y ledger | [cierre](../../apps/api/tests/test_cash_shift_operational_close.py), [ledger](../../apps/api/tests/test_cash_ledger.py) | AC04, AC09..11 |
| Concurrencia y migración | [PostgreSQL](../../apps/api/tests/test_user_cash_cuts_postgres.py), [migración](../../apps/api/tests/test_user_cash_cuts_migration.py) | AC07, AC10..12, AC14/15 |
| Offline y sincronización | [cierre offline](../../apps/api/tests/test_offline_order_cash_close.py), [sincronización](../../apps/api/tests/test_pco008_cash_sync.py), [outbox](../../tests/edge_gateway/test_pco008_cash_outbox.py) | AC02, AC04, AC13..15 |
| Frontend y recorrido | [semántica de corte](../../tests/frontend/test_pos_user_cash_cuts.mjs), nuevos E2E de roles y conteo | AC01, AC05..08, AC12..16 |

Por incremento: pruebas focales; lint/typecheck backend afectado; typecheck y prueba
semántica frontend; contratos/E2E de recorridos críticos; PostgreSQL aislado para
locks y carreras; SQLite/gateway para lo afectado; QA visual de estados y breakpoints
impactados; `git diff --check`. Build antes de release o al afectar empaquetado.
Suite completa aplicable una vez en CI según GOV-TEST-001. Evidencia local, CI,
Git, migración y piloto se reportan por separado; un gate omitido no está verde.
Cambiar IDs/relaciones canónicas activa `tests/architecture/test_traceability.py`.

La revisión R3 futura integrará afirmación, evidencia, intento de refutación,
resultado y riesgo residual. Refutaciones mínimas: lectura de esperado por alias,
grant acumulado, replay tras revocación, dos conteos simultáneos, pago contra cierre,
fallo entre escrituras, sincronización tardía y downgrade con historia.

Preguntas operativas para esa implementación:

1. ¿Quién accedió o intentó acceder al resultado financiero? Auditoría de acción,
   actor, alcance, resultado y versión de política, sin importes en logs generales.
2. ¿El conteo fue confirmado una sola vez? Correlación técnica entre comando,
   conteo y acuse; señal de replay/conflicto/rollback sin payload sensible.
3. ¿Por qué un turno no puede conciliarse definitivamente? Motivo estable,
   estado de sincronización y autoridad pendiente; nunca éxito aparente.
4. ¿Una corrección conserva el original? Referencias del corte y compensación
   consultables sólo por autoridad financiera; sin duplicar movimientos de dinero.

## 8. Cierre de la entrega documental

- Preparación del paquete y registro de decisiones: completados; CC-D01..12
  aprobadas el 2026-10-21, con aprobador y evidencia. No quedan decisiones de la
  lista de 12 pendientes.
- Matriz y aceptación: formalizadas en la cadena canónica como contrato objetivo,
  sin nuevos grants ni activación runtime. El cierre no amplía facultades fuera del alcance
  aprobado, incluida captura inicial de corte por Dueño.
- Pendientes de ejecución: mapeo individual de usuarios/permisos; detalle técnico
  del incremento (rutas/permisos/esquema, protocolo de completitud y límites) y verificación futura;
  selección/fecha/autorización productiva del piloto. No se declaran completados
  por cerrar las decisiones ni se inicia su ejecución en esta entrega.
- Implementación, auditoría R3 de implementación y piloto: no iniciados. La revisión
  documental independiente de esta formalización se registra debajo.
- Evidencia de preparación inicial del paquete (2026-10-21): 19 enlaces relativos válidos;
  unicidad de 12 decisiones, 18 filas de permisos, 16 criterios y 8 trabajos;
  referencias a decisiones y columnas de tablas consistentes. Comando
  `.venv/Scripts/python.exe -B -m pytest tests/architecture/test_traceability.py -q -p no:cacheprovider`:
  **9 passed**. `git diff --check` y revisión de whitespace del documento nuevo:
  sin errores. No se ejecutaron pruebas runtime ni gates de implementación R3.
- No se reutiliza el resultado de 71 pruebas de la auditoría anterior como GREEN
  del corte ciego. Nuevos criterios requieren su propia evidencia tras aprobación.

### Evidencia de formalización canónica

- PRD-FR-289..300, SDD §71/ADR-048, 28 escenarios BDD-SC-767..794 y 16 casos
  TDD-TC-450..465 en cuatro suites TDD-TS-157..160; estado `Disenado` en matriz.
- Ajustes explícitos a PCO-006 distinguen autoridad y proyecciones del contrato nuevo
  de la evidencia baseline. Nuevos permisos/capacidades no están aplicados.
- Verificación documental dirigida: `tests/architecture/test_traceability.py`:
  **9 passed**; enlaces locales, unicidad de IDs, correspondencia de las 12 decisiones
  y `git diff --check` sin errores. Ninguna ejecución documental sustituye pruebas
  de comportamiento, migración, CI del runtime o autorización productiva.
- Revisión independiente con contexto fresco de la formalización: sin hallazgos
  bloqueantes ni ampliaciones no aprobadas. Se precisó la evidencia histórica y
  la distinción entre revisión documental y auditoría futura de implementación.

| Afirmación contractual | Evidencia documental | Intento de refutación | Resultado y límite |
|---|---|---|---|
| Las doce decisiones conservan alcance y aceptación | Resoluciones anteriores, §3.1, PRD-FR-289..300 y matriz | Comparar cada resolución con requisitos/escenarios/casos, buscando facultades no aprobadas | Correspondencia completa; asignaciones reales y detalles técnicos no se declaran resueltos. |
| Finalizar/operar no concede lectura financiera ni corrección | SDD §71.1..3/7/12 y BDD-SC-767..772/780..781/791..792 | Rol superior, grant acumulado, delegado, sustitución y replay tras revocación | Restricciones expresas; requiere futuras pruebas API/runtime de todas las superficies. |
| Declaración e historia no se sobrescriben ni duplican | SDD §71.3..7/10..11 y BDD-SC-774..781/786..790/793..794 | Corrección de COUNTED, pago contra cierre, reenvío y downgrade | Contrato mantiene atomicidad, compensación y finalización central; protocolo físico y concurrencia aún no ejecutados. |
| Evidencia baseline no prueba el nuevo contrato | Notas de precedencia en PCO-006/BDD/TDD y estado Disenado de matriz | Buscar herencia de GREEN o atribución de pruebas documentales a comportamiento | Nuevos casos definidos sin ejecución; CI, migración, despliegue y piloto no certificados. |
