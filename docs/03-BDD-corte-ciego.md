# BDD — CORTE-CIEGO-001

Contrato objetivo aprobado. **Autoridad F1-04 implementada parcialmente; escenarios
integrales pendientes de integración y activación.** Evidencia en el plan de fase 1 §10.
Fuente: PRD-FR-289..300, SDD §71/ADR-048 y decisiones del
[paquete](implementation-plans/CORTE-CIEGO-001.md). Cada escenario se ejecutará con la
política nueva; los escenarios PCO-006 conservan su evidencia baseline, que no prueba
estos cambios. Los avisos externos se verifican en fase 3, no en fases 0..2.

## BDD-FEAT-155 Autoridad y declaración del corte ciego

```gherkin
@PRD-FR-289 @cash @critical @authorization
Feature: Separar lectura financiera y operación

  @BDD-SC-767
  Scenario: Cajero y encargado no reciben resultados financieros
    Given un cajero o encargado sin delegación financiera consulta dentro de su alcance
    When consulta antes o después de confirmar o finalizar un corte
    Then sólo recibe estado operativo y declaración propia autorizada
    And no recibe esperado, componentes agregados, diferencias, venta ni ticket promedio
    And tampoco indicador de cuadratura ni existencia de alerta financiera
    And la restricción cubre API, aliases, respuestas de comandos, reportes, asistentes y exportaciones

  @BDD-SC-768
  Scenario: Delegación revocable no concede facultades operativas
    Given un delegado financiero con concesión limitada a una sucursal
    When consulta resultados de esa sucursal con autoridad vigente
    Then obtiene sólo la información concedida
    But no puede finalizar, corregir cortes ni modificar pagos por esa delegación
    When se revoca la concesión y recupera un resultado anterior
    Then no obtiene la respuesta financiera guardada ni acceso a otra sucursal
```

```gherkin
@PRD-FR-290 @cash @critical @authorization
Feature: Revisar permisos efectivos sin renombrar roles

  @BDD-SC-769
  Scenario: Encargado corresponde a Líder sin elevación por nombre
    Given perfiles Cajero jefe, Líder, Supervisor y Administrador existentes
    When se evalúan las capacidades de la política nueva
    Then Líder corresponde a encargado dentro de su alcance
    And los otros perfiles no heredan autoridad de encargado ni financiera por su nombre
    And no se renombran roles ni se alteran asignaciones automáticamente

  @BDD-SC-770
  Scenario: Grant acumulado impide aprobar una transición insegura
    Given una cuenta operativa restringida conserva un grant general que revela importes
    When se revisan permisos efectivos antes de activar su sucursal
    Then la contradicción debe resolverse explícitamente antes de activar
    And la revisión muestra origen, alcance y permisos antes y después
    And no se retiran indiscriminadamente funciones ajenas al alcance
```

```gherkin
@PRD-FR-291 @cash @critical @acceptance
Feature: Capturar y finalizar con responsables distintos por función

  @BDD-SC-771
  Scenario: Conteo confirmado espera a un finalizador autorizado
    Given un cajero cerró operativamente su turno y confirmó el conteo
    When no hay encargado ni Dueño disponible
    Then el conteo queda pendiente de finalización e ineditable
    And el cajero y el delegado sólo financiero no pueden finalizarlo
    When un encargado autorizado finaliza con las demás condiciones satisfechas
    Then recibe acuse sin resultado financiero y finalizar no aprueba un faltante

  @BDD-SC-772
  Scenario: Encargado sustituye al cajero ausente y puede finalizar
    Given un turno cerrado cuyo cajero está ausente
    When el encargado captura por sustitución con identidad y motivo
    Then el responsable original del turno permanece
    And ese encargado puede finalizar sin exigir otra persona si cumple las demás condiciones
    And la sustitución no concede captura inicial a Dueño ni a otros perfiles por inferencia
```

```gherkin
@PRD-FR-292 @cash @critical @acceptance
Feature: Declaración verificable y confirmación única

  @BDD-SC-773
  Scenario: Denominaciones y medios distinguen vacío de cero
    Given un catálogo de denominaciones MXN configurado por Dueño
    When el operador declara piezas e importes por los medios habilitados
    Then ve el total de su captura calculado por servidor incluido el fondo presente
    And vacío sigue sin contar y cero requiere declaración explícita
    And no se acepta total del navegador como autoridad ni piezas fraccionarias
    And modificar después el catálogo no altera las denominaciones del conteo

  @BDD-SC-774
  Scenario: Borrador editable y confirmación inmutable no acreditan custodia
    Given un borrador de conteo con desglose
    When el operador lo corrige, revisa y confirma
    Then las ediciones quedan trazadas y una sola declaración queda ineditable
    And un reintento idéntico no duplica y otro contenido no reemplaza lo confirmado
    And una entrega posterior registra receptor y fecha sin inferirla por confirmar
```

## BDD-FEAT-156 Conciliación y corrección conservando historia

```gherkin
@PRD-FR-293 @cash @critical @acceptance
Feature: Conciliar cada medio sin inventar dinero

  @BDD-SC-775
  Scenario: Efectivo y pagos mixtos se contabilizan una vez
    Given fondo de 10000, pagos cash de 50000, depósitos de 2000 y retiros de 7000 centavos
    When el conteo declarado es de 54000 centavos y las fuentes están completas
    Then esperado es 55000 y diferencia es menos 1000 centavos
    And una tarjeta de 20000 centavos no cambia el cajón
    And en un caso separado un pago mixto de 50000 aporta sólo su parte cash de 20000 al efectivo

  @BDD-SC-776
  Scenario: Pendientes externos no se convierten en faltantes ficticios
    Given una declaración con operaciones locales completas y liquidación externa pendiente
    When encargado o Dueño finaliza con pendiente motivado por medio
    Then la declaración queda finalizada sin afirmar conciliación completa
    And no se inventa esperado cero ni diferencia por fuente insuficiente
    And un comprobante de transferencia no verificado no confirma un cobro
    And banco, plataforma, cobrador real y canal conservan su distinción
    When llega la liquidación posterior
    Then se vincula sin sobrescribir el corte ni revelar su resultado al operador

  @BDD-SC-777
  Scenario: Repartidor devolución y propina no duplican efectivo
    Given dinero pendiente de entrega por un repartidor
    When se recibe en otro turno
    Then se enlaza una vez al turno receptor sin duplicar venta ni reabrir el turno anterior
    And cancelar un pedido no registra por sí solo una devolución
    And sólo devolución confirmada afecta su medio
    And propinas no se integran en caja sin entradas y entregas trazables separadas de venta
```

```gherkin
@PRD-FR-294 @cash @critical @acceptance
Feature: Diferencias exactas y avisos de fase tres

  @BDD-SC-778
  Scenario: Tolerancia cero no bloquea ni compensa diferencias
    Given diferencias confirmadas de más un centavo en efectivo y menos un centavo en tarjeta
    When encargado o Dueño finaliza con las demás guardas satisfechas
    Then ambas diferencias se conservan sin netear y la finalización no las aprueba
    And queda evidencia para avisar al Dueño por cada resultado confirmado no cero
    And cero no origina aviso de diferencia
    And el operador no conoce la existencia de alerta financiera

  @BDD-SC-779
  Scenario: Entrega futura de aviso falla sin bloquear el corte
    Given la fase tres habilita un canal y un aviso por diferencia confirmada
    When falla el envío
    Then el aviso conserva pendiente y reintento sin bloquear el corte
    And sólo Dueño o delegado autorizado y designado puede recibirlo
    And un resultado desconocido no origina un faltante inventado
```

```gherkin
@PRD-FR-295 @cash @critical @authorization
Feature: Corregir declaración sin reescribir operaciones

  @BDD-SC-780
  Scenario: Operador reporta y Dueño corrige sin segundo aprobador
    Given un operador reporta un error con motivo y evidencia dentro de su alcance
    When el Dueño solicita formalmente, aprueba y aplica la corrección
    Then puede ser la misma persona en esas tres acciones y quedan auditadas
    And original, corrección y delta permanecen vinculados bajo lectura financiera autorizada
    And no se editan ledger ni pagos ni se liberan asociaciones históricas
    And delegado financiero y operador no pueden ejecutar esas acciones

  @BDD-SC-781
  Scenario: Error en conteo confirmado aún no finalizado
    Given un conteo confirmado con error reportado
    When se intenta corregir antes de finalizar
    Then no se reabre la captura ni se aplica compensación
    When encargado o Dueño finaliza original con todas las guardas satisfechas
    Then sólo Dueño puede aplicar después la corrección autorizada enlazada
    And reintentar no crea dinero ni una segunda compensación del mismo comando
```

## BDD-FEAT-157 Permisos colaterales sin ampliar autoridad

```gherkin
@PRD-FR-296 @orders @critical @authorization
Feature: Autorizar acciones concretas de pedidos

  @BDD-SC-782
  Scenario: Borrador editable y acciones sensibles autorizadas
    Given un cajero atiende su borrador con precios y reglas del servidor
    When modifica productos o cantidades antes de aceptar
    Then puede editar o descartar el borrador
    But descuento o cortesía requiere encargado o Dueño incluso en borrador
    And cualquier modificación o cancelación tras aceptar requiere esa autorización incluso sin pago
    And sin autorizador disponible la acción queda pendiente sin aplicarse

  @BDD-SC-783
  Scenario: Autorización exacta no evade producción ni pagos
    Given encargado o Dueño autoriza una acción con sus credenciales y motivo
    When cambia el pedido o contenido antes de aplicar
    Then se requiere nueva autorización y no se transfiere la sesión del autorizador al cajero
    And un replay idéntico no duplica efectos
    And estado incompatible sigue bloqueado y producto elaborado no vuelve automáticamente al inventario
    And se exige merma o recuperación para cancelación productiva permitida
    And pagos y sus correcciones conservan guardas canónicas e historia inmutable
```

```gherkin
@PRD-FR-297 @inventory @critical @authorization
Feature: Recibir y contar sin autoridad administrativa implícita

  @BDD-SC-784
  Scenario: Recepción sin costos por defecto
    Given encargado recibe contra una compra autorizada
    When registra recepción parcial y diferencias justificadas
    Then no ve costos ni precios sin concesión expresa y limitada
    And recibir no permite modificar precios, conversiones, presentaciones ni catálogo
    And consulta de precios no concede agregados financieros de caja

  @BDD-SC-785
  Scenario: Conteo ciego y revisión administrativa separada
    Given Cajero o encargado autorizado captura inventario físico
    When envía el conteo
    Then no ve teórico, costos ni diferencias y no mueve existencias
    When Dueño o responsable administrativo expresamente autorizado revisa y aprueba
    Then se generan ajustes trazables conservando movimientos concurrentes e historia
    And no se exigen dos aprobadores ni personas distintas
    And ser encargado o delegado financiero por sí solo no permite aprobar
```

## BDD-FEAT-158 Offline transición y reportes restringidos

```gherkin
@PRD-FR-298 @cash @critical @offline
Feature: Guardar localmente y finalizar sólo centralmente

  @BDD-SC-786
  Scenario: Captura durable se recupera con acuse provisional
    Given gateway de sucursal sin internet con identidad y autorización offline válidas
    When se cierra el turno, confirma conteo y reinicia el gateway
    Then se recupera la declaración única con acuse provisional sin esperado ni diferencia
    And reenviar o perder el acuse no duplica ni permite recapturar
    And no existe finalización definitiva local

  @BDD-SC-787
  Scenario: Cola vacía no acredita operaciones completas
    Given una fuente autorizada del turno conserva operaciones no recibidas centralmente
    When la cola consultada está vacía y encargado intenta finalizar
    Then no se finaliza hasta acreditar cierre y recepción completa de todas las fuentes
    When se acredita completitud y autoridad vigente de encargado o Dueño
    Then puede finalizar centralmente aunque exista un pendiente bancario explícito

  @BDD-SC-788
  Scenario: Vencimiento conflicto o caída prolongada conservan pendientes
    Given una autorización offline vencida o un conflicto al reconectar
    When se intenta emitir un comando sensible o sincronizar la declaración conflictiva
    Then no se renueva autoridad local ni se aplica el conflicto automáticamente
    And la evidencia se conserva pendiente sin sobrescritura ni compensación automática
    And no se promete revocación instantánea durante desconexión
    And caída prolongada o gateway caído no amplían permisos ni convierten contingencia en corte confirmado
```

```gherkin
@PRD-FR-299 @cash @critical @migration
Feature: Activar entre turnos sin modificar historia

  @BDD-SC-789
  Scenario: Pendientes anteriores posponen la activación
    Given una sucursal piloto con turno abierto, conteo confirmado pendiente o concesión offline anterior vigente
    When se intenta activar la nueva política
    Then se pospone hasta concluir y sincronizar turnos, finalizar conteos y resolver o agotar concesiones
    And no se fuerza cierre, segunda captura ni desglose inventado
    And activación requiere fecha, versión y revisión individual de permisos

  @BDD-SC-790
  Scenario: Historia y reversión conservan confidencialidad
    Given una sucursal activada y cortes legacy sin denominaciones
    When se consulta historia o se intenta usar una sesión o cliente incompatible
    Then historia conserva originales sin inventar detalle y aplica autoridad vigente
    And clientes incompatibles quedan bloqueados incluso en exportaciones y replay
    When falla el piloto
    Then se detiene ampliación y la recuperación preserva datos y restricciones
    And no se ejecuta downgrade destructivo ni se reactiva API que exponga importes
```

```gherkin
@PRD-FR-300 @reports @critical @authorization
Feature: Supervisar operación sin reportes monetarios indirectos

  @BDD-SC-791
  Scenario: Encargado recibe tickets y ranking acotados
    Given encargado autorizado para una sucursal
    When consulta día, semana o mes
    Then recibe número de tickets y top diez sólo con nombres y posiciones
    And no recibe cantidades, precios, ingresos, costos ni márgenes en ese ranking
    And reimprimir no cuenta como venta nueva y el Cajero no recibe ese reporte

  @BDD-SC-792
  Scenario: Consulta individual no concede historial financiero masivo
    Given un cajero consulta un pedido que atiende o encargado uno necesario en su sucursal
    When consulta su importe individual
    Then la operación se permite bajo alcance
    But no se habilita listado o exportación masiva para sumar ventas del periodo
    And API, asistentes y descargas aplican las mismas restricciones
    And agregados monetarios requieren Dueño o delegado con autoridad vigente
    And no se promete impedir estimaciones humanas a partir de importes individuales conocidos
```

## Casos transversales

```gherkin
@PRD-FR-291 @PRD-FR-292 @PRD-FR-298 @cash @critical @concurrency
Feature: Unicidad atomicidad y aislamiento del corte

  @BDD-SC-793
  Scenario: Confirmaciones y finalizaciones simultáneas no duplican efectos
    Given dos confirmaciones o finalizaciones concurrentes de la misma declaración
    When ambas intentan aplicar sus efectos
    Then sólo existe una declaración confirmada y una finalización con asociaciones exclusivas
    And periodo solapado o reenvío local y central no eluden la unicidad

  @BDD-SC-794
  Scenario: Fallo parcial o alcance adulterado no altera el corte
    Given una mutación del corte con IDs de otra sucursal o un fallo antes del commit
    When se procesa el comando
    Then se rechaza sin efecto parcial ni respuesta financiera ajena
    And auditoría, asociaciones, comando y corte mantienen consistencia
    And pago, retiro o entrega concurrente al cierre no desaparece ni entra dos veces
```

## Refinamiento de aceptación F1-01/02

El [SDD técnico](02-SDD-corte-ciego-fase-1.md) concreta escenarios existentes; no crea
nuevas decisiones de negocio ni evidencia de automatización:

- BDD-SC-767/768: las respuestas operativas v2 y acuses no contienen claves de resultado
  financiero; la API antigua responde upgrade bajo política nueva. Un replay concurrente,
  descarga, perfil CRM, logs de integración o consulta de asistente no eluden concesión
  vigente por dataset/sucursal. Revocar impide lecturas nuevas, sin prometer retirar bytes
  ya autorizados/enviados. Lectura financiera no concede acciones.
- BDD-SC-769/770: permiso financial.data.read aislado, grant general o nombre de rol no
  sustituyen Dueño gobernado/concesión explícita. Recibir compra no concede ver XML/precios;
  leer finanzas no aprueba ajustes. Preflight revisa cada combinación de autoridades.
- BDD-SC-787/790: versión antigua o contexto cambiado no muestra una respuesta tardía;
  el gateway mantiene acuses operativos y no emite delegación de lectura financiera.
- BDD-SC-791/792: día civil, semana ISO y mes civil en zona de sucursal; ticket canónico,
  top 10 sólo nombre/posición. Listado, filtros, cursor, perfil de cliente y detalle por
  ID sin contexto autorizado no ofrecen reconstrucción monetaria masiva. El importe de
  un pedido efectivamente atendido permanece visible para cobrarlo.
- BDD-SC-792: conocer un ID, introducir un motivo o crear una solicitud no acredita
  atención. Aceptación/modificación/entrega ejecutadas identifican al actor; reapertura
  requiere aprobación y versión vigente. Cerrar pedido/turno o retirar permiso invalida
  la atención ordinaria. Una lectura autorizada queda auditada sin copiar sus importes;
  fallo al persistir la auditoría no entrega el detalle. El historial fuera de contexto
  conserva su autoridad financiera independiente.

La prueba de ausencia de claves cubre payload completo, errores, headers y descargas;
no se satisface ocultando componentes. Los detalles técnicos de contexto, lock y
compatibilidad son los del SDD, no comportamientos ya acreditados en producción.


Refinamiento de BDD-SC-792 — impresión humana: dado un trabajo con ticket monetario
y error libre, cuando el operador lista trabajos, sólo recibe metadata y no se carga
el payload. Para reintentar, aun con la misma clave, debe conservar permiso de retry
y contexto autorizado del pedido. Cierre del pedido o pérdida de contexto deniega el
replay; una clave nueva sin contexto no encola nada. Un token técnico no suplanta al
humano. Si falla la auditoría, no se confirma el intento y no se expone SQL.


Refinamiento BDD-SC-792 — impresión técnica: un dispositivo vigente sólo ve metadata
al consultar la cola. Antes de claim, otro dispositivo, una credencial revocada o un
intento terminado no pueden descargar el contenido. Tras claim, el dispositivo asignado
puede leer el ticket de esa operación; cocina conserva instrucciones sin precios ni
importes anidados. La lectura deja auditoría; snapshot inválido, fallo de auditoría o
revocación confirmada antes de la revalidación de salida impiden entregar el payload.


Refinamiento BDD-SC-768/792 — solicitudes operativas: listar o resolver un intent propio
requiere lectura vigente de su sucursal/tipo bajo política activa. Retirar escritura
permite recuperar el acuse; retirar lectura deniega sin resolverlo. La prueba de efecto
no carga snapshots monetarios y conserva la integridad de compensaciones. Un token de
agente/dispositivo no puede usar estas rutas humanas. Cambiar autoridad tras confirmar
impide entregar el resultado; recuperar de nuevo no duplica el efecto ni su resolución.

Refinamiento BDD-SC-767/768 — movimientos: crear o compensar retorna acuse operativo
sin resúmenes ni importe bajo la política. Repetir una clave propia sólo permite leer
el acuse con lectura vigente; no exige reejecutar la acción ni reabre caja cerrada.
Cambiar actor/sucursal/cuerpo no recupera un resultado financiero. Una acción nueva
sin permiso o lectura no produce movimiento. Los snapshots y compensaciones siguen
inmutables; el gateway conserva su propia confirmación mínima y transacción atómica.

Refinamiento BDD-SC-768/792 — acuses propios de pedido/pago: un replay o recuperación
por clave entrega metadata sin dinero, aun si el pedido o turno terminaron. Perder
permiso de escritura impide una acción nueva, pero permite recuperar el acuse propio
si conserva lectura; perder también lectura lo deniega. El snapshot histórico conserva
sus importes internos y no se consulta para ese acuse. La vista previa puntual conserva
precio/cambio exactos únicamente con contexto vigente. Un error posterior al commit
no duplica el pago al reintentar la misma clave.

Refinamiento BDD-SC-767/768/792 — liquidaciones: el selector conserva repartidores
con pedidos pendientes aunque estén inactivos o trasladados, sin totales monetarios.
Confirmar conserva pagos atómicos e historia y devuelve sólo acuse. Recuperar con
la misma identidad/cuerpo/clave requiere lectura actual, no escritura ni caja abierta;
una clave desconocida nunca cobra. Identidad técnica, falta de lectura, cambio de actor
o revocación tras commit no entregan el resultado. Fallo de auditoría revierte el lote;
dos solicitudes concurrentes no cobran dos veces. Ninguna métrica publica el importe.

Refinamiento BDD-SC-767/768/792 — reapertura de pedido: solicitar, decidir o aplicar
devuelve acuse operativo bajo la política, sin copiar el resultado financiero guardado.
El reintento pertenece al actor original y exige lectura vigente, aunque haya perdido
escritura; otra identidad o cuerpo no recupera su acuse. La aplicación nueva mantiene
la autoridad canónica del Dueño y las compensaciones, sin editar historia. El listado
no carga before_snapshot. Revocación tras commit impide entregar el acuse; error de
auditoría previo a commit revierte toda la corrección. Tokens técnicos no usan estas rutas.

Refinamiento BDD-SC-768/792 — modificaciones de pedido: bajo política activa,
ejecutar o recuperar devuelve sólo el acuse propio, sin líneas/importes ni respuesta
histórica de envío. Reintentar requiere identidad y lectura vigentes, no permiso de
escritura. Cambiar el cuerpo con la misma clave se rechaza; si el histórico carece
de hash, sólo se permite recuperar metadata por la ruta de recuperación, nunca
ejecutar otra modificación. Una clave desconocida no produce efecto al recuperar.
Auditoría fallida revierte la modificación; revocación tras commit deniega entrega,
sin borrar el efecto ya confirmado. La consulta puntual conserva su propia autorización.

Refinamiento BDD-SC-767/768 — logs de integraciones: un administrador vigente puede
diagnosticar estado/fecha/proveedor sin recibir payload, firma, errores ni identificadores
externos libres. El Dueño recibe la misma metadata en esta lista. Otra organización,
actor inactivo o credencial técnica no consulta; filtrar por sucursal o suspender una
política previamente activada no recupera el original. La evidencia original se conserva
interna. Fallo de auditoría o revocación antes de entregar impide la respuesta.

Refinamiento BDD-SC-767/768/792 — gastos: el operador consulta metadata y su borrador
actual acreditado por un comando ejecutado; no reconstruye historial monetario por
paginación, filtros, id conocido o recuperación. Dueño/delegado con alcance expenses
mantiene los agregados autorizados. Confirmar y anular conservan retiro/compensación,
devuelven acuse propio y no revelan el result histórico. Retirar escritura permite
recuperar con lectura vigente; retirar lectura lo impide. Resolver un intento ausente
conserva el abandono terminal, mientras resolver otro objetivo no recupera un resultado.
Fallo de auditoría revierte el efecto y revocación posterior bloquea entrega, sin duplicados.
<!-- F1-06: complemento de BDD-767/768/792, sin ampliar permisos de acción. -->

Cancelación con política activa: dado un actor humano autorizado a leer y cancelar,
cuando cancela un pedido elegible, recibe sólo el acuse operativo; el importe original
permanece interno. Sin lectura vigente no se aplica el efecto. Si falla la auditoría,
no persisten cancelación ni movimientos. Si se revoca después del commit, no se entrega
el acuse; la cancelación ya confirmada permanece y puede consultarse operativamente.
Una segunda cancelación se rechaza sin duplicar liberaciones. Las restricciones de
producción y pago se mantienen, igual que la propiedad de transacción del llamador.

F1-06, complemento BDD-767/768/792: al aceptar/asignar con política activa, el actor
recibe un acuse operativo; el replay histórico no revela importe ni domicilio.
Otro actor no recupera el acuse original por conocer identificadores. La lectura
revocada impide nueva operación y recuperación; perder escritura conserva lectura
del acuse propio. Un fallo de auditoría revierte toda la aceptación/asignación.

F1-06 / BDD-767/768/792: un administrador sin concesión financiera no consulta el
historial monetario del repartidor. Un delegado sales de B sólo obtiene entregas de B
al solicitar esa sucursal; no obtiene A ni el consolidado. Revocar el grant o el
permiso administrativo impide consultas posteriores. La asignación original queda intacta.

F1-06 / BDD-767/768/792: las bandejas de los cuatro canales muestran metadata operativa
sin importes ni snapshots, incluso para Dueño. Pedir un estado o conocer un id externo
no abre historia monetaria. Sin orders.read vigente, con sucursal ajena o identidad
técnica se deniega. Revocación o error de auditoría antes de entrega impiden la respuesta.

Refinamiento BDD-767/792: con política, el lector humano de sincronización ve sólo
identificadores, checkpoint y fecha, aunque un evento histórico contenga importes o
cadenas privadas. Un token técnico no puede usar la rama humana; el gateway autorizado
conserva su transporte scoped. Revocación durante lectura o fallo de auditoría impide
entregar la respuesta; el original no se reescribe.

Refinamiento BDD-791/794: si una sucursal fue activada y luego suspendida, un cajero,
Dueño o delegado no consigue respuestas legacy monetarias ni comandos incompatibles.
Las rutas que resuelven esa política responden conflicto explícito, sin datos. Una
sucursal nunca activada conserva compatibilidad previa.
